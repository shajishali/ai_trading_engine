"""
Production settings for AI Trading Engine

This file contains production-specific configurations including:
- Production database settings
- Redis configuration
- Security hardening
- Performance optimizations
- SSL/HTTPS settings
"""

import os
from pathlib import Path
from decouple import config
from .settings import *

# Override DEBUG for production
DEBUG = False

# Production secret key (should be set via environment variable)
SECRET_KEY = config('PRODUCTION_SECRET_KEY', default=SECRET_KEY)

# Production allowed hosts
ALLOWED_HOSTS = config('PRODUCTION_ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# HSTS settings (DISABLED - not using HTTPS)
SECURE_HSTS_SECONDS = 0  # Disabled
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# SSL/HTTPS settings (DISABLED - using HTTP only)
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Production database configuration (MySQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='trading_engine_db'),
        'USER': config('DB_USER', default='tradingengine_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'CONN_MAX_AGE': 600,  # 10 minutes connection pooling
        'ATOMIC_REQUESTS': True,
        'AUTOCOMMIT': True,
    }
}

# Redis configuration for production
REDIS_HOST = config('REDIS_HOST', default='localhost')
REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)
REDIS_DB = config('REDIS_DB', default=0, cast=int)
REDIS_PASSWORD = config('REDIS_PASSWORD', default=None)

# Cache configuration with Redis
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PASSWORD': REDIS_PASSWORD,
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'ai_trading_engine',
        'TIMEOUT': 300,  # 5 minutes default
    },
    'session': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PASSWORD': REDIS_PASSWORD,
        },
        'KEY_PREFIX': 'session',
        'TIMEOUT': 3600,  # 1 hour for sessions
    }
}

# Channel layers with Redis for production
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [{
                'host': REDIS_HOST,
                'port': REDIS_PORT,
                'db': REDIS_DB,
                'password': REDIS_PASSWORD,
            }],
        },
    },
}

# Celery configuration for production
CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
CELERY_TASK_ALWAYS_EAGER = False
CELERY_WORKER_CONCURRENCY = config('CELERY_WORKER_CONCURRENCY', default=4, cast=int)
CELERY_MAX_TASKS_PER_CHILD = config('CELERY_MAX_TASKS_PER_CHILD', default=1000, cast=int)
CELERY_TASK_TIME_LIMIT = config('CELERY_TASK_TIME_LIMIT', default=3600, cast=int)  # 1 hour
CELERY_TASK_SOFT_TIME_LIMIT = config('CELERY_TASK_SOFT_TIME_LIMIT', default=3000, cast=int)  # 50 minutes

# AWS S3 Configuration for production
USE_S3 = config('USE_S3', default=True, cast=bool)

# Validate S3 credentials - disable S3 if credentials are not provided
if USE_S3:
    aws_access_key = config('AWS_ACCESS_KEY_ID', default='')
    aws_secret_key = config('AWS_SECRET_ACCESS_KEY', default='')
    aws_bucket = config('AWS_STORAGE_BUCKET_NAME', default='')
    
    if not aws_access_key or not aws_secret_key or not aws_bucket:
        print("Warning: S3 credentials not provided. Disabling S3 and using local storage.")
        USE_S3 = False

if USE_S3:
    # AWS S3 settings
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_DEFAULT_ACL = 'public-read'
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    
    # Static files configuration for S3
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
    
    # Media files configuration for S3
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    
    # Remove local static/media settings
    STATIC_ROOT = None
    MEDIA_ROOT = None
else:
    # Static files configuration for production (local)
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    
    # Media files configuration for production (local)
    MEDIA_ROOT = BASE_DIR / 'media'
    MEDIA_URL = '/media/'

