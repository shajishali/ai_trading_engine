#!/usr/bin/env python
"""
Script to list all coins with their data counts in the database
"""
import os
import sys
import django

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.trading.models import Symbol
from apps.data.models import MarketData
from django.db.models import Count

def list_coins_with_counts():
    """List all coins with their data counts"""
    
    # Get all symbols with market data and their counts
    symbols_with_data = Symbol.objects.filter(
        symbol_type='CRYPTO',
        is_active=True,
        marketdata__isnull=False
    ).annotate(
        record_count=Count('marketdata')
    ).order_by('-record_count', 'symbol')
    
    total_count = symbols_with_data.count()
    total_records = sum(s.record_count for s in symbols_with_data)
    
    print("=" * 70)
    print(f"ALL COINS WITH DATA IN DATABASE ({total_count} coins, {total_records:,} total records)")
    print("=" * 70)
    print(f"\n{'#':<4} {'Coin':<15} {'Records':<12} {'Percentage':<12}")
    print("-" * 70)
    
    for idx, symbol in enumerate(symbols_with_data, 1):
        percentage = (symbol.record_count / total_records * 100) if total_records > 0 else 0
        print(f"{idx:<4} {symbol.symbol:<15} {symbol.record_count:<12,} {percentage:>10.2f}%")
    
    print("=" * 70)
    print(f"\nTotal: {total_count} coins with {total_records:,} records")
    print("=" * 70)

if __name__ == "__main__":
    list_coins_with_counts()


