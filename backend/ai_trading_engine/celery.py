import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')

app = Celery('ai_trading_engine')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Phase 5: Enhanced Celery Configuration
app.conf.update(
    # Task prioritization and routing
    task_routes={
        'apps.trading.tasks.*': {'queue': 'trading', 'priority': 10},
        'apps.signals.tasks.*': {'queue': 'signals', 'priority': 8},
        'apps.sentiment.tasks.*': {'queue': 'sentiment', 'priority': 6},
        'apps.data.tasks.*': {'queue': 'data', 'priority': 4},
        'apps.analytics.tasks.*': {'queue': 'analytics', 'priority': 5},
    },
    
    # Queue definitions
    task_default_queue='default',
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('data', routing_key='data'),
        Queue('signals', routing_key='signals'),
        Queue('sentiment', routing_key='sentiment'),
        Queue('trading', routing_key='trading'),
        Queue('analytics', routing_key='analytics'),
    ),
    
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Broker connection settings
    broker_connection_retry_on_startup=True,  # Fix deprecation warning for Celery 6.0+
    
    # Performance optimization
    worker_prefetch_multiplier=1,  # Reduced to prevent memory issues
    task_acks_late=True,
    worker_disable_rate_limits=False,
    
    # Worker pool settings for better performance
    worker_pool='solo',  # Use solo pool for Windows compatibility
    worker_concurrency=1,  # Single thread per worker (divided workers handle concurrency)
    
    # Task retry and failure handling
    task_annotations={
        '*': {
            'retry_backoff': True,
            'retry_backoff_max': 600,
            'max_retries': 3,
        }
    },
    
    # Beat schedule for periodic tasks
    # Tasks are automatically routed to correct queues via task_routes
    beat_schedule={
        # TEMPORARILY DISABLED: Only keeping update coin task active
        # 'update-crypto-prices': {
        #     'task': 'apps.data.tasks.update_crypto_prices',
        #     'schedule': crontab(minute='*/30'),  # Every 30 minutes
        #     'options': {'queue': 'data', 'priority': 10},  # Explicitly route to data queue
        # },
        # ENABLED: Signal generation task (runs every hour)
        'generate-trading-signals': {
            'task': 'apps.signals.tasks.generate_signals_for_all_symbols',
            'schedule': crontab(minute=0),  # Every hour at minute 0
            'options': {'queue': 'signals', 'priority': 8},  # Explicitly route to signals queue
        },
        # DISABLED: Sentiment analysis tasks (disabled per user request)
        # 'update-sentiment-analysis': {
        #     'task': 'apps.sentiment.tasks.aggregate_sentiment_scores',
        #     'schedule': crontab(minute='*/10'),  # Every 10 minutes
        #     'options': {'queue': 'sentiment', 'priority': 6},  # Explicitly route to sentiment queue
        # },
        # DISABLED: News data collection (disabled per user request)
          'collect-news-data': {
              'task': 'apps.sentiment.tasks.collect_news_data',
              'schedule': crontab(minute='*/15'),  # Every 15 minutes
              'options': {'queue': 'sentiment', 'priority': 7},  # Explicitly route to sentiment queue
          },
        # DISABLED: Social media data collection (disabled per user request)
        # 'collect-social-media-data': {
        #     'task': 'apps.sentiment.tasks.collect_social_media_data',
        #     'schedule': crontab(minute='*/20'),  # Every 20 minutes
        #     'options': {'queue': 'sentiment', 'priority': 6},  # Explicitly route to sentiment queue
        # },
        # TEMPORARILY DISABLED: Only keeping update coin task active
        # 'cleanup-old-data': {
        #     'task': 'apps.data.tasks.cleanup_old_data_task',
        #     'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        #     'options': {'queue': 'data', 'priority': 2},  # Explicitly route to data queue
        # },
        # TEMPORARILY DISABLED: Only keeping update coin task active
        # Historical data update tasks for backtesting database
        # 'historical-incremental-hourly': {
        #     'task': 'apps.data.tasks.update_historical_data_task',
        #     'schedule': crontab(minute=0),  # Every hour at minute 0
        #     'options': {'queue': 'data', 'priority': 5},  # Explicitly route to data queue
        # },
        # TEMPORARILY DISABLED: Only keeping update coin task active
        # Enhanced hourly data collection for top 100 coins with multi-source fallback
        # 'enhanced-hourly-data-collection': {
        #     'task': 'apps.data.enhanced_tasks.enhanced_hourly_data_collection_task',
        #     'schedule': crontab(minute=5),  # Every hour at minute 5 (after previous hour completes)
        #     'options': {'queue': 'data', 'priority': 9},  # High priority for data collection
        #     'kwargs': {'max_coins': 100},  # Limit to 100 coins for testing
        # },
        # TEMPORARILY DISABLED: Only keeping update coin task active
        # Enhanced gap filling (daily) - limited to 100 coins
        # 'enhanced-gap-filling': {
        #     'task': 'apps.data.enhanced_tasks.enhanced_gap_filling_task',
        #     'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM UTC
        #     'options': {'queue': 'data', 'priority': 6},
        #     'kwargs': {'max_coins': 100},  # Limit to 100 coins for testing
        # },
        # TEMPORARILY DISABLED: Only keeping update coin task active
        # Enhanced data quality check (every 6 hours) - limited to 100 coins
        # 'enhanced-data-quality-check': {
        #     'task': 'apps.data.enhanced_tasks.enhanced_data_quality_check_task',
        #     'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        #     'options': {'queue': 'data', 'priority': 4},
        #     'kwargs': {'max_coins': 100},  # Limit to 100 coins for testing
        # },
        # TEMPORARILY DISABLED: Only keeping update coin task active
        # 'historical-incremental-daily-backup': {
        #     'task': 'apps.data.tasks.update_historical_data_daily_task',
        #     'schedule': crontab(hour=2, minute=30),  # Daily at 2:30 AM UTC (backup)
        #     'options': {'queue': 'data', 'priority': 4},  # Explicitly route to data queue
        # },
        # TEMPORARILY DISABLED: Only keeping update coin task active
        # 'historical-weekly-gap-check': {
        #     'task': 'apps.data.tasks.weekly_gap_check_and_fill_task',
        #     'schedule': crontab(hour=3, minute=0, day_of_week='sun'),  # Weekly on Sunday at 3 AM UTC
        #     'options': {'queue': 'data', 'priority': 3},  # Explicitly route to data queue
        # },
        # ACTIVE: Sync Binance futures-eligible coins (source of truth)
        'sync-binance-futures-symbols': {
            'task': 'apps.data.tasks.sync_binance_futures_symbols_task',
            'schedule': crontab(minute=0),  # Every hour at minute 0
            'options': {'queue': 'data', 'priority': 9},  # High priority: keeps eligible symbols accurate
        },
        # ACTIVE: Load market data for Binance futures coins (batch per run; over time all get data)
        'load-binance-futures-market-data': {
            'task': 'apps.data.tasks.load_binance_futures_market_data_task',
            'schedule': crontab(minute=10, hour='*/2'),  # Every 2 hours at :10 (e.g. 00:10, 02:10, ...)
            'options': {'queue': 'data', 'priority': 8},
            'kwargs': {'days': 90, 'max_symbols_per_run': 30, 'timeframes': ('1h', '4h', '1d')},
        },
        # Keep active-signal list clean by expiring old signals
        # This updates `is_valid=False` for signals past `expires_at`.
        'cleanup-expired-signals': {
            'task': 'apps.signals.tasks.cleanup_expired_signals',
            # Run frequently so UI/API doesn't show stale active signals
            'schedule': crontab(minute='*/15'),
            'options': {'queue': 'signals', 'priority': 3},
        },
        # DISABLED: Monthly cleanup to preserve all historical data from 2020
        # 'historical-cleanup-monthly': {
        #     'task': 'apps.data.tasks.cleanup_old_data_task',
        #     'schedule': crontab(hour=4, minute=0, day_of_month='1'),  # Monthly on 1st at 4 AM UTC
        #     'priority': 1,
        # },
    },
    
    # Result backend configuration
    result_backend='django-db',
    result_expires=3600,  # 1 hour
    
    # Worker settings
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=200000,  # 200MB
    
    # Monitoring and logging
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


# Phase 5: Task monitoring and health checks
@app.task(bind=True)
def health_check(self):
    """Health check task for monitoring Celery worker status"""
    return {
        'status': 'healthy',
        'worker_id': self.request.id,
        'timestamp': self.request.timestamp,
    }


@app.task(bind=True)
def performance_metrics(self):
    """Collect performance metrics for monitoring"""
    from django.core.cache import cache
    from django.db import connection
    
    # Database connection status
    db_status = 'healthy'
    try:
        connection.ensure_connection()
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    # Cache status
    cache_status = 'healthy'
    try:
        cache.set('health_check', 'ok', 10)
        cache.get('health_check')
    except Exception as e:
        cache_status = f'unhealthy: {str(e)}'
    
    return {
        'database': db_status,
        'cache': cache_status,
        'worker_id': self.request.id,
        'timestamp': self.request.timestamp,
    }
