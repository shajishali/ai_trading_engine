from django.core.management.base import BaseCommand
from apps.trading.models import Symbol
from apps.data.historical_data_manager import get_historical_data_manager


class Command(BaseCommand):
    help = "Compute data quality metrics (completeness, gaps) for symbols/timeframes"

    def add_arguments(self, parser):
        parser.add_argument('--symbol', type=str, help='Specific symbol (e.g., BTC). If omitted, checks a batch of active symbols.')
        parser.add_argument('--timeframe', type=str, default='1h', choices=['1m','5m','15m','1h','4h','1d'])
        parser.add_argument('--days', type=int, default=365, help='Window size to check (days)')
        parser.add_argument('--limit', type=int, default=20, help='How many symbols to check when symbol not given')

    def handle(self, *args, **options):
        symbol_arg = options.get('symbol')
        timeframe = options.get('timeframe')
        days = options.get('days')
        limit = options.get('limit')

        manager = get_historical_data_manager()

        if symbol_arg:
            symbols = Symbol.objects.filter(symbol=symbol_arg.upper(), symbol_type='CRYPTO', is_active=True)
        else:
            symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True).order_by('symbol')[:limit]

        for sym in symbols:
            report = manager.check_data_quality(sym, timeframe=timeframe, days_back=days)
            completeness = report.get('completeness_percentage', 0)
            self.stdout.write(self.style.SUCCESS(
                f"{sym.symbol} {timeframe}: completeness={completeness}% | gaps={report.get('gaps_count', 0)}"
            ))









































