import logging
from datetime import datetime, timedelta
from typing import List, Dict
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from apps.sentiment.models import (
    SocialMediaSource, NewsSource, SocialMediaPost, NewsArticle,
    CryptoMention, SentimentAggregate, Influencer
)
from apps.sentiment.services import (
    TwitterService, RedditService, NewsAPIService,
    SentimentAnalysisService, SentimentAggregationService
)
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


@shared_task
def collect_social_media_data():
    """Collect social media data from various platforms"""
    logger.info("Starting social media data collection...")
    
    # Initialize services
    twitter_service = TwitterService()
    reddit_service = RedditService()
    sentiment_service = SentimentAnalysisService()
    
    # Get active crypto assets
    crypto_assets = Symbol.objects.filter(is_active=True)
    crypto_symbols = [asset.symbol for asset in crypto_assets]
    
    # Collect Twitter data
    collect_twitter_data.delay()
    
    # Collect Reddit data
    collect_reddit_data.delay()
    
    # Process collected data
    process_social_media_sentiment.delay()
    
    logger.info("Social media data collection completed")


@shared_task
def collect_twitter_data():
    """Collect Twitter/X data for crypto mentions"""
    logger.info("Collecting Twitter data...")
    
    twitter_service = TwitterService()
    sentiment_service = SentimentAnalysisService()
    
    # Crypto-related search queries
    crypto_queries = [
        "bitcoin OR BTC",
        "ethereum OR ETH",
        "cryptocurrency",
        "crypto trading",
        "altcoin",
        "defi",
        "nft"
    ]
    
    for query in crypto_queries:
        try:
            tweets = twitter_service.search_tweets(query, max_results=100)
            
            for tweet in tweets:
                # Check if tweet already exists
                if SocialMediaPost.objects.filter(post_id=tweet['id']).exists():
                    continue
                
                # Analyze sentiment
                sentiment_result = sentiment_service.analyze_text_sentiment(tweet['text'])
                
                # Create social media post
                post = SocialMediaPost.objects.create(
                    source=SocialMediaSource.objects.get_or_create(
                        name="Twitter API",
                        platform="twitter"
                    )[0],
                    platform="twitter",
                    post_id=tweet['id'],
                    author=tweet.get('author_id', 'unknown'),
                    content=tweet['text'],
                    sentiment_score=sentiment_result['sentiment_score'],
                    sentiment_label=sentiment_result['sentiment_label'],
                    confidence_score=sentiment_result['confidence_score'],
                    created_at=datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                )
                
                # Create crypto mentions
                crypto_symbols = ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'UNI', 'AAVE']
                mentions = sentiment_service.analyze_crypto_mentions(tweet['text'], crypto_symbols)
                
                for mention in mentions:
                    try:
                        asset = Symbol.objects.get(symbol=mention['symbol'])
                        CryptoMention.objects.create(
                            asset=asset,
                            social_post=post,
                            mention_type='social',
                            sentiment_score=mention['sentiment_score'],
                            sentiment_label=mention['sentiment_label'],
                            confidence_score=mention['confidence_score']
                        )
                    except Symbol.DoesNotExist:
                        continue
                        
        except Exception as e:
            logger.error(f"Error collecting Twitter data for query '{query}': {e}")
    
    logger.info("Twitter data collection completed")


