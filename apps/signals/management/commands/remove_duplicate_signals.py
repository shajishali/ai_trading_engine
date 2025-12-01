"""
Django Management Command: Remove Duplicate Signals

This command identifies and removes duplicate trading signals from the database.
It can be run in dry-run mode to preview changes before actually removing duplicates.

Usage:
    python manage.py remove_duplicate_signals --dry-run
    python manage.py remove_duplicate_signals --symbol AAVEUSDT
    python manage.py remove_duplicate_signals --days-old 30
    python manage.py remove_duplicate_signals --tolerance 0.02
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from apps.signals.duplicate_signal_removal_service import duplicate_removal_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Remove duplicate trading signals from the database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without actually removing duplicates',
        )
        parser.add_argument(
            '--symbol',
            type=str,
            help='Filter by specific symbol (e.g., AAVEUSDT)',
        )
        parser.add_argument(
            '--days-old',
            type=int,
            help='Only process duplicates older than specified days',
        )
        parser.add_argument(
            '--tolerance',
            type=float,
            default=0.01,
            help='Price tolerance percentage for duplicate detection (default: 0.01 = 1%%)',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for filtering (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for filtering (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--statistics-only',
            action='store_true',
            help='Only show duplicate statistics without removing anything',
        )
        parser.add_argument(
            '--cleanup-old',
            action='store_true',
            help='Clean up duplicates older than 30 days',
        )
    
    def handle(self, *args, **options):
        try:
            self.stdout.write(
                self.style.SUCCESS('Starting duplicate signal removal process...')
            )
            
            # Parse date arguments
            start_date = None
            end_date = None
            
            if options['start_date']:
                try:
                    start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
                    start_date = timezone.make_aware(start_date)
                except ValueError:
                    raise CommandError('Invalid start date format. Use YYYY-MM-DD')
            
            if options['end_date']:
                try:
                    end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
                    end_date = timezone.make_aware(end_date)
                except ValueError:
                    raise CommandError('Invalid end date format. Use YYYY-MM-DD')
            
            # Handle cleanup old duplicates
            if options['cleanup_old']:
                days_old = options.get('days_old', 30)
                dry_run = options['dry_run']
                
                self.stdout.write(f'Cleaning up duplicates older than {days_old} days...')
                result = duplicate_removal_service.cleanup_old_duplicates(
                    days_old=days_old,
                    dry_run=dry_run
                )
                
                self._display_results(result, dry_run)
                return
            
            # Handle statistics only
            if options['statistics_only']:
                self.stdout.write('Generating duplicate statistics...')
                result = duplicate_removal_service.get_duplicate_statistics(
                    symbol=options['symbol']
                )
                
                self._display_statistics(result)
                return
            
            # Main duplicate removal process
            dry_run = options['dry_run']
            symbol = options['symbol']
            tolerance = options['tolerance']
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('DRY RUN MODE - No changes will be made')
                )
            
            # Display parameters
            self.stdout.write(f'Tolerance: {tolerance * 100}%')
            if symbol:
                self.stdout.write(f'Symbol filter: {symbol}')
            if start_date:
                self.stdout.write(f'Start date: {start_date.strftime("%Y-%m-%d")}')
            if end_date:
                self.stdout.write(f'End date: {end_date.strftime("%Y-%m-%d")}')
            
            # Run duplicate removal
            result = duplicate_removal_service.remove_duplicates(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                dry_run=dry_run,
                tolerance_percentage=tolerance
            )
            
            self._display_results(result, dry_run)
            
        except Exception as e:
            logger.error(f"Error in remove_duplicate_signals command: {e}")
            raise CommandError(f'Command failed: {e}')
    
    def _display_results(self, result, dry_run):
        """Display the results of duplicate removal"""
        if not result['success']:
            self.stdout.write(
                self.style.ERROR(f'Error: {result.get("error", "Unknown error")}')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('=== DRY RUN RESULTS ===')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('=== REMOVAL RESULTS ===')
            )
        
        # Basic statistics
        self.stdout.write(f'Total signals analyzed: {result.get("total_signals_analyzed", "N/A")}')
        self.stdout.write(f'Duplicate groups found: {result.get("duplicate_groups_found", "N/A")}')
        self.stdout.write(f'Total duplicate signals: {result.get("total_duplicate_signals", "N/A")}')
        
        if dry_run:
            self.stdout.write(f'Signals that would be removed: {result.get("removed_count", 0)}')
            self.stdout.write(f'Signals that would be kept: {result.get("kept_count", 0)}')
        else:
            self.stdout.write(f'Signals removed: {result.get("removed_count", 0)}')
            self.stdout.write(f'Signals kept: {result.get("kept_count", 0)}')
        
        # Duplicate percentage
        stats = result.get('statistics', {})
        if stats:
            duplicate_percentage = stats.get('duplicate_percentage', 0)
            self.stdout.write(f'Duplicate percentage: {duplicate_percentage:.2f}%')
        
        # Show some example duplicate groups
        duplicate_groups = result.get('duplicate_groups', [])
        if duplicate_groups:
            self.stdout.write('\n=== EXAMPLE DUPLICATE GROUPS ===')
            
            for i, group in enumerate(duplicate_groups[:5]):  # Show first 5 groups
                self.stdout.write(f'\nGroup {i + 1}:')
                self.stdout.write(f'  Symbol: {group["signals"][0].symbol.symbol}')
                self.stdout.write(f'  Signal Type: {group["signals"][0].signal_type.name if group["signals"][0].signal_type else "N/A"}')
                self.stdout.write(f'  Strength: {group["signals"][0].strength}')
                self.stdout.write(f'  Entry Price: ${group["signals"][0].entry_price}')
                self.stdout.write(f'  Duplicate Count: {group["count"]}')
                
                # Show date range
                dates = [s.created_at for s in group["signals"]]
                earliest = min(dates)
                latest = max(dates)
                self.stdout.write(f'  Date Range: {earliest.strftime("%Y-%m-%d %H:%M")} to {latest.strftime("%Y-%m-%d %H:%M")}')
                
                # Show which signal would be kept
                if not dry_run:
                    kept_signal = group["earliest_signal"]
                    self.stdout.write(f'  Kept Signal ID: {kept_signal.id} (earliest)')
                else:
                    self.stdout.write(f'  Would Keep: Earliest signal (ID: {group["earliest_signal"].id})')
            
            if len(duplicate_groups) > 5:
                self.stdout.write(f'\n... and {len(duplicate_groups) - 5} more groups')
        
        # Final message
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nThis was a dry run. Use --dry-run=False to actually remove duplicates.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nDuplicate removal completed successfully!')
            )
    
    def _display_statistics(self, result):
        """Display duplicate statistics"""
        if not result['success']:
            self.stdout.write(
                self.style.ERROR(f'Error: {result.get("error", "Unknown error")}')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS('=== DUPLICATE STATISTICS ===')
        )
        
        self.stdout.write(f'Total signals: {result.get("total_signals", "N/A")}')
        self.stdout.write(f'Total duplicates: {result.get("total_duplicates", "N/A")}')
        self.stdout.write(f'Duplicate percentage: {result.get("duplicate_percentage", 0):.2f}%')
        self.stdout.write(f'Duplicate groups: {result.get("duplicate_groups_count", "N/A")}')
        
        # Symbols with duplicates
        symbols_with_duplicates = result.get('symbols_with_duplicates', [])
        if symbols_with_duplicates:
            self.stdout.write(f'Symbols with duplicates: {", ".join(symbols_with_duplicates)}')
        
        # Signal types with duplicates
        signal_types_with_duplicates = result.get('signal_types_with_duplicates', [])
        if signal_types_with_duplicates:
            self.stdout.write(f'Signal types with duplicates: {", ".join(signal_types_with_duplicates)}')
        
        # Time analysis
        avg_time_span = result.get('avg_duplicate_time_span_hours', 0)
        max_time_span = result.get('max_duplicate_time_span_hours', 0)
        min_time_span = result.get('min_duplicate_time_span_hours', 0)
        
        if avg_time_span > 0:
            self.stdout.write(f'Average duplicate time span: {avg_time_span:.2f} hours')
            self.stdout.write(f'Max duplicate time span: {max_time_span:.2f} hours')
            self.stdout.write(f'Min duplicate time span: {min_time_span:.2f} hours')
