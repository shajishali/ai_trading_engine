#!/usr/bin/env python
"""
Batch import TradingView CSV exports

Usage:
    python scripts/batch_import_tradingview.py --directory path/to/csv/files
    python scripts/batch_import_tradingview.py --directory csv_exports --timeframe 1h
"""
import os
import sys
import django
import argparse
import re

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.trading.models import Symbol
from apps.data.tradingview_web_service import TradingViewDataImporter

def extract_symbol_from_filename(filename: str) -> str:
    """
    Extract symbol from filename
    
    Examples:
        BTCUSDT_1h.csv -> BTC
        ETHUSDT_4h.csv -> ETH
        BTC_2024-01-01.csv -> BTC
    """
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    # Try to extract symbol (remove USDT, timeframe, dates)
    # Pattern: SYMBOLUSDT_TIMEFRAME or SYMBOL_DATE
    patterns = [
        r'^([A-Z]+)USDT',  # BTCUSDT
        r'^([A-Z]+)_',     # BTC_
        r'^([A-Z]+)',      # BTC
    ]
    
    for pattern in patterns:
        match = re.match(pattern, name.upper())
        if match:
            return match.group(1)
    
    return name.upper().split('_')[0]

def batch_import_tradingview_csvs(directory: str, timeframe: str = '1h'):
    """
    Import all TradingView CSV files from a directory
    
    Args:
        directory: Directory containing CSV files
        timeframe: Timeframe for all files (default: 1h)
    """
    print("=" * 60)
    print("BATCH TRADINGVIEW CSV IMPORT")
    print("=" * 60)
    print(f"Directory: {directory}")
    print(f"Timeframe: {timeframe}")
    print("=" * 60)
    
    if not os.path.exists(directory):
        print(f"ERROR: Directory not found: {directory}")
        return False
    
    # Get all CSV files
    csv_files = [f for f in os.listdir(directory) if f.lower().endswith('.csv')]
    
    if not csv_files:
        print(f"No CSV files found in {directory}")
        return False
    
    print(f"\nFound {len(csv_files)} CSV file(s)")
    print("-" * 60)
    
    importer = TradingViewDataImporter()
    total_imported = 0
    successful = 0
    failed = 0
    
    for filename in csv_files:
        filepath = os.path.join(directory, filename)
        
        # Extract symbol from filename
        symbol_str = extract_symbol_from_filename(filename)
        
        print(f"\n[{successful + failed + 1}/{len(csv_files)}] Processing: {filename}")
        print(f"  Detected symbol: {symbol_str}")
        
        try:
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
                print(f"  ✓ Created new symbol: {symbol_obj.symbol}")
            else:
                print(f"  ✓ Using existing symbol: {symbol_obj.symbol}")
            
            # Import CSV
            saved_count = importer.import_csv_to_database(
                csv_file_path=filepath,
                symbol_obj=symbol_obj,
                timeframe=timeframe
            )
            
            if saved_count > 0:
                print(f"  ✓ Imported {saved_count} records")
                total_imported += saved_count
                successful += 1
            else:
                print(f"  ⚠ No new records imported (may already exist)")
                successful += 1  # Still count as success
                
        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("BATCH IMPORT SUMMARY")
    print("=" * 60)
    print(f"Total files processed: {len(csv_files)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total records imported: {total_imported}")
    print("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Batch import TradingView CSV exports'
    )
    parser.add_argument(
        '--directory',
        type=str,
        required=True,
        help='Directory containing CSV files'
    )
    parser.add_argument(
        '--timeframe',
        type=str,
        default='1h',
        choices=['1m', '5m', '15m', '1h', '4h', '1d'],
        help='Timeframe for all files (default: 1h)'
    )
    
    args = parser.parse_args()
    
    success = batch_import_tradingview_csvs(
        directory=args.directory,
        timeframe=args.timeframe
    )
    
    if success:
        print("\n✅ Batch import completed successfully!")
    else:
        print("\n❌ Some imports failed. Check the error messages above.")
        sys.exit(1)

