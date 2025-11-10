# Automation System Fix - Step-by-Step Action Plan

## Executive Summary

This document outlines the step-by-step actions required to fix the automated trading system. The system needs to:
1. Store coin data in DB every 30 minutes
2. Generate 10 best signals based on strategy, fundamental news, and market sentiment

**Current Issues Identified:**
- Celery tasks are configured but may not be executing properly
- Signal generation currently selects top 5 signals (needs to be 10)
- News and sentiment integration exists but may not be properly weighted in final signal selection
- Redis/Celery workers may not be running
- Multiple Celery configuration files causing confusion

---

## Phase 1: System Diagnosis & Verification

### Step 1.1: Verify Redis is Running
**Action:** Check if Redis server is running
```bash
# Windows PowerShell
Get-Process redis-server -ErrorAction SilentlyContinue
# Or check port
Test-NetConnection -ComputerName localhost -Port 6379

# If not running, start Redis
redis-server.exe redis.conf
```

**Expected Result:** Redis should be running on port 6379

**If Redis is not running:**
- Install Redis for Windows if not installed
- Start Redis server: `redis-server.exe redis.conf`
- Verify connection: `redis-cli ping` (should return PONG)

---

### Step 1.2: Verify Celery Worker is Running
**Action:** Check if Celery worker process is active
```bash
# Windows PowerShell
Get-Process python | Where-Object {$_.CommandLine -like "*celery*worker*"}

# Or check via Celery inspect
cd backend
python -m celery -A ai_trading_engine inspect active
```

**Expected Result:** Celery worker should be running and connected to Redis

**If Celery worker is not running:**
- Start worker: `python -m celery -A ai_trading_engine worker --loglevel=info --pool=solo`
- Verify it connects to Redis broker

---

### Step 1.3: Verify Celery Beat Scheduler is Running
**Action:** Check if Celery Beat (scheduler) is running
```bash
# Windows PowerShell
Get-Process python | Where-Object {$_.CommandLine -like "*celery*beat*"}

# Or check beat schedule
cd backend
python -m celery -A ai_trading_engine inspect scheduled
```

**Expected Result:** Celery Beat should be running and scheduling tasks

**If Celery Beat is not running:**
- Start beat: `python -m celery -A ai_trading_engine beat --loglevel=info`
- Verify it can read the beat schedule from celery.py

---

### Step 1.4: Verify Database Connection
**Action:** Test database connectivity and check recent data
```bash
cd backend
python manage.py shell
```

```python
from django.utils import timezone
from apps.data.models import MarketData
from apps.trading.models import Symbol
from datetime import timedelta

# Check recent market data
recent_data = MarketData.objects.filter(
    timestamp__gte=timezone.now() - timedelta(hours=1)
).count()
print(f"Recent market data records (last hour): {recent_data}")

# Check active symbols
active_symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True).count()
print(f"Active crypto symbols: {active_symbols}")
```

**Expected Result:** Should have recent market data and active symbols

---

### Step 1.5: Check Recent Task Execution
**Action:** Verify if tasks have been executing
```bash
cd backend
python manage.py shell
```

```python
from django_celery_results.models import TaskResult
from django.utils import timezone
from datetime import timedelta

# Check recent task results
recent_tasks = TaskResult.objects.filter(
    date_created__gte=timezone.now() - timedelta(hours=2)
).order_by('-date_created')[:10]

for task in recent_tasks:
    print(f"{task.task_name}: {task.status} at {task.date_created}")
```

**Expected Result:** Should see recent task executions for data updates and signal generation

---

## Phase 2: Fix Celery Configuration

### Step 2.1: Consolidate Celery Configuration
**Action:** Ensure single source of truth for Celery configuration

**File to check:** `backend/ai_trading_engine/celery.py`

**Verify the beat schedule includes:**
- `update-crypto-prices`: Every 30 minutes (`crontab(minute='*/30')`)
- `generate-trading-signals`: Every 30 minutes (`crontab(minute='*/30')`)
- `update-sentiment-analysis`: Every 10 minutes (`crontab(minute='*/10')`)

**If multiple celery.py files exist:**
- Keep only `backend/ai_trading_engine/celery.py` as the main configuration
- Remove or rename conflicting files (e.g., `celery_database_signals.py` if not needed)

---

### Step 2.2: Verify Redis Broker Configuration
**Action:** Ensure Celery is configured to use Redis

**File to check:** `backend/ai_trading_engine/settings.py`

