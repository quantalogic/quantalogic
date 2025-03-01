import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, List

import numpy as np
import pandas as pd
import requests
import ta
from loguru import logger
from pydantic import model_validator

from quantalogic.tools import Tool, ToolArgument


class AssetType(str, Enum):
    STOCK = "stock"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    ETF = "etf"
    INDEX = "index"

class DataType(str, Enum):
    INTRADAY = "intraday"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUOTE = "quote"
    SEARCH = "search"
    FUNDAMENTAL = "fundamental"
    ECONOMIC = "economic"
    NEWS = "news"

@dataclass
class MarketData:
    """Container for market data and analysis."""
    symbol: str
    asset_type: AssetType
    interval: str
    data: pd.DataFrame
    metadata: Dict[str, Any] = None
    indicators: Dict[str, pd.Series] = None
    fundamental_data: Dict[str, Any] = None
    news_sentiment: Dict[str, Any] = None
    economic_data: Dict[str, Any] = None

class AlphaVantageTool(Tool):
    """Advanced multi-asset financial data and analysis tool using Alpha Vantage."""

    name: ClassVar[str] = "alpha_vantage_tool"
    description: ClassVar[str] = "Enhanced multi-asset financial data and analysis tool using Alpha Vantage API"

    INTERVALS: ClassVar[List[str]] = ['1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly']
    
    # Rate limiting settings
    MAX_REQUESTS_PER_MINUTE: ClassVar[int] = 5
    last_request_time: float = 0

    arguments: ClassVar[list[ToolArgument]] = [
        ToolArgument(
            name="symbols",
            arg_type="string",
            description="Comma-separated list of symbols (e.g., 'AAPL,MSFT,GOOGL')",
            required=True
        ),
        ToolArgument(
            name="asset_type",
            arg_type="string",
            description="Type of asset (stock/forex/crypto)",
            required=True
        ),
        ToolArgument(
            name="function",
            arg_type="string",
            description="Alpha Vantage function (TIME_SERIES_INTRADAY/DAILY/WEEKLY/MONTHLY)",
            required=True
        ),
        ToolArgument(
            name="interval",
            arg_type="string",
            description="Time interval (1min/5min/15min/30min/60min) - only for intraday",
            required=False,
            default="5min"
        ),
        ToolArgument(
            name="outputsize",
            arg_type="string",
            description="Output size (compact/full)",
            required=False,
            default="compact"
        ),
        ToolArgument(
            name="api_key",
            arg_type="string",
            description="Alpha Vantage API key",
            required=True
        ),
        ToolArgument(
            name="indicators",
            arg_type="string",
            description="Comma-separated technical indicators to calculate (e.g., 'SMA,RSI,MACD')",
            required=False,
            default="all"
        ),
        ToolArgument(
            name="lookback_periods",
            arg_type="string",
            description="Number of periods to analyze",
            required=False,
            default="500"
        )
    ]

    @model_validator(mode='before')
    def validate_arguments(cls, values):
        """Validate tool arguments."""
        try:
            # Validate interval format
            if 'interval' in values and values['interval'] not in cls.INTERVALS:
                raise ValueError(f"Invalid interval: {values['interval']}")

            # Validate symbols and asset types match
            if len(values.get('symbols', '').split(',')) != len(values.get('asset_type', '').split(',')):
                raise ValueError("Number of symbols must match number of asset types")

            return values
        except Exception as e:
            logger.error(f"Error validating arguments: {e}")
            raise

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = None
        self.base_url = "https://www.alphavantage.co/query"
        self.cache = {}
        self.executor = ThreadPoolExecutor(max_workers=4)

    def _load_api_key(self, api_key_path: str) -> None:
        """Load Alpha Vantage API key from config file."""
        try:
            config_path = Path(api_key_path)
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                self.api_key = config.get('api_key')
            if not self.api_key:
                raise ValueError("API key not found in config file")
        except Exception as e:
            logger.error(f"Error loading API key: {e}")
            raise

    async def _make_request(self, params: Dict[str, str]) -> Dict:
        """Make rate-limited request to Alpha Vantage API."""
        try:
            # Implement rate limiting
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < (60 / self.MAX_REQUESTS_PER_MINUTE):
                await asyncio.sleep((60 / self.MAX_REQUESTS_PER_MINUTE) - time_since_last_request)

            params['apikey'] = self.api_key
            
            # Make request using ThreadPoolExecutor for blocking IO
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: requests.get(self.base_url, params=params)
            )
            response.raise_for_status()
            
            self.last_request_time = time.time()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error making API request: {e}")
            raise

    async def _fetch_time_series(
        self,
        symbol: str,
        asset_type: AssetType,
        interval: str,
        output_size: str
    ) -> MarketData:
        """Fetch time series data for any asset type."""
        try:
            # Determine the appropriate API function
            function = self._get_time_series_function(asset_type, interval)
            
            params = {
                'function': function,
                'symbol': symbol,
                'outputsize': output_size
            }
            
            if 'INTRADAY' in function:
                params['interval'] = interval
            
            data = await self._make_request(params)
            
            # Parse the response into a DataFrame
            time_series_key = [k for k in data.keys() if 'Time Series' in k][0]
            df = pd.DataFrame.from_dict(data[time_series_key], orient='index')
            
            # Clean up column names and convert to numeric
            df.columns = [col.split('. ')[1].lower() for col in df.columns]
            for col in df.columns:
                df[col] = pd.to_numeric(df[col])
            
            df.index = pd.to_datetime(df.index)
            
            return MarketData(
                symbol=symbol,
                asset_type=asset_type,
                interval=interval,
                data=df,
                metadata=data.get('Meta Data')
            )
            
        except Exception as e:
            logger.error(f"Error fetching time series data for {symbol}: {e}")
            raise

    async def _fetch_fundamental_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch comprehensive fundamental data for stocks."""
        try:
            fundamental_data = {}
            
            # Company Overview
            overview = await self._make_request({
                'function': 'OVERVIEW',
                'symbol': symbol
            })
            fundamental_data['overview'] = overview
            
            # Income Statement
            income_stmt = await self._make_request({
                'function': 'INCOME_STATEMENT',
                'symbol': symbol
            })
            fundamental_data['income_statement'] = income_stmt
            
            # Balance Sheet
            balance_sheet = await self._make_request({
                'function': 'BALANCE_SHEET',
                'symbol': symbol
            })
            fundamental_data['balance_sheet'] = balance_sheet
            
            # Cash Flow
            cash_flow = await self._make_request({
                'function': 'CASH_FLOW',
                'symbol': symbol
            })
            fundamental_data['cash_flow'] = cash_flow
            
            # Earnings
            earnings = await self._make_request({
                'function': 'EARNINGS',
                'symbol': symbol
            })
            fundamental_data['earnings'] = earnings
            
            return fundamental_data
            
        except Exception as e:
            logger.error(f"Error fetching fundamental data for {symbol}: {e}")
            raise

    async def _fetch_economic_data(self, indicators: List[str]) -> Dict[str, pd.DataFrame]:
        """Fetch economic indicators data."""
        try:
            economic_data = {}
            
            for indicator in indicators:
                data = await self._make_request({
                    'function': indicator
                })
                
                # Convert to DataFrame
                df = pd.DataFrame.from_dict(data['data'], orient='index')
                df.index = pd.to_datetime(df.index)
                economic_data[indicator] = df
            
            return economic_data
            
        except Exception as e:
            logger.error(f"Error fetching economic data: {e}")
            raise

    async def _fetch_news_sentiment(self, symbols: List[str]) -> Dict[str, Any]:
        """Fetch news and sentiment data."""
        try:
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': ','.join(symbols)
            }
            
            news_data = await self._make_request(params)
            return news_data
            
        except Exception as e:
            logger.error(f"Error fetching news sentiment: {e}")
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
            if 'volume' in df.columns:
                indicators['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
                indicators['mfi'] = ta.volume.money_flow_index(df['high'], df['low'], df['close'], df['volume'])
            
            market_data.indicators = indicators
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            raise

    def _get_time_series_function(self, asset_type: AssetType, interval: str) -> str:
        """Get the appropriate Alpha Vantage API function based on asset type and interval."""
        if interval in ['1min', '5min', '15min', '30min', '60min']:
            suffix = '_INTRADAY'
        elif interval == 'daily':
            suffix = '_DAILY'
        elif interval == 'weekly':
            suffix = '_WEEKLY'
        else:
            suffix = '_MONTHLY'
            
        if asset_type == AssetType.STOCK:
            return f'TIME_SERIES{suffix}'
        elif asset_type == AssetType.FOREX:
            return f'FX{suffix}'
        elif asset_type == AssetType.CRYPTO:
            return f'CRYPTO{suffix}'
        elif asset_type == AssetType.COMMODITY:
            return f'COMMODITY{suffix}'
        else:
            return f'TIME_SERIES{suffix}'

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the Alpha Vantage tool with comprehensive analysis."""
        try:
            # Load API key
            self._load_api_key(kwargs.get('api_key_path', 'config/alphavantage_config.json'))
            
            symbols = kwargs['symbols'].split(',')
            asset_type = AssetType(kwargs['asset_type'])
            function = kwargs['function']
            interval = kwargs.get('interval', '5min')
            outputsize = kwargs.get('outputsize', 'compact')
            lookback_periods = int(kwargs.get('lookback_periods', '500'))
            indicators = kwargs.get('indicators', 'all').split(',')
            
            results = {}
            
            # Fetch time series data for each symbol
            for symbol in symbols:
                if any(dt in [DataType.INTRADAY, DataType.DAILY, DataType.WEEKLY, DataType.MONTHLY] for dt in [DataType(function)]):
                    market_data = await self._fetch_time_series(
                        symbol, asset_type, interval, outputsize
                    )
                    
                    # Calculate technical indicators
                    self._calculate_technical_indicators(market_data)
                    
                    # Fetch fundamental data for stocks
                    if asset_type == AssetType.STOCK and function == 'FUNDAMENTAL':
                        market_data.fundamental_data = await self._fetch_fundamental_data(symbol)
                    
                    results[symbol] = {
                        'market_data': market_data.data.to_dict(orient='records'),
                        'metadata': market_data.metadata,
                        'indicators': {k: v.to_dict() for k, v in market_data.indicators.items()} if market_data.indicators else None,
                        'fundamental_data': market_data.fundamental_data
                    }
            
            # Fetch news sentiment if requested
            if function == 'NEWS':
                news_data = await self._fetch_news_sentiment(symbols)
                for symbol in symbols:
                    if symbol in results:
                        results[symbol]['news_sentiment'] = news_data
            
            # Fetch economic data if requested
            if function == 'ECONOMIC':
                economic_indicators = [
                    'REAL_GDP',
                    'REAL_GDP_PER_CAPITA',
                    'TREASURY_YIELD',
                    'FEDERAL_FUNDS_RATE',
                    'CPI',
                    'INFLATION',
                    'RETAIL_SALES',
                    'DURABLES',
                    'UNEMPLOYMENT',
                    'NONFARM_PAYROLL'
                ]
                economic_data = await self._fetch_economic_data(economic_indicators)
                for symbol in results:
                    results[symbol]['economic_data'] = economic_data
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing Alpha Vantage tool: {e}")
            raise

    def validate_arguments(self, **kwargs) -> bool:
        """Validate the provided arguments."""
        return super().validate_arguments(**kwargs)
