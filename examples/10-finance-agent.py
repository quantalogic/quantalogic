#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "streamlit",
#     "yfinance",
#     "pandas",
#     "plotly",
#     "quantalogic",
# ]
# ///

import html
from datetime import datetime
from io import StringIO
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from quantalogic import Agent
from quantalogic.tools import DuckDuckGoSearchTool, SerpApiSearchTool, Tool, ToolArgument


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


class TechnicalAnalysisTool(Tool):
    """Performs technical analysis with robust type validation and error handling."""

    name: str = "technical_analysis_tool"
    description: str = "Calculates SMA/RSI with input validation and interactive visualization"
    arguments: list[ToolArgument] = [
        ToolArgument(name="symbol", arg_type="string", description="Stock ticker symbol", required=True),
        ToolArgument(name="indicator", arg_type="string", description="Analysis type (sma/rsi/pe)", required=True),
        ToolArgument(name="period", arg_type="int", description="Lookback period (positive integer, not required for PE)", required=False),
        ToolArgument(
            name="start_date",
            arg_type="string",
            description="Start date (YYYY-MM-DD)",
            required=False,
            default=datetime.now().strftime("%Y-%m-%d"),
        ),
        ToolArgument(
            name="end_date",
            arg_type="string",
            description="End date (YYYY-MM-DD)",
            required=False,
            default=datetime.now().strftime("%Y-%m-%d"),
        ),
    ]

    def execute(self, symbol: str, indicator: str, period: int, start_date: str = None, end_date: str = None) -> str:
        """Execute technical analysis with type-safe operations"""
        try:
            # Create analysis container first for proper Streamlit context
            analysis_container = st.container(border=True)

            period = period if period is not None else 14

            with analysis_container:
                # Input validation and type conversion
                period = self._validate_period(period)
                start_date, end_date = self._validate_dates(start_date, end_date)
                symbol = symbol.upper().strip()

                st.header(f"{symbol} Technical Analysis", divider="rainbow")

                # Validate stock symbol
                stock_data = self._fetch_stock_data(symbol, start_date, end_date)
                if stock_data.empty:
                    return f"No data found for {symbol}"

                # Calculate technical indicator
                if indicator.lower() == "sma":
                    result_df = self._calculate_sma(stock_data, period)
                elif indicator.lower() == "rsi":
                    result_df = self._calculate_rsi(stock_data, period)
                elif indicator.lower() == "pe":
                    pe_ratio = self._calculate_pe_ratio(symbol)
                    st.metric(f"{symbol} PE Ratio", f"{pe_ratio:.2f}")
                    return f"Current PE Ratio for {symbol}: {pe_ratio:.2f}"
                else:
                    raise ValueError(f"Unsupported indicator: {indicator}")

                # Display results
                self._display_analysis(result_df, symbol, indicator, period)
                return f"Successfully displayed {indicator.upper()} analysis for {symbol}"

        except Exception as e:
            st.error(f"Technical analysis failed: {str(e)}")
            return f"Analysis error: {str(e)}"

    def _validate_period(self, period: int) -> int:
        """Convert and validate period parameter"""
        try:
            period = int(float(period))  # Handle numeric strings
            if period <= 0:
                raise ValueError("Period must be greater than 0")
            return period
        except (ValueError, TypeError):
            raise ValueError("Invalid period format - must be numeric")

    def _validate_dates(self, start: str, end: str) -> tuple[str, str]:
        """Validate and format date range"""
        try:
            start_dt = pd.to_datetime(start or datetime.now() - pd.DateOffset(years=1))
            end_dt = pd.to_datetime(end or datetime.now())

            if start_dt >= end_dt:
                raise ValueError("Start date must be before end date")

            return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError("Invalid date format - use YYYY-MM-DD")

    def _fetch_stock_data(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch and validate stock data"""
        with st.spinner(f"Fetching {symbol} data..."):
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(start=start, end=end)

                if hist.empty:
                    st.warning(f"No historical data found for {symbol}")
                    return pd.DataFrame()

                return hist.reset_index()
            except Exception as e:
                raise ValueError(f"Data fetch failed: {str(e)}")

    def _calculate_sma(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate Simple Moving Average"""
        with st.spinner(f"Calculating {period}-day SMA..."):
            df["SMA"] = df["Close"].rolling(window=period).mean()
            return df[["Date", "Close", "SMA"]].dropna()

    def _calculate_rsi(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calculate Relative Strength Index with safe division"""
        with st.spinner(f"Calculating {period}-day RSI..."):
            delta = df["Close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)

            avg_gain = gain.rolling(period).mean()
            avg_loss = loss.rolling(period).mean()

            # Prevent division by zero
            avg_loss = avg_loss.replace(0.0, 1e-10)
            rs = avg_gain / avg_loss

            df["RSI"] = 100 - (100 / (1 + rs))
            return df[["Date", "Close", "RSI"]].dropna()

    def _calculate_pe_ratio(self, symbol: str) -> float:
        """Calculate Price-to-Earnings ratio for given stock symbol"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            pe_ratio = info.get('trailingPE', info.get('forwardPE', None))
            if pe_ratio is None:
                raise ValueError("PE ratio data not available")
            return float(pe_ratio)
        except Exception as e:
            raise ValueError(f"Failed to calculate PE ratio: {str(e)}")

    def _display_analysis(self, df: pd.DataFrame, symbol: str, indicator: str, period: int) -> None:
        """Display interactive visualization and data table"""
        col1, col2 = st.columns([3, 1])

        period = int(period)

        with col1:
            fig = go.Figure()
            line_color = "#00FFAA" if indicator == "sma" else "#FFAA00"

            # Price trace
            fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="Price", line=dict(color="#FFFFFF", width=1)))

            # Indicator trace
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df[indicator.upper()],
                    name=f"{indicator.upper()} {period}",
                    line=dict(color=line_color, width=2),
                )
            )

            # RSI-specific elements
            if indicator.strip().lower() == "rsi":
                fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.2)", line_width=0)
                fig.add_hline(y=30, line_dash="dash", line_color="red")
                fig.add_hline(y=70, line_dash="dash", line_color="red")

            fig.update_layout(
                template="plotly_dark",
                title=f"{symbol} {indicator.upper()} Analysis",
                hovermode="x unified",
                height=500,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Latest Values", divider="gray")
            display_df = df.tail(10).copy()
            display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")

            st.dataframe(
                display_df.style.format({"Close": "{:.2f}", indicator.upper(): "{:.2f}"}).applymap(
                    lambda x: self._style_indicator(x, indicator, display_df["Close"].iloc[-1]),
                    subset=[indicator.upper()],
                ),
                hide_index=True,
                height=500,
            )

    def _style_indicator(self, value: float, indicator: str, last_close: float) -> str:
        """Apply conditional formatting to indicator values"""
        if indicator == "rsi":
            if value < 30:
                return "color: #4CAF50"
            if value > 70:
                return "color: #FF5722"
        elif indicator == "sma":
            if value > last_close:
                return "color: #4CAF50"
            if value < last_close:
                return "color: #FF5722"
        return ""


class YFinanceTool(Tool):
    """Retrieves stock market data from Yahoo Finance."""

    name: str = "yfinance_tool"
    description: str = "Fetches historical stock data"
    arguments: list[ToolArgument] = [
        ToolArgument(name="ticker", arg_type="string", description="Stock symbol", required=True),
        ToolArgument(name="start_date", arg_type="string", description="Start date (YYYY-MM-DD)", required=True),
        ToolArgument(name="end_date", arg_type="string", description="End date (YYYY-MM-DD)", required=True),
    ]

    def execute(self, ticker: str, start_date: str, end_date: str) -> str:
        try:
            with st.spinner(f"Fetching {ticker} data..."):
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_date, end=end_date)
                if hist.empty:
                    st.warning(f"No data for {ticker}")
                    return ""

                df = hist.reset_index()
                st.subheader(f"{ticker} Historical Data", divider="rainbow")
                st.dataframe(
                    df.style.format(
                        {"Open": "{:.2f}", "High": "{:.2f}", "Low": "{:.2f}", "Close": "{:.2f}", "Volume": "{:,.0f}"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
                return df.to_json()
        except Exception as e:
            st.error(f"Data error: {str(e)}")
            return f"Error: {str(e)}"


class VisualizationTool(Tool):
    """Generates interactive stock charts."""

    name: str = "visualization_tool"
    description: str = "Creates financial visualizations"
    arguments: list[ToolArgument] = [
        ToolArgument(name="data", arg_type="string", description="JSON historical data", required=True),
        ToolArgument(
            name="chart_type", arg_type="string", description="Chart style (line|candle|area)", required=False
        ),
        ToolArgument(name="caption", arg_type="string", description="Chart caption text", required=False),
    ]

    def execute(self, data: str, chart_type: str = "line", caption: Optional[str] = None) -> str:
        try:
            viz_container = st.container(border=True)
            with viz_container:
                df = pd.read_json(StringIO(data))
                df["Date"] = pd.to_datetime(df["Date"])

                st.subheader("Market Data Visualization", divider="rainbow")
                fig = go.Figure()

                if chart_type == "candle":
                    fig.add_trace(
                        go.Candlestick(x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"])
                    )
                elif chart_type == "area":
                    fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], fill="tozeroy", line=dict(color="#00FFAA")))
                else:
                    fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], line=dict(color="#FFAA00"), name="Price"))

                fig.update_layout(
                    template="plotly_dark",
                    title=caption or "Price Chart",
                    xaxis_rangeslider_visible=chart_type == "candle",
                    height=500,
                    margin=dict(l=20, r=20, t=60, b=20),
                )
                st.plotly_chart(fig, use_container_width=True)
                return "Visualization created"
        except Exception as e:
            st.error(f"Visualization error: {str(e)}")
            return f"Error: {str(e)}"


