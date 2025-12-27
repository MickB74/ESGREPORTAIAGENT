from esg_scraper import ESGScraper
import json

def test_deep_scan():
    print("Testing Deep Scan...")
    
    # Target: A known ESG page
    test_config = {
        "url": "https://www.apple.com/environment/",
        "name": "Apple",
        "wait_until": "domcontentloaded",
        "wait_for": "body"
    }
    
    scraper = ESGScraper(headless=True)
    results = scraper.run(sites_config=[test_config])
    
    if "Apple" in results:
        links = results["Apple"]
        print(f"Found {len(links)} links.")
        for l in links[:5]:
            print(f" - {l['text']} ({l['url']}) [Score: {l['score']}]")
            
        print("\nStructure of first link:")
        print(json.dumps(links[0], indent=2))
        
        # Verify app.py logic
        print("\nSimulating App Logic:")
        app_reports = []
        for link in links:
             pw_report = {
                 "title": link['text'],
                 "href": link['url'],
                 "body": "Detected via Deep Browser Scan",
                 "source": "Deep Browser Scan"
             }
             app_reports.append(pw_report)
        print(f"App would accept {len(app_reports)} reports.")
        
    else:
        print("No results found for Apple.")

if __name__ == "__main__":
    test_deep_scan()
