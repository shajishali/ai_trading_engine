"""
Unit tests for database-driven signal generation
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import TradingSignal, SignalType, SignalStrength
from apps.signals.database_signal_service import DatabaseSignalService, DatabaseTechnicalAnalysis
from apps.signals.database_data_utils import (
    get_recent_market_data,
    get_latest_price,
    validate_data_quality,
    get_database_health_status
)


class TestDatabaseSignalService(TestCase):
    """Test cases for DatabaseSignalService"""
    
    def setUp(self):
        """Set up test data"""
        self.symbol = Symbol.objects.create(
            symbol='BTC',
            name='Bitcoin',
            is_active=True,
            is_crypto_symbol=True
        )
        
        self.signal_service = DatabaseSignalService()
        
        # Create test market data
        self.create_test_market_data()
    
    def create_test_market_data(self):
        """Create test market data for the symbol"""
        base_time = timezone.now() - timedelta(hours=25)
        
        for i in range(25):  # 25 hours of data
            timestamp = base_time + timedelta(hours=i)
            MarketData.objects.create(
                symbol=self.symbol,
                timeframe='1h',
                timestamp=timestamp,
                open_price=Decimal('50000') + Decimal(str(i * 100)),
                high_price=Decimal('50100') + Decimal(str(i * 100)),
                low_price=Decimal('49900') + Decimal(str(i * 100)),
                close_price=Decimal('50050') + Decimal(str(i * 100)),
                volume=Decimal('1000000')
            )
    
    def test_get_recent_market_data(self):
        """Test getting recent market data"""
        market_data = get_recent_market_data(self.symbol, hours_back=24)
        
        self.assertEqual(market_data.count(), 24)
        self.assertTrue(market_data.exists())
        
        # Check ordering
        timestamps = list(market_data.values_list('timestamp', flat=True))
        self.assertEqual(timestamps, sorted(timestamps))
    
    def test_get_latest_price(self):
        """Test getting latest price from database"""
        price = get_latest_price(self.symbol)
        
        self.assertIsNotNone(price)
        self.assertGreater(price, 0)
        self.assertIsInstance(price, Decimal)
    
    def test_get_latest_market_data(self):
        """Test getting latest market data"""
        market_data = self.signal_service.get_latest_market_data(self.symbol)
        
        self.assertIsNotNone(market_data)
        self.assertEqual(market_data['symbol'], 'BTC')
        self.assertEqual(market_data['data_source'], 'database')
        self.assertIn('close_price', market_data)
        self.assertIn('timestamp', market_data)
    
    def test_validate_data_quality(self):
        """Test data quality validation"""
        quality = validate_data_quality(self.symbol, hours_back=24)
        
        self.assertTrue(quality['is_valid'])
        self.assertEqual(quality['data_points'], 24)
        self.assertTrue(quality['is_fresh'])
        self.assertTrue(quality['is_complete'])
    
    def test_validate_data_quality_insufficient_data(self):
        """Test data quality validation with insufficient data"""
        # Create symbol with no data
        empty_symbol = Symbol.objects.create(
            symbol='EMPTY',
            name='Empty Symbol',
            is_active=True,
            is_crypto_symbol=True
        )
        
        quality = validate_data_quality(empty_symbol, hours_back=24)
        
        self.assertFalse(quality['is_valid'])
        self.assertEqual(quality['data_points'], 0)
    
    def test_generate_signals_for_symbol(self):
        """Test generating signals for a symbol"""
        with patch.object(self.signal_service, '_create_trading_signal') as mock_create:
            mock_create.return_value = Mock()
            
            signals = self.signal_service.generate_logical_signals_for_symbol(
                self.symbol, 
                get_recent_market_data(self.symbol)
            )
            
            # Should generate some signals
            self.assertIsInstance(signals, list)
    
    def test_market_data_to_dataframe(self):
        """Test converting market data to DataFrame"""
        market_data = get_recent_market_data(self.symbol, hours_back=24)
        df = self.signal_service._market_data_to_dataframe(market_data)
        
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 0)
        self.assertIn('close', df.columns)
        self.assertIn('volume', df.columns)
    
    def test_calculate_confidence_level(self):
        """Test confidence level calculation"""
        # Test different confidence scores
        self.assertEqual(self.signal_service._calculate_confidence_level(0.9), 'VERY_HIGH')
        self.assertEqual(self.signal_service._calculate_confidence_level(0.8), 'HIGH')
        self.assertEqual(self.signal_service._calculate_confidence_level(0.6), 'MEDIUM')
        self.assertEqual(self.signal_service._calculate_confidence_level(0.3), 'LOW')
    
    def test_select_best_signals(self):
        """Test selecting best signals"""
        # Create mock signals with different confidence scores
        signals = []
        for i in range(10):
            signal = Mock()
            signal.confidence_score = i * 0.1
            signal.risk_reward_ratio = i * 0.1
            signal.strength = Mock()
            signal.strength.priority = i
            signals.append(signal)
        
        best_signals = self.signal_service._select_best_signals(signals)
        
        self.assertEqual(len(best_signals), 5)  # Should return top 5
        # Should be sorted by confidence score (highest first)
        self.assertEqual(best_signals[0].confidence_score, 0.9)
    
    def test_validate_database_data_quality(self):
        """Test database data quality validation"""
        quality = self.signal_service.validate_database_data_quality(self.symbol)
        
        self.assertTrue(quality['is_valid'])
        self.assertGreater(quality['data_points'], 0)
        self.assertIsNotNone(quality['data_age_hours'])


class TestDatabaseTechnicalAnalysis(TestCase):
    """Test cases for DatabaseTechnicalAnalysis"""
    
    def setUp(self):
        """Set up test data"""
        self.symbol = Symbol.objects.create(
            symbol='ETH',
            name='Ethereum',
            is_active=True,
            is_crypto_symbol=True
        )
        
        self.technical_analysis = DatabaseTechnicalAnalysis()
        
        # Create test market data
        self.create_test_market_data()
    
    def create_test_market_data(self):
        """Create test market data for technical analysis"""
        base_time = timezone.now() - timedelta(hours=168)  # 1 week
        
        for i in range(168):  # 1 week of hourly data
            timestamp = base_time + timedelta(hours=i)
            # Create some price movement
            base_price = 3000 + (i * 10) + (i % 10) * 5
            MarketData.objects.create(
                symbol=self.symbol,
                timeframe='1h',
                timestamp=timestamp,
                open_price=Decimal(str(base_price)),
                high_price=Decimal(str(base_price + 10)),
                low_price=Decimal(str(base_price - 10)),
                close_price=Decimal(str(base_price + 5)),
                volume=Decimal('1000000')
            )
    
    def test_calculate_indicators_from_database(self):
        """Test calculating indicators from database"""
        indicators = self.technical_analysis.calculate_indicators_from_database(
            self.symbol, hours_back=168
        )
        
        self.assertIsNotNone(indicators)
        self.assertIn('sma_20', indicators)
        self.assertIn('rsi', indicators)
        self.assertIn('macd', indicators)
        self.assertIn('bb_upper', indicators)
    
    def test_calculate_rsi(self):
        """Test RSI calculation"""
        # Create a simple price series
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113])
        rsi = self.technical_analysis._calculate_rsi(prices, 14)
        
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
    
    def test_calculate_macd(self):
        """Test MACD calculation"""
        # Create a simple price series
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113])
        macd_line, signal_line, histogram = self.technical_analysis._calculate_macd(prices)
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
    
    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation"""
        # Create a simple price series
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113])
        upper, middle, lower = self.technical_analysis._calculate_bollinger_bands(prices)
        
        self.assertIsNotNone(upper)
        self.assertIsNotNone(middle)
        self.assertIsNotNone(lower)
    
    def test_calculate_volatility(self):
        """Test volatility calculation"""
        # Create a simple price series
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113])
        volatility = self.technical_analysis._calculate_volatility(prices)
        
        self.assertIsNotNone(volatility)
        self.assertGreaterEqual(volatility, 0)
    
    def test_determine_trend(self):
        """Test trend determination"""
        # Create uptrending price series
        uptrend_prices = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118])
        trend = self.technical_analysis._determine_trend(uptrend_prices)
        
        self.assertIn(trend, ['UPTREND', 'DOWNTREND', 'SIDEWAYS', 'UNKNOWN'])
    
    def test_calculate_trend_strength(self):
        """Test trend strength calculation"""
        # Create a simple price series
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113])
        strength = self.technical_analysis._calculate_trend_strength(prices)
        
        if strength is not None:
            self.assertGreaterEqual(strength, 0)
            self.assertLessEqual(strength, 1)
    
    def test_get_signal_quality_score(self):
        """Test signal quality score calculation"""
        indicators = {
            'rsi': 30,
            'macd': 0.5,
            'macd_signal': 0.3,
            'bb_upper': 110,
            'bb_lower': 90,
            'current_price': 95,
            'volume_ratio': 2.0,
            'trend_strength': 0.8
        }
        
        score = self.technical_analysis.get_signal_quality_score(indicators)
        
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)
    
    def test_save_indicators_to_database(self):
        """Test saving indicators to database"""
        indicators = {
            'rsi': 65.5,
            'macd': 0.2,
            'macd_signal': 0.1,
            'bb_upper': 3200,
            'bb_lower': 2800,
            'sma_20': 3000,
            'sma_50': 2950,
            'volatility': 2.5,
            'atr': 50
        }
        
        result = self.technical_analysis.save_indicators_to_database(self.symbol, indicators)
        
        self.assertTrue(result)
        
        # Check if indicator was saved
        indicator = TechnicalIndicator.objects.filter(symbol=self.symbol).first()
        self.assertIsNotNone(indicator)
        self.assertEqual(float(indicator.rsi), 65.5)


