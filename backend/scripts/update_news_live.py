#!/usr/bin/env python
"""
Live News Updater for Cryptocurrency News Analysis
Continuously fetches and updates cryptocurrency news articles in the database
"""

import os
import sys
import django
import time
import logging
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django environment
# Get the backend directory (parent of scripts directory)
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.sentiment.models import NewsArticle, NewsSource, CryptoMention
from apps.sentiment.services import NewsAPIService, SentimentAnalysisService
from apps.trading.models import Symbol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('news_updater.log')
    ]
)
logger = logging.getLogger(__name__)


def update_impact_score(article):
    """
    Calculate and update impact score for a news article
    Impact score is based on:
    - Sentiment confidence
    - Number of crypto mentions
    - Recency (more recent = higher impact)
    - Source credibility
    """
    try:
        # Base impact from confidence
        impact = article.confidence_score or 0.0
        
        # Boost for number of mentions
        mention_count = article.cryptomention_set.count()
        if mention_count > 0:
            impact += min(mention_count * 0.1, 0.3)  # Max 0.3 boost
        
        # Recency boost (articles from last 24 hours get boost)
        hours_ago = (timezone.now() - article.published_at).total_seconds() / 3600
        if hours_ago < 24:
            impact += 0.2 * (1 - hours_ago / 24)  # Decay over 24 hours
        
        # Source credibility (major sources get boost)
        major_sources = ['CoinDesk', 'CoinTelegraph', 'Bloomberg', 'Reuters', 'Forbes', 'The Block']
        if article.source.name in major_sources:
            impact += 0.1
        
        # Normalize to 0-1 range
        impact = min(max(impact, 0.0), 1.0)
        
        article.impact_score = impact
        article.save(update_fields=['impact_score'])
        
        return impact
    except Exception as e:
        logger.error(f"Error updating impact score for article {article.id}: {e}")
        return 0.0