**Verify these settings:**
```python
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_RESULT_BACKEND = 'django-db'  # or 'redis://127.0.0.1:6379/0'
```

**If using memory backend:**
- Change `CELERY_BROKER_URL` from `'memory://'` to `'redis://127.0.0.1:6379/0'`
- Restart Celery worker and beat after changes

---

### Step 2.3: Verify Task Routes and Queues
**Action:** Ensure task routing is properly configured

**File to check:** `backend/ai_trading_engine/celery.py`

**Verify task_routes:**
```python
task_routes={
    'apps.data.tasks.*': {'queue': 'data', 'priority': 10},
    'apps.signals.tasks.*': {'queue': 'signals', 'priority': 8},
    'apps.sentiment.tasks.*': {'queue': 'sentiment', 'priority': 6},
}
```

**If queues are not defined:**
- Add queue definitions using `kombu.Queue`
- Ensure workers listen to all required queues

---

## Phase 3: Fix Data Collection Task (Every 30 Minutes)

### Step 3.1: Verify Data Update Task
**Action:** Check the task that updates crypto prices

**File:** `backend/apps/data/tasks.py`

**Task:** `update_crypto_prices()`

**Verify:**
1. Task is decorated with `@shared_task`
2. Task fetches data for all active crypto symbols
3. Task saves data to MarketData model
4. Task is scheduled in beat schedule as `update-crypto-prices`

**If task is not working:**
- Check task logs for errors
- Verify HistoricalDataManager is working
- Ensure Symbol objects have correct `symbol_type='CRYPTO'` and `is_active=True`

---

### Step 3.2: Test Data Update Task Manually
**Action:** Run the task manually to verify it works

```bash
cd backend
python manage.py shell
```

```python
from apps.data.tasks import update_crypto_prices
result = update_crypto_prices()
print(f"Task result: {result}")
```

**Expected Result:** Should return `True` and update market data

**If task fails:**
- Check error logs
- Verify API connections (if using external APIs)
- Verify database permissions
- Check HistoricalDataManager implementation

---

### Step 3.3: Verify Beat Schedule for Data Updates
**Action:** Ensure data update is scheduled every 30 minutes

**File:** `backend/ai_trading_engine/celery.py`

**Verify beat_schedule:**
```python
'update-crypto-prices': {
    'task': 'apps.data.tasks.update_crypto_prices',
    'schedule': crontab(minute='*/30'),  # Every 30 minutes
    'priority': 10,
},
```

**If schedule is incorrect:**
- Update to `crontab(minute='*/30')` for every 30 minutes
- Restart Celery Beat after changes

---

## Phase 4: Fix Signal Generation (10 Best Signals)

### Step 4.1: Update Signal Selection to 10 Signals
**Action:** Change signal selection from 5 to 10

**Files to modify:**
1. `backend/apps/signals/database_signal_service.py`
   - Method: `_select_best_signals()`
   - Change: `return sorted_signals[:5]` to `return sorted_signals[:10]`

2. `backend/apps/signals/enhanced_signal_generation_service.py`
   - Method: `_select_best_signals()`
   - Change: `return sorted_signals[:5]` to `return sorted_signals[:10]`

3. `backend/apps/signals/database_signal_service.py`
   - Method: `generate_best_signals_for_all_coins()`
   - Update docstring: "Generate the best 10 signals" (instead of 5)

**Code Change Example:**
```python
def _select_best_signals(self, all_signals: List[TradingSignal]) -> List[TradingSignal]:
    """Select the best 10 signals based on confidence and quality"""
    if not all_signals:
        return []
    
    sorted_signals = sorted(
        all_signals,
        key=lambda s: (
            s.confidence_score,
            s.risk_reward_ratio or 0,
            s.strength.priority if hasattr(s.strength, 'priority') else 0
        ),
        reverse=True
    )
    
    # Return top 10 signals (changed from 5)
    return sorted_signals[:10]
```

---

### Step 4.2: Integrate News Analysis into Signal Scoring
**Action:** Ensure news sentiment is included in signal scoring

**File to check:** `backend/apps/signals/services.py`

**Method:** `_calculate_news_score()`

**Verify:**
1. News score is calculated for each symbol
2. News score is included in final signal confidence calculation
3. News data is fetched from NewsArticle model or NewsAPIService

**If news integration is missing:**
- Add news score calculation in signal generation
- Fetch recent news articles for each symbol
- Calculate sentiment impact on signal confidence

