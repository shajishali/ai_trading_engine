from django.core.management.base import BaseCommand
from apps.analytics.services import PositionPriceUpdateService


class Command(BaseCommand):
    help = 'Update current prices for all portfolio positions using live market data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Update prices for a specific symbol only',
        )

    def handle(self, *args, **options):
        symbol = options.get('symbol')
        
        if symbol:
            # Update specific symbol
            self.stdout.write(f"Updating prices for {symbol}...")
            success = PositionPriceUpdateService.update_position_price(symbol, None)
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully updated prices for {symbol}")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"Failed to update prices for {symbol}")
                )
        else:
            # Update all positions
            self.stdout.write("Updating prices for all positions...")
            success = PositionPriceUpdateService.update_all_position_prices()
            if success:
                self.stdout.write(
                    self.style.SUCCESS("Successfully updated all position prices")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("Failed to update position prices")
                )






























