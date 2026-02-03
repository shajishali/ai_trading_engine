"""
Load symbols and market data for all Binance USDT perpetual futures coins.

Step 1: Sync Symbol table from Binance (creates/updates symbols, optionally deactivates non-futures).
Step 2: Fetch OHLCV market data from Binance Futures API for each symbol (1h, 4h, 1d).

Usage:
    python manage.py load_binance_futures_data
    python manage.py load_binance_futures_data --symbols-only
    python manage.py load_binance_futures_data --days 30
    python manage.py load_binance_futures_data --max-coins 50
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, timezone as dt_timezone
import logging

from apps.trading.models import Symbol
from apps.trading.binance_futures_service import sync_binance_futures_symbols, get_binance_usdt_futures_base_assets
from apps.data.historical_data_manager import get_historical_data_manager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load Binance USDT perpetual futures symbols and their market data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols-only',
            action='store_true',
            help='Only sync symbols from Binance, do not fetch market data',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days of market data to fetch (default: 90)',
        )
        parser.add_argument(
            '--timeframes',
            type=str,
            nargs='+',
            default=['1h', '4h', '1d'],
            help='Timeframes to fetch (default: 1h 4h 1d)',
        )
        parser.add_argument(
            '--max-coins',
            type=int,
            default=None,
            help='Max number of coins to load data for (default: all)',
        )
        parser.add_argument(
            '--no-deactivate',
            action='store_true',
            help='Do not deactivate non-Binance-futures symbols (keep existing symbols active)',
        )

    def handle(self, *args, **options):
        # Step 1: Sync Binance futures symbols
        self.stdout.write(self.style.SUCCESS('Step 1: Syncing Binance USDT perpetual futures symbols...'))
        try:
            result = sync_binance_futures_symbols(
                deactivate_non_futures=not options['no_deactivate'],
                force_refresh=True,
            )
            if result.get('status') != 'success':
                self.stdout.write(self.style.ERROR(f"Sync failed: {result.get('error', 'Unknown')}"))
                return
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Synced: {result.get('futures_base_assets', 0)} futures, "
                    f"created={result.get('created', 0)}, updated={result.get('updated', 0)}, "
                    f"deactivated={result.get('deactivated', 0)}"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Step 1 failed: {e}"))
            return

        if options['symbols_only']:
            self.stdout.write(self.style.SUCCESS('Symbols-only mode: skipping market data.'))
            return

        # Step 2: Load market data for Binance futures symbols
        symbols = Symbol.objects.filter(
            symbol_type='CRYPTO',
            is_active=True,
            is_crypto_symbol=True,
        )
        valid = get_binance_usdt_futures_base_assets(force_refresh=True)
        if valid:
            symbols = symbols.filter(symbol__in=valid)
        symbols = symbols.order_by('symbol')
        if options['max_coins']:
            symbols = symbols[: options['max_coins']]
        total = symbols.count()

        self.stdout.write(
            self.style.SUCCESS(f'Step 2: Loading market data for {total} Binance futures coins ({options["days"]} days)...')
        )
        timeframes = options['timeframes']
        end_date = timezone.now()
        start_date = end_date - timedelta(days=options['days'])

        manager = get_historical_data_manager()
        ok = 0
        fail = 0
        for idx, symbol in enumerate(symbols, start=1):
            self.stdout.write(f'  [{idx}/{total}] {symbol.symbol}...')
            symbol_ok = False
            for tf in timeframes:
                try:
                    if manager.fetch_complete_historical_data(
                        symbol, timeframe=tf, start=start_date, end=end_date
                    ):
                        symbol_ok = True
                except Exception as e:
                    logger.warning(f'{symbol.symbol} {tf}: {e}')
            if symbol_ok:
                ok += 1
            else:
                fail += 1

        self.stdout.write(self.style.SUCCESS(f'Done. OK: {ok}, Failed: {fail}'))
