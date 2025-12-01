"""
Comprehensive testing for Phase 4: Database-Driven Signal Generation
Testing technical indicators, signal quality monitoring, and migration strategy
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import TradingSignal, SignalAlert
from apps.signals.database_technical_analysis import database_technical_analysis
from apps.signals.database_signal_monitoring import database_signal_monitor
from apps.signals.feature_flags import feature_flags, SignalGenerationMode, MigrationStatus


class TestDatabaseTechnicalAnalysis(TestCase):
    """Test database technical analysis functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.symbol = Symbol.objects.create(
            symbol="BTCUSDT",
            name="Bitcoin/USDT",
            is_active=True,
            is_crypto_symbol=True
        )
        
        # Create sample market data
        self.create_sample_market_data()
    
    def create_sample_market_data(self):
        """Create sample market data for testing"""
        base_time = timezone.now() - timedelta(hours=100)
        
        for i in range(100):
            timestamp = base_time + timedelta(hours=i)
            price = 50000 + (i * 100) + np.random.normal(0, 50)
            
            MarketData.objects.create(
                symbol=self.symbol,
                timestamp=timestamp,
                open_price=price,
                high_price=price * 1.02,
                low_price=price * 0.98,
                close_price=price,
                volume=1000000 + np.random.normal(0, 100000)
            )
    
    def test_calculate_indicators_from_database(self):
        """Test calculating indicators from database data"""
        indicators = database_technical_analysis.calculate_indicators_from_database(
            self.symbol, hours_back=24
        )
        
        self.assertIsNotNone(indicators)
        self.assertIsInstance(indicators, dict)
        
        # Check that key indicators are present
        expected_indicators = [
            'sma_20', 'sma_50', 'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'bollinger_upper', 'bollinger_middle', 'bollinger_lower'
        ]
        
        for indicator in expected_indicators:
            self.assertIn(indicator, indicators)
            self.assertIsInstance(indicators[indicator], (int, float))
    
    def test_calculate_moving_averages(self):
        """Test moving average calculations"""
        # Get market data
        market_data = MarketData.objects.filter(symbol=self.symbol).order_by('timestamp')
        df = pd.DataFrame(list(market_data.values(
            'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
        )))
        
        # Test moving averages
        close_prices = df['close_price']
        sma_20 = close_prices.rolling(window=20).mean()
        sma_50 = close_prices.rolling(window=50).mean()
        
        self.assertIsNotNone(sma_20.iloc[-1])
        self.assertIsNotNone(sma_50.iloc[-1])
        self.assertGreater(sma_20.iloc[-1], 0)
        self.assertGreater(sma_50.iloc[-1], 0)
    
    def test_calculate_rsi(self):
        """Test RSI calculation"""
        market_data = MarketData.objects.filter(symbol=self.symbol).order_by('timestamp')
        df = pd.DataFrame(list(market_data.values(
            'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
        )))
        
        close_prices = df['close_price']
        rsi = database_technical_analysis._calculate_rsi(close_prices)
        
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
    
    def test_calculate_macd(self):
        """Test MACD calculation"""
        market_data = MarketData.objects.filter(symbol=self.symbol).order_by('timestamp')
        df = pd.DataFrame(list(market_data.values(
            'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
        )))
        
        close_prices = df['close_price']
        macd_result = database_technical_analysis._calculate_macd(close_prices)
        
        self.assertIsInstance(macd_result, dict)
        self.assertIn('macd', macd_result)
        self.assertIn('macd_signal', macd_result)
        self.assertIn('macd_histogram', macd_result)
        
        for key, value in macd_result.items():
            self.assertIsInstance(value, (int, float))
    
    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation"""
        market_data = MarketData.objects.filter(symbol=self.symbol).order_by('timestamp')
        df = pd.DataFrame(list(market_data.values(
            'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
        )))
        
        close_prices = df['close_price']
        bb_result = database_technical_analysis._calculate_bollinger_bands(close_prices)
        
        self.assertIsInstance(bb_result, dict)
        self.assertIn('bollinger_upper', bb_result)
        self.assertIn('bollinger_middle', bb_result)
        self.assertIn('bollinger_lower', bb_result)
        
        # Check that upper > middle > lower
        self.assertGreater(bb_result['bollinger_upper'], bb_result['bollinger_middle'])
        self.assertGreater(bb_result['bollinger_middle'], bb_result['bollinger_lower'])
    
    def test_calculate_signal_strength(self):
        """Test signal strength calculation"""
        # Create sample indicators
        indicators = {
            'rsi': 65.0,
            'macd': 0.5,
            'macd_signal': 0.3,
            'bollinger_upper': 52000,
            'bollinger_lower': 48000,
            'close_price': 50000,
            'sma_20': 49500,
            'sma_50': 49000
        }
        
        strength = database_technical_analysis.calculate_signal_strength(indicators)
        
        self.assertIsInstance(strength, float)
        self.assertGreaterEqual(strength, -1.0)
        self.assertLessEqual(strength, 1.0)
    
    def test_get_latest_indicators(self):
        """Test getting latest indicators"""
        # First calculate indicators
        database_technical_analysis.calculate_indicators_from_database(self.symbol, 24)
        
        # Then get latest indicators
        latest_indicators = database_technical_analysis.get_latest_indicators(self.symbol)
        
        self.assertIsNotNone(latest_indicators)
        self.assertIsInstance(latest_indicators, dict)


class TestDatabaseSignalMonitoring(TestCase):
    """Test database signal monitoring functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.symbol = Symbol.objects.create(
            symbol="ETHUSDT",
            name="Ethereum/USDT",
            is_active=True,
            is_crypto_symbol=True
        )
        
        # Create sample signals
        self.create_sample_signals()
    
    def create_sample_signals(self):
        """Create sample signals for testing"""
        base_time = timezone.now() - timedelta(hours=24)
        
        for i in range(20):
            timestamp = base_time + timedelta(hours=i)
            TradingSignal.objects.create(
                symbol=self.symbol,
                signal_type_id=1,  # Assuming signal type exists
                strength_id=1,     # Assuming strength exists
                confidence_score=0.7 + (i * 0.01),
                quality_score=0.8 + (i * 0.005),
                is_profitable=i % 3 == 0,  # 1/3 profitable
                data_source='database',
                created_at=timestamp
            )
    
    def test_monitor_signal_quality(self):
        """Test signal quality monitoring"""
        quality_report = database_signal_monitor.monitor_signal_quality()
        
        self.assertIsInstance(quality_report, dict)
        self.assertIn('timestamp', quality_report)
        self.assertIn('signals_generated', quality_report)
        self.assertIn('quality_score', quality_report)
        self.assertIn('system_health', quality_report)
        
        self.assertGreaterEqual(quality_report['quality_score'], 0)
        self.assertLessEqual(quality_report['quality_score'], 100)
    
    def test_monitor_data_freshness(self):
        """Test data freshness monitoring"""
        # Create sample market data
        MarketData.objects.create(
            symbol=self.symbol,
            timestamp=timezone.now() - timedelta(hours=1),
            open_price=3000,
            high_price=3100,
            low_price=2900,
            close_price=3000,
            volume=1000000
        )
        
        freshness_report = database_signal_monitor.monitor_data_freshness()
        
        self.assertIsInstance(freshness_report, dict)
        self.assertIn('timestamp', freshness_report)
        self.assertIn('total_symbols', freshness_report)
        self.assertIn('freshness_score', freshness_report)
        
        self.assertGreaterEqual(freshness_report['freshness_score'], 0)
        self.assertLessEqual(freshness_report['freshness_score'], 100)
    
    def test_monitor_signal_generation_performance(self):
        """Test signal generation performance monitoring"""
        performance_report = database_signal_monitor.monitor_signal_generation_performance()
        
        self.assertIsInstance(performance_report, dict)
        self.assertIn('timestamp', performance_report)
        self.assertIn('total_signals', performance_report)
        self.assertIn('performance_score', performance_report)
        
        self.assertGreaterEqual(performance_report['performance_score'], 0)
        self.assertLessEqual(performance_report['performance_score'], 100)
    
    def test_get_comprehensive_monitoring_report(self):
        """Test comprehensive monitoring report"""
        report = database_signal_monitor.get_comprehensive_monitoring_report()
        
        self.assertIsInstance(report, dict)
        self.assertIn('timestamp', report)
        self.assertIn('overall_system_score', report)
        self.assertIn('system_status', report)
        self.assertIn('quality_monitoring', report)
        self.assertIn('data_freshness', report)
        self.assertIn('performance_monitoring', report)
        
        self.assertGreaterEqual(report['overall_system_score'], 0)
        self.assertLessEqual(report['overall_system_score'], 100)


