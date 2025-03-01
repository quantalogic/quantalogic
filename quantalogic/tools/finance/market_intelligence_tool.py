"""Advanced Market Intelligence Tool for comprehensive financial information retrieval."""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import ccxt
import numpy as np
import pandas as pd
import requests
import tweepy
import yfinance as yf
from alpha_vantage.fundamentaldata import FundamentalData
from alpha_vantage.timeseries import TimeSeries
from loguru import logger
from newsapi import NewsApiClient
from serpapi import GoogleSearch

from quantalogic.agent import Agent
from quantalogic.tools.tool import Tool, ToolArgument


@dataclass
class MarketNews:
    """Container for market news data."""
    title: str
    source: str
    url: str
    published_at: datetime
    sentiment: float
    relevance: float
    summary: str
    keywords: List[str]

@dataclass
class SocialMetrics:
    """Container for social media metrics."""
    sentiment_score: float
    engagement_rate: float
    mention_count: int
    trending_topics: List[str]
    influential_posts: List[Dict]
    source: str
    timestamp: datetime

@dataclass
class FundamentalMetrics:
    """Container for fundamental analysis metrics."""
    market_cap: float
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]
    quick_ratio: Optional[float]
    roa: Optional[float]
    roe: Optional[float]
    profit_margin: Optional[float]
    revenue_growth: Optional[float]
    institutional_ownership: Optional[float]
    insider_ownership: Optional[float]

@dataclass
class MarketIntelligence:
    """Container for comprehensive market intelligence."""
    symbol: str
    asset_type: str
    timestamp: datetime
    current_price: float
    market_news: List[MarketNews]
    social_metrics: Dict[str, SocialMetrics]
    fundamental_metrics: Optional[FundamentalMetrics]
    analyst_ratings: Dict[str, Any]
    market_events: List[Dict]
    regulatory_updates: List[Dict]
    competitor_analysis: Dict[str, Any]
    risk_metrics: Dict[str, float]

