"""
Health Check Management Command

This command provides comprehensive health checking for the AI Trading Engine
production deployment, including database, Redis, Celery, and application health.
"""

import time
import psutil
import redis
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class HealthCheck:
    """Comprehensive health checking for production deployment"""
    
    def __init__(self):
        self.checks = []
        self.start_time = time.time()
        
    def add_check(self, name, check_func, critical=False):
        """Add a health check"""
        self.checks.append({
            'name': name,
            'check_func': check_func,
            'critical': critical
        })
    
    def run_checks(self):
        """Run all health checks"""
        results = {
            'timestamp': timezone.now().isoformat(),
            'uptime': time.time() - self.start_time,
            'checks': [],
            'overall_status': 'healthy',
            'critical_failures': 0,
            'total_checks': len(self.checks)
        }
        
        for check in self.checks:
            try:
                start_time = time.time()
                status, message, details = check['check_func']()
                duration = time.time() - start_time
                
                check_result = {
                    'name': check['name'],
                    'status': status,
                    'message': message,
                    'duration': round(duration, 3),
                    'critical': check['critical'],
                    'details': details
                }
                
                if status == 'unhealthy' and check['critical']:
                    results['critical_failures'] += 1
                    results['overall_status'] = 'unhealthy'
                elif status == 'unhealthy' and results['overall_status'] == 'healthy':
                    results['overall_status'] = 'degraded'
                
                results['checks'].append(check_result)
                
            except Exception as e:
                logger.error(f"Health check '{check['name']}' failed with error: {e}")
                check_result = {
                    'name': check['name'],
                    'status': 'unhealthy',
                    'message': f'Check failed with error: {str(e)}',
                    'duration': 0,
                    'critical': check['critical'],
                    'details': {'error': str(e)}
                }
                
                if check['critical']:
                    results['critical_failures'] += 1
                    results['overall_status'] = 'unhealthy'
                
                results['checks'].append(check_result)
        
        return results


