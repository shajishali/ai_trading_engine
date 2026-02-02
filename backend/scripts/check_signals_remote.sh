#!/bin/bash
# Quick command to check signals on remote server
cd /home/ubuntu/trading-engine/backend
source venv/bin/activate
python manage.py shell << 'EOF'
from apps.signals.models import TradingSignal
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("RECENT VALID SIGNALS (Last 10)")
print("=" * 80)
signals = TradingSignal.objects.filter(is_valid=True).select_related('symbol', 'signal_type').order_by('-created_at')[:10]

print(f"{'ID':<8} {'Symbol':<12} {'Type':<10} {'Created At':<25} {'Analyzed At':<25}")
print("-" * 80)

for s in signals:
    created = s.created_at.strftime('%Y-%m-%d %H:%M:%S') if s.created_at else 'N/A'
    analyzed = s.analyzed_at.strftime('%Y-%m-%d %H:%M:%S') if s.analyzed_at else 'N/A'
    print(f"{s.id:<8} {s.symbol.symbol:<12} {s.signal_type.name:<10} {created:<25} {analyzed:<25}")

print()
print("=" * 80)
print("CHECKING FOR DUPLICATES (same symbol + type)")
print("=" * 80)
from django.db.models import Count
duplicates = TradingSignal.objects.values('symbol__symbol', 'signal_type__name').annotate(count=Count('id')).filter(count__gt=1).order_by('-count')[:5]
if duplicates:
    for dup in duplicates:
        print(f"{dup['symbol__symbol']} + {dup['signal_type__name']}: {dup['count']} signals")
else:
    print("No duplicates found")

EOF

