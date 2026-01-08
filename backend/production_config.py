"""
Production configuration for database-driven signal generation system
Phase 3: Production deployment configuration and optimization
"""

import os
import logging
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Production Settings
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com', 'localhost']

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'ai_trading_engine_prod'),
        'USER': os.environ.get('DB_USER', 'trading_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'secure_password'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
            'CONN_MAX_AGE': 600,
        },
    }
}

# Redis Configuration for Caching and Celery
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'TIMEOUT': 300,
        'VERSION': 1,
        'KEY_PREFIX': 'ai_trading_engine',
    }
}

# Celery Configuration for Production
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Celery Beat Schedule for Production
CELERY_BEAT_SCHEDULE = {
    # Database signal generation (every 30 minutes)
    'generate-database-signals': {
        'task': 'apps.signals.database_signal_tasks.generate_database_signals_task',
        'schedule': 1800,  # 30 minutes
        'options': {'queue': 'database_signals', 'priority': 9}
    },
    
    # Hybrid signal generation (every 15 minutes)
    'generate-hybrid-signals': {
        'task': 'apps.signals.database_signal_tasks.generate_hybrid_signals_task',
        'schedule': 900,  # 15 minutes
        'options': {'queue': 'signals', 'priority': 8}
    },
    
    # Data quality validation (every 15 minutes)
    'validate-database-quality': {
        'task': 'apps.signals.database_signal_tasks.validate_database_data_quality_task',
        'schedule': 900,  # 15 minutes
        'options': {'queue': 'data_quality', 'priority': 7}
    },
    
    # Technical indicators calculation (every hour)
    'calculate-database-indicators': {
        'task': 'apps.signals.database_signal_tasks.calculate_database_technical_indicators_task',
        'schedule': 3600,  # 1 hour
        'options': {'queue': 'data', 'priority': 6}
    },
    
    # Data freshness monitoring (every 10 minutes)
    'monitor-data-freshness': {
        'task': 'apps.signals.data_quality_validation_tasks.monitor_data_freshness',
        'schedule': 600,  # 10 minutes
        'options': {'queue': 'monitoring', 'priority': 6}
    },
    
    # Performance monitoring (every 30 minutes)
    'monitor-database-signal-performance': {
        'task': 'apps.signals.database_signal_tasks.monitor_database_signal_performance',
        'schedule': 1800,  # 30 minutes
        'options': {'queue': 'monitoring', 'priority': 6}
    },
    
    # System health check (every 15 minutes)
    'database-signal-health-check': {
        'task': 'apps.signals.database_signal_tasks.database_signal_health_check',
        'schedule': 900,  # 15 minutes
        'options': {'queue': 'monitoring', 'priority': 7}
    },
    
    # Cache cleanup (every 2 hours)
    'cleanup-database-signal-cache': {
        'task': 'apps.signals.database_signal_tasks.cleanup_database_signal_cache',
        'schedule': 7200,  # 2 hours
        'options': {'queue': 'maintenance', 'priority': 3}
    },
    
    # Historical data updates (every hour)
    'historical-incremental-hourly': {
        'task': 'apps.data.tasks.update_historical_data_task',
        'schedule': 3600,  # 1 hour
        'options': {'queue': 'data', 'priority': 5}
    },
    
    # Archive all generated signals to history (every hour)
    'archive-signals-to-history-hourly': {
        'task': 'apps.signals.enhanced_tasks.archive_signals_to_history_hourly_task',
        'schedule': 3600,  # 1 hour
        'options': {'queue': 'signals', 'priority': 6}
    },
    
    # Generate enhanced signals hourly (at the start of each hour)
    'generate-enhanced-signals-hourly': {
        'task': 'apps.signals.enhanced_tasks.generate_enhanced_signals_hourly_task',
        'schedule': 3600,  # 1 hour
        'options': {'queue': 'signals', 'priority': 9}
    },
    
    # Daily backup (2:30 AM UTC)
    'historical-incremental-daily-backup': {
        'task': 'apps.data.tasks.update_historical_data_daily_task',
        'schedule': {'hour': 2, 'minute': 30},
        'options': {'queue': 'data', 'priority': 4}
    },
    
    # Weekly gap check (Sunday 3:00 AM UTC)
    'historical-weekly-gap-check': {
        'task': 'apps.data.tasks.weekly_gap_check_and_fill_task',
        'schedule': {'hour': 3, 'minute': 0, 'day_of_week': 0},  # Sunday
        'options': {'queue': 'data', 'priority': 3}
    },
}

# Celery Task Routes for Production
CELERY_TASK_ROUTES = {
    'apps.signals.database_signal_tasks.*': {'queue': 'database_signals'},
    'apps.signals.data_quality_validation_tasks.*': {'queue': 'data_quality'},
    'apps.signals.tasks.*': {'queue': 'signals'},
    'apps.signals.enhanced_tasks.*': {'queue': 'signals'},
    'apps.data.tasks.*': {'queue': 'data'},
    'apps.trading.tasks.*': {'queue': 'trading'},
    'apps.sentiment.tasks.*': {'queue': 'sentiment'},
    'apps.analytics.tasks.*': {'queue': 'analytics'},
}

