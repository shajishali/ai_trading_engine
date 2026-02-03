#!/usr/bin/env python
"""
Production diagnostic: run each step separately and share the output.
Usage: python manage.py shell < step_N.txt  (or paste one block at a time in Django shell)
Or: cd ~/trading-engine/backend && python manage.py shell -c "..."
"""
# Step 1: How many signals were created in the last hour vs last 24h?
def step1_signals_last_hour_vs_24h():
    from django.utils import timezone
    from datetime import timedelta
    from apps.signals.models import TradingSignal
    now = timezone.now()
    last_hour = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)
    in_last_hour = TradingSignal.objects.filter(created_at__gte=last_hour, is_valid=True).count()
    in_last_24h = TradingSignal.objects.filter(created_at__gte=last_24h, created_at__lt=last_hour, is_valid=True).count()
    print("=== Step 1: Signals by time window (UTC) ===")
    print(f"Now (UTC): {now}")
    print(f"Signals created in LAST HOUR (last 60 min): {in_last_hour}")
    print(f"Signals created in 1–24 HOURS AGO: {in_last_24h}")
    print("(Page shows top 5 from last hour; if <5, fills from 1–24h. If last hour=0, you see same 5.)")

# Step 2: How many symbols already have a signal created TODAY? (these are excluded next run)
def step2_symbols_with_signal_today():
    from django.utils import timezone
    from apps.signals.models import TradingSignal
    from apps.trading.models import Symbol
    today = timezone.now().date()
    symbol_ids_today = set(TradingSignal.objects.filter(created_at__date=today).values_list("symbol_id", flat=True).distinct())
    names = list(Symbol.objects.filter(id__in=symbol_ids_today).values_list("symbol", flat=True))[:25]
    print("=== Step 2: Coins that already have a signal created TODAY (excluded next hour) ===")
    print(f"Count: {len(symbol_ids_today)}")
    print(f"Examples: {names}")

# Step 3: Last 10 signals in DB (id, symbol, created_at) — confirm new ones each hour
def step3_last_10_signals():
    from apps.signals.models import TradingSignal
    from django.utils import timezone
    signals = TradingSignal.objects.select_related("symbol", "signal_type").order_by("-created_at")[:10]
    print("=== Step 3: Last 10 signals in DB (created_at UTC) ===")
    for s in signals:
        print(f"  id={s.id} symbol={s.symbol.symbol} type={s.signal_type.name} created_at={s.created_at}")

# Step 4: Is Celery beat schedule correct? (run on server: celery -A ai_trading_engine inspect scheduled 2>/dev/null || true)
# Step 5: Run hourly task manually and see result (run: python manage.py shell -c "from apps.signals.tasks import generate_signals_for_all_symbols; print(generate_signals_for_all_symbols())")

if __name__ == "__main__":
    import os, sys, django
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_trading_engine.settings")
    django.setup()
    step1_signals_last_hour_vs_24h()
    print()
    step2_symbols_with_signal_today()
    print()
    step3_last_10_signals()
