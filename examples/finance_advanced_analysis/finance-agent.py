#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "streamlit",
#     "yfinance",
#     "pandas",
#     "plotly",
#     "quantalogic",
#     "loguru",
# ]
# ///

import html
import json
from datetime import datetime
from io import StringIO
from typing import Optional, Dict, List
from pathlib import Path
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from loguru import logger

from quantalogic import Agent
from quantalogic.tools import DuckDuckGoSearchTool, SerpApiSearchTool, Tool, ToolArgument, LLMTool

from examples.finance_advanced_analysis.technical_analysis import TechnicalAnalysisTool
from examples.finance_advanced_analysis.yahoo_finance import YFinanceTool
from examples.finance_advanced_analysis.visualize import VisualizationTool

# Configure logger
logger.add("finance_agent.log", rotation="500 MB")

def setup_page_config() -> None:
    """Configure Streamlit page settings and styling"""
    st.set_page_config(
        page_title="Finance Suite Pro",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': 'https://github.com/yourusername/finance-suite-pro',
            'Report a bug': "https://github.com/yourusername/finance-suite-pro/issues",
            'About': "# Finance Suite Pro\nYour AI-Powered Financial Analysis Platform"
        }
    )

def apply_custom_styles() -> None:
    """Apply custom CSS styles for better UI"""
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(180deg, #ffffff 0%, #ffffff 100%);
            color: #000000;
        }
        .css-1d391kg {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        .stButton>button {
            background: linear-gradient(45deg, #2e7d32 30%, #388e3c 90%);
            color: white;
            border-radius: 25px;
            padding: 10px 25px;
            font-weight: 600;
            border: none;
            transition: all 0.3s ease;
            box-shadow: 0 3px 5px rgba(0,0,0,0.2);
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        .css-1v0mbdj.etr89bj1 {
            margin-top: 20px;
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(255, 255, 255, 0.02);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px;
            padding: 10px 20px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }
        </style>
    """, unsafe_allow_html=True)

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

        input_container = st.container()
        with input_container:
            with st.form(key="input_form"):
                st.markdown(f"**{question.strip()}**")
                user_input = st.text_input("Your answer:", key="input_field")
                if st.form_submit_button("Submit", use_container_width=True) and user_input:
                    st.session_state.user_input = user_input
                    st.rerun()
        return st.session_state.user_input

def save_analysis(query: str, result: str) -> None:
    """Save analysis results to a file with timestamp"""
    try:
        # Create analyses directory if it doesn't exist
        analyses_dir = Path("analyses")
        analyses_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_{timestamp}.md"
        
        with open(analyses_dir / filename, "w") as f:
            f.write(f"# Analysis Query\n{query}\n\n# Results\n{result}")
            
        # Update analysis history in session state
        if "analysis_history" not in st.session_state:
            st.session_state.analysis_history = []
        st.session_state.analysis_history.append({
            "timestamp": timestamp,
            "query": query,
            "result": result,
            "filename": filename
        })
        
        logger.info(f"Analysis saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving analysis: {str(e)}")

def load_analysis_history() -> List[Dict]:
    """Load all saved analyses"""
    try:
        analyses_dir = Path("analyses")
        if not analyses_dir.exists():
            return []
            
        history = []
        for file in sorted(analyses_dir.glob("analysis_*.md"), reverse=True):
            with open(file, "r") as f:
                content = f.read()
                query_section = content.split("# Results")[0].replace("# Analysis Query\n", "").strip()
                result_section = content.split("# Results")[1].strip()
                
                timestamp = file.stem.replace("analysis_", "")
                formatted_time = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                
                history.append({
                    "timestamp": timestamp,
                    "formatted_time": formatted_time,
                    "query": query_section,
                    "result": result_section,
                    "filename": file.name
                })
        return history
    except Exception as e:
        logger.error(f"Error loading analysis history: {str(e)}")
        return []

def create_sidebar() -> None:
    """Create and populate the sidebar with controls and examples"""
    with st.sidebar:
        st.header("📊 Analysis Controls")
        st.markdown("---")
        
        # Analysis History Section
        st.subheader("📜 Analysis History")
        if "analysis_history" not in st.session_state:
            st.session_state.analysis_history = load_analysis_history()
            
        if st.session_state.analysis_history:
            for analysis in st.session_state.analysis_history[:5]:  # Show last 5 analyses
                with st.expander(f"📊 {analysis['formatted_time']}"):
                    st.markdown("**Query:**")
                    st.info(analysis['query'])
                    st.markdown("**Results:**")
                    st.markdown(analysis['result'])
        else:
            st.info("No previous analyses found")
            
        st.markdown("---")
        
        # Example Queries Section
        st.subheader("📝 Example Queries")
        example_queries = [
            "Show AAPL stock analysis with SMA 50",
            "Compare TSLA and NVDA performance",
            "Analyze market sentiment for crypto",
            "Show technical indicators for MSFT"
        ]
        for query in example_queries:
            if st.button(query, key=f"example_{query}", use_container_width=True):
                st.session_state.example_query = query
                st.experimental_rerun()

        st.markdown("---")
        st.markdown("### 🎯 Pro Tips")
        st.info("""
        - Use specific timeframes
        - Compare multiple stocks
        - Ask for technical indicators
        - Request market sentiment
        """)

def handle_stream_chunk(event: str, data: Optional[str] = None) -> None:
    """Handle streaming token chunks with proper formatting and display"""
    if event == "stream_chunk" and data:
        if "response" not in st.session_state:
            st.session_state.response = ""
            st.session_state.chunk_container = st.empty()
            
        st.session_state.response += data
        formatted_response = st.session_state.response.replace("\n", "  \n")
        with st.session_state.chunk_container.container():
            st.code(formatted_response, language="python")

def track_events(event: str, data: Optional[Dict] = None) -> None:
    """Track and display agent events"""
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

def initialize_agent(model_name: str) -> Agent:
    """Initialize the AI agent with necessary tools"""
    agent = Agent(
        model_name=model_name,
        tools=[
            StreamlitInputTool(),
            YFinanceTool(),
            VisualizationTool(),
            TechnicalAnalysisTool(),
            LLMTool(model_name=model_name, on_token=handle_stream_chunk),
            DuckDuckGoSearchTool(),
            SerpApiSearchTool(),
        ],
    )
    agent.event_emitter.on(
        [
            "task_think_start",
            "tool_execution_start",
            "task_think_end",
            "tool_execution_end",
            "error_max_iterations_reached",
        ],
        track_events,
    )
    agent.event_emitter.on(["stream_chunk"], handle_stream_chunk)
    return agent

def main() -> None:
    """Main application entry point"""
    try:
        # model_name = "deepseek/deepseek-chat"
        model_name = "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
        #model_name = "openrouter/deepseek/deepseek-chat"
        
        setup_page_config()
        apply_custom_styles()

        # Header section
        col1, col2 = st.columns([1, 4])
        with col1:
            st.image("https://img.icons8.com/fluency/96/financial-analytics.png", width=80)
        with col2:
            st.title("🚀 QUANTALOGIC : Finance Suite Pro")
            st.markdown("*Your AI-Powered Financial Analysis Platform*")

        create_sidebar()

        # Initialize agent
        if "agent" not in st.session_state:
            st.session_state.agent = initialize_agent(model_name)

        # Main chat interface
        st.markdown("### 💬 Ask Your Financial Questions")
        query = st.chat_input("E.g., 'Show AAPL stock analysis with SMA 50'", key="chat_input")
        
        if "example_query" in st.session_state:
            query = st.session_state.example_query
            del st.session_state.example_query

        if query:
            logger.info(f"Processing query: {query}")
            
            # Clear previous state
            for key in ["response", "chunk_container"]:
                if key in st.session_state:
                    del st.session_state[key]

            with st.spinner("🔄 Processing your request..."):
                try:
                    with st.container():
                        st.markdown("#### 🎯 Query")
                        st.info(query)
                        
                        result = st.session_state.agent.solve_task(f"User query: {query}\n")
                        logger.info("Analysis completed successfully")

                        # Save analysis
                        save_analysis(query, result)

                        st.markdown("---")
                        st.subheader("📊 Analysis Results", divider="rainbow")
                        
                        tab1, tab2 = st.tabs(["📈 Key Findings", "🔍 Detailed Analysis"])
                        
                        with tab1:
                            st.markdown(html.escape(result))
                        with tab2:
                            st.markdown("Detailed technical analysis and additional insights will appear here when available.")

                except Exception as e:
                    logger.error(f"Error during analysis: {str(e)}")
                    st.error("🚨 Analysis Error")
                    with st.expander("Error Details"):
                        st.exception(e)

            del st.session_state.agent

    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error("🚨 Application Error")
        st.exception(e)

if __name__ == "__main__":
    import sys
    import streamlit.web.cli as stcli

    if st.runtime.exists():
        main()
    else:
        sys.argv = ["streamlit", "run", __file__]
        sys.exit(stcli.main())