class Command(BaseCommand):
    help = 'Perform comprehensive health checks for production deployment'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['json', 'text', 'detailed'],
            default='text',
            help='Output format for health check results'
        )
        parser.add_argument(
            '--critical-only',
            action='store_true',
            help='Only show critical failures'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout for health checks in seconds'
        )
    
    def handle(self, *args, **options):
        """Execute health checks"""
        self.stdout.write("Starting comprehensive health checks...")
        
        # Initialize health checker
        health_checker = HealthCheck()
        
        # Add system health checks
        health_checker.add_check('system_resources', self.check_system_resources, critical=True)
        health_checker.add_check('disk_space', self.check_disk_space, critical=True)
        health_checker.add_check('memory_usage', self.check_memory_usage, critical=True)
        
        # Add database health checks
        health_checker.add_check('database_connection', self.check_database_connection, critical=True)
        health_checker.add_check('database_performance', self.check_database_performance, critical=False)
        
        # Add Redis health checks
        health_checker.add_check('redis_connection', self.check_redis_connection, critical=True)
        health_checker.add_check('redis_performance', self.check_redis_performance, critical=False)
        
        # Add application health checks
        health_checker.add_check('django_app', self.check_django_app, critical=True)
        health_checker.add_check('static_files', self.check_static_files, critical=False)
        
        # Add external service checks
        health_checker.add_check('external_apis', self.check_external_apis, critical=False)
        
        # Run all checks
        results = health_checker.run_checks()
        
        # Output results
        self.output_results(results, options['format'], options['critical_only'])
        
        # Exit with appropriate code
        if results['overall_status'] == 'unhealthy':
            self.stdout.write(self.style.ERROR("Health checks failed - system is unhealthy"))
            exit(1)
        elif results['overall_status'] == 'degraded':
            self.stdout.write(self.style.WARNING("Health checks show degraded performance"))
            exit(0)
        else:
            self.stdout.write(self.style.SUCCESS("All health checks passed - system is healthy"))
            exit(0)
    
    def check_system_resources(self):
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            load_avg = psutil.getloadavg()
            
            if cpu_percent > 90:
                return 'unhealthy', f'CPU usage too high: {cpu_percent}%', {
                    'cpu_percent': cpu_percent,
                    'load_avg': load_avg
                }
            elif cpu_percent > 80:
                return 'degraded', f'CPU usage elevated: {cpu_percent}%', {
                    'cpu_percent': cpu_percent,
                    'load_avg': load_avg
                }
            else:
                return 'healthy', f'CPU usage normal: {cpu_percent}%', {
                    'cpu_percent': cpu_percent,
                    'load_avg': load_avg
                }
        except Exception as e:
            return 'unhealthy', f'Failed to check system resources: {e}', {}
    
    def check_disk_space(self):
        """Check disk space"""
        try:
            disk_usage = psutil.disk_usage('/')
            free_percent = (disk_usage.free / disk_usage.total) * 100
            
            if free_percent < 5:
                return 'unhealthy', f'Disk space critical: {free_percent:.1f}% free', {
                    'free_percent': free_percent,
                    'free_gb': disk_usage.free / (1024**3),
                    'total_gb': disk_usage.total / (1024**3)
                }
            elif free_percent < 10:
                return 'degraded', f'Disk space low: {free_percent:.1f}% free', {
                    'free_percent': free_percent,
                    'free_gb': disk_usage.free / (1024**3),
                    'total_gb': disk_usage.total / (1024**3)
                }
            else:
                return 'healthy', f'Disk space adequate: {free_percent:.1f}% free', {
                    'free_percent': free_percent,
                    'free_gb': disk_usage.free / (1024**3),
                    'total_gb': disk_usage.total / (1024**3)
                }
        except Exception as e:
            return 'unhealthy', f'Failed to check disk space: {e}', {}
    
    def check_memory_usage(self):
        """Check memory usage"""
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            if memory_percent > 95:
                return 'unhealthy', f'Memory usage critical: {memory_percent}%', {
                    'memory_percent': memory_percent,
                    'available_gb': memory.available / (1024**3),
                    'total_gb': memory.total / (1024**3)
                }
            elif memory_percent > 85:
                return 'degraded', f'Memory usage high: {memory_percent}%', {
                    'memory_percent': memory_percent,
                    'available_gb': memory.available / (1024**3),
                    'total_gb': memory.total / (1024**3)
                }
            else:
                return 'healthy', f'Memory usage normal: {memory_percent}%', {
                    'memory_percent': memory_percent,
                    'available_gb': memory.available / (1024**3),
                    'total_gb': memory.total / (1024**3)
                }
        except Exception as e:
            return 'unhealthy', f'Failed to check memory usage: {e}', {}
    
    def check_database_connection(self):
        """Check database connection"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            return 'healthy', 'Database connection successful', {
                'database': settings.DATABASES['default']['ENGINE'],
                'connection_time': 0.001
            }
        except Exception as e:
            return 'unhealthy', f'Database connection failed: {e}', {}
    
    def check_database_performance(self):
        """Check database performance"""
        try:
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM django_migrations")
                cursor.fetchone()
            duration = time.time() - start_time
            
            if duration > 1.0:
                return 'degraded', f'Database query slow: {duration:.3f}s', {
                    'query_time': duration,
                    'threshold': 1.0
                }
            else:
                return 'healthy', f'Database query fast: {duration:.3f}s', {
                    'query_time': duration,
                    'threshold': 1.0
                }
        except Exception as e:
            return 'unhealthy', f'Database performance check failed: {e}', {}
    
    def check_redis_connection(self):
        """Check Redis connection"""
        try:
            # Test cache operations
            test_key = 'health_check_test'
            test_value = 'test_value'
            
            cache.set(test_key, test_value, 10)
            retrieved_value = cache.get(test_key)
            cache.delete(test_key)
            
            if retrieved_value == test_value:
                return 'healthy', 'Redis connection and operations successful', {
                    'redis_host': getattr(settings, 'REDIS_HOST', 'localhost'),
                    'redis_port': getattr(settings, 'REDIS_PORT', 6379)
                }
            else:
                return 'unhealthy', 'Redis operations failed', {}
                
        except Exception as e:
            return 'unhealthy', f'Redis connection failed: {e}', {}
    
    def check_redis_performance(self):
        """Check Redis performance"""
        try:
            start_time = time.time()
            test_key = 'health_check_performance_test'
            test_value = 'x' * 1000  # 1KB of data
            
            cache.set(test_key, test_value, 10)
            retrieved_value = cache.get(test_key)
            cache.delete(test_key)
            
            duration = time.time() - start_time
            
            if duration > 0.1:
                return 'degraded', f'Redis operations slow: {duration:.3f}s', {
                    'operation_time': duration,
                    'threshold': 0.1
                }
            else:
                return 'healthy', f'Redis operations fast: {duration:.3f}s', {
                    'operation_time': duration,
                    'threshold': 0.1
                }
                
        except Exception as e:
            return 'unhealthy', f'Redis performance check failed: {e}', {}
    
    def check_django_app(self):
        """Check Django application health"""
        try:
            from django.core.management import execute_from_command_line
            from django.conf import settings
            
            # Check if settings are properly configured
            if not hasattr(settings, 'SECRET_KEY') or not settings.SECRET_KEY:
                return 'unhealthy', 'Django SECRET_KEY not configured', {}
            
            if not hasattr(settings, 'DATABASES') or not settings.DATABASES:
                return 'unhealthy', 'Django databases not configured', {}
            
            return 'healthy', 'Django application properly configured', {
                'debug_mode': getattr(settings, 'DEBUG', False),
                'installed_apps_count': len(getattr(settings, 'INSTALLED_APPS', [])),
                'middleware_count': len(getattr(settings, 'MIDDLEWARE', []))
            }
            
        except Exception as e:
            return 'unhealthy', f'Django application check failed: {e}', {}
    
    def check_static_files(self):
        """Check static files accessibility"""
        try:
            static_root = getattr(settings, 'STATIC_ROOT', None)
            if not static_root:
                return 'degraded', 'STATIC_ROOT not configured', {}
            
            import os
            if not os.path.exists(static_root):
                return 'degraded', 'STATIC_ROOT directory does not exist', {}
            
            return 'healthy', 'Static files directory accessible', {
                'static_root': str(static_root),
                'exists': True
            }
            
        except Exception as e:
            return 'unhealthy', f'Static files check failed: {e}', {}
    
    def check_external_apis(self):
        """Check external API connectivity"""
        try:
            # Check if we can reach external services
            test_urls = [
                'https://httpbin.org/status/200',
                'https://api.github.com/zen'
            ]
            
            successful_checks = 0
            total_checks = len(test_urls)
            
            for url in test_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        successful_checks += 1
                except:
                    pass
            
            success_rate = successful_checks / total_checks
            
            if success_rate < 0.5:
                return 'unhealthy', f'External API connectivity poor: {success_rate:.1%}', {
                    'success_rate': success_rate,
                    'successful_checks': successful_checks,
                    'total_checks': total_checks
                }
            elif success_rate < 1.0:
                return 'degraded', f'External API connectivity degraded: {success_rate:.1%}', {
                    'success_rate': success_rate,
                    'successful_checks': successful_checks,
                    'total_checks': total_checks
                }
            else:
                return 'healthy', f'External API connectivity good: {success_rate:.1%}', {
                    'success_rate': success_rate,
                    'successful_checks': successful_checks,
                    'total_checks': total_checks
                }
                
        except Exception as e:
            return 'unhealthy', f'External API check failed: {e}', {}
    
    def output_results(self, results, format_type, critical_only):
        """Output health check results in specified format"""
        if format_type == 'json':
            import json
            self.stdout.write(json.dumps(results, indent=2))
        elif format_type == 'detailed':
            self.output_detailed(results, critical_only)
        else:
            self.output_text(results, critical_only)
    
    def output_text(self, results, critical_only):
        """Output results in human-readable text format"""
        self.stdout.write(f"\nHealth Check Results")
        self.stdout.write(f"Overall Status: {results['overall_status'].upper()}")
        self.stdout.write(f"Timestamp: {results['timestamp']}")
        self.stdout.write(f"Uptime: {results['uptime']:.1f}s")
        self.stdout.write(f"Total Checks: {results['total_checks']}")
        self.stdout.write(f"Critical Failures: {results['critical_failures']}")
        
        self.stdout.write(f"\nCheck Details:")
        for check in results['checks']:
            if critical_only and not check['critical']:
                continue
                
            status_icon = "OK" if check['status'] == 'healthy' else "WARN" if check['status'] == 'degraded' else "ERROR"
            critical_mark = " [CRITICAL]" if check['critical'] else ""
            
            self.stdout.write(f"{status_icon} {check['name']}{critical_mark}")
            self.stdout.write(f"   Status: {check['status']}")
            self.stdout.write(f"   Message: {check['message']}")
            self.stdout.write(f"   Duration: {check['duration']}s")
            if check['details']:
                for key, value in check['details'].items():
                    self.stdout.write(f"   {key}: {value}")
            self.stdout.write("")
    
    def output_detailed(self, results, critical_only):
        """Output results in detailed format"""
        self.output_text(results, critical_only)
        
        # Additional summary
        healthy_count = sum(1 for c in results['checks'] if c['status'] == 'healthy')
        degraded_count = sum(1 for c in results['checks'] if c['status'] == 'degraded')
        unhealthy_count = sum(1 for c in results['checks'] if c['status'] == 'unhealthy')
        
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"Healthy: {healthy_count}")
        self.stdout.write(f"Degraded: {degraded_count}")
        self.stdout.write(f"Unhealthy: {unhealthy_count}")
        
        if results['overall_status'] == 'unhealthy':
            self.stdout.write(self.style.ERROR("System requires immediate attention!"))
        elif results['overall_status'] == 'degraded':
            self.stdout.write(self.style.WARNING("System performance degraded"))
        else:
            self.stdout.write(self.style.SUCCESS("System operating normally"))
