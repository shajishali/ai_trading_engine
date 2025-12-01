"""
Frontend JavaScript tests for enhanced backtesting functionality
Tests the JavaScript functionality added in Phases 2-3
"""

import os
import sys
import django
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


class FrontendJavaScriptTest(TestCase):
    """Test cases for frontend JavaScript functionality"""
    
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
    
    def test_backtest_page_loads(self):
        """Test that the backtest page loads correctly"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enhanced Backtesting')
        self.assertContains(response, 'Generate Historical Signals')
        self.assertContains(response, 'TradingView Export')
    
    def test_backtest_page_contains_required_elements(self):
        """Test that backtest page contains all required UI elements"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for required form elements
        self.assertContains(response, 'id="symbol-select"')
        self.assertContains(response, 'id="start-date"')
        self.assertContains(response, 'id="end-date"')
        self.assertContains(response, 'id="action-select"')
        self.assertContains(response, 'id="search-name"')
        self.assertContains(response, 'id="notes"')
        
        # Check for buttons
        self.assertContains(response, 'id="run-backtest-btn"')
        self.assertContains(response, 'id="export-csv-btn"')
        self.assertContains(response, 'id="export-json-btn"')
        self.assertContains(response, 'id="export-pinescript-btn"')
        
        # Check for results containers
        self.assertContains(response, 'id="results-container"')
        self.assertContains(response, 'id="signals-container"')
        self.assertContains(response, 'id="export-container"')
    
    def test_backtest_page_contains_javascript(self):
        """Test that backtest page contains required JavaScript"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for JavaScript functions
        self.assertContains(response, 'function runBacktest()')
        self.assertContains(response, 'function exportSignals(format)')
        self.assertContains(response, 'function updateUI()')
        self.assertContains(response, 'function showResults(data)')
        self.assertContains(response, 'function showSignals(signals)')
        self.assertContains(response, 'function showExportOptions()')
    
    def test_backtest_page_contains_css_classes(self):
        """Test that backtest page contains required CSS classes"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for CSS classes
        self.assertContains(response, 'class="form-group"')
        self.assertContains(response, 'class="btn btn-primary"')
        self.assertContains(response, 'class="btn btn-success"')
        self.assertContains(response, 'class="alert alert-info"')
        self.assertContains(response, 'class="table table-striped"')
    
    def test_backtest_page_contains_bootstrap(self):
        """Test that backtest page uses Bootstrap styling"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for Bootstrap classes
        self.assertContains(response, 'container')
        self.assertContains(response, 'row')
        self.assertContains(response, 'col-md-')
        self.assertContains(response, 'form-control')
        self.assertContains(response, 'btn')
    
    def test_backtest_page_contains_chartjs(self):
        """Test that backtest page includes Chart.js for visualization"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for Chart.js
        self.assertContains(response, 'chart.js')
        self.assertContains(response, 'Chart.register')
        self.assertContains(response, 'new Chart(')
    
    def test_backtest_page_contains_date_pickers(self):
        """Test that backtest page has proper date picker functionality"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for date picker attributes
        self.assertContains(response, 'type="date"')
        self.assertContains(response, 'min="2020-01-01"')
        self.assertContains(response, 'max="')
    
    def test_backtest_page_contains_symbol_options(self):
        """Test that backtest page loads symbol options"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create additional symbols
        Symbol.objects.create(symbol='BTC', name='Bitcoin', is_active=True)
        Symbol.objects.create(symbol='ETH', name='Ethereum', is_active=True)
        
        response = self.client.get('/signals/backtest/')
        
        # Check for symbol options
        self.assertContains(response, '<option value="XRP">XRP - Ripple</option>')
        self.assertContains(response, '<option value="BTC">BTC - Bitcoin</option>')
        self.assertContains(response, '<option value="ETH">ETH - Ethereum</option>')
    
    def test_backtest_page_contains_action_options(self):
        """Test that backtest page has correct action options"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for action options
        self.assertContains(response, '<option value="backtest">Traditional Backtest</option>')
        self.assertContains(response, '<option value="generate_signals">Generate Historical Signals</option>')
    
    def test_backtest_page_contains_export_options(self):
        """Test that backtest page has export options"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for export buttons
        self.assertContains(response, 'Export CSV')
        self.assertContains(response, 'Export JSON')
        self.assertContains(response, 'Export Pine Script')
    
    def test_backtest_page_contains_loading_states(self):
        """Test that backtest page has loading states"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for loading states
        self.assertContains(response, 'Loading...')
        self.assertContains(response, 'disabled')
        self.assertContains(response, 'spinner-border')
    
    def test_backtest_page_contains_error_handling(self):
        """Test that backtest page has error handling"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for error handling
        self.assertContains(response, 'alert-danger')
        self.assertContains(response, 'error-message')
        self.assertContains(response, 'try-catch')
    
    def test_backtest_page_contains_success_messages(self):
        """Test that backtest page has success message handling"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for success messages
        self.assertContains(response, 'alert-success')
        self.assertContains(response, 'success-message')
    
    def test_backtest_page_contains_validation(self):
        """Test that backtest page has form validation"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for validation
        self.assertContains(response, 'required')
        self.assertContains(response, 'validateForm')
        self.assertContains(response, 'isValid')
    
    def test_backtest_page_contains_responsive_design(self):
        """Test that backtest page is responsive"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for responsive classes
        self.assertContains(response, 'col-sm-')
        self.assertContains(response, 'col-md-')
        self.assertContains(response, 'col-lg-')
        self.assertContains(response, 'd-md-block')
    
    def test_backtest_page_contains_accessibility(self):
        """Test that backtest page has accessibility features"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for accessibility attributes
        self.assertContains(response, 'aria-label')
        self.assertContains(response, 'aria-describedby')
        self.assertContains(response, 'role=')
    
    def test_backtest_page_contains_meta_tags(self):
        """Test that backtest page has proper meta tags"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for meta tags
        self.assertContains(response, '<meta name="viewport"')
        self.assertContains(response, '<meta name="description"')
    
    def test_backtest_page_contains_favicon(self):
        """Test that backtest page has favicon"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for favicon
        self.assertContains(response, 'favicon')
    
    def test_backtest_page_contains_analytics(self):
        """Test that backtest page has analytics tracking"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for analytics
        self.assertContains(response, 'gtag')
        self.assertContains(response, 'analytics')
    
    def test_backtest_page_contains_security_headers(self):
        """Test that backtest page has security headers"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for security headers
        self.assertIn('X-Frame-Options', response)
        self.assertIn('X-Content-Type-Options', response)
    
    def test_backtest_page_contains_csrf_token(self):
        """Test that backtest page has CSRF token"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for CSRF token
        self.assertContains(response, 'csrfmiddlewaretoken')
    
    def test_backtest_page_contains_progress_indicators(self):
        """Test that backtest page has progress indicators"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for progress indicators
        self.assertContains(response, 'progress')
        self.assertContains(response, 'progress-bar')
    
    def test_backtest_page_contains_tooltips(self):
        """Test that backtest page has tooltips"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for tooltips
        self.assertContains(response, 'data-bs-toggle="tooltip"')
        self.assertContains(response, 'title=')
    
    def test_backtest_page_contains_modals(self):
        """Test that backtest page has modals"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for modals
        self.assertContains(response, 'modal')
        self.assertContains(response, 'modal-dialog')
    
    def test_backtest_page_contains_tabs(self):
        """Test that backtest page has tabs"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for tabs
        self.assertContains(response, 'nav-tabs')
        self.assertContains(response, 'tab-content')
    
    def test_backtest_page_contains_cards(self):
        """Test that backtest page has cards"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for cards
        self.assertContains(response, 'card')
        self.assertContains(response, 'card-body')
    
    def test_backtest_page_contains_badges(self):
        """Test that backtest page has badges"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for badges
        self.assertContains(response, 'badge')
    
    def test_backtest_page_contains_alerts(self):
        """Test that backtest page has alerts"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for alerts
        self.assertContains(response, 'alert')
    
    def test_backtest_page_contains_forms(self):
        """Test that backtest page has proper form structure"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for form elements
        self.assertContains(response, '<form')
        self.assertContains(response, '<input')
        self.assertContains(response, '<select')
        self.assertContains(response, '<textarea')
        self.assertContains(response, '<button')
    
    def test_backtest_page_contains_tables(self):
        """Test that backtest page has tables"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for tables
        self.assertContains(response, '<table')
        self.assertContains(response, '<thead')
        self.assertContains(response, '<tbody')
        self.assertContains(response, '<tr')
        self.assertContains(response, '<th')
        self.assertContains(response, '<td')
    
    def test_backtest_page_contains_lists(self):
        """Test that backtest page has lists"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for lists
        self.assertContains(response, '<ul')
        self.assertContains(response, '<li')
    
    def test_backtest_page_contains_links(self):
        """Test that backtest page has links"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for links
        self.assertContains(response, '<a href')
    
    def test_backtest_page_contains_images(self):
        """Test that backtest page has images"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for images
        self.assertContains(response, '<img')
    
    def test_backtest_page_contains_scripts(self):
        """Test that backtest page has scripts"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for scripts
        self.assertContains(response, '<script')
    
    def test_backtest_page_contains_styles(self):
        """Test that backtest page has styles"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for styles
        self.assertContains(response, '<style')
    
    def test_backtest_page_contains_icons(self):
        """Test that backtest page has icons"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for icons
        self.assertContains(response, 'fa-')
        self.assertContains(response, 'bi-')
    
    def test_backtest_page_contains_animations(self):
        """Test that backtest page has animations"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/signals/backtest/')
        
        # Check for animations
        self.assertContains(response, 'fade')
        self.assertContains(response, 'slide')
        self.assertContains(response, 'animate')


if __name__ == '__main__':
    import unittest
    unittest.main()
































































