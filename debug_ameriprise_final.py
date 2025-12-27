#!/usr/bin/env python3
"""Debug Ameriprise responsible business page scraping - REAL SCRAPER FINAL TEST"""

from esg_scraper import ESGScraper

# Test configuration
ameriprise_config = [{
    "url": "https://www.ameriprise.com/about/responsible-business/index",
    "name": "Ameriprise_Test",
    "wait_for": "body"
}]

print("Testing Ameriprise scraper with lowered threshold...")
print("=" * 60)

scraper = ESGScraper(headless=True)
results = scraper.run(ameriprise_config)

print("\n" * 2)
if results and results.get("Ameriprise_Test"):
    links = results["Ameriprise_Test"]
    if isinstance(links, list):
        print(f"\n✅ Found {len(links)} links:")
        for i, link in enumerate(links[:15], 1):
            print(f"\n{i}. {link['text']}")
            print(f"   URL: {link['url']}")
    else:
        print(f"\n⚠️ Unexpected format: {type(links)}")
else:
    print("\n❌ No results found")
