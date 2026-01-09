#!/usr/bin/env python
"""
Diagnostic script for signal generation issues in deployment
Run this script on the server to diagnose signal generation problems

Usage:
    python manage.py shell < scripts/diagnose_signal_generation.py
    OR
    python scripts/diagnose_signal_generation.py (if run from backend directory)
"""

import os
import sys
import django

# Setup Django
if __name__ == "__main__":
    # Try to find manage.py and set up Django
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, backend_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings_production')
    django.setup()

from django.db import connection, connections
from django.conf import settings
from apps.trading.models import Symbol
from apps.signals.services import SignalGenerationService
from apps.data.models import MarketData, TechnicalIndicator
import traceback

def test_database_connection():
    """Test database connection"""
    print("=" * 60)
    print("1. Testing Database Connection")
    print("=" * 60)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                print("✓ Database connection: OK")
                return True
            else:
                print("✗ Database connection: FAILED (no result)")
                return False
    except Exception as e:
        print(f"✗ Database connection: FAILED - {e}")
        return False

def test_symbol_retrieval():
    """Test if symbols can be retrieved"""
    print("\n" + "=" * 60)
    print("2. Testing Symbol Retrieval")
    print("=" * 60)
    try:
        # Test BTC symbol
        btc = Symbol.objects.filter(symbol__iexact='BTC').first()
        if btc:
            print(f"✓ Symbol 'BTC' found: {btc.symbol} (Active: {btc.is_active})")
            return btc
        else:
            print("✗ Symbol 'BTC' not found")
            # Try to find any active symbol
            any_symbol = Symbol.objects.filter(is_active=True).first()
            if any_symbol:
                print(f"  Found alternative symbol: {any_symbol.symbol}")
                return any_symbol
            return None
    except Exception as e:
        print(f"✗ Symbol retrieval failed: {e}")
        traceback.print_exc()
        return None

def test_market_data(symbol):
    """Test if market data exists for symbol"""
    print("\n" + "=" * 60)
    print("3. Testing Market Data Availability")
    print("=" * 60)
    if not symbol:
        print("✗ Cannot test market data - no symbol available")
        return False
    
    try:
        market_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp').first()
        if market_data:
            print(f"✓ Market data found for {symbol.symbol}")
            print(f"  Latest price: ${market_data.close_price}")
            print(f"  Timestamp: {market_data.timestamp}")
            return True
        else:
            print(f"✗ No market data found for {symbol.symbol}")
            print("  This may cause signal generation to fail")
            return False
    except Exception as e:
        print(f"✗ Market data check failed: {e}")
        traceback.print_exc()
        return False

def test_technical_indicators(symbol):
    """Test if technical indicators exist"""
    print("\n" + "=" * 60)
    print("4. Testing Technical Indicators")
    print("=" * 60)
    if not symbol:
        print("✗ Cannot test indicators - no symbol available")
        return False
    
    try:
        indicators = TechnicalIndicator.objects.filter(symbol=symbol).order_by('-timestamp').first()
        if indicators:
            print(f"✓ Technical indicators found for {symbol.symbol}")
            return True
        else:
            print(f"⚠ No technical indicators found for {symbol.symbol}")
            print("  Signal generation may still work but with limited data")
            return False
    except Exception as e:
        print(f"✗ Technical indicators check failed: {e}")
        return False

def test_signal_generation_service(symbol):
    """Test signal generation service"""
    print("\n" + "=" * 60)
    print("5. Testing Signal Generation Service")
    print("=" * 60)
    if not symbol:
        print("✗ Cannot test signal generation - no symbol available")
        return False
    
    try:
        print(f"Attempting to generate signals for {symbol.symbol}...")
        signal_service = SignalGenerationService()
        signals = signal_service.generate_signals_for_symbol(symbol)
        
        if signals:
            print(f"✓ Signal generation successful: {len(signals)} signals generated")
            for i, signal in enumerate(signals[:3], 1):  # Show first 3
                print(f"  Signal {i}: {signal.signal_type.name} - Confidence: {signal.confidence_score:.2%}")
            return True
        else:
            print(f"⚠ Signal generation completed but no signals were generated for {symbol.symbol}")
            print("  This may be normal if no trading opportunities are detected")
            return True  # Not necessarily an error
    except Exception as e:
        print(f"✗ Signal generation failed: {e}")
        traceback.print_exc()
        return False

