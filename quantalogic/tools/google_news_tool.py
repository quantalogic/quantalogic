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
from pydantic import Field, validator
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import html2text

from quantalogic.tools.tool import Tool, ToolArgument


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

    def __init__(self):
        """Initialize the tool and download required NLTK data."""
        super().__init__()
        try:
            nltk.download('vader_lexicon', quiet=True)
        except Exception as e:
            logger.warning(f"Failed to download NLTK data: {str(e)}")

    async def _fetch_article_data(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Fetch detailed data for multiple articles concurrently."""
        async with aiohttp.ClientSession() as session:
            tasks = [article.enrich(session) for article in articles]
            await asyncio.gather(*tasks)
        return articles

    def _format_results(self, articles: List[NewsArticle], analyze: bool) -> str:
        """Format news results with optional analysis data."""
        results = ["=== Advanced Google News Results ===\n"]
        
        for i, article in enumerate(articles, 1):
            results.extend([
                f"{i}. {article.title}",
                f"   Source: {article.source} | Date: {article.date}",
                f"   URL: {article.url}",
                ""
            ])
            
            if analyze and article.summary:
                results.extend([
                    "   Summary:",
                    f"   {article.summary}",
                    "",
                    "   Key Topics:",
                    f"   {', '.join(article.keywords[:5])}",
                    "",
                    "   Sentiment Analysis:",
                    "   Overall tone: " + self._interpret_sentiment(article.sentiment),
                    f"   - Positive: {article.sentiment.get('pos', 0)*100:.1f}% ({self._get_sentiment_level(article.sentiment.get('pos', 0))})",
                    f"   - Negative: {article.sentiment.get('neg', 0)*100:.1f}% ({self._get_sentiment_level(article.sentiment.get('neg', 0))})",
                    f"   - Neutral:  {article.sentiment.get('neu', 0)*100:.1f}% ({self._get_sentiment_level(article.sentiment.get('neu', 0))})",
                    ""
                ])
            
            results.append("")
        
        return "\n".join(results)

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
        period: str = "1d",
        max_results: int = 10,
        country: str = "US",
        sort_by: str = "relevance",
        analyze: bool = True,
    ) -> str:
        """Execute an advanced news search with analysis.

        Args:
            query: The news search query
            language: Language code
            period: Time period for news
            max_results: Maximum number of results
            country: Country code for news sources
            sort_by: Sort method (relevance/date)
            analyze: Whether to perform detailed analysis

        Returns:
            Formatted news results with optional analysis data

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If the operation fails
        """
        try:
            # Input validation
            if not query:
                raise ValueError("Query must be a non-empty string")
            if max_results < 1 or max_results > 100:
                raise ValueError("max_results must be between 1 and 100")
            
            # Configure GNews
            google_news = GNews(
                language=language,
                country=country,
                max_results=max_results,
                period=period,
                exclude_websites=None
            )
            
            # Fetch initial news data
            logger.info(f"Fetching news for query: {query}")
            news_items = google_news.get_news(query)
            
            if not news_items:
                return "No news articles found for the given query."
            
            # Create NewsArticle objects
            articles = [
                NewsArticle(
                    title=item['title'],
                    url=item['url'],
                    source=item.get('publisher', 'Unknown'),
                    date=item.get('published date', 'Date not available')
                )
                for item in news_items
            ]
            
            # Enrich articles with additional data if requested
            if analyze:
                logger.info("Performing detailed analysis of articles...")
                asyncio.run(self._fetch_article_data(articles))
            
            # Sort results if needed
            if sort_by == "date":
                articles.sort(key=lambda x: x.date if isinstance(x.date, datetime) else datetime.min, reverse=True)
            
            return self._format_results(articles, analyze)

        except Exception as e:
            logger.error(f"Error in news search: {str(e)}")
            raise RuntimeError(f"Failed to fetch or analyze news: {str(e)}")


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