class TestFeatureFlags(TestCase):
    """Test feature flags and migration strategy"""
    
    def setUp(self):
        """Set up test data"""
        # Clear cache
        cache.clear()
    
    def test_get_current_mode(self):
        """Test getting current mode"""
        mode = feature_flags.get_current_mode()
        
        self.assertIsInstance(mode, SignalGenerationMode)
        self.assertIn(mode, [SignalGenerationMode.LIVE_API, SignalGenerationMode.DATABASE, 
                            SignalGenerationMode.HYBRID, SignalGenerationMode.AUTO])
    
    def test_set_mode(self):
        """Test setting mode"""
        # Test setting to database mode
        result = feature_flags.set_mode(SignalGenerationMode.DATABASE, force=True)
        
        self.assertTrue(result)
        
        # Verify mode was set
        current_mode = feature_flags.get_current_mode()
        self.assertEqual(current_mode, SignalGenerationMode.DATABASE)
    
    def test_start_migration(self):
        """Test starting migration"""
        # Mock system health check
        with patch.object(feature_flags, '_check_system_health', return_value="HEALTHY"):
            with patch.object(feature_flags, '_check_migration_prerequisites', 
                            return_value={'can_migrate': True, 'reason': 'All prerequisites met'}):
                
                result = feature_flags.start_migration(SignalGenerationMode.DATABASE)
                
                self.assertIsInstance(result, dict)
                if 'error' not in result:
                    self.assertIn('status', result)
                    self.assertIn('target_mode', result)
    
    def test_check_migration_status(self):
        """Test checking migration status"""
        status = feature_flags.check_migration_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn('status', status)
    
    def test_force_rollback(self):
        """Test forcing rollback"""
        result = feature_flags.force_rollback()
        
        self.assertTrue(result)
        
        # Verify mode was set to live API
        current_mode = feature_flags.get_current_mode()
        self.assertEqual(current_mode, SignalGenerationMode.LIVE_API)
    
    def test_get_feature_flags_status(self):
        """Test getting feature flags status"""
        status = feature_flags.get_feature_flags_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn('current_mode', status)
        self.assertIn('migration_enabled', status)
        self.assertIn('system_health', status)


