from esg_scraper import ESGScraper

def debug_honeywell():
    url = "https://www.honeywell.com/us/en/company/impact-report"
    print(f"--- Debugging Honeywell: {url} ---")
    
    scraper = ESGScraper(headless=True)
    
    print(f"Calling scraper.scan_url('{url}')...")
    links = scraper.scan_url(url)
    
    print(f"\nFound {len(links)} links via scan_url:")
    for l in links:
        print(f" - {l}")

if __name__ == "__main__":
    debug_honeywell()
