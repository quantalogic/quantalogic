from datetime import datetime
from typing import ClassVar, Dict

import pandas as pd
import requests
from loguru import logger

from quantalogic.tools import Tool, ToolArgument


class GFinanceTool(Tool):
    """Enhanced Google Finance data retrieval and analysis tool."""

    name: str = "gfinance_tool"
    description: str = "Advanced financial data and analysis tool using Google Finance"
    arguments: list[ToolArgument] = [
        ToolArgument(name="ticker", arg_type="string", description="Stock symbol (e.g., GOOGL)", required=True),
        ToolArgument(name="start_date", arg_type="string", description="Start date (YYYY-MM-DD)", required=True),
        ToolArgument(name="end_date", arg_type="string", description="End date (YYYY-MM-DD)", required=True),
        ToolArgument(
            name="interval",
            arg_type="string",
            description="Data interval (1d/1wk/1mo)",
            required=False,
            default="1d"
        ),
        ToolArgument(
            name="analysis_type",
            arg_type="string",
            description="Type of analysis to perform (technical/fundamental/all)",
            required=False,
            default="all"
        )
    ]

    INTERVAL_MAPPING: ClassVar[Dict[str, int]] = {
        '1d': 86400,    # 1 day in seconds
        '1wk': 604800,  # 1 week in seconds
        '1mo': 2592000  # 1 month in seconds (30 days)
    }

    BASE_URL = "https://www.google.com/finance/quote"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache = {}

    def _validate_dates(self, start_date: str, end_date: str) -> tuple[datetime, datetime]:
        """Validate and convert date strings to datetime objects."""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            if start > end:
                raise ValueError("Start date must be before end date")
            return start, end
        except ValueError as e:
            logger.error(f"Date validation error: {e}")
            raise

    def _fetch_data(self, ticker: str, start_date: datetime, end_date: datetime, interval: str) -> pd.DataFrame:
        """Fetch financial data from Google Finance."""
        try:
            # Construct the URL
            params = {
                'period': self.INTERVAL_MAPPING.get(interval, self.INTERVAL_MAPPING['1d']),
                'window': int((end_date - start_date).total_seconds())
            }
            url = f"{self.BASE_URL}/{ticker}/historical"
            
            # Make the request
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # Parse the response and convert to DataFrame
            data = response.json()
            df = pd.DataFrame(data['prices'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except requests.RequestException as e:
            logger.error(f"Error fetching data from Google Finance: {e}")
            raise

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators."""
        if len(df) < 50:
            logger.warning("Not enough data points for technical analysis")
            return df

        # Moving Averages
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['EMA_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['close'].ewm(span=26, adjust=False).mean()
        
        # MACD
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df['BB_middle'] = df['close'].rolling(window=20).mean()
        std = df['close'].rolling(window=20).std()
        df['BB_upper'] = df['BB_middle'] + (std * 2)
        df['BB_lower'] = df['BB_middle'] - (std * 2)
        
        return df

    def _get_fundamental_data(self, ticker: str) -> Dict:
        """Fetch fundamental data from Google Finance."""
        try:
            url = f"{self.BASE_URL}/{ticker}"
            response = requests.get(url)
            response.raise_for_status()
            
            # Parse the response to extract fundamental data
            data = response.json()
            return {
                'market_cap': data.get('marketCap'),
                'pe_ratio': data.get('peRatio'),
                'dividend_yield': data.get('dividendYield'),
                'eps': data.get('eps'),
                'high_52week': data.get('high52Week'),
                'low_52week': data.get('low52Week')
            }
            
        except requests.RequestException as e:
            logger.error(f"Error fetching fundamental data: {e}")
            return {}

    def execute(self,  **kwargs) -> Dict:
        """Execute the Google Finance tool with the provided parameters."""
        ticker = kwargs.get('ticker')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        interval = kwargs.get('interval', '1d')
        analysis_type = kwargs.get('analysis_type', 'all')

        try:
            # Validate dates
            start_dt, end_dt = self._validate_dates(start_date, end_date)
            
            # Fetch historical data
            df = self._fetch_data(ticker, start_dt, end_dt, interval)
            
            result = {
                'historical_data': df.to_dict(orient='records'),
                'metadata': {
                    'ticker': ticker,
                    'start_date': start_date,
                    'end_date': end_date,
                    'interval': interval
                }
            }

            # Add technical analysis if requested
            if analysis_type in ['technical', 'all']:
                df = self._calculate_technical_indicators(df)
                result['technical_indicators'] = df.to_dict(orient='records')

            # Add fundamental analysis if requested
            if analysis_type in ['fundamental', 'all']:
                fundamental_data = self._get_fundamental_data(ticker)
                result['fundamental_data'] = fundamental_data

            return result

        except Exception as e:
            logger.error(f"Error executing Google Finance tool: {e}")
            raise

    def validate_arguments(self, **kwargs) -> bool:
        """Validate the provided arguments."""
        required_args = [arg.name for arg in self.arguments if arg.required]
        for arg in required_args:
            if arg not in kwargs:
                logger.error(f"Missing required argument: {arg}")
                return False

        if 'interval' in kwargs and kwargs['interval'] not in self.INTERVAL_MAPPING:
            logger.error(f"Invalid interval: {kwargs['interval']}")
            return False

        return True
