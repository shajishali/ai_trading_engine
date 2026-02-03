"""
Comprehensive command to populate historical OHLCV data for all crypto coins from 2021 to 2025
"""
from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone
from django.db import transaction
from datetime import datetime, timezone as dt_timezone
import logging

from apps.trading.models import Symbol
from apps.data.models import MarketData, HistoricalDataRange, DataSource
from apps.data.historical_data_manager import get_historical_data_manager
from apps.data.services import CryptoDataIngestionService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Populate historical OHLCV data for all crypto coins from 2021 to 2025"

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-year',
            type=int,
            default=2021,
            help='Start year (default: 2021)'
        )
        parser.add_argument(
            '--end-year',
            type=int,
            default=None,
            help='End year (default: current year/now)'
        )
        parser.add_argument(
            '--timeframes',
            type=str,
            nargs='+',
            default=['1h', '4h', '1d'],
            help='Timeframes to fetch (default: 1h 4h 1d)'
        )
        parser.add_argument(
            '--max-coins',
            type=int,
            default=None,
            help='Maximum number of coins to process (default: all)'
        )
        parser.add_argument(
            '--skip-sync',
            action='store_true',
            help='Skip syncing coins from CoinGecko (use existing coins)'
        )
        parser.add_argument(
            '--symbol',
            type=str,
            default=None,
            help='Process only a specific symbol (e.g., BTC)'
        )

    def handle(self, *args, **options):
        start_year = options.get('start_year', 2021)
        end_year = options.get('end_year')
        timeframes = options.get('timeframes', ['1h', '4h', '1d'])
        max_coins = options.get('max_coins')
        skip_sync = options.get('skip_sync', False)
        symbol_arg = options.get('symbol')

        # Build date range - default to now if end_year not specified
        start_date = datetime(start_year, 1, 1, tzinfo=dt_timezone.utc)
        if end_year:
            end_date = datetime(end_year, 12, 31, 23, 59, 59, tzinfo=dt_timezone.utc)
        else:
            end_date = dj_timezone.now()
            end_year = end_date.year
        
        # Cap end date to today if future
        today = dj_timezone.now()
        if end_date > today:
            end_date = today
            end_year = today.year

        self.stdout.write(self.style.SUCCESS(
            f"=== Populating Historical OHLCV Data for All Crypto Coins ==="
        ))
        self.stdout.write(f"Period: {start_year}-01-01 to {end_date.strftime('%Y-%m-%d %H:%M:%S')} (NOW)")
        self.stdout.write(f"Timeframes: {', '.join(timeframes)}")
        self.stdout.write("")

        # Step 1: Sync all coins from CoinGecko (if not skipped)
        if not skip_sync:
            self.stdout.write(self.style.WARNING("Step 1: Syncing all crypto coins from CoinGecko..."))
            try:
                ingestion_service = CryptoDataIngestionService()
                max_coins_to_sync = max_coins if max_coins else 1000
                success = ingestion_service.sync_crypto_symbols(
                    limit=None,
                    max_coins=max_coins_to_sync
                )
                if success:
                    self.stdout.write(self.style.SUCCESS("[+] Successfully synced coins from CoinGecko"))
                else:
                    self.stdout.write(self.style.ERROR("[-] Failed to sync coins from CoinGecko"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[-] Error syncing coins: {e}"))
                return
        else:
            self.stdout.write(self.style.WARNING("Skipping coin sync (using existing coins)"))

        # Step 2: Get all active crypto symbols
        if symbol_arg:
            symbols = Symbol.objects.filter(
                symbol=symbol_arg.upper(),
                symbol_type='CRYPTO',
                is_active=True
            )
        else:
            symbols = Symbol.objects.filter(
                symbol_type='CRYPTO',
                is_active=True,
                is_crypto_symbol=True
            ).order_by('market_cap_rank', 'symbol')

        if max_coins:
            symbols = symbols[:max_coins]

        total_symbols = symbols.count()
        self.stdout.write(self.style.SUCCESS(
            f"Step 2: Found {total_symbols} active crypto symbols to process"
        ))
        self.stdout.write("")

        # Step 3: Populate historical data for each symbol
        self.stdout.write(self.style.WARNING("Step 3: Populating historical OHLCV data..."))
        self.stdout.write("")

        # Date range already built above

        manager = get_historical_data_manager()
        
        # Statistics
        stats = {
            'total_symbols': total_symbols,
            'successful_symbols': 0,
            'failed_symbols': 0,
            'skipped_symbols': 0,
            'total_records': 0,
            'errors': []
        }

        # Process each symbol
        for idx, symbol in enumerate(symbols, start=1):
            symbol_name = symbol.symbol
            self.stdout.write(
                f"[{idx}/{total_symbols}] Processing {symbol_name} ({symbol.name})..."
            )

            symbol_success = False
            symbol_records = 0

            # Process each timeframe
            for timeframe in timeframes:
                try:
                    self.stdout.write(f"  → Fetching {timeframe} data...")
                    
                    # Check if data already exists for this symbol/timeframe
                    existing_range = HistoricalDataRange.objects.filter(
                        symbol=symbol,
                        timeframe=timeframe
                    ).first()

                    if existing_range:
                        # Check if we already have data for the requested period
                        if (existing_range.earliest_date <= start_date and
                            existing_range.latest_date >= end_date):
                            self.stdout.write(
                                self.style.WARNING(
                                    f"    ⚠ Data already exists: "
                                    f"{existing_range.earliest_date.date()} to "
                                    f"{existing_range.latest_date.date()} "
                                    f"({existing_range.total_records} records)"
                                )
                            )
                            continue

                    # Fetch historical data
                    success = manager.fetch_complete_historical_data(
                        symbol=symbol,
                        timeframe=timeframe,
                        start=start_date,
                        end=end_date
                    )

                    if success:
                        # Get count of records for this symbol/timeframe
                        records_count = MarketData.objects.filter(
                            symbol=symbol,
                            timeframe=timeframe,
                            timestamp__gte=start_date,
                            timestamp__lte=end_date
                        ).count()
                        symbol_records += records_count
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    [+] {timeframe}: {records_count} records"
                            )
                        )
                        symbol_success = True
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"    [-] {timeframe}: Failed to fetch data")
                        )
                        stats['errors'].append(
                            f"{symbol_name} {timeframe}: Failed to fetch data"
                        )

                except Exception as e:
                    error_msg = f"{symbol_name} {timeframe}: {str(e)}"
                    self.stdout.write(self.style.ERROR(f"    [-] Error: {e}"))
                    stats['errors'].append(error_msg)
                    logger.error(f"Error processing {symbol_name} {timeframe}: {e}")

            # Update statistics
            if symbol_success:
                stats['successful_symbols'] += 1
                stats['total_records'] += symbol_records
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [+] Completed {symbol_name}: {symbol_records} total records"
                    )
                )
            else:
                stats['failed_symbols'] += 1
                self.stdout.write(
                    self.style.ERROR(f"  [-] Failed {symbol_name}: No data fetched")
                )

            self.stdout.write("")  # Empty line between symbols

            # Progress update every 10 symbols
            if idx % 10 == 0:
                self.stdout.write(self.style.WARNING(
                    f"Progress: {idx}/{total_symbols} symbols processed "
                    f"({stats['successful_symbols']} successful, "
                    f"{stats['failed_symbols']} failed)"
                ))
                self.stdout.write("")

        # Final summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Summary ==="))
        self.stdout.write(f"Total symbols: {stats['total_symbols']}")
        self.stdout.write(
            self.style.SUCCESS(f"Successful: {stats['successful_symbols']}")
        )
        self.stdout.write(
            self.style.ERROR(f"Failed: {stats['failed_symbols']}")
        )
        self.stdout.write(f"Total records: {stats['total_records']:,}")

        if stats['errors']:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Errors:"))
            for error in stats['errors'][:20]:  # Show first 20 errors
                self.stdout.write(f"  - {error}")
            if len(stats['errors']) > 20:
                self.stdout.write(
                    f"  ... and {len(stats['errors']) - 20} more errors"
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Completed ==="))

