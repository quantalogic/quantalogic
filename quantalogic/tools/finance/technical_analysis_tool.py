"""Advanced Technical Analysis Tool for comprehensive market analysis."""

from typing import Dict, List, Optional, Union, Tuple, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger
import ta
from dataclasses import dataclass
from enum import Enum
import scipy.stats as stats
from scipy.signal import argrelextrema
import warnings
warnings.filterwarnings('ignore')

from quantalogic import Agent
from quantalogic.tools import Tool, ToolArgument

class SignalType(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

class PatternType(str, Enum):
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_SHOULDERS = "head_shoulders"
    INV_HEAD_SHOULDERS = "inv_head_shoulders"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DESCENDING_TRIANGLE = "descending_triangle"
    BULL_FLAG = "bull_flag"
    BEAR_FLAG = "bear_flag"
    CHANNEL_UP = "channel_up"
    CHANNEL_DOWN = "channel_down"

@dataclass
class TechnicalSignal:
    """Container for technical analysis signals."""
    indicator_type: str
    signal: SignalType
    value: float
    threshold: float
    timestamp: datetime
    confidence: float
    metadata: Dict[str, Any] = None

@dataclass
class PatternSignal:
    """Container for pattern recognition signals."""
    pattern_type: PatternType
    start_idx: int
    end_idx: int
    confidence: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float
    volume_confirmation: bool
    metadata: Dict[str, Any] = None

@dataclass
class TechnicalAnalysis:
    """Container for comprehensive technical analysis results."""
    symbol: str
    timeframe: str
    analysis_timestamp: datetime
    current_price: float
    trend_signals: Dict[str, TechnicalSignal]
    momentum_signals: Dict[str, TechnicalSignal]
    volatility_signals: Dict[str, TechnicalSignal]
    volume_signals: Dict[str, TechnicalSignal]
    pattern_signals: List[PatternSignal]
    support_resistance: Dict[str, float]
    pivot_points: Dict[str, float]
    fibonacci_levels: Dict[str, float]
    divergences: Dict[str, Dict[str, Any]]
    market_strength: Dict[str, float]

class TechnicalAnalysisTool(Tool):
    """Advanced technical analysis tool with comprehensive market analysis capabilities."""

    name: str = "technical_analysis_tool"
    description: str = "Advanced technical analysis tool for comprehensive market analysis"

    arguments: list[ToolArgument] = [
        ToolArgument(
            name="data",
            arg_type="dict",
            description="OHLCV data in pandas DataFrame format",
            required=True
        ),
        ToolArgument(
            name="timeframe",
            arg_type="string",
            description="Timeframe of the data",
            required=True
        ),
        ToolArgument(
            name="symbol",
            arg_type="string",
            description="Trading symbol",
            required=True
        ),
        ToolArgument(
            name="analysis_types",
            arg_type="list",
            description="Types of analysis to perform",
            required=False,
            default=["all"]
        )
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache = {}

    def _calculate_trend_indicators(self, df: pd.DataFrame) -> Dict[str, TechnicalSignal]:
        """Calculate comprehensive trend indicators."""
        signals = {}
        
        try:
            # Moving Averages
            df['sma_20'] = ta.trend.sma_indicator(df['close'], 20)
            df['sma_50'] = ta.trend.sma_indicator(df['close'], 50)
            df['sma_200'] = ta.trend.sma_indicator(df['close'], 200)
            df['ema_12'] = ta.trend.ema_indicator(df['close'], 12)
            df['ema_26'] = ta.trend.ema_indicator(df['close'], 26)
            
            # MACD
            df['macd'] = ta.trend.macd(df['close'])
            df['macd_signal'] = ta.trend.macd_signal(df['close'])
            df['macd_diff'] = ta.trend.macd_diff(df['close'])
            
            # ADX
            df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'])
            df['di_plus'] = ta.trend.adx_pos(df['high'], df['low'], df['close'])
            df['di_minus'] = ta.trend.adx_neg(df['high'], df['low'], df['close'])
            
            # Ichimoku Cloud
            df['ichimoku_a'] = ta.trend.ichimoku_a(df['high'], df['low'])
            df['ichimoku_b'] = ta.trend.ichimoku_b(df['high'], df['low'])
            
            # Trend Signals
            signals['ma_cross'] = self._analyze_ma_crossover(df)
            signals['macd'] = self._analyze_macd(df)
            signals['adx'] = self._analyze_adx(df)
            signals['ichimoku'] = self._analyze_ichimoku(df)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error calculating trend indicators: {e}")
            raise

    def _calculate_momentum_indicators(self, df: pd.DataFrame) -> Dict[str, TechnicalSignal]:
        """Calculate comprehensive momentum indicators."""
        signals = {}
        
        try:
            # RSI
            df['rsi'] = ta.momentum.rsi(df['close'])
            
            # Stochastic
            df['stoch_k'] = ta.momentum.stoch(df['high'], df['low'], df['close'])
            df['stoch_d'] = ta.momentum.stoch_signal(df['high'], df['low'], df['close'])
            
            # ROC
            df['roc'] = ta.momentum.roc(df['close'])
            
            # Ultimate Oscillator
            df['uo'] = ta.momentum.ultimate_oscillator(df['high'], df['low'], df['close'])
            
            # TSI
            df['tsi'] = ta.momentum.tsi(df['close'])
            
            # Momentum Signals
            signals['rsi'] = self._analyze_rsi(df)
            signals['stochastic'] = self._analyze_stochastic(df)
            signals['ultimate_oscillator'] = self._analyze_ultimate_oscillator(df)
            signals['tsi'] = self._analyze_tsi(df)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error calculating momentum indicators: {e}")
            raise

    def _calculate_volatility_indicators(self, df: pd.DataFrame) -> Dict[str, TechnicalSignal]:
        """Calculate comprehensive volatility indicators."""
        signals = {}
        
        try:
            # Bollinger Bands
            df['bb_upper'] = ta.volatility.bollinger_hband(df['close'])
            df['bb_middle'] = ta.volatility.bollinger_mavg(df['close'])
            df['bb_lower'] = ta.volatility.bollinger_lband(df['close'])
            
            # ATR
            df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'])
            
            # Keltner Channel
            df['kc_upper'] = ta.volatility.keltner_channel_hband(df['high'], df['low'], df['close'])
            df['kc_lower'] = ta.volatility.keltner_channel_lband(df['high'], df['low'], df['close'])
            
            # Donchian Channel
            df['dc_upper'] = df['high'].rolling(20).max()
            df['dc_lower'] = df['low'].rolling(20).min()
            
            # Volatility Signals
            signals['bollinger'] = self._analyze_bollinger_bands(df)
            signals['atr'] = self._analyze_atr(df)
            signals['keltner'] = self._analyze_keltner_channel(df)
            signals['donchian'] = self._analyze_donchian_channel(df)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error calculating volatility indicators: {e}")
            raise

    def _calculate_volume_indicators(self, df: pd.DataFrame) -> Dict[str, TechnicalSignal]:
        """Calculate comprehensive volume indicators."""
        signals = {}
        
        try:
            # On-Balance Volume
            df['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
            
            # Money Flow Index
            df['mfi'] = ta.volume.money_flow_index(df['high'], df['low'], df['close'], df['volume'])
            
            # Volume Price Trend
            df['vpt'] = ta.volume.volume_price_trend(df['close'], df['volume'])
            
            # Ease of Movement
            df['eom'] = ta.volume.ease_of_movement(df['high'], df['low'], df['volume'])
            
            # Volume-Weighted Average Price
            df['vwap'] = self._calculate_vwap(df)
            
            # Volume Signals
            signals['obv'] = self._analyze_obv(df)
            signals['mfi'] = self._analyze_mfi(df)
            signals['vpt'] = self._analyze_vpt(df)
            signals['vwap'] = self._analyze_vwap(df)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error calculating volume indicators: {e}")
            raise

    def _identify_chart_patterns(self, df: pd.DataFrame) -> List[PatternSignal]:
        """Identify chart patterns using advanced pattern recognition."""
        patterns = []
        
        try:
            # Find local maxima and minima
            max_idx = argrelextrema(df['high'].values, np.greater, order=5)[0]
            min_idx = argrelextrema(df['low'].values, np.less, order=5)[0]
            
            # Double Top/Bottom
            patterns.extend(self._find_double_patterns(df, max_idx, min_idx))
            
            # Head and Shoulders
            patterns.extend(self._find_head_shoulders(df, max_idx, min_idx))
            
            # Triangle Patterns
            patterns.extend(self._find_triangle_patterns(df, max_idx, min_idx))
            
            # Flag Patterns
            patterns.extend(self._find_flag_patterns(df))
            
            # Channels
            patterns.extend(self._find_channels(df))
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error identifying chart patterns: {e}")
            raise

    def _calculate_support_resistance(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate support and resistance levels using multiple methods."""
        levels = {}
        
        try:
            # Price Action Based
            levels.update(self._find_price_levels(df))
            
            # Volume Profile Based
            levels.update(self._find_volume_levels(df))
            
            # Fibonacci Based
            levels.update(self._calculate_fibonacci_levels(df))
            
            return levels
            
        except Exception as e:
            logger.error(f"Error calculating support/resistance: {e}")
            raise

    def _find_divergences(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Identify regular and hidden divergences."""
        divergences = {}
        
        try:
            # RSI Divergences
            divergences['rsi'] = self._find_indicator_divergences(df, df['rsi'], 'RSI')
            
            # MACD Divergences
            divergences['macd'] = self._find_indicator_divergences(df, df['macd'], 'MACD')
            
            # OBV Divergences
            divergences['obv'] = self._find_indicator_divergences(df, df['obv'], 'OBV')
            
            return divergences
            
        except Exception as e:
            logger.error(f"Error finding divergences: {e}")
            raise

    def _calculate_market_strength(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate overall market strength using multiple metrics."""
        strength = {}
        
        try:
            # Trend Strength
            strength['trend'] = self._calculate_trend_strength(df)
            
            # Momentum Strength
            strength['momentum'] = self._calculate_momentum_strength(df)
            
            # Volume Strength
            strength['volume'] = self._calculate_volume_strength(df)
            
            # Overall Strength
            strength['overall'] = np.mean([
                strength['trend'],
                strength['momentum'],
                strength['volume']
            ])
            
            return strength
            
        except Exception as e:
            logger.error(f"Error calculating market strength: {e}")
            raise

    def execute(self, agent: Agent, **kwargs) -> TechnicalAnalysis:
        """Execute comprehensive technical analysis."""
        try:
            df = pd.DataFrame(kwargs['data'])
            timeframe = kwargs['timeframe']
            symbol = kwargs['symbol']
            analysis_types = kwargs.get('analysis_types', ['all'])
            
            # Initialize containers
            trend_signals = {}
            momentum_signals = {}
            volatility_signals = {}
            volume_signals = {}
            pattern_signals = []
            
            # Perform requested analyses
            if 'all' in analysis_types or 'trend' in analysis_types:
                trend_signals = self._calculate_trend_indicators(df)
            
            if 'all' in analysis_types or 'momentum' in analysis_types:
                momentum_signals = self._calculate_momentum_indicators(df)
            
            if 'all' in analysis_types or 'volatility' in analysis_types:
                volatility_signals = self._calculate_volatility_indicators(df)
            
            if 'all' in analysis_types or 'volume' in analysis_types:
                volume_signals = self._calculate_volume_indicators(df)
            
            if 'all' in analysis_types or 'patterns' in analysis_types:
                pattern_signals = self._identify_chart_patterns(df)
            
            # Calculate additional analyses
            support_resistance = self._calculate_support_resistance(df)
            pivot_points = self._calculate_pivot_points(df)
            fibonacci_levels = self._calculate_fibonacci_levels(df)
            divergences = self._find_divergences(df)
            market_strength = self._calculate_market_strength(df)
            
            # Combine all analyses
            return TechnicalAnalysis(
                symbol=symbol,
                timeframe=timeframe,
                analysis_timestamp=datetime.now(),
                current_price=df['close'].iloc[-1],
                trend_signals=trend_signals,
                momentum_signals=momentum_signals,
                volatility_signals=volatility_signals,
                volume_signals=volume_signals,
                pattern_signals=pattern_signals,
                support_resistance=support_resistance,
                pivot_points=pivot_points,
                fibonacci_levels=fibonacci_levels,
                divergences=divergences,
                market_strength=market_strength
            )
            
        except Exception as e:
            logger.error(f"Error executing technical analysis: {e}")
            raise

    def validate_arguments(self, **kwargs) -> bool:
        """Validate the provided arguments."""
        try:
            required_args = [arg.name for arg in self.arguments if arg.required]
            for arg in required_args:
                if arg not in kwargs:
                    raise ValueError(f"Missing required argument: {arg}")

            # Validate data structure
            if 'data' in kwargs:
                required_columns = ['open', 'high', 'low', 'close', 'volume']
                df = pd.DataFrame(kwargs['data'])
                missing_columns = set(required_columns) - set(df.columns)
                if missing_columns:
                    raise ValueError(f"Missing required columns: {missing_columns}")

            return True
        except Exception as e:
            logger.error(f"Argument validation error: {e}")
            return False
