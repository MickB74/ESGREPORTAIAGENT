from esg_scraper import ESGScraper

scraper = ESGScraper(headless=True)
site = {
    "url": "https://corporate.ford.com/social-impact/sustainability/",
    "name": "Ford",
    "wait_until": "commit",
    "wait_for": "footer" # Relaxed wait
}

results = scraper.run([site])
print(results)
