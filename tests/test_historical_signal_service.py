"""
Unit tests for HistoricalSignalService
Tests the HistoricalSignalService functionality added in Phase 1
"""

import os
import sys
import django
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.test import TestCase
from django.utils import timezone

from apps.signals.services import HistoricalSignalService
from apps.signals.models import TradingSignal, SignalType
from apps.trading.models import Symbol
from apps.data.models import MarketData


class HistoricalSignalServiceTest(TestCase):
    """Test cases for HistoricalSignalService"""
    
    def setUp(self):
        """Set up test data"""
        self.service = HistoricalSignalService()
        
        self.symbol = Symbol.objects.create(
            symbol='XRP',
            name='Ripple',
            is_active=True
        )
        
        self.signal_type = SignalType.objects.create(
            name='BUY',
            description='Buy Signal',
            color='#00ff00'
        )
        
        self.start_date = datetime(2025, 1, 1, 0, 0, 0)
        self.end_date = datetime(2025, 8, 31, 23, 59, 59)
    
    def test_validate_date_range_valid(self):
        """Test valid date range validation"""
        is_valid, error_msg = self.service.validate_date_range(self.start_date, self.end_date)
        
        self.assertTrue(is_valid)
        self.assertEqual(error_msg, '')
    
    def test_validate_date_range_start_after_end(self):
        """Test validation when start date is after end date"""
        is_valid, error_msg = self.service.validate_date_range(self.end_date, self.start_date)
        
        self.assertFalse(is_valid)
        self.assertEqual(error_msg, 'Start date must be before end date')
    
    def test_validate_date_range_too_long(self):
        """Test validation when date range exceeds 2 years"""
        long_end_date = self.start_date + timedelta(days=800)  # More than 2 years
        
        is_valid, error_msg = self.service.validate_date_range(self.start_date, long_end_date)
        
        self.assertFalse(is_valid)
        self.assertEqual(error_msg, 'Date range cannot exceed 2 years')
    
    def test_validate_date_range_start_before_2020(self):
        """Test validation when start date is before 2020"""
        old_start_date = datetime(2019, 12, 31)
        
        is_valid, error_msg = self.service.validate_date_range(old_start_date, self.end_date)
        
        self.assertFalse(is_valid)
        self.assertEqual(error_msg, 'Start date cannot be before 2020')
    
    def test_validate_date_range_end_in_future(self):
        """Test validation when end date is in the future"""
        future_end_date = timezone.now() + timedelta(days=1)
        
        is_valid, error_msg = self.service.validate_date_range(self.start_date, future_end_date)
        
        self.assertFalse(is_valid)
        self.assertEqual(error_msg, 'End date cannot be in the future')
    
    def test_get_available_symbols(self):
        """Test getting available symbols"""
        # Create additional symbols
        Symbol.objects.create(symbol='BTC', name='Bitcoin', is_active=True)
        Symbol.objects.create(symbol='ETH', name='Ethereum', is_active=True)
        Symbol.objects.create(symbol='INACTIVE', name='Inactive', is_active=False)
        
        symbols = self.service.get_available_symbols()
        
        # Should return only active symbols, ordered by symbol
        self.assertEqual(len(symbols), 3)
        self.assertEqual(symbols[0].symbol, 'BTC')
        self.assertEqual(symbols[1].symbol, 'ETH')
        self.assertEqual(symbols[2].symbol, 'XRP')
    
    @patch('apps.signals.services.SignalGenerationService')
    def test_generate_signals_for_period_with_existing_data(self, mock_signal_service):
        """Test signal generation when historical data exists"""
        # Create some historical market data
        MarketData.objects.create(
            symbol=self.symbol,
            timestamp=self.start_date,
            open_price=0.45,
            high_price=0.47,
            low_price=0.43,
            close_price=0.46,
            volume=1000000
        )
        
        # Mock the signal generation service
        mock_service_instance = MagicMock()
        mock_signal_service.return_value = mock_service_instance
        
        # Create mock signals
        mock_signal1 = MagicMock()
        mock_signal1.id = 1
        mock_signal1.symbol = self.symbol
        mock_signal1.signal_type = self.signal_type
        mock_signal1.strength = 0.8
        mock_signal1.confidence_score = 0.85
        mock_signal1.confidence_level = 'HIGH'
        mock_signal1.entry_price = 0.45
        mock_signal1.target_price = 0.50
        mock_signal1.stop_loss = 0.42
        mock_signal1.risk_reward_ratio = 2.0
        mock_signal1.timeframe = '1H'
        mock_signal1.entry_point_type = 'BREAKOUT'
        mock_signal1.quality_score = 0.9
        mock_signal1.created_at = self.start_date + timedelta(hours=1)
        mock_signal1.expires_at = self.start_date + timedelta(hours=25)
        
        mock_service_instance.generate_signals_for_symbol.return_value = [mock_signal1]
        
        # Generate signals
        signals = self.service.generate_signals_for_period(
            self.symbol, self.start_date, self.end_date
        )
        
        # Verify results
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0], mock_signal1)
        
        # Verify service was called correctly
        mock_service_instance.generate_signals_for_symbol.assert_called_once_with(self.symbol)
    
    @patch('apps.signals.services.SignalGenerationService')
    def test_generate_signals_for_period_no_data(self, mock_signal_service):
        """Test signal generation when no historical data exists"""
        # Mock the signal generation service
        mock_service_instance = MagicMock()
        mock_signal_service.return_value = mock_service_instance
        mock_service_instance.generate_signals_for_symbol.return_value = []
        
        # Generate signals (should create synthetic data)
        signals = self.service.generate_signals_for_period(
            self.symbol, self.start_date, self.end_date
        )
        
        # Verify results
        self.assertEqual(len(signals), 0)
        
        # Verify synthetic data was created
        market_data = MarketData.objects.filter(symbol=self.symbol)
        self.assertTrue(market_data.exists())
    
    def test_generate_signals_for_period_invalid_dates(self):
        """Test signal generation with invalid date range"""
        with self.assertRaises(ValueError) as context:
            self.service.generate_signals_for_period(
                self.symbol, self.end_date, self.start_date
            )
        
        self.assertIn('Start date must be before end date', str(context.exception))
    
    @patch('apps.signals.services.SignalGenerationService')
    def test_generate_signals_for_period_exception_handling(self, mock_signal_service):
        """Test exception handling in signal generation"""
        # Mock the signal generation service to raise an exception
        mock_service_instance = MagicMock()
        mock_signal_service.return_value = mock_service_instance
        mock_service_instance.generate_signals_for_symbol.side_effect = Exception('Test error')
        
        # Generate signals - should return empty list and not raise exception
        signals = self.service.generate_signals_for_period(
            self.symbol, self.start_date, self.end_date
        )
        
        self.assertEqual(len(signals), 0)
    
    def test_get_historical_data(self):
        """Test getting historical data for a symbol and date range"""
        # Create test market data
        data1 = MarketData.objects.create(
            symbol=self.symbol,
            timestamp=self.start_date,
            open_price=0.45,
            high_price=0.47,
            low_price=0.43,
            close_price=0.46,
            volume=1000000
        )
        
        data2 = MarketData.objects.create(
            symbol=self.symbol,
            timestamp=self.start_date + timedelta(hours=1),
            open_price=0.46,
            high_price=0.48,
            low_price=0.44,
            close_price=0.47,
            volume=1200000
        )
        
        # Get historical data
        historical_data = self.service._get_historical_data(
            self.symbol, self.start_date, self.end_date
        )
        
        # Verify results
        self.assertEqual(historical_data.count(), 2)
        self.assertEqual(historical_data[0], data1)
        self.assertEqual(historical_data[1], data2)
    
    def test_get_historical_data_no_data(self):
        """Test getting historical data when no data exists"""
        historical_data = self.service._get_historical_data(
            self.symbol, self.start_date, self.end_date
        )
        
        self.assertEqual(historical_data.count(), 0)
    
    def test_generate_synthetic_data(self):
        """Test synthetic data generation"""
        # Generate synthetic data
        self.service._generate_synthetic_data(self.symbol, self.start_date, self.end_date)
        
        # Verify data was created
        market_data = MarketData.objects.filter(symbol=self.symbol)
        self.assertTrue(market_data.exists())
        
        # Verify data structure
        first_data = market_data.first()
        self.assertEqual(first_data.symbol, self.symbol)
        self.assertIsNotNone(first_data.open_price)
        self.assertIsNotNone(first_data.high_price)
        self.assertIsNotNone(first_data.low_price)
        self.assertIsNotNone(first_data.close_price)
        self.assertIsNotNone(first_data.volume)
    
    def test_generate_synthetic_data_xrp_pricing(self):
        """Test that XRP gets appropriate pricing in synthetic data"""
        self.service._generate_synthetic_data(self.symbol, self.start_date, self.end_date)
        
        market_data = MarketData.objects.filter(symbol=self.symbol).first()
        
        # XRP should have realistic pricing (around 0.50)
        self.assertGreater(market_data.close_price, 0.01)
        self.assertLess(market_data.close_price, 10.0)
    
    def test_generate_synthetic_data_other_symbol_pricing(self):
        """Test that non-XRP symbols get appropriate pricing"""
        btc_symbol = Symbol.objects.create(symbol='BTC', name='Bitcoin', is_active=True)
        
        self.service._generate_synthetic_data(btc_symbol, self.start_date, self.end_date)
        
        market_data = MarketData.objects.filter(symbol=btc_symbol).first()
        
        # BTC should have realistic pricing (around 100)
        self.assertGreater(market_data.close_price, 10.0)
        self.assertLess(market_data.close_price, 1000.0)
    
    def test_generate_synthetic_data_realistic_volatility(self):
        """Test that synthetic data has realistic volatility"""
        self.service._generate_synthetic_data(self.symbol, self.start_date, self.end_date)
        
        market_data = MarketData.objects.filter(symbol=self.symbol).order_by('timestamp')
        
        # Check that prices have reasonable volatility
        prices = [data.close_price for data in market_data[:10]]  # First 10 data points
        
        if len(prices) > 1:
            price_changes = [abs(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
            avg_change = sum(price_changes) / len(price_changes)
            
            # Average change should be reasonable (not too volatile, not too flat)
            self.assertGreater(avg_change, 0.001)  # At least 0.1% change
            self.assertLess(avg_change, 0.1)  # Not more than 10% change
    
    def test_generate_synthetic_data_volume_realistic(self):
        """Test that synthetic data has realistic volume"""
        self.service._generate_synthetic_data(self.symbol, self.start_date, self.end_date)
        
        market_data = MarketData.objects.filter(symbol=self.symbol)
        
        for data in market_data:
            # Volume should be realistic (1M to 10M range)
            self.assertGreaterEqual(data.volume, 1000000)
            self.assertLessEqual(data.volume, 10000000)
    
    def test_generate_synthetic_data_ohlc_consistency(self):
        """Test that OHLC data is consistent"""
        self.service._generate_synthetic_data(self.symbol, self.start_date, self.end_date)
        
        market_data = MarketData.objects.filter(symbol=self.symbol)
        
        for data in market_data:
            # High should be >= all other prices
            self.assertGreaterEqual(data.high_price, data.open_price)
            self.assertGreaterEqual(data.high_price, data.close_price)
            self.assertGreaterEqual(data.high_price, data.low_price)
            
            # Low should be <= all other prices
            self.assertLessEqual(data.low_price, data.open_price)
            self.assertLessEqual(data.low_price, data.close_price)
            self.assertLessEqual(data.low_price, data.high_price)
    
    def test_service_initialization(self):
        """Test that service initializes correctly"""
        service = HistoricalSignalService()
        
        self.assertIsNotNone(service.signal_service)
        self.assertIsNotNone(service.logger)
    
    def test_edge_case_same_start_end_date(self):
        """Test edge case where start and end dates are the same"""
        same_date = datetime(2025, 1, 1, 12, 0, 0)
        
        is_valid, error_msg = self.service.validate_date_range(same_date, same_date)
        
        self.assertFalse(is_valid)
        self.assertEqual(error_msg, 'Start date must be before end date')
    
    def test_edge_case_one_day_range(self):
        """Test edge case with one day range"""
        start = datetime(2025, 1, 1, 0, 0, 0)
        end = datetime(2025, 1, 2, 0, 0, 0)
        
        is_valid, error_msg = self.service.validate_date_range(start, end)
        
        self.assertTrue(is_valid)
        self.assertEqual(error_msg, '')


if __name__ == '__main__':
    import unittest
    unittest.main()
































































