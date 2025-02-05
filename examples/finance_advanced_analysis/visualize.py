import html
import json
from datetime import datetime
from io import StringIO
from typing import Optional, Dict, Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf
import numpy as np

from quantalogic import Agent
from quantalogic.tools import DuckDuckGoSearchTool, LLMTool, SerpApiSearchTool, Tool, ToolArgument 


class VisualizationTool(Tool):
    """Advanced financial visualization tool with multiple chart types and technical indicators."""

    name: str = "visualization_tool"
    description: str = "Creates sophisticated financial visualizations"
    arguments: list[ToolArgument] = [
        ToolArgument(name="data", arg_type="string", description="JSON historical data", required=True),
        ToolArgument(
            name="chart_type", 
            arg_type="string", 
            description="Chart style (line|candle|area|volume|ohlc|advanced)", 
            required=False
        ),
        ToolArgument(name="caption", arg_type="string", description="Chart caption text", required=False),
        ToolArgument(
            name="indicators",
            arg_type="string",
            description="JSON string of technical indicators to display",
            required=False
        ),
    ]

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate technical indicators for the dataset."""
        indicators = {}
        
        # Calculate moving averages
        indicators['SMA20'] = df['Close'].rolling(window=20).mean()
        indicators['SMA50'] = df['Close'].rolling(window=50).mean()
        indicators['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        
        # Calculate Bollinger Bands
        sma20 = df['Close'].rolling(window=20).mean()
        std20 = df['Close'].rolling(window=20).std()
        indicators['BB_Upper'] = sma20 + (std20 * 2)
        indicators['BB_Lower'] = sma20 - (std20 * 2)
        
        # Calculate RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        indicators['RSI'] = 100 - (100 / (1 + rs))
        
        return indicators

    def _create_advanced_chart(self, df: pd.DataFrame, indicators: Dict[str, pd.Series]) -> go.Figure:
        """Create an advanced chart with multiple subplots."""
        fig = make_subplots(
            rows=3, 
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.6, 0.2, 0.2],
            subplot_titles=('Price & Indicators', 'Volume', 'RSI')
        )

        # Main price chart
        candlestick = go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='OHLC',
            showlegend=True
        )
        fig.add_trace(candlestick, row=1, col=1)

        # Add indicators
        colors = {'SMA20': '#FF9900', 'SMA50': '#00FF00', 'EMA20': '#00FFFF'}
        for name, color in colors.items():
            fig.add_trace(
                go.Scatter(
                    x=df['Date'],
                    y=indicators[name],
                    name=name,
                    line=dict(color=color, width=1),
                ),
                row=1, col=1
            )

        # Bollinger Bands
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=indicators['BB_Upper'],
                name='BB Upper',
                line=dict(color='rgba(255,255,255,0.5)', dash='dash'),
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=indicators['BB_Lower'],
                name='BB Lower',
                line=dict(color='rgba(255,255,255,0.5)', dash='dash'),
                fill='tonexty'
            ),
            row=1, col=1
        )

        # Volume chart
        colors = np.where(df['Close'] >= df['Open'], '#00FF00', '#FF0000')
        fig.add_trace(
            go.Bar(
                x=df['Date'],
                y=df['Volume'],
                name='Volume',
                marker_color=colors,
                opacity=0.7
            ),
            row=2, col=1
        )

        # RSI
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=indicators['RSI'],
                name='RSI',
                line=dict(color='#FF00FF')
            ),
            row=3, col=1
        )
        
        # Add RSI levels
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

        return fig

    def _apply_layout(self, fig: go.Figure, title: str, chart_type: str) -> None:
        """Apply consistent layout styling to the chart."""
        fig.update_layout(
            template="plotly_dark",
            title=dict(
                text=title,
                x=0.5,
                xanchor='center',
                font=dict(size=24, color='white')
            ),
            xaxis_rangeslider_visible=chart_type in ['candle', 'ohlc'],
            height=800,
            margin=dict(l=20, r=20, t=60, b=20),
            showlegend=True,
            legend=dict(
                bgcolor='rgba(0,0,0,0.5)',
                bordercolor='white',
                borderwidth=1,
                font=dict(color='white')
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)')
        )
        
        # Update axes styling
        fig.update_xaxes(showline=True, linewidth=1, linecolor='white', mirror=True)
        fig.update_yaxes(showline=True, linewidth=1, linecolor='white', mirror=True)

    def execute(self, data: str, chart_type: str = "candle", caption: Optional[str] = None,
                indicators: Optional[str] = None) -> str:
        try:
            viz_container = st.container(border=True)
            with viz_container:
                df = pd.read_json(StringIO(data))
                df["Date"] = pd.to_datetime(df["Date"])

                st.subheader("📊 Advanced Market Analysis", divider="rainbow")
                
                # Calculate indicators
                technical_indicators = self._calculate_indicators(df)

                if chart_type == "advanced":
                    fig = self._create_advanced_chart(df, technical_indicators)
                else:
                    fig = go.Figure()
                    
                    if chart_type == "candle":
                        fig.add_trace(
                            go.Candlestick(
                                x=df["Date"],
                                open=df["Open"],
                                high=df["High"],
                                low=df["Low"],
                                close=df["Close"],
                                increasing_line_color='#00FF00',
                                decreasing_line_color='#FF0000'
                            )
                        )
                    elif chart_type == "ohlc":
                        fig.add_trace(
                            go.Ohlc(
                                x=df["Date"],
                                open=df["Open"],
                                high=df["High"],
                                low=df["Low"],
                                close=df["Close"],
                                increasing_line_color='#00FF00',
                                decreasing_line_color='#FF0000'
                            )
                        )
                    elif chart_type == "area":
                        fig.add_trace(
                            go.Scatter(
                                x=df["Date"],
                                y=df["Close"],
                                fill="tozeroy",
                                line=dict(color="#00FFAA"),
                                name="Price"
                            )
                        )
                    elif chart_type == "volume":
                        colors = np.where(df['Close'] >= df['Open'], '#00FF00', '#FF0000')
                        fig.add_trace(
                            go.Bar(
                                x=df["Date"],
                                y=df["Volume"],
                                marker_color=colors,
                                name="Volume"
                            )
                        )
                    else:  # line chart
                        fig.add_trace(
                            go.Scatter(
                                x=df["Date"],
                                y=df["Close"],
                                line=dict(color="#FFAA00", width=2),
                                name="Price"
                            )
                        )

                self._apply_layout(fig, caption or "Market Analysis", chart_type)
                
                # Display stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        "Current Price",
                        f"${df['Close'].iloc[-1]:.2f}",
                        f"{((df['Close'].iloc[-1] - df['Close'].iloc[-2])/df['Close'].iloc[-2]*100):.2f}%"
                    )
                with col2:
                    st.metric(
                        "Volume",
                        f"{df['Volume'].iloc[-1]:,.0f}",
                        f"{((df['Volume'].iloc[-1] - df['Volume'].iloc[-2])/df['Volume'].iloc[-2]*100):.2f}%"
                    )
                with col3:
                    st.metric(
                        "RSI",
                        f"{technical_indicators['RSI'].iloc[-1]:.2f}",
                        None
                    )
                
                st.plotly_chart(fig, use_container_width=True)
                return "Visualization created successfully"
                
        except Exception as e:
            st.error(f"Visualization error: {str(e)}")
            return f"Error: {str(e)}"
