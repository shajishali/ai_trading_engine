import os
import sys
import django


def main():
    # Ensure project root on sys.path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
    django.setup()

    from apps.signals.models import TradingSignal
    from apps.trading.models import Symbol

    symbol_code = os.environ.get('SYMBOL', 'PEPE')
    try:
        symbol = Symbol.objects.filter(symbol__iexact=symbol_code).first()
        if not symbol:
            print(f"NO_SYMBOL {symbol_code}")
            return
        qs = TradingSignal.objects.filter(symbol=symbol).order_by('-created_at')[:5]
        print(f"COUNT {qs.count()}")
        for ts in qs:
            entry = f"{float(ts.entry_price):.6f}" if ts.entry_price is not None else "n/a"
            sl = f"{float(ts.stop_loss):.6f}" if ts.stop_loss is not None else "n/a"
            tp = f"{float(ts.target_price):.6f}" if ts.target_price is not None else "n/a"
            st = ts.signal_type.name if ts.signal_type else "UNKNOWN"
            print(ts.id, entry, sl, tp, st, ts.created_at.isoformat())
    except Exception as e:
        print("ERROR", str(e))


if __name__ == '__main__':
    main()


