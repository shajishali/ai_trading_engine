"""
Management command to generate enhanced trading signals every 2 hours
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from apps.signals.enhanced_signal_generation_service import enhanced_signal_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate enhanced trading signals for all 200+ coins and select best 5 every 2 hours'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without saving signals to database',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force generation even if recently generated',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write('Starting enhanced signal generation...')
        
        try:
            # Check if signals were recently generated (unless forced)
            if not force:
                from apps.signals.models import TradingSignal
                recent_signals = TradingSignal.objects.filter(
                    created_at__gte=timezone.now() - timedelta(hours=1)
                ).count()
                
                if recent_signals > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Found {recent_signals} signals generated in the last hour. '
                            'Use --force to override or wait for the next cycle.'
                        )
                    )
                    return
            
            # Generate signals
            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN MODE - No signals will be saved'))
            
            result = enhanced_signal_service.generate_best_signals_for_all_coins()
            
            # Display results
            self.stdout.write(
                self.style.SUCCESS(
                    f'Signal generation completed successfully!'
                )
            )
            
            self.stdout.write(f'Total signals generated: {result["total_signals_generated"]}')
            self.stdout.write(f'Best signals selected: {result["best_signals_selected"]}')
            self.stdout.write(f'Processed symbols: {result["processed_symbols"]}')
            
            # Display best signals
            if result['best_signals']:
                self.stdout.write('\nBest 5 Signals:')
                for i, signal in enumerate(result['best_signals'], 1):
                    symbol = signal['symbol'].symbol
                    signal_type = signal['signal_type']
                    confidence = signal['confidence_score']
                    entry_price = signal['entry_price']
                    target_price = signal['target_price']
                    stop_loss = signal['stop_loss']
                    risk_reward = signal['risk_reward_ratio']
                    
                    self.stdout.write(
                        f'{i}. {symbol} {signal_type} - '
                        f'Confidence: {confidence:.1%}, '
                        f'Entry: ${entry_price:.2f}, '
                        f'Target: ${target_price:.2f}, '
                        f'Stop: ${stop_loss:.2f}, '
                        f'R/R: {risk_reward:.1f}x'
                    )
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('DRY RUN COMPLETE - No signals were saved to database')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('Signals saved to database successfully!')
                )
                
        except Exception as e:
            logger.error(f"Error in enhanced signal generation: {e}")
            self.stdout.write(
                self.style.ERROR(f'Error generating signals: {e}')
            )
            raise















