# Logging configuration for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s", "process": "%(process)d", "thread": "%(thread)d"}',
            'style': '%',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'trading_engine_prod.log',
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
        },
        'json_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'trading_engine_prod_json.log',
            'formatter': 'json',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'errors_prod.log',
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 20,
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
        },
    },
    'root': {
        'handlers': ['file', 'json_file', 'error_file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'json_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'trading': {
            'handlers': ['file', 'json_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['file', 'json_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'allauth': {
            'handlers': ['file', 'json_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Import security settings
from .security_settings import *

# Performance optimizations for production
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'apps.core.middleware.SecurityHeadersMiddleware',
    'apps.core.middleware.RequestValidationMiddleware',
    'apps.core.middleware.CSRFProtectionMiddleware',
    'apps.core.middleware.AuditLoggingMiddleware',
    'apps.core.middleware.IPWhitelistMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.APIRateLimitMiddleware',  # Moved after AuthenticationMiddleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.PerformanceMonitoringMiddleware',
]

# CORS settings for production
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='https://yourdomain.com').split(',')
CORS_ALLOW_CREDENTIALS = True

# Rate limiting for production
REST_FRAMEWORK = {
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
        'anon': '50/hour',  # Reduced for production
        'user': '500/hour'  # Reduced for production
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Production-specific trading settings
TRADING_SETTINGS = {
    'DEFAULT_CURRENCY': config('DEFAULT_CURRENCY', default='USD'),
    'RISK_PERCENTAGE': config('RISK_PERCENTAGE', default=1.0, cast=float),  # Reduced risk for production
    'MAX_POSITION_SIZE': config('MAX_PERCENTAGE', default=5.0, cast=float),  # Reduced size for production
    'SIGNAL_CONFIDENCE_THRESHOLD': config('SIGNAL_CONFIDENCE_THRESHOLD', default=0.8, cast=float),  # Higher threshold for production
    'MODEL_UPDATE_FREQUENCY': config('MODEL_UPDATE_FREQUENCY', default=7200, cast=int),  # Less frequent updates
}

# Security-specific settings
SECURITY_SETTINGS = {
    'SECURITY_AUDIT_ENABLED': True,
    'SECURITY_MONITORING_ENABLED': True,
    'SECURITY_ALERT_THRESHOLD': 0.8,
    'SECURITY_CHECK_INTERVAL': 60,
    'SECURITY_WEBHOOK_URL': config('SECURITY_WEBHOOK_URL', default=None),
    'SLACK_WEBHOOK_URL': config('SLACK_WEBHOOK_URL', default=None),
    'IP_WHITELIST_ENABLED': config('IP_WHITELIST_ENABLED', default=False, cast=bool),
    'WHITELISTED_IPS': config('WHITELISTED_IPS', default='', cast=lambda v: v.split(',') if v else []),
    'MAX_POST_SIZE': config('MAX_POST_SIZE', default=10 * 1024 * 1024, cast=int),  # 10MB
    'BLOCKED_USER_AGENTS': [
        'sqlmap', 'nikto', 'nmap', 'scanner', 'bot', 'crawler',
        'spider', 'harvester', 'grabber', 'wget', 'curl'
    ],
    'ALLOWED_CONTENT_TYPES': [
        'application/json',
        'application/x-www-form-urlencoded',
        'multipart/form-data',
        'text/plain'
    ],
    'BLOCKED_EXTENSIONS': [
        '.php', '.asp', '.aspx', '.jsp', '.exe', '.bat', '.cmd',
        '.com', '.pif', '.scr', '.vbs', '.js', '.jar'
    ]
}

# Enhanced logging for security
LOGGING['loggers']['security_audit'] = {
    'handlers': ['file', 'json_file', 'error_file'],
    'level': 'INFO',
    'propagate': False,
}

LOGGING['loggers']['security_monitoring'] = {
    'handlers': ['file', 'json_file', 'error_file'],
    'level': 'INFO',
    'propagate': False,
}

LOGGING['loggers']['audit'] = {
    'handlers': ['file', 'json_file', 'error_file'],
    'level': 'INFO',
    'propagate': False,
}

# Security monitoring configuration
SECURITY_MONITORING = {
    'ENABLED': True,
    'CHECK_INTERVAL': 60,  # 1 minute
    'ALERT_THRESHOLD': 0.8,  # 80% security score
    'ALERT_CHANNELS': ['email', 'slack', 'webhook'],
    'SECURITY_SCORE_CALCULATION': True,
    'VULNERABILITY_SCANNING': True,
    'PENETRATION_TESTING': False,  # Enable for security audits
    'INCIDENT_RESPONSE_PLAN': True,
    'FORENSIC_LOGGING': True,
    'THREAT_INTELLIGENCE': True
}

# Health check settings
HEALTH_CHECK = {
    'ENABLED': True,
    'CHECK_INTERVAL': 60,  # 1 minute
    'MAX_FAILURES': 3,
    'RECOVERY_TIMEOUT': 300,  # 5 minutes
}

# Monitoring and alerting settings
MONITORING = {
    'ENABLED': True,
    'METRICS_INTERVAL': 30,  # 30 seconds
    'ALERT_THRESHOLD': 0.8,  # 80% performance threshold
    'SLACK_WEBHOOK': config('SLACK_WEBHOOK', default=None),
    'EMAIL_ALERTS': config('EMAIL_ALERTS', default=False, cast=bool),
}

# Backup settings
BACKUP = {
    'ENABLED': True,
    'FREQUENCY': 'daily',
    'RETENTION_DAYS': 30,
    'BACKUP_PATH': config('BACKUP_PATH', default='/backups'),
}

# Load balancer settings
LOAD_BALANCER = {
    'ENABLED': config('LOAD_BALANCER_ENABLED', default=False, cast=bool),
    'HEALTH_CHECK_PATH': '/health/',
    'STICKY_SESSIONS': True,
    'SESSION_COOKIE_NAME': 'sessionid',
}