**Code to add:**
```python
def _calculate_news_score(self, symbol: Symbol) -> float:
    """Calculate news impact score for signal"""
    try:
        from apps.sentiment.models import NewsArticle, CryptoMention
        from django.utils import timezone
        from datetime import timedelta
        
        # Get recent news mentions (last 24 hours)
        recent_mentions = CryptoMention.objects.filter(
            asset=symbol,
            news_article__published_at__gte=timezone.now() - timedelta(hours=24),
            mention_type='news'
        )
        
        if not recent_mentions.exists():
            return 0.5  # Neutral if no news
        
        # Calculate weighted sentiment score
        total_score = 0.0
        total_weight = 0.0
        
        for mention in recent_mentions:
            # Weight by confidence and recency
            hours_ago = (timezone.now() - mention.news_article.published_at).total_seconds() / 3600
            recency_weight = max(0, 1 - (hours_ago / 24))  # Decay over 24 hours
            weight = mention.confidence_score * recency_weight
            
            # Convert sentiment to score (-1 to 1, then normalize to 0-1)
            sentiment_value = mention.sentiment_score if mention.sentiment_label == 'POSITIVE' else -mention.sentiment_score
            normalized_sentiment = (sentiment_value + 1) / 2  # Convert -1 to 1 range to 0 to 1
            
            total_score += normalized_sentiment * weight
            total_weight += weight
        
        if total_weight > 0:
            return total_score / total_weight
        return 0.5
        
    except Exception as e:
        logger.error(f"Error calculating news score for {symbol.symbol}: {e}")
        return 0.5
```

---

### Step 4.3: Integrate Market Sentiment into Signal Scoring
**Action:** Ensure market sentiment is included in signal scoring

**File to check:** `backend/apps/signals/services.py`

**Method:** `_calculate_sentiment_score()`

**Verify:**
1. Sentiment score is calculated for each symbol
2. Sentiment score is included in final signal confidence calculation
3. Sentiment data is fetched from SentimentAggregate model

**If sentiment integration is missing:**
- Add sentiment score calculation in signal generation
- Fetch recent sentiment aggregates for each symbol
- Calculate sentiment impact on signal confidence

**Code to add:**
```python
def _calculate_sentiment_score(self, sentiment_data) -> float:
    """Calculate sentiment score from sentiment data"""
    try:
        if not sentiment_data:
            return 0.5  # Neutral if no sentiment data
        
        # Get aggregate sentiment score
        from apps.sentiment.models import SentimentAggregate
        from django.utils import timezone
        from datetime import timedelta
        
        recent_aggregate = SentimentAggregate.objects.filter(
            asset=sentiment_data.get('symbol'),
            timeframe='1h',
            created_at__gte=timezone.now() - timedelta(hours=2)
        ).order_by('-created_at').first()
        
        if recent_aggregate:
            # Convert sentiment score (-1 to 1) to normalized score (0 to 1)
            normalized_score = (recent_aggregate.aggregate_sentiment_score + 1) / 2
            return normalized_score
        
        return 0.5
        
    except Exception as e:
        logger.error(f"Error calculating sentiment score: {e}")
        return 0.5
```

---

### Step 4.4: Create Unified Signal Generation Task
**Action:** Create a new task that combines strategy, news, and sentiment

**New File:** `backend/apps/signals/unified_signal_task.py`

**Create task:**
```python
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from apps.signals.models import TradingSignal
from apps.signals.services import SignalGenerationService
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def generate_unified_signals_task(self):
    """
    Unified task to generate 10 best signals combining:
    - Strategy (technical analysis)
    - Fundamental news
    - Market sentiment
    """
    try:
        logger.info("Starting unified signal generation (strategy + news + sentiment)")
        
        signal_service = SignalGenerationService()
        active_symbols = Symbol.objects.filter(
            is_active=True,
            is_crypto_symbol=True
        )
        
        all_signals = []
        
        for symbol in active_symbols:
            try:
                # Generate signals using service (includes strategy, news, sentiment)
                signals = signal_service.generate_signals_for_symbol(symbol)
                all_signals.extend(signals)
                
            except Exception as e:
                logger.error(f"Error generating signals for {symbol.symbol}: {e}")
                continue
        
        # Select top 10 signals based on combined score
        best_signals = _select_top_10_signals(all_signals)
        
        # Save signals
        saved_count = 0
        for signal in best_signals:
            try:
                signal.save()
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving signal: {e}")
        
        logger.info(
            f"Unified signal generation completed: "
            f"{len(all_signals)} total signals, "
            f"{len(best_signals)} best signals selected, "
            f"{saved_count} signals saved"
        )
        
        return {
            'success': True,
            'total_signals': len(all_signals),
            'best_signals': len(best_signals),
            'saved_signals': saved_count
        }
        
    except Exception as e:
        logger.error(f"Unified signal generation failed: {e}")
        raise self.retry(countdown=60 * (2 ** self.request.retries))

def _select_top_10_signals(signals):
    """Select top 10 signals based on combined score"""
    if not signals:
        return []
    
    # Calculate combined score for each signal
    scored_signals = []
    for signal in signals:
        # Combine confidence, quality, news impact, sentiment impact
        combined_score = (
            signal.confidence_score * 0.4 +  # Strategy weight: 40%
            signal.quality_score * 0.3 +     # Quality weight: 30%
            getattr(signal, 'news_score', 0.5) * 0.15 +  # News weight: 15%
            getattr(signal, 'sentiment_score', 0.5) * 0.15  # Sentiment weight: 15%
        )
        scored_signals.append((combined_score, signal))
    
    # Sort by combined score
    scored_signals.sort(key=lambda x: x[0], reverse=True)
    
    # Return top 10
    return [signal for _, signal in scored_signals[:10]]
```

