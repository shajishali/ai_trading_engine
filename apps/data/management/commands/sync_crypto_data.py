from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

from apps.data.services import CryptoDataIngestionService, TechnicalAnalysisService
from apps.data.models import DataSyncLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync crypto market data and calculate technical indicators'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols-only',
            action='store_true',
            help='Only sync symbols, skip market data',
        )
        parser.add_argument(
            '--indicators-only',
            action='store_true',
            help='Only calculate indicators, skip data sync',
        )
        parser.add_argument(
            '--symbol',
            type=str,
            help='Sync data for specific symbol only',
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        
        try:
            if options['indicators_only']:
                self.calculate_indicators(options)
            else:
                self.sync_data(options)
                
        except Exception as e:
            logger.error(f"Error in sync_crypto_data command: {e}")
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )
        finally:
            end_time = timezone.now()
            duration = end_time - start_time
            self.stdout.write(
                self.style.SUCCESS(f'Command completed in {duration}')
            )

    def sync_data(self, options):
        """Sync crypto data"""
        service = CryptoDataIngestionService()
        
        # Sync symbols
        if not options['symbol']:
            self.stdout.write('Syncing crypto symbols...')
            symbols_success = service.sync_crypto_symbols()
            
            if symbols_success:
                self.stdout.write(
                    self.style.SUCCESS('Successfully synced crypto symbols')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Failed to sync crypto symbols')
                )
        
        # Sync market data
        if not options['symbols_only']:
            if options['symbol']:
                symbols = [options['symbol'].upper()]
            else:
                symbols = list(service.data_source.symbol_set.filter(
                    symbol_type='CRYPTO',
                    is_active=True
                ).values_list('symbol', flat=True)[:10])
            
            self.stdout.write(f'Syncing market data for {len(symbols)} symbols...')
            
            success_count = 0
            for symbol_name in symbols:
                try:
                    symbol = service.data_source.symbol_set.get(symbol=symbol_name)
                    if service.sync_market_data(symbol):
                        success_count += 1
                        self.stdout.write(f'✓ Synced {symbol_name}')
                    else:
                        self.stdout.write(f'✗ Failed to sync {symbol_name}')
                except Exception as e:
                    self.stdout.write(f'✗ Error syncing {symbol_name}: {e}')
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully synced market data for {success_count}/{len(symbols)} symbols')
            )

    def calculate_indicators(self, options):
        """Calculate technical indicators"""
        service = TechnicalAnalysisService()
        
        if options['symbol']:
            symbols = [options['symbol'].upper()]
        else:
            symbols = list(service.data_source.symbol_set.filter(
                symbol_type='CRYPTO',
                is_active=True
            ).values_list('symbol', flat=True)[:10])
        
        self.stdout.write(f'Calculating indicators for {len(symbols)} symbols...')
        
        success_count = 0
        for symbol_name in symbols:
            try:
                symbol = service.data_source.symbol_set.get(symbol=symbol_name)
                if service.calculate_all_indicators(symbol):
                    success_count += 1
                    self.stdout.write(f'✓ Calculated indicators for {symbol_name}')
                else:
                    self.stdout.write(f'✗ Failed to calculate indicators for {symbol_name}')
            except Exception as e:
                self.stdout.write(f'✗ Error calculating indicators for {symbol_name}: {e}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully calculated indicators for {success_count}/{len(symbols)} symbols')
        )