def test_cache():
    """Test cache configuration"""
    print("\n" + "=" * 60)
    print("6. Testing Cache Configuration")
    print("=" * 60)
    try:
        from django.core.cache import cache
        cache.set('test_key', 'test_value', 10)
        value = cache.get('test_key')
        if value == 'test_value':
            print("✓ Cache is working")
            cache.delete('test_key')
            return True
        else:
            print("✗ Cache test failed - value mismatch")
            return False
    except Exception as e:
        print(f"✗ Cache test failed: {e}")
        print("  Cache may not be configured properly")
        return False

def check_settings():
    """Check important settings"""
    print("\n" + "=" * 60)
    print("7. Checking Settings")
    print("=" * 60)
    print(f"DEBUG: {settings.DEBUG}")
    print(f"Database Engine: {settings.DATABASES['default']['ENGINE']}")
    print(f"Cache Backend: {settings.CACHES.get('default', {}).get('BACKEND', 'Not configured')}")
    
    # Check if production settings are being used
    if hasattr(settings, 'DJANGO_SETTINGS_MODULE'):
        print(f"Settings Module: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')}")
    
    return True

def main():
    """Run all diagnostic tests"""
    print("\n" + "=" * 60)
    print("SIGNAL GENERATION DIAGNOSTIC TOOL")
    print("=" * 60)
    print("\nThis script will test various components needed for signal generation.\n")
    
    results = {
        'database': test_database_connection(),
        'symbol': test_symbol_retrieval(),
        'market_data': False,
        'indicators': False,
        'signal_generation': False,
        'cache': test_cache(),
        'settings': check_settings()
    }
    
    if results['symbol']:
        results['market_data'] = test_market_data(results['symbol'])
        results['indicators'] = test_technical_indicators(results['symbol'])
        results['signal_generation'] = test_signal_generation_service(results['symbol'])
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"Database Connection: {'✓ PASS' if results['database'] else '✗ FAIL'}")
    print(f"Symbol Retrieval: {'✓ PASS' if results['symbol'] else '✗ FAIL'}")
    print(f"Market Data: {'✓ PASS' if results['market_data'] else '✗ FAIL'}")
    print(f"Technical Indicators: {'✓ PASS' if results['indicators'] else '⚠ WARNING'}")
    print(f"Signal Generation: {'✓ PASS' if results['signal_generation'] else '✗ FAIL'}")
    print(f"Cache: {'✓ PASS' if results['cache'] else '✗ FAIL'}")
    print(f"Settings: {'✓ PASS' if results['settings'] else '✗ FAIL'}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if not results['database']:
        print("1. Fix database connection issues")
        print("   - Check database server is running")
        print("   - Verify database credentials in settings")
        print("   - Check network connectivity")
    
    if not results['symbol']:
        print("2. Ensure symbols are populated in database")
        print("   - Run: python manage.py populate_symbols")
        print("   - Or import symbols from your data source")
    
    if not results['market_data']:
        print("3. Update market data")
        print("   - Run: python manage.py update_all_coins")
        print("   - Or check data import scripts")
    
    if not results['signal_generation']:
        print("4. Signal generation failed - check logs for details")
        print("   - Review error messages above")
        print("   - Check application logs: tail -f logs/errors.log")
    
    if not results['cache']:
        print("5. Configure cache backend")
        print("   - Redis is recommended for production")
        print("   - Check CACHES setting in settings_production.py")
    
    print("\n" + "=" * 60)
    print("Diagnostic complete!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

