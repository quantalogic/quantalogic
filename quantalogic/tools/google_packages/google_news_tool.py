"""Advanced tool for retrieving and analyzing news articles from Google News.

This tool provides a sophisticated interface to fetch, analyze, and format news articles
from Google News using multiple sources and advanced filtering capabilities.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
from urllib.parse import quote_plus
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from gnews import GNews
from loguru import logger
from pydantic import Field, validator, ConfigDict 
import html2text

from quantalogic.tools.tool import Tool, ToolArgument 
from quantalogic.event_emitter import EventEmitter


class NewsArticle:
    """Represents a news article with enhanced metadata and analysis."""
    
    def __init__(self, title: str, url: str, source: str, date: str):
        self.title = title
        self.url = url
        self.source = source
        self.date = date
        self.description = ""
        self.full_text = ""
        self.keywords = []
        self.sentiment = {}
        self.summary = ""
        
    async def enrich(self, session: aiohttp.ClientSession):
        """Enrich article with additional data and analysis."""
        try:
            # Fetch article content
            async with session.get(self.url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    
                    # Convert HTML to text
                    h = html2text.HTML2Text()
                    h.ignore_links = True
                    h.ignore_images = True
                    self.full_text = h.handle(html_content)
                    
                    # Extract main content using BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Remove unwanted elements
                    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                        tag.decompose()
                    
                    # Get main content
                    main_content = soup.find('main') or soup.find('article') or soup.find('body')
                    if main_content:
                        self.full_text = main_content.get_text(strip=True)
                    
                    # Basic keyword extraction from title and content
                    words = set(word.lower() for word in self.title.split() + self.full_text.split()
                              if len(word) > 3)
                    self.keywords = list(words)[:10]  # Top 10 keywords
                    
                    # Create a basic summary (first 2-3 sentences)
                    sentences = [s.strip() for s in self.full_text.split('.') if s.strip()]
                    self.summary = '. '.join(sentences[:3]) + '.'
                    
                    # Perform sentiment analysis
                    # sia = SentimentIntensityAnalyzer()
                    # self.sentiment = sia.polarity_scores(self.title + " " + self.summary)
                    self.sentiment = {'pos': 0.0, 'neg': 0.0, 'neu': 1.0, 'compound': 0.0}
            
        except Exception as e:
            logger.warning(f"Error enriching article {self.url}: {str(e)}")
            # Set basic info even if enrichment fails
            self.summary = self.title
            self.keywords = [word.lower() for word in self.title.split() if len(word) > 3]
            self.sentiment = {'pos': 0.0, 'neg': 0.0, 'neu': 1.0, 'compound': 0.0}


class GoogleNewsTool(Tool):
    """Advanced tool for retrieving and analyzing news articles from Google News.

    Features:
    - Multi-source news aggregation
    - Sentiment analysis
    - Keyword extraction
    - Article summarization
    - Advanced filtering
    - Async processing for better performance
    """

    name: str = "google_news_tool"
    need_post_process: bool = False
    description: str = (
        "Advanced news retrieval and analysis tool with support for sentiment analysis, "
        "keyword extraction, and article summarization."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="The news search query",
            required=True,
            example="artificial intelligence developments",
        ),
        ToolArgument(
            name="language",
            arg_type="string",
            description="Language code (e.g., 'en' for English)",
            required=False,
            default="en",
            example="en",
        ),
        ToolArgument(
            name="period",
            arg_type="string",
            description="Time period (1h, 1d, 7d, 1m)",
            required=False,
            default="1d",
            example="7d",
        ),
        ToolArgument(
            name="max_results",
            arg_type="int",
            description="Maximum number of results (1-100)",
            required=False,
            default="25",
            example="20",
        ),
        ToolArgument(
            name="country",
            arg_type="string",
            description="Country code for news sources",
            required=False,
            default="US",
            example="GB",
        ),
        ToolArgument(
            name="sort_by",
            arg_type="string",
            description="Sort by relevance or date",
            required=False,
            default="relevance",
            example="date",
        ),
        ToolArgument(
            name="analyze",
            arg_type="boolean",
            description="Perform detailed analysis of articles",
            required=False,
            default="True",
            example="True",
        ),
    ]

    def __init__(self, name: str | None = None):
        """Initialize the GoogleNewsTool.
        
        Args:
            name (str | None): Optional name override for the tool
        """
        super().__init__()
        if name:
            self.name = name

    def _format_html_output(self, articles: List[Dict[str, Any]], query: str) -> str:
        """Format articles as HTML with a modern, clean design."""
        return json.dumps(articles, indent=2)

    def _fetch_article_data(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Fetch detailed data for multiple articles."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def fetch_all():
            tasks = []
            async with aiohttp.ClientSession() as session:
                for article in articles:
                    tasks.append(article.enrich(session))
                await asyncio.gather(*tasks)
            return articles

        return loop.run_until_complete(fetch_all())

    def _get_sentiment_level(self, score: float) -> str:
        """Convert sentiment score to descriptive level."""
        if score >= 0.6:
            return "Very High"
        elif score >= 0.4:
            return "High"
        elif score >= 0.2:
            return "Moderate"
        elif score > 0.1:
            return "Low"
        else:
            return "Very Low"

    def _interpret_sentiment(self, sentiment: Dict[str, float]) -> str:
        """Interpret the overall sentiment of the text."""
        compound = sentiment.get('compound', 0)
        if compound >= 0.5:
            return "Very Positive"
        elif compound >= 0.1:
            return "Slightly Positive"
        elif compound <= -0.5:
            return "Very Negative"
        elif compound <= -0.1:
            return "Slightly Negative"
        else:
            return "Neutral"

    def execute(
        self,
        query: str,
        language: str = "en",
        period: str = "1m",
        max_results: int = 30,
        country: str = "US",
        sort_by: str = "relevance",
        analyze: bool = True,
    ) -> str:
        """Execute the Google News search and return full articles in JSON format.

        Args:
            query (str): Search query
            language (str, optional): Language code. Defaults to "en".
            period (str, optional): Time period. Defaults to "1m".
            max_results (int, optional): Maximum results. Defaults to 30.
            country (str, optional): Country code. Defaults to "US".
            sort_by (str, optional): Sort method. Defaults to "relevance".
            analyze (bool, optional): Whether to analyze results. Defaults to True.

        Returns:
            str: JSON-formatted string containing list of article dictionaries with full content
        """
        try:
            # Input validation
            if not query:
                raise ValueError("Query cannot be empty")

            # Configure GNews
            google_news = GNews(
                language=language,
                country=country,
                period=period,
                max_results=max_results,
            )

            # Fetch news
            logger.info(f"Fetching news for query: {query}")
            articles = []
            try:
                raw_articles = google_news.get_news(query)
                for article_data in raw_articles:
                    articles.append(
                        NewsArticle(
                            title=article_data.get("title", ""),
                            url=article_data.get("url", ""),
                            source=article_data.get("publisher", {}).get("title", ""),
                            date=article_data.get("published date", ""),
                        )
                    )
            except Exception as e:
                logger.error(f"Error fetching articles: {e}")
                raise RuntimeError(f"Failed to fetch articles: {str(e)}")

            # Enrich articles with additional data if requested
            if analyze:
                logger.info("Performing detailed analysis of articles...")
                articles = self._fetch_article_data(articles)
            
            # Sort results if needed
            if sort_by == "date":
                articles.sort(key=lambda x: x.date if x.date else "", reverse=True)
            
            # Process and return full article data
            processed_articles = []
            for article in articles:
                processed_article = {
                    'title': article.title,
                    'url': article.url,
                    'source': article.source,
                    'date': article.date,
                    'full_text': article.full_text if hasattr(article, 'full_text') else '',
                    'keywords': article.keywords if hasattr(article, 'keywords') else [],
                    'sentiment': article.sentiment if hasattr(article, 'sentiment') else {},
                    'summary': article.summary if hasattr(article, 'summary') else ''
                }
                processed_articles.append(processed_article)


            logger.info(f"Fetched {len(processed_articles)} articles for query: {query}")
            # Return pretty-printed JSON string, matching DuckDuckGo tool format
            return json.dumps(processed_articles, indent=4, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error in GoogleNewsTool: {e}")
            raise Exception(f"Failed to fetch news: {str(e)}")


if __name__ == "__main__":
    # Example usage with analysis
    tool = GoogleNewsTool()
    try:
        result = tool.execute(
            query="XRP crypto coin",
            language="en",
            period="7d",
            max_results=25,
            analyze=True
        )
        print(result)
    except Exception as e:
        print(f"Error: {e}")
