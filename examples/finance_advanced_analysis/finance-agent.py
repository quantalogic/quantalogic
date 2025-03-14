#!/usr/bin/env uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "streamlit",
#     "yfinance",
#     "pandas",
#     "plotly",
#     "quantalogic",
#     "loguru",
#     "typer",
# ]
# ///

import html
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
import typer
from loguru import logger

from examples.finance_advanced_analysis.technical_analysis import TechnicalAnalysisTool
from examples.finance_advanced_analysis.visualize import VisualizationTool
from examples.finance_advanced_analysis.yahoo_finance import YFinanceTool
from quantalogic import Agent
from quantalogic.tools import DuckDuckGoSearchTool, LLMTool, SerpApiSearchTool, Tool, ToolArgument

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
        formatted_time = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.analysis_history.append({
            "timestamp": timestamp,
            "formatted_time": formatted_time,
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
            with open(file) as f:
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

def create_sidebar(model_name: str) -> None:
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
                st.rerun()

        st.markdown("---")
        st.markdown("### 🎯 Pro Tips")
        st.info("""
        - Use specific timeframes
        - Compare multiple stocks
        - Ask for technical indicators
        - Request market sentiment
        """)
        
        # Display model information
        st.markdown("---")
        st.info(f"🤖 Using model: {model_name}")

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
    """Initialize the AI agent with necessary tools using the specified model"""
    logger.info(f"Initializing agent with model: {model_name}")
    
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

def run_app(model_name: str) -> None:
    """Run the Streamlit application with the specified model"""
    try:
        logger.info(f"Starting application with model: {model_name}")
        
        # Store model name in session state for consistency
        st.session_state.model_name = model_name
        
        setup_page_config()
        apply_custom_styles()

        # Header section
        col1, col2 = st.columns([1, 4])
        with col1:
            st.image("https://img.icons8.com/fluency/96/financial-analytics.png", width=80)
        with col2:
            st.title("🚀 QUANTALOGIC : Finance Suite Pro")
            st.markdown("*Your AI-Powered Financial Analysis Platform*")

        create_sidebar(model_name)

        # Initialize agent with specified model
        if "agent" not in st.session_state or st.session_state.agent.model_name != model_name:
            st.session_state.agent = initialize_agent(model_name)

        # Main chat interface
        st.markdown("### 💬 Ask Your Financial Questions")
        query = st.chat_input("E.g., 'Show AAPL stock analysis with SMA 50'", key="chat_input")
        
        if "example_query" in st.session_state:
            query = st.session_state.example_query
            del st.session_state.example_query

        if query:
            logger.info(f"Processing query: {query} with model: {model_name}")
            
            # Clear previous state
            for key in ["response", "chunk_container"]:
                if key in st.session_state:
                    del st.session_state[key]

            with st.spinner("🔄 Processing your request..."):
                try:
                    with st.container():
                        st.markdown("#### 🎯 Query")
                        st.info(query)
                        
                        logger.info(f"Solving task with model: {model_name}")
                        st.sidebar.info(f"🔍 Analyzing with model: {model_name}")
                        
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
                    logger.error(f"Error during analysis with model {model_name}: {str(e)}")
                    st.error("🚨 Analysis Error")
                    with st.expander("Error Details"):
                        st.exception(e)

    except Exception as e:
        logger.error(f"Application error with model {model_name}: {str(e)}")
        st.error("🚨 Application Error")
        st.exception(e)

def main(model_name: str = typer.Option(
        "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0", 
        "--model", 
        "-m", 
        help="Model name to use for the AI agent. Examples: 'deepseek/deepseek-chat', 'bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0'"
    )) -> None:
    """Finance Suite Pro - AI-Powered Financial Analysis Platform
    
    Run this application with a specific AI model.
    """
    import streamlit.web.cli as stcli
    
    # Store model name in environment for consistency
    os.environ["FINANCE_AGENT_MODEL"] = model_name
    
    if st.runtime.exists():
        run_app(model_name)
    else:
        sys.argv = ["streamlit", "run", __file__, "--", "--model", model_name]
        stcli.main()

if __name__ == "__main__":
    typer.run(main)