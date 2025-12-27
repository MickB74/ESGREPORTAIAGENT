from esg_scraper import ESGScraper

scraper = ESGScraper(headless=True)
site = {
    "url": "https://investor.spglobal.com/corporate-governance/Impact-and-TCFD-Reports/",
    "name": "SP_Global",
    "wait_for": "body" 
}

print("Running scraper on S&P Global...")
# Fixed: run calls directly
# results = scraper.run([site]) # Called below

results = scraper.run([site])
print(f"Found: {results}")

# If we found nothing, let's debug the HTML content
if not results:
    from playwright.sync_api import sync_playwright
    print("DEBUG: Dumping page content keys...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(site['url'])
        page.wait_for_timeout(5000) # Wait for potential JS
        content = page.content()
        if "TCFD" in content:
            print("Page HAS 'TCFD' text.")
        else:
            print("Page MISSING 'TCFD' text.")
            
        # Check for iframes
        frames = page.frames
        print(f"Frame count: {len(frames)}")
        browser.close()
