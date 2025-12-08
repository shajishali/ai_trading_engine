"""
Phase 5.5: Caching and Performance Optimization Service
Implements caching strategies and performance optimizations
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
import json
import pickle
import hashlib

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import (
    TradingSignal, SignalHistory
)

logger = logging.getLogger(__name__)


class CachingService:
    """Service for implementing caching strategies"""
    
    def __init__(self):
        self.cache_config = {
            'default_ttl': 3600,  # 1 hour
            'model_cache_ttl': 1800,  # 30 minutes
            'prediction_cache_ttl': 300,  # 5 minutes
            'signal_cache_ttl': 600,  # 10 minutes
            'market_data_cache_ttl': 60,  # 1 minute
            'max_cache_size': 1000,  # Maximum cache entries
            'cache_compression': True,
            'cache_versioning': True
        }
        
        # Cache key prefixes
        self.cache_prefixes = {
            'model': 'ml_model',
            'signal': 'trading_signal',
            'market_data': 'market_data',
            'pattern': 'chart_pattern',
            'entry_point': 'entry_point',
            'technical_indicator': 'technical_indicator'
        }
    
    def cache_model(self, model_id: int, model_data: Any, ttl: Optional[int] = None) -> bool:
        """Cache ML model data"""
        try:
            cache_key = self._generate_cache_key('model', f"{model_id}")
            ttl = ttl or self.cache_config['model_cache_ttl']
            
            # Serialize model data
            serialized_data = self._serialize_data(model_data)
            
            # Store in cache
            cache.set(cache_key, serialized_data, timeout=ttl)
            
            logger.debug(f"Cached model {model_id} with TTL {ttl}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching model {model_id}: {e}")
            return False
    
    def get_cached_model(self, model_id: int) -> Optional[Any]:
        """Get cached ML model data"""
        try:
            cache_key = self._generate_cache_key('model', f"{model_id}")
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return self._deserialize_data(cached_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached model {model_id}: {e}")
            return None
    
    def cache_prediction(self, prediction_key: str, prediction_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache ML prediction"""
        try:
            cache_key = self._generate_cache_key('prediction', prediction_key)
            ttl = ttl or self.cache_config['prediction_cache_ttl']
            
            # Add metadata
            prediction_data['cached_at'] = timezone.now().isoformat()
            prediction_data['cache_ttl'] = ttl
            
            # Store in cache
            cache.set(cache_key, prediction_data, timeout=ttl)
            
            logger.debug(f"Cached prediction {prediction_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching prediction {prediction_key}: {e}")
            return False
    
    def get_cached_prediction(self, prediction_key: str) -> Optional[Dict[str, Any]]:
        """Get cached ML prediction"""
        try:
            cache_key = self._generate_cache_key('prediction', prediction_key)
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"Cache hit for prediction {prediction_key}")
                return cached_data
            
            logger.debug(f"Cache miss for prediction {prediction_key}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached prediction {prediction_key}: {e}")
            return None
    
    def cache_market_data(self, symbol: str, timeframe: str, data: List[Dict], ttl: Optional[int] = None) -> bool:
        """Cache market data"""
        try:
            cache_key = self._generate_cache_key('market_data', f"{symbol}_{timeframe}")
            ttl = ttl or self.cache_config['market_data_cache_ttl']
            
            # Compress data if enabled
            if self.cache_config['cache_compression']:
                data = self._compress_data(data)
            
            cache.set(cache_key, data, timeout=ttl)
            
            logger.debug(f"Cached market data for {symbol} {timeframe}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching market data: {e}")
            return False
    
    def get_cached_market_data(self, symbol: str, timeframe: str) -> Optional[List[Dict]]:
        """Get cached market data"""
        try:
            cache_key = self._generate_cache_key('market_data', f"{symbol}_{timeframe}")
            cached_data = cache.get(cache_key)
            
            if cached_data:
                # Decompress if needed
                if self.cache_config['cache_compression']:
                    cached_data = self._decompress_data(cached_data)
                
                logger.debug(f"Cache hit for market data {symbol} {timeframe}")
                return cached_data
            
            logger.debug(f"Cache miss for market data {symbol} {timeframe}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached market data: {e}")
            return None
    
    def cache_signals(self, symbol: str, signals: List[TradingSignal], ttl: Optional[int] = None) -> bool:
        """Cache trading signals"""
        try:
            cache_key = self._generate_cache_key('signal', f"{symbol}_signals")
            ttl = ttl or self.cache_config['signal_cache_ttl']
            
            # Convert signals to serializable format
            signals_data = []
            for signal in signals:
                signals_data.append({
                    'id': signal.id,
                    'signal_type': signal.signal_type,
                    'confidence_score': signal.confidence_score,
                    'strength': signal.strength,
                    'entry_price': float(signal.entry_price) if signal.entry_price else None,
                    'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                    'take_profit': float(signal.take_profit) if signal.take_profit else None,
                    'risk_reward_ratio': signal.risk_reward_ratio,
                    'timeframe': signal.timeframe,
                    'created_at': signal.created_at.isoformat(),
                    'metadata': signal.metadata
                })
            
            cache.set(cache_key, signals_data, timeout=ttl)
            
            logger.debug(f"Cached {len(signals)} signals for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching signals: {e}")
            return False
    
    def get_cached_signals(self, symbol: str) -> Optional[List[Dict]]:
        """Get cached trading signals"""
        try:
            cache_key = self._generate_cache_key('signal', f"{symbol}_signals")
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"Cache hit for signals {symbol}")
                return cached_data
            
            logger.debug(f"Cache miss for signals {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached signals: {e}")
            return None
    
    def invalidate_cache(self, cache_type: str, identifier: str) -> bool:
        """Invalidate specific cache entry"""
        try:
            cache_key = self._generate_cache_key(cache_type, identifier)
            cache.delete(cache_key)
            
            logger.info(f"Invalidated cache for {cache_type}: {identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False
    
    def clear_all_cache(self) -> bool:
        """Clear all cache entries"""
        try:
            cache.clear()
            logger.info("Cleared all cache entries")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            # This would depend on the cache backend implementation
            # For Redis, you could use redis-cli info
            stats = {
                'cache_backend': settings.CACHES['default']['BACKEND'],
                'cache_location': settings.CACHES['default'].get('LOCATION', 'N/A'),
                'cache_config': self.cache_config,
                'timestamp': timezone.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def _generate_cache_key(self, cache_type: str, identifier: str) -> str:
        """Generate cache key with versioning"""
        try:
            prefix = self.cache_prefixes.get(cache_type, 'default')
            
            if self.cache_config['cache_versioning']:
                version = getattr(settings, 'CACHE_VERSION', '1.0')
                return f"{prefix}:{version}:{identifier}"
            else:
                return f"{prefix}:{identifier}"
                
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            return f"{cache_type}:{identifier}"
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for caching"""
        try:
            if self.cache_config['cache_compression']:
                return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                return json.dumps(data, default=str).encode('utf-8')
                
        except Exception as e:
            logger.error(f"Error serializing data: {e}")
            return pickle.dumps(data)
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize cached data"""
        try:
            if self.cache_config['cache_compression']:
                return pickle.loads(data)
            else:
                return json.loads(data.decode('utf-8'))
                
        except Exception as e:
            logger.error(f"Error deserializing data: {e}")
            return pickle.loads(data)
    
    def _compress_data(self, data: Any) -> bytes:
        """Compress data for caching"""
        try:
            import gzip
            serialized = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            compressed = gzip.compress(serialized)
            return compressed
            
        except Exception as e:
            logger.error(f"Error compressing data: {e}")
            return pickle.dumps(data)
    
    def _decompress_data(self, data: bytes) -> Any:
        """Decompress cached data"""
        try:
            import gzip
            decompressed = gzip.decompress(data)
            return pickle.loads(decompressed)
            
        except Exception as e:
            logger.error(f"Error decompressing data: {e}")
            return pickle.loads(data)


class PerformanceOptimizationService:
    """Service for performance optimizations"""
    
    def __init__(self):
        self.optimization_config = {
            'query_optimization': True,
            'lazy_loading': True,
            'connection_pooling': True,
            'async_processing': True,
            'batch_processing': True,
            'memory_optimization': True,
            'cpu_optimization': True
        }
        
        # Performance metrics
        self.performance_metrics = {
            'query_count': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'response_times': [],
            'memory_usage': [],
            'cpu_usage': []
        }
    
    def optimize_database_queries(self, queryset, select_related: List[str] = None, prefetch_related: List[str] = None) -> Any:
        """Optimize database queries"""
        try:
            if self.optimization_config['query_optimization']:
                if select_related:
                    queryset = queryset.select_related(*select_related)
                
                if prefetch_related:
                    queryset = queryset.prefetch_related(*prefetch_related)
            
            self.performance_metrics['query_count'] += 1
            return queryset
            
        except Exception as e:
            logger.error(f"Error optimizing database queries: {e}")
            return queryset
    
    def batch_process_signals(self, signals: List[TradingSignal], batch_size: int = 100) -> List[TradingSignal]:
        """Process signals in batches for better performance"""
        try:
            if not self.optimization_config['batch_processing']:
                return signals
            
            processed_signals = []
            
            for i in range(0, len(signals), batch_size):
                batch = signals[i:i + batch_size]
                
                # Process batch
                processed_batch = self._process_signal_batch(batch)
                processed_signals.extend(processed_batch)
                
                # Yield control to other threads
                if i % (batch_size * 10) == 0:
                    time.sleep(0.001)
            
            return processed_signals
            
        except Exception as e:
            logger.error(f"Error batch processing signals: {e}")
            return signals
    
    def _process_signal_batch(self, batch: List[TradingSignal]) -> List[TradingSignal]:
        """Process a batch of signals"""
        try:
            # Add any batch processing logic here
            # For now, just return the batch as-is
            return batch
            
        except Exception as e:
            logger.error(f"Error processing signal batch: {e}")
            return batch
    
    def optimize_memory_usage(self) -> Dict[str, Any]:
        """Optimize memory usage"""
        try:
            if not self.optimization_config['memory_optimization']:
                return {'status': 'disabled'}
            
            import gc
            
            # Force garbage collection
            collected = gc.collect()
            
            # Get memory usage
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            optimization_result = {
                'status': 'success',
                'garbage_collected': collected,
                'memory_usage_mb': memory_info.rss / 1024 / 1024,
                'memory_percent': process.memory_percent(),
                'timestamp': timezone.now().isoformat()
            }
            
            self.performance_metrics['memory_usage'].append(optimization_result['memory_usage_mb'])
            
            return optimization_result
            
        except Exception as e:
            logger.error(f"Error optimizing memory usage: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def optimize_cpu_usage(self) -> Dict[str, Any]:
        """Optimize CPU usage"""
        try:
            if not self.optimization_config['cpu_optimization']:
                return {'status': 'disabled'}
            
            import psutil
            
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            optimization_result = {
                'status': 'success',
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None,
                'timestamp': timezone.now().isoformat()
            }
            
            self.performance_metrics['cpu_usage'].append(cpu_percent)
            
            return optimization_result
            
        except Exception as e:
            logger.error(f"Error optimizing CPU usage: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        try:
            metrics = {
                'query_count': self.performance_metrics['query_count'],
                'cache_hits': self.performance_metrics['cache_hits'],
                'cache_misses': self.performance_metrics['cache_misses'],
                'cache_hit_ratio': (
                    self.performance_metrics['cache_hits'] / 
                    max(self.performance_metrics['cache_hits'] + self.performance_metrics['cache_misses'], 1)
                ),
                'average_response_time': (
                    sum(self.performance_metrics['response_times']) / 
                    max(len(self.performance_metrics['response_times']), 1)
                ),
                'average_memory_usage': (
                    sum(self.performance_metrics['memory_usage']) / 
                    max(len(self.performance_metrics['memory_usage']), 1)
                ),
                'average_cpu_usage': (
                    sum(self.performance_metrics['cpu_usage']) / 
                    max(len(self.performance_metrics['cpu_usage']), 1)
                ),
                'optimization_config': self.optimization_config,
                'timestamp': timezone.now().isoformat()
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def record_response_time(self, response_time: float):
        """Record response time for performance monitoring"""
        try:
            self.performance_metrics['response_times'].append(response_time)
            
            # Keep only last 1000 response times
            if len(self.performance_metrics['response_times']) > 1000:
                self.performance_metrics['response_times'] = self.performance_metrics['response_times'][-1000:]
                
        except Exception as e:
            logger.error(f"Error recording response time: {e}")
    
    def record_cache_hit(self):
        """Record cache hit"""
        try:
            self.performance_metrics['cache_hits'] += 1
            
        except Exception as e:
            logger.error(f"Error recording cache hit: {e}")
    
    def record_cache_miss(self):
        """Record cache miss"""
        try:
            self.performance_metrics['cache_misses'] += 1
            
        except Exception as e:
            logger.error(f"Error recording cache miss: {e}")


class AsyncProcessingService:
    """Service for asynchronous processing"""
    
    def __init__(self):
        self.async_config = {
            'enabled': True,
            'max_workers': 4,
            'queue_size': 1000,
            'timeout': 30,
            'retry_attempts': 3
        }
        
        # Task queue
        self.task_queue = []
        self.worker_threads = []
        
        # Start worker threads
        if self.async_config['enabled']:
            self._start_workers()
    
    def _start_workers(self):
        """Start worker threads for async processing"""
        try:
            for i in range(self.async_config['max_workers']):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"AsyncWorker-{i}",
                    daemon=True
                )
                worker.start()
                self.worker_threads.append(worker)
                
            logger.info(f"Started {self.async_config['max_workers']} async worker threads")
            
        except Exception as e:
            logger.error(f"Error starting async workers: {e}")
    
    def _worker_loop(self):
        """Worker thread loop"""
        while True:
            try:
                if self.task_queue:
                    task = self.task_queue.pop(0)
                    self._process_task(task)
                else:
                    time.sleep(0.1)  # Wait for tasks
                    
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(1)
    
    def _process_task(self, task: Dict[str, Any]):
        """Process an async task"""
        try:
            task_type = task.get('type')
            task_data = task.get('data', {})
            
            if task_type == 'signal_generation':
                self._process_signal_generation_task(task_data)
            else:
                logger.warning(f"Unknown task type: {task_type}")
                
        except Exception as e:
            logger.error(f"Error processing task: {e}")
    
    def _process_signal_generation_task(self, task_data: Dict[str, Any]):
        """Process signal generation task"""
        try:
            symbol_id = task_data.get('symbol_id')
            if symbol_id:
                from apps.signals.services import SignalGenerationService
                signal_service = SignalGenerationService()
                symbol = Symbol.objects.get(id=symbol_id)
                signals = signal_service.generate_signals_for_symbol(symbol)
                logger.info(f"Generated {len(signals)} signals for {symbol.symbol}")
                
        except Exception as e:
            logger.error(f"Error processing signal generation task: {e}")
    
    def queue_task(self, task_type: str, task_data: Dict[str, Any]) -> bool:
        """Queue an async task"""
        try:
            if not self.async_config['enabled']:
                return False
            
            if len(self.task_queue) >= self.async_config['queue_size']:
                logger.warning("Task queue is full")
                return False
            
            task = {
                'type': task_type,
                'data': task_data,
                'queued_at': timezone.now().isoformat(),
                'retry_count': 0
            }
            
            self.task_queue.append(task)
            logger.debug(f"Queued {task_type} task")
            return True
            
        except Exception as e:
            logger.error(f"Error queueing task: {e}")
            return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get async queue status"""
        try:
            return {
                'enabled': self.async_config['enabled'],
                'queue_size': len(self.task_queue),
                'max_queue_size': self.async_config['queue_size'],
                'worker_count': len(self.worker_threads),
                'max_workers': self.async_config['max_workers'],
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {}























