#!/usr/bin/env python3
"""Debug Ameriprise responsible business page scraping - RAW LINK DUMP"""

from playwright.sync_api import sync_playwright
import time

url = "https://www.ameriprise.com/about/responsible-business/index"

print(f"Inspecting: {url}")
print("=" * 60)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    time.sleep(5)  # Wait for JS
    
    # Get all links
    links = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a')).map(a => ({
            text: a.innerText.trim(),
            href: a.href,
            aria: a.getAttribute('aria-label') || '',
            title: a.getAttribute('title') || ''
        }));
    }""")
    
    print(f"Found {len(links)} total links on page (raw).")
    print("-" * 60)
    
    relevant_keywords = ["report", "esg", "sustainability", "csr", "impact", "environment", "climate", "social", "governance"]
    
    count = 0
    for l in links:
        text = l['text'] or l['aria'] or l['title']
        href = l['href']
        
        # Simple local filter to highlight likely candidates
        if any(k in text.lower() for k in relevant_keywords) or any(k in href.lower() for k in relevant_keywords):
            count += 1
            print(f"{count}. Text: {text[:50]}...")
            print(f"   URL:  {href}")
            print(f"   Raw:  {l}")
            print("-" * 20)

    browser.close()

