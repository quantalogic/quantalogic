import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, List

import ccxt.async_support as ccxt
import pandas as pd
import ta
from loguru import logger

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
    levels: Dict[str, float] = None
    volume_profile: Dict[str, float] = None

class CCXTTool(Tool):
    """Advanced cryptocurrency trading and analysis tool using CCXT."""

    name: ClassVar[str] = "ccxt_tool"
    description: ClassVar[str] = "Enhanced cryptocurrency trading and analysis tool using CCXT"
    
    TIMEFRAMES: ClassVar[List[str]] = [
        '1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'
    ]

    arguments: ClassVar[list[ToolArgument]] = [
        ToolArgument(
            name="exchange_ids",
            arg_type="string",
            description="Comma-separated exchange IDs (e.g., 'binance,kucoin')",
            required=True
        ),
        ToolArgument(
            name="symbols",
            arg_type="string",
            description="Comma-separated trading pairs (e.g., 'BTC/USDT,ETH/USDT')",
            required=True
        ),
        ToolArgument(
            name="timeframe",
            arg_type="string",
            description="Time interval for data",
            required=False,
            default="1h"
        ),
        ToolArgument(
            name="lookback_periods",
            arg_type="string",
            description="Number of periods to analyze",
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
            description="Path to exchange credentials file",
            required=False,
            default="config/exchange_credentials.json"
        )
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.cache = {}
        self.executor = ThreadPoolExecutor(max_workers=4)

    def validate_arguments(self, **kwargs) -> bool:
        """Validate tool arguments."""
        try:
            # Validate required arguments
            required_args = [arg.name for arg in self.arguments if arg.required]
            for arg in required_args:
                if arg not in kwargs:
                    raise ValueError(f"Missing required argument: {arg}")

            # Validate timeframe
            if 'timeframe' in kwargs and kwargs['timeframe'] not in self.TIMEFRAMES:
                raise ValueError(f"Invalid timeframe: {kwargs['timeframe']}")

            # Validate exchange IDs format
            if 'exchange_ids' in kwargs:
                exchange_ids = kwargs['exchange_ids'].split(',')
                if not all(exchange_id.strip() for exchange_id in exchange_ids):
                    raise ValueError("Invalid exchange IDs format")

            # Validate trading pairs format
            if 'symbols' in kwargs:
                symbols = kwargs['symbols'].split(',')
                if not all('/' in symbol for symbol in symbols):
                    raise ValueError("Invalid trading pair format. Must be in format BASE/QUOTE")

            return True
        except Exception as e:
            logger.error(f"Error validating arguments: {e}")
            raise

    async def _initialize_exchanges(self, exchange_ids: List[str], credentials_path: str) -> None:
        """Initialize exchange instances with credentials if available."""
        try:
            creds = {}
            creds_path = Path(credentials_path)
            if creds_path.exists():
                with open(creds_path) as f:
                    creds = json.load(f)

            for exchange_id in exchange_ids:
                exchange_class = getattr(ccxt, exchange_id)
                exchange_creds = creds.get(exchange_id, {})
                
                self.exchanges[exchange_id] = exchange_class({
                    'apiKey': exchange_creds.get('api_key'),
                    'secret': exchange_creds.get('secret'),
                    'password': exchange_creds.get('password'),
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })

                # Load markets for symbol validation
                await self.exchanges[exchange_id].load_markets()
                
        except Exception as e:
            logger.error(f"Error initializing exchanges: {e}")
            raise

    async def _fetch_ohlcv(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int
    ) -> MarketData:
        """Fetch OHLCV data from exchange."""
        try:
            exchange = self.exchanges[exchange_id]
            
            # Fetch OHLCV data
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return MarketData(
                symbol=symbol,
                exchange=exchange_id,
                timeframe=timeframe,
                data=df
            )
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV data for {symbol} on {exchange_id}: {e}")
            raise

    async def _fetch_order_book(self, exchange_id: str, symbol: str, limit: int = 100) -> Dict:
        """Fetch order book data."""
        try:
            exchange = self.exchanges[exchange_id]
            order_book = await exchange.fetch_order_book(symbol, limit)
            
            return {
                'bids': order_book['bids'],
                'asks': order_book['asks'],
                'timestamp': order_book['timestamp'],
                'datetime': order_book['datetime'],
                'nonce': order_book.get('nonce')
            }
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol} on {exchange_id}: {e}")
            raise

    def _calculate_technical_indicators(self, market_data: MarketData) -> None:
        """Calculate comprehensive technical indicators."""
        df = market_data.data
        indicators = {}
        
        try:
            # Trend Indicators
            indicators['sma_20'] = ta.trend.sma_indicator(df['close'], 20)
            indicators['sma_50'] = ta.trend.sma_indicator(df['close'], 50)
            indicators['sma_200'] = ta.trend.sma_indicator(df['close'], 200)
            indicators['ema_12'] = ta.trend.ema_indicator(df['close'], 12)
            indicators['ema_26'] = ta.trend.ema_indicator(df['close'], 26)
            indicators['macd'] = ta.trend.macd(df['close'])
            indicators['macd_signal'] = ta.trend.macd_signal(df['close'])
            indicators['macd_diff'] = ta.trend.macd_diff(df['close'])
            indicators['adx'] = ta.trend.adx(df['high'], df['low'], df['close'])
            
            # Momentum Indicators
            indicators['rsi'] = ta.momentum.rsi(df['close'])
            indicators['stoch'] = ta.momentum.stoch(df['high'], df['low'], df['close'])
            indicators['stoch_signal'] = ta.momentum.stoch_signal(df['high'], df['low'], df['close'])
            indicators['williams_r'] = ta.momentum.williams_r(df['high'], df['low'], df['close'])
            
            # Volatility Indicators
            indicators['bbands_upper'] = ta.volatility.bollinger_hband(df['close'])
            indicators['bbands_lower'] = ta.volatility.bollinger_lband(df['close'])
            indicators['bbands_middle'] = ta.volatility.bollinger_mavg(df['close'])
            indicators['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'])
            
            # Volume Indicators
            indicators['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
            indicators['mfi'] = ta.volume.money_flow_index(df['high'], df['low'], df['close'], df['volume'])
            indicators['vwap'] = self._calculate_vwap(df)
            
            market_data.indicators = indicators
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            raise

    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Volume Weighted Average Price."""
        v = df['volume']
        tp = (df['high'] + df['low'] + df['close']) / 3
        return (tp * v).cumsum() / v.cumsum()

    def _identify_patterns(self, market_data: MarketData) -> None:
        """Identify chart patterns and candlestick patterns."""
        df = market_data.data
        patterns = {}
        
        try:
            # Candlestick Patterns
            patterns['doji'] = ta.candlestick.doji(df['open'], df['high'], df['low'], df['close'])
            patterns['hammer'] = ta.candlestick.hammer(df['open'], df['high'], df['low'], df['close'])
            patterns['shooting_star'] = ta.candlestick.shooting_star(df['open'], df['high'], df['low'], df['close'])
            patterns['morning_star'] = ta.candlestick.morning_star(df['open'], df['high'], df['low'], df['close'])
            patterns['evening_star'] = ta.candlestick.evening_star(df['open'], df['high'], df['low'], df['close'])
            
            # Custom Pattern Detection
            patterns['double_top'] = self._detect_double_top(df)
            patterns['double_bottom'] = self._detect_double_bottom(df)
            patterns['head_shoulders'] = self._detect_head_shoulders(df)
            
            market_data.patterns = patterns
            
        except Exception as e:
            logger.error(f"Error identifying patterns: {e}")
            raise

    def _detect_double_top(self, df: pd.DataFrame) -> pd.Series:
        """Detect double top pattern."""
        window = 20
        peaks = df['high'].rolling(window, center=True).apply(
            lambda x: 1 if x.iloc[window//2] == max(x) else 0
        )
        return peaks

    def _detect_double_bottom(self, df: pd.DataFrame) -> pd.Series:
        """Detect double bottom pattern."""
        window = 20
        troughs = df['low'].rolling(window, center=True).apply(
            lambda x: 1 if x.iloc[window//2] == min(x) else 0
        )
        return troughs

    def _detect_head_shoulders(self, df: pd.DataFrame) -> pd.Series:
        """Detect head and shoulders pattern."""
        window = 30
        result = pd.Series(0, index=df.index)
        
        for i in range(window, len(df)-window):
            left = df['high'].iloc[i-window:i].max()
            head = df['high'].iloc[i]
            right = df['high'].iloc[i:i+window].max()
            
            if head > left and head > right and abs(left - right) < 0.1 * head:
                result.iloc[i] = 1
                
        return result

    def _analyze_volume_profile(self, market_data: MarketData) -> None:
        """Analyze volume profile and identify key price levels."""
        df = market_data.data
        
        try:
            # Calculate volume profile
            price_bins = pd.qcut(df['close'], q=50, duplicates='drop')
            volume_profile = df.groupby(price_bins)['volume'].sum()
            
            # Identify high volume nodes
            high_volume_levels = volume_profile.nlargest(5)
            
            market_data.volume_profile = {
                'volume_by_price': volume_profile.to_dict(),
                'high_volume_levels': high_volume_levels.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volume profile: {e}")
            raise

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the CCXT tool with comprehensive analysis."""
        try:
            self.validate_arguments(**kwargs)
            
            exchange_ids = kwargs['exchange_ids'].split(',')  # Split comma-separated string
            symbols = kwargs['symbols'].split(',')  # Split comma-separated string
            timeframe = kwargs.get('timeframe', '1h')
            lookback_periods = int(kwargs.get('lookback_periods', '500'))  # Convert to int
            analysis_types = kwargs.get('analysis_types', 'all').split(',')  # Split comma-separated string
            credentials_path = kwargs.get('credentials_path', 'config/exchange_credentials.json')
            
            # Initialize exchanges
            await self._initialize_exchanges(exchange_ids, credentials_path)
            
            # Fetch data and analyze for each symbol on each exchange
            results = {}
            for exchange_id in exchange_ids:
                for symbol in symbols:
                    # Fetch OHLCV data
                    market_data = await self._fetch_ohlcv(
                        exchange_id, symbol, timeframe, lookback_periods
                    )
                    
                    # Perform requested analyses
                    if 'all' in analysis_types or 'technical' in analysis_types:
                        self._calculate_technical_indicators(market_data)
                    
                    if 'all' in analysis_types or 'patterns' in analysis_types:
                        self._identify_patterns(market_data)
                    
                    if 'all' in analysis_types or 'volume' in analysis_types:
                        self._analyze_volume_profile(market_data)
                    
                    if 'all' in analysis_types or 'orderbook' in analysis_types:
                        order_book = await self._fetch_order_book(exchange_id, symbol)
                    else:
                        order_book = None
                    
                    # Format results
                    key = f"{exchange_id}:{symbol}"
                    results[key] = {
                        'market_data': market_data.data.to_dict(orient='records'),
                        'indicators': {k: v.to_dict() for k, v in market_data.indicators.items()} if market_data.indicators else None,
                        'patterns': {k: v.to_dict() for k, v in market_data.patterns.items()} if market_data.patterns else None,
                        'volume_profile': market_data.volume_profile,
                        'order_book': order_book
                    }
            
            # Close exchange connections
            for exchange in self.exchanges.values():
                await exchange.close()
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing CCXT tool: {e}")
            raise
