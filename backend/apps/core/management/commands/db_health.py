from django.core.management.base import BaseCommand
from django.db import connection, connections
from django.conf import settings
from django.core.cache import cache
import time
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor database health and performance for Phase 5'

    def add_arguments(self, parser):
        parser.add_argument(
            '--connections',
            action='store_true',
            help='Check database connections',
        )
        parser.add_argument(
            '--performance',
            action='store_true',
            help='Run performance tests',
        )
        parser.add_argument(
            '--optimization',
            action='store_true',
            help='Show optimization recommendations',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all health checks',
        )

    def handle(self, *args, **options):
        if options['all'] or not any([options['connections'], options['performance'], options['optimization']]):
            self.run_all_checks()
        else:
            if options['connections']:
                self.check_connections()
            if options['performance']:
                self.run_performance_tests()
            if options['optimization']:
                self.show_optimization_recommendations()

    def run_all_checks(self):
        """Run all database health checks"""
        self.stdout.write(self.style.SUCCESS('=== DATABASE HEALTH MONITORING ==='))
        self.stdout.write('')
        
        self.check_connections()
        self.stdout.write('')
        self.run_performance_tests()
        self.stdout.write('')
        self.show_optimization_recommendations()

    def check_connections(self):
        """Check database connection health"""
        self.stdout.write(self.style.SUCCESS('--- CONNECTION HEALTH ---'))
        
        try:
            # Test basic connection
            connection.ensure_connection()
            self.stdout.write(self.style.SUCCESS('✓ Database connection: Healthy'))
            
            # Check connection settings
            db_settings = settings.DATABASES['default']
            self.stdout.write(f'Engine: {db_settings["ENGINE"]}')
            self.stdout.write(f'Connection Max Age: {db_settings.get("CONN_MAX_AGE", "Default")} seconds')
            self.stdout.write(f'Atomic Requests: {db_settings.get("ATOMIC_REQUESTS", False)}')
            
            # Test connection pool
            if hasattr(connection, 'connection'):
                conn = connection.connection
                if hasattr(conn, 'pool_size'):
                    self.stdout.write(f'Pool Size: {conn.pool_size}')
                if hasattr(conn, 'max_overflow'):
                    self.stdout.write(f'Max Overflow: {conn.max_overflow}')
            
            # Test query execution
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    self.stdout.write(self.style.SUCCESS('✓ Query execution: Healthy'))
                else:
                    self.stdout.write(self.style.ERROR('✗ Query execution: Failed'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Database connection: Unhealthy - {e}'))
            logger.error(f'Database connection error: {e}')

    def run_performance_tests(self):
        """Run database performance tests"""
        self.stdout.write(self.style.SUCCESS('--- PERFORMANCE TESTS ---'))
        
        try:
            # Test simple query performance
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM django_migrations")
                result = cursor.fetchone()
            simple_query_time = time.time() - start_time
            
            if simple_query_time < 0.1:
                self.stdout.write(self.style.SUCCESS(f'✓ Simple query: {simple_query_time:.3f}s (Excellent)'))
            elif simple_query_time < 0.5:
                self.stdout.write(self.style.SUCCESS(f'✓ Simple query: {simple_query_time:.3f}s (Good)'))
            elif simple_query_time < 1.0:
                self.stdout.write(self.style.WARNING(f'⚠ Simple query: {simple_query_time:.3f}s (Slow)'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Simple query: {simple_query_time:.3f}s (Very Slow)'))
            
            # Test complex query performance (if tables exist)
            try:
                start_time = time.time()
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        ORDER BY name
                    """)
                    tables = cursor.fetchall()
                complex_query_time = time.time() - start_time
                
                if complex_query_time < 0.1:
                    self.stdout.write(self.style.SUCCESS(f'✓ Complex query: {complex_query_time:.3f}s (Excellent)'))
                elif complex_query_time < 0.5:
                    self.stdout.write(self.style.SUCCESS(f'✓ Complex query: {complex_query_time:.3f}s (Good)'))
                elif complex_query_time < 1.0:
                    self.stdout.write(self.style.WARNING(f'⚠ Complex query: {complex_query_time:.3f}s (Slow)'))
                else:
                    self.stdout.write(self.style.ERROR(f'✗ Complex query: {complex_query_time:.3f}s (Very Slow)'))
                
                self.stdout.write(f'Total tables: {len(tables)}')
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠ Complex query test skipped: {e}'))
            
            # Test cache performance
            cache_key = 'db_health_test'
            start_time = time.time()
            cache.set(cache_key, 'test_value', 10)
            cache.get(cache_key)
            cache_time = time.time() - start_time
            
            if cache_time < 0.01:
                self.stdout.write(self.style.SUCCESS(f'✓ Cache performance: {cache_time:.3f}s (Excellent)'))
            elif cache_time < 0.05:
                self.stdout.write(self.style.SUCCESS(f'✓ Cache performance: {cache_time:.3f}s (Good)'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Cache performance: {cache_time:.3f}s (Slow)'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Performance test failed: {e}'))
            logger.error(f'Performance test error: {e}')

    def show_optimization_recommendations(self):
        """Show database optimization recommendations"""
        self.stdout.write(self.style.SUCCESS('--- OPTIMIZATION RECOMMENDATIONS ---'))
        
        # Check current database engine
        db_engine = settings.DATABASES['default']['ENGINE']
        
        if 'sqlite' in db_engine:
            self.stdout.write('📋 SQLite Database Detected:')
            self.stdout.write('  • Consider migrating to PostgreSQL for production')
            self.stdout.write('  • Enable WAL mode for better concurrency')
            self.stdout.write('  • Regular VACUUM operations recommended')
            self.stdout.write('  • Monitor database file size')
        
        elif 'postgresql' in db_engine:
            self.stdout.write('📋 PostgreSQL Database Detected:')
            self.stdout.write('  • Enable connection pooling (PgBouncer)')
            self.stdout.write('  • Configure appropriate shared_buffers')
            self.stdout.write('  • Enable query plan caching')
            self.stdout.write('  • Regular ANALYZE operations')
        
        elif 'mysql' in db_engine:
            self.stdout.write('📋 MySQL Database Detected:')
            self.stdout.write('  • Configure innodb_buffer_pool_size')
            self.stdout.write('  • Enable query cache')
            self.stdout.write('  • Monitor slow query log')
            self.stdout.write('  • Regular OPTIMIZE TABLE operations')
        
        # General recommendations
        self.stdout.write('')
        self.stdout.write('🔧 General Optimization Tips:')
        self.stdout.write('  • Add database indexes for frequently queried fields')
        self.stdout.write('  • Use select_related() and prefetch_related() for related queries')
        self.stdout.write('  • Implement database query result caching')
        self.stdout.write('  • Monitor slow queries and optimize them')
        self.stdout.write('  • Regular database maintenance and cleanup')
        self.stdout.write('  • Consider read replicas for heavy read workloads')
        
        # Check current settings
        self.stdout.write('')
        self.stdout.write('⚙️ Current Settings:')
        db_opt = getattr(settings, 'DB_OPTIMIZATION', {})
        self.stdout.write(f'  • Query timeout: {db_opt.get("QUERY_TIMEOUT", "Not set")}s')
        self.stdout.write(f'  • Max connections: {db_opt.get("MAX_CONNECTIONS", "Not set")}')
        self.stdout.write(f'  • Connection retry attempts: {db_opt.get("CONNECTION_RETRY_ATTEMPTS", "Not set")}')
        
        # Recommendations based on current settings
        if not db_opt.get('QUERY_TIMEOUT'):
            self.stdout.write(self.style.WARNING('  ⚠️ Consider setting QUERY_TIMEOUT for long-running queries'))
        
        if not db_opt.get('MAX_CONNECTIONS'):
            self.stdout.write(self.style.WARNING('  ⚠️ Consider setting MAX_CONNECTIONS for connection pooling'))













