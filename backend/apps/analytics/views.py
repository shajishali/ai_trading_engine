from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import AnalyticsPortfolio, AnalyticsPosition, AnalyticsTrade, PerformanceMetrics, BacktestResult, MarketData, Alert
from .services import PortfolioAnalytics, TechnicalIndicators, BacktestEngine, RiskManager, MarketAnalyzer, MarketSentimentService

@login_required
def backtesting_view(request):
    """Backtesting interface for strategy validation"""
    user = request.user
    
    # Get user's backtest results
    backtest_results = BacktestResult.objects.filter(user=user).order_by('-created_at')
    
    if request.method == 'POST':
        # Handle backtest form submission
        strategy_name = request.POST.get('strategy_name')
        symbol = request.POST.get('symbol', 'BTC')  # Default symbol
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        initial_capital = float(request.POST.get('initial_capital', 10000))
        
        # Convert dates to datetime objects
        from datetime import datetime
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Create a mock strategy object for demonstration
        class MockStrategy:
            def __init__(self, name):
                self.name = name
                self.symbol = symbol
        
        strategy = MockStrategy(strategy_name)
        
        # Use the new BacktestingService
        backtest_service = BacktestingService(initial_capital=initial_capital)
        results = backtest_service.backtest_strategy(
            strategy=strategy,
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt
        )
        
        if results:
            metrics = results['performance_metrics']
            
            # Save backtest results
            BacktestResult.objects.create(
                user=user,
                strategy_name=strategy_name,
                start_date=start_dt,
                end_date=end_dt,
                initial_capital=initial_capital,
                total_return=metrics.get('total_return', 0),
                sharpe_ratio=metrics.get('sharpe_ratio', 0),
                max_drawdown=metrics.get('max_drawdown', 0),
                win_rate=metrics.get('win_rate', 0),
            )
            
            messages.success(request, 'Backtest completed successfully!')
            return redirect('analytics:backtesting')
    
    latest_result = backtest_results.first() if backtest_results.exists() else None
    
    context = {
        'backtest_results': backtest_results,
        'latest_result': latest_result,
    }
    
    return render(request, 'analytics/backtesting.html', context)

@login_required
def market_data_api(request):
    """API endpoint for market data"""
    symbol = request.GET.get('symbol', 'BTC')
    
    market_data = MarketData.objects.filter(symbol=symbol).order_by('-date')[:50]
    
    chart_data = {
        'labels': [data.date.strftime('%Y-%m-%d') for data in market_data],
        'prices': [float(data.close_price) for data in market_data],
        'volumes': [float(data.volume) for data in market_data],
    }
    
    return JsonResponse(chart_data)

@login_required
def market_sentiment_view(request):
    """Market sentiment analysis dashboard"""
    try:
        user = request.user
        
        # Initialize sentiment service
        sentiment_service = MarketSentimentService()
        
        # Get current sentiment data
        current_sentiment = sentiment_service.calculate_market_sentiment()
        fear_greed_data = sentiment_service.get_fear_greed_index()
        vix_data = sentiment_service.get_vix_data()
        put_call_data = sentiment_service.get_put_call_ratio()
        
        # Get sentiment signal
        sentiment_signal = sentiment_service.get_sentiment_signal()
        
        # Get historical sentiment data (last 30 days)
        from .models import MarketSentimentIndicator, FearGreedIndex, VIXData, PutCallRatio
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        historical_sentiment = MarketSentimentIndicator.objects.filter(
            timestamp__range=(start_date, end_date)
        ).order_by('timestamp')
        
        context = {
            'current_sentiment': current_sentiment,
            'fear_greed_data': fear_greed_data,
            'vix_data': vix_data,
            'put_call_data': put_call_data,
            'sentiment_signal': sentiment_signal,
            'historical_sentiment': historical_sentiment,
        }
        
        return render(request, 'analytics/market_sentiment_analysis.html', context)
        
    except Exception as e:
        print(f"Error in market_sentiment_view: {e}")
        messages.error(request, f'Error loading market sentiment analysis: {str(e)}')
        return redirect('analytics:backtesting')

