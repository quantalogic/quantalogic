import html
import json
from datetime import datetime
from io import StringIO
from typing import Optional, Dict, ClassVar

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from quantalogic import Agent
from quantalogic.tools import DuckDuckGoSearchTool, LLMTool, SerpApiSearchTool, Tool, ToolArgument 

class StreamlitInputTool(Tool):
    """Captures user input through Streamlit interface."""

    name: str = "input_tool"
    description: str = "Gets user input through Streamlit components"
    arguments: list[ToolArgument] = [
        ToolArgument(name="question", arg_type="string", description="Prompt for user", required=True)
    ]

    def execute(self, question: str) -> str:
        if "user_input" not in st.session_state:
            st.session_state.user_input = ""

        input_container = st.container(border=True)
        with input_container:
            with st.form(key="input_form"):
                st.markdown(f"**{question.strip()}**")  # Proper bold formatting
                user_input = st.text_input("Your answer:", key="input_field")
                if st.form_submit_button("Submit") and user_input:
                    st.session_state.user_input = user_input
                    st.rerun()
        return st.session_state.user_input


class YFinanceTool(Tool):
    """Enhanced Yahoo Finance data retrieval with advanced features."""

    name: str = "yfinance_tool"
    description: str = "Fetches historical stock data with advanced interval support"
    arguments: list[ToolArgument] = [
        ToolArgument(name="ticker", arg_type="string", description="Stock symbol", required=True),
        ToolArgument(name="start_date", arg_type="string", description="Start date (YYYY-MM-DD)", required=True),
        ToolArgument(name="end_date", arg_type="string", description="End date (YYYY-MM-DD)", required=True),
        ToolArgument(
            name="interval",
            arg_type="string",
            description="Data interval (1m/2m/5m/15m/30m/60m/90m/1h/1d/5d/1wk/1mo/3mo)",
            required=False,
            default="4h"
        ),
    ]

    INTERVAL_LIMITS: ClassVar[Dict[str, str]] = {
        '1m': '7d',      # 1 minute data available for last 7 days
        '2m': '60d',     # 2 minutes
        '5m': '60d',     # 5 minutes
        '15m': '60d',    # 15 minutes
        '30m': '60d',    # 30 minutes
        '60m': '730d',   # 60 minutes
        '90m': '60d',    # 90 minutes
        '1h': '730d',    # 1 hour
        '4h': '2y',      # 4 hours
        '1d': 'max',     # 1 day
        '5d': 'max',     # 5 days
        '1wk': 'max',    # 1 week
        '1mo': 'max',    # 1 month
        '3mo': 'max'     # 3 months
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache = {}

    def _validate_interval(self, interval: str, start_date: datetime) -> str:
        """Validate and adjust the interval based on date range."""
        if interval not in self.INTERVAL_LIMITS:
            st.warning(f"Invalid interval: {interval}. Using default: 4h")
            return "4h"

        limit = self.INTERVAL_LIMITS[interval]
        if limit != 'max':
            limit_days = int(''.join(filter(str.isdigit, limit)))
            if 'y' in limit:
                limit_days *= 365
            
            date_diff = (datetime.now() - start_date).days
            if date_diff > limit_days:
                st.warning(f"Interval {interval} only supports {limit} of historical data. Adjusting interval...")
                return self._get_appropriate_interval(date_diff)
        
        return interval

    def _get_appropriate_interval(self, days: int) -> str:
        """Get appropriate interval based on date range."""
        if days <= 7:
            return '1m'
        elif days <= 60:
            return '5m'
        elif days <= 730:
            return '1h'
        else:
            return '1d'

    def _format_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format and clean the data."""
        if df.empty:
            return df
            
        # Add technical indicators
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        
        # Calculate daily returns
        df['Returns'] = df['Close'].pct_change()
        
        # Calculate volatility
        df['Volatility'] = df['Returns'].rolling(window=20).std() * (252 ** 0.5)
        
        return df

    def execute(self, ticker: str, start_date: str, end_date: str, interval: str = "4h") -> str:
        """Execute the Yahoo Finance data retrieval with enhanced features."""
        try:
            # Convert dates to datetime
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Validate interval
            validated_interval = self._validate_interval(interval, start)
            
            # Check cache
            cache_key = f"{ticker}_{start_date}_{end_date}_{validated_interval}"
            if cache_key in self.cache:
                st.info("Using cached data...")
                df = self.cache[cache_key]
            else:
                with st.spinner(f"Fetching {ticker} data with {validated_interval} interval..."):
                    stock = yf.Ticker(ticker)
                    
                    # Get historical data
                    hist = stock.history(
                        start=start_date,
                        end=end_date,
                        interval=validated_interval
                    )
                    
                    if hist.empty:
                        st.warning(f"No data available for {ticker}")
                        return ""

                    df = hist.reset_index()
                    df = self._format_data(df)
                    self.cache[cache_key] = df

            # Display data
            self._display_data(df, ticker, validated_interval)
            
            return df.to_json()

        except Exception as e:
            st.error(f"Error fetching data: {str(e)}")
            logging.error(f"YFinance error for {ticker}: {str(e)}")
            return f"Error: {str(e)}"

    def _display_data(self, df: pd.DataFrame, ticker: str, interval: str) -> None:
        """Display the data with enhanced visualization."""
        st.subheader(f"{ticker} Historical Data ({interval} interval)", divider="rainbow")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}", 
                     f"{((df['Close'].iloc[-1] / df['Close'].iloc[-2]) - 1) * 100:.2f}%")
        with col2:
            st.metric("Volume", f"{df['Volume'].iloc[-1]:,.0f}", 
                     f"{((df['Volume'].iloc[-1] / df['Volume_MA'].iloc[-1]) - 1) * 100:.2f}%")
        with col3:
            st.metric("Volatility", f"{df['Volatility'].iloc[-1]:.2%}")
        with col4:
            st.metric("Trading Days", len(df))

        # Interactive price chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Price'
        ))
        
        # Add moving averages
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['SMA_20'],
            name='SMA 20',
            line=dict(color='orange')
        ))
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['SMA_50'],
            name='SMA 50',
            line=dict(color='blue')
        ))
        
        fig.update_layout(
            title=f"{ticker} Price Chart",
            yaxis_title="Price",
            xaxis_title="Date",
            height=600
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # Data table
        st.dataframe(
            df.style.format({
                "Open": "${:.2f}",
                "High": "${:.2f}",
                "Low": "${:.2f}",
                "Close": "${:.2f}",
                "Volume": "{:,.0f}",
                "Returns": "{:.2%}",
                "Volatility": "{:.2%}"
            }),
            use_container_width=True,
            hide_index=True,
        )
