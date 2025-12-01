"""
Django management command to sync ALL available coins from CoinGecko
"""

from django.core.management.base import BaseCommand
from apps.data.services import CryptoDataIngestionService


class Command(BaseCommand):
    help = 'Sync ALL available crypto coins from CoinGecko to database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of coins to sync (default: all available, up to 1000)',
            default=None
        )
        parser.add_argument(
            '--max-coins',
            type=int,
            help='Maximum coins to fetch when using all (default: 1000)',
            default=1000
        )
    
    def handle(self, *args, **options):
        limit = options['limit']
        max_coins = options['max_coins']
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SYNCING ALL COINS FROM COINGECKO'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        
        if limit:
            self.stdout.write(f"Syncing top {limit} coins...")
        else:
            self.stdout.write(f"Syncing ALL available coins from CoinGecko (up to {max_coins})...")
            self.stdout.write("(This may take a few minutes)")
        self.stdout.write('')
        
        service = CryptoDataIngestionService()
        
        try:
            success = service.sync_crypto_symbols(limit=limit, max_coins=max_coins)
            
            if success:
                from apps.trading.models import Symbol
                total_symbols = Symbol.objects.filter(
                    is_active=True,
                    is_crypto_symbol=True
                ).count()
                
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('=' * 60))
                self.stdout.write(self.style.SUCCESS('SYNC COMPLETED SUCCESSFULLY'))
                self.stdout.write(self.style.SUCCESS('=' * 60))
                self.stdout.write('')
                self.stdout.write(f"Total active crypto symbols in database: {total_symbols}")
                self.stdout.write('')
                self.stdout.write("Next steps:")
                self.stdout.write("1. Run: python scripts/update_all_coins.py")
                self.stdout.write("   (This will fetch market data for all symbols)")
                self.stdout.write("2. Signals will be generated for all symbols with data")
            else:
                self.stdout.write(self.style.ERROR('Sync failed. Check logs for details.'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error syncing coins: {e}'))
            raise

