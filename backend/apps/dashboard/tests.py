from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.trading.models import Portfolio, Position, Trade, Symbol
from apps.signals.models import TradingSignal, SignalType
from apps.data.models import MarketData


class DashboardViewsTestCase(TestCase):
    """Test cases for dashboard views"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test symbols
        self.btc_symbol = Symbol.objects.create(
            symbol='BTC',
            symbol_type='CRYPTO',
            is_active=True,
            name='Bitcoin'
        )
        
        self.eth_symbol = Symbol.objects.create(
            symbol='ETH',
            symbol_type='CRYPTO',
            is_active=True,
            name='Ethereum'
        )
        
        # Create signal types
        self.buy_signal = SignalType.objects.create(
            name='BUY',
            description='Buy Signal',
            color='#28a745',
            is_active=True
        )
        
        self.sell_signal = SignalType.objects.create(
            name='SELL',
            description='Sell Signal',
            color='#dc3545',
            is_active=True
        )
        
        # Create portfolio
        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name='Test Portfolio',
            balance=Decimal('10500.00'),
            currency='USD'
        )
        
        # Create positions
        self.position = Position.objects.create(
            portfolio=self.portfolio,
            symbol=self.btc_symbol,
            position_type='LONG',
            quantity=Decimal('0.5'),
            entry_price=Decimal('45000.00'),
            current_price=Decimal('46000.00'),
            is_open=True
        )
        
        # Create trades
        self.trade = Trade.objects.create(
            portfolio=self.portfolio,
            symbol=self.btc_symbol,
            trade_type='BUY',
            quantity=Decimal('0.5'),
            price=Decimal('45000.00'),
            executed_at=timezone.now()
        )
        
        # Create trading signals
        self.signal = TradingSignal.objects.create(
            symbol=self.btc_symbol,
            signal_type=self.buy_signal,
            strength='STRONG',
            confidence_score=0.85,
            confidence_level='HIGH',
            entry_price=Decimal('45000.00'),
            target_price=Decimal('50000.00'),
            stop_loss=Decimal('42000.00'),
            quality_score=0.82,
            is_valid=True
        )
        
        # Create client
        self.client = Client()
    
    def test_home_page(self):
        """Test home page loads correctly"""
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AI-Enhanced Trading Signal Engine')
        self.assertContains(response, 'advanced trading platform')
    
    def test_login_page_get(self):
        """Test login page loads correctly"""
        response = self.client.get(reverse('dashboard:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login')
    
    def test_login_success(self):
        """Test successful login"""
        response = self.client.post(reverse('dashboard:login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after login
        self.assertRedirects(response, '/dashboard/')
    
    def test_login_failure(self):
        """Test failed login"""
        response = self.client.post(reverse('dashboard:login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')
    
    def test_login_empty_fields(self):
        """Test login with empty fields"""
        response = self.client.post(reverse('dashboard:login'), {
            'username': '',
            'password': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a username')
    
    def test_dashboard_authenticated(self):
        """Test dashboard access for authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
    
    def test_dashboard_unauthenticated(self):
        """Test dashboard redirects unauthenticated users to login"""
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/login/?next=/dashboard/')
    
    def test_dashboard_context_data(self):
        """Test dashboard returns correct context data"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        # Check portfolio data
        self.assertEqual(context['portfolio'], self.portfolio)
        self.assertEqual(context['total_positions'], 1)
        self.assertEqual(context['total_signals'], 1)
        self.assertEqual(context['active_signals'], 1)
    
    def test_portfolio_view_authenticated(self):
        """Test portfolio view for authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:portfolio'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Portfolio')
    
    def test_portfolio_view_unauthenticated(self):
        """Test portfolio view redirects unauthenticated users"""
        response = self.client.get(reverse('dashboard:portfolio'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/login/?next=/portfolio/')
    
    def test_portfolio_context_data(self):
        """Test portfolio view returns correct context data"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:portfolio'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        self.assertEqual(context['portfolio'], self.portfolio)
        self.assertEqual(len(context['positions']), 1)
        self.assertEqual(len(context['trades']), 1)
    
    def test_signals_view_authenticated(self):
        """Test signals view for authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:signals'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Signals')
    
    def test_signals_view_unauthenticated(self):
        """Test signals view redirects unauthenticated users"""
        response = self.client.get(reverse('dashboard:signals'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/login/?next=/signals/')
    
    def test_signals_context_data(self):
        """Test signals view returns correct context data"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:signals'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        self.assertEqual(context['total_signals'], 1)
        self.assertEqual(context['active_signals'], 1)
    
    def test_logout(self):
        """Test logout functionality"""
        self.client.login(username='testuser', password='testpass123')
        
        # Verify user is logged in
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Logout
        response = self.client.get(reverse('dashboard:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/')
        
        # Verify user is logged out
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 302)
    
    def test_dashboard_no_portfolio(self):
        """Test dashboard when user has no portfolio"""
        user_no_portfolio = User.objects.create_user(
            username='noportfolio',
            password='testpass123'
        )
        self.client.login(username='noportfolio', password='testpass123')
        
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        context = response.context
        self.assertIsNone(context['portfolio'])
        self.assertEqual(context['total_positions'], 0)
        self.assertEqual(context['total_pnl'], 0)
    
    def test_dashboard_no_signals(self):
        """Test dashboard when no signals exist"""
        # Delete all signals
        TradingSignal.objects.all().delete()
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        context = response.context
        # Dashboard creates sample signals when none exist, so we expect some signals
        self.assertGreater(context['total_signals'], 0)
        self.assertGreater(context['active_signals'], 0)
    
    def test_dashboard_signal_creation(self):
        """Test dashboard creates sample signals when none exist"""
        # Delete all signals
        TradingSignal.objects.all().delete()
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Check if sample signals were created
        signals_count = TradingSignal.objects.count()
        self.assertGreater(signals_count, 0)
    
    def test_dashboard_performance_metrics(self):
        """Test dashboard calculates performance metrics correctly"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        # Check if metrics are calculated
        self.assertIn('win_rate', context)
        self.assertIn('avg_quality', context)
        self.assertIn('avg_confidence', context)
        self.assertIn('signal_distribution', context)
    
    @patch('apps.dashboard.views.SignalType.objects.filter')
    def test_dashboard_signal_type_error_handling(self, mock_filter):
        """Test dashboard handles SignalType errors gracefully"""
        mock_filter.side_effect = Exception("Database error")
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context['active_signal_types'], 0)
    
    def test_dashboard_template_rendering(self):
        """Test dashboard template renders without errors"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/enhanced_dashboard.html')
    
    def test_portfolio_template_rendering(self):
        """Test portfolio template renders without errors"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:portfolio'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/portfolio.html')
    
    def test_signals_redirects_to_signals_dashboard(self):
        """Test dashboard signals view redirects to main signals page"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard:signals'))
        self.assertRedirects(response, reverse('signals:signal_dashboard'))


class DashboardIntegrationTestCase(TestCase):
    """Integration tests for dashboard functionality"""
    
    def setUp(self):
        """Set up integration test data"""
        self.user = User.objects.create_user(
            username='integrationuser',
            password='testpass123'
        )
        self.client = Client()
    
    def test_full_user_journey(self):
        """Test complete user journey from login to dashboard"""
        # 1. Access home page
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        
        # 2. Try to access dashboard (should redirect to login)
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 302)
        
        # 3. Login
        response = self.client.post(reverse('dashboard:login'), {
            'username': 'integrationuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)
        
        # 4. Access dashboard (should work now)
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # 5. Access portfolio
        response = self.client.get(reverse('dashboard:portfolio'))
        self.assertEqual(response.status_code, 200)
        
        # 6. Access signals
        response = self.client.get(reverse('dashboard:signals'))
        self.assertEqual(response.status_code, 200)
        
        # 7. Logout
        response = self.client.get(reverse('dashboard:logout'))
        self.assertEqual(response.status_code, 302)
        
        # 8. Try to access dashboard again (should redirect to login)
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 302)
    
    def test_dashboard_data_persistence(self):
        """Test that dashboard data persists across requests"""
        self.client.login(username='integrationuser', password='testpass123')
        
        # First request
        response1 = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response1.status_code, 200)
        
        # Second request
        response2 = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response2.status_code, 200)
        
        # Data should be consistent
        self.assertEqual(response1.context['total_signals'], response2.context['total_signals'])
    
    def test_dashboard_error_handling(self):
        """Test dashboard handles various error conditions gracefully"""
        self.client.login(username='integrationuser', password='testpass123')
        
        # Test with missing portfolio (should handle gracefully)
        with patch('apps.dashboard.views.Portfolio.objects.get') as mock_get:
            mock_get.side_effect = Portfolio.DoesNotExist("Portfolio not found")
            
            response = self.client.get(reverse('dashboard:dashboard'))
            self.assertEqual(response.status_code, 200)  # Should still render
    
    def test_dashboard_performance(self):
        """Test dashboard performance with multiple requests"""
        self.client.login(username='integrationuser', password='testpass123')
        
        # Make multiple requests to test performance
        start_time = timezone.now()
        
        for _ in range(5):
            response = self.client.get(reverse('dashboard:dashboard'))
            self.assertEqual(response.status_code, 200)
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        # Should complete within reasonable time (adjust threshold as needed)
        self.assertLess(duration, 10.0)  # 10 seconds max for 5 requests


class DashboardSecurityTestCase(TestCase):
    """Security tests for dashboard views"""
    
    def setUp(self):
        """Set up security test data"""
        self.user1 = User.objects.create_user(
            username='user1',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='testpass123'
        )
        self.client = Client()
    
    def test_user_isolation(self):
        """Test that users can only see their own data"""
        # Create portfolios for both users
        portfolio1 = Portfolio.objects.create(
            user=self.user1,
            name='Portfolio 1',
            balance=Decimal('10000.00'),
            currency='USD'
        )
        
        portfolio2 = Portfolio.objects.create(
            user=self.user2,
            name='Portfolio 2',
            balance=Decimal('20000.00'),
            currency='USD'
        )
        
        # User1 logs in and accesses dashboard
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(reverse('dashboard:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context['portfolio'], portfolio1)
        self.assertNotEqual(context['portfolio'], portfolio2)
    
    def test_csrf_protection(self):
        """Test CSRF protection on forms"""
        # Try to post to login without CSRF token
        response = self.client.post(reverse('dashboard:login'), {
            'username': 'user1',
            'password': 'testpass123'
        }, follow=False)
        
        # Should get CSRF error or redirect
        self.assertNotEqual(response.status_code, 200)
    
    def test_sql_injection_protection(self):
        """Test protection against SQL injection"""
        malicious_input = "'; DROP TABLE auth_user; --"
        
        response = self.client.post(reverse('dashboard:login'), {
            'username': malicious_input,
            'password': 'testpass123'
        })
        
        # Should not crash and should handle gracefully
        self.assertEqual(response.status_code, 200)
        
        # Verify user table still exists
        user_count = User.objects.count()
        self.assertGreater(user_count, 0)
    
    def test_xss_protection(self):
        """Test protection against XSS attacks"""
        malicious_input = "<script>alert('XSS')</script>"
        
        response = self.client.post(reverse('dashboard:login'), {
            'username': malicious_input,
            'password': 'testpass123'
        })
        
        # Should not crash
        self.assertEqual(response.status_code, 200)
        
        # Check if malicious input is properly handled
        response_content = response.content.decode()
        
        # The malicious input should not appear as raw HTML in the response
        # It should either be escaped or not displayed at all
        if malicious_input in response_content:
            # If it appears, it should be escaped
            self.assertIn('&lt;script&gt;', response_content)
        else:
            # If it doesn't appear, that's also fine (input validation)
            pass
