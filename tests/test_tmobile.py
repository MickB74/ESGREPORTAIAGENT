from esg_scraper import ESGScraper
import sys

def test_tmobile():
    url = "https://www.t-mobile.com/responsibility/reporting?INTNAV=tNav%3AResponsibility%3AReporting"
    print(f"--- Testing T-Mobile: {url} ---", flush=True)
    
    scraper = ESGScraper(headless=True)
    
    print(f"Calling scraper.scan_url('{url}')...", flush=True)
    sys.stdout.flush()
    
    links = scraper.scan_url(url)
    
    print(f"\n=== RESULTS ===", flush=True)
    print(f"Found {len(links)} links via scan_url:", flush=True)
    
    for i, link in enumerate(links[:10], 1):
        print(f"{i}. {link['text']}", flush=True)
        print(f"   URL: {link['url']}", flush=True)
        print(f"   Score: {link['score']}", flush=True)
    
    if len(links) > 10:
        print(f"\n... and {len(links) - 10} more links", flush=True)

if __name__ == "__main__":
    test_tmobile()
