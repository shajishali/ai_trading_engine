#!/usr/bin/env python
"""Verify data import"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.db import connection

print("=" * 60)
print("Step 10: Data Import Verification")
print("=" * 60)
print()

cursor = connection.cursor()

# Check key tables
tables_to_check = {
    'data_marketdata': 'Market Data',
    'signals_tradingsignal': 'Trading Signals',
    'signals_spottradingsignal': 'Spot Trading Signals',
    'signals_marketregime': 'Market Regime',
    'data_technicalindicator': 'Technical Indicators',
    'auth_user': 'Users',
    'trading_symbol': 'Trading Symbols',
}

all_good = True
for table, description in tables_to_check.items():
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"✓ {description:30} {count:>12,} rows")
        else:
            print(f"✗ {description:30} {count:>12,} rows (empty)")
            all_good = False
    except Exception as e:
        print(f"✗ {description:30} Error: {str(e)[:50]}")
        all_good = False

cursor.close()

print()
print("=" * 60)
if all_good:
    print("✓ All key tables have data!")
    print("Step 10 is COMPLETE!")
else:
    print("⚠ Some tables are empty or have errors")
print("=" * 60)






