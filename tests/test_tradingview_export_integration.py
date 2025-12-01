"""
Integration tests for TradingViewExportAPIView
Tests the TradingView export functionality added in Phase 3
"""

import os
import sys
import django
import json
from datetime import datetime, date, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.signals.models import BacktestSearch, TradingSignal, SignalType
from apps.trading.models import Symbol
from apps.data.models import MarketData


class TradingViewExportAPIViewIntegrationTest(TestCase):
    """Integration tests for TradingViewExportAPIView"""
    
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
        
        # Create signal types
        self.buy_signal_type = SignalType.objects.create(
            name='BUY',
            description='Buy Signal',
            color='#00ff00'
        )
        
        self.sell_signal_type = SignalType.objects.create(
            name='SELL',
            description='Sell Signal',
            color='#ff0000'
        )
        
        # Test dates
        self.start_date = datetime(2025, 1, 1, 0, 0, 0)
        self.end_date = datetime(2025, 8, 31, 23, 59, 59)
        
        # Create test signals
        self._create_test_signals()
        
        # Create test search
        self.search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date.date(),
            end_date=self.end_date.date(),
            signals_generated=3,
            search_name='Test XRP Search',
            notes='Test search for XRP signals'
        )
    
    def _create_test_signals(self):
        """Create test trading signals"""
        # Create BUY signal
        TradingSignal.objects.create(
            symbol=self.symbol,
            signal_type=self.buy_signal_type,
            strength=0.8,
            confidence_score=0.85,
            confidence_level='HIGH',
            entry_price=0.45,
            target_price=0.50,
            stop_loss=0.42,
            risk_reward_ratio=2.0,
            timeframe='1H',
            entry_point_type='BREAKOUT',
            quality_score=0.9,
            created_at=self.start_date + timedelta(hours=1),
            expires_at=self.start_date + timedelta(hours=25)
        )
        
        # Create SELL signal
        TradingSignal.objects.create(
            symbol=self.symbol,
            signal_type=self.sell_signal_type,
            strength=0.7,
            confidence_score=0.75,
            confidence_level='MEDIUM',
            entry_price=0.52,
            target_price=0.48,
            stop_loss=0.55,
            risk_reward_ratio=1.5,
            timeframe='4H',
            entry_point_type='REVERSAL',
            quality_score=0.8,
            created_at=self.start_date + timedelta(hours=5),
            expires_at=self.start_date + timedelta(hours=29)
        )
        
        # Create another BUY signal
        TradingSignal.objects.create(
            symbol=self.symbol,
            signal_type=self.buy_signal_type,
            strength=0.9,
            confidence_score=0.95,
            confidence_level='HIGH',
            entry_price=0.48,
            target_price=0.55,
            stop_loss=0.45,
            risk_reward_ratio=2.5,
            timeframe='1D',
            entry_point_type='SUPPORT',
            quality_score=0.95,
            created_at=self.start_date + timedelta(days=1),
            expires_at=self.start_date + timedelta(days=2)
        )
    
    def test_tradingview_export_requires_login(self):
        """Test that TradingView export API requires authentication"""
        response = self.client.get('/signals/api/tradingview-export/')
        
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_tradingview_export_csv_format(self):
        """Test CSV export format"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=csv')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Check CSV content
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 3 data rows
        self.assertEqual(len(lines), 4)
        
        # Check header
        header = lines[0]
        expected_columns = ['timestamp', 'symbol', 'signal_type', 'entry_price', 'target_price', 'stop_loss']
        for col in expected_columns:
            self.assertIn(col, header)
        
        # Check data rows
        for i in range(1, 4):
            data_line = lines[i]
            self.assertIn('XRP', data_line)
            self.assertIn('BUY', data_line)  # At least one BUY signal
    
    def test_tradingview_export_json_format(self):
        """Test JSON export format"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Check JSON content
        data = json.loads(response.content)
        self.assertIn('signals', data)
        self.assertIn('metadata', data)
        
        signals = data['signals']
        self.assertEqual(len(signals), 3)
        
        # Check signal structure
        signal = signals[0]
        required_fields = ['timestamp', 'symbol', 'signal_type', 'entry_price', 'target_price', 'stop_loss']
        for field in required_fields:
            self.assertIn(field, signal)
    
    def test_tradingview_export_pinescript_format(self):
        """Test Pine Script export format"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=pinescript')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        
        # Check Pine Script content
        content = response.content.decode('utf-8')
        
        # Should contain Pine Script specific elements
        self.assertIn('//@version=5', content)
        self.assertIn('indicator("AI Trading Signals"', content)
        self.assertIn('plotshape(', content)
        self.assertIn('XRP', content)
    
    def test_tradingview_export_default_format(self):
        """Test default export format (CSV)"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
    
    def test_tradingview_export_with_search_id(self):
        """Test export with specific search ID"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(f'/signals/api/tradingview-export/?search_id={self.search.id}')
        
        self.assertEqual(response.status_code, 200)
        
        # Check that only signals from the specified search are exported
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 3 data rows (all signals)
        self.assertEqual(len(lines), 4)
    
    def test_tradingview_export_with_symbol_filter(self):
        """Test export with symbol filter"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?symbol=XRP')
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 3 data rows (all XRP signals)
        self.assertEqual(len(lines), 4)
        
        # All data lines should contain XRP
        for i in range(1, 4):
            self.assertIn('XRP', lines[i])
    
    def test_tradingview_export_with_signal_type_filter(self):
        """Test export with signal type filter"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?signal_type=BUY')
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 2 data rows (2 BUY signals)
        self.assertEqual(len(lines), 3)
        
        # All data lines should contain BUY
        for i in range(1, 3):
            self.assertIn('BUY', lines[i])
    
    def test_tradingview_export_with_date_range(self):
        """Test export with date range filter"""
        self.client.login(username='testuser', password='testpass123')
        
        start_date = (self.start_date + timedelta(hours=2)).isoformat()
        end_date = (self.start_date + timedelta(hours=6)).isoformat()
        
        response = self.client.get(
            f'/signals/api/tradingview-export/?start_date={start_date}&end_date={end_date}'
        )
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 1 data row (1 signal in range)
        self.assertEqual(len(lines), 2)
    
    def test_tradingview_export_with_quality_threshold(self):
        """Test export with quality threshold filter"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?min_quality=0.9')
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 2 data rows (2 signals with quality >= 0.9)
        self.assertEqual(len(lines), 3)
    
    def test_tradingview_export_with_confidence_threshold(self):
        """Test export with confidence threshold filter"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?min_confidence=0.8')
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 2 data rows (2 signals with confidence >= 0.8)
        self.assertEqual(len(lines), 3)
    
    def test_tradingview_export_invalid_search_id(self):
        """Test export with invalid search ID"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?search_id=99999')
        
        self.assertEqual(response.status_code, 404)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Search not found', response_data['error'])
    
    def test_tradingview_export_unauthorized_search(self):
        """Test export with search ID belonging to different user"""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        # Create search for other user
        other_search = BacktestSearch.objects.create(
            user=other_user,
            symbol=self.symbol,
            start_date=self.start_date.date(),
            end_date=self.end_date.date()
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(f'/signals/api/tradingview-export/?search_id={other_search.id}')
        
        self.assertEqual(response.status_code, 403)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Access denied', response_data['error'])
    
    def test_tradingview_export_no_signals(self):
        """Test export when no signals exist"""
        # Create user with no signals
        empty_user = User.objects.create_user(
            username='emptyuser',
            email='empty@example.com',
            password='testpass123'
        )
        
        self.client.login(username='emptyuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/')
        
        self.assertEqual(response.status_code, 200)
        
        # CSV should have only header
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        self.assertEqual(len(lines), 1)  # Only header
    
    def test_tradingview_export_invalid_format(self):
        """Test export with invalid format"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=invalid')
        
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Invalid format', response_data['error'])
    
    def test_tradingview_export_csv_filename(self):
        """Test CSV export filename"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=csv')
        
        self.assertEqual(response.status_code, 200)
        
        content_disposition = response['Content-Disposition']
        self.assertIn('attachment', content_disposition)
        self.assertIn('filename=', content_disposition)
        self.assertIn('.csv', content_disposition)
    
    def test_tradingview_export_json_filename(self):
        """Test JSON export filename"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=json')
        
        self.assertEqual(response.status_code, 200)
        
        content_disposition = response['Content-Disposition']
        self.assertIn('attachment', content_disposition)
        self.assertIn('filename=', content_disposition)
        self.assertIn('.json', content_disposition)
    
    def test_tradingview_export_pinescript_filename(self):
        """Test Pine Script export filename"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=pinescript')
        
        self.assertEqual(response.status_code, 200)
        
        content_disposition = response['Content-Disposition']
        self.assertIn('attachment', content_disposition)
        self.assertIn('filename=', content_disposition)
        self.assertIn('.pine', content_disposition)
    
    def test_tradingview_export_metadata(self):
        """Test export metadata in JSON format"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=json')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        metadata = data['metadata']
        
        self.assertIn('export_timestamp', metadata)
        self.assertIn('total_signals', metadata)
        self.assertIn('filters_applied', metadata)
        self.assertEqual(metadata['total_signals'], 3)
    
    def test_tradingview_export_pinescript_syntax(self):
        """Test Pine Script syntax correctness"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/tradingview-export/?format=pinescript')
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check Pine Script syntax elements
        self.assertIn('//@version=5', content)
        self.assertIn('indicator(', content)
        self.assertIn('plotshape(', content)
        self.assertIn('if ', content)
        self.assertIn('strategy(', content)
        
        # Check that it's valid Pine Script structure
        lines = content.split('\n')
        self.assertGreater(len(lines), 10)  # Should be a substantial script
    
    def test_tradingview_export_multiple_filters(self):
        """Test export with multiple filters applied"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(
            '/signals/api/tradingview-export/?symbol=XRP&signal_type=BUY&min_quality=0.8'
        )
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 2 data rows (2 BUY signals with quality >= 0.8)
        self.assertEqual(len(lines), 3)
        
        # All data lines should contain XRP and BUY
        for i in range(1, 3):
            self.assertIn('XRP', lines[i])
            self.assertIn('BUY', lines[i])
    
    def test_tradingview_export_large_dataset(self):
        """Test export with large dataset"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create many signals
        for i in range(100):
            TradingSignal.objects.create(
                symbol=self.symbol,
                signal_type=self.buy_signal_type,
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
        
        response = self.client.get('/signals/api/tradingview-export/?format=csv')
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        lines = content.strip().split('\n')
        
        # Should have header + 103 data rows (3 original + 100 new)
        self.assertEqual(len(lines), 104)


if __name__ == '__main__':
    import unittest
    unittest.main()
































































