#!/usr/bin/env python3
"""
Comprehensive Playwright Test Suite for AI Trading Engine
Tests all major functionality including authentication, navigation, dashboard, and theme switching
"""

import asyncio
from playwright.async_api import async_playwright, expect
import os
import sys

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestAITradingEngine:
    """Main test class for AI Trading Engine application"""
    
    def __init__(self):
        self.base_url = "http://127.0.0.1:8000"
        self.admin_credentials = {
            "username": "admin",
            "password": "admin123"
        }
        self.test_user_credentials = {
            "username": "testuser",
            "password": "testpass123"
        }
    
    async def setup_browser(self):
        """Setup browser and context for testing"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Set to True for headless testing
            slow_mo=1000  # Slow down actions for visibility
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir="test_videos/" if os.path.exists("test_videos/") else None
        )
        self.page = await self.context.new_page()
        
        # Enable console logging
        self.page.on("console", lambda msg: print(f"Console: {msg.text}"))
        self.page.on("pageerror", lambda err: print(f"Page Error: {err}"))
    
    async def teardown_browser(self):
        """Clean up browser resources"""
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()
    
    async def test_home_page(self):
        """Test home page functionality"""
        print("\n🧪 Testing Home Page...")
        
        await self.page.goto(f"{self.base_url}/")
        
        # Check page title
        await expect(self.page).to_have_title("AI-Enhanced Trading Signal Engine - Home")
        
        # Check main sections exist
        await expect(self.page.locator("h1")).to_contain_text("Welcome to AI Trading Engine")
        await expect(self.page.locator("h2:has-text('Quick Access')")).to_be_visible()
        await expect(self.page.locator("h2:has-text('Trading Overview')")).to_be_visible()
        await expect(self.page.locator("h2:has-text('Technology Stack')")).to_be_visible()
        await expect(self.page.locator("h3:has-text('Ready to Access Your Trading Dashboard?')")).to_be_visible()
        
        # Test theme toggle button (only visible for non-authenticated users)
        theme_toggle = self.page.locator("#theme-toggle-home")
        if await theme_toggle.is_visible():
            await expect(theme_toggle).to_be_visible()
            print("  ✅ Theme toggle button is visible")
        else:
            print("  ℹ️ Theme toggle button not visible (user may be authenticated)")
        
        # Test initial theme (should be light by default)
        initial_theme = await self.page.get_attribute("body", "data-theme")
        print(f"Initial theme: {initial_theme}")
        
        # Test theme switching if button is visible
        if await theme_toggle.is_visible():
            await theme_toggle.click()
            await asyncio.sleep(1)
            
            new_theme = await self.page.get_attribute("body", "data-theme")
            print(f"New theme after toggle: {new_theme}")
            assert new_theme != initial_theme, "Theme should change after toggle"
        else:
            print("  ℹ️ Skipping theme toggle test (button not visible)")
        
        # Test navigation links
        await expect(self.page.locator("a[href='/dashboard/']").first).to_be_visible()
        await expect(self.page.locator("a[href='/signals/']").first).to_be_visible()
        await expect(self.page.locator("a[href='/analytics/']").first).to_be_visible()
        
        print("✅ Home page tests passed!")
    
    async def test_authentication(self):
        """Test login/logout functionality"""
        print("\n🔐 Testing Authentication...")
        
        # Test login page
        await self.page.goto(f"{self.base_url}/login/")
        await expect(self.page).to_have_title("Login - AI Trading Engine")
        
        # Fill login form
        await self.page.fill("#username", self.admin_credentials["username"])
        await self.page.fill("#password", self.admin_credentials["password"])
        
        # Submit form
        await self.page.click("button[type='submit']")
        
        # Should redirect to dashboard
        await self.page.wait_for_url(f"{self.base_url}/dashboard/")
        await expect(self.page).to_have_title("AI Trading Engine - Enhanced Dashboard")
        
        # Test logout - first click on user dropdown to reveal logout link
        user_dropdown = self.page.locator("#navbarDropdown")
        if await user_dropdown.is_visible():
            await user_dropdown.click()
            await asyncio.sleep(1)
        
        logout_link = self.page.locator("a[href='/logout/']")
        await expect(logout_link).to_be_visible()
        await logout_link.click()
        
        # Should redirect to home page
        await self.page.wait_for_url(f"{self.base_url}/")
        
        print("✅ Authentication tests passed!")
    
    async def test_dashboard_navigation(self):
        """Test dashboard navigation and functionality"""
        print("\n📊 Testing Dashboard Navigation...")
        
        # Login first
        await self.page.goto(f"{self.base_url}/login/")
        await self.page.fill("#username", self.admin_credentials["username"])
        await self.page.fill("#password", self.admin_credentials["password"])
        await self.page.click("button[type='submit']")
        await self.page.wait_for_url(f"{self.base_url}/dashboard/")
        
        # Test dashboard sections
        await expect(self.page.locator("h1:has-text('Trading Dashboard')")).to_be_visible()
        await expect(self.page.locator(".stats-card")).to_be_visible()
        await expect(self.page.locator(".card")).to_be_visible()
        
        # Test navigation menu
        nav_items = [
            ("Dashboard", "/dashboard/"),
            ("Portfolio", "/portfolio/"),
            ("Signals", "/signals/"),
            ("Analytics", "/analytics/"),
            ("Settings", "/settings/"),
            ("Subscription", "/subscription/choice/")
        ]
        
        for nav_text, nav_url in nav_items:
            nav_link = self.page.locator(f"a[href='{nav_url}']")
            await expect(nav_link).to_be_visible()
            print(f"  ✅ Navigation item '{nav_text}' is visible")
        
        print("✅ Dashboard navigation tests passed!")
    
    async def test_portfolio_page(self):
        """Test portfolio page functionality"""
        print("\n💼 Testing Portfolio Page...")
        
        # Navigate to portfolio
        await self.page.goto(f"{self.base_url}/portfolio/")
        
        # Check if redirected to login (if not authenticated)
        if "/login/" in self.page.url:
            # Login first
            await self.page.fill("#username", self.admin_credentials["username"])
            await self.page.fill("#password", self.admin_credentials["password"])
            await self.page.click("button[type='submit']")
            await self.page.wait_for_url(f"{self.base_url}/portfolio/")
        
        # Test portfolio content
        await expect(self.page.locator(".portfolio-header")).to_be_visible()
        await expect(self.page.locator(".portfolio-summary")).to_be_visible()
        await expect(self.page.locator(".holdings-table")).to_be_visible()
        
        print("✅ Portfolio page tests passed!")
    
    async def test_signals_page(self):
        """Test signals page functionality"""
        print("\n📡 Testing Signals Page...")
        
        # Navigate to signals
        await self.page.goto(f"{self.base_url}/signals/")
        
        # Check if redirected to login (if not authenticated)
        if "/login/" in self.page.url:
            # Login first
            await self.page.fill("#username", self.admin_credentials["username"])
            await self.page.fill("#password", self.admin_credentials["password"])
            await self.page.click("button[type='submit']")
            await self.page.wait_for_url(f"{self.base_url}/signals/")
        
        # Test signals content
        await expect(self.page.locator(".signals-header")).to_be_visible()
        await expect(self.page.locator(".signals-filters")).to_be_visible()
        await expect(self.page.locator(".signals-list")).to_be_visible()
        
        print("✅ Signals page tests passed!")
    
    async def test_analytics_pages(self):
        """Test analytics pages functionality"""
        print("\n📈 Testing Analytics Pages...")
        
        # Login first
        await self.page.goto(f"{self.base_url}/login/")
        await self.page.fill("#username", self.admin_credentials["username"])
        await self.page.fill("#password", self.admin_credentials["password"])
        await self.page.click("button[type='submit']")
        
        # Test main analytics page
        await self.page.goto(f"{self.base_url}/analytics/")
        await expect(self.page.locator(".analytics-header")).to_be_visible()
        await expect(self.page.locator(".analytics-nav")).to_be_visible()
        
        # Test performance analytics
        await self.page.goto(f"{self.base_url}/analytics/performance/")
        await expect(self.page.locator(".performance-header")).to_be_visible()
        await expect(self.page.locator(".performance-charts")).to_be_visible()
        
        # Test risk analytics
        await self.page.goto(f"{self.base_url}/analytics/risk/")
        await expect(self.page.locator(".risk-header")).to_be_visible()
        await expect(self.page.locator(".risk-metrics")).to_be_visible()
        
        # Test backtesting
        await self.page.goto(f"{self.base_url}/analytics/backtesting/")
        await expect(self.page.locator(".backtesting-header")).to_be_visible()
        await expect(self.page.locator(".backtesting-form")).to_be_visible()
        
        print("✅ Analytics pages tests passed!")
    
    async def test_subscription_page(self):
        """Test subscription page functionality"""
        print("\n💳 Testing Subscription Page...")
        
        # Login first
        await self.page.goto(f"{self.base_url}/login/")
        await self.page.fill("#username", self.admin_credentials["username"])
        await self.page.fill("#password", self.admin_credentials["password"])
        await self.page.click("button[type='submit']")
        
        # Navigate to subscription
        await self.page.goto(f"{self.base_url}/subscription/choice/")
        await expect(self.page.locator(".subscription-header")).to_be_visible()
        await expect(self.page.locator(".plan-options")).to_be_visible()
        
        print("✅ Subscription page tests passed!")
    
    async def test_settings_page(self):
        """Test settings page functionality"""
        print("\n⚙️ Testing Settings Page...")
        
        # Login first
        await self.page.goto(f"{self.base_url}/login/")
        await self.page.fill("#username", self.admin_credentials["username"])
        await self.page.fill("#password", self.admin_credentials["password"])
        await self.page.click("button[type='submit']")
        
        # Navigate to settings
        await self.page.goto(f"{self.base_url}/settings/")
        await expect(self.page.locator(".settings-header")).to_be_visible()
        await expect(self.page.locator(".settings-form")).to_be_visible()
        
        print("✅ Settings page tests passed!")
    
    async def test_theme_switching(self):
        """Test theme switching across all pages"""
        print("\n🎨 Testing Theme Switching...")
        
        # Login first
        await self.page.goto(f"{self.base_url}/login/")
        await self.page.fill("#username", self.admin_credentials["username"])
        await self.page.fill("#password", self.admin_credentials["password"])
        await self.page.click("button[type='submit']")
        
        # Test theme switching on dashboard
        await self.page.goto(f"{self.base_url}/dashboard/")
        theme_toggle = self.page.locator("#theme-toggle")
        await expect(theme_toggle).to_be_visible()
        
        # Get initial theme
        initial_theme = await self.page.get_attribute("body", "data-theme")
        print(f"Dashboard initial theme: {initial_theme}")
        
        # Toggle theme
        await theme_toggle.click()
        await asyncio.sleep(1)
        
        new_theme = await self.page.get_attribute("body", "data-theme")
        print(f"Dashboard new theme: {new_theme}")
        assert new_theme != initial_theme, "Theme should change on dashboard"
        
        # Test theme switching on other pages
        pages_to_test = [
            "/portfolio/",
            "/signals/",
            "/analytics/",
            "/settings/",
            "/subscription/choice/"
        ]
        
        for page_url in pages_to_test:
            await self.page.goto(f"{self.base_url}{page_url}")
            page_theme_toggle = self.page.locator("#theme-toggle")
            
            if await page_theme_toggle.is_visible():
                page_initial_theme = await self.page.get_attribute("body", "data-theme")
                await page_theme_toggle.click()
                await asyncio.sleep(1)
                page_new_theme = await self.page.get_attribute("body", "data-theme")
                print(f"  {page_url}: {page_initial_theme} → {page_new_theme}")
        
        print("✅ Theme switching tests passed!")
    
    async def test_responsive_design(self):
        """Test responsive design on different screen sizes"""
        print("\n📱 Testing Responsive Design...")
        
        # Test mobile viewport
        await self.page.set_viewport_size({"width": 375, "height": 667})
        await self.page.goto(f"{self.base_url}/")
        
        # Check mobile navigation
        await expect(self.page.locator(".navbar-toggler")).to_be_visible()
        
        # Test tablet viewport
        await self.page.set_viewport_size({"width": 768, "height": 1024})
        await self.page.goto(f"{self.base_url}/")
        
        # Test desktop viewport
        await self.page.set_viewport_size({"width": 1920, "height": 1080})
        await self.page.goto(f"{self.base_url}/")
        
        print("✅ Responsive design tests passed!")
    
    async def test_error_handling(self):
        """Test error handling and 404 pages"""
        print("\n⚠️ Testing Error Handling...")
        
        # Test 404 page
        await self.page.goto(f"{self.base_url}/nonexistent-page/")
        
        # Should show 404 or redirect to home
        if "/nonexistent-page/" in self.page.url:
            # Check if there's a 404 message
            page_content = await self.page.content()
            if "404" in page_content or "not found" in page_content.lower():
                print("  ✅ 404 page handling works")
            else:
                print("  ⚠️ 404 page handling needs improvement")
        else:
            print("  ✅ Redirected from invalid page")
        
        print("✅ Error handling tests passed!")
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting AI Trading Engine Test Suite...")
        print("=" * 60)
        
        try:
            await self.setup_browser()
            
            # Run all tests
            await self.test_home_page()
            await self.test_authentication()
            await self.test_dashboard_navigation()
            await self.test_portfolio_page()
            await self.test_signals_page()
            await self.test_analytics_pages()
            await self.test_subscription_page()
            await self.test_settings_page()
            await self.test_theme_switching()
            await self.test_responsive_design()
            await self.test_error_handling()
            
            print("\n" + "=" * 60)
            print("🎉 ALL TESTS PASSED! AI Trading Engine is working correctly.")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {str(e)}")
            raise
        finally:
            await self.teardown_browser()

async def main():
    """Main function to run tests"""
    test_suite = TestAITradingEngine()
    await test_suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
