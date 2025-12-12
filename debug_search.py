from ddgs import DDGS
import time
from urllib.parse import urlparse

def get_domain(url):
    try:
        return urlparse(url).netloc
    except:
        return ""

def test(company):
    print(f"\nTesting for: {company}")
    with DDGS() as ddgs:
        # Step 1: Find Official Website
        # Using 'official corporate website' usually ranks the main site #1
        q_site = f"{company} official corporate website"
        print(f"  Query 1: {q_site}")
        
        candidates = list(ddgs.text(q_site, max_results=3, region='us-en'))
        
        official_domain = None
        
        for c in candidates:
            url = c['href']
            domain = get_domain(url)
            # Filter out common encyclopedias/news if possible, though 'official' usually pushes them down
            if 'wikipedia' not in domain and 'bloomberg' not in domain and 'reuters' not in domain:
                official_domain = domain
                print(f"  Found potential official domain: {official_domain} ({url})")
                break
        
        if not official_domain:
            print("  Could not determine official domain.")
            return

        # Step 2: Search specific ESG site on that domain
        q_esg = f"site:{official_domain} ESG sustainability"
        print(f"  Query 2: {q_esg}")
        
        esg_results = list(ddgs.text(q_esg, max_results=3, region='us-en'))
        for res in esg_results:
            print(f"    Result: {res['title']} -> {res['href']}")

if __name__ == "__main__":
    test("Apple")
    test("ExxonMobil")
    test("3M")
