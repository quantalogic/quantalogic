import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, Optional

import pandas as pd
import ta
from loguru import logger
from pydantic import model_validator
from tvDatafeed import Interval, TvDatafeed

from quantalogic.tools import Tool, ToolArgument


@dataclass
class MarketData:
    """Container for market data and analysis."""
    symbol: str
    exchange: str
    timeframe: str
    data: pd.DataFrame
    indicators: Dict[str, pd.Series] = None
    patterns: Dict[str, pd.Series] = None
    support_resistance: Dict[str, float] = None

class TradingViewTool(Tool):
    """Advanced TradingView data retrieval and analysis tool with real-time capabilities."""

    name: ClassVar[str] = "tradingview_tool"
    description: ClassVar[str] = "Enhanced financial data and analysis tool using TradingView"

    # Mapping intervals to tvDatafeed format
    INTERVAL_MAPPING: ClassVar[Dict[str, Interval]] = {
        '1m': Interval.in_1_minute,
        '3m': Interval.in_3_minute,
        '5m': Interval.in_5_minute,
        '15m': Interval.in_15_minute,
        '30m': Interval.in_30_minute,
        '45m': Interval.in_45_minute,
        '1h': Interval.in_1_hour,
        '2h': Interval.in_2_hour,
        '3h': Interval.in_3_hour,
        '4h': Interval.in_4_hour,
        '1d': Interval.in_daily,
        '1w': Interval.in_weekly,
        '1M': Interval.in_monthly
    }

    arguments: ClassVar[list[ToolArgument]] = [
        ToolArgument(
            name="symbols",
            arg_type="string",
            description="Comma-separated list of symbols (e.g., 'AAPL,MSFT,GOOGL')",
            required=True
        ),
        ToolArgument(
            name="exchanges",
            arg_type="string",
            description="Comma-separated list of exchanges (e.g., 'NASDAQ,NYSE')",
            required=True
        ),
        ToolArgument(
            name="interval",
            arg_type="string",
            description="Time interval (1m/3m/5m/15m/30m/1h/2h/4h/1d/1w/1M)",
            required=False,
            default="1h"
        ),
        ToolArgument(
            name="lookback_periods",
            arg_type="string",
            description="Number of periods to look back",
            required=False,
            default="500"
        ),
        ToolArgument(
            name="analysis_types",
            arg_type="string",
            description="Comma-separated analysis types (technical,patterns,volume,all)",
            required=False,
            default="all"
        ),
        ToolArgument(
            name="credentials_path",
            arg_type="string",
            description="Path to credentials file",
            required=False,
            default="config/tradingview_credentials.json"
        )
    ]

    @model_validator(mode='before')
    def validate_arguments(cls, values):
        """Validate tool arguments."""
        try:
            # Validate interval
            if 'interval' in values and values['interval'] not in cls.INTERVAL_MAPPING:
                raise ValueError(f"Invalid interval: {values['interval']}")

            # Validate symbols format
            if 'symbols' in values:
                symbols = values['symbols'].split(',')
                if not all(symbol.strip() for symbol in symbols):
                    raise ValueError("Invalid symbols format")

            # Validate exchanges format
            if 'exchanges' in values:
                exchanges = values['exchanges'].split(',')
                if not all(exchange.strip() for exchange in exchanges):
                    raise ValueError("Invalid exchanges format")

            return values
        except Exception as e:
            logger.error(f"Error validating arguments: {e}")
            raise

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tv: Optional[TvDatafeed] = None
        self.cache = {}
        self.executor = ThreadPoolExecutor(max_workers=4)

    def _initialize_client(self, credentials_path: str) -> None:
        """Initialize TradingView client with credentials."""
        try:
            if self.tv is None:
                creds_path = Path(credentials_path)
                if creds_path.exists():
                    with open(creds_path) as f:
                        creds = json.load(f)
                    self.tv = TvDatafeed(
                        username=creds.get('username'),
                        password=creds.get('password')
                    )
                else:
                    logger.warning("No credentials found, using anonymous access")
                    self.tv = TvDatafeed()
        except Exception as e:
            logger.error(f"Error initializing TradingView client: {e}")
            raise

    async def _fetch_market_data(
        self,
        symbol: str,
        exchange: str,
        interval: Interval,
        n_bars: int
    ) -> MarketData:
        """Fetch market data asynchronously."""
        try:
            # Use ThreadPoolExecutor for blocking TvDatafeed calls
            df = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self.tv.get_hist,
                symbol,
                exchange,
                interval,
                n_bars
            )
            
            if df is None or df.empty:
                raise ValueError(f"No data returned for {symbol} on {exchange}")

            return MarketData(
                symbol=symbol,
                exchange=exchange,
                timeframe=interval.value,
                data=df
            )
        except Exception as e:
            logger.error(f"Error fetching data for {symbol} on {exchange}: {e}")
            raise

    def _calculate_technical_indicators(self, market_data: MarketData) -> None:
        """Calculate comprehensive technical indicators using the ta library."""
        df = market_data.data
        
        try:
            # Initialize indicator dictionary
            indicators = {}
            
            # Trend Indicators
            indicators['sma_20'] = ta.trend.sma_indicator(df['close'], 20)
            indicators['sma_50'] = ta.trend.sma_indicator(df['close'], 50)
            indicators['sma_200'] = ta.trend.sma_indicator(df['close'], 200)
            indicators['ema_12'] = ta.trend.ema_indicator(df['close'], 12)
            indicators['ema_26'] = ta.trend.ema_indicator(df['close'], 26)
            indicators['macd'] = ta.trend.macd(df['close'])
            indicators['macd_signal'] = ta.trend.macd_signal(df['close'])
            indicators['adx'] = ta.trend.adx(df['high'], df['low'], df['close'])
            
            # Momentum Indicators
            indicators['rsi'] = ta.momentum.rsi(df['close'])
            indicators['stoch'] = ta.momentum.stoch(df['high'], df['low'], df['close'])
            indicators['stoch_signal'] = ta.momentum.stoch_signal(df['high'], df['low'], df['close'])
            indicators['williams_r'] = ta.momentum.williams_r(df['high'], df['low'], df['close'])
            
            # Volatility Indicators
            indicators['bbands_upper'] = ta.volatility.bollinger_hband(df['close'])
            indicators['bbands_lower'] = ta.volatility.bollinger_lband(df['close'])
            indicators['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'])
            
            # Volume Indicators
            indicators['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
            indicators['mfi'] = ta.volume.money_flow_index(df['high'], df['low'], df['close'], df['volume'])
            
            market_data.indicators = indicators
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            raise

    def _identify_patterns(self, market_data: MarketData) -> None:
        """Identify chart patterns."""
        df = market_data.data
        patterns = {}
        
        try:
            # Candlestick Patterns
            patterns['doji'] = ta.candlestick.doji(df['open'], df['high'], df['low'], df['close'])
            patterns['hammer'] = ta.candlestick.hammer(df['open'], df['high'], df['low'], df['close'])
            patterns['shooting_star'] = ta.candlestick.shooting_star(df['open'], df['high'], df['low'], df['close'])
            patterns['morning_star'] = ta.candlestick.morning_star(df['open'], df['high'], df['low'], df['close'])
            patterns['evening_star'] = ta.candlestick.evening_star(df['open'], df['high'], df['low'], df['close'])
            
            market_data.patterns = patterns
            
        except Exception as e:
            logger.error(f"Error identifying patterns: {e}")
            raise

    def _calculate_support_resistance(self, market_data: MarketData) -> None:
        """Calculate support and resistance levels using various methods."""
        df = market_data.data
        levels = {}
        
        try:
            # Calculate using price action
            highs = df['high'].rolling(window=20).max()
            lows = df['low'].rolling(window=20).min()
            
            # Find significant levels
            levels['major_support'] = lows.iloc[-1]
            levels['major_resistance'] = highs.iloc[-1]
            
            # Calculate using volume profile
            volume_profile = df.groupby(pd.cut(df['close'], bins=50))['volume'].sum()
            high_volume_prices = volume_profile.nlargest(3).index
            
            levels['volume_levels'] = [level.mid for level in high_volume_prices]
            
            market_data.support_resistance = levels
            
        except Exception as e:
            logger.error(f"Error calculating support/resistance: {e}")
            raise

    async def execute(self,  **kwargs) -> Dict:
        """Execute the TradingView tool with enhanced analysis capabilities."""
        try:
            # Validate arguments
            if not self.validate_arguments(**kwargs):
                raise ValueError("Invalid arguments")

            # Initialize client
            self._initialize_client(kwargs.get('credentials_path', 'config/tradingview_credentials.json'))
            
            symbols = [symbol.strip() for symbol in kwargs['symbols'].split(',')]
            exchanges = [exchange.strip() for exchange in kwargs['exchanges'].split(',')]
            interval = self.INTERVAL_MAPPING[kwargs.get('interval', '1h')]
            lookback_periods = int(kwargs.get('lookback_periods', '500'))  # Convert to int
            analysis_types = [analysis_type.strip() for analysis_type in kwargs.get('analysis_types', 'all').split(',')]
            
            # Calculate number of bars based on interval and lookback
            n_bars = self._calculate_n_bars(interval, lookback_periods)
            
            # Fetch data for all symbol-exchange pairs concurrently
            tasks = []
            for symbol, exchange in zip(symbols, exchanges):
                tasks.append(self._fetch_market_data(symbol, exchange, interval, n_bars))
            
            market_data_list = await asyncio.gather(*tasks)
            
            # Process each market data
            results = {}
            for market_data in market_data_list:
                if 'all' in analysis_types or 'technical' in analysis_types:
                    self._calculate_technical_indicators(market_data)
                
                if 'all' in analysis_types or 'patterns' in analysis_types:
                    self._identify_patterns(market_data)
                
                if 'all' in analysis_types or 'support_resistance' in analysis_types:
                    self._calculate_support_resistance(market_data)
                
                # Format results
                symbol_key = f"{market_data.exchange}:{market_data.symbol}"
                results[symbol_key] = {
                    'data': market_data.data.to_dict(orient='records'),
                    'indicators': {k: v.to_dict() for k, v in market_data.indicators.items()} if market_data.indicators else None,
                    'patterns': {k: v.to_dict() for k, v in market_data.patterns.items()} if market_data.patterns else None,
                    'support_resistance': market_data.support_resistance
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing TradingView tool: {e}")
            raise

    def _calculate_n_bars(self, interval: Interval, lookback_periods: int) -> int:
        """Calculate number of bars needed based on interval and lookback period."""
        interval_minutes = {
            Interval.in_1_minute: 1,
            Interval.in_3_minute: 3,
            Interval.in_5_minute: 5,
            Interval.in_15_minute: 15,
            Interval.in_30_minute: 30,
            Interval.in_45_minute: 45,
            Interval.in_1_hour: 60,
            Interval.in_2_hour: 120,
            Interval.in_3_hour: 180,
            Interval.in_4_hour: 240,
            Interval.in_daily: 1440,
            Interval.in_weekly: 10080,
            Interval.in_monthly: 43200
        }
        
        minutes_in_lookback = lookback_periods * interval_minutes[interval]
        return minutes_in_lookback // interval_minutes[interval]

    def validate_arguments(self, **kwargs) -> bool:
        """Validate the provided arguments."""
        return super().validate_arguments(**kwargs)
