"""
Django management command to start the live data service
"""

from django.core.management.base import BaseCommand
from apps.data.live_data_service import start_live_data_service, stop_live_data_service
import signal
import sys


class Command(BaseCommand):
    help = 'Start the live data service for real-time market data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--stop',
            action='store_true',
            help='Stop the live data service',
        )
    
    def handle(self, *args, **options):
        if options['stop']:
            self.stdout.write(
                self.style.WARNING('Stopping live data service...')
            )
            stop_live_data_service()
            self.stdout.write(
                self.style.SUCCESS('Live data service stopped')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Starting live data service...')
            )
            
            # Set up signal handlers for graceful shutdown
            def signal_handler(sig, frame):
                self.stdout.write(
                    self.style.WARNING('\nShutting down live data service...')
                )
                stop_live_data_service()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            try:
                # Start the service
                start_live_data_service()
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING('\nLive data service interrupted')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error in live data service: {e}')
                )
                sys.exit(1)