# Celery Worker Configuration
CELERY_WORKER_CONCURRENCY = 4
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000  # 200MB
CELERY_WORKER_DISABLE_RATE_LIMITS = False

# Security Settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/ai_trading_engine/django.log',
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/ai_trading_engine/celery.log',
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps.signals': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps.data': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'celery': {
            'handlers': ['celery_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Performance Settings
CONN_MAX_AGE = 600
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Static and Media Files
STATIC_URL = '/static/'
STATIC_ROOT = '/var/www/ai_trading_engine/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = '/var/www/ai_trading_engine/media/'

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@your-domain.com')

# Email verification links - Use HTTP in production (set to True if using HTTP)
USE_HTTP_IN_PRODUCTION = os.environ.get('USE_HTTP_IN_PRODUCTION', 'True').lower() == 'true'
FORCE_HTTPS_IN_EMAILS = False  # Disabled when using HTTP

# Monitoring and Alerting
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=True
    )

# Signal Generation Configuration
SIGNAL_GENERATION_MODE = os.environ.get('SIGNAL_GENERATION_MODE', 'hybrid')  # database, live_api, hybrid, auto
DATABASE_SIGNAL_ENABLED = os.environ.get('DATABASE_SIGNAL_ENABLED', 'True').lower() == 'true'
LIVE_API_FALLBACK_ENABLED = os.environ.get('LIVE_API_FALLBACK_ENABLED', 'True').lower() == 'true'

# Performance Optimization Settings
CACHE_WARMING_ENABLED = os.environ.get('CACHE_WARMING_ENABLED', 'True').lower() == 'true'
QUERY_OPTIMIZATION_ENABLED = os.environ.get('QUERY_OPTIMIZATION_ENABLED', 'True').lower() == 'true'
BULK_OPERATION_SIZE = int(os.environ.get('BULK_OPERATION_SIZE', '100'))

# Monitoring Settings
HEALTH_CHECK_INTERVAL = int(os.environ.get('HEALTH_CHECK_INTERVAL', '300'))  # 5 minutes
PERFORMANCE_MONITORING_ENABLED = os.environ.get('PERFORMANCE_MONITORING_ENABLED', 'True').lower() == 'true'
ALERT_THRESHOLDS = {
    'database_health_critical': 'CRITICAL',
    'data_freshness_hours': 2,
    'signal_generation_failure_rate': 0.1,
    'cache_hit_rate_minimum': 0.7,
    'memory_usage_maximum': 0.8,
    'response_time_maximum': 5.0
}

# API Configuration
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com",
]

CORS_ALLOW_CREDENTIALS = True

# Production-specific settings
USE_TZ = True
TIME_ZONE = 'UTC'

# Database connection pooling
DATABASE_CONNECTION_POOL_SIZE = 20
DATABASE_CONNECTION_MAX_AGE = 600

# Cache configuration for production
CACHE_TTL = 3600  # 1 hour default
CACHE_MAX_ENTRIES = 10000
CACHE_CULL_FREQUENCY = 3

# Signal generation performance settings
SIGNAL_GENERATION_BATCH_SIZE = 50
SIGNAL_GENERATION_TIMEOUT = 300  # 5 minutes
SIGNAL_GENERATION_RETRY_ATTEMPTS = 3

# Data quality settings
DATA_QUALITY_MIN_COMPLETENESS = 0.8
DATA_QUALITY_MAX_AGE_HOURS = 2
DATA_QUALITY_CHECK_INTERVAL = 900  # 15 minutes

# Monitoring and alerting settings
MONITORING_ENABLED = True
ALERT_EMAIL_ENABLED = True
ALERT_SLACK_ENABLED = False
ALERT_WEBHOOK_URL = os.environ.get('ALERT_WEBHOOK_URL', '')

# Production deployment settings
DEPLOYMENT_ENVIRONMENT = 'production'
VERSION = os.environ.get('APP_VERSION', '1.0.0')
BUILD_NUMBER = os.environ.get('BUILD_NUMBER', 'unknown')

# Health check settings
HEALTH_CHECK_ENDPOINTS = [
    '/health/database/',
    '/health/celery/',
    '/health/cache/',
    '/health/signals/',
]

# Performance monitoring
PERFORMANCE_MONITORING_INTERVAL = 300  # 5 minutes
PERFORMANCE_METRICS_RETENTION_DAYS = 30

# Backup settings
BACKUP_ENABLED = True
BACKUP_SCHEDULE = '0 2 * * *'  # Daily at 2 AM
BACKUP_RETENTION_DAYS = 30
BACKUP_STORAGE_PATH = '/var/backups/ai_trading_engine/'

# Security headers
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True














