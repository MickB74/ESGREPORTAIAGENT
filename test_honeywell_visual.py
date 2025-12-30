from esg_scraper import ESGScraper
import sys

def test_honeywell_nonheadless():
    url = "https://www.honeywell.com/us/en/company/sustainability"
    print(f"--- Testing Honeywell (NON-HEADLESS): {url} ---", flush=True)
    print("This will open a visible browser window to see what's happening...", flush=True)
    
    scraper = ESGScraper(headless=False)  # Run with visible browser
    
    print(f"\nCalling scraper.scan_url('{url}')...", flush=True)
    sys.stdout.flush()
    
    links = scraper.scan_url(url)
    
    print(f"\n=== RESULTS ===", flush=True)
    print(f"Found {len(links)} links via scan_url:", flush=True)
    
    for i, link in enumerate(links[:10], 1):  # Show first 10
        print(f"{i}. {link['text']}", flush=True)
        print(f"   URL: {link['url']}", flush=True)
        print(f"   Score: {link['score']}", flush=True)
    
    if len(links) > 10:
        print(f"\n... and {len(links) - 10} more links", flush=True)

if __name__ == "__main__":
    test_honeywell_nonheadless()