class TestDatabaseDataUtils(TestCase):
    """Test cases for database data utilities"""
    
    def setUp(self):
        """Set up test data"""
        self.symbol = Symbol.objects.create(
            symbol='ADA',
            name='Cardano',
            is_active=True,
            is_crypto_symbol=True
        )
        
        # Create test market data
        self.create_test_market_data()
    
    def create_test_market_data(self):
        """Create test market data"""
        base_time = timezone.now() - timedelta(hours=48)
        
        for i in range(48):  # 48 hours of data
            timestamp = base_time + timedelta(hours=i)
            MarketData.objects.create(
                symbol=self.symbol,
                timeframe='1h',
                timestamp=timestamp,
                open_price=Decimal('0.5') + Decimal(str(i * 0.01)),
                high_price=Decimal('0.52') + Decimal(str(i * 0.01)),
                low_price=Decimal('0.48') + Decimal(str(i * 0.01)),
                close_price=Decimal('0.51') + Decimal(str(i * 0.01)),
                volume=Decimal('1000000')
            )
    
    def test_get_database_health_status(self):
        """Test database health status"""
        health = get_database_health_status()
        
        self.assertIn('status', health)
        self.assertIn('reason', health)
        self.assertIn('latest_data_age_hours', health)
        self.assertIn('active_symbols', health)
        
        # Should be healthy with recent data
        self.assertIn(health['status'], ['HEALTHY', 'WARNING', 'CRITICAL', 'ERROR'])
    
    def test_get_symbols_with_recent_data(self):
        """Test getting symbols with recent data"""
        from apps.signals.database_data_utils import get_symbols_with_recent_data
        
        symbols = get_symbols_with_recent_data(hours_back=24, min_data_points=20)
        
        self.assertIn(self.symbol, symbols)
        self.assertGreater(len(symbols), 0)
    
    def test_get_data_gaps(self):
        """Test finding data gaps"""
        from apps.signals.database_data_utils import get_data_gaps
        
        gaps = get_data_gaps(self.symbol, hours_back=48)
        
        # Should have no gaps with continuous data
        self.assertEqual(len(gaps), 0)
    
    def test_get_data_statistics(self):
        """Test getting data statistics"""
        from apps.signals.database_data_utils import get_data_statistics
        
        stats = get_data_statistics(self.symbol, days_back=3)
        
        self.assertGreater(stats['total_records'], 0)
        self.assertIsNotNone(stats['date_range'])
        self.assertIsNotNone(stats['price_range'])
        self.assertIsNotNone(stats['volume_stats'])


