#!/usr/bin/env python3
"""Debug Costco sustainability page scraping"""

from esg_scraper import ESGScraper

# Test configuration
costco_config = [{
    "url": "https://www.costco.com/f/-/sustainability",
    "name": "Costco_Test",
    "wait_for": "body"  # Generic wait
}]

print("Testing Costco sustainability page scraping...")
print("=" * 60)

scraper = ESGScraper(headless=False)  # Visible browser for debugging
results = scraper.run(costco_config)

print("\n" + "=" * 60)
print(f"Results: {results}")

if results and results.get("Costco_Test"):
    links = results["Costco_Test"]
    if isinstance(links, list):
        print(f"\n✅ Found {len(links)} links:")
        for i, link in enumerate(links[:10], 1):
            print(f"  {i}. {link['text'][:80]}")
            print(f"     URL: {link['url'][:100]}")
    else:
        print(f"\n⚠️ Unexpected result format: {type(links)}")
else:
    print("\n❌ No results found")
