
import time
import os
from playwright.sync_api import sync_playwright
from selectolax.parser import HTMLParser
from urllib.parse import urljoin

# --- CONFIGURATION: The "Brain" of the Tool ---
# This is where you adapt to new sites without rewriting the engine.
SITES = [
    {
        "url": "https://sustainability.atmeta.com/",
        "name": "Meta",
        # Meta is dynamic; we just need to wait for the page to load
        "wait_for": "body" 
    },
    {
        "url": "https://corporate.visa.com/en/about-visa/esg.html",
        "name": "Visa",
        "wait_for": "body"
    },
    {
        "url": "https://corporate.homedepot.com/page/resources-reports",
        "name": "Home_Depot",
        # Home Depot is heavy JS; we explicitly wait for their report container
        "wait_for": ".views-element-container" 
    },
    {
        "url": "https://www.factset.com/our-company/sustainability",
        "name": "FactSet",
        "wait_for": "main" # Detected by auto-config
    },
    {
        "url": "https://investor.spglobal.com/corporate-governance/Impact-and-TCFD-Reports/",
        "name": "SP_Global",
        "wait_for": "body"
    },
    {
        "url": "https://corporate.ford.com/social-impact/sustainability/",
        "name": "Ford",
        "wait_until": "domcontentloaded",
        "wait_for": "div.module-container" # Waiting for some content container
    }
]

# Keywords to score "good" links if we are guessing
REPORT_KEYWORDS = ["report", "esg", "sustainability", "2024", "2025", "2023", "impact", "tcfd", "annual"]

class ESGScraper:
    def __init__(self, headless=True):
        self.headless = headless

    def get_report_links(self, page_content, base_url):
        """
        Parses HTML and finds PDF links.
        Uses 'Heuristic Scoring' to prioritize likely ESG reports.
        """
        tree = HTMLParser(page_content)
        candidates = []
        
        for node in tree.css("a"):
            href = node.attributes.get("href")
            text = node.text(strip=True).lower()
            
            if not href:
                continue
                
            # 1. Score: Does the text look like a report?
            score = 0
            for kw in REPORT_KEYWORDS:
                if kw in text or kw in href.lower():
                    score += 1
            
            # Normalize URL
            href = urljoin(base_url, href)

            # 2. Filter: Must be a PDF OR have a good score
            if href.lower().endswith(".pdf") or score >= 1:
                # Boost score for PDF to keep them top priority
                if href.lower().endswith(".pdf"):
                    score += 2
                
                candidates.append({"url": href, "text": text, "score": score})

        # Return only high-quality links (score > 0) or all if strict mode is off
        # We prioritize higher scores
        return sorted(candidates, key=lambda x: x['score'], reverse=True)

    def scrape_site(self, site, browser_context):
        """
        Process a single site configuration.
        """
        print(f"\n🌍 Processing: {site['name']}...")
        page = browser_context.new_page()
        
        try:
            wait_strategy = site.get("wait_until", "load") # Default to 'load', but can be 'domcontentloaded' or 'commit'
            page.goto(site['url'], timeout=60000, wait_until=wait_strategy)
            
            # --- STRATEGY: Click to Download ---
            if "click_selector" in site:
                print(f"   🖱️ Clicking selector: {site['click_selector']}")
                try:
                    page.click(site['click_selector'], timeout=5000)
                    time.sleep(2) # Wait for reaction
                except Exception as e:
                    print(f"   ⚠️ Warning: Click failed on {site['name']}: {e}")

            # --- STRATEGY: Dynamic Wait ---
            if "wait_for" in site:
                try:
                    page.wait_for_selector(site['wait_for'], timeout=15000)
                except:
                    print(f"   ⚠️ Warning: Timeout waiting for selector {site['wait_for']} on {site['name']}")

            # Small sleep to ensure animations settle
            time.sleep(3)
            
            # Get the fully rendered HTML
            html = page.content()
            
            # Analyze links
            links = self.get_report_links(html, site['url'])
            
            print(f"   found {len(links)} potential PDF(s)")
            
            if links:
                best_link = links[0] # The one with the highest keyword score
                print(f"   ⬇️  Downloading top match: {best_link['text'][:50]}...")
                print(f"   🔗  URL: {best_link['url']}")
                return best_link
            else:
                print("   ❌ No obvious PDF reports found.")
                return None
                
        except Exception as e:
            print(f"   🔥 Error scraping {site['name']}: {e}")
            return None
        finally:
            page.close()

    def run(self, sites_config=SITES):
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            
            results = {}
            for site in sites_config:
                result = self.scrape_site(site, context)
                if result:
                    results[site['name']] = result
            
            browser.close()
            return results

def detect_config(url):
    """
    Experimental: Tries to auto-detect the best wait selector for a given URL.
    This is the 'Config Generator' script.
    """
    print(f"🕵️ Analyzing {url} for config...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=30000)
            # Basic heuristic: Check if 'body' is loaded.
            # Real detection would be more complex, looking for loading spinners or skeletal UIs.
            
            # Check for common heavy-weight containers
            common_selectors = [".views-element-container", "#main-content", "main", "div[class*='report']", "footer"]
            
            suggested = "body" 
            for sel in common_selectors:
                if page.locator(sel).count() > 0:
                    suggested = sel
                    break
            
            print(f"✅ Suggested Config:\n{{\n    'url': '{url}',\n    'name': 'Detected_Site',\n    'wait_for': '{suggested}'\n}}")
            return suggested
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    # Example Usage:
    scraper = ESGScraper(headless=True) # Set headless=False to watch it work
    scraper.run()
    
    # Example Config Gen:
    # detect_config("https://www.apple.com/environment/")