---

### Step 4.5: Update Beat Schedule for Unified Signal Generation
**Action:** Add unified signal generation to beat schedule

**File:** `backend/ai_trading_engine/celery.py`

**Add to beat_schedule:**
```python
'generate-unified-signals': {
    'task': 'apps.signals.unified_signal_task.generate_unified_signals_task',
    'schedule': crontab(minute='*/30'),  # Every 30 minutes, synchronized with data updates
    'priority': 9,
},
```

**Or replace existing signal generation task:**
```python
'generate-trading-signals': {
    'task': 'apps.signals.unified_signal_task.generate_unified_signals_task',
    'schedule': crontab(minute='*/30'),  # Every 30 minutes
    'priority': 8,
},
```

---

## Phase 5: Ensure News and Sentiment Data Collection

### Step 5.1: Verify News Collection Task
**Action:** Ensure news data is being collected

**File:** `backend/apps/sentiment/tasks.py`

**Task:** `collect_news_data()`

**Verify:**
1. Task is scheduled in beat schedule
2. Task fetches news from NewsAPIService
3. Task saves news articles to NewsArticle model
4. Task creates CryptoMention records for symbol mentions

**If news collection is not scheduled:**
- Add to beat schedule in `celery.py`:
```python
'collect-news-data': {
    'task': 'apps.sentiment.tasks.collect_news_data',
    'schedule': crontab(minute='*/15'),  # Every 15 minutes
    'priority': 6,
},
```

---

### Step 5.2: Verify Sentiment Collection Task
**Action:** Ensure sentiment data is being collected

**File:** `backend/apps/sentiment/tasks.py`

**Task:** `update_sentiment()` or `aggregate_sentiment_scores()`

**Verify:**
1. Task is scheduled in beat schedule
2. Task aggregates sentiment from social media and news
3. Task saves sentiment aggregates to SentimentAggregate model

**If sentiment collection is not scheduled:**
- Verify `update-sentiment-analysis` is in beat schedule
- Ensure it runs frequently enough (every 10-15 minutes)

---

### Step 5.3: Test News and Sentiment Integration
**Action:** Manually test news and sentiment data collection

```bash
cd backend
python manage.py shell
```

```python
from apps.sentiment.tasks import collect_news_data, aggregate_sentiment_scores

# Test news collection
news_result = collect_news_data()
print(f"News collection result: {news_result}")

# Test sentiment aggregation
sentiment_result = aggregate_sentiment_scores()
print(f"Sentiment aggregation result: {sentiment_result}")

# Check recent news
from apps.sentiment.models import NewsArticle, CryptoMention
from django.utils import timezone
from datetime import timedelta

recent_news = NewsArticle.objects.filter(
    published_at__gte=timezone.now() - timedelta(hours=24)
).count()
print(f"Recent news articles (last 24h): {recent_news}")

recent_mentions = CryptoMention.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=24)
).count()
print(f"Recent crypto mentions (last 24h): {recent_mentions}")
```

---

## Phase 6: Testing and Verification

### Step 6.1: Test Complete Automation Flow
**Action:** Run the complete automation flow manually

```bash
cd backend
python manage.py shell
```