class TestIntegration(TestCase):
    """Integration tests for Phase 4 components"""
    
    def setUp(self):
        """Set up test data"""
        self.symbol = Symbol.objects.create(
            symbol="ADAUSDT",
            name="Cardano/USDT",
            is_active=True,
            is_crypto_symbol=True
        )
        
        # Create sample market data
        self.create_sample_market_data()
    
    def create_sample_market_data(self):
        """Create sample market data for integration testing"""
        base_time = timezone.now() - timedelta(hours=50)
        
        for i in range(50):
            timestamp = base_time + timedelta(hours=i)
            price = 1.0 + (i * 0.01) + np.random.normal(0, 0.05)
            
            MarketData.objects.create(
                symbol=self.symbol,
                timestamp=timestamp,
                open_price=price,
                high_price=price * 1.02,
                low_price=price * 0.98,
                close_price=price,
                volume=1000000 + np.random.normal(0, 100000)
            )
    
    def test_end_to_end_signal_generation(self):
        """Test end-to-end signal generation process"""
        # Calculate indicators
        indicators = database_technical_analysis.calculate_indicators_from_database(
            self.symbol, hours_back=24
        )
        
        self.assertIsNotNone(indicators)
        
        # Monitor signal quality
        quality_report = database_signal_monitor.monitor_signal_quality()
        
        self.assertIsNotNone(quality_report)
        self.assertIn('quality_score', quality_report)
        
        # Check feature flags
        flags_status = feature_flags.get_feature_flags_status()
        
        self.assertIsNotNone(flags_status)
        self.assertIn('current_mode', flags_status)
    
    def test_migration_workflow(self):
        """Test complete migration workflow"""
        # Start migration
        with patch.object(feature_flags, '_check_system_health', return_value="HEALTHY"):
            with patch.object(feature_flags, '_check_migration_prerequisites', 
                            return_value={'can_migrate': True, 'reason': 'All prerequisites met'}):
                
                migration_result = feature_flags.start_migration(SignalGenerationMode.DATABASE)
                
                if 'error' not in migration_result:
                    # Check migration status
                    status = feature_flags.check_migration_status()
                    
                    self.assertIsNotNone(status)
                    self.assertIn('status', status)
                    
                    # Force rollback
                    rollback_result = feature_flags.force_rollback()
                    
                    self.assertTrue(rollback_result)
    
    def test_performance_under_load(self):
        """Test performance under simulated load"""
        # Create multiple symbols
        symbols = []
        for i in range(5):
            symbol = Symbol.objects.create(
                symbol=f"TEST{i}USDT",
                name=f"Test{i}/USDT",
                is_active=True,
                is_crypto_symbol=True
            )
            symbols.append(symbol)
            
            # Create market data for each symbol
            for j in range(20):
                MarketData.objects.create(
                    symbol=symbol,
                    timestamp=timezone.now() - timedelta(hours=j),
                    open_price=100 + j,
                    high_price=102 + j,
                    low_price=98 + j,
                    close_price=100 + j,
                    volume=1000000
                )
        
        # Test performance with multiple symbols
        start_time = timezone.now()
        
        for symbol in symbols:
            indicators = database_technical_analysis.calculate_indicators_from_database(
                symbol, hours_back=12
            )
            self.assertIsNotNone(indicators)
        
        end_time = timezone.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Should complete within reasonable time (adjust threshold as needed)
        self.assertLess(processing_time, 10.0)  # 10 seconds max
    
    def test_error_handling(self):
        """Test error handling in various scenarios"""
        # Test with non-existent symbol
        non_existent_symbol = Symbol.objects.create(
            symbol="NONEXISTENT",
            name="Non-existent",
            is_active=False,
            is_crypto_symbol=True
        )
        
        indicators = database_technical_analysis.calculate_indicators_from_database(
            non_existent_symbol, hours_back=24
        )
        
        # Should handle gracefully
        self.assertIsNone(indicators)
        
        # Test monitoring with no data
        quality_report = database_signal_monitor.monitor_signal_quality()
        
        # Should return valid report even with no data
        self.assertIsInstance(quality_report, dict)
        self.assertIn('quality_score', quality_report)


