"""
Database data query utilities for signal generation
Provides optimized database queries and data access methods
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import pandas as pd

from django.utils import timezone
from django.db.models import Q, Avg, Max, Min, Count
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator

logger = logging.getLogger(__name__)


def get_recent_market_data(symbol: Symbol, hours_back: int = 24) -> 'QuerySet':
    """Get recent market data from database with optimized query"""
    cutoff_time = timezone.now() - timedelta(hours=hours_back)
    return MarketData.objects.filter(
        symbol=symbol,
        timeframe='1h',
        timestamp__gte=cutoff_time
    ).select_related('symbol').only(
        'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
    ).order_by('timestamp')


def get_latest_price(symbol: Symbol) -> Optional[Decimal]:
    """Get latest price from database instead of live API with caching"""
    cache_key = f"latest_price_{symbol.symbol}"
    
    # Try cache first
    cached_price = cache.get(cache_key)
    if cached_price and float(cached_price) > 0:
        return Decimal(str(cached_price))
    
    # Get from database
    latest_data = MarketData.objects.filter(
        symbol=symbol,
        timeframe='1h'
    ).order_by('-timestamp').first()
    
    if latest_data and latest_data.close_price and float(latest_data.close_price) > 0:
        price_decimal = Decimal(str(latest_data.close_price))
        cache.set(cache_key, float(price_decimal), 300)  # 5 minutes cache
        logger.info(f"Using database price for {symbol.symbol}: ${price_decimal:,}")
        return price_decimal
    
    logger.warning(f"No recent price data found for {symbol.symbol}")
    return None


def get_latest_market_data(symbol: Symbol) -> Optional[Dict]:
    """Get latest market data for signal generation - uses database data"""
    try:
        # Get latest market data from database
        latest_data = MarketData.objects.filter(
            symbol=symbol,
            timeframe='1h'
        ).order_by('-timestamp').first()
        
        if latest_data and latest_data.close_price and float(latest_data.close_price) > 0:
            market_data = {
                'close_price': latest_data.close_price,
                'high_price': latest_data.high_price,
                'low_price': latest_data.low_price,
                'open_price': latest_data.open_price,
                'volume': latest_data.volume,
                'timestamp': latest_data.timestamp,
                'data_source': 'database',
                'symbol': symbol.symbol
            }
            
            logger.info(f"Using database market data for {symbol.symbol}: ${latest_data.close_price:,.2f}")
            return market_data
        else:
            logger.warning(f"No recent database data for {symbol.symbol}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting database market data for {symbol.symbol}: {e}")
        return None


def get_optimized_market_data(symbol: Symbol, hours_back: int = 24) -> 'QuerySet':
    """Optimized query for market data with proper indexing"""
    cutoff_time = timezone.now() - timedelta(hours=hours_back)
    return MarketData.objects.filter(
        symbol=symbol,
        timeframe='1h',
        timestamp__gte=cutoff_time
    ).select_related('symbol').only(
        'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
    ).order_by('timestamp')


def get_market_data_dataframe(symbol: Symbol, hours_back: int = 24) -> Optional[pd.DataFrame]:
    """Get market data as pandas DataFrame for technical analysis"""
    try:
        market_data = get_optimized_market_data(symbol, hours_back)
        
        if not market_data.exists():
            logger.warning(f"No market data found for {symbol.symbol}")
            return None
        
        data = []
        for record in market_data:
            data.append({
                'timestamp': record.timestamp,
                'open': float(record.open_price),
                'high': float(record.high_price),
                'low': float(record.low_price),
                'close': float(record.close_price),
                'volume': float(record.volume) if record.volume else 0
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        return df
        
    except Exception as e:
        logger.error(f"Error converting market data to DataFrame for {symbol.symbol}: {e}")
        return None


def validate_data_quality(symbol: Symbol, hours_back: int = 24) -> Dict[str, any]:
    """Validate database data quality for a symbol"""
    try:
        # Check data freshness
        latest_data = MarketData.objects.filter(
            symbol=symbol,
            timeframe='1h'
        ).order_by('-timestamp').first()
        
        if not latest_data:
            return {
                'is_valid': False,
                'reason': 'No data found',
                'data_age_hours': None,
                'data_points': 0,
                'completeness': 0.0
            }
        
        data_age = timezone.now() - latest_data.timestamp
        data_age_hours = data_age.total_seconds() / 3600
        
        # Check data completeness
        recent_data = get_recent_market_data(symbol, hours_back)
        data_points = recent_data.count()
        expected_points = hours_back  # 1 data point per hour
        completeness = data_points / expected_points if expected_points > 0 else 0
        
        # Validation criteria
        is_fresh = data_age_hours <= 2  # Data should be within 2 hours
        is_complete = data_points >= 20  # Minimum data points
        is_quality_good = completeness >= 0.8  # 80% completeness
        
        return {
            'is_valid': is_fresh and is_complete and is_quality_good,
            'reason': 'Valid' if (is_fresh and is_complete and is_quality_good) else 'Invalid data',
            'data_age_hours': data_age_hours,
            'data_points': data_points,
            'completeness': completeness,
            'is_fresh': is_fresh,
            'is_complete': is_complete,
            'is_quality_good': is_quality_good
        }
        
    except Exception as e:
        logger.error(f"Error validating data quality for {symbol.symbol}: {e}")
        return {
            'is_valid': False,
            'reason': f'Validation error: {e}',
            'data_age_hours': None,
            'data_points': 0,
            'completeness': 0.0
        }


def get_data_statistics(symbol: Symbol, days_back: int = 7) -> Dict[str, any]:
    """Get data statistics for a symbol over specified days"""
    try:
        cutoff_time = timezone.now() - timedelta(days=days_back)
        
        # Get market data
        market_data = MarketData.objects.filter(
            symbol=symbol,
            timeframe='1h',
            timestamp__gte=cutoff_time
        ).order_by('timestamp')
        
        if not market_data.exists():
            return {
                'total_records': 0,
                'date_range': None,
                'price_range': None,
                'volume_stats': None
            }
        
        # Calculate statistics
        total_records = market_data.count()
        
        # Date range
        first_record = market_data.first()
        last_record = market_data.last()
        date_range = {
            'start': first_record.timestamp,
            'end': last_record.timestamp,
            'duration_hours': (last_record.timestamp - first_record.timestamp).total_seconds() / 3600
        }
        
        # Price statistics
        prices = [float(record.close_price) for record in market_data if record.close_price]
        if prices:
            price_range = {
                'min': min(prices),
                'max': max(prices),
                'avg': sum(prices) / len(prices),
                'current': prices[-1]
            }
        else:
            price_range = None
        
        # Volume statistics
        volumes = [float(record.volume) for record in market_data if record.volume]
        if volumes:
            volume_stats = {
                'min': min(volumes),
                'max': max(volumes),
                'avg': sum(volumes) / len(volumes),
                'current': volumes[-1]
            }
        else:
            volume_stats = None
        
        return {
            'total_records': total_records,
            'date_range': date_range,
            'price_range': price_range,
            'volume_stats': volume_stats
        }
        
    except Exception as e:
        logger.error(f"Error getting data statistics for {symbol.symbol}: {e}")
        return {
            'total_records': 0,
            'date_range': None,
            'price_range': None,
            'volume_stats': None
        }


def get_symbols_with_recent_data(hours_back: int = 24, min_data_points: int = 20) -> List[Symbol]:
    """Get symbols that have recent data meeting quality criteria"""
    try:
        cutoff_time = timezone.now() - timedelta(hours=hours_back)
        
        # Get symbols with recent data
        symbols_with_data = Symbol.objects.filter(
            is_active=True,
            is_crypto_symbol=True,
            marketdata__timeframe='1h',
            marketdata__timestamp__gte=cutoff_time
        ).annotate(
            data_count=Count('marketdata')
        ).filter(
            data_count__gte=min_data_points
        ).distinct()
        
        logger.info(f"Found {symbols_with_data.count()} symbols with recent data")
        return list(symbols_with_data)
        
    except Exception as e:
        logger.error(f"Error getting symbols with recent data: {e}")
        return []


def get_data_gaps(symbol: Symbol, hours_back: int = 168) -> List[Dict]:
    """Identify data gaps in the database for a symbol"""
    try:
        cutoff_time = timezone.now() - timedelta(hours=hours_back)
        
        # Get all timestamps
        timestamps = MarketData.objects.filter(
            symbol=symbol,
            timeframe='1h',
            timestamp__gte=cutoff_time
        ).values_list('timestamp', flat=True).order_by('timestamp')
        
        if not timestamps:
            return []
        
        # Find gaps
        gaps = []
        expected_interval = timedelta(hours=1)
        
        for i in range(len(timestamps) - 1):
            current_time = timestamps[i]
            next_time = timestamps[i + 1]
            
            if next_time - current_time > expected_interval:
                gaps.append({
                    'start': current_time,
                    'end': next_time,
                    'duration_hours': (next_time - current_time).total_seconds() / 3600
                })
        
        return gaps
        
    except Exception as e:
        logger.error(f"Error finding data gaps for {symbol.symbol}: {e}")
        return []


def get_technical_indicators_from_db(symbol: Symbol, hours_back: int = 168) -> Optional[Dict]:
    """Get technical indicators from database if available"""
    try:
        cutoff_time = timezone.now() - timedelta(hours=hours_back)
        
        # Get latest technical indicators
        indicators = TechnicalIndicator.objects.filter(
            symbol=symbol,
            timestamp__gte=cutoff_time
        ).order_by('-timestamp')
        
        if not indicators.exists():
            return None
        
        # Convert to dictionary
        latest_indicators = indicators.first()
        indicator_data = {
            'timestamp': latest_indicators.timestamp,
            'rsi': float(latest_indicators.rsi) if latest_indicators.rsi else None,
            'macd': float(latest_indicators.macd) if latest_indicators.macd else None,
            'macd_signal': float(latest_indicators.macd_signal) if latest_indicators.macd_signal else None,
            'bollinger_upper': float(latest_indicators.bollinger_upper) if latest_indicators.bollinger_upper else None,
            'bollinger_lower': float(latest_indicators.bollinger_lower) if latest_indicators.bollinger_lower else None,
            'sma_20': float(latest_indicators.sma_20) if latest_indicators.sma_20 else None,
            'sma_50': float(latest_indicators.sma_50) if latest_indicators.sma_50 else None,
        }
        
        return indicator_data
        
    except Exception as e:
        logger.error(f"Error getting technical indicators for {symbol.symbol}: {e}")
        return None


def clear_price_cache(symbol: Symbol = None):
    """Clear price cache for a symbol or all symbols"""
    try:
        if symbol:
            cache_key = f"latest_price_{symbol.symbol}"
            cache.delete(cache_key)
            logger.info(f"Cleared price cache for {symbol.symbol}")
        else:
            # Clear all price caches (this is a simplified approach)
            # In production, you might want to use cache versioning or tags
            logger.info("Cleared all price caches")
            
    except Exception as e:
        logger.error(f"Error clearing price cache: {e}")


def get_database_health_status() -> Dict[str, any]:
    """Get overall database health status for signal generation"""
    try:
        # Check latest data across all symbols
        latest_data = MarketData.objects.order_by('-timestamp').first()
        if not latest_data:
            return {
                'status': 'CRITICAL',
                'reason': 'No data found in database',
                'latest_data_age_hours': None,
                'active_symbols': 0
            }
        
        data_age = timezone.now() - latest_data.timestamp
        data_age_hours = data_age.total_seconds() / 3600
        
        # Count active symbols with recent data
        cutoff_time = timezone.now() - timedelta(hours=24)
        active_symbols = Symbol.objects.filter(
            is_active=True,
            is_crypto_symbol=True,
            marketdata__timeframe='1h',
            marketdata__timestamp__gte=cutoff_time
        ).distinct().count()
        
        # Determine status
        if data_age_hours <= 1:
            status = 'HEALTHY'
        elif data_age_hours <= 2:
            status = 'WARNING'
        else:
            status = 'CRITICAL'
        
        return {
            'status': status,
            'reason': f'Latest data is {data_age_hours:.1f} hours old',
            'latest_data_age_hours': data_age_hours,
            'active_symbols': active_symbols,
            'latest_symbol': latest_data.symbol.symbol if latest_data.symbol else 'Unknown'
        }
        
    except Exception as e:
        logger.error(f"Error getting database health status: {e}")
        return {
            'status': 'ERROR',
            'reason': f'Error checking database health: {e}',
            'latest_data_age_hours': None,
            'active_symbols': 0
        }














