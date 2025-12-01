#!/usr/bin/env python3
"""
Data Verification Script
Verifies the accuracy and completeness of imported crypto data
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.data.models import MarketData
from apps.trading.models import Symbol

class DataVerifier:
    def __init__(self):
        self.start_date = datetime(2020, 1, 1)
        self.end_date = datetime(2025, 10, 14)
        
    def verify_symbol_data(self, symbol):
        """Verify data for a specific symbol"""
        print(f"\nVerifying data for {symbol.symbol}...")
        
        # Get all records for this symbol
        records = MarketData.objects.filter(
            symbol=symbol,
            timeframe='1d'
        ).order_by('timestamp')
        
        if not records.exists():
            print(f"  ❌ No data found for {symbol.symbol}")
            return False
        
        # Check date range
        first_record = records.first()
        last_record = records.last()
        
        print(f"  📅 Date range: {first_record.timestamp.date()} to {last_record.timestamp.date()}")
        
        # Check for data gaps
        expected_days = (self.end_date - self.start_date).days
        actual_records = records.count()
        
        print(f"  📊 Records: {actual_records} (Expected: ~{expected_days})")
        
        # Check for missing days
        gaps = self.find_data_gaps(records)
        if gaps:
            print(f"  ⚠️  Found {len(gaps)} data gaps")
            for gap in gaps[:5]:  # Show first 5 gaps
                print(f"    Missing: {gap}")
        else:
            print(f"  ✅ No data gaps found")
        
        # Check price ranges
        self.check_price_ranges(records)
        
        return True
    
    def find_data_gaps(self, records):
        """Find gaps in the data"""
        gaps = []
        prev_date = None
        
        for record in records:
            current_date = record.timestamp.date()
            
            if prev_date:
                expected_date = prev_date + timedelta(days=1)
                while expected_date < current_date:
                    gaps.append(expected_date)
                    expected_date += timedelta(days=1)
            
            prev_date = current_date
        
        return gaps
    
    def check_price_ranges(self, records):
        """Check if price ranges are reasonable"""
        prices = [r.close_price for r in records if r.close_price]
        
        if not prices:
            print(f"  ❌ No price data found")
            return
        
        min_price = min(prices)
        max_price = max(prices)
        
        print(f"  💰 Price range: ${min_price:.2f} - ${max_price:.2f}")
        
        # Check for suspicious values (prices that are too low or too high)
        suspicious_low = [p for p in prices if p < Decimal('0.01')]
        suspicious_high = [p for p in prices if p > Decimal('100000')]
        
        if suspicious_low:
            print(f"  ⚠️  Found {len(suspicious_low)} suspiciously low prices")
        if suspicious_high:
            print(f"  ⚠️  Found {len(suspicious_high)} suspiciously high prices")
        
        if not suspicious_low and not suspicious_high:
            print(f"  ✅ Price ranges look reasonable")
    
    def verify_specific_date(self, symbol_name, target_date):
        """Verify data for a specific symbol and date"""
        try:
            symbol = Symbol.objects.get(symbol=symbol_name)
            target_datetime = datetime.strptime(target_date, '%Y-%m-%d')
            
            record = MarketData.objects.filter(
                symbol=symbol,
                timestamp__date=target_datetime.date(),
                timeframe='1d'
            ).first()
            
            if record:
                print(f"\n📊 {symbol_name} on {target_date}:")
                print(f"  Open:  ${record.open_price}")
                print(f"  High:  ${record.high_price}")
                print(f"  Low:   ${record.low_price}")
                print(f"  Close: ${record.close_price}")
                print(f"  Volume: {record.volume:,.0f}")
                return True
            else:
                print(f"❌ No data found for {symbol_name} on {target_date}")
                return False
                
        except Symbol.DoesNotExist:
            print(f"❌ Symbol {symbol_name} not found in database")
            return False
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report"""
        print("\n" + "="*60)
        print("DATA VERIFICATION SUMMARY REPORT")
        print("="*60)
        
        # Get all USDT symbols
        usdt_symbols = Symbol.objects.filter(symbol__endswith='USDT').exclude(symbol='USDT')
        
        total_symbols = usdt_symbols.count()
        symbols_with_data = 0
        total_records = 0
        
        print(f"\n📈 Total USDT symbols: {total_symbols}")
        
        for symbol in usdt_symbols:
            records = MarketData.objects.filter(symbol=symbol, timeframe='1d')
            if records.exists():
                symbols_with_data += 1
                total_records += records.count()
        
        print(f"📊 Symbols with data: {symbols_with_data}/{total_symbols}")
        print(f"📋 Total records: {total_records:,}")
        
        if symbols_with_data == total_symbols:
            print("✅ All symbols have data")
        else:
            print(f"⚠️  {total_symbols - symbols_with_data} symbols missing data")
        
        # Check data source
        sources = MarketData.objects.values('source__name').distinct()
        print(f"\n🔗 Data sources:")
        for source in sources:
            count = MarketData.objects.filter(source__name=source['source__name']).count()
            print(f"  - {source['source__name']}: {count:,} records")

def main():
    """Main verification function"""
    verifier = DataVerifier()
    
    print("=== CRYPTO DATA VERIFICATION ===")
    print(f"Verifying data from {verifier.start_date.date()} to {verifier.end_date.date()}")
    
    # Generate summary report
    verifier.generate_summary_report()
    
    # Verify specific symbols
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
    
    print(f"\n🔍 Detailed verification for test symbols:")
    for symbol_name in test_symbols:
        try:
            symbol = Symbol.objects.get(symbol=symbol_name)
            verifier.verify_symbol_data(symbol)
        except Symbol.DoesNotExist:
            print(f"❌ Symbol {symbol_name} not found")
    
    # Verify specific dates
    print(f"\n📅 Verifying specific dates:")
    test_dates = ['2022-01-01', '2023-01-01', '2024-01-01']
    
    for date in test_dates:
        print(f"\n--- {date} ---")
        for symbol_name in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
            verifier.verify_specific_date(symbol_name, date)

if __name__ == "__main__":
    main()
