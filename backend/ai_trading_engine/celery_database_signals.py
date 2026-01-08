"""
Enhanced Celery configuration for database-driven signal generation
Phase 2: Updated beat schedule with database signal tasks
"""

import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')

app = Celery('ai_trading_engine')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Phase 2: Enhanced Celery Configuration for Database Signals
app.conf.update(
    # Task prioritization and routing
    task_routes={
        'apps.trading.tasks.*': {'queue': 'trading', 'priority': 10},
        'apps.signals.tasks.*': {'queue': 'signals', 'priority': 8},
        'apps.signals.database_signal_tasks.*': {'queue': 'database_signals', 'priority': 9},
        'apps.signals.data_quality_validation_tasks.*': {'queue': 'data_quality', 'priority': 7},
        'apps.sentiment.tasks.*': {'queue': 'sentiment', 'priority': 6},
        'apps.data.tasks.*': {'queue': 'data', 'priority': 4},
        'apps.analytics.tasks.*': {'queue': 'analytics', 'priority': 5},
    },
    
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Performance optimization
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    
    # Task retry and failure handling
    task_annotations={
        '*': {
            'retry_backoff': True,
            'retry_backoff_max': 600,
            'max_retries': 3,
        }
    },
    
    # Beat schedule for periodic tasks - Phase 2 Database Signals
    beat_schedule={
        # Data collection tasks (unchanged)
        'update-crypto-prices': {
            'task': 'apps.data.tasks.update_crypto_prices',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
            'priority': 10,
        },
        'historical-incremental-hourly': {
            'task': 'apps.data.tasks.update_historical_data_task',
            'schedule': crontab(minute=0),  # Every hour at minute 0
            'priority': 5,
        },
        'historical-incremental-daily-backup': {
            'task': 'apps.data.tasks.update_historical_data_daily_task',
            'schedule': crontab(hour=2, minute=30),  # Daily at 2:30 AM UTC
            'priority': 4,
        },
        'historical-weekly-gap-check': {
            'task': 'apps.data.tasks.weekly_gap_check_and_fill_task',
            'schedule': crontab(hour=3, minute=0, day_of_week='sun'),  # Weekly on Sunday at 3 AM UTC
            'priority': 3,
        },
        
        # NEW: Database-driven signal generation (every 30 minutes)
        'generate-database-signals': {
            'task': 'apps.signals.database_signal_tasks.generate_database_signals_task',
            'schedule': crontab(minute='*/30'),  # Every 30 minutes
            'priority': 9,
        },
        
        # NEW: Hybrid signal generation (every 15 minutes with fallback)
        'generate-hybrid-signals': {
            'task': 'apps.signals.database_signal_tasks.generate_hybrid_signals_task',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
            'priority': 8,
        },
        
        # NEW: Data quality validation (every 15 minutes)
        'validate-database-quality': {
            'task': 'apps.signals.database_signal_tasks.validate_database_data_quality_task',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
            'priority': 7,
        },
        
        # NEW: Technical indicators calculation (every hour)
        'calculate-database-indicators': {
            'task': 'apps.signals.database_signal_tasks.calculate_database_technical_indicators_task',
            'schedule': crontab(minute=0),  # Every hour at minute 0
            'priority': 6,
        },
        
        # NEW: Data quality monitoring (every 10 minutes)
        'monitor-data-freshness': {
            'task': 'apps.signals.data_quality_validation_tasks.monitor_data_freshness',
            'schedule': crontab(minute='*/10'),  # Every 10 minutes
            'priority': 6,
        },
        
        # NEW: Data gap detection (every 2 hours)
        'detect-data-gaps': {
            'task': 'apps.signals.data_quality_validation_tasks.detect_data_gaps',
            'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
            'priority': 5,
        },
        
        # NEW: Comprehensive data quality validation (daily)
        'comprehensive-data-quality-validation': {
            'task': 'apps.signals.data_quality_validation_tasks.comprehensive_data_quality_validation',
            'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM UTC
            'priority': 4,
        },
        
        # NEW: Database signal performance monitoring (every 30 minutes)
        'monitor-database-signal-performance': {
            'task': 'apps.signals.database_signal_tasks.monitor_database_signal_performance',
            'schedule': crontab(minute='*/30'),  # Every 30 minutes
            'priority': 6,
        },
        
        # NEW: Database signal health check (every 15 minutes)
        'database-signal-health-check': {
            'task': 'apps.signals.database_signal_tasks.database_signal_health_check',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
            'priority': 7,
        },
        
        # NEW: Cache cleanup (every 2 hours)
        'cleanup-database-signal-cache': {
            'task': 'apps.signals.database_signal_tasks.cleanup_database_signal_cache',
            'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
            'priority': 3,
        },
        
        # NEW: Database signal statistics update (every hour)
        'update-database-signal-statistics': {
            'task': 'apps.signals.database_signal_tasks.update_database_signal_statistics',
            'schedule': crontab(minute=0),  # Every hour at minute 0
            'priority': 5,
        },
        
        # NEW: Archive all generated signals to history (every hour)
        'archive-signals-to-history-hourly': {
            'task': 'apps.signals.enhanced_tasks.archive_signals_to_history_hourly_task',
            'schedule': crontab(minute=0),  # Every hour at minute 0
            'priority': 6,
        },
        
        # NEW: Generate enhanced signals hourly (at the start of each hour)
        'generate-enhanced-signals-hourly': {
            'task': 'apps.signals.enhanced_tasks.generate_enhanced_signals_hourly_task',
            'schedule': crontab(minute=0),  # Every hour at minute 0
            'priority': 9,
        },
        
        # NEW: Technical indicators quality validation (every 4 hours)
        'validate-technical-indicators-quality': {
            'task': 'apps.signals.data_quality_validation_tasks.validate_technical_indicators_quality',
            'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
            'priority': 4,
        },
        
        # NEW: Data quality report generation (daily)
        'generate-data-quality-report': {
            'task': 'apps.signals.data_quality_validation_tasks.generate_data_quality_report',
            'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM UTC
            'priority': 3,
        },
        
        # Keep existing tasks for backward compatibility
        'update-sentiment-analysis': {
            'task': 'apps.sentiment.tasks.update_sentiment',
            'schedule': crontab(minute='*/10'),  # Every 10 minutes
            'priority': 6,
        },
        'cleanup-old-data': {
            'task': 'apps.data.tasks.cleanup_old_data_task',
            'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
            'priority': 2,
        },
        
        # DISABLED: Old live API signal generation (replaced by database signals)
        # 'generate-trading-signals': {
        #     'task': 'apps.signals.tasks.generate_signals_for_all_symbols',
        #     'schedule': crontab(minute='*/15'),
        #     'priority': 8,
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


@app.task(bind=True)
def database_signal_system_health(self):
    """Comprehensive health check for database signal system"""
    try:
        from apps.signals.database_data_utils import get_database_health_status
        from apps.signals.database_signal_tasks import database_signal_health_check
        
        # Get database health
        db_health = get_database_health_status()
        
        # Get signal system health
        signal_health = database_signal_health_check()
        
        return {
            'database_health': db_health,
            'signal_health': signal_health,
            'overall_status': 'healthy' if (
                db_health.get('status') in ['HEALTHY', 'WARNING'] and
                signal_health.get('health_status') in ['healthy', 'warning']
            ) else 'critical',
            'timestamp': self.request.timestamp,
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'overall_status': 'error',
            'timestamp': self.request.timestamp,
        }














