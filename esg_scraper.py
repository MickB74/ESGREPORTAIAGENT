
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
        
        GENERIC_TERMS = ["download", "pdf", "click here", "read more", "view", "report", "file", "link"]

        def extract_year(text):
            """Extract 4-digit year from text (2020-2030)"""
            import re
            years = re.findall(r'\b(202[0-9]|203[0])\b', text)
            return years[0] if years else None

        def get_parent_context(node):
            """Get text from parent elements for context"""
            context_text = ""
            parent = node.parent
            
            # Go up 2 levels max to find context
            for _ in range(2):
                if parent and parent.tag in ['div', 'p', 'li', 'td', 'section', 'article']:
                    parent_text = parent.text(strip=True)
                    if parent_text and len(parent_text) < 200:  # Don't get huge blocks
                        context_text = parent_text
                        break
                if parent:
                    parent = parent.parent
                else:
                    break
            
            return context_text

        def get_best_text(node):
            # 1. Visible Text
            text = node.text(strip=True)
            
            # 2. Attributes (aria-label, title) - often has the full context
            aria = node.attributes.get("aria-label", "").strip()
            title = node.attributes.get("title", "").strip()
            
            # 3. Image Alt Text (if link wraps an image)
            alt_text = ""
            img = node.css_first("img")
            if img:
                alt_text = img.attributes.get("alt", "").strip()

            # Decision Logic:
            # If text is empty or generic, prefer attributes
            is_text_generic = not text or text.lower() in GENERIC_TERMS or len(text) < 4
            
            if is_text_generic:
                if aria: return aria
                if title: return title
                if alt_text: return alt_text
            
            # If we have text but aria is strictly more descriptive (longer), use aria
            if text and aria and len(aria) > len(text) + 5:
                # heuristic: if aria is significantly longer, it's probably better
                return aria

            base_text = text if text else (aria or title or alt_text or "Unknown Link")
            
            # 4. Enhancement: Add year from context if missing
            year = extract_year(base_text)
            if not year:
                # Look in parent context
                context = get_parent_context(node)
                year = extract_year(context)
                
                # If we found a year in context and it's not in the base text, add it
                if year and year not in base_text:
                    base_text = f"{base_text} ({year})"
            
            return base_text

        for node in tree.css("a"):
            href = node.attributes.get("href")
            text = get_best_text(node)
            
            # Clean text (remove newlines, extra spaces)
            import re
            text = re.sub(r'\s+', ' ', text).strip()
            if not text: text = "Unknown Report Document"
            text_lower = text.lower()
            
            if not href:
                continue
                
            # 1. Score: Does the text look like a report?
            score = 0
            for kw in REPORT_KEYWORDS:
                if kw in text_lower or kw in href.lower():
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
