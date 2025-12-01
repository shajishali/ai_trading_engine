"""
Start Monitoring Services Management Command

This command starts all monitoring and alerting services for Phase 7B.3
including application monitoring, error alerting, and uptime monitoring.
"""

import time
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.services import (
    ApplicationMonitoringService,
    ErrorAlertingService,
    UptimeMonitoringService
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Start all monitoring and alerting services for Phase 7B.3'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run monitoring services in daemon mode (continuous)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Monitoring interval in seconds (default: 30)'
        )
        parser.add_argument(
            '--services',
            nargs='+',
            choices=['application', 'error', 'uptime', 'all'],
            default=['all'],
            help='Which monitoring services to start (default: all)'
        )
        
    def handle(self, *args, **options):
        try:
            self.stdout.write(
                self.style.SUCCESS('🚀 Starting AI Trading Engine Monitoring Services (Phase 7B.3)')
            )
            
            # Initialize monitoring services
            services = {}
            
            if 'all' in options['services'] or 'application' in options['services']:
                self.stdout.write('📊 Initializing Application Monitoring Service...')
                services['application'] = ApplicationMonitoringService()
                services['application'].metrics_interval = options['interval']
                
            if 'all' in options['services'] or 'error' in options['services']:
                self.stdout.write('🚨 Initializing Error Alerting Service...')
                services['error'] = ErrorAlertingService()
                
            if 'all' in options['services'] or 'uptime' in options['services']:
                self.stdout.write('⏱️ Initializing Uptime Monitoring Service...')
                services['uptime'] = UptimeMonitoringService()
                services['uptime'].check_interval = options['interval']
                
            # Start monitoring services
            self.stdout.write('\n🔄 Starting monitoring services...')
            
            for service_name, service in services.items():
                try:
                    if hasattr(service, 'start_monitoring'):
                        service.start_monitoring()
                        self.stdout.write(
                            self.style.SUCCESS(f'✅ {service_name.title()} Monitoring Service started successfully')
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'⚠️ {service_name.title()} service does not have start_monitoring method')
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Failed to start {service_name.title()} Monitoring Service: {e}')
                    )
                    
            # Display service status
            self.stdout.write('\n📋 Monitoring Services Status:')
            for service_name, service in services.items():
                if hasattr(service, 'monitoring_active'):
                    status = '🟢 ACTIVE' if service.monitoring_active else '🔴 INACTIVE'
                else:
                    status = '🟡 UNKNOWN'
                self.stdout.write(f'  {service_name.title()}: {status}')
                
            # Display configuration
            self.stdout.write(f'\n⚙️ Configuration:')
            self.stdout.write(f'  Monitoring Interval: {options["interval"]} seconds')
            self.stdout.write(f'  Daemon Mode: {"Yes" if options["daemon"] else "No"}')
            self.stdout.write(f'  Services: {", ".join(options["services"])}')
            
            # Health check endpoints
            self.stdout.write(f'\n🔗 Health Check Endpoints:')
            self.stdout.write(f'  Main Health: /health/')
            self.stdout.write(f'  Monitoring Dashboard: /api/monitoring/dashboard/')
            self.stdout.write(f'  Performance Metrics: /api/monitoring/performance/')
            self.stdout.write(f'  Service Status: /api/monitoring/services/')
            self.stdout.write(f'  Alert History: /api/monitoring/alerts/')
            
            if options['daemon']:
                self.stdout.write('\n🔄 Running in daemon mode. Press Ctrl+C to stop...')
                try:
                    while True:
                        time.sleep(10)
                        # Display periodic status
                        self._display_status(services)
                except KeyboardInterrupt:
                    self.stdout.write('\n🛑 Stopping monitoring services...')
                    self._stop_services(services)
                    self.stdout.write(self.style.SUCCESS('✅ All monitoring services stopped'))
            else:
                self.stdout.write('\n✅ Monitoring services started successfully!')
                self.stdout.write('Use --daemon flag to run continuously')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error starting monitoring services: {e}')
            )
            logger.error(f"Error starting monitoring services: {e}")
            
    def _display_status(self, services):
        """Display periodic status of monitoring services"""
        try:
            self.stdout.write('\n📊 Status Update:')
            for service_name, service in services.items():
                if hasattr(service, 'monitoring_active'):
                    status = '🟢 ACTIVE' if service.monitoring_active else '🔴 INACTIVE'
                    self.stdout.write(f'  {service_name.title()}: {status}')
                    
                    # Show additional info for application monitoring
                    if service_name == 'application' and hasattr(service, 'get_monitoring_status'):
                        try:
                            status_info = service.get_monitoring_status()
                            if 'performance_summary' in status_info:
                                summary = status_info['performance_summary']
                                if 'cpu_usage' in summary:
                                    cpu_current = summary['cpu_usage'].get('current', 0)
                                    self.stdout.write(f'    CPU Usage: {cpu_current:.1f}%')
                                if 'memory_usage' in summary:
                                    mem_current = summary['memory_usage'].get('current', 0)
                                    self.stdout.write(f'    Memory Usage: {mem_current:.1f}%')
                        except Exception as e:
                            self.stdout.write(f'    Status Error: {e}')
                            
        except Exception as e:
            self.stdout.write(f'  Status Error: {e}')
            
    def _stop_services(self, services):
        """Stop all monitoring services"""
        for service_name, service in services.items():
            try:
                if hasattr(service, 'stop_monitoring'):
                    service.stop_monitoring()
                    self.stdout.write(f'✅ {service_name.title()} Monitoring Service stopped')
                else:
                    self.stdout.write(f'⚠️ {service_name.title()} service does not have stop_monitoring method')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error stopping {service_name.title()} Monitoring Service: {e}')
                )
