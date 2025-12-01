"""
Phase 6, Step 6.3: Verify Scheduled Execution
This script verifies that tasks are executing automatically according to schedule.
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta, datetime
from django_celery_results.models import TaskResult
from apps.data.models import MarketData
from apps.signals.models import TradingSignal
from apps.sentiment.models import NewsArticle, SentimentAggregate

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def check_log_files():
    """Check if log files exist and show recent entries"""
    print_section("Log Files Check")
    
    log_files = {
        'Celery Worker': 'logs/celery_worker.log',
        'Celery Beat': 'logs/celery_beat.log',
        'Django Server': 'logs/django_server.log',
    }
    
    base_dir = Path(__file__).parent
    
    for log_name, log_path in log_files.items():
        full_path = base_dir / log_path
        if full_path.exists():
            print(f"✓ {log_name}: {log_path} exists")
            try:
                # Get file size and modification time
                stat = full_path.stat()
                size_kb = stat.st_size / 1024
                mod_time = datetime.fromtimestamp(stat.st_mtime)
                print(f"  Size: {size_kb:.1f} KB")
                print(f"  Last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Show last few lines if file is not too large
                if stat.st_size < 1024 * 1024:  # Less than 1MB
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        if lines:
                            print(f"  Last 3 lines:")
                            for line in lines[-3:]:
                                print(f"    {line.strip()[:100]}")
            except Exception as e:
                print(f"  ⚠ Could not read log file: {e}")
        else:
            print(f"⚠ {log_name}: {log_path} not found")
            print(f"  (This is normal if logging to console or not configured)")

def verify_data_updates():
    """Verify data update task ran at :00 and :30 minutes"""
    print_section("Data Update Task Verification")
    
    try:
        now = timezone.now()
        current_minute = now.minute
        
        # Check last hour for updates at :00 and :30
        hour_ago = now - timedelta(hours=1)
        
        # Check for updates around :00 minutes
        minute_0_updates = MarketData.objects.filter(
            timestamp__gte=hour_ago,
            timestamp__minute=0
        ).count()
        
        # Check for updates around :30 minutes
        minute_30_updates = MarketData.objects.filter(
            timestamp__gte=hour_ago,
            timestamp__minute=30
        ).count()
        
        # Check recent updates (last 30 minutes)
        recent_updates = MarketData.objects.filter(
            timestamp__gte=now - timedelta(minutes=30)
        ).count()
        
        print(f"Data updates in last hour:")
        print(f"  Around :00 minutes: {minute_0_updates} records")
        print(f"  Around :30 minutes: {minute_30_updates} records")
        print(f"  Last 30 minutes: {recent_updates} records")
        
        # Check task execution
        task_name = 'apps.data.tasks.update_crypto_prices'
        recent_tasks = TaskResult.objects.filter(
            task_name=task_name,
            date_created__gte=hour_ago
        ).order_by('-date_created')
        
        if recent_tasks.exists():
            print(f"\nTask executions in last hour: {recent_tasks.count()}")
            for task in recent_tasks[:5]:
                status_icon = "✓" if task.status == "SUCCESS" else "✗"
                print(f"  {status_icon} {task.date_created.strftime('%H:%M:%S')} - {task.status}")
        else:
            print(f"\n⚠ No task executions found in last hour")
            print(f"  Task name: {task_name}")
        
        if recent_updates > 0 or recent_tasks.exists():
            print("\n✓ Data update task appears to be running")
        else:
            print("\n⚠ Data update task may not be running automatically")
            
    except Exception as e:
        print(f"✗ Error verifying data updates: {e}")
        import traceback
        traceback.print_exc()

def verify_signal_generation():
    """Verify signal generation task ran at :00 and :30 minutes"""
    print_section("Signal Generation Task Verification")
    
    try:
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        
        # Check recent signals
        recent_signals = TradingSignal.objects.filter(
            created_at__gte=hour_ago,
            is_valid=True
        ).order_by('-created_at')
        
        signal_count = recent_signals.count()
        print(f"Signals generated in last hour: {signal_count}")
        
        if signal_count > 0:
            print(f"\nRecent signals (last 10):")
            for signal in recent_signals[:10]:
                print(f"  {signal.created_at.strftime('%H:%M:%S')} - "
                      f"{signal.symbol.symbol} - "
                      f"Confidence: {signal.confidence_score:.2%}")
        
        # Check task execution
        task_name = 'apps.signals.unified_signal_task.generate_unified_signals_task'
        recent_tasks = TaskResult.objects.filter(
            task_name=task_name,
            date_created__gte=hour_ago
        ).order_by('-date_created')
        
        if recent_tasks.exists():
            print(f"\nTask executions in last hour: {recent_tasks.count()}")
            for task in recent_tasks[:5]:
                status_icon = "✓" if task.status == "SUCCESS" else "✗"
                print(f"  {status_icon} {task.date_created.strftime('%H:%M:%S')} - {task.status}")
        else:
            print(f"\n⚠ No task executions found in last hour")
            print(f"  Task name: {task_name}")
        
        # Check if we have 10 signals (or close to it)
        if signal_count >= 10:
            print(f"\n✓ Signal generation: SUCCESS ({signal_count} signals found)")
        elif signal_count > 0:
            print(f"\n⚠ Signal generation: Partial ({signal_count} signals, expected ~10)")
        else:
            print(f"\n⚠ Signal generation: No signals found")
            
    except Exception as e:
        print(f"✗ Error verifying signal generation: {e}")
        import traceback
        traceback.print_exc()

def verify_news_sentiment_tasks():
    """Verify news and sentiment tasks ran periodically"""
    print_section("News and Sentiment Tasks Verification")
    
    try:
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        
        # Check news collection
        news_task = 'apps.sentiment.tasks.collect_news_data'
        news_tasks = TaskResult.objects.filter(
            task_name=news_task,
            date_created__gte=hour_ago
        ).order_by('-date_created')
        
        print(f"News collection task (last hour):")
        if news_tasks.exists():
            print(f"  Executions: {news_tasks.count()}")
            for task in news_tasks[:3]:
                status_icon = "✓" if task.status == "SUCCESS" else "✗"
                print(f"  {status_icon} {task.date_created.strftime('%H:%M:%S')} - {task.status}")
        else:
            print(f"  ⚠ No executions found")
        
        # Check sentiment aggregation
        sentiment_task = 'apps.sentiment.tasks.aggregate_sentiment_scores'
        sentiment_tasks = TaskResult.objects.filter(
            task_name=sentiment_task,
            date_created__gte=hour_ago
        ).order_by('-date_created')
        
        print(f"\nSentiment aggregation task (last hour):")
        if sentiment_tasks.exists():
            print(f"  Executions: {sentiment_tasks.count()}")
            for task in sentiment_tasks[:3]:
                status_icon = "✓" if task.status == "SUCCESS" else "✗"
                print(f"  {status_icon} {task.date_created.strftime('%H:%M:%S')} - {task.status}")
        else:
            print(f"  ⚠ No executions found")
        
        # Check data
        recent_news = NewsArticle.objects.filter(
            published_at__gte=now - timedelta(hours=24)
        ).count()
        recent_sentiment = SentimentAggregate.objects.filter(
            created_at__gte=hour_ago
        ).count()
        
        print(f"\nData collected:")
        print(f"  News articles (last 24h): {recent_news}")
        print(f"  Sentiment aggregates (last hour): {recent_sentiment}")
        
        if news_tasks.exists() or sentiment_tasks.exists():
            print("\n✓ News and sentiment tasks appear to be running")
        else:
            print("\n⚠ News and sentiment tasks may not be running automatically")
            
    except Exception as e:
        print(f"✗ Error verifying news/sentiment tasks: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main verification function"""
    print("\n" + "=" * 70)
    print("PHASE 6: SCHEDULED EXECUTION VERIFICATION")
    print("=" * 70)
    print("\nThis script verifies that tasks are executing automatically.")
    print("Note: For accurate results, wait 30+ minutes after starting Celery Beat.")
    
    # Check log files
    check_log_files()
    
    # Verify data updates
    verify_data_updates()
    
    # Verify signal generation
    verify_signal_generation()
    
    # Verify news and sentiment tasks
    verify_news_sentiment_tasks()
    
    print("\n" + "=" * 70)
    print("Verification complete.")
    print("\nTo see real-time execution:")
    print("  1. Ensure Celery Beat is running")
    print("  2. Ensure Celery Worker is running")
    print("  3. Wait 30+ minutes")
    print("  4. Run this script again")
    print("=" * 70)

if __name__ == "__main__":
    main()





















