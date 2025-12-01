#!/usr/bin/env python
"""
Script to import TradingView CSV exports into the database

Usage:
    python scripts/import_tradingview_csv.py --symbol BTC --file path/to/tradingview_export.csv
    python scripts/import_tradingview_csv.py --symbol ETH --file path/to/export.csv --timeframe 1h
"""
import os
import sys
import django
import argparse

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.trading.models import Symbol
from apps.data.tradingview_web_service import TradingViewDataImporter

def import_tradingview_csv(symbol_str: str, csv_file_path: str, timeframe: str = '1h'):
    """
    Import TradingView CSV export into database
    
    Args:
        symbol_str: Symbol name (e.g., BTC, ETH)
        csv_file_path: Path to TradingView CSV export file
        timeframe: Timeframe (1h, 4h, 1d, etc.)
    """
    print("=" * 60)
    print("TRADINGVIEW CSV IMPORT")
    print("=" * 60)
    
    # Check if file exists
    if not os.path.exists(csv_file_path):
        print(f"ERROR: File not found: {csv_file_path}")
        return False
    
    # Get or create symbol
    symbol_obj, created = Symbol.objects.get_or_create(
        symbol=symbol_str.upper(),
        defaults={
            'name': symbol_str.upper(),
            'symbol_type': 'CRYPTO',
            'is_crypto_symbol': True,
            'is_active': True
        }
    )
    
    if created:
        print(f"Created new symbol: {symbol_obj.symbol}")
    else:
        print(f"Using existing symbol: {symbol_obj.symbol}")
    
    # Import CSV
    print(f"\nImporting data from: {csv_file_path}")
    print(f"Timeframe: {timeframe}")
    print("-" * 60)
    
    importer = TradingViewDataImporter()
    saved_count = importer.import_csv_to_database(
        csv_file_path=csv_file_path,
        symbol_obj=symbol_obj,
        timeframe=timeframe
    )
    
    print("-" * 60)
    print(f"IMPORT SUMMARY:")
    print(f"Symbol: {symbol_obj.symbol}")
    print(f"Records imported: {saved_count}")
    print("=" * 60)
    
    return saved_count > 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Import TradingView CSV exports into database'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        required=True,
        help='Symbol name (e.g., BTC, ETH)'
    )
    parser.add_argument(
        '--file',
        type=str,
        required=True,
        help='Path to TradingView CSV export file'
    )
    parser.add_argument(
        '--timeframe',
        type=str,
        default='1h',
        choices=['1m', '5m', '15m', '1h', '4h', '1d'],
        help='Timeframe (default: 1h)'
    )
    
    args = parser.parse_args()
    
    success = import_tradingview_csv(
        symbol_str=args.symbol,
        csv_file_path=args.file,
        timeframe=args.timeframe
    )
    
    if success:
        print("\n✅ Import completed successfully!")
    else:
        print("\n❌ Import failed. Check the error messages above.")
        sys.exit(1)