```python
# Step 1: Update data
from apps.data.tasks import update_crypto_prices
data_result = update_crypto_prices()
print(f"Data update: {data_result}")

# Step 2: Collect news and sentiment
from apps.sentiment.tasks import collect_news_data, aggregate_sentiment_scores
news_result = collect_news_data()
sentiment_result = aggregate_sentiment_scores()
print(f"News: {news_result}, Sentiment: {sentiment_result}")

# Step 3: Generate signals
from apps.signals.unified_signal_task import generate_unified_signals_task
signal_result = generate_unified_signals_task()
print(f"Signal generation: {signal_result}")

# Step 4: Verify 10 best signals
from apps.signals.models import TradingSignal
from django.utils import timezone
from datetime import timedelta

recent_signals = TradingSignal.objects.filter(
    created_at__gte=timezone.now() - timedelta(minutes=5),
    is_valid=True
).order_by('-confidence_score')[:10]

print(f"\nTop 10 Signals Generated:")
for i, signal in enumerate(recent_signals, 1):
    print(f"{i}. {signal.symbol.symbol} - {signal.signal_type.name} - "
          f"Confidence: {signal.confidence_score:.2%}")
```

**Expected Result:**
- Data updated successfully
- News and sentiment collected
- 10 signals generated and saved
- Signals show combined scores from strategy, news, and sentiment

---

### Step 6.2: Monitor Celery Task Execution
**Action:** Monitor tasks as they execute automatically

**Option 1: Use Celery Flower (Web UI)**
```bash
cd backend
python -m celery -A ai_trading_engine flower --port=5555
```
Access at: http://localhost:5555

**Option 2: Check Task Results in Database**
```python
from django_celery_results.models import TaskResult
from django.utils import timezone
from datetime import timedelta

recent_tasks = TaskResult.objects.filter(
    date_created__gte=timezone.now() - timedelta(hours=1)
).order_by('-date_created')

for task in recent_tasks:
    print(f"{task.task_name}: {task.status} - {task.date_created}")
    if task.status == 'FAILURE':
        print(f"  Error: {task.traceback}")
```

---

### Step 6.3: Verify Scheduled Execution
**Action:** Wait 30 minutes and verify tasks executed automatically

**Check logs:**
- Celery worker logs: `logs/celery_worker.log`
- Celery beat logs: `logs/celery_beat.log`
- Django logs: `logs/django_server.log`

**Verify:**
1. Data update task ran at :00 and :30 minutes
2. Signal generation task ran at :00 and :30 minutes
3. News/sentiment tasks ran periodically
4. 10 signals were generated and saved

---

## Phase 7: Production Deployment

### Step 7.1: Create Startup Scripts
**Action:** Create scripts to start all services

**File:** `backend/start_automation.bat` (Windows)
```batch
@echo off
echo Starting Automation System...

REM Start Redis
start "Redis Server" redis-server.exe redis.conf

REM Wait for Redis to start
timeout /t 3

REM Start Celery Worker
start "Celery Worker" python -m celery -A ai_trading_engine worker --loglevel=info --pool=solo

REM Start Celery Beat
start "Celery Beat" python -m celery -A ai_trading_engine beat --loglevel=info

echo Automation system started!
echo - Redis: Running
echo - Celery Worker: Running
echo - Celery Beat: Running
pause
```

**File:** `backend/start_automation.sh` (Linux/Mac)
```bash
#!/bin/bash
echo "Starting Automation System..."

# Start Redis
redis-server redis.conf &

# Wait for Redis
sleep 3

# Start Celery Worker
celery -A ai_trading_engine worker --loglevel=info &

# Start Celery Beat
celery -A ai_trading_engine beat --loglevel=info &

echo "Automation system started!"
```

---

### Step 7.2: Create Monitoring Script
**Action:** Create script to monitor automation health

