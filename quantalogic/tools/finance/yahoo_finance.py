import json
from datetime import datetime, timedelta
from typing import ClassVar, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

from quantalogic.tools import Tool, ToolArgument


class YFinanceTool(Tool):
    """Enhanced Yahoo Finance data retrieval and analysis tool."""

    name: str = "yfinance_tool"
    description: str = "Advanced financial data and analysis tool using Yahoo Finance"
    arguments: list[ToolArgument] = [
        ToolArgument(name="ticker", arg_type="string", description="Stock symbol", required=True),
        ToolArgument(name="start_date", arg_type="string", description="Start date (YYYY-MM-DD)", required=True),
        ToolArgument(name="end_date", arg_type="string", description="End date (YYYY-MM-DD)", required=True),
        ToolArgument(
            name="interval",
            arg_type="string",
            description="Data interval (1m/2m/5m/15m/30m/60m/90m/1h/1d/5d/1wk/1mo/3mo)",
            required=False,
            default="4h"
        ),
        ToolArgument(
            name="analysis_type",
            arg_type="string",
            description="Type of analysis to perform (technical/fundamental/all)",
            required=False,
            default="all"
        )
    ]

    INTERVAL_LIMITS: ClassVar[Dict[str, str]] = {
        '1m': '7d',      # 1 minute data available for last 7 days
        '2m': '60d',     # 2 minutes
        '5m': '60d',     # 5 minutes
        '15m': '60d',    # 15 minutes
        '30m': '60d',    # 30 minutes
        '60m': '730d',   # 60 minutes
        '90m': '60d',    # 90 minutes
        '1h': '730d',    # 1 hour
        '4h': '2y',      # 4 hours
        '1d': 'max',     # 1 day
        '5d': 'max',     # 5 days
        '1wk': 'max',    # 1 week
        '1mo': 'max',    # 1 month
        '3mo': 'max'     # 3 months
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache = {}

    def _validate_interval(self, interval: str, start_date: datetime) -> str:
        """Validate and adjust the interval based on date range."""
        if interval not in self.INTERVAL_LIMITS:
            logger.warning(f"Invalid interval: {interval}. Using default: 4h")
            return "4h"

        limit = self.INTERVAL_LIMITS[interval]
        if limit != 'max':
            limit_days = int(''.join(filter(str.isdigit, limit)))
            if 'y' in limit:
                limit_days *= 365
            
            date_diff = (datetime.now() - start_date).days
            if date_diff > limit_days:
                logger.warning(f"Interval {interval} only supports {limit} of historical data. Adjusting interval...")
                return self._get_appropriate_interval(date_diff)
        
        return interval

    def _get_appropriate_interval(self, days: int) -> str:
        """Get appropriate interval based on date range."""
        if days <= 7:
            return '1m'
        elif days <= 60:
            return '5m'
        elif days <= 730:
            return '1h'
        else:
            return '1d'

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators."""
        # Moving Averages
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        
        # MACD
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        # Volume Analysis
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        
        # Volatility and Returns
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=20).std() * np.sqrt(252)
        
        return df

    def _get_fundamental_data(self, ticker: str) -> Dict:
        """Get fundamental data for the stock."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            return {
                'company_info': {
                    'name': info.get('longName'),
                    'sector': info.get('sector'),
                    'industry': info.get('industry'),
                    'country': info.get('country'),
                    'website': info.get('website'),
                    'description': info.get('longBusinessSummary')
                },
                'financial_metrics': {
                    'market_cap': info.get('marketCap'),
                    'forward_pe': info.get('forwardPE'),
                    'trailing_pe': info.get('trailingPE'),
                    'price_to_book': info.get('priceToBook'),
                    'enterprise_value': info.get('enterpriseValue'),
                    'profit_margins': info.get('profitMargins'),
                    'operating_margins': info.get('operatingMargins'),
                    'roa': info.get('returnOnAssets'),
                    'roe': info.get('returnOnEquity'),
                    'revenue_growth': info.get('revenueGrowth'),
                    'debt_to_equity': info.get('debtToEquity'),
                    'current_ratio': info.get('currentRatio'),
                    'beta': info.get('beta')
                },
                'dividend_info': {
                    'dividend_rate': info.get('dividendRate'),
                    'dividend_yield': info.get('dividendYield'),
                    'payout_ratio': info.get('payoutRatio'),
                    'ex_dividend_date': info.get('exDividendDate')
                }
            }
        except Exception as e:
            logger.error(f"Error fetching fundamental data for {ticker}: {str(e)}")
            return {}

    def execute(self, ticker: str, start_date: str, end_date: str, interval: str = "4h", analysis_type: str = "all") -> str:
        """Execute the Yahoo Finance data retrieval with enhanced features."""
        try:
            # Convert dates to datetime
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Validate interval
            validated_interval = self._validate_interval(interval, start)
            
            # Check cache
            cache_key = f"{ticker}_{start_date}_{end_date}_{validated_interval}_{analysis_type}"
            if cache_key in self.cache:
                logger.info("Using cached data...")
                return self.cache[cache_key]

            logger.info(f"Fetching {ticker} data with {validated_interval} interval...")
            stock = yf.Ticker(ticker)
            
            # Get historical data
            hist = stock.history(
                start=start_date,
                end=end_date,
                interval=validated_interval
            )
            
            if hist.empty:
                logger.warning(f"No data available for {ticker}")
                return json.dumps({"error": "No data available"})

            df = hist.reset_index()
            
            result = {
                "metadata": {
                    "ticker": ticker,
                    "start_date": start_date,
                    "end_date": end_date,
                    "interval": validated_interval,
                    "analysis_type": analysis_type
                },
                "price_data": {}
            }

            # Technical Analysis
            if analysis_type in ["technical", "all"]:
                df = self._calculate_technical_indicators(df)
                result["price_data"] = json.loads(df.to_json(orient='records', date_format='iso'))
                
                # Add summary statistics
                result["technical_summary"] = {
                    "current_price": float(df['Close'].iloc[-1]),
                    "price_change": float(df['Returns'].iloc[-1]),
                    "volume": float(df['Volume'].iloc[-1]),
                    "volume_ratio": float(df['Volume_Ratio'].iloc[-1]),
                    "volatility": float(df['Volatility'].iloc[-1]),
                    "rsi": float(df['RSI'].iloc[-1]),
                    "macd": float(df['MACD'].iloc[-1]),
                    "trading_days": len(df)
                }

            # Fundamental Analysis
            if analysis_type in ["fundamental", "all"]:
                result["fundamental_data"] = self._get_fundamental_data(ticker)

            # Cache the result
            self.cache[cache_key] = json.dumps(result)
            return self.cache[cache_key]

        except Exception as e:
            error_msg = f"Error processing {ticker}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
