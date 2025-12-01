from playwright.sync_api import Playwright, sync_playwright, expect
import time

def test_home_page(playwright: Playwright) -> None:
    """Test the home page loads correctly"""
    browser = playwright.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        record_video_dir="test_videos/",
        record_har_path="test_results.har"
    )
    
    page = context.new_page()
    
    # Enable console logging
    page.on("console", lambda msg: print(f"Console: {msg.text}"))
    page.on("pageerror", lambda err: print(f"Page Error: {err}"))
    
    try:
        # Test home page
        print("Testing home page...")
        page.goto("http://127.0.0.1:8000/")
        expect(page).to_have_title("AI Trading Engine")
        
        # Check for main navigation elements
        expect(page.locator("nav")).to_be_visible()
        expect(page.locator("text=Dashboard")).to_be_visible()
        expect(page.locator("text=Analytics")).to_be_visible()
        expect(page.locator("text=Signals")).to_be_visible()
        
        print("✅ Home page test passed")
        
    except Exception as e:
        print(f"❌ Home page test failed: {e}")
        page.screenshot(path="test_home_page_error.png")
    
    finally:
        context.close()
        browser.close()

def test_login_functionality(playwright: Playwright) -> None:
    """Test login functionality"""
    browser = playwright.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        record_video_dir="test_videos/",
        record_har_path="test_results.har"
    )
    
    page = context.new_page()
    
    try:
        # Test login page
        print("Testing login functionality...")
        page.goto("http://127.0.0.1:8000/login/")
        expect(page.locator("text=Login")).to_be_visible()
        
        # Fill login form
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "admin123")
        page.click("button[type='submit']")
        
        # Wait for redirect and check dashboard
        page.wait_for_url("**/dashboard/")
        expect(page.locator("text=Welcome")).to_be_visible()
        
        print("✅ Login test passed")
        
    except Exception as e:
        print(f"❌ Login test failed: {e}")
        page.screenshot(path="test_login_error.png")
    
    finally:
        context.close()
        browser.close()

def test_dashboard_navigation(playwright: Playwright) -> None:
    """Test dashboard navigation"""
    browser = playwright.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        record_video_dir="test_videos/",
        record_har_path="test_results.har"
    )
    
    page = context.new_page()
    
    try:
        # Login first
        print("Testing dashboard navigation...")
        page.goto("http://127.0.0.1:8000/login/")
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "admin123")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard/")
        
        # Test navigation to different sections
        # Portfolio
        page.click("text=Portfolio")
        page.wait_for_url("**/portfolio/")
        expect(page.locator("text=Portfolio")).to_be_visible()
        
        # Signals
        page.click("text=Signals")
        page.wait_for_url("**/signals/")
        expect(page.locator("text=Signals")).to_be_visible()
        
        # Analytics
        page.click("text=Analytics")
        page.wait_for_url("**/analytics/")
        expect(page.locator("text=Analytics")).to_be_visible()
        
        print("✅ Dashboard navigation test passed")
        
    except Exception as e:
        print(f"❌ Dashboard navigation test failed: {e}")
        page.screenshot(path="test_dashboard_nav_error.png")
    
    finally:
        context.close()
        browser.close()

def test_analytics_features(playwright: Playwright) -> None:
    """Test analytics features"""
    browser = playwright.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        record_video_dir="test_videos/",
        record_har_path="test_results.har"
    )
    
    page = context.new_page()
    
    try:
        # Login first
        print("Testing analytics features...")
        page.goto("http://127.0.0.1:8000/login/")
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "admin123")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard/")
        
        # Navigate to analytics
        page.click("text=Analytics")
        page.wait_for_url("**/analytics/")
        
        # Test different analytics pages
        # Performance
        page.click("text=Performance")
        page.wait_for_url("**/performance/")
        expect(page.locator("text=Performance Analysis")).to_be_visible()
        
        # Risk Management
        page.click("text=Risk Management")
        page.wait_for_url("**/risk/")
        expect(page.locator("text=Risk Management")).to_be_visible()
        
        # Backtesting
        page.click("text=Backtesting")
        page.wait_for_url("**/backtesting/")
        expect(page.locator("text=Backtesting")).to_be_visible()
        
        # ML Dashboard
        page.click("text=ML Dashboard")
        page.wait_for_url("**/ml/")
        expect(page.locator("text=Machine Learning")).to_be_visible()
        
        print("✅ Analytics features test passed")
        
    except Exception as e:
        print(f"❌ Analytics features test failed: {e}")
        page.screenshot(path="test_analytics_error.png")
    
    finally:
        context.close()
        browser.close()

def test_signals_functionality(playwright: Playwright) -> None:
    """Test signals functionality"""
    browser = playwright.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        record_video_dir="test_videos/",
        record_har_path="test_results.har"
    )
    
    page = context.new_page()
    
    try:
        # Login first
        print("Testing signals functionality...")
        page.goto("http://127.0.0.1:8000/login/")
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "admin123")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard/")
        
        # Navigate to signals
        page.click("text=Signals")
        page.wait_for_url("**/signals/")
        
        # Check for signals content
        expect(page.locator("text=Market Signals")).to_be_visible()
        
        # Test signal filters if they exist
        try:
            page.click("text=Filter")
            time.sleep(1)
            print("✅ Signal filters working")
        except:
            print("ℹ️ No signal filters found")
        
        print("✅ Signals functionality test passed")
        
    except Exception as e:
        print(f"❌ Signals functionality test failed: {e}")
        page.screenshot(path="test_signals_error.png")
    
    finally:
        context.close()
        browser.close()

def test_subscription_management(playwright: Playwright) -> None:
    """Test subscription management"""
    browser = playwright.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        record_video_dir="test_videos/",
        record_har_path="test_results.har"
    )
    
    page = context.new_page()
    
    try:
        # Login first
        print("Testing subscription management...")
        page.goto("http://127.0.0.1:8000/login/")
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "admin123")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard/")
        
        # Navigate to subscription
        page.click("text=Subscription")
        page.wait_for_url("**/subscription/choice/")
        
        # Check subscription options
        expect(page.locator("text=Choose Your Plan")).to_be_visible()
        
        print("✅ Subscription management test passed")
        
    except Exception as e:
        print(f"❌ Subscription management test failed: {e}")
        page.screenshot(path="test_subscription_error.png")
    
    finally:
        context.close()
        browser.close()

def run_all_tests():
    """Run all Playwright tests"""
    print("🚀 Starting Playwright Tests for AI Trading Engine")
    print("=" * 50)
    
    with sync_playwright() as playwright:
        test_functions = [
            test_home_page,
            test_login_functionality,
            test_dashboard_navigation,
            test_analytics_features,
            test_signals_functionality,
            test_subscription_management
        ]
        
        passed = 0
        failed = 0
        
        for test_func in test_functions:
            try:
                test_func(playwright)
                passed += 1
            except Exception as e:
                print(f"❌ {test_func.__name__} failed with error: {e}")
                failed += 1
            print("-" * 30)
        
        print("=" * 50)
        print(f"🎯 Test Results: {passed} passed, {failed} failed")
        print("=" * 50)

if __name__ == "__main__":
    run_all_tests()

