@shared_task
def collect_reddit_data():
    """Collect Reddit data for crypto mentions"""
    logger.info("Collecting Reddit data...")
    
    reddit_service = RedditService()
    sentiment_service = SentimentAnalysisService()
    
    # Crypto-related subreddits
    crypto_subreddits = [
        "cryptocurrency",
        "bitcoin",
        "ethereum",
        "altcoin",
        "defi",
        "cryptomarkets"
    ]
    
    # Search queries
    search_queries = [
        "bitcoin",
        "ethereum",
        "crypto",
        "trading",
        "bullish",
        "bearish"
    ]
    
    for subreddit in crypto_subreddits:
        for query in search_queries:
            try:
                posts = reddit_service.search_posts(subreddit, query, limit=50)
                
                for post_data in posts:
                    # Check if post already exists
                    if SocialMediaPost.objects.filter(post_id=post_data['id']).exists():
                        continue
                    
                    # Analyze sentiment
                    content = f"{post_data['title']} {post_data['content']}"
                    sentiment_result = sentiment_service.analyze_text_sentiment(content)
                    
                    # Create social media post
                    post = SocialMediaPost.objects.create(
                        source=SocialMediaSource.objects.get_or_create(
                            name=f"Reddit r/{subreddit}",
                            platform="reddit"
                        )[0],
                        platform="reddit",
                        post_id=post_data['id'],
                        author=post_data['author'],
                        content=content,
                        sentiment_score=sentiment_result['sentiment_score'],
                        sentiment_label=sentiment_result['sentiment_label'],
                        confidence_score=sentiment_result['confidence_score'],
                        created_at=datetime.fromtimestamp(post_data['created_utc'])
                    )
                    
                    # Create crypto mentions
                    crypto_symbols = ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'UNI', 'AAVE']
                    mentions = sentiment_service.analyze_crypto_mentions(content, crypto_symbols)
                    
                    for mention in mentions:
                        try:
                            asset = Symbol.objects.get(symbol=mention['symbol'])
                            CryptoMention.objects.create(
                                asset=asset,
                                social_post=post,
                                mention_type='social',
                                sentiment_score=mention['sentiment_score'],
                                sentiment_label=mention['sentiment_label'],
                                confidence_score=mention['confidence_score']
                            )
                        except Symbol.DoesNotExist:
                            continue
                            
            except Exception as e:
                logger.error(f"Error collecting Reddit data for r/{subreddit}: {e}")
    
    logger.info("Reddit data collection completed")


