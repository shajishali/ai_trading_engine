"""
Phase 2 Verification Script
Verify that Celery configuration is correct after Phase 2 fixes
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')

import django
django.setup()

from celery import current_app

print("="*60)
print("PHASE 2: CELERY CONFIGURATION VERIFICATION")
print("="*60)

# Check Redis broker
broker_url = current_app.conf.broker_url
print(f"\n✓ Redis Broker: {broker_url}")
if 'redis://' in broker_url:
    print("  Status: Correctly configured")
else:
    print("  ⚠ WARNING: Not using Redis broker")

# Check result backend
result_backend = current_app.conf.result_backend
print(f"\n✓ Result Backend: {result_backend}")

# Check beat schedule
beat_schedule = current_app.conf.beat_schedule
print(f"\n✓ Beat Schedule: {len(beat_schedule)} tasks configured")

print("\nScheduled Tasks:")
required_tasks = {
    'update-crypto-prices': 'Every 30 minutes',
    'generate-trading-signals': 'Every 30 minutes',
    'update-sentiment-analysis': 'Every 10 minutes',
    'collect-news-data': 'Every 15 minutes',
    'collect-social-media-data': 'Every 20 minutes',
}

for task_name, expected_freq in required_tasks.items():
    if task_name in beat_schedule:
        schedule = beat_schedule[task_name].get('schedule', 'N/A')
        print(f"  ✓ {task_name}: {schedule} (Expected: {expected_freq})")
    else:
        print(f"  ✗ {task_name}: MISSING (Expected: {expected_freq})")

# Check task routes
task_routes = current_app.conf.task_routes
print(f"\n✓ Task Routes: {len(task_routes)} routes configured")
for pattern, route in task_routes.items():
    print(f"  - {pattern}: queue={route.get('queue', 'default')}, priority={route.get('priority', 0)}")

# Check queues
task_queues = current_app.conf.task_queues
if task_queues:
    print(f"\n✓ Task Queues: {len(task_queues)} queues defined")
    for queue in task_queues:
        print(f"  - {queue.name}")
else:
    print("\n⚠ WARNING: No queues defined")

# Verify settings.py doesn't have conflicting schedule
try:
    from django.conf import settings as django_settings
    if hasattr(django_settings, 'CELERY_BEAT_SCHEDULE') and django_settings.CELERY_BEAT_SCHEDULE:
        print("\n⚠ WARNING: CELERY_BEAT_SCHEDULE found in settings.py")
        print("  This may override celery.py configuration")
    else:
        print("\n✓ No conflicting CELERY_BEAT_SCHEDULE in settings.py")
except:
    pass

print("\n" + "="*60)
print("VERIFICATION COMPLETE")
print("="*60)
print("\nNext Steps:")
print("1. Restart Celery Beat to pick up new configuration")
print("2. Verify tasks are being scheduled correctly")
print("3. Monitor task execution")