**File:** `backend/check_automation_health.py`
```python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
import django
django.setup()

from django.utils import timezone
from datetime import timedelta
from apps.data.models import MarketData
from apps.signals.models import TradingSignal
from apps.sentiment.models import NewsArticle, SentimentAggregate
import redis

def check_redis():
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        return True, "Redis is running"
    except Exception as e:
        return False, f"Redis error: {e}"

def check_recent_data():
    recent_data = MarketData.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=1)
    ).count()
    return recent_data > 0, f"Recent data records: {recent_data}"

def check_recent_signals():
    recent_signals = TradingSignal.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=1),
        is_valid=True
    ).count()
    return recent_signals >= 10, f"Recent signals: {recent_signals}"

def check_news_sentiment():
    recent_news = NewsArticle.objects.filter(
        published_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    recent_sentiment = SentimentAggregate.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    return recent_news > 0 and recent_sentiment > 0, \
           f"Recent news: {recent_news}, Recent sentiment: {recent_sentiment}"

def main():
    print("=" * 50)
    print("Automation System Health Check")
    print("=" * 50)
    
    checks = [
        ("Redis Connection", check_redis),
        ("Recent Data Updates", check_recent_data),
        ("Recent Signal Generation", check_recent_signals),
        ("News & Sentiment Data", check_news_sentiment),
    ]
    
    all_ok = True
    for name, check_func in checks:
        status, message = check_func()
        symbol = "✓" if status else "✗"
        print(f"{symbol} {name}: {message}")
        if not status:
            all_ok = False
    
    print("=" * 50)
    if all_ok:
        print("✓ All systems operational")
    else:
        print("✗ Some issues detected - check logs")
    print("=" * 50)

if __name__ == "__main__":
    main()
```

---

### Step 7.3: Set Up Logging
**Action:** Ensure proper logging for debugging

**File:** `backend/ai_trading_engine/settings.py`

**Verify logging configuration:**
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/automation.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'apps.data.tasks': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
        'apps.signals.tasks': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
        'apps.sentiment.tasks': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
    },
}
```

---

## Phase 8: Troubleshooting Common Issues

### Issue 1: Tasks Not Executing
**Symptoms:** Tasks scheduled but not running

**Solutions:**
1. Verify Celery Beat is running: `Get-Process python | Where-Object {$_.CommandLine -like "*beat*"}`
2. Check beat schedule: `python -m celery -A ai_trading_engine inspect scheduled`
3. Verify Redis connection: `redis-cli ping`
4. Check task registration: `python -m celery -A ai_trading_engine inspect registered`
5. Review beat logs for errors

---

### Issue 2: Redis Connection Errors
**Symptoms:** "Connection refused" or "Cannot connect to Redis"

**Solutions:**
1. Start Redis: `redis-server.exe redis.conf`
2. Verify Redis is listening: `Test-NetConnection -ComputerName localhost -Port 6379`
3. Check Redis configuration in settings.py
4. Verify Redis URL format: `redis://127.0.0.1:6379/0`

---

### Issue 3: Only 5 Signals Generated Instead of 10
**Symptoms:** System generates 5 signals instead of 10

**Solutions:**
1. Verify `_select_best_signals()` returns `[:10]` not `[:5]`
2. Check all signal generation services are updated
3. Verify signal filtering isn't removing too many signals
4. Check confidence thresholds aren't too high

---

### Issue 4: News/Sentiment Not Integrated
**Symptoms:** Signals don't include news or sentiment scores

**Solutions:**
1. Verify news collection task is running
2. Check NewsArticle and CryptoMention models have data
3. Verify `_calculate_news_score()` and `_calculate_sentiment_score()` are called
4. Check signal model has news_score and sentiment_score fields (or add them)

---

### Issue 5: Data Not Updating Every 30 Minutes
**Symptoms:** Market data is stale

**Solutions:**
1. Verify `update-crypto-prices` task is in beat schedule
2. Check schedule is `crontab(minute='*/30')`
3. Verify task is executing: Check TaskResult model
4. Check HistoricalDataManager is working correctly
5. Verify API connections (if using external APIs)

---

## Summary Checklist

Before considering the automation system fixed, verify:

- [ ] Redis is running and accessible
- [ ] Celery worker is running and connected to Redis
- [ ] Celery Beat is running and scheduling tasks
- [ ] Data update task executes every 30 minutes
- [ ] Signal generation task executes every 30 minutes
- [ ] 10 best signals are generated (not 5)
- [ ] Signals include strategy analysis
- [ ] Signals include news sentiment
- [ ] Signals include market sentiment
- [ ] News data is being collected
- [ ] Sentiment data is being aggregated
- [ ] All tasks are logging properly
- [ ] Health check script passes all checks

---

## Next Steps After Fix

1. **Monitor for 24 hours** to ensure stability
2. **Review generated signals** to verify quality
3. **Adjust scoring weights** if needed (strategy 40%, quality 30%, news 15%, sentiment 15%)
4. **Set up alerts** for task failures
5. **Document any customizations** made

---

## Notes

- All file paths are relative to the `backend/` directory
- Windows commands use PowerShell syntax
- Linux/Mac commands use bash syntax
- Replace `ai_trading_engine` with your actual Django project name if different
- Adjust Redis/Celery paths based on your installation

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-27  
**Status:** Ready for Implementation