class MarketIntelligenceTool(Tool):
    """Advanced market intelligence tool for comprehensive financial information retrieval."""

    name: str = "market_intelligence_tool"
    description: str = (
        "Advanced tool for retrieving comprehensive market intelligence including "
        "news, social metrics, fundamental data, and market events for various "
        "financial instruments."
    )

    arguments: list = [
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
            name="data_types",
            arg_type="list",
            description="Types of data to retrieve",
            required=False,
            default="['all']"
        ),
        ToolArgument(
            name="time_range",
            arg_type="string",
            description="Time range for historical data",
            required=False,
            default="7d"
        )
    ]

    def __init__(self, **kwargs):
        """Initialize the Market Intelligence tool with API configurations."""
        super().__init__(**kwargs)
        
        # Initialize API clients
        self._init_api_clients()
        
        # Initialize cache
        self.cache = {}

    def _init_api_clients(self):
        """Initialize various API clients."""
        try:
            # News API
            self.news_api = NewsApiClient(api_key=os.getenv('NEWS_API_KEY'))
            
            # Alpha Vantage
            self.alpha_vantage_fd = FundamentalData(key=os.getenv('ALPHA_VANTAGE_KEY'))
            self.alpha_vantage_ts = TimeSeries(key=os.getenv('ALPHA_VANTAGE_KEY'))
            
            # Twitter API
            auth = tweepy.OAuthHandler(
                os.getenv('TWITTER_API_KEY'),
                os.getenv('TWITTER_API_SECRET')
            )
            auth.set_access_token(
                os.getenv('TWITTER_ACCESS_TOKEN'),
                os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            )
            self.twitter_api = tweepy.API(auth)
            
            # SerpAPI
            self.serp_api = GoogleSearch({
                "api_key": os.getenv('SERPAPI_KEY')
            })
            
            # CCXT
            self.exchange = ccxt.binance()
            
        except Exception as e:
            logger.error(f"Error initializing API clients: {e}")
            raise

    async def _fetch_market_news(self, symbol: str, asset_type: str) -> List[MarketNews]:
        """Fetch and analyze market news from multiple sources."""
        news_items = []
        
        try:
            # News API
            news_query = f"{symbol} stock" if asset_type == "stock" else f"{symbol} crypto"
            news_response = self.news_api.get_everything(
                q=news_query,
                language='en',
                sort_by='relevancy',
                page_size=20
            )
            
            # Google News via SerpAPI
            serp_params = {
                "q": f"{symbol} news",
                "tbm": "nws",
                "num": 20
            }
            serp_response = self.serp_api.get_dict()
            
            # Combine and process news
            for article in news_response['articles'] + serp_response.get('news_results', []):
                # Analyze sentiment
                sentiment = self._analyze_sentiment(article['title'] + " " + article.get('description', ''))
                
                # Calculate relevance
                relevance = self._calculate_relevance(article, symbol)
                
                news_items.append(MarketNews(
                    title=article['title'],
                    source=article['source']['name'],
                    url=article['url'],
                    published_at=datetime.strptime(article['publishedAt'][:19], '%Y-%m-%dT%H:%M:%S'),
                    sentiment=sentiment,
                    relevance=relevance,
                    summary=article.get('description', ''),
                    keywords=self._extract_keywords(article)
                ))
            
            return sorted(news_items, key=lambda x: (x.relevance, x.published_at), reverse=True)
            
        except Exception as e:
            logger.error(f"Error fetching market news: {e}")
            return []

    async def _fetch_social_metrics(self, symbol: str, asset_type: str) -> Dict[str, SocialMetrics]:
        """Fetch and analyze social media metrics."""
        social_data = {}
        
        try:
            # Twitter Analysis
            twitter_metrics = await self._analyze_twitter(symbol)
            social_data['twitter'] = twitter_metrics
            
            # Reddit Analysis
            reddit_metrics = await self._analyze_reddit(symbol)
            social_data['reddit'] = reddit_metrics
            
            # StockTwits Analysis (if stock)
            if asset_type == 'stock':
                stocktwits_metrics = await self._analyze_stocktwits(symbol)
                social_data['stocktwits'] = stocktwits_metrics
            
            return social_data
            
        except Exception as e:
            logger.error(f"Error fetching social metrics: {e}")
            return {}

    async def _fetch_fundamental_data(self, symbol: str, asset_type: str) -> Optional[FundamentalMetrics]:
        """Fetch fundamental data for stocks."""
        if asset_type != 'stock':
            return None
            
        try:
            # Alpha Vantage Fundamental Data
            overview = self.alpha_vantage_fd.get_company_overview(symbol)[0]
            
            # Yahoo Finance Additional Data
            yf_data = yf.Ticker(symbol)
            info = yf_data.info
            
            return FundamentalMetrics(
                market_cap=float(overview.get('MarketCapitalization', 0)),
                pe_ratio=float(overview.get('PERatio', 0)) or None,
                pb_ratio=float(overview.get('PriceToBookRatio', 0)) or None,
                debt_to_equity=float(overview.get('DebtToEquityRatio', 0)) or None,
                current_ratio=float(overview.get('CurrentRatio', 0)) or None,
                quick_ratio=float(info.get('quickRatio', 0)) or None,
                roa=float(overview.get('ReturnOnAssetsTTM', 0)) or None,
                roe=float(overview.get('ReturnOnEquityTTM', 0)) or None,
                profit_margin=float(overview.get('ProfitMargin', 0)) or None,
                revenue_growth=float(info.get('revenueGrowth', 0)) or None,
                institutional_ownership=float(info.get('institutionPercentHeld', 0)) or None,
                insider_ownership=float(info.get('insiderPercentHeld', 0)) or None
            )
            
        except Exception as e:
            logger.error(f"Error fetching fundamental data: {e}")
            return None

    async def _fetch_analyst_ratings(self, symbol: str, asset_type: str) -> Dict[str, Any]:
        """Fetch and analyze analyst ratings and price targets."""
        ratings = {}
        
        try:
            if asset_type == 'stock':
                # Yahoo Finance Analyst Ratings
                yf_data = yf.Ticker(symbol)
                recommendations = yf_data.recommendations
                
                if recommendations is not None:
                    ratings['recommendations'] = recommendations.to_dict('records')
                
                # Seeking Alpha via SerpAPI
                serp_params = {
                    "q": f"{symbol} stock analysis site:seekingalpha.com",
                    "num": 5
                }
                serp_response = self.serp_api.get_dict()
                
                if 'organic_results' in serp_response:
                    ratings['analysis_articles'] = serp_response['organic_results']
            
            elif asset_type == 'crypto':
                # CoinGecko API for crypto
                url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}/market_data"
                response = requests.get(url)
                if response.status_code == 200:
                    ratings['market_data'] = response.json()
            
            return ratings
            
        except Exception as e:
            logger.error(f"Error fetching analyst ratings: {e}")
            return {}

    async def _fetch_market_events(self, symbol: str, asset_type: str) -> List[Dict]:
        """Fetch significant market events and calendar items."""
        events = []
        
        try:
            if asset_type == 'stock':
                # Earnings Calendar
                yf_data = yf.Ticker(symbol)
                calendar = yf_data.calendar
                if calendar is not None:
                    events.extend([
                        {'type': 'earnings', 'data': calendar}
                    ])
                
                # SEC Filings
                filings = yf_data.get_sec_filings()
                if filings is not None:
                    events.extend([
                        {'type': 'sec_filing', 'data': filing}
                        for filing in filings.to_dict('records')
                    ])
            
            elif asset_type == 'crypto':
                # CoinGecko Events
                url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}/events"
                response = requests.get(url)
                if response.status_code == 200:
                    events.extend([
                        {'type': 'crypto_event', 'data': event}
                        for event in response.json()['data']
                    ])
            
            return events
            
        except Exception as e:
            logger.error(f"Error fetching market events: {e}")
            return []

    async def _fetch_regulatory_updates(self, symbol: str, asset_type: str) -> List[Dict]:
        """Fetch regulatory updates and compliance information."""
        updates = []
        
        try:
            # SEC API for stocks
            if asset_type == 'stock':
                sec_url = f"https://data.sec.gov/submissions/CIK{symbol}.json"
                response = requests.get(sec_url)
                if response.status_code == 200:
                    updates.extend([
                        {'type': 'sec_update', 'data': filing}
                        for filing in response.json()['filings']['recent']
                    ])
            
            # Regulatory news search
            serp_params = {
                "q": f"{symbol} regulation compliance news",
                "tbm": "nws",
                "num": 5
            }
            serp_response = self.serp_api.get_dict()
            
            if 'news_results' in serp_response:
                updates.extend([
                    {'type': 'regulatory_news', 'data': news}
                    for news in serp_response['news_results']
                ])
            
            return updates
            
        except Exception as e:
            logger.error(f"Error fetching regulatory updates: {e}")
            return []

    async def _analyze_competitors(self, symbol: str, asset_type: str) -> Dict[str, Any]:
        """Analyze competitor performance and relative metrics."""
        analysis = {}
        
        try:
            if asset_type == 'stock':
                # Get sector peers
                yf_data = yf.Ticker(symbol)
                info = yf_data.info
                
                if 'sector' in info:
                    # Find companies in same sector
                    sector_etf = self._get_sector_etf(info['sector'])
                    if sector_etf:
                        etf_data = yf.Ticker(sector_etf)
                        holdings = etf_data.get_holdings()
                        
                        if holdings is not None:
                            analysis['sector_peers'] = holdings.head(10).to_dict('records')
                
                # Relative performance
                if 'sector_peers' in analysis:
                    peer_performance = {}
                    for peer in analysis['sector_peers']:
                        peer_data = yf.Ticker(peer['symbol'])
                        peer_performance[peer['symbol']] = {
                            'return_1y': peer_data.info.get('regularMarketPrice', 0) / 
                                       peer_data.info.get('regularMarketPreviousClose', 1) - 1,
                            'market_cap': peer_data.info.get('marketCap', 0),
                            'pe_ratio': peer_data.info.get('forwardPE', 0)
                        }
                    analysis['peer_performance'] = peer_performance
            
            elif asset_type == 'crypto':
                # Get top coins by market cap
                url = "https://api.coingecko.com/api/v3/coins/markets"
                params = {
                    'vs_currency': 'usd',
                    'order': 'market_cap_desc',
                    'per_page': 10,
                    'page': 1
                }
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    analysis['market_leaders'] = response.json()
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing competitors: {e}")
            return {}

    async def _calculate_risk_metrics(self, symbol: str, asset_type: str) -> Dict[str, float]:
        """Calculate comprehensive risk metrics."""
        risk_metrics = {}
        
        try:
            # Get historical data
            if asset_type == 'stock':
                data = yf.download(symbol, period='1y')
            else:
                data = self.exchange.fetch_ohlcv(symbol, '1d', limit=365)
                data = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calculate risk metrics
            returns = data['close'].pct_change().dropna()
            
            risk_metrics.update({
                'volatility': returns.std() * np.sqrt(252),
                'var_95': returns.quantile(0.05),
                'max_drawdown': (data['close'] / data['close'].expanding(min_periods=1).max() - 1).min(),
                'sharpe_ratio': (returns.mean() * 252) / (returns.std() * np.sqrt(252)),
                'sortino_ratio': (returns.mean() * 252) / (returns[returns < 0].std() * np.sqrt(252))
            })
            
            return risk_metrics
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {}

    async def execute(self, agent: Agent, **kwargs) -> Dict[str, MarketIntelligence]:
        """Execute comprehensive market intelligence gathering."""
        try:
            symbols = kwargs['symbols']
            asset_types = kwargs['asset_types']
            data_types = kwargs.get('data_types', ['all'])
            
            results = {}
            
            for symbol, asset_type in zip(symbols, asset_types):
                # Get current price
                current_price = await self._get_current_price(symbol, asset_type)
                
                # Gather intelligence components
                market_news = await self._fetch_market_news(symbol, asset_type)
                social_metrics = await self._fetch_social_metrics(symbol, asset_type)
                fundamental_metrics = await self._fetch_fundamental_data(symbol, asset_type)
                analyst_ratings = await self._fetch_analyst_ratings(symbol, asset_type)
                market_events = await self._fetch_market_events(symbol, asset_type)
                regulatory_updates = await self._fetch_regulatory_updates(symbol, asset_type)
                competitor_analysis = await self._analyze_competitors(symbol, asset_type)
                risk_metrics = await self._calculate_risk_metrics(symbol, asset_type)
                
                # Combine all intelligence
                results[symbol] = MarketIntelligence(
                    symbol=symbol,
                    asset_type=asset_type,
                    timestamp=datetime.now(),
                    current_price=current_price,
                    market_news=market_news,
                    social_metrics=social_metrics,
                    fundamental_metrics=fundamental_metrics,
                    analyst_ratings=analyst_ratings,
                    market_events=market_events,
                    regulatory_updates=regulatory_updates,
                    competitor_analysis=competitor_analysis,
                    risk_metrics=risk_metrics
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing market intelligence gathering: {e}")
            raise

    def validate_arguments(self, **kwargs) -> bool:
        """Validate the provided arguments."""
        try:
            required_args = [arg.name for arg in self.arguments if arg.required]
            for arg in required_args:
                if arg not in kwargs:
                    raise ValueError(f"Missing required argument: {arg}")
                    
            if len(kwargs['symbols']) != len(kwargs['asset_types']):
                raise ValueError("Number of symbols must match number of asset types")
                
            valid_asset_types = ['crypto', 'stock', 'index']
            invalid_types = set(kwargs['asset_types']) - set(valid_asset_types)
            if invalid_types:
                raise ValueError(f"Invalid asset types: {invalid_types}")
                
            return True
        except Exception as e:
            logger.error(f"Argument validation error: {e}")
            return False
