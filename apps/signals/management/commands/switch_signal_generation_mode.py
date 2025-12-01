"""
Management command to switch between database and live API signal generation modes
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.conf import settings


class Command(BaseCommand):
    help = 'Switch between database and live API signal generation modes'

    def add_arguments(self, parser):
        parser.add_argument(
            'mode',
            choices=['database', 'live_api', 'hybrid', 'auto'],
            help='Signal generation mode to use'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force the mode change even if system health is poor'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=3600,
            help='Duration in seconds to keep the mode active (default: 1 hour)'
        )

    def handle(self, *args, **options):
        mode = options['mode']
        force = options['force']
        duration = options['duration']
        
        self.stdout.write(f"Switching signal generation mode to: {mode}")
        
        try:
            if mode == 'database':
                success = self._switch_to_database_mode(force, duration)
            elif mode == 'live_api':
                success = self._switch_to_live_api_mode(force, duration)
            elif mode == 'hybrid':
                success = self._switch_to_hybrid_mode(force, duration)
            elif mode == 'auto':
                success = self._switch_to_auto_mode()
            else:
                raise CommandError(f"Invalid mode: {mode}")
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully switched to {mode} mode")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Mode switch to {mode} may not be optimal")
                )
                
        except Exception as e:
            raise CommandError(f"Error switching mode: {e}")

    def _switch_to_database_mode(self, force: bool, duration: int) -> bool:
        """Switch to database-only signal generation"""
        try:
            # Check database health
            from apps.signals.database_data_utils import get_database_health_status
            health = get_database_health_status()
            
            if not force and health['status'] == 'CRITICAL':
                self.stdout.write(
                    self.style.WARNING(
                        f"Database health is {health['status']}. "
                        "Use --force to override or consider hybrid mode."
                    )
                )
                return False
            
            # Set database mode
            cache.set('signal_generation_mode', 'database', duration)
            cache.set('force_database_mode', True, duration)
            cache.delete('force_live_api_mode')
            
            self.stdout.write(f"Database mode enabled for {duration} seconds")
            self.stdout.write(f"Database health: {health['status']}")
            
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error switching to database mode: {e}"))
            return False

    def _switch_to_live_api_mode(self, force: bool, duration: int) -> bool:
        """Switch to live API signal generation"""
        try:
            # Set live API mode
            cache.set('signal_generation_mode', 'live_api', duration)
            cache.set('force_live_api_mode', True, duration)
            cache.delete('force_database_mode')
            
            self.stdout.write(f"Live API mode enabled for {duration} seconds")
            self.stdout.write("Note: This mode depends on external API availability")
            
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error switching to live API mode: {e}"))
            return False

    def _switch_to_hybrid_mode(self, force: bool, duration: int) -> bool:
        """Switch to hybrid signal generation (database + live API fallback)"""
        try:
            # Set hybrid mode
            cache.set('signal_generation_mode', 'hybrid', duration)
            cache.delete('force_database_mode')
            cache.delete('force_live_api_mode')
            
            self.stdout.write(f"Hybrid mode enabled for {duration} seconds")
            self.stdout.write("This mode uses database signals with live API fallback")
            
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error switching to hybrid mode: {e}"))
            return False

    def _switch_to_auto_mode(self) -> bool:
        """Switch to automatic mode selection"""
        try:
            # Clear all forced modes
            cache.delete('signal_generation_mode')
            cache.delete('force_database_mode')
            cache.delete('force_live_api_mode')
            
            self.stdout.write("Automatic mode selection enabled")
            self.stdout.write("System will automatically choose the best mode based on health")
            
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error switching to auto mode: {e}"))
            return False

    def _get_current_mode(self) -> str:
        """Get current signal generation mode"""
        try:
            mode = cache.get('signal_generation_mode', 'auto')
            return mode
        except:
            return 'unknown'

    def _show_system_status(self):
        """Show current system status"""
        try:
            from apps.signals.database_data_utils import get_database_health_status
            from apps.signals.database_signal_tasks import database_signal_health_check
            
            # Get database health
            db_health = get_database_health_status()
            
            # Get signal health
            signal_health = database_signal_health_check()
            
            self.stdout.write("\n=== System Status ===")
            self.stdout.write(f"Current mode: {self._get_current_mode()}")
            self.stdout.write(f"Database health: {db_health.get('status', 'unknown')}")
            self.stdout.write(f"Signal health: {signal_health.get('health_status', 'unknown')}")
            self.stdout.write(f"Active symbols: {db_health.get('active_symbols', 0)}")
            self.stdout.write(f"Latest data age: {db_health.get('latest_data_age_hours', 0):.1f} hours")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error getting system status: {e}"))














