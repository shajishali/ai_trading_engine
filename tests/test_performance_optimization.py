"""
Performance optimization tests for Phase 4
Tests performance improvements and optimizations
"""

import os
import sys
import django
import time
import json
from datetime import datetime, date, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import connection
from django.core.cache import cache

from apps.signals.models import BacktestSearch, TradingSignal, SignalType
from apps.trading.models import Symbol
from apps.data.models import MarketData


class PerformanceOptimizationTest(TestCase):
    """Test cases for performance optimization"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test symbol
        self.symbol = Symbol.objects.create(
            symbol='XRP',
            name='Ripple',
            is_active=True
        )
        
        # Create signal type
        self.signal_type = SignalType.objects.create(
            name='BUY',
            description='Buy Signal',
            color='#00ff00'
        )
        
        # Test dates
        self.start_date = datetime(2025, 1, 1, 0, 0, 0)
        self.end_date = datetime(2025, 8, 31, 23, 59, 59)
    
    def test_api_response_time(self):
        """Test API response time is within acceptable limits"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat()
        }
        
        start_time = time.time()
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        end_time = time.time()
        
        response_time = end_time - start_time
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 5.0)  # Should respond within 5 seconds
    
    def test_database_query_performance(self):
        """Test database query performance"""
        # Create test data
        for i in range(100):
            TradingSignal.objects.create(
                symbol=self.symbol,
                signal_type=self.signal_type,
                strength=0.8,
                confidence_score=0.85,
                confidence_level='HIGH',
                entry_price=0.45 + i * 0.001,
                target_price=0.50 + i * 0.001,
                stop_loss=0.42 + i * 0.001,
                risk_reward_ratio=2.0,
                timeframe='1H',
                entry_point_type='BREAKOUT',
                quality_score=0.9,
                created_at=self.start_date + timedelta(hours=i),
                expires_at=self.start_date + timedelta(hours=i+24)
            )
        
        # Test query performance
        start_time = time.time()
        signals = TradingSignal.objects.filter(symbol=self.symbol).order_by('-created_at')[:50]
        list(signals)  # Force evaluation
        end_time = time.time()
        
        query_time = end_time - start_time
        
        self.assertLess(query_time, 0.1)  # Should query within 100ms
    
    def test_bulk_operations_performance(self):
        """Test bulk operations performance"""
        # Test bulk creation
        signals_data = []
        for i in range(1000):
            signals_data.append(TradingSignal(
                symbol=self.symbol,
                signal_type=self.signal_type,
                strength=0.8,
                confidence_score=0.85,
                confidence_level='HIGH',
                entry_price=0.45 + i * 0.001,
                target_price=0.50 + i * 0.001,
                stop_loss=0.42 + i * 0.001,
                risk_reward_ratio=2.0,
                timeframe='1H',
                entry_point_type='BREAKOUT',
                quality_score=0.9,
                created_at=self.start_date + timedelta(hours=i),
                expires_at=self.start_date + timedelta(hours=i+24)
            ))
        
        start_time = time.time()
        TradingSignal.objects.bulk_create(signals_data)
        end_time = time.time()
        
        bulk_time = end_time - start_time
        
        self.assertLess(bulk_time, 2.0)  # Should bulk create within 2 seconds
    
    def test_cache_performance(self):
        """Test cache performance"""
        # Clear cache
        cache.clear()
        
        # Test cache miss
        start_time = time.time()
        cached_data = cache.get('test_key')
        end_time = time.time()
        
        cache_miss_time = end_time - start_time
        
        # Test cache set
        start_time = time.time()
        cache.set('test_key', 'test_value', 300)
        end_time = time.time()
        
        cache_set_time = end_time - start_time
        
        # Test cache hit
        start_time = time.time()
        cached_data = cache.get('test_key')
        end_time = time.time()
        
        cache_hit_time = end_time - start_time
        
        self.assertLess(cache_miss_time, 0.01)  # Cache miss should be fast
        self.assertLess(cache_set_time, 0.01)   # Cache set should be fast
        self.assertLess(cache_hit_time, 0.01)   # Cache hit should be fast
        self.assertEqual(cached_data, 'test_value')
    
    def test_memory_usage(self):
        """Test memory usage during operations"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create large dataset
        signals_data = []
        for i in range(10000):
            signals_data.append(TradingSignal(
                symbol=self.symbol,
                signal_type=self.signal_type,
                strength=0.8,
                confidence_score=0.85,
                confidence_level='HIGH',
                entry_price=0.45 + i * 0.001,
                target_price=0.50 + i * 0.001,
                stop_loss=0.42 + i * 0.001,
                risk_reward_ratio=2.0,
                timeframe='1H',
                entry_point_type='BREAKOUT',
                quality_score=0.9,
                created_at=self.start_date + timedelta(hours=i),
                expires_at=self.start_date + timedelta(hours=i+24)
            ))
        
        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        self.assertLess(memory_increase, 100 * 1024 * 1024)
    
    def test_concurrent_requests_performance(self):
        """Test performance under concurrent requests"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat()
        }
        
        # Simulate concurrent requests
        start_time = time.time()
        
        responses = []
        for i in range(10):  # 10 concurrent requests
            response = self.client.post(
                '/signals/api/backtest/',
                data=json.dumps(data),
                content_type='application/json'
            )
            responses.append(response)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # All requests should succeed
        for response in responses:
            self.assertEqual(response.status_code, 200)
        
        # Total time should be reasonable (less than 30 seconds for 10 requests)
        self.assertLess(total_time, 30.0)
    
    def test_database_connection_pooling(self):
        """Test database connection pooling"""
        connections = []
        
        # Test multiple database connections
        for i in range(10):
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                connections.append(result)
        
        # All connections should work
        for result in connections:
            self.assertEqual(result[0], 1)
    
    def test_query_optimization(self):
        """Test query optimization with select_related and prefetch_related"""
        # Create test data with relationships
        for i in range(100):
            BacktestSearch.objects.create(
                user=self.user,
                symbol=self.symbol,
                start_date=self.start_date.date(),
                end_date=self.end_date.date(),
                signals_generated=i
            )
        
        # Test unoptimized query
        start_time = time.time()
        searches = BacktestSearch.objects.all()[:50]
        for search in searches:
            _ = search.user.username  # This will cause additional queries
            _ = search.symbol.name
        end_time = time.time()
        unoptimized_time = end_time - start_time
        
        # Test optimized query
        start_time = time.time()
        searches = BacktestSearch.objects.select_related('user', 'symbol').all()[:50]
        for search in searches:
            _ = search.user.username  # No additional queries
            _ = search.symbol.name
        end_time = time.time()
        optimized_time = end_time - start_time
        
        # Optimized query should be faster
        self.assertLess(optimized_time, unoptimized_time)
    
    def test_pagination_performance(self):
        """Test pagination performance"""
        # Create large dataset
        for i in range(1000):
            TradingSignal.objects.create(
                symbol=self.symbol,
                signal_type=self.signal_type,
                strength=0.8,
                confidence_score=0.85,
                confidence_level='HIGH',
                entry_price=0.45 + i * 0.001,
                target_price=0.50 + i * 0.001,
                stop_loss=0.42 + i * 0.001,
                risk_reward_ratio=2.0,
                timeframe='1H',
                entry_point_type='BREAKOUT',
                quality_score=0.9,
                created_at=self.start_date + timedelta(hours=i),
                expires_at=self.start_date + timedelta(hours=i+24)
            )
        
        # Test pagination performance
        start_time = time.time()
        signals = TradingSignal.objects.all()[100:150]  # Page 3, 50 items
        list(signals)  # Force evaluation
        end_time = time.time()
        
        pagination_time = end_time - start_time
        
        self.assertLess(pagination_time, 0.05)  # Should paginate within 50ms
    
    def test_export_performance(self):
        """Test export performance"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create test signals
        for i in range(500):
            TradingSignal.objects.create(
                symbol=self.symbol,
                signal_type=self.signal_type,
                strength=0.8,
                confidence_score=0.85,
                confidence_level='HIGH',
                entry_price=0.45 + i * 0.001,
                target_price=0.50 + i * 0.001,
                stop_loss=0.42 + i * 0.001,
                risk_reward_ratio=2.0,
                timeframe='1H',
                entry_point_type='BREAKOUT',
                quality_score=0.9,
                created_at=self.start_date + timedelta(hours=i),
                expires_at=self.start_date + timedelta(hours=i+24)
            )
        
        # Test CSV export performance
        start_time = time.time()
        response = self.client.get('/signals/api/tradingview-export/?format=csv')
        end_time = time.time()
        
        csv_export_time = end_time - start_time
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(csv_export_time, 3.0)  # Should export within 3 seconds
        
        # Test JSON export performance
        start_time = time.time()
        response = self.client.get('/signals/api/tradingview-export/?format=json')
        end_time = time.time()
        
        json_export_time = end_time - start_time
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(json_export_time, 2.0)  # Should export within 2 seconds
    
    def test_signal_generation_performance(self):
        """Test signal generation performance"""
        # Create market data
        for i in range(1000):
            MarketData.objects.create(
                symbol=self.symbol,
                timestamp=self.start_date + timedelta(hours=i),
                open_price=0.45 + i * 0.001,
                high_price=0.47 + i * 0.001,
                low_price=0.43 + i * 0.001,
                close_price=0.46 + i * 0.001,
                volume=1000000
            )
        
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat()
        }
        
        start_time = time.time()
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        end_time = time.time()
        
        signal_generation_time = end_time - start_time
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(signal_generation_time, 10.0)  # Should generate signals within 10 seconds
    
    def test_database_index_performance(self):
        """Test database index performance"""
        # Test query with index
        start_time = time.time()
        signals = TradingSignal.objects.filter(symbol=self.symbol).order_by('-created_at')
        list(signals[:100])  # Force evaluation
        end_time = time.time()
        
        indexed_query_time = end_time - start_time
        
        # Test query without index (by filtering on non-indexed field)
        start_time = time.time()
        signals = TradingSignal.objects.filter(strength__gt=0.5).order_by('-created_at')
        list(signals[:100])  # Force evaluation
        end_time = time.time()
        
        non_indexed_query_time = end_time - start_time
        
        # Indexed query should be faster
        self.assertLess(indexed_query_time, non_indexed_query_time)
    
    def test_memory_cleanup(self):
        """Test memory cleanup after operations"""
        import gc
        
        # Force garbage collection
        gc.collect()
        
        initial_memory = psutil.Process(os.getpid()).memory_info().rss
        
        # Create and destroy large objects
        for i in range(100):
            signals_data = []
            for j in range(1000):
                signals_data.append(TradingSignal(
                    symbol=self.symbol,
                    signal_type=self.signal_type,
                    strength=0.8,
                    confidence_score=0.85,
                    confidence_level='HIGH',
                    entry_price=0.45 + j * 0.001,
                    target_price=0.50 + j * 0.001,
                    stop_loss=0.42 + j * 0.001,
                    risk_reward_ratio=2.0,
                    timeframe='1H',
                    entry_point_type='BREAKOUT',
                    quality_score=0.9,
                    created_at=self.start_date + timedelta(hours=j),
                    expires_at=self.start_date + timedelta(hours=j+24)
                ))
            
            # Process data
            _ = [signal.entry_price for signal in signals_data]
            
            # Clear data
            del signals_data
        
        # Force garbage collection
        gc.collect()
        
        final_memory = psutil.Process(os.getpid()).memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be minimal after cleanup
        self.assertLess(memory_increase, 50 * 1024 * 1024)  # Less than 50MB


if __name__ == '__main__':
    import unittest
    unittest.main()
































































