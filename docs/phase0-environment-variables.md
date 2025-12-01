# Phase 0: Environment Variables Documentation

## Overview
This document lists all environment variables required for production deployment of the AI Trading Engine.

## Required Environment Variables

### Django Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEBUG` | Yes | `False` | Set to `False` in production |
| `SECRET_KEY` | Yes | - | Django secret key (generate strong random key) |
| `PRODUCTION_SECRET_KEY` | Yes | - | Production-specific secret key |
| `ALLOWED_HOSTS` | Yes | - | Comma-separated list of IP addresses and domains |
| `PRODUCTION_ALLOWED_HOSTS` | Yes | - | Production allowed hosts |

**How to generate SECRET_KEY:**
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Database Configuration (MySQL)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_ENGINE` | Yes | `django.db.backends.mysql` | Database engine |
| `DB_NAME` | Yes | `trading_engine_db` | Database name |
| `DB_USER` | Yes | `tradingengine_user` | Database user |
| `DB_PASSWORD` | Yes | - | Database password (strong password required) |
| `DB_HOST` | Yes | `localhost` | Database host |
| `DB_PORT` | Yes | `3306` | Database port |
| `DATABASE_URL` | Optional | - | Full database URL (alternative format) |

### Redis Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_HOST` | Optional | `127.0.0.1` | Redis host |
| `REDIS_PORT` | Optional | `6379` | Redis port |
| `REDIS_DB` | Optional | `0` | Redis database number |
| `REDIS_PASSWORD` | Optional | - | Redis password (if configured) |

### Celery Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CELERY_BROKER_URL` | Yes | `redis://localhost:6379/0` | Celery broker URL |
| `CELERY_RESULT_BACKEND` | Yes | `redis://localhost:6379/0` | Celery result backend |
| `CELERY_WORKER_CONCURRENCY` | Optional | `2` | Number of worker processes (for 2GB RAM) |
| `CELERY_MAX_TASKS_PER_CHILD` | Optional | `1000` | Max tasks per worker child |
| `CELERY_TASK_TIME_LIMIT` | Optional | `3600` | Hard time limit in seconds |
| `CELERY_TASK_SOFT_TIME_LIMIT` | Optional | `3000` | Soft time limit in seconds |

### AWS S3 Configuration (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `USE_S3` | Optional | `False` | Enable S3 for static/media files |
| `AWS_ACCESS_KEY_ID` | If USE_S3=True | - | AWS access key ID |
| `AWS_SECRET_ACCESS_KEY` | If USE_S3=True | - | AWS secret access key |
| `AWS_STORAGE_BUCKET_NAME` | If USE_S3=True | - | S3 bucket name |
| `AWS_S3_REGION_NAME` | Optional | `us-east-1` | AWS region |

### API Keys (Optional - for external services)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEWS_API_KEY` | No | NewsAPI.org API key |
| `CRYPTOPANIC_API_KEY` | No | CryptoPanic API key |
| `CRYPTONEWS_API_KEY` | No | CryptoNewsAPI.com key |
| `STOCKDATA_API_KEY` | No | StockData.org API key (preferred) |
| `BINANCE_API_KEY` | No | Binance API key |
| `BINANCE_SECRET_KEY` | No | Binance secret key |
| `COINBASE_API_KEY` | No | Coinbase API key |
| `COINBASE_SECRET_KEY` | No | Coinbase secret key |

### Trading Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEFAULT_CURRENCY` | Optional | `USD` | Default trading currency |
| `RISK_PERCENTAGE` | Optional | `1.0` | Risk percentage per trade |
| `MAX_POSITION_SIZE` | Optional | `5.0` | Maximum position size |
| `SIGNAL_CONFIDENCE_THRESHOLD` | Optional | `0.8` | Minimum confidence for signals |
| `MODEL_UPDATE_FREQUENCY` | Optional | `7200` | Model update frequency in seconds |

### Email Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMAIL_BACKEND` | Optional | `django.core.mail.backends.smtp.EmailBackend` | Email backend |
| `EMAIL_HOST` | Optional | `smtp.gmail.com` | SMTP host |
| `EMAIL_PORT` | Optional | `587` | SMTP port |
| `EMAIL_USE_TLS` | Optional | `True` | Use TLS |
| `EMAIL_HOST_USER` | Optional | - | SMTP username |
| `EMAIL_HOST_PASSWORD` | Optional | - | SMTP password/app password |
| `DEFAULT_FROM_EMAIL` | Optional | `noreply@ai-trading-engine.com` | Default from email |
| `SERVER_EMAIL` | Optional | - | Server email address |

### OAuth/Social Authentication (Optional)

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_OAUTH2_CLIENT_ID` | No | Google OAuth client ID |
| `GOOGLE_OAUTH2_CLIENT_SECRET` | No | Google OAuth client secret |

### CORS Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ALLOWED_ORIGINS` | Yes | - | Comma-separated list of allowed origins |

### Security & Monitoring (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECURITY_WEBHOOK_URL` | No | - | Webhook URL for security alerts |
| `SLACK_WEBHOOK_URL` | No | - | Slack webhook for notifications |
| `IP_WHITELIST_ENABLED` | Optional | `False` | Enable IP whitelisting |
| `WHITELISTED_IPS` | Optional | - | Comma-separated list of whitelisted IPs |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | Optional | `INFO` | Logging level |
| `LOG_FILE` | Optional | `logs/trading_engine.log` | Log file path |

### Backup Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BACKUP_PATH` | Optional | `/home/tradingengine/backups` | Backup directory path |

## Environment Variable Priority

1. **Production .env file** (highest priority)
2. **System environment variables**
3. **Default values in settings.py** (lowest priority)

## Security Best Practices

1. **Never commit .env files** with actual secrets to Git
2. **Use strong passwords** for database and Redis
3. **Rotate secrets regularly** (especially SECRET_KEY)
4. **Restrict file permissions**: `chmod 600 .env`
5. **Use environment-specific values** for production vs development
6. **Store sensitive keys** in secure password managers
7. **Use AWS Secrets Manager** or similar for production (optional)

## Generating Secure Values

### Django SECRET_KEY
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Database Password
```bash
# Generate strong password (Linux/Mac)
openssl rand -base64 32

# Or use Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Redis Password
```bash
# Generate strong password
openssl rand -base64 32
```

## Example Production .env File Structure

See `backend/env.production.template` for a complete template.

## Validation Checklist

Before deployment, verify:
- [ ] All required variables are set
- [ ] DEBUG=False
- [ ] SECRET_KEY is strong and unique
- [ ] Database credentials are correct
- [ ] Redis connection string is correct
- [ ] ALLOWED_HOSTS includes production IP/domain
- [ ] CORS_ALLOWED_ORIGINS includes production frontend URL
- [ ] Email configuration is tested
- [ ] File permissions are secure (600 for .env)