def collect_and_process_news():
    """
    Collect news articles and process them for sentiment analysis
    """
    logger.info("=" * 60)
    logger.info("Starting news collection cycle...")
    logger.info("=" * 60)
    
    news_service = NewsAPIService()
    sentiment_service = SentimentAnalysisService()
    
    try:
        # Get crypto news from the last 24 hours
        from_date = (timezone.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
        logger.info(f"Fetching news from date: {from_date}")
        
        articles = news_service.get_crypto_news(from_date=from_date)
        logger.info(f"Fetched {len(articles)} articles from news API")
        
        if not articles:
            logger.warning("No articles retrieved from news API")
            return
        
        # Get active crypto symbols
        active_crypto_assets = Symbol.objects.filter(
            is_active=True,
            is_crypto_symbol=True
        )
        crypto_symbols = [asset.symbol for asset in active_crypto_assets]
        
        # Fallback to common crypto symbols if none are active
        if not crypto_symbols:
            crypto_symbols = ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'UNI', 'AAVE', 'SOL', 'MATIC', 'AVAX']
            logger.info(f"Using fallback crypto symbols: {crypto_symbols}")
        else:
            logger.info(f"Using {len(crypto_symbols)} active crypto symbols from database")
        
        new_articles_count = 0
        updated_articles_count = 0
        errors_count = 0
        
        for idx, article_data in enumerate(articles, 1):
            try:
                # Skip if article URL is missing
                if not article_data.get('url'):
                    logger.warning(f"Article {idx}: Missing URL, skipping")
                    continue
                
                # Check if article already exists
                existing_article = NewsArticle.objects.filter(url=article_data['url']).first()
                
                if existing_article:
                    logger.debug(f"Article {idx}: Already exists - {article_data.get('title', 'No title')[:50]}")
                    # Update impact score for existing article
                    update_impact_score(existing_article)
                    updated_articles_count += 1
                    continue
                
                # Parse published date
                try:
                    published_at_str = article_data.get('publishedAt', '')
                    if published_at_str:
                        # Handle ISO format with Z or +00:00
                        try:
                            if published_at_str.endswith('Z'):
                                published_at_str = published_at_str.replace('Z', '+00:00')
                            # Try parsing with fromisoformat first
                            published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                            # Convert to timezone-aware if needed
                            if published_at.tzinfo is None:
                                published_at = timezone.make_aware(published_at)
                        except (ValueError, AttributeError):
                            # Fallback: try parsing with strptime for common formats
                            try:
                                published_at = datetime.strptime(published_at_str, '%Y-%m-%dT%H:%M:%S%z')
                                if published_at.tzinfo is None:
                                    published_at = timezone.make_aware(published_at)
                            except ValueError:
                                logger.warning(f"Article {idx}: Could not parse date format: {published_at_str}")
                                published_at = timezone.now()
                    else:
                        published_at = timezone.now()
                        logger.warning(f"Article {idx}: No published date, using current time")
                except Exception as e:
                    logger.warning(f"Article {idx}: Error parsing date: {e}, using current time")
                    published_at = timezone.now()
                
                # Skip articles older than 7 days
                if (timezone.now() - published_at).days > 7:
                    logger.debug(f"Article {idx}: Too old ({published_at}), skipping")
                    continue
                
                # Prepare content for sentiment analysis
                title = article_data.get('title', '')
                description = article_data.get('description', '') or article_data.get('content', '')
                content = f"{title} {description}".strip()
                
                if not content:
                    logger.warning(f"Article {idx}: No content, skipping")
                    continue
                
                # Analyze sentiment
                logger.debug(f"Article {idx}: Analyzing sentiment...")
                sentiment_result = sentiment_service.analyze_text_sentiment(content)
                
                # Convert sentiment label to uppercase format (POSITIVE/NEGATIVE/NEUTRAL)
                sentiment_label_raw = sentiment_result.get('sentiment_label', 'neutral').upper()
                # Map bullish/bearish to POSITIVE/NEGATIVE
                sentiment_label_map = {
                    'BULLISH': 'POSITIVE',
                    'BEARISH': 'NEGATIVE',
                    'NEUTRAL': 'NEUTRAL'
                }
                sentiment_label = sentiment_label_map.get(sentiment_label_raw, 'NEUTRAL')
                
                # Get or create news source
                source_name = article_data.get('source', {}).get('name', 'Unknown')
                source_url = article_data.get('source', {}).get('url', '')
                source, created = NewsSource.objects.get_or_create(
                    name=source_name,
                    defaults={'url': source_url}
                )
                if created:
                    logger.info(f"Created new news source: {source_name}")
                
                # Create news article
                article = NewsArticle.objects.create(
                    source=source,
                    title=title[:500],  # Truncate if too long
                    content=description[:5000] if description else '',  # Limit content length
                    url=article_data['url'],
                    published_at=published_at,
                    sentiment_score=sentiment_result.get('sentiment_score', 0.0),
                    sentiment_label=sentiment_label,
                    confidence_score=sentiment_result.get('confidence_score', 0.0),
                    impact_score=0.0  # Will be calculated below
                )
                
                logger.info(f"Article {idx}: Created - {title[:60]}")
                
                # Analyze crypto mentions
                mentions = sentiment_service.analyze_crypto_mentions(content, crypto_symbols)
                
                # Create crypto mentions
                mention_count = 0
                for mention in mentions:
                    try:
                        asset = Symbol.objects.get(symbol=mention['symbol'])
                        # Calculate impact weight based on source credibility and sentiment confidence
                        impact_weight = mention.get('impact_weight', 1.0)
                        # Boost impact for major sources
                        if source.name in ['CoinDesk', 'CoinTelegraph', 'Bloomberg', 'Reuters']:
                            impact_weight = 1.5
                        
                        # Convert sentiment label for crypto mentions
                        mention_sentiment_raw = mention.get('sentiment_label', 'neutral').upper()
                        mention_sentiment_map = {
                            'BULLISH': 'POSITIVE',
                            'BEARISH': 'NEGATIVE',
                            'NEUTRAL': 'NEUTRAL'
                        }
                        mention_sentiment_label = mention_sentiment_map.get(mention_sentiment_raw, 'NEUTRAL')
                        
                        CryptoMention.objects.create(
                            asset=asset,
                            news_article=article,
                            mention_type='news',
                            sentiment_score=mention.get('sentiment_score', 0.0),
                            sentiment_label=mention_sentiment_label,
                            confidence_score=mention.get('confidence_score', 0.0),
                            impact_weight=impact_weight
                        )
                        mention_count += 1
                    except Symbol.DoesNotExist:
                        logger.debug(f"Symbol {mention['symbol']} not found in database, skipping mention")
                        continue
                    except Exception as e:
                        logger.warning(f"Error creating mention for {mention.get('symbol')}: {e}")
                        continue
                
                # Update impact score after mentions are created
                impact_score = update_impact_score(article)
                
                logger.info(
                    f"Article {idx}: Processed - Sentiment: {article.sentiment_label} "
                    f"({article.sentiment_score:.2f}), Mentions: {mention_count}, Impact: {impact_score:.2f}"
                )
                
                new_articles_count += 1
                
            except Exception as e:
                errors_count += 1
                logger.error(f"Error processing article {idx}: {e}", exc_info=True)
                continue
        
        logger.info("=" * 60)
        logger.info(f"News collection cycle completed:")
        logger.info(f"  - New articles: {new_articles_count}")
        logger.info(f"  - Updated articles: {updated_articles_count}")
        logger.info(f"  - Errors: {errors_count}")
        logger.info(f"  - Total processed: {len(articles)}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error in news collection: {e}", exc_info=True)


def main():
    """
    Main function to run news updater continuously
    """
    logger.info("=" * 60)
    logger.info("CRYPTOCURRENCY NEWS LIVE UPDATER")
    logger.info("=" * 60)
    logger.info("This script will continuously update cryptocurrency news")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)
    logger.info("")
    
    # Configuration
    UPDATE_INTERVAL = 15 * 60  # 15 minutes in seconds
    INITIAL_DELAY = 30  # Wait 30 seconds before first update
    
    try:
        # Wait a bit before first update to let other services start
        logger.info(f"Waiting {INITIAL_DELAY} seconds before first update...")
        time.sleep(INITIAL_DELAY)
        
        cycle_count = 0
        while True:
            cycle_count += 1
            logger.info(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting update cycle #{cycle_count}")
            
            try:
                collect_and_process_news()
            except KeyboardInterrupt:
                logger.info("\nReceived interrupt signal, shutting down gracefully...")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            
            # Wait before next update
            logger.info(f"Waiting {UPDATE_INTERVAL // 60} minutes until next update...")
            logger.info(f"Next update at: {(datetime.now() + timedelta(seconds=UPDATE_INTERVAL)).strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                time.sleep(UPDATE_INTERVAL)
            except KeyboardInterrupt:
                logger.info("\nReceived interrupt signal, shutting down gracefully...")
                break
                
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("News updater stopped by user")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