def handle_stream_chunk(event: str, data: Optional[str] = None) -> None:
    """Handle streaming token chunks with proper formatting and display"""
    if event == "stream_chunk" and data:
        if "response" not in st.session_state:
            st.session_state.response = ""
            st.session_state.chunk_container = st.empty()
            
        # Append new chunk and update display
        st.session_state.response += data
        
        # Create formatted display with syntax highlighting
        formatted_response = st.session_state.response.replace("\n", "  \n")
        with st.session_state.chunk_container.container():
            st.code(formatted_response, language="python")


def track_events(event: str, data: Optional[dict] = None) -> None:
    if event == "task_think_start":
        st.session_state.current_status = st.status("🔍 Analyzing query...", expanded=False)
    elif event == "tool_execution_start":
        tool_name = data.get("tool_name", "Unknown tool")
        icon = "📊" if "viz" in tool_name.lower() else "💹"
        st.toast(f"{icon} Executing {tool_name}", icon="⏳")
    elif event == "task_think_end":
        if "current_status" in st.session_state:
            st.session_state.current_status.update(label="✅ Analysis Complete", state="complete")
    elif event == "tool_execution_end":
        tool_name = data.get("tool_name", "")
        if tool_name == "llm_tool":
            if "chunk_container" in st.session_state:
                st.session_state.chunk_container.empty()
                del st.session_state.chunk_container
            if "response" in st.session_state:
                del st.session_state.response


