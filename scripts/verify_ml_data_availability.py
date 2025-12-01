#!/usr/bin/env python
"""
Verify Data Availability for ML Model Training
Checks if we have sufficient historical data for training ML models
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal
from apps.data.models import MarketData, TechnicalIndicator
from apps.sentiment.models import SentimentAggregate, NewsArticle, CryptoMention
from django.db.models import Count, Q

def verify_data_availability():
    """Verify all required data for ML training"""
    print("=" * 60)
    print("ML MODEL TRAINING - DATA AVAILABILITY CHECK")
    print("=" * 60)
    print()
    
    results = {
        'symbols': False,
        'signals': False,
        'market_data': False,
        'technical_indicators': False,
        'sentiment': False,
        'news': False,
    }
    
    # 1. Check Symbols
    print("1. Checking Symbols...")
    active_symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True)
    symbol_count = active_symbols.count()
    print(f"   Active crypto symbols: {symbol_count}")
    if symbol_count > 0:
        results['symbols'] = True
        print(f"   ✅ Symbols available: {', '.join([s.symbol for s in active_symbols[:10]])}")
        if symbol_count > 10:
            print(f"   ... and {symbol_count - 10} more")
    else:
        print("   ❌ No active crypto symbols found")
    print()
    
    # 2. Check Trading Signals
    print("2. Checking Trading Signals...")
    total_signals = TradingSignal.objects.count()
    executed_signals = TradingSignal.objects.filter(is_executed=True).count()
    
    # Check signals in last 90 days
    end_date = timezone.now()
    start_date = end_date - timedelta(days=90)
    recent_signals = TradingSignal.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).count()
    
    print(f"   Total signals: {total_signals}")
    print(f"   Executed signals: {executed_signals}")
    print(f"   Signals in last 90 days: {recent_signals}")
    
    if total_signals >= 100:
        results['signals'] = True
        print(f"   ✅ Sufficient signals for training ({total_signals} total)")
    elif total_signals >= 50:
        results['signals'] = True
        print(f"   ⚠️  Minimum signals available ({total_signals} total, recommend 100+)")
    else:
        print(f"   ❌ Insufficient signals for training (need at least 50, have {total_signals})")
    print()
    
    # 3. Check Market Data
    print("3. Checking Market Data...")
    total_market_data = MarketData.objects.count()
    
    # Check recent market data
    recent_market_data = MarketData.objects.filter(
        timestamp__gte=start_date
    ).count()
    
    symbols_with_data = MarketData.objects.values('symbol').distinct().count()
    
    print(f"   Total market data records: {total_market_data}")
    print(f"   Market data in last 90 days: {recent_market_data}")
    print(f"   Symbols with market data: {symbols_with_data}")
    
    if total_market_data >= 1000:
        results['market_data'] = True
        print(f"   ✅ Sufficient market data ({total_market_data} records)")
    elif total_market_data >= 500:
        results['market_data'] = True
        print(f"   ⚠️  Minimum market data available ({total_market_data} records)")
    else:
        print(f"   ❌ Insufficient market data (need at least 500, have {total_market_data})")
    print()
    
    # 4. Check Technical Indicators
    print("4. Checking Technical Indicators...")
    total_indicators = TechnicalIndicator.objects.count()
    
    # Check by indicator type
    rsi_count = TechnicalIndicator.objects.filter(indicator_type='RSI').count()
    macd_count = TechnicalIndicator.objects.filter(indicator_type='MACD').count()
    sma_count = TechnicalIndicator.objects.filter(indicator_type='SMA').count()
    
    print(f"   Total technical indicators: {total_indicators}")
    print(f"   RSI indicators: {rsi_count}")
    print(f"   MACD indicators: {macd_count}")
    print(f"   SMA indicators: {sma_count}")
    
    if total_indicators >= 500:
        results['technical_indicators'] = True
        print(f"   ✅ Sufficient technical indicators ({total_indicators} records)")
    elif total_indicators >= 200:
        results['technical_indicators'] = True
        print(f"   ⚠️  Minimum technical indicators available ({total_indicators} records)")
    else:
        print(f"   ❌ Insufficient technical indicators (need at least 200, have {total_indicators})")
    print()
    
    # 5. Check Sentiment Data
    print("5. Checking Sentiment Data...")
    total_sentiment = SentimentAggregate.objects.count()
    recent_sentiment = SentimentAggregate.objects.filter(
        created_at__gte=start_date
    ).count()
    
    print(f"   Total sentiment records: {total_sentiment}")
    print(f"   Sentiment in last 90 days: {recent_sentiment}")
    
    if total_sentiment >= 100:
        results['sentiment'] = True
        print(f"   ✅ Sufficient sentiment data ({total_sentiment} records)")
    elif total_sentiment >= 50:
        results['sentiment'] = True
        print(f"   ⚠️  Minimum sentiment data available ({total_sentiment} records)")
    else:
        print(f"   ⚠️  Limited sentiment data ({total_sentiment} records) - will use defaults")
    print()
    
    # 6. Check News Articles
    print("6. Checking News Articles...")
    total_news = NewsArticle.objects.count()
    recent_news = NewsArticle.objects.filter(
        published_at__gte=start_date
    ).count()
    
    crypto_mentions = CryptoMention.objects.count()
    
    print(f"   Total news articles: {total_news}")
    print(f"   News in last 90 days: {recent_news}")
    print(f"   Crypto mentions: {crypto_mentions}")
    
    if total_news >= 100:
        results['news'] = True
        print(f"   ✅ Sufficient news data ({total_news} articles)")
    elif total_news >= 50:
        results['news'] = True
        print(f"   ⚠️  Minimum news data available ({total_news} articles)")
    else:
        print(f"   ⚠️  Limited news data ({total_news} articles) - will use defaults")
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_critical = results['symbols'] and results['signals'] and results['market_data']
    all_available = all(results.values())
    
    if all_critical:
        print("✅ CRITICAL DATA: All available")
        print("   - Symbols: ✅")
        print("   - Signals: ✅")
        print("   - Market Data: ✅")
    else:
        print("❌ CRITICAL DATA: Some missing")
        if not results['symbols']:
            print("   - Symbols: ❌")
        if not results['signals']:
            print("   - Signals: ❌")
        if not results['market_data']:
            print("   - Market Data: ❌")
    
    print()
    print("SUPPLEMENTARY DATA:")
    print(f"   - Technical Indicators: {'✅' if results['technical_indicators'] else '⚠️'}")
    print(f"   - Sentiment Data: {'✅' if results['sentiment'] else '⚠️'}")
    print(f"   - News Articles: {'✅' if results['news'] else '⚠️'}")
    print()
    
    if all_critical:
        print("✅ READY FOR ML MODEL TRAINING")
        print()
        print("Next Steps:")
        print("1. Proceed to Phase 2: Feature Engineering Service")
        print("2. Create MLFeatureEngineeringService")
        print("3. Test feature extraction")
    else:
        print("❌ NOT READY - Need to collect more data")
        print()
        print("Recommendations:")
        if not results['signals']:
            print("- Run signal generation to create more historical signals")
        if not results['market_data']:
            print("- Run update_all_coins.py to collect market data")
        if not results['technical_indicators']:
            print("- Ensure technical indicators are being calculated")
    
    print("=" * 60)
    
    return all_critical

if __name__ == '__main__':
    verify_data_availability()

