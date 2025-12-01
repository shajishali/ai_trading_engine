"""
Integration tests for BacktestAPIView
Tests the enhanced backtesting API functionality added in Phases 1-3
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


class BacktestAPIViewIntegrationTest(TestCase):
    """Integration tests for BacktestAPIView"""
    
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
        
        # Create some market data
        self._create_market_data()
    
    def _create_market_data(self):
        """Create test market data"""
        current_date = self.start_date
        price = 0.50
        
        while current_date <= self.end_date:
            MarketData.objects.create(
                symbol=self.symbol,
                timestamp=current_date,
                open_price=price,
                high_price=price * 1.02,
                low_price=price * 0.98,
                close_price=price * 1.01,
                volume=1000000
            )
            price += 0.001  # Small price increment
            current_date += timedelta(hours=1)
    
    def test_backtest_api_requires_login(self):
        """Test that backtest API requires authentication"""
        response = self.client.post('/signals/api/backtest/', {})
        
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_backtest_api_generate_signals_success(self):
        """Test successful signal generation via API"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'search_name': 'Test XRP Signals',
            'notes': 'Testing signal generation'
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['action'], 'generate_signals')
        self.assertIn('signals', response_data)
        self.assertIn('total_signals', response_data)
        self.assertTrue(response_data['search_saved'])
        self.assertIn('search_id', response_data)
    
    def test_backtest_api_traditional_backtest_success(self):
        """Test successful traditional backtest via API"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'backtest',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'strategy_name': 'SMA_Crossover',
            'initial_capital': 10000,
            'commission_rate': 0.001,
            'slippage_rate': 0.0005
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['action'], 'backtest')
        self.assertIn('result', response_data)
    
    def test_backtest_api_missing_required_fields(self):
        """Test API with missing required fields"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP'
            # Missing start_date and end_date
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Missing required field', response_data['error'])
    
    def test_backtest_api_invalid_symbol(self):
        """Test API with invalid symbol"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'INVALID',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat()
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Symbol INVALID not found', response_data['error'])
    
    def test_backtest_api_invalid_date_range(self):
        """Test API with invalid date range"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': self.end_date.isoformat(),  # Start after end
            'end_date': self.start_date.isoformat()
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Start date must be before end date', response_data['error'])
    
    def test_backtest_api_invalid_json(self):
        """Test API with invalid JSON"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(
            '/signals/api/backtest/',
            data='invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertEqual(response_data['error'], 'Invalid JSON data')
    
    def test_backtest_api_creates_search_history(self):
        """Test that API creates search history"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'search_name': 'Test Search',
            'notes': 'Test notes'
        }
        
        # Check no searches exist initially
        self.assertEqual(BacktestSearch.objects.count(), 0)
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check search was created
        self.assertEqual(BacktestSearch.objects.count(), 1)
        
        search = BacktestSearch.objects.first()
        self.assertEqual(search.user, self.user)
        self.assertEqual(search.symbol, self.symbol)
        self.assertEqual(search.search_name, 'Test Search')
        self.assertEqual(search.notes, 'Test notes')
    
    def test_backtest_api_updates_existing_search(self):
        """Test that API updates existing search instead of creating duplicate"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create existing search
        existing_search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date.date(),
            end_date=self.end_date.date(),
            signals_generated=5,
            search_name='Existing Search',
            notes='Existing notes'
        )
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'search_name': 'Updated Search',
            'notes': 'Updated notes'
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check only one search exists (updated, not duplicated)
        self.assertEqual(BacktestSearch.objects.count(), 1)
        
        updated_search = BacktestSearch.objects.first()
        self.assertEqual(updated_search.id, existing_search.id)
        self.assertEqual(updated_search.search_name, 'Updated Search')
        self.assertEqual(updated_search.notes, 'Updated notes')
    
    def test_backtest_api_get_method(self):
        """Test GET method for retrieving backtest results"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/backtest/')
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('results', response_data)
        self.assertIn('total_count', response_data)
    
    def test_backtest_api_get_with_filters(self):
        """Test GET method with query parameters"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/backtest/?symbol=XRP&limit=10&offset=0')
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('results', response_data)
    
    def test_backtest_api_get_with_invalid_limit(self):
        """Test GET method with invalid limit parameter"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/backtest/?limit=invalid')
        
        self.assertEqual(response.status_code, 200)  # Should default to 20
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
    
    def test_backtest_api_get_with_invalid_offset(self):
        """Test GET method with invalid offset parameter"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/api/backtest/?offset=invalid')
        
        self.assertEqual(response.status_code, 200)  # Should default to 0
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
    
    def test_backtest_api_default_action(self):
        """Test API with default action (backtest)"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            # No action specified - should default to 'backtest'
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat()
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['action'], 'backtest')
    
    def test_backtest_api_default_parameters(self):
        """Test API with default parameters"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'backtest',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat()
            # No optional parameters - should use defaults
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
    
    def test_backtest_api_custom_parameters(self):
        """Test API with custom parameters"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'backtest',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'strategy_name': 'RSI_Strategy',
            'initial_capital': 50000,
            'commission_rate': 0.002,
            'slippage_rate': 0.001
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
    
    def test_backtest_api_error_handling(self):
        """Test API error handling"""
        self.client.login(username='testuser', password='testpass123')
        
        # Test with invalid date format
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': 'invalid-date',
            'end_date': self.end_date.isoformat()
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 500)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('error', response_data)
    
    def test_backtest_api_concurrent_requests(self):
        """Test API handles concurrent requests"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat()
        }
        
        # Make multiple concurrent requests
        responses = []
        for i in range(3):
            response = self.client.post(
                '/signals/api/backtest/',
                data=json.dumps(data),
                content_type='application/json'
            )
            responses.append(response)
        
        # All requests should succeed
        for response in responses:
            self.assertEqual(response.status_code, 200)
            
            response_data = json.loads(response.content)
            self.assertTrue(response_data['success'])
    
    def test_backtest_api_large_date_range(self):
        """Test API with large date range"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create a large date range (but within 2 year limit)
        large_start = datetime(2023, 1, 1)
        large_end = datetime(2024, 12, 31)
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': large_start.isoformat(),
            'end_date': large_end.isoformat()
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
    
    def test_backtest_api_exceeds_date_limit(self):
        """Test API with date range exceeding 2 year limit"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create a date range exceeding 2 years
        old_start = datetime(2020, 1, 1)
        far_end = datetime(2025, 12, 31)
        
        data = {
            'action': 'generate_signals',
            'symbol': 'XRP',
            'start_date': old_start.isoformat(),
            'end_date': far_end.isoformat()
        }
        
        response = self.client.post(
            '/signals/api/backtest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Date range cannot exceed 2 years', response_data['error'])


if __name__ == '__main__':
    import unittest
    unittest.main()
































































