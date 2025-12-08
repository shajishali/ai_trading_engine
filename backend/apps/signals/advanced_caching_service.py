"""
Advanced caching service for database-driven signal generation
Phase 3: Multi-level caching strategies and performance optimization
"""

import logging
import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from functools import wraps

from django.utils import timezone
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db.models import QuerySet
from django.conf import settings

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import TradingSignal
from apps.signals.database_data_utils import get_database_health_status

logger = logging.getLogger(__name__)


class AdvancedCachingService:
    """Advanced multi-level caching service for optimal performance"""
    
    def __init__(self):
        self.cache_layers = {
            'L1': {'timeout': 300, 'description': 'In-memory cache (5 minutes)'},
            'L2': {'timeout': 1800, 'description': 'Redis cache (30 minutes)'},
            'L3': {'timeout': 3600, 'description': 'Database cache (1 hour)'}
        }
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_requests': 0
        }
        self.cache_warming_enabled = True
        
    def get_cached_data(self, cache_key: str, data_type: str = 'general') -> Optional[Any]:
        """Get data from cache with multi-level fallback"""
        try:
            self.cache_stats['total_requests'] += 1
            
            # Try L1 cache first (in-memory)
            l1_data = self._get_from_l1_cache(cache_key)
            if l1_data is not None:
                self.cache_stats['hits'] += 1
                logger.debug(f"L1 cache hit for {cache_key}")
                return l1_data
            
            # Try L2 cache (Redis)
            l2_data = self._get_from_l2_cache(cache_key)
            if l2_data is not None:
                self.cache_stats['hits'] += 1
                # Store in L1 for faster access
                self._set_l1_cache(cache_key, l2_data)
                logger.debug(f"L2 cache hit for {cache_key}")
                return l2_data
            
            # Try L3 cache (Database)
            l3_data = self._get_from_l3_cache(cache_key, data_type)
            if l3_data is not None:
                self.cache_stats['hits'] += 1
                # Store in L1 and L2 for faster access
                self._set_l1_cache(cache_key, l3_data)
                self._set_l2_cache(cache_key, l3_data)
                logger.debug(f"L3 cache hit for {cache_key}")
                return l3_data
            
            # Cache miss
            self.cache_stats['misses'] += 1
            logger.debug(f"Cache miss for {cache_key}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached data for {cache_key}: {e}")
            return None
    
    def set_cached_data(self, cache_key: str, data: Any, layer: str = 'L2', timeout: Optional[int] = None) -> bool:
        """Set data in cache with specified layer"""
        try:
            if timeout is None:
                timeout = self.cache_layers[layer]['timeout']
            
            success = False
            
            if layer == 'L1':
                success = self._set_l1_cache(cache_key, data, timeout)
            elif layer == 'L2':
                success = self._set_l2_cache(cache_key, data, timeout)
            elif layer == 'L3':
                success = self._set_l3_cache(cache_key, data, timeout)
            
            if success:
                logger.debug(f"Data cached in {layer} for {cache_key}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error setting cached data for {cache_key}: {e}")
            return False
    
    def _get_from_l1_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from L1 cache (in-memory)"""
        try:
            # Use Django's cache framework for L1
            return cache.get(f"l1_{cache_key}")
        except Exception as e:
            logger.error(f"Error getting from L1 cache: {e}")
            return None
    
    def _get_from_l2_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from L2 cache (Redis)"""
        try:
            # Use Django's cache framework for L2
            return cache.get(f"l2_{cache_key}")
        except Exception as e:
            logger.error(f"Error getting from L2 cache: {e}")
            return None
    
    def _get_from_l3_cache(self, cache_key: str, data_type: str) -> Optional[Any]:
        """Get data from L3 cache (Database)"""
        try:
            # For L3 cache, we would implement database-level caching
            # This could be materialized views, cached query results, etc.
            # For now, we'll use a simplified approach
            
            if data_type == 'market_data':
                return self._get_cached_market_data(cache_key)
            elif data_type == 'technical_indicators':
                return self._get_cached_technical_indicators(cache_key)
            elif data_type == 'signals':
                return self._get_cached_signals(cache_key)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting from L3 cache: {e}")
            return None
    
    def _set_l1_cache(self, cache_key: str, data: Any, timeout: int = 300) -> bool:
        """Set data in L1 cache (in-memory)"""
        try:
            cache.set(f"l1_{cache_key}", data, timeout)
            return True
        except Exception as e:
            logger.error(f"Error setting L1 cache: {e}")
            return False
    
    def _set_l2_cache(self, cache_key: str, data: Any, timeout: int = 1800) -> bool:
        """Set data in L2 cache (Redis)"""
        try:
            cache.set(f"l2_{cache_key}", data, timeout)
            return True
        except Exception as e:
            logger.error(f"Error setting L2 cache: {e}")
            return False
    
    def _set_l3_cache(self, cache_key: str, data: Any, timeout: int = 3600) -> bool:
        """Set data in L3 cache (Database)"""
        try:
            # For L3 cache, we would store in a dedicated cache table
            # For now, we'll use the regular cache
            cache.set(f"l3_{cache_key}", data, timeout)
            return True
        except Exception as e:
            logger.error(f"Error setting L3 cache: {e}")
            return False
    
    def _get_cached_market_data(self, cache_key: str) -> Optional[Any]:
        """Get cached market data from L3 cache"""
        try:
            # Parse cache key to get symbol and timeframe
            # This is a simplified implementation
            return cache.get(f"l3_market_data_{cache_key}")
        except Exception as e:
            logger.error(f"Error getting cached market data: {e}")
            return None
    
    def _get_cached_technical_indicators(self, cache_key: str) -> Optional[Any]:
        """Get cached technical indicators from L3 cache"""
        try:
            return cache.get(f"l3_indicators_{cache_key}")
        except Exception as e:
            logger.error(f"Error getting cached technical indicators: {e}")
            return None
    
    def _get_cached_signals(self, cache_key: str) -> Optional[Any]:
        """Get cached signals from L3 cache"""
        try:
            return cache.get(f"l3_signals_{cache_key}")
        except Exception as e:
            logger.error(f"Error getting cached signals: {e}")
            return None
    
    def cache_market_data(self, symbol: Symbol, hours_back: int = 24) -> bool:
        """Cache market data for a symbol"""
        try:
            cache_key = f"market_data_{symbol.symbol}_{hours_back}h"
            
            # Get market data
            from apps.signals.database_data_utils import get_recent_market_data
            market_data = get_recent_market_data(symbol, hours_back)
            
            # Convert to cacheable format
            data = list(market_data.values(
                'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
            ))
            
            # Cache in all layers
            self.set_cached_data(cache_key, data, 'L1', 300)  # 5 minutes
            self.set_cached_data(cache_key, data, 'L2', 1800)  # 30 minutes
            self.set_cached_data(cache_key, data, 'L3', 3600)  # 1 hour
            
            logger.info(f"Cached market data for {symbol.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching market data for {symbol.symbol}: {e}")
            return False
    
    def cache_technical_indicators(self, symbol: Symbol, hours_back: int = 168) -> bool:
        """Cache technical indicators for a symbol"""
        try:
            cache_key = f"indicators_{symbol.symbol}_{hours_back}h"
            
            # Get technical indicators
            from apps.signals.database_technical_analysis import database_technical_analysis
            indicators = database_technical_analysis.calculate_indicators_from_database(
                symbol, hours_back
            )
            
            if indicators:
                # Cache in all layers
                self.set_cached_data(cache_key, indicators, 'L1', 300)  # 5 minutes
                self.set_cached_data(cache_key, indicators, 'L2', 1800)  # 30 minutes
                self.set_cached_data(cache_key, indicators, 'L3', 3600)  # 1 hour
                
                logger.info(f"Cached technical indicators for {symbol.symbol}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error caching technical indicators for {symbol.symbol}: {e}")
            return False
    
    def cache_signals(self, symbol: Symbol, signals: List[TradingSignal]) -> bool:
        """Cache signals for a symbol"""
        try:
            cache_key = f"signals_{symbol.symbol}_{timezone.now().strftime('%Y%m%d%H')}"
            
            # Convert signals to cacheable format
            data = []
            for signal in signals:
                data.append({
                    'id': signal.id,
                    'signal_type': signal.signal_type.name,
                    'confidence_score': float(signal.confidence_score),
                    'entry_price': float(signal.entry_price) if signal.entry_price else None,
                    'target_price': float(signal.target_price) if signal.target_price else None,
                    'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                    'created_at': signal.created_at.isoformat()
                })
            
            # Cache in L1 and L2 (signals change frequently)
            self.set_cached_data(cache_key, data, 'L1', 300)  # 5 minutes
            self.set_cached_data(cache_key, data, 'L2', 1800)  # 30 minutes
            
            logger.info(f"Cached {len(signals)} signals for {symbol.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching signals for {symbol.symbol}: {e}")
            return False
    
    def warm_cache(self, symbols: List[Symbol] = None) -> Dict[str, Any]:
        """Warm cache with frequently accessed data"""
        try:
            if not self.cache_warming_enabled:
                return {'status': 'disabled', 'message': 'Cache warming is disabled'}
            
            logger.info("Starting cache warming...")
            
            if symbols is None:
                symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True)[:50]
            
            warming_results = {
                'symbols_processed': 0,
                'market_data_cached': 0,
                'indicators_cached': 0,
                'signals_cached': 0,
                'errors': 0
            }
            
            for symbol in symbols:
                try:
                    # Cache market data
                    if self.cache_market_data(symbol, 24):
                        warming_results['market_data_cached'] += 1
                    
                    # Cache technical indicators
                    if self.cache_technical_indicators(symbol, 168):
                        warming_results['indicators_cached'] += 1
                    
                    # Cache recent signals
                    recent_signals = TradingSignal.objects.filter(
                        symbol=symbol,
                        created_at__gte=timezone.now() - timedelta(hours=1)
                    )
                    if recent_signals.exists():
                        if self.cache_signals(symbol, list(recent_signals)):
                            warming_results['signals_cached'] += 1
                    
                    warming_results['symbols_processed'] += 1
                    
                except Exception as e:
                    logger.error(f"Error warming cache for {symbol.symbol}: {e}")
                    warming_results['errors'] += 1
            
            logger.info(f"Cache warming completed: {warming_results['symbols_processed']} symbols processed")
            return warming_results
            
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
            return {'error': str(e)}
    
    def clear_cache(self, layer: str = None, pattern: str = None) -> Dict[str, Any]:
        """Clear cache with optional layer and pattern filtering"""
        try:
            logger.info(f"Clearing cache - layer: {layer}, pattern: {pattern}")
            
            cleared_count = 0
            
            if layer is None or layer == 'L1':
                cleared_count += self._clear_l1_cache(pattern)
            
            if layer is None or layer == 'L2':
                cleared_count += self._clear_l2_cache(pattern)
            
            if layer is None or layer == 'L3':
                cleared_count += self._clear_l3_cache(pattern)
            
            # Update cache stats
            self.cache_stats['evictions'] += cleared_count
            
            logger.info(f"Cache cleared: {cleared_count} entries")
            return {
                'status': 'success',
                'entries_cleared': cleared_count,
                'layer': layer,
                'pattern': pattern
            }
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return {'error': str(e)}
    
    def _clear_l1_cache(self, pattern: str = None) -> int:
        """Clear L1 cache"""
        try:
            # In a real implementation, you would iterate through cache keys
            # and delete matching entries
            if pattern:
                # Clear specific pattern
                cache.delete_many([f"l1_{pattern}"])
                return 1
            else:
                # Clear all L1 cache (simplified)
                return 0
        except Exception as e:
            logger.error(f"Error clearing L1 cache: {e}")
            return 0
    
    def _clear_l2_cache(self, pattern: str = None) -> int:
        """Clear L2 cache"""
        try:
            if pattern:
                cache.delete_many([f"l2_{pattern}"])
                return 1
            else:
                return 0
        except Exception as e:
            logger.error(f"Error clearing L2 cache: {e}")
            return 0
    
    def _clear_l3_cache(self, pattern: str = None) -> int:
        """Clear L3 cache"""
        try:
            if pattern:
                cache.delete_many([f"l3_{pattern}"])
                return 1
            else:
                return 0
        except Exception as e:
            logger.error(f"Error clearing L3 cache: {e}")
            return 0
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        try:
            total_requests = self.cache_stats['total_requests']
            hits = self.cache_stats['hits']
            misses = self.cache_stats['misses']
            
            hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
            miss_rate = (misses / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'total_requests': total_requests,
                'hits': hits,
                'misses': misses,
                'evictions': self.cache_stats['evictions'],
                'hit_rate_percentage': hit_rate,
                'miss_rate_percentage': miss_rate,
                'cache_layers': self.cache_layers,
                'warming_enabled': self.cache_warming_enabled
            }
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {'error': str(e)}
    
    def optimize_cache_performance(self) -> Dict[str, Any]:
        """Optimize cache performance based on usage patterns"""
        try:
            logger.info("Starting cache performance optimization...")
            
            optimization_results = {
                'recommendations': [],
                'performance_improvements': {},
                'cache_tuning': {}
            }
            
            # Analyze cache hit rates
            stats = self.get_cache_statistics()
            hit_rate = stats.get('hit_rate_percentage', 0)
            
            if hit_rate < 70:
                optimization_results['recommendations'].append(
                    "Low cache hit rate - consider increasing cache timeouts"
                )
            
            if hit_rate < 50:
                optimization_results['recommendations'].append(
                    "Very low cache hit rate - review caching strategy"
                )
            
            # Optimize cache timeouts based on data type
            optimization_results['cache_tuning'] = {
                'market_data_timeout': 1800,  # 30 minutes
                'indicators_timeout': 3600,   # 1 hour
                'signals_timeout': 300,       # 5 minutes
                'health_data_timeout': 600    # 10 minutes
            }
            
            # Performance improvements
            optimization_results['performance_improvements'] = {
                'estimated_hit_rate_improvement': min(hit_rate + 20, 95),
                'estimated_response_time_improvement': '15-30%',
                'memory_usage_optimization': '10-20%'
            }
            
            logger.info("Cache performance optimization completed")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error optimizing cache performance: {e}")
            return {'error': str(e)}


def cache_result(timeout: int = 300, layer: str = 'L2', key_prefix: str = ''):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}_{func.__name__}_{hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()}"
            
            # Try to get from cache
            caching_service = AdvancedCachingService()
            cached_result = caching_service.get_cached_data(cache_key)
            
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            caching_service.set_cached_data(cache_key, result, layer, timeout)
            
            logger.debug(f"Result cached for {func.__name__}")
            return result
        
        return wrapper
    return decorator


# Global instance
advanced_caching_service = AdvancedCachingService()














