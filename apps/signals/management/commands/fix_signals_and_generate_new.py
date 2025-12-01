"""
Management command to fix signal generation issues

This command:
1. Clears existing signals with invalid data
2. Generates new signals using improved logic
3. Ensures proper price handling and deduplication
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import models
from apps.trading.models import Symbol
from apps.signals.models import TradingSignal
from apps.signals.improved_signal_generation_service import improved_signal_service
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix signals by clearing invalid data and generating new improved signals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            help='Comma-separated list of symbol codes to process (optional)',
        )
        parser.add_argument(
            '--clear-bad-signals',
            action='store_true',
            help='Clear existing signals with invalid price data',
        )
        parser.add_argument(
            '--generate-new',
            action='store_true',
            help='Generate new improved signals',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting signal fix process...')
        
        # Get symbols to process
        if options['symbols']:
            symbol_codes = [s.strip().upper() for s in options['symbols'].split(',')]
            symbols = Symbol.objects.filter(symbol__in=symbol_codes, is_source_active=True)
            self.stdout.write(f'Processing {symbols.count()} specified symbols...')
        else:
            # Process major cryptocurrencies only to avoid too many signals
            major_symbols = [
                'BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOGE', 'MATIC', 'DOT', 'AVAX',
                'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'XLM', 'ADAUSDT', 'AVAXUSDT', 
                'BTCUSDT', 'ETHUSDT', 'AAVEUSDT', 'LINKUSDT'
            ]
            symbols = Symbol.objects.filter(symbol__in=major_symbols, is_active=True)
            self.stdout.write(f'Processing {symbols.count()} major cryptocurrency symbols...')
        
        if symbols.count() == 0:
            self.stdout.write(self.style.ERROR('No symbols found to process'))
            return
        
        # Clear bad signals if requested
        if options['clear_bad_signals']:
            self.clear_bad_signals(options['dry_run'])
        
        # Generate new signals if requested
        if options['generate_new']:
            self.generate_improved_signals(symbols, options['dry_run'])
        
        self.stdout.write(self.style.SUCCESS('Signal fix process completed!'))

    def clear_bad_signals(self, dry_run=False):
        """Clear signals with invalid price data"""
        self.stdout.write('\nClearing signals with invalid price data...')
        
        try:
            # Find signals with invalid data
            invalid_signals = TradingSignal.objects.filter(
                # Signals with zero or negative entry prices
                models.Q(entry_price__lte=0) |
                models.Q(entry_price__isnull=True) |
                # Signals with impossible targets (target < 0 or target too far from entry)
                models.Q(target_price__lte=0) |
                models.Q(stop_loss__lte=0) |
                models.Q(target_price__isnull=True) |
                models.Q(stop_loss__isnull=True) |
                # Signals where target is in wrong direction relative to signal type
                models.Q(entry_price__gt=models.F('target_price'), signal_type__name__in=['BUY', 'STRONG_BUY']) |
                models.Q(entry_price__lt=models.F('target_price'), signal_type__name__in=['SELL', 'STRONG_SELL'])
            )
            
            count = invalid_signals.count()
            
            if count > 0:
                if dry_run:
                    self.stdout.write(f'DRY RUN: Would delete {count} invalid signals')
                    
                    # Show examples of bad signals
                    examples = invalid_signals[:5]
                    for signal in examples:
                        self.stdout.write(f'  - {signal.symbol.symbol}: Entry=${signal.entry_price}, Target=${signal.target_price}, Stop=${signal.stop_loss}')
                else:
                    deleted_count = invalid_signals.delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} invalid signals'))
            else:
                self.stdout.write('No invalid signals found')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error clearing bad signals: {e}'))

    def generate_improved_signals(self, symbols, dry_run=False):
        """Generate new improved signals"""
        self.stdout.write(f'\nGenerating improved signals...')
        
        total_generated = 0
        
        for symbol in symbols:
            try:
                self.stdout.write(f'Processing {symbol.symbol}...', ending=' ')
                
                if dry_run:
                    # Just check if we can get a price
                    current_price = improved_signal_service._get_reliable_current_price(symbol)
                    if current_price:
                        self.stdout.write(f'Has price ${current_price:,}')
                    else:
                        self.stdout.write('No price data available')
                else:
                    # Generate actual signals
                    signals = improved_signal_service.generate_signals_for_symbol(symbol)
                    
                    if signals:
                        total_generated += len(signals)
                        self.stdout.write(f'Generated {len(signals)} signals')
                    else:
                        self.stdout.write('No signals generated')
                        
            except Exception as e:
                self.stdout.write(f'Error: {e}')
        
        if not dry_run:
            self.stdout.write(f'\nTotal signals generated: {total_generated}')
        else:
            self.stdout.write('\nDRY RUN completed - no signals were actually generated')

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            help='Comma-separated list of symbol codes to process')
        parser.add_argument(
            '--clear-bad-signals',
            action='store_true',
            help='Clear existing signals with invalid price data')
        parser.add_argument(
            '--generate-new',
            action='store_true',
            help='Generate new improved signals')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes')
        parser.add_argument(
            '--full-rebuild',
            action='store_true',
            help='Clear bad signals AND generate new ones (equivalent to both --clear-bad-signals --generate-new)')

    def handle(self, *args, **options):
        if options['full_rebuild']:
            options['clear_bad_signals'] = True
            options['generate_new'] = True
        
        if not any([options['clear_bad_signals'], options['generate_new']]):
            raise CommandError('You must specify at least one action: --clear-bad-signals, --generate-new, or --full-rebuild')
        
        self.stdout.write('Starting improved signal generation process...')
        
        # Get symbols to process
        if options['symbols']:
            symbol_codes = [s.strip().upper() for s in options['symbols'].split(',')]
            symbols = Symbol.objects.filter(symbol__in=symbol_codes, is_active=True)
            self.stdout.write(f'Processing {symbols.count()} specified symbols...')
        else:
            # Process major cryptocurrencies only
            major_symbols = [
                'BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOGE', 'MATIC', 'DOT', 'AVAX',
                'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'XLM', 'ADAUSDT', 'AVAXUSDT', 
                'BTCUSDT', 'ETHUSDT', 'AAVEUSDT', 'LINKUSDT'
            ]
            symbols = Symbol.objects.filter(symbol__in=major_symbols, is_active=True)
            self.stdout.write(f'Processing {symbols.count()} major cryptocurrency symbols...')
        
        if symbols.count() == 0:
            self.stdout.write(self.style.ERROR('No symbols found to process'))
            return
        
        # Clear bad signals if requested
        if options['clear_bad_signals']:
            self.clear_bad_signals(options['dry_run'])
        
        # Generate new signals if requested
        if options['generate_new']:
            self.generate_improved_signals(symbols, options['dry_run'])
        
        self.stdout.write(self.style.SUCCESS('Process completed successfully!'))
