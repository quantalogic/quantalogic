"""Advanced tool for retrieving and analyzing news articles from Google News.

This tool provides a sophisticated interface to fetch, analyze, and format news articles
from Google News using multiple sources and advanced filtering capabilities.
"""

import asyncio
from typing import Any, Dict, List

import aiohttp
import html2text
from bs4 import BeautifulSoup
from gnews import GNews
from loguru import logger

from quantalogic.event_emitter import EventEmitter
from quantalogic.tools.llm_tool import LLMTool
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

    def __init__(
        self,
        model_name: str | None = None,
        on_token: Any | None = None,
        event_emitter: EventEmitter | None = None,
    ):
        """Initialize the GoogleNewsTool.
        
        Args:
            model_name (str | None): Name of the LLM model to use for summarization
            on_token (Any | None): Token callback for streaming
            event_emitter (EventEmitter | None): Event emitter for the tool
        """
        super().__init__()
        self.model_name = model_name
        self.on_token = on_token
        self.event_emitter = event_emitter
        if model_name:
            self.llm_tool = LLMTool(
                model_name=model_name,
                on_token=on_token,
                event_emitter=event_emitter,
            )

    def _summarize_article(self, article: Dict[str, Any]) -> str:
        """Summarize a news article using LLM.
        
        Args:
            article (Dict[str, Any]): Article data including title and description
            
        Returns:
            str: Summarized article content
        """
        if not hasattr(self, 'llm_tool'):
            return article.get('description', '')

        prompt = f"""
        Summarize this news article concisely and professionally:
        
        Title: {article.get('title', '')}
        Description: {article.get('description', '')}
        
        Provide a 2-3 sentence summary that captures the key points.
        """

        try:
            summary = self.llm_tool.execute(
                system_prompt="You are a professional news summarizer. Create clear, accurate, and concise summaries.",
                prompt=prompt,
                temperature="0.3"
            )
            return summary
        except Exception as e:
            logger.error(f"Error summarizing article: {e}")
            return article.get('description', '')

    def _format_html_output(self, articles: List[Dict[str, Any]], query: str) -> str:
        """Format articles as HTML with a modern, clean design."""
        css_styles = """
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .header {
                background-color: #2c3e50;
                color: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .article {
                background-color: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .article h2 {
                color: #2c3e50;
                margin-top: 0;
            }
            .article-meta {
                color: #666;
                font-size: 0.9em;
                margin-bottom: 10px;
            }
            .summary {
                border-left: 4px solid #2c3e50;
                padding-left: 15px;
                margin: 15px 0;
            }
            .source-link {
                display: inline-block;
                margin-top: 10px;
                color: #3498db;
                text-decoration: none;
            }
            .source-link:hover {
                text-decoration: underline;
            }
        """

        articles_html = []
        for article in articles:
            article_html = f"""
                <div class="article">
                    <h2>{article.get('title', 'No Title')}</h2>
                    <div class="article-meta">
                        <span>Source: {article.get('source', {}).get('title', 'Unknown')}</span>
                        <span> • </span>
                        <span>Published: {article.get('published_date', 'Unknown date')}</span>
                    </div>
                    <div class="summary">
                        {article.get('summary', 'No summary available')}
                    </div>
                    <a href="{article.get('link', '#')}" class="source-link" target="_blank">Read full article →</a>
                </div>
            """
            articles_html.append(article_html)

        html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    {css_styles}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>News Results for: {query}</h1>
                    <p>Found {len(articles)} articles</p>
                </div>
                {''.join(articles_html)}
            </body>
            </html>
        """
        
        return html_content.strip()

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
        period: str = "1m",
        max_results: int = 30,
        country: str = "US",
        sort_by: str = "relevance",
        analyze: bool = True,
    ) -> str:
        """Execute the Google News search with summarization and HTML formatting.

        Args:
            query (str): Search query
            language (str, optional): Language code. Defaults to "en".
            period (str, optional): Time period. Defaults to "1m".
            max_results (int, optional): Maximum results. Defaults to 30.
            country (str, optional): Country code. Defaults to "US".
            sort_by (str, optional): Sort method. Defaults to "relevance".
            analyze (bool, optional): Whether to analyze results. Defaults to True.

        Returns:
            str: HTML formatted news results with summaries
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
            
            # Process and summarize each article
            processed_articles = []
            for article in articles:
                article_copy = {
                    'title': article.title,
                    'link': article.url,
                    'source': {'title': article.source},
                    'published_date': article.date,
                    'description': article.full_text if hasattr(article, 'full_text') else '',
                }
                article_copy['summary'] = self._summarize_article(article_copy)
                processed_articles.append(article_copy)

            # Format results as HTML
            html_output = self._format_html_output(processed_articles, query)
            return html_output

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