def main():
    model_name = "deepseek/deepseek-chat"
    st.set_page_config(page_title="Finance Suite Pro", layout="wide")
    st.title("📈 AI Financial Analyst")

    # Initialize agent with tools
    if "agent" not in st.session_state:
        st.session_state.agent = Agent(
            model_name=model_name,
            tools=[
                StreamlitInputTool(),
                YFinanceTool(),
                VisualizationTool(),
                TechnicalAnalysisTool(),
                DuckDuckGoSearchTool(),
                SerpApiSearchTool(),
            ],
        )
        st.session_state.agent.event_emitter.on(
            [
                "task_think_start",
                "tool_execution_start",
                "task_think_end",
                "tool_execution_end",
                "error_max_iterations_reached",
            ],
            track_events,
        )
        st.session_state.agent.event_emitter.on(["stream_chunk"], handle_stream_chunk)

    # Chat interface
    query = st.chat_input("Ask financial questions (e.g., 'Show AAPL stock analysis with SMA 50')")

    if query:


        with st.spinner("Processing request..."):
            try:
                response_container = st.container(border=True)
                with response_container:
                    result = st.session_state.agent.solve_task(f"User query: {query}\n")

                    # Display formatted analysis results
                    st.subheader("📊 Analysis Results", divider="rainbow")
                    st.markdown("#### Key Findings:")
                    st.markdown(html.escape(result))

            except Exception as e:
                st.error(f"Processing error: {str(e)}")
                st.exception(e)

        # Reset session for fresh instance on next query
        del st.session_state.agent


if __name__ == "__main__":
    import sys

    import streamlit.web.cli as stcli

    if st.runtime.exists():
        main()
    else:
        sys.argv = ["streamlit", "run", __file__]
        sys.exit(stcli.main())
