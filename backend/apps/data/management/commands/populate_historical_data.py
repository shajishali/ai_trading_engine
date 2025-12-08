from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone
from datetime import datetime, timezone as dt_timezone

from apps.trading.models import Symbol
from apps.data.historical_data_manager import get_historical_data_manager


class Command(BaseCommand):
    help = "Backfill historical OHLCV data for symbols and timeframes"

    def add_arguments(self, parser):
        parser.add_argument('--symbol', type=str, help='Specific symbol (e.g., BTC). If omitted, all active crypto symbols are processed.')
        parser.add_argument('--timeframe', type=str, default='1h', choices=['1m','5m','15m','1h','4h','1d'], help='Timeframe to fetch')
        parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD). Default: 2020-01-01')
        parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD). Default: now')
        parser.add_argument('--start-datetime', type=str, help='Start datetime (YYYY-MM-DD HH:MM) UTC')
        parser.add_argument('--end-datetime', type=str, help='End datetime (YYYY-MM-DD HH:MM) UTC')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of symbols to process')

    def handle(self, *args, **options):
        symbol_arg = options.get('symbol')
        timeframe = options.get('timeframe')
        start_str = options.get('start')
        end_str = options.get('end')
        start_dt_str = options.get('start_datetime')
        end_dt_str = options.get('end_datetime')
        limit = options.get('limit')

        # Build start/end datetimes in UTC
        if start_dt_str:
            start_dt = datetime.strptime(start_dt_str, '%Y-%m-%d %H:%M').replace(tzinfo=dt_timezone.utc)
        elif start_str:
            start_dt = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=dt_timezone.utc)
        else:
            start_dt = datetime(2020, 1, 1, tzinfo=dt_timezone.utc)

        if end_dt_str:
            end_dt = datetime.strptime(end_dt_str, '%Y-%m-%d %H:%M').replace(tzinfo=dt_timezone.utc)
        elif end_str:
            end_dt = datetime.strptime(end_str, '%Y-%m-%d').replace(tzinfo=dt_timezone.utc)
        else:
            end_dt = dj_timezone.now()

        manager = get_historical_data_manager()

        if symbol_arg:
            symbols = Symbol.objects.filter(symbol=symbol_arg.upper(), symbol_type='CRYPTO', is_active=True)
        else:
            symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True).order_by('symbol')
            if limit and limit > 0:
                symbols = symbols[:limit]

        total = symbols.count()
        self.stdout.write(self.style.SUCCESS(f"Starting backfill: {total} symbols, timeframe={timeframe}, {start_dt.date()}→{end_dt.date()}"))

        success_count = 0
        for idx, sym in enumerate(symbols, start=1):
            self.stdout.write(f"[{idx}/{total}] {sym.symbol} ...")
            try:
                ok = manager.fetch_complete_historical_data(sym, timeframe=timeframe, start=start_dt, end=end_dt)
                if ok:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✔ Done"))
                else:
                    self.stdout.write(self.style.ERROR(f"  ✖ Failed"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✖ Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Completed: {success_count}/{total} symbols processed successfully"))









































