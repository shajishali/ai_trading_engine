#!/usr/bin/env python
"""
Script to update all supported crypto symbols with fresh data from multiple sources
Uses multi-source data service with automatic fallback
"""
import os
import sys
import django
from datetime import datetime, timezone as dt_timezone

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.trading.models import Symbol
from apps.data.historical_data_manager import HistoricalDataManager
from apps.data.services import CryptoDataIngestionService
from apps.data.multi_source_service import MultiSourceDataService
from django.utils import timezone as django_timezone

def update_all_supported_coins_multi_source(
    source_priority=None,
    use_binance_first=True,
    use_coingecko_fallback=True
):
    """
    Update ALL active crypto symbols with fresh data from multiple sources
    
    Args:
        source_priority: List of source names in priority order
                        Options: 'binance', 'cryptocompare', 'okx', 'bybit', 'coingecko'
        use_binance_first: Use Binance as primary source (default: True)
        use_coingecko_fallback: Use CoinGecko as final fallback (default: True)
    """
    
    # Get ALL active crypto symbols from database
    symbols = Symbol.objects.filter(
        symbol_type='CRYPTO', 
        is_active=True, 
        is_crypto_symbol=True
    ).order_by('symbol')
    
    print(f"Updating {symbols.count()} crypto symbols using multiple data sources...")
    print("=" * 60)
    
    # Initialize services
    manager = HistoricalDataManager()
    coingecko_service = CryptoDataIngestionService()
    
    # Initialize multi-source service if using alternative sources
    multi_source = None
    if source_priority and any(s not in ['binance', 'coingecko'] for s in source_priority):
        multi_source = MultiSourceDataService(source_priority=source_priority)
        print(f"Using multi-source service with priority: {', '.join(source_priority)}")
    else:
        print("Using Binance (primary) and CoinGecko (fallback)")
    
    success_count = 0
    error_count = 0
    binance_count = 0
    coingecko_count = 0
    other_source_count = 0
    source_stats = {}
    
    # Calculate time range: from 1 hour ago to 1 hour before current time
    end_time = django_timezone.now() - django_timezone.timedelta(hours=1)
    start_time = end_time - django_timezone.timedelta(hours=1)
    
    print(f"Time range: {start_time} to {end_time}")
    print("=" * 60)
    
    for i, symbol in enumerate(symbols, 1):
        try:
            print(f"[{i:3d}/{symbols.count()}] Updating {symbol.symbol}...", end=" ", flush=True)
            
            # Skip symbols that are already USDT pairs if base symbol exists
            symbol_upper = symbol.symbol.upper()
            if symbol_upper.endswith('USDT') and len(symbol_upper) > 4:
                base_symbol = symbol_upper[:-4]
                base_exists = Symbol.objects.filter(
                    symbol=base_symbol,
                    symbol_type='CRYPTO',
                    is_active=True
                ).exists()
                if base_exists:
                    print("[SKIP] (Base symbol exists)")
                    success_count += 1
                    continue
            
            # Check if symbol has any existing data
            from apps.data.models import MarketData
            has_existing_data = MarketData.objects.filter(symbol=symbol).exists()
            
            success = False
            source_used = None
            
            # Step 1: Try Binance first (if enabled)
            if use_binance_first:
                try:
                    if not has_existing_data:
                        historical_start = django_timezone.now() - django_timezone.timedelta(days=30)
                        if manager.fetch_complete_historical_data(symbol, timeframe='1h', start=historical_start, end=end_time):
                            print("[OK] (Binance - Historical)")
                            success = True
                            source_used = 'binance'
                            binance_count += 1
                    else:
                        if manager.fetch_complete_historical_data(symbol, timeframe='1h', start=start_time, end=end_time):
                            print("[OK] (Binance - Update)")
                            success = True
                            source_used = 'binance'
                            binance_count += 1
                except Exception as e:
                    error_msg = str(e)
                    if "Invalid symbol" in error_msg or "Invalid trading pair" in error_msg:
                        # Invalid symbol - skip to next source
                        pass
                    else:
                        # Other error - try next source
                        pass
            
            # Step 2: Try multi-source service (if enabled and Binance failed)
            if not success and multi_source:
                try:
                    days_to_fetch = 30 if not has_existing_data else 7
                    records, source_name = multi_source.fetch_historical_data(
                        symbol=symbol,
                        timeframe='1h',
                        days=days_to_fetch
                    )
                    
                    # Skip TradingView for direct API calls (requires CSV import)
                    if source_name == 'tradingview' and (not records or len(records) == 0):
                        # TradingView doesn't have free API - skip to next source
                        pass
                    elif records and len(records) > 0:
                        saved = multi_source.save_market_data(
                            symbol=symbol,
                            records=records,
                            timeframe='1h',
                            source_name=source_name
                        )
                        if saved > 0:
                            print(f"[OK] ({source_name.title()} - {saved} records)")
                            success = True
                            source_used = source_name
                            other_source_count += 1
                            source_stats[source_name] = source_stats.get(source_name, 0) + 1
                except Exception as e:
                    pass  # Try next source
            
            # Step 3: Fallback to CoinGecko (if enabled)
            if not success and use_coingecko_fallback:
                try:
                    days_to_fetch = 30 if not has_existing_data else 7
                    if coingecko_service.sync_market_data(symbol, days=days_to_fetch):
                        print(f"[OK] (CoinGecko - {days_to_fetch}d)")
                        success = True
                        source_used = 'coingecko'
                        coingecko_count += 1
                except Exception as e:
                    print(f"[FAIL] ({str(e)[:30]})")
            
            if success:
                success_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            print(f"[ERROR] {str(e)[:30]}")
            error_count += 1
    
    print("=" * 60)
    print(f"UPDATE SUMMARY:")
    print(f"Successful: {success_count}")
    print(f"Failed: {error_count}")
    print(f"Binance: {binance_count}")
    print(f"CoinGecko: {coingecko_count}")
    if source_stats:
        print(f"Other Sources:")
        for source, count in source_stats.items():
            print(f"  - {source.title()}: {count}")
    print(f"Total: {symbols.count()}")
    print(f"Success Rate: {(success_count/symbols.count()*100):.1f}%")
    print("=" * 60)
    
    return success_count, error_count

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Update coin data from multiple sources')
    parser.add_argument(
        '--sources',
        nargs='+',
        choices=['binance', 'cryptocompare', 'okx', 'bybit', 'coingecko'],
        default=None,
        help='Data sources in priority order (default: binance, cryptocompare, okx, bybit, coingecko)'
    )
    parser.add_argument(
        '--no-binance',
        action='store_true',
        help='Skip Binance as primary source'
    )
    parser.add_argument(
        '--no-coingecko',
        action='store_true',
        help='Skip CoinGecko as fallback'
    )
    
    args = parser.parse_args()
    
    source_priority = args.sources
    use_binance = not args.no_binance
    use_coingecko = not args.no_coingecko
    
    print("Starting automated update for all supported crypto coins...")
    print(f"Configuration:")
    print(f"  - Use Binance: {use_binance}")
    print(f"  - Use CoinGecko: {use_coingecko}")
    if source_priority:
        print(f"  - Source Priority: {', '.join(source_priority)}")
    print()
    
    success, errors = update_all_supported_coins_multi_source(
        source_priority=source_priority,
        use_binance_first=use_binance,
        use_coingecko_fallback=use_coingecko
    )
    
    if success > 0:
        print(f"\nSuccessfully updated {success} crypto symbols!")
    else:
        print("\nNo symbols were updated successfully.")
    
    print("\nUpdate process completed!")

