from playwright.sync_api import sync_playwright

def check_ford():
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        # Context with user agent is crucial for corporate sites
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        url = "https://corporate.ford.com/social-impact/sustainability/"
        print(f"Going to {url}...")
        try:
            page.goto(url, timeout=45000)
            print("Page loaded.")
            print(f"Title: {page.title()}")
            
            # Check for report links
            links = page.locator("a[href$='.pdf']").all()
            print(f"Found {len(links)} PDF links immediately.")
            
            # Check for 'Download' buttons/text
            buttons = page.get_by_text("Download", exact=False).all()
            print(f"Found {len(buttons)} elements with 'Download'.")
            
            # Wait for footer to see if it makes a difference (full load)
            page.wait_for_selector("footer", timeout=10000)
            print("Footer found.")
            
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="ford_error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    check_ford()