# Performance tests
class TestPerformance(TestCase):
    """Performance tests for Phase 4 components"""
    
    def test_technical_analysis_performance(self):
        """Test technical analysis performance"""
        symbol = Symbol.objects.create(
            symbol="PERFTEST",
            name="Performance Test",
            is_active=True,
            is_crypto_symbol=True
        )
        
        # Create large dataset
        base_time = timezone.now() - timedelta(hours=1000)
        
        for i in range(1000):
            timestamp = base_time + timedelta(hours=i)
            price = 100 + (i * 0.1) + np.random.normal(0, 1)
            
            MarketData.objects.create(
                symbol=symbol,
                timestamp=timestamp,
                open_price=price,
                high_price=price * 1.01,
                low_price=price * 0.99,
                close_price=price,
                volume=1000000
            )
        
        # Test performance
        start_time = timezone.now()
        
        indicators = database_technical_analysis.calculate_indicators_from_database(
            symbol, hours_back=168  # 1 week
        )
        
        end_time = timezone.now()
        processing_time = (end_time - start_time).total_seconds()
        
        self.assertIsNotNone(indicators)
        self.assertLess(processing_time, 5.0)  # Should complete within 5 seconds
    
    def test_monitoring_performance(self):
        """Test monitoring performance"""
        # Create test data
        symbol = Symbol.objects.create(
            symbol="MONITORTEST",
            name="Monitor Test",
            is_active=True,
            is_crypto_symbol=True
        )
        
        # Create signals
        for i in range(100):
            TradingSignal.objects.create(
                symbol=symbol,
                signal_type_id=1,
                strength_id=1,
                confidence_score=0.5 + (i * 0.005),
                quality_score=0.6 + (i * 0.004),
                is_profitable=i % 2 == 0,
                data_source='database',
                created_at=timezone.now() - timedelta(hours=i)
            )
        
        # Test monitoring performance
        start_time = timezone.now()
        
        report = database_signal_monitor.get_comprehensive_monitoring_report()
        
        end_time = timezone.now()
        processing_time = (end_time - start_time).total_seconds()
        
        self.assertIsNotNone(report)
        self.assertLess(processing_time, 3.0)  # Should complete within 3 seconds


if __name__ == '__main__':
    pytest.main([__file__])














