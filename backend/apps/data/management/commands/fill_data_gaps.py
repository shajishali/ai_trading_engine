from django.core.management.base import BaseCommand
from apps.trading.models import Symbol
from apps.data.historical_data_manager import get_historical_data_manager


class Command(BaseCommand):
    help = "Fill detected gaps in historical data for symbols/timeframes"

    def add_arguments(self, parser):
        parser.add_argument('--symbol', type=str, help='Specific symbol (e.g., BTC). If omitted, processes a batch of active symbols.')
        parser.add_argument('--timeframe', type=str, default='1h', choices=['1m','5m','15m','1h','4h','1d'])
        parser.add_argument('--limit', type=int, default=20, help='How many symbols to process when symbol not given')

    def handle(self, *args, **options):
        symbol_arg = options.get('symbol')
        timeframe = options.get('timeframe')
        limit = options.get('limit')

        manager = get_historical_data_manager()

        if symbol_arg:
            symbols = Symbol.objects.filter(symbol=symbol_arg.upper(), symbol_type='CRYPTO', is_active=True)
        else:
            symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True).order_by('symbol')[:limit]

        for sym in symbols:
            self.stdout.write(f"Filling gaps for {sym.symbol} {timeframe}...")
            ok = manager.fill_data_gaps(sym, timeframe=timeframe)
            self.stdout.write(self.style.SUCCESS(f"  {'OK' if ok else 'No action'}"))









































