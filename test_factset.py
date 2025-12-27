from esg_scraper import ESGScraper

scraper = ESGScraper(headless=True)
# Define just the FactSet site
site = {
    "url": "https://www.factset.com/our-company/sustainability",
    "name": "FactSet",
    "wait_for": "main"
}

results = scraper.run([site])
print(results)
