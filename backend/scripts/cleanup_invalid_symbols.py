#!/usr/bin/env python
"""
Script to clean up invalid and duplicate symbols in the database.

This script:
1. Removes duplicate symbols (keeps base symbols, removes USDT pairs)
2. Deactivates symbols that don't exist on Binance
3. Validates symbols before attempting to fetch
"""
import os
import sys
import django
import requests
from typing import Set, List

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.trading.models import Symbol
from apps.data.models import MarketData
from django.db import transaction

# Binance Futures API endpoint to check valid symbols
BINANCE_EXCHANGE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"


def get_valid_binance_symbols() -> Set[str]:
    """Fetch list of valid trading pairs from Binance Futures API"""
    try:
        response = requests.get(BINANCE_EXCHANGE_INFO, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract all USDT trading pairs
        valid_pairs = set()
        for symbol_info in data.get('symbols', []):
            if symbol_info.get('status') == 'TRADING' and symbol_info.get('quoteAsset') == 'USDT':
                valid_pairs.add(symbol_info['symbol'])
        
        print(f"Found {len(valid_pairs)} valid USDT trading pairs on Binance")
        return valid_pairs
    except Exception as e:
        print(f"Error fetching Binance symbols: {e}")
        return set()


def get_base_symbol_from_pair(pair: str) -> str:
    """Extract base symbol from trading pair (e.g., BTCUSDT -> BTC)"""
    if pair.endswith('USDT'):
        return pair[:-4]  # Remove 'USDT'
    return pair


def cleanup_duplicate_symbols(valid_binance_pairs: Set[str]) -> dict:
    """Remove duplicate symbols - keep base symbols, remove USDT pairs"""
    stats = {
        'deactivated': 0,
        'deleted': 0,
        'kept': 0
    }
    
    # Get all crypto symbols
    crypto_symbols = Symbol.objects.filter(
        symbol_type='CRYPTO',
        is_crypto_symbol=True
    ).order_by('symbol')
    
    print(f"\nProcessing {crypto_symbols.count()} crypto symbols...")
    
    # Track base symbols we want to keep
    base_symbols_to_keep = set()
    usdt_pairs_to_remove = []
    
    for symbol in crypto_symbols:
        symbol_upper = symbol.symbol.upper()
        
        # If it's a USDT pair
        if symbol_upper.endswith('USDT'):
            base_symbol = get_base_symbol_from_pair(symbol_upper)
            
            # Check if base symbol exists
            base_exists = Symbol.objects.filter(
                symbol=base_symbol,
                symbol_type='CRYPTO'
            ).exists()
            
            # Check if this pair is valid on Binance
            is_valid_pair = symbol_upper in valid_binance_pairs
            
            if base_exists:
                # Base symbol exists, mark USDT pair for removal
                usdt_pairs_to_remove.append(symbol)
                print(f"  Marking {symbol.symbol} for removal (base symbol {base_symbol} exists)")
            elif not is_valid_pair:
                # Not a valid Binance pair, mark for deactivation
                symbol.is_active = False
                symbol.save()
                stats['deactivated'] += 1
                print(f"  Deactivated {symbol.symbol} (not a valid Binance pair)")
            else:
                # Valid pair but no base symbol - keep it but mark base symbol to keep
                base_symbols_to_keep.add(base_symbol)
                stats['kept'] += 1
        else:
            # Base symbol - check if corresponding USDT pair exists
            usdt_pair = f"{symbol_upper}USDT"
            usdt_exists = Symbol.objects.filter(
                symbol=usdt_pair,
                symbol_type='CRYPTO'
            ).exists()
            
            if usdt_exists and usdt_pair in valid_binance_pairs:
                # USDT pair exists and is valid - keep base symbol
                base_symbols_to_keep.add(symbol_upper)
                stats['kept'] += 1
            elif symbol_upper not in base_symbols_to_keep:
                # Check if this base symbol has a valid Binance pair
                if usdt_pair in valid_binance_pairs:
                    base_symbols_to_keep.add(symbol_upper)
                    stats['kept'] += 1
                else:
                    # No valid pair, deactivate
                    symbol.is_active = False
                    symbol.save()
                    stats['deactivated'] += 1
                    print(f"  Deactivated {symbol.symbol} (no valid Binance pair)")
    
    # Remove duplicate USDT pairs
    with transaction.atomic():
        for symbol in usdt_pairs_to_remove:
            # Check if it has market data
            has_data = MarketData.objects.filter(symbol=symbol).exists()
            
            if has_data:
                # Has data - deactivate instead of delete
                symbol.is_active = False
                symbol.save()
                stats['deactivated'] += 1
                print(f"  Deactivated {symbol.symbol} (has market data, base symbol exists)")
            else:
                # No data - safe to delete
                symbol.delete()
                stats['deleted'] += 1
                print(f"  Deleted {symbol.symbol} (no market data, base symbol exists)")
    
    return stats


def deactivate_invalid_symbols(valid_binance_pairs: Set[str]) -> int:
    """Deactivate symbols that don't have valid Binance pairs"""
    deactivated = 0
    
    crypto_symbols = Symbol.objects.filter(
        symbol_type='CRYPTO',
        is_crypto_symbol=True,
        is_active=True
    )
    
    for symbol in crypto_symbols:
        symbol_upper = symbol.symbol.upper()
        
        # Check if it's a valid pair or has a valid pair
        is_valid_pair = symbol_upper in valid_binance_pairs
        has_valid_pair = False
        
        if not symbol_upper.endswith('USDT'):
            # Base symbol - check if USDT pair exists
            usdt_pair = f"{symbol_upper}USDT"
            has_valid_pair = usdt_pair in valid_binance_pairs
        else:
            # Already a pair
            has_valid_pair = is_valid_pair
        
        if not is_valid_pair and not has_valid_pair:
            # Not valid and no valid pair - deactivate
            symbol.is_active = False
            symbol.save()
            deactivated += 1
            print(f"  Deactivated {symbol.symbol} (no valid Binance pair)")
    
    return deactivated


def main():
    print("=" * 60)
    print("CLEANING UP INVALID AND DUPLICATE SYMBOLS")
    print("=" * 60)
    
    # Step 1: Get valid Binance symbols
    print("\n[1/3] Fetching valid Binance trading pairs...")
    valid_binance_pairs = get_valid_binance_symbols()
    
    if not valid_binance_pairs:
        print("ERROR: Could not fetch valid Binance symbols. Aborting.")
        return
    
    # Step 2: Clean up duplicates
    print("\n[2/3] Cleaning up duplicate symbols...")
    stats = cleanup_duplicate_symbols(valid_binance_pairs)
    
    # Step 3: Deactivate invalid symbols
    print("\n[3/3] Deactivating invalid symbols...")
    invalid_count = deactivate_invalid_symbols(valid_binance_pairs)
    
    # Summary
    print("\n" + "=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"Symbols deactivated: {stats['deactivated'] + invalid_count}")
    print(f"Symbols deleted: {stats['deleted']}")
    print(f"Symbols kept: {stats['kept']}")
    
    # Show active symbol count
    active_count = Symbol.objects.filter(
        symbol_type='CRYPTO',
        is_crypto_symbol=True,
        is_active=True
    ).count()
    print(f"\nActive crypto symbols remaining: {active_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()

