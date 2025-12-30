from playwright.sync_api import sync_playwright
import time

def simple_honeywell_test():
    """Simple test to see if we can even load the page at all"""
    # Test both URLs
    urls = [
        "https://www.honeywell.com/us/en/company/impact-report",
        "https://www.honeywell.com/us/en/company/sustainability"
    ]
    
    for url in urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print('='*60)
    
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-http2", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            print("Attempting simple navigation...")
            try:
                page.goto(url, timeout=30000, wait_until="commit")  # Just wait for initial commit
                print(f"✓ Page navigation committed")
                
                time.sleep(10)  # Wait for content to load
                
                # Get page content
                html = page.content()
                print(f"✓ Page HTML length: {len(html)} characters")
                
                # Check for any links
                links = page.locator("a[href]").all()
                print(f"✓ Found {len(links)} total anchor tags")
                
                # Check for PDF links
                pdf_links = page.locator("a[href*='.pdf']").all()
                print(f"✓ Found {len(pdf_links)} PDF links")
                
                # Get page title
                title = page.title()
                print(f"✓ Page title: {title}")
                
            except Exception as e:
                print(f"✗ Error: {e}")
            finally:
                browser.close()

if __name__ == "__main__":
    simple_honeywell_test()
