# Signal Generation Differences: Local vs Production

## Overview
This document outlines the key differences in signal generation between local (Windows) and production (Linux) environments.

---

## 1. **Settings Module Configuration**

### Current Issue ❌
The signal generation script (`run_signal_generation.py`) **always uses development settings**:

```python
# Line 22 in run_signal_generation.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
```

### Local Environment:
- Uses: `ai_trading_engine.settings`
- DEBUG = True
- Development database settings
- Basic logging

### Production Environment:
- **Should use:** `ai_trading_engine.settings_production`
- DEBUG = False
- Production database settings (different connection pooling)
- Enhanced logging with file handlers
- Redis cache configuration
- Security settings

**⚠️ CRITICAL:** Production is using development settings!

---

## 2. **Execution Method**

### Local (Windows):
```batch
start "Signal Generation" cmd /k "cd /d %~dp0\.. && python scripts\run_signal_generation.py"
```
- Runs in a **visible terminal window**
- User can see output in real-time
- Process stops when window is closed
- Uses Windows path separators (`\`)

### Production (Linux):
```bash
nohup python scripts/run_signal_generation.py > logs/signal_generation.log 2>&1 &
```
- Runs in **background** (detached)
- Output redirected to log file
- Process survives terminal closure
- Uses Linux path separators (`/`)
- Captures PID for process management

**✅ BETTER:** Production approach is more suitable for servers

---

## 3. **Database Connection Handling**

### Local:
- Basic connection handling
- Development connection settings
- No connection pooling optimization
- Shorter connection timeouts

### Production:
- **Enhanced connection pooling** (`CONN_MAX_AGE: 600` = 10 minutes)
- Production database credentials
- Connection retry logic
- Database connection health checks
- Optimized for high load

**Key Differences:**
```python
# Local (settings.py)
'CONN_MAX_AGE': 300,  # 5 minutes

# Production (settings_production.py)
'CONN_MAX_AGE': 600,  # 10 minutes
```

---

## 4. **Logging Configuration**

### Local:
```python
# run_signal_generation.py - Basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
```
- Logs to **console/stdout**
- Simple format
- No file logging
- UTF-8 encoding handling for Windows

### Production:
- Should use **production logging configuration** from `settings_production.py`
- Logs to **file** (`logs/signal_generation.log`)
- More detailed format
- File rotation
- Separate log files for different components

**Production Logging (from settings_production.py):**
```python
LOGGING = {
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/signal_generation.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        }
    }
}
```

---

## 5. **Signal Generation Method**

### Both Use Same Function:
Both environments call the same function:
```python
result = generate_signals_for_all_symbols()
```

### But Different Execution Context:

#### Local:
- Runs directly in Python process
- Synchronous execution
- Immediate feedback
- Can be interrupted easily

#### Production:
- Should run via **Celery tasks** (better for production)
- Asynchronous execution
- Better resource management
- Automatic retry on failure
- Task queuing and prioritization

**Production Should Use:**
```python
# Via Celery (recommended for production)
from apps.signals.database_signal_tasks import generate_database_signals_task
generate_database_signals_task.delay()  # Async

# OR via Celery Beat (scheduled)
# Configured in settings_production.py
CELERY_BEAT_SCHEDULE = {
    'generate-database-signals': {
        'task': 'apps.signals.database_signal_tasks.generate_database_signals_task',
        'schedule': 1800,  # 30 minutes
    }
}
```

---

## 6. **Error Handling & Retry Logic**

### Local:
- Basic error handling
- Manual retry (script restarts)
- Errors visible in console

### Production:
- **Enhanced error handling** with retry logic
- Database connection recovery
- Automatic retry with exponential backoff
- Error logging to files
- Health monitoring

**Production Features:**
```python
# From run_signal_generation.py
def ensure_db_connection():
    """Ensure database connection is active, reconnect if needed"""
    try:
        connection.ensure_connection()
        return True
    except (InterfaceError, OperationalError) as e:
        # Reconnect logic
        close_db_connections()
        connection.ensure_connection()
        return True
