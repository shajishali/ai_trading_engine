from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.db.models import Q, Avg, Count
from django.utils import timezone
from datetime import timedelta
import json
import logging

from apps.sentiment.models import (
    SocialMediaPost, NewsArticle, CryptoMention, SentimentAggregate,
    Influencer
)
from apps.sentiment.services import SentimentAggregationService
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


def sentiment_dashboard(request):
    """Sentiment analysis dashboard view"""
    # Get recent sentiment data
    recent_aggregates = SentimentAggregate.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).select_related('asset').order_by('-created_at')[:50]
    
    # Get sentiment statistics
    sentiment_stats = {
        'total_mentions_24h': CryptoMention.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count(),
        'bullish_mentions_24h': CryptoMention.objects.filter(
            sentiment_label='bullish',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count(),
        'bearish_mentions_24h': CryptoMention.objects.filter(
            sentiment_label='bearish',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count(),
        'neutral_mentions_24h': CryptoMention.objects.filter(
            sentiment_label='neutral',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count(),
    }
    
    # Get top influencers
    top_influencers = Influencer.objects.filter(
        is_active=True
    ).order_by('-impact_score')[:10]
    
    context = {
        'recent_aggregates': recent_aggregates,
        'sentiment_stats': sentiment_stats,
        'top_influencers': top_influencers,
    }
    
    return render(request, 'sentiment/dashboard.html', context)


@csrf_exempt
@require_http_methods(["GET"])
def get_sentiment_data(request, asset_symbol):
    """Get sentiment data for a specific crypto asset"""
    try:
        asset = Symbol.objects.get(symbol=asset_symbol.upper())
    except Symbol.DoesNotExist:
        return JsonResponse({'error': 'Asset not found'}, status=404)
    
    # Get timeframe from query params
    timeframe = request.GET.get('timeframe', '1h')
    
    # Get latest sentiment aggregate
    aggregate = SentimentAggregate.objects.filter(
        asset=asset,
        timeframe=timeframe
    ).order_by('-created_at').first()
    
    if not aggregate:
        return JsonResponse({'error': 'No sentiment data available'}, status=404)
    
    # Get recent mentions
    recent_mentions = CryptoMention.objects.filter(
        asset=asset,
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).select_related('social_post', 'news_article').order_by('-created_at')[:20]
    
    # Format mentions for response
    mentions_data = []
    for mention in recent_mentions:
        mention_data = {
            'id': mention.id,
            'type': mention.mention_type,
            'sentiment_label': mention.sentiment_label,
            'sentiment_score': mention.sentiment_score,
            'confidence_score': mention.confidence_score,
            'created_at': mention.created_at.isoformat(),
        }
        
        if mention.social_post:
            mention_data['content'] = mention.social_post.content[:200] + '...'
            mention_data['author'] = mention.social_post.author
            mention_data['platform'] = mention.social_post.platform
        elif mention.news_article:
            mention_data['content'] = mention.news_article.title
            mention_data['source'] = mention.news_article.source.name
            mention_data['url'] = mention.news_article.url
        
        mentions_data.append(mention_data)
    
    response_data = {
        'asset': {
            'symbol': asset.symbol,
            'name': asset.name,
        },
        'timeframe': timeframe,
        'sentiment': {
            'combined_score': aggregate.combined_sentiment_score,
            'social_score': aggregate.social_sentiment_score,
            'news_score': aggregate.news_sentiment_score,
            'confidence_score': aggregate.confidence_score,
            'bullish_mentions': aggregate.bullish_mentions,
            'bearish_mentions': aggregate.bearish_mentions,
            'neutral_mentions': aggregate.neutral_mentions,
            'total_mentions': aggregate.total_mentions,
        },
        'recent_mentions': mentions_data,
        'last_updated': aggregate.created_at.isoformat(),
    }
    
    return JsonResponse(response_data)


@csrf_exempt
@require_http_methods(["GET"])
def get_sentiment_summary(request):
    """Get sentiment summary for all assets"""
    # Get latest sentiment aggregates for all assets
    assets = Symbol.objects.filter(is_active=True)
    
    summary_data = []
    for asset in assets:
        aggregate = SentimentAggregate.objects.filter(
            asset=asset,
            timeframe='1h'
        ).order_by('-created_at').first()
        
        if aggregate:
            summary_data.append({
                'symbol': asset.symbol,
                'name': asset.name,
                'sentiment_score': aggregate.combined_sentiment_score,
                'sentiment_label': 'bullish' if aggregate.combined_sentiment_score > 0.1 else 'bearish' if aggregate.combined_sentiment_score < -0.1 else 'neutral',
                'confidence_score': aggregate.confidence_score,
                'total_mentions': aggregate.total_mentions,
                'last_updated': aggregate.created_at.isoformat(),
            })
    
    # Sort by sentiment score
    summary_data.sort(key=lambda x: abs(x['sentiment_score']), reverse=True)
    
    return JsonResponse({'assets': summary_data})


@csrf_exempt
@require_http_methods(["POST"])
def trigger_sentiment_collection(request):
    """Trigger manual sentiment data collection"""
    try:
        from apps.sentiment.tasks import collect_social_media_data, collect_news_data
        
        # Start background tasks
        collect_social_media_data.delay()
        collect_news_data.delay()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Sentiment data collection started'
        })
    except Exception as e:
        logger.error(f"Error triggering sentiment collection: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def trigger_sentiment_aggregation(request):
    """Trigger manual sentiment aggregation"""
    try:
        from apps.sentiment.tasks import aggregate_sentiment_scores
        
        # Start background task
        aggregate_sentiment_scores.delay()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Sentiment aggregation started'
        })
    except Exception as e:
        logger.error(f"Error triggering sentiment aggregation: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_influencer_data(request):
    """Get influencer data and impact scores"""
    influencers = Influencer.objects.filter(
        is_active=True
    ).order_by('-impact_score')
    
    influencer_data = []
    for influencer in influencers:
        # Get recent posts by this influencer
        recent_posts = SocialMediaPost.objects.filter(
            author=influencer.username,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        influencer_data.append({
            'username': influencer.username,
            'display_name': influencer.display_name,
            'platform': influencer.platform,
            'followers_count': influencer.followers_count,
            'impact_score': influencer.impact_score,
            'engagement_rate': influencer.engagement_rate,
            'is_verified': influencer.is_verified,
            'recent_posts': recent_posts,
            'last_activity': influencer.last_activity.isoformat() if influencer.last_activity else None,
        })
    
    return JsonResponse({'influencers': influencer_data})


@csrf_exempt
@require_http_methods(["GET"])
def get_sentiment_trends(request, asset_symbol):
    """Get sentiment trends for a specific asset"""
    try:
        asset = Symbol.objects.get(symbol=asset_symbol.upper())
    except Symbol.DoesNotExist:
        return JsonResponse({'error': 'Asset not found'}, status=404)
    
    # Get sentiment data for different timeframes
    timeframes = ['1h', '4h', '1d', '1w']
    trends_data = {}
    
    for timeframe in timeframes:
        aggregates = SentimentAggregate.objects.filter(
            asset=asset,
            timeframe=timeframe
        ).order_by('-created_at')[:24]  # Last 24 data points
        
        if aggregates.exists():
            trends_data[timeframe] = [
                {
                    'timestamp': agg.created_at.isoformat(),
                    'sentiment_score': agg.combined_sentiment_score,
                    'confidence_score': agg.confidence_score,
                    'total_mentions': agg.total_mentions,
                }
                for agg in aggregates
            ]
        else:
            trends_data[timeframe] = []
    
    return JsonResponse({
        'asset': {
            'symbol': asset.symbol,
            'name': asset.name,
        },
        'trends': trends_data
    })


@csrf_exempt
@require_http_methods(["GET"])
def get_sentiment_health(request):
    """Get sentiment analysis system health status"""
    # Check data freshness
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_posts = SocialMediaPost.objects.filter(created_at__gte=one_hour_ago).count()
    recent_articles = NewsArticle.objects.filter(published_at__gte=one_hour_ago).count()
    
    # Check processing status
    unprocessed_posts = SocialMediaPost.objects.filter(sentiment_score__isnull=True).count()
    
    # Calculate system health score
    health_score = 100
    issues = []
    
    if recent_posts == 0 and recent_articles == 0:
        health_score -= 50
        issues.append('No recent data collected')
    
    if unprocessed_posts > 1000:
        health_score -= 30
        issues.append(f'High number of unprocessed posts: {unprocessed_posts}')
    
    if unprocessed_posts > 5000:
        health_score -= 20
        issues.append('Critical backlog in sentiment processing')
    
    health_status = 'healthy' if health_score >= 80 else 'warning' if health_score >= 50 else 'critical'
    
    return JsonResponse({
        'health_score': health_score,
        'health_status': health_status,
        'issues': issues,
        'metrics': {
            'recent_posts_1h': recent_posts,
            'recent_articles_1h': recent_articles,
            'unprocessed_posts': unprocessed_posts,
            'total_mentions_24h': CryptoMention.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count(),
        }
    })
