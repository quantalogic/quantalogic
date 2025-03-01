"""Advanced Financial Analysis LLM Tool combining market data with AI insights."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, ClassVar, Dict, List, Optional, Union

import pandas as pd
import ta
from loguru import logger
from pydantic import ConfigDict, Field

from quantalogic.agent import Agent
from quantalogic.event_emitter import EventEmitter
from quantalogic.generative_model import GenerativeModel, Message
from quantalogic.tools.finance.alpha_vantage_tool import AlphaVantageTool
from quantalogic.tools.finance.ccxt_tool import CCXTTool
from quantalogic.tools.tool import Tool, ToolArgument


@dataclass
class StrategyResult:
    """Container for strategy analysis results."""
    name: str
    signals: Dict[str, str]  # buy/sell/hold signals
    confidence: float
    reasoning: str
    metrics: Dict[str, float]
    timestamp: datetime

@dataclass
class MarketAnalysis:
    """Container for comprehensive market analysis."""
    symbol: str
    asset_type: str
    timeframe: str
    current_price: float
    analysis_timestamp: datetime
    technical_signals: Dict[str, Dict[str, Union[str, float]]]
    fundamental_data: Optional[Dict[str, Any]] = None
    market_sentiment: Optional[Dict[str, float]] = None
    strategy_results: List[StrategyResult] = None
    ai_insights: Optional[Dict[str, Any]] = None

class FinanceLLMTool(Tool):
    """Advanced financial analysis tool combining market data with AI insights."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="finance_llm_tool")
    description: str = Field(
        default=(
            "Advanced financial analysis tool that combines real-time market data, "
            "technical analysis, fundamental analysis, and AI-powered insights for "
            "stocks, cryptocurrencies, and indices. Provides detailed strategy analysis "
            "and market insights using state-of-the-art language models."
        )
    )

    STRATEGIES: ClassVar[List[str]] = [
        "trend_following",
        "mean_reversion",
        "breakout",
        "momentum",
        "volume_analysis",
        "sentiment_based",
        "multi_timeframe",
        "adaptive_momentum",
        "volatility_based",
        "correlation_based"
    ]

    TIMEFRAMES: ClassVar[List[str]] = [
        "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"
    ]

    arguments: list = Field(
        default=[
            ToolArgument(
                name="symbols",
                arg_type="list",
                description="List of trading symbols to analyze",
                required=True,
                example="['BTC/USDT', 'AAPL', 'SPY']"
            ),
            ToolArgument(
                name="asset_types",
                arg_type="list",
                description="List of asset types (crypto/stock/index)",
                required=True,
                example="['crypto', 'stock', 'index']"
            ),
            ToolArgument(
                name="strategies",
                arg_type="list",
                description="List of trading strategies to analyze",
                required=False,
                default="['trend_following', 'momentum', 'multi_timeframe']"
            ),
            ToolArgument(
                name="timeframes",
                arg_type="list",
                description="List of timeframes to analyze",
                required=False,
                default="['1h', '4h', '1d']"
            ),
            ToolArgument(
                name="analysis_types",
                arg_type="list",
                description="Types of analysis to perform (technical/fundamental/sentiment/ai)",
                required=False,
                default="['technical', 'sentiment', 'ai']"
            ),
            ToolArgument(
                name="temperature",
                arg_type="string",
                description="LLM temperature for analysis generation",
                required=False,
                default="0.3"
            )
        ]
    )

    model_name: str = Field(..., description="The name of the language model to use")
    system_prompt: str = Field(
        default=(
            "You are an expert financial analyst and trading strategist with deep knowledge of:"
            "\n- Technical Analysis and Chart Patterns"
            "\n- Fundamental Analysis and Valuation Methods"
            "\n- Market Psychology and Sentiment Analysis"
            "\n- Risk Management and Position Sizing"
            "\n- Multi-Timeframe Analysis"
            "\n- Inter-market Analysis and Correlations"
            "\n- Machine Learning in Trading"
            "\nYour role is to analyze market data and provide detailed, actionable insights while:"
            "\n- Maintaining objectivity and avoiding bias"
            "\n- Providing clear reasoning for all conclusions"
            "\n- Highlighting potential risks and limitations"
            "\n- Considering multiple timeframes and perspectives"
            "\n- Adapting analysis to market conditions"
            "\n- Following proper risk management principles"
        )
    )

    def __init__(
        self,
        model_name: str,
        system_prompt: str | None = None,
        on_token: Callable | None = None,
        name: str = "finance_llm_tool",
        generative_model: GenerativeModel | None = None,
        event_emitter: EventEmitter | None = None,
    ):
        """Initialize the Finance LLM tool."""
        super().__init__(
            **{
                "model_name": model_name,
                "system_prompt": system_prompt or self.system_prompt,
                "on_token": on_token,
                "name": name,
                "generative_model": generative_model,
                "event_emitter": event_emitter,
            }
        )
        
        # Initialize market data tools
        self.ccxt_tool = CCXTTool()
        self.alpha_vantage_tool = AlphaVantageTool()
        
        # Initialize the generative model
        self.model_post_init(None)

    async def _analyze_technical_indicators(self, df: pd.DataFrame) -> Dict[str, Dict[str, Union[str, float]]]:
        """Analyze technical indicators and generate signals."""
        signals = {}
        
        try:
            # Calculate indicators
            df['sma_20'] = ta.trend.sma_indicator(df['close'], 20)
            df['sma_50'] = ta.trend.sma_indicator(df['close'], 50)
            df['sma_200'] = ta.trend.sma_indicator(df['close'], 200)
            df['rsi'] = ta.momentum.rsi(df['close'])
            df['macd'] = ta.trend.macd_diff(df['close'])
            df['bbands_upper'] = ta.volatility.bollinger_hband(df['close'])
            df['bbands_lower'] = ta.volatility.bollinger_lband(df['close'])
            
            # Generate signals
            signals['trend'] = {
                'signal': 'buy' if df['sma_20'].iloc[-1] > df['sma_50'].iloc[-1] else 'sell',
                'strength': abs(df['sma_20'].iloc[-1] - df['sma_50'].iloc[-1]) / df['close'].iloc[-1]
            }
            
            signals['momentum'] = {
                'signal': 'buy' if df['rsi'].iloc[-1] < 30 else 'sell' if df['rsi'].iloc[-1] > 70 else 'hold',
                'strength': abs(50 - df['rsi'].iloc[-1]) / 50
            }
            
            signals['macd'] = {
                'signal': 'buy' if df['macd'].iloc[-1] > 0 else 'sell',
                'strength': abs(df['macd'].iloc[-1])
            }
            
            return signals
            
        except Exception as e:
            logger.error(f"Error analyzing technical indicators: {e}")
            raise

    async def _analyze_strategy(
        self,
        df: pd.DataFrame,
        strategy: str,
        timeframe: str
    ) -> StrategyResult:
        """Analyze market data using a specific strategy."""
        try:
            # Prepare strategy prompt
            strategy_prompt = self._get_strategy_prompt(strategy, df, timeframe)
            
            # Get AI analysis
            response = await self.generative_model.chat_completion(
                messages=[
                    Message(role="system", content=self.system_prompt),
                    Message(role="user", content=strategy_prompt)
                ],
                temperature=0.3
            )
            
            # Parse response
            analysis = json.loads(response.content)
            
            return StrategyResult(
                name=strategy,
                signals=analysis['signals'],
                confidence=analysis['confidence'],
                reasoning=analysis['reasoning'],
                metrics=analysis['metrics'],
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error analyzing strategy {strategy}: {e}")
            raise

    def _get_strategy_prompt(self, strategy: str, df: pd.DataFrame, timeframe: str) -> str:
        """Generate strategy-specific analysis prompt."""
        base_prompt = (
            f"Analyze the following market data using the {strategy} strategy on {timeframe} timeframe. "
            "Provide analysis in JSON format with the following structure:\n"
            "{\n"
            '  "signals": {"primary": "buy/sell/hold", "secondary": "string"},\n'
            '  "confidence": float between 0 and 1,\n'
            '  "reasoning": "detailed explanation",\n'
            '  "metrics": {"risk_reward": float, "probability": float}\n'
            "}\n\n"
            "Market Data Summary:\n"
        )
        
        # Add strategy-specific data points
        if strategy == "trend_following":
            base_prompt += (
                f"Current Price: {df['close'].iloc[-1]}\n"
                f"SMA20: {df['sma_20'].iloc[-1]}\n"
                f"SMA50: {df['sma_50'].iloc[-1]}\n"
                f"SMA200: {df['sma_200'].iloc[-1]}\n"
            )
        elif strategy == "momentum":
            base_prompt += (
                f"RSI: {df['rsi'].iloc[-1]}\n"
                f"MACD: {df['macd'].iloc[-1]}\n"
                f"Recent Price Change: {(df['close'].iloc[-1] / df['close'].iloc[-5] - 1) * 100}%\n"
            )
        
        return base_prompt

    async def execute(self, agent: Agent, **kwargs) -> Dict[str, MarketAnalysis]:
        """Execute comprehensive financial analysis."""
        try:
            symbols = kwargs['symbols']
            asset_types = kwargs['asset_types']
            strategies = kwargs.get('strategies', ['trend_following', 'momentum'])
            timeframes = kwargs.get('timeframes', ['1h', '4h', '1d'])
            analysis_types = kwargs.get('analysis_types', ['technical', 'sentiment', 'ai'])
            
            results = {}
            
            for symbol, asset_type in zip(symbols, asset_types):
                # Fetch market data
                if asset_type == 'crypto':
                    market_data = await self.ccxt_tool.execute(
                        agent=agent,
                        symbols=[symbol],
                        exchanges=['binance'],
                        timeframe='1h'
                    )
                else:
                    market_data = await self.alpha_vantage_tool.execute(
                        agent=agent,
                        symbols=[symbol],
                        asset_types=[asset_type],
                        data_types=['daily', 'fundamental']
                    )
                
                # Process each timeframe
                for timeframe in timeframes:
                    df = pd.DataFrame(market_data[symbol]['market_data'])
                    
                    # Technical Analysis
                    if 'technical' in analysis_types:
                        technical_signals = await self._analyze_technical_indicators(df)
                    else:
                        technical_signals = None
                    
                    # Strategy Analysis
                    strategy_results = []
                    for strategy in strategies:
                        result = await self._analyze_strategy(df, strategy, timeframe)
                        strategy_results.append(result)
                    
                    # AI Insights
                    if 'ai' in analysis_types:
                        ai_prompt = (
                            f"Analyze {symbol} on {timeframe} timeframe considering:\n"
                            f"1. Current market conditions\n"
                            f"2. Technical signals: {technical_signals}\n"
                            f"3. Strategy results: {strategy_results}\n"
                            "Provide insights in JSON format with:\n"
                            "- Overall market outlook\n"
                            "- Key levels to watch\n"
                            "- Risk factors\n"
                            "- Trading opportunities"
                        )
                        
                        ai_response = await self.generative_model.chat_completion(
                            messages=[
                                Message(role="system", content=self.system_prompt),
                                Message(role="user", content=ai_prompt)
                            ],
                            temperature=float(kwargs.get('temperature', 0.3))
                        )
                        
                        ai_insights = json.loads(ai_response.content)
                    else:
                        ai_insights = None
                    
                    # Combine all analysis
                    results[f"{symbol}_{timeframe}"] = MarketAnalysis(
                        symbol=symbol,
                        asset_type=asset_type,
                        timeframe=timeframe,
                        current_price=df['close'].iloc[-1],
                        analysis_timestamp=datetime.now(),
                        technical_signals=technical_signals,
                        fundamental_data=market_data[symbol].get('fundamental_data'),
                        market_sentiment=market_data[symbol].get('news_sentiment'),
                        strategy_results=strategy_results,
                        ai_insights=ai_insights
                    )
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing financial analysis: {e}")
            raise

    def validate_arguments(self, **kwargs) -> bool:
        """Validate the provided arguments."""
        try:
            required_args = [arg.name for arg in self.arguments if arg.required]
            for arg in required_args:
                if arg not in kwargs:
                    raise ValueError(f"Missing required argument: {arg}")

            if 'strategies' in kwargs:
                invalid_strategies = set(kwargs['strategies']) - set(self.STRATEGIES)
                if invalid_strategies:
                    raise ValueError(f"Invalid strategies: {invalid_strategies}")

            if 'timeframes' in kwargs:
                invalid_timeframes = set(kwargs['timeframes']) - set(self.TIMEFRAMES)
                if invalid_timeframes:
                    raise ValueError(f"Invalid timeframes: {invalid_timeframes}")

            return True
        except Exception as e:
            logger.error(f"Argument validation error: {e}")
            return False