@shared_task
def collect_news_data():
    """Collect news data for crypto mentions"""
    logger.info("Collecting news data...")
    
    news_service = NewsAPIService()
    sentiment_service = SentimentAnalysisService()
    
    try:
        # Get crypto news from the last 24 hours
        from_date = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        articles = news_service.get_crypto_news(from_date=from_date)
        
        logger.info(f"Fetched {len(articles)} articles from news API")
        
        new_articles_count = 0
        for article_data in articles:
            # Check if article already exists
            if NewsArticle.objects.filter(url=article_data.get('url', '')).exists():
                continue
            
            # Skip if required fields are missing
            if not article_data.get('url') or not article_data.get('title'):
                logger.warning(f"Skipping article with missing required fields: {article_data}")
                continue
            
            # Analyze sentiment
            content = f"{article_data['title']} {article_data.get('description', '')}"
            sentiment_result = sentiment_service.analyze_text_sentiment(content)
            
            # Parse published date - handle different formats
            published_at = timezone.now()  # Default to now
            try:
                published_at_str = article_data.get('publishedAt', '')
                if published_at_str:
                    # Handle ISO format with Z or +00:00
                    if published_at_str.endswith('Z'):
                        published_at_str = published_at_str.replace('Z', '+00:00')
                    # Try parsing with fromisoformat first
                    try:
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
                            # Try other common formats
                            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S']:
                                try:
                                    published_at = datetime.strptime(published_at_str, fmt)
                                    if published_at.tzinfo is None:
                                        published_at = timezone.make_aware(published_at)
                                    break
                                except ValueError:
                                    continue
            except Exception as e:
                logger.warning(f"Error parsing date for article {article_data.get('title', 'Unknown')}: {e}, using current time")
                published_at = timezone.now()
            
            # Convert sentiment label to uppercase format (POSITIVE/NEGATIVE/NEUTRAL)
            sentiment_label_raw = sentiment_result.get('sentiment_label', 'neutral').upper()
            sentiment_label_map = {
                'BULLISH': 'POSITIVE',
                'BEARISH': 'NEGATIVE',
                'NEUTRAL': 'NEUTRAL'
            }
            sentiment_label = sentiment_label_map.get(sentiment_label_raw, 'NEUTRAL')
            
            # Create news article
            article = NewsArticle.objects.create(
                source=NewsSource.objects.get_or_create(
                    name=article_data.get('source', {}).get('name', 'Unknown'),
                    defaults={'url': article_data.get('source', {}).get('url', '')}
                )[0],
                title=article_data['title'][:500],  # Truncate if too long
                content=article_data.get('description', '')[:5000] if article_data.get('description') else '',  # Limit content length
                url=article_data['url'],
                published_at=published_at,
                sentiment_score=sentiment_result.get('sentiment_score', 0.0),
                sentiment_label=sentiment_label,
                confidence_score=sentiment_result.get('confidence_score', 0.0),
                impact_score=0.0  # Will be calculated below
            )
            
            new_articles_count += 1
            
            # Create crypto mentions - use active crypto symbols from database
            active_crypto_assets = Symbol.objects.filter(
                is_active=True,
                is_crypto_symbol=True
            )
            crypto_symbols = [asset.symbol for asset in active_crypto_assets]
            
            # If no active symbols, fall back to common ones
            if not crypto_symbols:
                crypto_symbols = ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'UNI', 'AAVE', 'SOL', 'MATIC', 'AVAX']
            
            mentions = sentiment_service.analyze_crypto_mentions(content, crypto_symbols)
            
            # Also check for currencies from CryptoNewsAPI response
            if 'currencies' in article_data and article_data['currencies']:
                for currency in article_data['currencies']:
                    if currency not in crypto_symbols:
                        crypto_symbols.append(currency)
            
            for mention in mentions:
                try:
                    asset = Symbol.objects.get(symbol=mention['symbol'])
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
                        impact_weight=1.0
                    )
                except Symbol.DoesNotExist:
                    continue
            
            # Update impact score after mentions are created
            # Calculate impact score
            mention_count = article.cryptomention_set.count()
            impact_score = article.confidence_score or 0.0
            if mention_count > 0:
                impact_score += min(mention_count * 0.1, 0.3)
            hours_ago = (timezone.now() - article.published_at).total_seconds() / 3600
            if hours_ago < 24:
                impact_score += 0.2 * (1 - hours_ago / 24)
            impact_score = min(max(impact_score, 0.0), 1.0)
            article.impact_score = impact_score
            article.save(update_fields=['impact_score'])
                    
    except Exception as e:
        logger.error(f"Error collecting news data: {e}", exc_info=True)
    
    logger.info(f"News data collection completed. Added {new_articles_count} new articles.")


@shared_task
def process_social_media_sentiment():
    """Process sentiment for collected social media data"""
    logger.info("Processing social media sentiment...")
    
    sentiment_service = SentimentAnalysisService()
    
    # Get unprocessed social media posts
    unprocessed_posts = SocialMediaPost.objects.filter(
        sentiment_score__isnull=True
    )[:1000]  # Process in batches
    
    for post in unprocessed_posts:
        try:
            # Analyze sentiment
            sentiment_result = sentiment_service.analyze_text_sentiment(post.content)
            
            # Update post
            post.sentiment_score = sentiment_result['sentiment_score']
            post.sentiment_label = sentiment_result['sentiment_label']
            post.confidence_score = sentiment_result['confidence_score']
            post.save()
            
        except Exception as e:
            logger.error(f"Error processing sentiment for post {post.id}: {e}")
    
    logger.info("Social media sentiment processing completed")


