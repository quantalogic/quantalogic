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

import json
from datetime import datetime
from io import StringIO
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from quantalogic import Agent
from quantalogic.tools.tool import Tool, ToolArgument


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
        
        with st.form(key="input_form"):
            st.markdown(f"**{question}**")
            user_input = st.text_input("Your answer:", key="input_field")
            if st.form_submit_button("Submit") and user_input:
                st.session_state.user_input = user_input
                st.rerun()
        return st.session_state.user_input

class YFinanceTool(Tool):
    """Retrieves stock market data from Yahoo Finance."""
    name: str = "yfinance_tool"
    description: str = "Fetches historical stock data"
    arguments: list[ToolArgument] = [
        ToolArgument(name="ticker", arg_type="string", description="Stock symbol", required=True),
        ToolArgument(name="start_date", arg_type="string", description="Start date (YYYY-MM-DD)", required=True),
        ToolArgument(name="end_date", arg_type="string", description="End date (YYYY-MM-DD)", required=True)
    ]

    def execute(self, ticker: str, start_date: str, end_date: str) -> str:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            if not hist.empty:
                # Reset index to make Date a column and format decimals
                df = hist.reset_index()
                # Display the table in Streamlit
                st.subheader(f"{ticker} Historical Data")
                st.dataframe(
                    df.style.format({
                        'Open': '{:.2f}',
                        'High': '{:.2f}',
                        'Low': '{:.2f}',
                        'Close': '{:.2f}',
                        'Volume': '{:,.0f}'
                    }),
                    use_container_width=True
                )
                return df.to_json(date_format='iso')
            return ""
        except Exception as e:
            return f"Data error: {str(e)}"

class VisualizationTool(Tool):
    """Generates interactive stock charts."""
    name: str = "visualization_tool"
    description: str = "Creates financial visualizations"
    arguments: list[ToolArgument] = [
        ToolArgument(name="data", arg_type="string", description="JSON historical data", required=True),
        ToolArgument(name="chart_type", arg_type="string", description="Chart style (line|candle|area)", required=False)
    ]

    def execute(self, data: str, chart_type: str = "line") -> str:
        try:
            df = pd.read_json(StringIO(data))
            df['Date'] = pd.to_datetime(df['Date'])

            if chart_type == "candle":
                fig = go.Figure(data=[go.Candlestick(
                    x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']
                )])
            elif chart_type == "area":
                fig = px.area(df, x='Date', y='Close')
                fig.update_traces(fill='tozeroy')
            else:
                fig = px.line(df, x='Date', y='Close', markers=True)

            fig.update_layout(
                template='plotly_dark',
                xaxis_rangeslider_visible=chart_type == "candle",
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
            return "Graph displayed successfully"
        except Exception as e:
            return f"Viz error: {str(e)}"

def handle_stream_chunk(event: str, data: Optional[str] = None) -> None:
    if event == "stream_chunk" and data:
        if "response" not in st.session_state:
            st.session_state.response = ""
        st.session_state.response += data
        st.markdown(f"```\n{st.session_state.response}\n```")

def track_events(event: str, data: Optional[dict] = None) -> None:
    if event == "task_think_start":
        st.session_state.current_status = st.status("🔍 Analyzing query...", expanded=True)
    elif event == "tool_execution_start":
        with st.session_state.current_status:
            tool_name = data.get('tool_name', 'Unknown tool')
            icon = "📊" if "viz" in tool_name.lower() else "💹"
            st.write(f"{icon} Executing {tool_name}")
    elif event == "task_think_end":
        st.session_state.current_status.update(label="✅ Analysis Complete", state="complete")

def main():
    st.set_page_config(page_title="Finance Suite Pro", layout="centered")
    st.title("📈 AI Financial Analyst")

    if "agent" not in st.session_state:
        st.session_state.agent = Agent(
            model_name="deepseek/deepseek-chat",
            tools=[StreamlitInputTool(), YFinanceTool(), VisualizationTool()]
        )
        
        # Configure event handlers properly
        st.session_state.agent.event_emitter.on(
            ["task_think_start", "tool_execution_start", "task_think_end"],
            track_events
        )
        st.session_state.agent.event_emitter.on(
            ["stream_chunk"],
            handle_stream_chunk
        )

    query = st.chat_input("Ask financial questions (e.g., 'Show AAPL stock from 2020-2023 as candles')")
    
    if query:
        with st.spinner("Processing market data..."):
            try:
                result = st.session_state.agent.solve_task(
                    f"Financial analysis request: {query}\n"
                )

                # Result processing
                with st.container():
                     st.markdown(f"```\n{result}\n```")

            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    import sys

    import streamlit.web.cli as stcli
    
    if st.runtime.exists():
        main()
    else:
        sys.argv = ["streamlit", "run", __file__]
        sys.exit(stcli.main())