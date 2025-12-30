from playwright.sync_api import sync_playwright
import os

def capture_honeywell_screenshot():
    """Simple test that just tries to get SOME screenshot of Honeywell, no matter what"""
    url = "https://www.honeywell.com/us/en/company/sustainability"
    
    print(f"Attempting to capture screenshot of: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-http2", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        try:
            # Try very basic navigation with short timeout
            print("Attempting page navigation...")
            try:
                page.goto(url, timeout=20000, wait_until="commit")
                print("✓ Page committed")
            except Exception as nav_error:
                print(f"Navigation error (will try screenshot anyway): {nav_error}")
            
            # Wait a moment for any content
            import time
            time.sleep(5)
            
            # Take screenshot no matter what
            print("Capturing screenshot...")
            os.makedirs("screenshots", exist_ok=True)
            screenshot_path = "screenshots/honeywell_com_sustainability.png"
            
            page.screenshot(path=screenshot_path, full_page=True, timeout=15000)
            print(f"✓ Screenshot saved to: {screenshot_path}")
            
        except Exception as e:
            print(f"✗ Fatal error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    capture_honeywell_screenshot()
