import requests
from selectolax.parser import HTMLParser
from urllib.parse import urljoin
import re

def test_tmobile_simple():
    url = "https://www.t-mobile.com/responsibility/reporting"
    print(f"Testing T-Mobile with simple requests: {url}")
    
    # Use requests instead of Playwright
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        tree = HTMLParser(response.text)
        
        # Look for PDF links
        links = []
        for node in tree.css("a"):
            href = node.attributes.get("href")
            if not href:
                continue
                
            # Get link text
            text = node.text(strip=True) or ""
            
            # Check for PDF or ESG keywords
            if ".pdf" in href.lower() or any(kw in text.lower() for kw in ["report", "esg", "sustainability", "responsibility", "cdp", "gri", "sasb"]):
                full_url = urljoin(url, href)
                
                # Clean up text
                text = re.sub(r'\s+', ' ', text).strip()
                if not text:
                    text = "Report Document"
                    
                links.append({
                    "url": full_url,
                    "text": text
                })
        
        print(f"\n=== FOUND {len(links)} LINKS ===")
        for i, link in enumerate(links[:15], 1):
            print(f"{i}. {link['text']}")
            print(f"   {link['url']}")
            print()
            
    else:
        print(f"Failed to fetch: {response.status_code}")

if __name__ == "__main__":
    test_tmobile_simple()
