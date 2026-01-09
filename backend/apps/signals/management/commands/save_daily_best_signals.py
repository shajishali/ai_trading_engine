"""
Management command to save daily best signals at end of day

This command:
1. Finds all signals created today
2. Calculates combined score (confidence + quality + risk/reward)
3. Selects top 20 best signals
4. Marks them as best_of_day with the date and rank

Usage:
    python manage.py save_daily_best_signals
    python manage.py save_daily_best_signals --date 2024-01-15  # For a specific date
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, date, timedelta
from apps.signals.models import TradingSignal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Save daily best signals for today or a specific date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to process (YYYY-MM-DD format). Defaults to today.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Number of best signals to save (default: 20)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        # Parse date
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD')
                )
                return
        else:
            target_date = timezone.now().date()
        
        limit = options['limit']
        dry_run = options['dry_run']
        
        self.stdout.write(
            self.style.SUCCESS(f'Processing best signals for {target_date}...')
        )
        
        # Clear existing best_of_day marks for this date (if re-running)
        if not dry_run:
            TradingSignal.objects.filter(
                best_of_day_date=target_date
            ).update(
                is_best_of_day=False,
                best_of_day_date=None,
                best_of_day_rank=None
            )
        
        # Get all signals created on the target date
        start_datetime = timezone.make_aware(
            datetime.combine(target_date, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(target_date, datetime.max.time())
        )
        
        signals = TradingSignal.objects.filter(
            created_at__gte=start_datetime,
            created_at__lte=end_datetime,
            is_valid=True
        ).select_related('symbol', 'signal_type')
        
        signal_count = signals.count()
        self.stdout.write(f'Found {signal_count} signals for {target_date}')
        
        if signal_count == 0:
            self.stdout.write(
                self.style.WARNING(f'No signals found for {target_date}')
            )
            return
        
        # Calculate combined score for each signal
        scored_signals = []
        for signal in signals:
            # Combined score: confidence (50%) + quality (30%) + risk/reward (20%)
            confidence = signal.confidence_score or 0
            quality = signal.quality_score or 0
            risk_reward = signal.risk_reward_ratio or 0
            
            combined_score = (confidence * 0.5) + (quality * 0.3) + (risk_reward * 0.2)
            
            scored_signals.append({
                'signal': signal,
                'score': combined_score,
                'confidence': confidence,
                'quality': quality,
                'risk_reward': risk_reward
            })
        
        # Sort by combined score (descending)
        scored_signals.sort(key=lambda x: x['score'], reverse=True)
        
        # Get top N signals
        best_signals = scored_signals[:limit]
        
        self.stdout.write(
            self.style.SUCCESS(f'Selected {len(best_signals)} best signals:')
        )
        
        # Display and mark best signals
        for rank, signal_data in enumerate(best_signals, 1):
            signal = signal_data['signal']
            score = signal_data['score']
            
            self.stdout.write(
                f"  {rank}. {signal.symbol.symbol} - "
                f"Score: {score:.4f} "
                f"(Conf: {signal_data['confidence']:.2f}, "
                f"Qual: {signal_data['quality']:.2f}, "
                f"R/R: {signal_data['risk_reward']:.2f})"
            )
            
            if not dry_run:
                signal.is_best_of_day = True
                signal.best_of_day_date = target_date
                signal.best_of_day_rank = rank
                signal.save(update_fields=['is_best_of_day', 'best_of_day_date', 'best_of_day_rank'])
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nDRY RUN - No changes made. Remove --dry-run to apply changes.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully marked {len(best_signals)} signals as best of day for {target_date}'
                )
            )
            
            logger.info(
                f'Saved {len(best_signals)} daily best signals for {target_date}'
            )