```

---

## 7. **Update Interval**

### Both Use Same Interval:
```python
UPDATE_INTERVAL = 60 * 60  # 1 hour (3600 seconds)
INITIAL_DELAY = 30  # Wait 30 seconds before first generation
```

### But Production Should Use Celery Beat:
- **Local:** Script runs in loop with `time.sleep()`
- **Production:** Should use Celery Beat scheduler (more reliable)

**Production Celery Beat Schedule:**
```python
# From production_config.py
CELERY_BEAT_SCHEDULE = {
    'generate-database-signals': {
        'schedule': 1800,  # 30 minutes (more frequent)
    },
    'generate-hybrid-signals': {
        'schedule': 900,  # 15 minutes
    }
}
```

---

## 8. **Process Management**

### Local:
- Manual process management
- User must keep terminal open
- No automatic restart on failure
- Process visible in Task Manager

### Production:
- **Should use systemd** for process management
- Automatic restart on failure
- Runs as background service
- Process monitoring
- Log rotation

**Production Should Use:**
```ini
# systemd service (ai-trading-celery-worker.service)
[Service]
Restart=always
RestartSec=10
ExecStart=/path/to/venv/bin/celery -A ai_trading_engine worker
```

---

## 9. **Resource Management**

### Local:
- Single process
- Limited resource optimization
- Development-level performance

### Production:
- **Connection pooling** (database, Redis)
- **Worker processes** (if using Celery)
- **Caching** (Redis)
- **Resource limits** and monitoring
- Performance optimizations

**Production Optimizations:**
```python
# Database connection pooling
'CONN_MAX_AGE': 600

# Redis connection pooling
'CONNECTION_POOL_KWARGS': {
    'max_connections': 50,
    'retry_on_timeout': True,
}

# Celery worker configuration
worker_prefetch_multiplier=1
task_acks_late=True
```

---

## 10. **Environment Variables**

### Local:
- Uses `.env` file (if exists)
- Development defaults
- Basic configuration

### Production:
- Uses **environment variables** or `.env.production`
- Production-specific values
- Secure credential management
- Different database credentials

**Production Environment:**
```bash
DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
DB_HOST=production-db-host
DB_PASSWORD=secure-production-password
REDIS_HOST=production-redis-host
```

---

## Summary Table

| Feature | Local | Production (Current) | Production (Should Be) |
|---------|-------|---------------------|----------------------|
| **Settings Module** | `settings` ✅ | `settings` ❌ | `settings_production` ✅ |
| **Execution** | Terminal window | Background (nohup) ✅ | **Celery tasks** ✅ |
| **Logging** | Console | File ✅ | File + rotation ✅ |
| **Database** | Dev settings | Dev settings ❌ | **Prod settings** ✅ |
| **Process Mgmt** | Manual | nohup | **systemd** ✅ |
| **Scheduling** | Script loop | Script loop | **Celery Beat** ✅ |
| **Error Handling** | Basic | Enhanced ✅ | Enhanced ✅ |
| **Connection Pool** | Basic | Basic ❌ | **Optimized** ✅ |
| **Monitoring** | None | Logs | **Health checks** ✅ |
| **Restart** | Manual | Manual | **Automatic** ✅ |

---

## Critical Issues to Fix

### ❌ **Issue 1: Wrong Settings Module**
**Problem:** Script uses `settings` instead of `settings_production`
**Fix:** Update script to detect environment and use correct settings

### ❌ **Issue 2: Not Using Celery**
**Problem:** Running as standalone script instead of Celery task
**Fix:** Use Celery tasks for production signal generation

### ❌ **Issue 3: No Systemd Integration**
**Problem:** Using nohup instead of proper service management
**Fix:** Use systemd service (already exists: `ai-trading-celery-worker.service`)

### ❌ **Issue 4: Manual Scheduling**
**Problem:** Using script loop instead of Celery Beat
**Fix:** Use Celery Beat scheduler (already configured)

---

## Recommended Fixes

### Fix 1: Update Script to Use Production Settings
```python
# In run_signal_generation.py, line 22
import os
if os.environ.get('DJANGO_SETTINGS_MODULE'):
    # Use provided settings
    pass
else:
    # Auto-detect environment
    if os.path.exists('/etc/systemd') or os.environ.get('PRODUCTION'):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings_production')
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
```

### Fix 2: Use Celery for Production
Instead of running the script directly, use Celery:
```bash
# Production should use Celery (already configured)
# Celery Beat will schedule tasks automatically
# No need to run run_signal_generation.py manually
```

### Fix 3: Update Automation Script
```bash
# In start_all_automation.sh
# For production, don't run signal generation script
# Instead, ensure Celery services are running:
sudo systemctl start ai-trading-celery-worker
sudo systemctl start ai-trading-celery-beat
```

---

## Next Steps

Tell me which fixes you want to implement:
1. ✅ Update script to auto-detect and use production settings
2. ✅ Remove signal generation script from production automation (use Celery instead)
3. ✅ Update automation script to use systemd services
4. ✅ All of the above


