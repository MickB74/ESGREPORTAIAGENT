import requests
from bs4 import BeautifulSoup
import re

url = "https://www.cbre.com/about/corporate-responsibility"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    print(f"Fetching {url}...")
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    
    soup = BeautifulSoup(resp.content, 'html.parser')
    links = soup.find_all('a', href=True)
    print(f"Found {len(links)} links.")
    
    found_pdfs = 0
    found_reports = 0
    
    for link in links:
        href = link['href']
        text = link.get_text(strip=True)
        
        if 'pdf' in href.lower():
            print(f"PDF Found: {text} -> {href}")
            found_pdfs += 1
            
        elif 'report' in text.lower():
            print(f"Report Link Found: {text} -> {href}")
            found_reports += 1
            
    print(f"\nSummary: {found_pdfs} PDFs, {found_reports} 'Report' links.")

except Exception as e:
    print(f"Error: {e}")