@login_required
def news_analysis(request):
    """News analysis page for crypto news and sentiment - Showcases current cryptocurrency news"""
    try:
        from apps.sentiment.models import NewsArticle, CryptoMention, NewsSource
        from apps.trading.models import Symbol
        
        # Get filter parameters
        symbol_filter = request.GET.get('symbol', '')
        sentiment_filter = request.GET.get('sentiment', '')
        date_filter = request.GET.get('date_range', '30d')  # Default to 30 days to show more news
        source_filter = request.GET.get('source', '')
        
        # Calculate date range - Focus on recent news (default to last 30 days to show more news)
        now = timezone.now()
        if date_filter == '24h':
            start_date = now - timedelta(hours=24)
        elif date_filter == '7d':
            start_date = now - timedelta(days=7)
        elif date_filter == '30d':
            start_date = now - timedelta(days=30)
        else:
            # Default to last 30 days to show more news
            start_date = now - timedelta(days=30)
        
        # Get current crypto news articles (ordered by time for calendar view)
        # Sort by published_at ascending (oldest first) to match calendar style
        # Within same time, show higher impact first
        news_articles = NewsArticle.objects.filter(
            published_at__gte=start_date
        ).select_related('source').prefetch_related(
            'cryptomention_set__asset'
        ).order_by('published_at', '-impact_score')  # Chronological order (oldest to newest)
        
        # Apply filters
        if symbol_filter:
            news_articles = news_articles.filter(
                cryptomention__asset__symbol=symbol_filter
            ).distinct()
        
        if sentiment_filter:
            news_articles = news_articles.filter(sentiment_label=sentiment_filter.upper())
        
        if source_filter:
            news_articles = news_articles.filter(source__name__icontains=source_filter)
        
        # Get crypto mentions for articles (for statistics and analysis)
        crypto_mentions = CryptoMention.objects.filter(
            news_article__in=news_articles,
            mention_type='news'
        ).select_related('asset', 'news_article')
        
        # Get comprehensive statistics
        total_articles = news_articles.count()
        positive_articles = news_articles.filter(sentiment_label='POSITIVE').count()
        negative_articles = news_articles.filter(sentiment_label='NEGATIVE').count()
        neutral_articles = news_articles.filter(sentiment_label='NEUTRAL').count()
        
        # Calculate sentiment percentage
        sentiment_percentage = {
            'positive': (positive_articles / total_articles * 100) if total_articles > 0 else 0,
            'negative': (negative_articles / total_articles * 100) if total_articles > 0 else 0,
            'neutral': (neutral_articles / total_articles * 100) if total_articles > 0 else 0,
        }
        
        # Get overall average sentiment
        avg_sentiment = news_articles.aggregate(
            avg_sentiment=Avg('sentiment_score')
        )['avg_sentiment'] or 0.0
        
        # Calculate sentiment bar width (normalize -1 to 1 range to 0 to 100%)
        # Convert -1 to 1 range to 0 to 100% for progress bar
        sentiment_bar_width = ((avg_sentiment + 1) / 2) * 100
        if sentiment_bar_width < 0:
            sentiment_bar_width = 0
        elif sentiment_bar_width > 100:
            sentiment_bar_width = 100
        
        # Get top mentioned coins with detailed stats
        top_coins = crypto_mentions.values('asset__symbol', 'asset__name').annotate(
            count=Count('id'),
            avg_sentiment=Avg('sentiment_score'),
            positive_count=Count('id', filter=Q(sentiment_label='POSITIVE')),
            negative_count=Count('id', filter=Q(sentiment_label='NEGATIVE')),
            max_impact=Sum('impact_weight')
        ).order_by('-count')[:15]
        
        # Get trending news (high impact, recent)
        trending_news = news_articles.filter(
            impact_score__gt=0.5
        ).order_by('-impact_score', '-published_at')[:10]
        
        # Get high impact news (top impact scores)
        high_impact_news = news_articles.order_by('-impact_score', '-published_at')[:5]
        
        # Get news by sentiment for analysis
        positive_news = news_articles.filter(sentiment_label='POSITIVE').order_by('-impact_score', '-published_at')[:10]
        negative_news = news_articles.filter(sentiment_label='NEGATIVE').order_by('-impact_score', '-published_at')[:10]
        
        # Get news sources with statistics
        news_sources = NewsSource.objects.filter(
            newsarticle__in=news_articles
        ).annotate(
            article_count=Count('newsarticle'),
            avg_sentiment=Avg('newsarticle__sentiment_score'),
            avg_impact=Avg('newsarticle__impact_score')
        ).distinct().order_by('-article_count')[:15]
        
        # Get active crypto symbols for filter (most mentioned first)
        active_symbols = Symbol.objects.filter(
            is_active=True,
            is_crypto_symbol=True,
            cryptomention__news_article__in=news_articles
        ).annotate(
            mention_count=Count('cryptomention')
        ).distinct().order_by('-mention_count', 'symbol')[:50]
        
        # Get recent news timeline (last 24 hours by default)
        recent_news_timeline = news_articles.filter(
            published_at__gte=now - timedelta(hours=24)
        ).order_by('-published_at')[:20]
        
        # Calculate news trends (hourly distribution for last 24h)
        hourly_news = {}
        for hour in range(24):
            hour_start = now - timedelta(hours=hour+1)
            hour_end = now - timedelta(hours=hour)
            count = news_articles.filter(
                published_at__gte=hour_start,
                published_at__lt=hour_end
            ).count()
            hourly_news[hour] = count
        
        context = {
            # Main news data - Show more articles for calendar view
            'news_articles': news_articles[:200],  # Show up to 200 articles for calendar
            'trending_news': trending_news,
            'high_impact_news': high_impact_news,
            'positive_news': positive_news,
            'negative_news': negative_news,
            'recent_news_timeline': recent_news_timeline,
            
            # Statistics
            'total_articles': total_articles,
            'positive_articles': positive_articles,
            'negative_articles': negative_articles,
            'neutral_articles': neutral_articles,
            'sentiment_percentage': sentiment_percentage,
            'avg_sentiment': avg_sentiment,
            
            # Analysis data
            'top_coins': top_coins,
            'news_sources': news_sources,
            'hourly_news': hourly_news,
            'crypto_mentions': crypto_mentions,
            
            # Filters
            'active_symbols': active_symbols,
            'symbol_filter': symbol_filter,
            'sentiment_filter': sentiment_filter,
            'date_filter': date_filter,
            'source_filter': source_filter,
            
            # Metadata
            'date_range_start': start_date,
            'date_range_end': now,
            'sentiment_bar_width': sentiment_bar_width,
        }
        
        return render(request, 'analytics/news_analysis.html', context)
        
    except Exception as e:
        print(f"Error in news_analysis: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Error loading news analysis: {str(e)}')
        return redirect('analytics:backtesting')

@login_required
def update_sentiment_data(request):
    """Update sentiment data via AJAX"""
    try:
        if request.method == 'POST':
            # Trigger sentiment update task
            from apps.sentiment.tasks import collect_news_data
            collect_news_data.delay()
            return JsonResponse({'status': 'success', 'message': 'News data collection started'})
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def fetch_news_now(request):
    """Manually trigger news collection and return results"""
    try:
        from apps.sentiment.tasks import collect_news_data
        from apps.sentiment.models import NewsArticle
        from django.utils import timezone
        from datetime import timedelta
        
        # Count articles before
        articles_before = NewsArticle.objects.filter(
            published_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Run news collection synchronously for immediate feedback
        try:
            collect_news_data()
            # Count articles after
            articles_after = NewsArticle.objects.filter(
                published_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            new_articles = articles_after - articles_before
            
            return JsonResponse({
                'status': 'success', 
                'message': f'Successfully fetched news! Added {new_articles} new articles.',
                'new_articles': new_articles,
                'total_articles': articles_after
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error', 
                'message': f'Error fetching news: {str(e)}'
            })
            
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