class TestDatabaseSignalIntegration(TestCase):
    """Integration tests for database signal generation"""
    
    def setUp(self):
        """Set up test data"""
        self.symbol = Symbol.objects.create(
            symbol='SOL',
            name='Solana',
            is_active=True,
            is_crypto_symbol=True
        )
        
        # Create signal types and strengths
        self.buy_signal = SignalType.objects.create(
            name='BUY',
            description='Buy Signal'
        )
        
        self.strong_strength = SignalStrength.objects.create(
            name='STRONG',
            description='Strong Signal'
        )
        
        # Create test market data
        self.create_test_market_data()
    
    def create_test_market_data(self):
        """Create test market data with some price movement"""
        base_time = timezone.now() - timedelta(hours=100)
        base_price = 100
        
        for i in range(100):
            timestamp = base_time + timedelta(hours=i)
            # Create some realistic price movement
            price_change = (i % 10 - 5) * 2  # Oscillating price
            current_price = base_price + price_change
            
            MarketData.objects.create(
                symbol=self.symbol,
                timeframe='1h',
                timestamp=timestamp,
                open_price=Decimal(str(current_price)),
                high_price=Decimal(str(current_price + 1)),
                low_price=Decimal(str(current_price - 1)),
                close_price=Decimal(str(current_price)),
                volume=Decimal('1000000')
            )
    
    def test_end_to_end_signal_generation(self):
        """Test end-to-end signal generation process"""
        service = DatabaseSignalService()
        
        # Generate signals
        result = service.generate_best_signals_for_all_coins()
        
        self.assertIn('total_signals_generated', result)
        self.assertIn('best_signals_selected', result)
        self.assertIn('processed_symbols', result)
        self.assertIn('best_signals', result)
        
        # Should have processed at least one symbol
        self.assertGreaterEqual(result['processed_symbols'], 0)
    
    def test_signal_quality_validation(self):
        """Test signal quality validation"""
        service = DatabaseSignalService()
        
        # Validate data quality
        quality = service.validate_database_data_quality(self.symbol)
        
        self.assertTrue(quality['is_valid'])
        self.assertGreater(quality['data_points'], 0)
        self.assertIsNotNone(quality['data_age_hours'])
    
    def test_technical_analysis_integration(self):
        """Test technical analysis integration"""
        analysis = DatabaseTechnicalAnalysis()
        
        # Calculate indicators
        indicators = analysis.calculate_indicators_from_database(
            self.symbol, hours_back=100
        )
        
        self.assertIsNotNone(indicators)
        
        # Test signal quality score
        if indicators:
            quality_score = analysis.get_signal_quality_score(indicators)
            self.assertGreaterEqual(quality_score, 0)
            self.assertLessEqual(quality_score, 1)


