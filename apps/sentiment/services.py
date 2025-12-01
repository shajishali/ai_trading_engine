import requests
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.db.models import Q, Avg, Count
from apps.sentiment.models import (
    SocialMediaSource, NewsSource, SocialMediaPost, NewsArticle,
    CryptoMention, SentimentAggregate, Influencer, SentimentModel
)
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class TwitterService:
    """Service for Twitter/X API integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'TWITTER_API_KEY', None)
        self.api_secret = getattr(settings, 'TWITTER_API_SECRET', None)
        self.bearer_token = getattr(settings, 'TWITTER_BEARER_TOKEN', None)
        self.base_url = "https://api.twitter.com/2"
    
    def search_tweets(self, query: str, max_results: int = 100) -> List[Dict]:
        """Search for tweets containing crypto-related keywords"""
        if not self.bearer_token:
            logger.warning("Twitter API credentials not configured")
            return []
        
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,author_id,public_metrics",
            "user.fields": "username,name,public_metrics",
            "expansions": "author_id"
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/tweets/search/recent",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception as e:
            logger.error(f"Error fetching Twitter data: {e}")
            return []
    
    def get_user_tweets(self, user_id: str, max_results: int = 100) -> List[Dict]:
        """Get tweets from a specific user"""
        if not self.bearer_token:
            return []
        
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics",
            "exclude": "retweets,replies"
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/users/{user_id}/tweets",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception as e:
            logger.error(f"Error fetching user tweets: {e}")
            return []


class RedditService:
    """Service for Reddit API integration"""
    
    def __init__(self):
        self.client_id = getattr(settings, 'REDDIT_CLIENT_ID', None)
        self.client_secret = getattr(settings, 'REDDIT_CLIENT_SECRET', None)
        self.user_agent = "AI-Trading-Signal-Engine/1.0"
    
    def search_posts(self, subreddit: str, query: str, limit: int = 100) -> List[Dict]:
        """Search for posts in a subreddit"""
        if not self.client_id or not self.client_secret:
            logger.warning("Reddit API credentials not configured")
            return []
        
        headers = {
            "User-Agent": self.user_agent
        }
        
        auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
        data = {
            "grant_type": "client_credentials"
        }
        
        try:
            # Get access token
            token_response = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth,
                data=data,
                headers=headers
            )
            token_response.raise_for_status()
            access_token = token_response.json()['access_token']
            
            # Search posts
            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.get(
                f"https://oauth.reddit.com/r/{subreddit}/search",
                headers=headers,
                params={"q": query, "limit": limit, "sort": "new"}
            )
            response.raise_for_status()
            
            posts = []
            for post in response.json()['data']['children']:
                post_data = post['data']
                posts.append({
                    'id': post_data['id'],
                    'title': post_data['title'],
                    'content': post_data['selftext'],
                    'author': post_data['author'],
                    'score': post_data['score'],
                    'created_utc': post_data['created_utc'],
                    'num_comments': post_data['num_comments']
                })
            
            return posts
        except Exception as e:
            logger.error(f"Error fetching Reddit data: {e}")
            return []


class CryptoPanicService:
    """Service for CryptoPanic API integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'CRYPTOPANIC_API_KEY', None)
        self.base_url = "https://cryptopanic.com/api/v1"
    
    def get_posts(self, kind: str = 'news', currencies: str = None, filter: str = None) -> List[Dict]:
        """Get posts from CryptoPanic API
        
        Args:
            kind: Type of posts ('news', 'media', 'hot')
            currencies: Comma-separated currency codes (e.g., 'BTC,ETH')
            filter: Filter by type ('hot', 'rising', 'bullish', 'bearish')
        """
        if not self.api_key:
            logger.warning("CryptoPanic API key not configured")
            return []
        
        params = {
            "auth_token": self.api_key,
            "kind": kind
        }
        
        if currencies:
            params["currencies"] = currencies
        
        if filter:
            params["filter"] = filter
        
        try:
            response = requests.get(
                f"{self.base_url}/posts/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Transform CryptoPanic format to match expected format
            posts = data.get('results', [])
            articles = []
            
            for post in posts:
                # Map CryptoPanic fields to standard format
                article = {
                    'title': post.get('title', ''),
                    'description': post.get('title', ''),  # CryptoPanic uses title
                    'url': post.get('url', ''),
                    'publishedAt': post.get('created_at', ''),
                    'source': {
                        'name': post.get('source', {}).get('title', 'CryptoPanic'),
                        'url': post.get('source', {}).get('url', 'https://cryptopanic.com')
                    },
                    'votes': post.get('votes', {}),
                    'currencies': post.get('currencies', []),
                    'kind': post.get('kind', kind)
                }
                articles.append(article)
            
            return articles
        except Exception as e:
            logger.error(f"Error fetching CryptoPanic data: {e}")
            return []
    
    def get_crypto_news(self, currencies: str = None) -> List[Dict]:
        """Get crypto news from CryptoPanic"""
        return self.get_posts(kind='news', currencies=currencies)


class CryptoNewsAPIService:
    """Service for CryptoNewsAPI.online integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'CRYPTONEWS_API_KEY', None)
        # CryptoNewsAPI.online uses different base URL and authentication
        self.base_url = "https://cryptonewsapi.online"
        if self.api_key:
            # Strip whitespace and remove any comments
            self.api_key = self.api_key.strip().split('#')[0].strip()
            if self.api_key:
                logger.info(f"CryptoNewsAPI.online API key loaded (length: {len(self.api_key)})")
            else:
                logger.warning("CryptoNewsAPI.online API key is empty after cleaning")
        else:
            logger.warning("CryptoNewsAPI.online API key not found in settings")
    
    def get_news(self, currencies: str = None, items: int = 50) -> List[Dict]:
        """Get crypto news from CryptoNewsAPI.online
        
        Args:
            currencies: Comma-separated currency codes (e.g., 'BTC,ETH')
            items: Number of news items to fetch (default: 50)
        """
        if not self.api_key:
            logger.warning("CryptoNewsAPI key not configured")
            return []
        
        # CryptoNewsAPI.online uses token as query parameter
        params = {
            "token": self.api_key,
            "limit": min(items, 50)  # Limit to reasonable number
        }
        
        if currencies:
            # Add currency filter if provided
            params["currencies"] = currencies
        
        headers = {
            "Accept": "application/json"
        }
        
        # Try different endpoint formats
        endpoints = [
            f"{self.base_url}/news",
            f"{self.base_url}/api/news",
            f"https://api.cryptonewsapi.online/news"
        ]
        
        response = None
        for endpoint in endpoints:
            try:
                logger.info(f"Making request to CryptoNewsAPI.online: {endpoint}")
                response = requests.get(
                    endpoint,
                    params=params,
                    headers=headers,
                    timeout=15
                )
                
                logger.info(f"CryptoNewsAPI.online response status: {response.status_code}")
                
                if response.status_code == 200:
                    break  # Success, use this endpoint
                elif response.status_code == 404:
                    continue  # Try next endpoint
                else:
                    logger.warning(f"CryptoNewsAPI.online endpoint {endpoint} returned {response.status_code}")
                    continue
            except Exception as e:
                logger.warning(f"Error trying endpoint {endpoint}: {e}")
                continue
        
        if not response or response.status_code != 200:
            if response:
                logger.error(f"CryptoNewsAPI.online returned error: {response.status_code} - {response.text[:200]}")
            else:
                logger.error("CryptoNewsAPI.online: All endpoints failed")
            return []
        
        try:
            
            response.raise_for_status()
            data = response.json()
            
            # Transform CryptoNewsAPI.online format to match expected format
            articles = []
            # CryptoNewsAPI.online may return data directly as array or in 'data' field
            news_items = data if isinstance(data, list) else data.get('data', []) or data.get('articles', [])
            
            if not news_items:
                logger.warning(f"CryptoNewsAPI.online returned no news items. Response keys: {list(data.keys()) if isinstance(data, dict) else 'array'}")
                return []
            
            logger.info(f"CryptoNewsAPI.online returned {len(news_items)} news items")
            
            for item in news_items:
                # Handle date format from CryptoNewsAPI.online
                published_at = item.get('published_at', '') or item.get('date', '') or item.get('publishedAt', '')
                if not published_at:
                    published_at = datetime.now().isoformat() + '+00:00'
                elif not published_at.endswith('Z') and '+' not in published_at:
                    # Convert to ISO format if needed
                    try:
                        # Try parsing different formats
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%SZ']:
                            try:
                                dt = datetime.strptime(published_at.replace('Z', ''), fmt.replace('Z', ''))
                                published_at = dt.isoformat() + '+00:00'
                                break
                            except ValueError:
                                continue
                    except:
                        published_at = datetime.now().isoformat() + '+00:00'
                
                article = {
                    'title': item.get('title', ''),
                    'description': item.get('description', '') or item.get('text', '') or item.get('summary', ''),
                    'url': item.get('url', '') or item.get('news_url', '') or item.get('link', ''),
                    'publishedAt': published_at,
                    'source': {
                        'name': item.get('source', '') or item.get('source_name', 'CryptoNewsAPI.online'),
                        'url': item.get('source_url', 'https://cryptonewsapi.online')
                    },
                    'currencies': item.get('currencies', []) if isinstance(item.get('currencies'), list) else [],
                    'sentiment': item.get('sentiment', 'neutral')
                }
                articles.append(article)
            
            logger.info(f"Fetched {len(articles)} articles from CryptoNewsAPI.online")
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching CryptoNewsAPI.online data: {e}", exc_info=True)
            return []


class StockDataService:
    """Service for StockData.org API integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'STOCKDATA_API_KEY', None)
        self.base_url = "https://api.stockdata.org/v1"
        if self.api_key:
            # Strip whitespace and remove any comments
            self.api_key = self.api_key.strip().split('#')[0].strip()
            if self.api_key:
                logger.info(f"StockData.org API key loaded (length: {len(self.api_key)})")
            else:
                logger.warning("StockData.org API key is empty after cleaning")
        else:
            logger.warning("StockData.org API key not found in settings")
    
    def get_crypto_news(self, symbols: str = None, limit: int = 50) -> List[Dict]:
        """Get crypto news from StockData.org
        
        Args:
            symbols: Comma-separated crypto symbols (e.g., 'BTC,ETH')
            limit: Number of news items to fetch (default: 50, max based on plan)
        """
        if not self.api_key:
            logger.warning("StockData.org API key not configured")
            return []
        
        # StockData.org API uses api_token as query parameter
        # Note: Free plans may have lower limits, so we'll use a reasonable default
        params = {
            "api_token": self.api_key.strip(),  # Ensure no whitespace
            "limit": min(limit, 10),  # Limit to 10 to avoid plan restrictions
            # Use search parameter to filter for crypto-related news
            "search": "bitcoin OR ethereum OR cryptocurrency OR crypto OR blockchain OR BTC OR ETH OR SOL OR BNB OR ADA OR XRP"
        }
        
        # Add crypto symbols if provided (limit to a few major ones to avoid issues)
        if symbols:
            # Take only first 5 symbols to avoid API issues
            symbol_list = symbols.split(',')[:5]
            # Add symbols to search query
            symbol_search = " OR ".join(symbol_list)
            params["search"] = f"{params['search']} OR {symbol_search}"
        
        # Also try with Authorization header as some APIs prefer that
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Accept": "application/json"
        }
        
        try:
            logger.info(f"Making request to StockData.org API: {self.base_url}/news/all")
            logger.debug(f"Request params: api_token={'*' * 10}..., limit={limit}, symbols={symbols[:50] if symbols else None}")
            
            # Try with query parameter first (standard StockData.org format)
            response = requests.get(
                f"{self.base_url}/news/all",
                params=params,
                headers=headers,
                timeout=15
            )
            
            logger.info(f"StockData.org API response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"StockData.org API returned error: {response.status_code} - {response.text[:200]}")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            # Check for warnings (like limit exceeded)
            if 'warnings' in data:
                for warning in data['warnings']:
                    logger.warning(f"StockData.org API warning: {warning}")
            
            # Check if we got data
            if not data:
                logger.warning("StockData.org API returned empty response")
                return []
            
            # Transform StockData.org format to match expected format
            articles = []
            news_items = data.get('data', [])
            
            if not news_items:
                logger.warning(f"StockData.org API returned no news items. Response keys: {list(data.keys())}")
                # Log meta info if available
                if 'meta' in data:
                    logger.info(f"API meta info: {data['meta']}")
                return []
            
            logger.info(f"StockData.org returned {len(news_items)} news items (requested limit: {params.get('limit', 'N/A')})")
            
            for item in news_items:
                # Handle date format from StockData.org
                published_at = item.get('published_at', '') or item.get('date', '')
                if not published_at:
                    published_at = datetime.now().isoformat() + '+00:00'
                elif not published_at.endswith('Z') and '+' not in published_at:
                    # Convert to ISO format if needed
                    try:
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                            try:
                                dt = datetime.strptime(published_at, fmt)
                                published_at = dt.isoformat() + '+00:00'
                                break
                            except ValueError:
                                continue
                    except:
                        published_at = datetime.now().isoformat() + '+00:00'
                
                article = {
                    'title': item.get('title', ''),
                    'description': item.get('description', '') or item.get('text', '') or item.get('snippet', ''),
                    'url': item.get('url', '') or item.get('link', ''),
                    'publishedAt': published_at,
                    'source': {
                        'name': item.get('source', '') or item.get('source_name', 'StockData.org'),
                        'url': item.get('source_url', 'https://stockdata.org')
                    },
                    'currencies': item.get('symbols', []) if isinstance(item.get('symbols'), list) else [],
                    'sentiment': item.get('sentiment', 'neutral')
                }
                articles.append(article)
            
            logger.info(f"Fetched {len(articles)} articles from StockData.org")
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching StockData.org data: {e}", exc_info=True)
            return []


class NewsAPIService:
    """Service for news API integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'NEWS_API_KEY', None)
        self.base_url = "https://newsapi.org/v2"
        # Try StockData.org first (preferred - good crypto news coverage)
        self.stockdata_service = StockDataService()
        # Try CryptoNewsAPI second (preferred for crypto news)
        self.cryptonews_service = CryptoNewsAPIService()
        # Try CryptoPanic as fallback
        self.cryptopanic_service = CryptoPanicService()
    
    def search_news(self, query: str, from_date: str = None, language: str = 'en') -> List[Dict]:
        """Search for news articles"""
        if not self.api_key:
            logger.warning("News API key not configured")
            return []
        
        params = {
            "q": query,
            "apiKey": self.api_key,
            "language": language,
            "sortBy": "publishedAt"
        }
        
        if from_date:
            params["from"] = from_date
        
        try:
            response = requests.get(
                f"{self.base_url}/everything",
                params=params
            )
            response.raise_for_status()
            return response.json().get('articles', [])
        except Exception as e:
            logger.error(f"Error fetching news data: {e}")
            return []
    
    def get_crypto_news(self, from_date: str = None, use_cryptopanic: bool = True) -> List[Dict]:
        """Get crypto-specific news
        
        Priority order:
        1. CryptoNewsAPI.online (preferred - dedicated crypto news API)
        2. StockData.org (good crypto news coverage)
        3. CryptoPanic (fallback)
        4. NewsAPI.org (last resort)
        
        Args:
            from_date: Date filter (for NewsAPI only)
            use_cryptopanic: If True, try CryptoPanic as fallback
        """
        # Debug: Log which API keys are available
        logger.info(f"Checking available news APIs - StockData: {bool(self.stockdata_service.api_key)}, "
                   f"CryptoNewsAPI: {bool(self.cryptonews_service.api_key)}, "
                   f"CryptoPanic: {bool(self.cryptopanic_service.api_key)}, "
                   f"NewsAPI: {bool(self.api_key)}")
        
        # Try CryptoNewsAPI.online first (preferred - dedicated crypto news API)
        if self.cryptonews_service.api_key:
            logger.info("Fetching crypto news from CryptoNewsAPI.online")
            try:
                cryptonews_articles = self.cryptonews_service.get_news(items=50)
                if cryptonews_articles and len(cryptonews_articles) > 0:
                    logger.info(f"Successfully fetched {len(cryptonews_articles)} articles from CryptoNewsAPI.online")
                    return cryptonews_articles
                else:
                    logger.warning("CryptoNewsAPI.online returned 0 articles, trying StockData.org...")
            except Exception as e:
                logger.warning(f"Error fetching from CryptoNewsAPI.online: {e}, trying StockData.org...")
        
        # Try StockData.org second (good crypto news coverage)
        if self.stockdata_service.api_key:
            logger.info("Fetching crypto news from StockData.org")
            # Get common crypto symbols for filtering (limit to top 5 to avoid API issues)
            crypto_symbols = "BTC,ETH,SOL,BNB,ADA"
            try:
                stockdata_articles = self.stockdata_service.get_crypto_news(symbols=crypto_symbols, limit=10)
                if stockdata_articles and len(stockdata_articles) > 0:
                    logger.info(f"Successfully fetched {len(stockdata_articles)} articles from StockData.org")
                    return stockdata_articles
                else:
                    logger.warning("StockData.org returned 0 articles")
            except Exception as e:
                logger.error(f"Error fetching from StockData.org: {e}", exc_info=True)
        
        # Try CryptoPanic as fallback if enabled and API key is available
        if use_cryptopanic and self.cryptopanic_service.api_key:
            logger.info("Fetching crypto news from CryptoPanic API")
            cryptopanic_news = self.cryptopanic_service.get_crypto_news()
            if cryptopanic_news:
                return cryptopanic_news
        
        # Fallback to NewsAPI if other services are not available
        if self.api_key:
            logger.info("Fetching crypto news from NewsAPI.org")
            crypto_keywords = [
                "bitcoin", "ethereum", "cryptocurrency", "blockchain",
                "crypto", "defi", "nft", "altcoin"
            ]
            
            all_articles = []
            for keyword in crypto_keywords:
                articles = self.search_news(keyword, from_date)
                all_articles.extend(articles)
            
            return all_articles
        
        logger.warning("No crypto news API configured - Please set STOCKDATA_API_KEY, CRYPTONEWS_API_KEY, CRYPTOPANIC_API_KEY, or NEWS_API_KEY in your environment variables")
        return []


class SentimentAnalysisService:
    """Service for sentiment analysis using NLP models"""
    
    def __init__(self):
        self.models = {}
        self.load_models()
    
    def load_models(self):
        """Load trained sentiment analysis models"""
        try:
            # In production, load actual trained models
            # For now, use simple rule-based approach
            self.models['rule_based'] = self._rule_based_sentiment
            logger.info("Sentiment models loaded successfully")
        except Exception as e:
            logger.error(f"Error loading sentiment models: {e}")
    
    def analyze_text_sentiment(self, text: str, model_type: str = 'rule_based') -> Dict:
        """Analyze sentiment of text using specified model"""
        if model_type not in self.models:
            logger.warning(f"Model {model_type} not found, using rule_based")
            model_type = 'rule_based'
        
        return self.models[model_type](text)
    
    def _rule_based_sentiment(self, text: str) -> Dict:
        """Simple rule-based sentiment analysis"""
        text_lower = text.lower()
        
        # Bullish keywords
        bullish_words = [
            'bullish', 'moon', 'pump', 'rally', 'surge', 'breakout',
            'buy', 'long', 'hodl', 'diamond hands', 'to the moon',
            'bull run', 'accumulate', 'strong', 'bullish af'
        ]
        
        # Bearish keywords
        bearish_words = [
            'bearish', 'dump', 'crash', 'sell', 'short', 'paper hands',
            'bear market', 'correction', 'dip', 'weak', 'bearish af',
            'dump it', 'sell signal'
        ]
        
        bullish_count = sum(1 for word in bullish_words if word in text_lower)
        bearish_count = sum(1 for word in bearish_words if word in text_lower)
        
        # Calculate sentiment score (-1 to 1)
        total_words = len(text.split())
        if total_words == 0:
            sentiment_score = 0
        else:
            sentiment_score = (bullish_count - bearish_count) / max(total_words, 1)
            sentiment_score = max(-1, min(1, sentiment_score))
        
        # Determine label
        if sentiment_score > 0.1:
            sentiment_label = 'bullish'
        elif sentiment_score < -0.1:
            sentiment_label = 'bearish'
        else:
            sentiment_label = 'neutral'
        
        # Calculate confidence based on keyword density
        confidence_score = min(1.0, (bullish_count + bearish_count) / max(total_words, 1))
        
        return {
            'sentiment_score': sentiment_score,
            'sentiment_label': sentiment_label,
            'confidence_score': confidence_score,
            'bullish_count': bullish_count,
            'bearish_count': bearish_count
        }
    
    def analyze_crypto_mentions(self, text: str, crypto_symbols: List[str]) -> List[Dict]:
        """Analyze sentiment for specific crypto mentions in text"""
        mentions = []
        
        for symbol in crypto_symbols:
            if symbol.lower() in text.lower():
                sentiment_result = self.analyze_text_sentiment(text)
                mentions.append({
                    'symbol': symbol,
                    'sentiment_score': sentiment_result['sentiment_score'],
                    'sentiment_label': sentiment_result['sentiment_label'],
                    'confidence_score': sentiment_result['confidence_score']
                })
        
        return mentions


class SentimentAggregationService:
    """Service for aggregating sentiment scores"""
    
    def aggregate_sentiment(self, asset: Symbol, timeframe: str = '1h') -> Dict:
        """Aggregate sentiment scores for a crypto asset"""
        now = timezone.now()
        
        if timeframe == '1h':
            start_time = now - timedelta(hours=1)
        elif timeframe == '4h':
            start_time = now - timedelta(hours=4)
        elif timeframe == '1d':
            start_time = now - timedelta(days=1)
        elif timeframe == '1w':
            start_time = now - timedelta(weeks=1)
        else:
            start_time = now - timedelta(hours=1)
        
        # Get social media mentions
        social_mentions = CryptoMention.objects.filter(
            asset=asset,
            mention_type='social',
            created_at__gte=start_time
        )
        
        # Get news mentions
        news_mentions = CryptoMention.objects.filter(
            asset=asset,
            mention_type='news',
            created_at__gte=start_time
        )
        
        # Calculate social sentiment
        if social_mentions.exists():
            social_sentiment = social_mentions.aggregate(
                avg_sentiment=Avg('sentiment_score'),
                bullish_count=Count('id', filter=Q(sentiment_label='bullish')),
                bearish_count=Count('id', filter=Q(sentiment_label='bearish')),
                neutral_count=Count('id', filter=Q(sentiment_label='neutral'))
            )
        else:
            social_sentiment = {
                'avg_sentiment': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0
            }
        
        # Calculate news sentiment
        if news_mentions.exists():
            news_sentiment = news_mentions.aggregate(
                avg_sentiment=Avg('sentiment_score'),
                bullish_count=Count('id', filter=Q(sentiment_label='bullish')),
                bearish_count=Count('id', filter=Q(sentiment_label='bearish')),
                neutral_count=Count('id', filter=Q(sentiment_label='neutral'))
            )
        else:
            news_sentiment = {
                'avg_sentiment': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0
            }
        
        # Calculate combined sentiment (weighted average)
        social_weight = 0.6
        news_weight = 0.4
        
        combined_sentiment = (
            social_sentiment['avg_sentiment'] * social_weight +
            news_sentiment['avg_sentiment'] * news_weight
        )
        
        # Calculate confidence based on mention volume
        total_mentions = (
            social_sentiment['bullish_count'] + social_sentiment['bearish_count'] + social_sentiment['neutral_count'] +
            news_sentiment['bullish_count'] + news_sentiment['bearish_count'] + news_sentiment['neutral_count']
        )
        
        confidence_score = min(1.0, total_mentions / 10.0)  # Normalize to 0-1
        
        return {
            'asset': asset,
            'timeframe': timeframe,
            'social_sentiment_score': social_sentiment['avg_sentiment'] or 0.0,
            'news_sentiment_score': news_sentiment['avg_sentiment'] or 0.0,
            'combined_sentiment_score': combined_sentiment,
            'bullish_mentions': (
                social_sentiment['bullish_count'] + news_sentiment['bullish_count']
            ),
            'bearish_mentions': (
                social_sentiment['bearish_count'] + news_sentiment['bearish_count']
            ),
            'neutral_mentions': (
                social_sentiment['neutral_count'] + news_sentiment['neutral_count']
            ),
            'total_mentions': total_mentions,
            'confidence_score': confidence_score
        }
    
    def save_aggregate(self, aggregate_data: Dict) -> SentimentAggregate:
        """Save sentiment aggregate to database"""
        return SentimentAggregate.objects.create(**aggregate_data)
    
    def get_latest_sentiment(self, asset: Symbol, timeframe: str = '1h') -> Optional[SentimentAggregate]:
        """Get the latest sentiment aggregate for an asset"""
        return SentimentAggregate.objects.filter(
            asset=asset,
            timeframe=timeframe
        ).order_by('-created_at').first()
