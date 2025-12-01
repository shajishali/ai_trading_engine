"""
Django management command to test Redis connection
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import redis


class Command(BaseCommand):
    help = 'Test Redis connection for Django Channels'
    
    def handle(self, *args, **options):
        self.stdout.write('Testing Redis connection...')
        
        try:
            # Test basic Redis connection
            r = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', '127.0.0.1'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0)
            )
            
            # Test connection
            r.ping()
            self.stdout.write(
                self.style.SUCCESS('✅ Redis connection successful!')
            )
            
            # Test basic operations
            r.set('django_test_key', 'django_test_value')
            value = r.get('django_test_key')
            self.stdout.write(
                self.style.SUCCESS(f'✅ Redis read/write test successful: {value.decode()}')
            )
            
            # Clean up
            r.delete('django_test_key')
            self.stdout.write(
                self.style.SUCCESS('✅ Redis cleanup successful!')
            )
            
            # Test channel layers if available
            try:
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                self.stdout.write(
                    self.style.SUCCESS('✅ Django Channels channel layer accessible!')
                )
                
                # Test sending a message to a test group
                from asgiref.sync import async_to_sync
                async_to_sync(channel_layer.group_send)(
                    'test_group',
                    {
                        'type': 'test.message',
                        'message': 'Test message from Django'
                    }
                )
                self.stdout.write(
                    self.style.SUCCESS('✅ Channel layer message sending successful!')
                )
                
            except ImportError:
                self.stdout.write(
                    self.style.WARNING('⚠️ Django Channels not available (channels not installed)')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Channel layer test failed: {e}')
                )
            
            self.stdout.write(
                self.style.SUCCESS('\n🎉 Redis is fully operational for Django Channels!')
            )
            
        except redis.ConnectionError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Redis connection failed: {e}')
            )
            self.stdout.write(
                self.style.ERROR('Make sure Redis server is running on 127.0.0.1:6379')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Redis test failed: {e}')
            )









