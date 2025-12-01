from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection
from celery import current_app
import json
import time


class Command(BaseCommand):
    help = 'Monitor Celery workers and task performance for Phase 5'

    def add_arguments(self, parser):
        parser.add_argument(
            '--workers',
            action='store_true',
            help='Show worker status',
        )
        parser.add_argument(
            '--tasks',
            action='store_true',
            help='Show task statistics',
        )
        parser.add_argument(
            '--queues',
            action='store_true',
            help='Show queue status',
        )
        parser.add_argument(
            '--health',
            action='store_true',
            help='Run health checks',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Show all monitoring information',
        )

    def handle(self, *args, **options):
        if options['all'] or not any([options['workers'], options['tasks'], options['queues'], options['health']]):
            self.show_all()
        else:
            if options['workers']:
                self.show_workers()
            if options['tasks']:
                self.show_tasks()
            if options['queues']:
                self.show_queues()
            if options['health']:
                self.run_health_checks()

    def show_all(self):
        """Show all monitoring information"""
        self.stdout.write(self.style.SUCCESS('=== CELERY MONITORING DASHBOARD ==='))
        self.stdout.write('')
        
        self.show_workers()
        self.stdout.write('')
        self.show_tasks()
        self.stdout.write('')
        self.show_queues()
        self.stdout.write('')
        self.run_health_checks()

    def show_workers(self):
        """Show worker status"""
        self.stdout.write(self.style.SUCCESS('--- WORKER STATUS ---'))
        
        try:
            # Get active workers
            inspect = current_app.control.inspect()
            active_workers = inspect.active()
            registered_workers = inspect.registered()
            stats = inspect.stats()
            
            if not active_workers:
                self.stdout.write(self.style.WARNING('No active workers found'))
                return
            
            for worker_name in active_workers.keys():
                self.stdout.write(f'Worker: {worker_name}')
                
                # Show worker stats
                if stats and worker_name in stats:
                    worker_stats = stats[worker_name]
                    self.stdout.write(f'  Pool: {worker_stats.get("pool", {}).get("implementation", "Unknown")}')
                    self.stdout.write(f'  Processed: {worker_stats.get("total", {}).get("total", 0)}')
                    self.stdout.write(f'  Memory: {worker_stats.get("total", {}).get("mem", "Unknown")}')
                
                # Show active tasks
                if active_workers and worker_name in active_workers:
                    active_tasks = active_workers[worker_name]
                    self.stdout.write(f'  Active Tasks: {len(active_tasks)}')
                    for task in active_tasks:
                        self.stdout.write(f'    - {task["name"]} (ID: {task["id"]})')
                
                self.stdout.write('')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting worker status: {e}'))

    def show_tasks(self):
        """Show task statistics"""
        self.stdout.write(self.style.SUCCESS('--- TASK STATISTICS ---'))
        
        try:
            # Get task statistics
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            
            if not stats:
                self.stdout.write(self.style.WARNING('No worker statistics available'))
                return
            
            total_processed = 0
            for worker_name, worker_stats in stats.items():
                worker_total = worker_stats.get("total", {}).get("total", 0)
                total_processed += worker_total
                self.stdout.write(f'{worker_name}: {worker_total} tasks processed')
            
            self.stdout.write(f'Total Tasks Processed: {total_processed}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting task statistics: {e}'))

    def show_queues(self):
        """Show queue status"""
        self.stdout.write(self.style.SUCCESS('--- QUEUE STATUS ---'))
        
        try:
            # Get queue information
            inspect = current_app.control.inspect()
            active_queues = inspect.active_queues()
            
            if not active_queues:
                self.stdout.write(self.style.WARNING('No queue information available'))
                return
            
            for worker_name, queues in active_queues.items():
                self.stdout.write(f'Worker: {worker_name}')
                for queue in queues:
                    self.stdout.write(f'  Queue: {queue["name"]} (Priority: {queue.get("routing_key", "default")})')
                    self.stdout.write(f'    Consumers: {queue.get("consumers", 0)}')
                    self.stdout.write(f'    Messages: {queue.get("messages", 0)}')
                self.stdout.write('')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting queue status: {e}'))

    def run_health_checks(self):
        """Run system health checks"""
        self.stdout.write(self.style.SUCCESS('--- HEALTH CHECKS ---'))
        
        # Database health check
        try:
            connection.ensure_connection()
            self.stdout.write(self.style.SUCCESS('✓ Database: Healthy'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Database: Unhealthy - {e}'))
        
        # Cache health check
        try:
            cache.set('health_check', 'ok', 10)
            cache_result = cache.get('health_check')
            if cache_result == 'ok':
                self.stdout.write(self.style.SUCCESS('✓ Cache: Healthy'))
            else:
                self.stdout.write(self.style.ERROR('✗ Cache: Unhealthy - Read/Write mismatch'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Cache: Unhealthy - {e}'))
        
        # Celery connection check
        try:
            inspect = current_app.control.inspect()
            ping_result = inspect.ping()
            if ping_result:
                self.stdout.write(self.style.SUCCESS(f'✓ Celery: Healthy - {len(ping_result)} workers responding'))
            else:
                self.stdout.write(self.style.WARNING('⚠ Celery: No workers responding'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Celery: Unhealthy - {e}'))
        
        # Memory usage check
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            if memory_percent < 80:
                self.stdout.write(self.style.SUCCESS(f'✓ Memory: Healthy - {memory_percent:.1f}% used'))
            elif memory_percent < 90:
                self.stdout.write(self.style.WARNING(f'⚠ Memory: Warning - {memory_percent:.1f}% used'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Memory: Critical - {memory_percent:.1f}% used'))
        except ImportError:
            self.stdout.write(self.style.WARNING('⚠ Memory: psutil not available for monitoring'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Memory: Error checking - {e}'))

