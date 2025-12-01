#!/usr/bin/env python
"""
Automated TradingView CSV Import Script

This script monitors a directory for new TradingView CSV exports and
automatically imports them into the database.

Usage:
    python scripts/automated_tradingview_import.py --watch-dir path/to/csv/files
    python scripts/automated_tradingview_import.py --watch-dir csv_exports --interval 60
"""
import os
import sys
import django
import argparse
import time
from pathlib import Path
from datetime import datetime

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.trading.models import Symbol
from apps.data.tradingview_web_service import TradingViewDataImporter
from scripts.batch_import_tradingview import extract_symbol_from_filename

def watch_and_import(watch_directory: str, interval: int = 60, timeframe: str = '1h'):
    """
    Watch directory for new CSV files and import them automatically
    
    Args:
        watch_directory: Directory to watch for CSV files
        interval: Check interval in seconds (default: 60)
        timeframe: Timeframe for imports (default: 1h)
    """
    print("=" * 60)
    print("AUTOMATED TRADINGVIEW CSV IMPORT")
    print("=" * 60)
    print(f"Watching directory: {watch_directory}")
    print(f"Check interval: {interval} seconds")
    print(f"Timeframe: {timeframe}")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")
    
    if not os.path.exists(watch_directory):
        print(f"ERROR: Directory not found: {watch_directory}")
        print(f"Creating directory: {watch_directory}")
        os.makedirs(watch_directory, exist_ok=True)
    
    # Track processed files
    processed_files = set()
    
    # Get initial list of files
    initial_files = set()
    if os.path.exists(watch_directory):
        for f in os.listdir(watch_directory):
            if f.lower().endswith('.csv'):
                initial_files.add(f)
    
    print(f"Found {len(initial_files)} existing CSV file(s) - will skip on first run")
    print("Waiting for new files...\n")
    
    importer = TradingViewDataImporter()
    
    try:
        while True:
            # Check for new files
            if os.path.exists(watch_directory):
                current_files = set()
                for f in os.listdir(watch_directory):
                    if f.lower().endswith('.csv'):
                        current_files.add(f)
                
                # Find new files
                new_files = current_files - processed_files - initial_files
                
                if new_files:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(new_files)} new file(s)")
                    
                    for filename in new_files:
                        filepath = os.path.join(watch_directory, filename)
                        symbol_str = extract_symbol_from_filename(filename)
                        
                        print(f"  Processing: {filename} (Symbol: {symbol_str})")
                        
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
                            
                            # Import CSV
                            saved_count = importer.import_csv_to_database(
                                csv_file_path=filepath,
                                symbol_obj=symbol_obj,
                                timeframe=timeframe
                            )
                            
                            if saved_count > 0:
                                print(f"    ✓ Imported {saved_count} records")
                            else:
                                print(f"    ⚠ No new records (may already exist)")
                            
                            processed_files.add(filename)
                            
                        except Exception as e:
                            print(f"    ✗ ERROR: {str(e)}")
                    
                    print()  # Empty line for readability
                
                # Update initial files after first run
                if not initial_files:
                    initial_files = current_files
            
            # Wait before next check
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Automated TradingView CSV import watcher'
    )
    parser.add_argument(
        '--watch-dir',
        type=str,
        required=True,
        help='Directory to watch for CSV files'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Check interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--timeframe',
        type=str,
        default='1h',
        choices=['1m', '5m', '15m', '1h', '4h', '1d'],
        help='Timeframe for imports (default: 1h)'
    )
    
    args = parser.parse_args()
    
    watch_and_import(
        watch_directory=args.watch_dir,
        interval=args.interval,
        timeframe=args.timeframe
    )

