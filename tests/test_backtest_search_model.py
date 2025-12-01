"""
Unit tests for BacktestSearch model
Tests the new BacktestSearch model functionality added in Phase 1
"""

import os
import sys
import django
from datetime import datetime, date, timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.signals.models import BacktestSearch
from apps.trading.models import Symbol


class BacktestSearchModelTest(TestCase):
    """Test cases for BacktestSearch model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.symbol = Symbol.objects.create(
            symbol='XRP',
            name='Ripple',
            is_active=True
        )
        
        self.start_date = date(2025, 1, 1)
        self.end_date = date(2025, 8, 31)
    
    def test_create_backtest_search(self):
        """Test creating a basic BacktestSearch instance"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date,
            signals_generated=25,
            search_name='XRP Jan-Aug 2025',
            notes='Testing XRP signals for 8 months'
        )
        
        self.assertEqual(search.user, self.user)
        self.assertEqual(search.symbol, self.symbol)
        self.assertEqual(search.start_date, self.start_date)
        self.assertEqual(search.end_date, self.end_date)
        self.assertEqual(search.signals_generated, 25)
        self.assertEqual(search.search_name, 'XRP Jan-Aug 2025')
        self.assertEqual(search.notes, 'Testing XRP signals for 8 months')
        self.assertIsNotNone(search.created_at)
        self.assertIsNotNone(search.last_accessed)
    
    def test_duration_days_property(self):
        """Test the duration_days property calculation"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        expected_days = (self.end_date - self.start_date).days
        self.assertEqual(search.duration_days, expected_days)
        self.assertEqual(search.duration_days, 242)  # Jan 1 to Aug 31, 2025
    
    def test_search_summary_property(self):
        """Test the search_summary property"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date,
            signals_generated=15
        )
        
        expected_summary = f"{self.symbol.symbol} from {self.start_date} to {self.end_date} (15 signals)"
        self.assertEqual(search.search_summary, expected_summary)
    
    def test_str_representation(self):
        """Test the string representation of BacktestSearch"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        expected_str = f"{self.user.username} - {self.symbol.symbol} ({self.start_date} to {self.end_date})"
        self.assertEqual(str(search), expected_str)
    
    def test_unique_together_constraint(self):
        """Test that unique_together constraint works correctly"""
        # Create first search
        BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        # Try to create duplicate search - should raise IntegrityError
        with self.assertRaises(IntegrityError):
            BacktestSearch.objects.create(
                user=self.user,
                symbol=self.symbol,
                start_date=self.start_date,
                end_date=self.end_date
            )
    
    def test_different_users_can_have_same_search(self):
        """Test that different users can have the same search parameters"""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create search for first user
        search1 = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        # Create same search for second user - should work
        search2 = BacktestSearch.objects.create(
            user=user2,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        self.assertNotEqual(search1.id, search2.id)
        self.assertEqual(search1.user, self.user)
        self.assertEqual(search2.user, user2)
    
    def test_different_symbols_same_user(self):
        """Test that same user can have searches for different symbols"""
        symbol2 = Symbol.objects.create(
            symbol='BTC',
            name='Bitcoin',
            is_active=True
        )
        
        # Create search for XRP
        search1 = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        # Create search for BTC - should work
        search2 = BacktestSearch.objects.create(
            user=self.user,
            symbol=symbol2,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        self.assertNotEqual(search1.id, search2.id)
        self.assertEqual(search1.symbol, self.symbol)
        self.assertEqual(search2.symbol, symbol2)
    
    def test_different_date_ranges_same_user_symbol(self):
        """Test that same user can have different date ranges for same symbol"""
        end_date2 = date(2025, 12, 31)
        
        # Create search for Jan-Aug
        search1 = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        # Create search for Jan-Dec - should work
        search2 = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=end_date2
        )
        
        self.assertNotEqual(search1.id, search2.id)
        self.assertEqual(search1.end_date, self.end_date)
        self.assertEqual(search2.end_date, end_date2)
    
    def test_default_values(self):
        """Test default values for optional fields"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        self.assertEqual(search.signals_generated, 0)
        self.assertEqual(search.search_name, '')
        self.assertEqual(search.notes, '')
    
    def test_ordering(self):
        """Test that searches are ordered by last_accessed descending"""
        # Create searches with different last_accessed times
        search1 = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        # Update last_accessed to be earlier
        search1.last_accessed = datetime.now() - timedelta(days=1)
        search1.save()
        
        # Create search with different date range to avoid unique constraint
        search2 = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date + timedelta(days=1)  # Different end date
        )
        
        # Get all searches ordered by last_accessed
        searches = BacktestSearch.objects.all()
        
        # search2 should come first (more recent last_accessed)
        self.assertEqual(searches[0], search2)
        self.assertEqual(searches[1], search1)
    
    def test_verbose_names(self):
        """Test verbose names in Meta class"""
        self.assertEqual(BacktestSearch._meta.verbose_name, 'Backtest Search')
        self.assertEqual(BacktestSearch._meta.verbose_name_plural, 'Backtest Searches')
    
    def test_foreign_key_relationships(self):
        """Test foreign key relationships work correctly"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        # Test user relationship
        self.assertEqual(search.user.backtest_searches.count(), 1)
        self.assertEqual(search.user.backtest_searches.first(), search)
        
        # Test symbol relationship
        self.assertEqual(search.symbol.backtest_searches.count(), 1)
        self.assertEqual(search.symbol.backtest_searches.first(), search)
    
    def test_cascade_delete_user(self):
        """Test that searches are deleted when user is deleted"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        search_id = search.id
        
        # Delete user
        self.user.delete()
        
        # Search should be deleted too
        with self.assertRaises(BacktestSearch.DoesNotExist):
            BacktestSearch.objects.get(id=search_id)
    
    def test_cascade_delete_symbol(self):
        """Test that searches are deleted when symbol is deleted"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        search_id = search.id
        
        # Delete symbol
        self.symbol.delete()
        
        # Search should be deleted too
        with self.assertRaises(BacktestSearch.DoesNotExist):
            BacktestSearch.objects.get(id=search_id)
    
    def test_edge_case_dates(self):
        """Test edge cases for date handling"""
        # Same start and end date
        same_date = date(2025, 1, 1)
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=same_date,
            end_date=same_date
        )
        
        self.assertEqual(search.duration_days, 0)
        
        # Leap year test
        leap_start = date(2024, 1, 1)
        leap_end = date(2024, 12, 31)
        leap_search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=leap_start,
            end_date=leap_end
        )
        
        self.assertEqual(leap_search.duration_days, 365)  # 2024 is a leap year
    
    def test_large_signals_generated(self):
        """Test handling of large numbers for signals_generated"""
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date,
            signals_generated=999999
        )
        
        self.assertEqual(search.signals_generated, 999999)
    
    def test_long_search_name_and_notes(self):
        """Test handling of long search names and notes"""
        long_name = 'A' * 100  # Max length is 100
        long_notes = 'B' * 1000  # TextField can handle long text
        
        search = BacktestSearch.objects.create(
            user=self.user,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date,
            search_name=long_name,
            notes=long_notes
        )
        
        self.assertEqual(search.search_name, long_name)
        self.assertEqual(search.notes, long_notes)


if __name__ == '__main__':
    import unittest
    unittest.main()