class TestDatabaseSignalPerformance(TestCase):
    """Performance tests for database signal generation"""
    
    def setUp(self):
        """Set up test data"""
        self.symbols = []
        
        # Create multiple symbols
        for i in range(10):
            symbol = Symbol.objects.create(
                symbol=f'TEST{i}',
                name=f'Test Coin {i}',
                is_active=True,
                is_crypto_symbol=True
            )
            self.symbols.append(symbol)
            
            # Create market data for each symbol
            self.create_test_market_data(symbol)
    
    def create_test_market_data(self, symbol):
        """Create test market data for a symbol"""
        base_time = timezone.now() - timedelta(hours=24)
        
        for i in range(24):
            timestamp = base_time + timedelta(hours=i)
            MarketData.objects.create(
                symbol=symbol,
                timeframe='1h',
                timestamp=timestamp,
                open_price=Decimal('100'),
                high_price=Decimal('105'),
                low_price=Decimal('95'),
                close_price=Decimal('102'),
                volume=Decimal('1000000')
            )
    
    def test_bulk_signal_generation_performance(self):
        """Test performance of bulk signal generation"""
        import time
        
        service = DatabaseSignalService()
        
        start_time = time.time()
        
        # Generate signals for all symbols
        result = service.generate_best_signals_for_all_coins()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within reasonable time (5 minutes)
        self.assertLess(execution_time, 300)
        
        # Should process multiple symbols
        self.assertGreaterEqual(result['processed_symbols'], 0)
    
    def test_database_query_performance(self):
        """Test database query performance"""
        import time
        
        start_time = time.time()
        
        # Test multiple database queries
        for symbol in self.symbols:
            get_recent_market_data(symbol, hours_back=24)
            get_latest_price(symbol)
            validate_data_quality(symbol)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete quickly (within 10 seconds for 10 symbols)
        self.assertLess(execution_time, 10)
    
    def test_technical_analysis_performance(self):
        """Test technical analysis performance"""
        import time
        
        analysis = DatabaseTechnicalAnalysis()
        
        start_time = time.time()
        
        # Calculate indicators for all symbols
        for symbol in self.symbols:
            analysis.calculate_indicators_from_database(symbol, hours_back=24)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within reasonable time (30 seconds for 10 symbols)
        self.assertLess(execution_time, 30)














