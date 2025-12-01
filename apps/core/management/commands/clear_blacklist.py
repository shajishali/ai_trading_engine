"""
Management command to clear IP blacklist and rate limiting cache
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clear IP blacklist and rate limiting cache for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ip',
            type=str,
            help='Specific IP address to unblock',
        )

    def handle(self, *args, **options):
        specific_ip = options.get('ip')
        
        self.stdout.write('Clearing IP blacklist and rate limiting cache...')
        
        try:
            if specific_ip:
                # Clear specific IP
                cache.delete(f'blacklisted_ip_{specific_ip}')
                self.stdout.write(
                    self.style.SUCCESS(f'Cleared blacklist for IP: {specific_ip}')
                )
            else:
                # Clear all blacklisted IPs and rate limit cache
                cleared_count = 0
                
                # Clear all blacklisted IP cache entries
                for key in cache._cache.keys():
                    if key.startswith('blacklisted_ip_'):
                        cache.delete(key)
                        cleared_count += 1
                
                # Clear all rate limit cache entries
                rate_limit_count = 0
                for key in cache._cache.keys():
                    if key.startswith('rate_limit:'):
                        cache.delete(key)
                        rate_limit_count += 1
                
                # Clear suspicious IPs cache
                cache.delete('rate_limit_violations')
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Cleared {cleared_count} blacklisted IPs and {rate_limit_count} rate limit entries'
                    )
                )
            
            # Clear any other related cache
            cache.delete('suspicious_ips')
            
            self.stdout.write(
                self.style.SUCCESS('IP blacklist and rate limiting cache cleared successfully!')
            )
            
        except Exception as e:
            logger.error(f"Error clearing blacklist: {e}")
            self.stdout.write(
                self.style.ERROR(f'Error clearing blacklist: {e}')
            )
            raise















