@shared_task
def aggregate_sentiment_scores():
    """Aggregate sentiment scores for all crypto assets"""
    logger.info("Aggregating sentiment scores...")
    
    aggregation_service = SentimentAggregationService()
    crypto_assets = Symbol.objects.filter(is_active=True)
    
    timeframes = ['1h', '4h', '1d', '1w']
    
    for asset in crypto_assets:
        for timeframe in timeframes:
            try:
                # Calculate aggregate sentiment
                aggregate_data = aggregation_service.aggregate_sentiment(asset, timeframe)
                
                # Save aggregate
                aggregation_service.save_aggregate(aggregate_data)
                
            except Exception as e:
                logger.error(f"Error aggregating sentiment for {asset.symbol} {timeframe}: {e}")
    
    logger.info("Sentiment aggregation completed")


@shared_task
def cleanup_old_sentiment_data():
    """Clean up old sentiment data to prevent database bloat"""
    logger.info("Cleaning up old sentiment data...")
    
    # Keep data for 30 days
    cutoff_date = timezone.now() - timedelta(days=30)
    
    # Clean up old social media posts
    deleted_posts = SocialMediaPost.objects.filter(
        created_at__lt=cutoff_date
    ).delete()
    
    # Clean up old news articles
    deleted_articles = NewsArticle.objects.filter(
        published_at__lt=cutoff_date
    ).delete()
    
    # Clean up old crypto mentions
    deleted_mentions = CryptoMention.objects.filter(
        created_at__lt=cutoff_date
    ).delete()
    
    # Clean up old sentiment aggregates (keep only latest for each asset/timeframe)
    for asset in Symbol.objects.filter(is_active=True):
        for timeframe in ['1h', '4h', '1d', '1w']:
            aggregates = SentimentAggregate.objects.filter(
                asset=asset,
                timeframe=timeframe
            ).order_by('-created_at')[10:]  # Keep only 10 most recent
            
            if aggregates.exists():
                aggregates.delete()
    
    logger.info(f"Cleanup completed: {deleted_posts[0]} posts, {deleted_articles[0]} articles, {deleted_mentions[0]} mentions deleted")


@shared_task
def update_influencer_impact():
    """Update influencer impact scores based on recent activity"""
    logger.info("Updating influencer impact scores...")
    
    # Get influencers with recent activity
    recent_cutoff = timezone.now() - timedelta(days=7)
    
    for influencer in Influencer.objects.filter(is_active=True):
        try:
            # Calculate recent engagement
            recent_posts = SocialMediaPost.objects.filter(
                author=influencer.username,
                created_at__gte=recent_cutoff
            )
            
            if recent_posts.exists():
                avg_engagement = recent_posts.aggregate(
                    avg_engagement=models.Avg('engagement_score')
                )['avg_engagement'] or 0.0
                
                # Update impact score based on engagement and follower count
                impact_score = min(1.0, (avg_engagement * influencer.followers_count) / 1000000)
                
                influencer.impact_score = impact_score
                influencer.last_activity = recent_posts.latest('created_at').created_at
                influencer.save()
                
        except Exception as e:
            logger.error(f"Error updating influencer {influencer.username}: {e}")
    
    logger.info("Influencer impact update completed")


@shared_task
def sentiment_health_check():
    """Health check for sentiment analysis system"""
    logger.info("Running sentiment analysis health check...")
    
    # Check data freshness
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_posts = SocialMediaPost.objects.filter(created_at__gte=one_hour_ago).count()
    recent_articles = NewsArticle.objects.filter(published_at__gte=one_hour_ago).count()
    
    # Check sentiment processing
    unprocessed_posts = SocialMediaPost.objects.filter(sentiment_score__isnull=True).count()
    
    # Log health metrics
    logger.info(f"Health check - Recent posts: {recent_posts}, Recent articles: {recent_articles}, Unprocessed: {unprocessed_posts}")
    
    # Alert if no recent data
    if recent_posts == 0 and recent_articles == 0:
        logger.warning("No recent sentiment data collected - check data sources")
    
    # Alert if too many unprocessed posts
    if unprocessed_posts > 1000:
        logger.warning(f"High number of unprocessed posts: {unprocessed_posts}")
    
    logger.info("Sentiment analysis health check completed")
