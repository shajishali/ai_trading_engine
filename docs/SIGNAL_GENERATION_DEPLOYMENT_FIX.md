# Signal Generation Page - Deployment Fix Guide

## Overview
This guide helps fix signal generation page issues in deployment environments.

## Recent Improvements Made

### 1. Enhanced Error Handling
- Added database connection retry logic (3 retries with exponential backoff)
- Added specific error type detection and handling
- Improved error messages for better debugging
- Added timeout handling

### 2. Frontend Improvements
- Better error message display based on error types
- Network error handling
- More informative user feedback

### 3. Diagnostic Tools
- Created diagnostic script: `backend/scripts/diagnose_signal_generation.py`

## Quick Fix Steps (Using PuTTY/SSH)

### Step 1: Connect to Server
```bash
# Connect via PuTTY or SSH
ssh user@your-server-ip
```

### Step 2: Navigate to Project
```bash
cd /path/to/your/project/backend
source venv/bin/activate  # Activate virtual environment
```

### Step 3: Run Diagnostic Script
```bash
# Option 1: Using Django shell
python manage.py shell < scripts/diagnose_signal_generation.py

# Option 2: Direct execution
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
python scripts/diagnose_signal_generation.py
```

### Step 4: Check Common Issues

#### Issue 1: Database Connection Problems
```bash
# Test database connection
python manage.py dbshell
# If connection fails, check:
# - Database server is running
# - Credentials in settings_production.py
# - Network connectivity
```

#### Issue 2: Missing Market Data
```bash
# Update market data
python manage.py update_all_coins

# Or run specific update
python manage.py update_coin_data BTC
```

#### Issue 3: Missing Symbols
```bash
# Check if symbols exist
python manage.py shell
>>> from apps.trading.models import Symbol
>>> Symbol.objects.filter(is_active=True).count()

# If count is 0, populate symbols
python manage.py populate_symbols
```

#### Issue 4: Cache Issues
```bash
# Test Redis connection
redis-cli ping
# Should return: PONG

# If Redis is not running
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Step 5: Check Application Logs
```bash
# View recent errors
tail -f logs/errors.log

# View signal generation logs
tail -f logs/trading_engine.log | grep -i signal

# Check Django logs
tail -f /var/log/django/error.log
```

### Step 6: Test Signal Generation Manually
```bash
python manage.py shell
```

In Python shell:
```python
from apps.trading.models import Symbol
from apps.signals.services import SignalGenerationService

# Get a symbol
symbol = Symbol.objects.filter(symbol__iexact='BTC').first()
if symbol:
    # Generate signals
    service = SignalGenerationService()
    signals = service.generate_signals_for_symbol(symbol)
    print(f"Generated {len(signals)} signals")
else:
    print("Symbol not found")
```

### Step 7: Restart Services (if needed)
```bash
# Restart Gunicorn
sudo systemctl restart gunicorn
# OR
sudo systemctl restart your-app-service

# Restart Celery (if using)
sudo systemctl restart ai-trading-celery-worker
sudo systemctl restart ai-trading-celery-beat

# Check status
sudo systemctl status gunicorn
sudo systemctl status ai-trading-celery-worker
```

## Common Error Messages and Fixes

### Error: "Database connection failed"
**Fix:**
1. Check database server is running
2. Verify database credentials
3. Check network connectivity
4. Restart database service if needed

### Error: "Symbol not found"
**Fix:**
1. Ensure symbols are populated: `python manage.py populate_symbols`
2. Check symbol is active: `Symbol.objects.filter(symbol='BTC').update(is_active=True)`

### Error: "Insufficient market data"
**Fix:**
1. Update market data: `python manage.py update_all_coins`
2. Check MarketData table has recent entries
3. Verify data import scripts are running

### Error: "Signal generation timed out"
**Fix:**
1. Check server resources (CPU, memory)
2. Review signal generation logic for performance issues
3. Consider running signal generation as background task (Celery)

### Error: "Service temporarily unavailable"
**Fix:**
1. Check if application server is running
2. Review application logs for errors
3. Check if database is accessible
4. Verify Redis/cache is running

## Testing the Fix

### Test via Browser
1. Navigate to signal generation page
2. Click "Generate New" button
3. Check for error messages
4. Verify signals are generated

### Test via API
```bash
# Using curl (replace with your domain and credentials)
curl -X POST http://your-domain.com/signals/api/generate/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: your-csrf-token" \
  -d '{"symbol": "BTC"}'
```

## Monitoring

### Check Signal Generation Status
```bash
# View recent signals
python manage.py shell
>>> from apps.signals.models import TradingSignal
>>> TradingSignal.objects.order_by('-created_at')[:5]
```

### Monitor Logs in Real-time
```bash
# Watch error logs
tail -f logs/errors.log

# Watch application logs
tail -f logs/trading_engine.log
```

## Additional Resources

- Celery Setup: `docs/PUTTY_CELERY_SETUP_STEPS.md`
- Deployment Guide: `DEPLOYMENT_GUIDE.md`
- Production Settings: `backend/ai_trading_engine/settings_production.py`

## Support

If issues persist:
1. Run diagnostic script and share output
2. Check application logs for detailed errors
3. Verify all services are running
4. Check database and cache connectivity

## Code Changes Summary

### Backend (`backend/apps/signals/views.py`)
- Enhanced `generate_signals_manual()` function
- Added database connection retry logic
- Improved error handling with specific error types
- Better logging for debugging

### Frontend (`frontend/templates/dashboard/signals.html`)
- Improved error message handling
- Better user feedback based on error types
- Network error detection
- More informative notifications

### Diagnostic Tool (`backend/scripts/diagnose_signal_generation.py`)
- Comprehensive diagnostic script
- Tests all components needed for signal generation
- Provides recommendations for fixes

