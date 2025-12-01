"""
Comprehensive Test Suite Runner for Phase 4
Runs all tests for the enhanced backtesting functionality
"""

import os
import sys
import django
import unittest
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.test import TestCase
from django.core.management import call_command
from django.db import connection


class ComprehensiveTestSuite:
    """Comprehensive test suite for Phase 4 testing and optimization"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now()
    
    def run_all_tests(self):
        """Run all test suites"""
        print("=" * 80)
        print("PHASE 4: COMPREHENSIVE TEST SUITE")
        print("=" * 80)
        print(f"Started at: {self.start_time}")
        print()
        
        # Test suites to run
        test_suites = [
            ('BacktestSearch Model Tests', self.run_backtest_search_tests),
            ('HistoricalSignalService Tests', self.run_historical_signal_service_tests),
            ('BacktestAPI Integration Tests', self.run_backtest_api_tests),
            ('TradingViewExport Integration Tests', self.run_tradingview_export_tests),
            ('Frontend JavaScript Tests', self.run_frontend_javascript_tests),
            ('Database Tests', self.run_database_tests),
            ('Performance Tests', self.run_performance_tests),
            ('Security Tests', self.run_security_tests),
            ('API Endpoint Tests', self.run_api_endpoint_tests),
            ('Model Validation Tests', self.run_model_validation_tests)
        ]
        
        total_tests = 0
        total_failures = 0
        total_errors = 0
        
        for suite_name, test_function in test_suites:
            print(f"Running {suite_name}...")
            print("-" * 60)
            
            try:
                result = test_function()
                self.test_results[suite_name] = result
                
                total_tests += result.get('tests_run', 0)
                total_failures += result.get('failures', 0)
                total_errors += result.get('errors', 0)
                
                if result.get('success', False):
                    print(f"✅ {suite_name}: PASSED")
                else:
                    print(f"❌ {suite_name}: FAILED")
                    if result.get('failures', 0) > 0:
                        print(f"   Failures: {result['failures']}")
                    if result.get('errors', 0) > 0:
                        print(f"   Errors: {result['errors']}")
                
            except Exception as e:
                print(f"❌ {suite_name}: ERROR - {str(e)}")
                self.test_results[suite_name] = {'success': False, 'error': str(e)}
                total_errors += 1
            
            print()
        
        # Summary
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        print("=" * 80)
        print("TEST SUITE SUMMARY")
        print("=" * 80)
        print(f"Total Tests Run: {total_tests}")
        print(f"Total Failures: {total_failures}")
        print(f"Total Errors: {total_errors}")
        print(f"Success Rate: {((total_tests - total_failures - total_errors) / total_tests * 100):.1f}%" if total_tests > 0 else "N/A")
        print(f"Duration: {duration}")
        print()
        
        if total_failures == 0 and total_errors == 0:
            print("🎉 ALL TESTS PASSED! Phase 4 testing completed successfully.")
        else:
            print("⚠️  Some tests failed. Please review the results above.")
        
        return {
            'total_tests': total_tests,
            'total_failures': total_failures,
            'total_errors': total_errors,
            'duration': duration,
            'success': total_failures == 0 and total_errors == 0
        }
    
    def run_backtest_search_tests(self):
        """Run BacktestSearch model tests"""
        from tests.test_backtest_search_model import BacktestSearchModelTest
        
        suite = unittest.TestLoader().loadTestsFromTestCase(BacktestSearchModelTest)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        return {
            'success': result.wasSuccessful(),
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors)
        }
    
    def run_historical_signal_service_tests(self):
        """Run HistoricalSignalService tests"""
        from tests.test_historical_signal_service import HistoricalSignalServiceTest
        
        suite = unittest.TestLoader().loadTestsFromTestCase(HistoricalSignalServiceTest)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        return {
            'success': result.wasSuccessful(),
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors)
        }
    
    def run_backtest_api_tests(self):
        """Run BacktestAPI integration tests"""
        from tests.test_backtest_api_integration import BacktestAPIViewIntegrationTest
        
        suite = unittest.TestLoader().loadTestsFromTestCase(BacktestAPIViewIntegrationTest)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        return {
            'success': result.wasSuccessful(),
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors)
        }
    
    def run_tradingview_export_tests(self):
        """Run TradingViewExport integration tests"""
        from tests.test_tradingview_export_integration import TradingViewExportAPIViewIntegrationTest
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TradingViewExportAPIViewIntegrationTest)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        return {
            'success': result.wasSuccessful(),
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors)
        }
    
    def run_frontend_javascript_tests(self):
        """Run frontend JavaScript tests"""
        from tests.test_frontend_javascript import FrontendJavaScriptTest
        
        suite = unittest.TestLoader().loadTestsFromTestCase(FrontendJavaScriptTest)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        return {
            'success': result.wasSuccessful(),
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors)
        }
    
    def run_database_tests(self):
        """Run database-specific tests"""
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            if result[0] == 1:
                return {'success': True, 'tests_run': 1, 'failures': 0, 'errors': 0}
            else:
                return {'success': False, 'tests_run': 1, 'failures': 1, 'errors': 0}
                
        except Exception as e:
            return {'success': False, 'tests_run': 1, 'failures': 0, 'errors': 1, 'error': str(e)}
    
    def run_performance_tests(self):
        """Run performance tests"""
        import time
        
        try:
            # Test API response time
            start_time = time.time()
            
            # Simulate API call
            from django.test import Client
            client = Client()
            
            # Test basic page load
            response = client.get('/')
            load_time = time.time() - start_time
            
            if response.status_code == 200 and load_time < 2.0:  # Should load in under 2 seconds
                return {'success': True, 'tests_run': 1, 'failures': 0, 'errors': 0}
            else:
                return {'success': False, 'tests_run': 1, 'failures': 1, 'errors': 0}
                
        except Exception as e:
            return {'success': False, 'tests_run': 1, 'failures': 0, 'errors': 1, 'error': str(e)}
    
    def run_security_tests(self):
        """Run security tests"""
        try:
            # Test CSRF protection
            from django.test import Client
            client = Client()
            
            # Test that POST requests without CSRF token are rejected
            response = client.post('/signals/api/backtest/', {})
            
            if response.status_code in [403, 302]:  # CSRF protection working
                return {'success': True, 'tests_run': 1, 'failures': 0, 'errors': 0}
            else:
                return {'success': False, 'tests_run': 1, 'failures': 1, 'errors': 0}
                
        except Exception as e:
            return {'success': False, 'tests_run': 1, 'failures': 0, 'errors': 1, 'error': str(e)}
    
    def run_api_endpoint_tests(self):
        """Run API endpoint tests"""
        try:
            from django.test import Client
            client = Client()
            
            # Test that API endpoints exist and return proper status codes
            endpoints = [
                ('/signals/api/backtest/', 302),  # Should redirect to login
                ('/signals/api/tradingview-export/', 302),  # Should redirect to login
                ('/signals/api/search-history/', 302),  # Should redirect to login
            ]
            
            tests_passed = 0
            total_tests = len(endpoints)
            
            for endpoint, expected_status in endpoints:
                response = client.get(endpoint)
                if response.status_code == expected_status:
                    tests_passed += 1
            
            success_rate = tests_passed / total_tests
            
            return {
                'success': success_rate >= 0.8,  # 80% pass rate
                'tests_run': total_tests,
                'failures': total_tests - tests_passed,
                'errors': 0
            }
            
        except Exception as e:
            return {'success': False, 'tests_run': 1, 'failures': 0, 'errors': 1, 'error': str(e)}
    
    def run_model_validation_tests(self):
        """Run model validation tests"""
        try:
            from apps.signals.models import BacktestSearch
            from apps.trading.models import Symbol
            from django.contrib.auth.models import User
            
            # Test model creation and validation
            user = User.objects.create_user(username='testuser', password='testpass')
            symbol = Symbol.objects.create(symbol='TEST', name='Test', is_active=True)
            
            # Test BacktestSearch model
            search = BacktestSearch.objects.create(
                user=user,
                symbol=symbol,
                start_date='2025-01-01',
                end_date='2025-12-31'
            )
            
            # Test model methods
            duration = search.duration_days
            summary = search.search_summary
            str_repr = str(search)
            
            if duration > 0 and summary and str_repr:
                return {'success': True, 'tests_run': 1, 'failures': 0, 'errors': 0}
            else:
                return {'success': False, 'tests_run': 1, 'failures': 1, 'errors': 0}
                
        except Exception as e:
            return {'success': False, 'tests_run': 1, 'failures': 0, 'errors': 1, 'error': str(e)}


def run_phase4_tests():
    """Main function to run Phase 4 tests"""
    test_suite = ComprehensiveTestSuite()
    return test_suite.run_all_tests()


if __name__ == '__main__':
    result = run_phase4_tests()
    
    if result['success']:
        print("\n🎉 Phase 4 Testing Complete - All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Phase 4 Testing Complete - Some tests failed.")
        sys.exit(1)
































































