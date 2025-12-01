#!/usr/bin/env python3
"""
Simple test runner for AI Trading Engine Playwright tests
"""

import asyncio
import sys
import os
from test_ai_trading_engine import TestAITradingEngine

def print_banner():
    """Print test suite banner"""
    print("=" * 70)
    print("🚀 AI TRADING ENGINE - PLAYWRIGHT TEST SUITE")
    print("=" * 70)
    print("Testing all major functionality:")
    print("  ✅ Home page and navigation")
    print("  ✅ Authentication (login/logout)")
    print("  ✅ Dashboard functionality")
    print("  ✅ Portfolio management")
    print("  ✅ Trading signals")
    print("  ✅ Analytics and reporting")
    print("  ✅ Subscription management")
    print("  ✅ User settings")
    print("  ✅ Theme switching (light/dark)")
    print("  ✅ Responsive design")
    print("  ✅ Error handling")
    print("=" * 70)

async def main():
    """Main test runner"""
    print_banner()
    
    # Check if Django server is running
    print("🔍 Checking if Django server is running...")
    try:
        import requests
        response = requests.get("http://127.0.0.1:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ Django server is running on http://127.0.0.1:8000/")
        else:
            print("⚠️ Django server responded with status:", response.status_code)
    except Exception as e:
        print("❌ Django server is not running or not accessible")
        print("   Please start the server with: python manage.py runserver")
        print("   Error:", str(e))
        return
    
    # Create test instance
    test_suite = TestAITradingEngine()
    
    # Run tests
    try:
        await test_suite.run_all_tests()
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
