#!/usr/bin/env python
"""
Script to update all supported crypto symbols with fresh data
"""
import os
import sys
import django
import time
from datetime import datetime, timezone

# Setup Django environment
# Get the backend directory (parent of scripts directory)
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.trading.models import Symbol
from apps.data.enhanced_multi_source_service import EnhancedMultiSourceDataService
from django.utils import timezone as django_timezone

def safe_encode(text):
    """Safely encode text for Windows console output"""
    if not text:
        return ""
    try:
        # Try to encode to ASCII, replacing problematic characters
        return text.encode('ascii', 'replace').decode('ascii')
    except:
        # If that fails, just return a safe version
        return str(text).encode('ascii', 'replace').decode('ascii')


def update_all_supported_coins(max_coins=None):
    """Update all active crypto symbols with fresh data"""
    
    # Get all active crypto symbols from database (no limit)
    symbols = Symbol.objects.filter(
        symbol_type='CRYPTO', 
        is_active=True, 
        is_crypto_symbol=True
    ).order_by('market_cap_rank', 'symbol')
    
    # Apply limit only if specified
    if max_coins:
        symbols = symbols[:max_coins]
    
    total_count = symbols.count()
    if max_coins:
        print(f"Updating top {total_count} crypto symbols (limited to {max_coins})...")
    else:
        print(f"Updating all {total_count} crypto symbols (no limit)...")
    print("=" * 60)
    
    # Use enhanced multi-source service with automatic fallback
    service = EnhancedMultiSourceDataService()
    success_count = 0
    error_count = 0
    sources_used = {}
    
    # Calculate time range: from 1 hour ago to 1 hour before current time
    end_time = django_timezone.now() - django_timezone.timedelta(hours=1)
    start_time = end_time - django_timezone.timedelta(hours=1)
    
    print(f"Time range: {start_time} to {end_time}")
    print("=" * 60)
    
    for i, symbol in enumerate(symbols, 1):
        try:
            safe_symbol = safe_encode(symbol.symbol)
            print(f"[{i:3d}/{total_count}] Updating {safe_symbol}...", end=" ", flush=True)
            
            # Skip symbols that are already USDT pairs if base symbol exists
            symbol_upper = symbol.symbol.upper()
            if symbol_upper.endswith('USDT') and len(symbol_upper) > 4:
                base_symbol = symbol_upper[:-4]  # Remove 'USDT'
                base_exists = Symbol.objects.filter(
                    symbol=base_symbol,
                    symbol_type='CRYPTO',
                    is_active=True
                ).exists()
                if base_exists:
                    print("[SKIP] (Base symbol exists)")
                    success_count += 1  # Count as success since base symbol will be updated
                    continue
            
            # Check if symbol has any existing data
            from apps.data.models import MarketData
            has_existing_data = MarketData.objects.filter(symbol=symbol).exists()
            
            # Use enhanced service which automatically tries all sources with fallback
            if not has_existing_data:
                # Fetch 30 days of historical data for new symbols
                historical_start = django_timezone.now() - django_timezone.timedelta(days=30)
                success, source_name, records_saved = service.fetch_and_store_historical_data(
                    symbol=symbol,
                    timeframe='1h',
                    start=historical_start,
                    end=end_time
                )
            else:
                # Just update with latest hour
                success, source_name, records_saved = service.fetch_and_store_historical_data(
                    symbol=symbol,
                    timeframe='1h',
                    start=start_time,
                    end=end_time
                )
            
            if success:
                # Success means data was fetched (even if 0 new records = already exists)
                if records_saved > 0:
                    print(f"[OK] ({source_name} - {records_saved} records)")
                else:
                    print(f"[OK] ({source_name} - data already exists)")
                success_count += 1
                sources_used[source_name] = sources_used.get(source_name, 0) + 1
            else:
                print("[FAIL] (All sources failed)")
                error_count += 1
                
        except Exception as e:
            safe_error = safe_encode(str(e))
            print(f"[ERROR] {safe_error[:50]}")
            error_count += 1
    
    print("=" * 60)
    print(f"UPDATE SUMMARY:")
    print(f"Successful: {success_count}")
    print(f"Failed: {error_count}")
    print(f"Total: {total_count}")
    print(f"Success Rate: {(success_count/total_count*100):.1f}%")
    print("")
    print("Sources Used:")
    for source, count in sources_used.items():
        print(f"  - {source}: {count} symbols")
    print("=" * 60)
    
    return success_count, error_count

if __name__ == "__main__":
    print("Starting automated update for all crypto coins (no limit)...")
    
    # Wait for server to be ready before starting updates
    INITIAL_DELAY = 45  # Wait 45 seconds to ensure server is fully ready
    print(f"Waiting {INITIAL_DELAY} seconds for server to be ready...")
    time.sleep(INITIAL_DELAY)
    print("Starting coin updates now...")
    print("=" * 60)
    
    # No limit - update all coins
    success, errors = update_all_supported_coins(max_coins=None)
    
    if success > 0:
        print(f"\nSuccessfully updated {success} crypto symbols!")
        print("Your automated hourly updates are now running.")
        print("Data will be updated every hour at minute 0.")
    else:
        print("\nNo symbols were updated successfully.")
    
    print("\nUpdate process completed!")




















