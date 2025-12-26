
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
            
        def get_preceding_header(node):
            """
            Traverses backwards to find the nearest header (h1-h6).
            Useful for lists like: 
            <h3>2024 Reports</h3> 
            <ul><li><a...>Report</a></li></ul>
            """
            current = node.parent
            for _ in range(5): # Limit traversal depth
                if not current: break
                
                # Check previous siblings
                prev = current.prev
                while prev:
                    if prev.tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        return prev.text(strip=True)
                    prev = prev.prev
                
                current = current.parent
            return None

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
            href = node.attributes.get("href", "")
            
            # 2. Attributes (aria-label, title) - often has the full context
            aria = node.attributes.get("aria-label", "").strip()
            title = node.attributes.get("title", "").strip()
            
            # 3. Image Alt Text (if link wraps an image)
            alt_text = ""
            img = node.css_first("img")
            if img:
                alt_text = img.attributes.get("alt", "").strip()

            # Decision Logic:
            generic_terms = ["download", "pdf", "click here", "read more", "view", "report", "file", "link", "sustainability", "esg", "annual", "environmental", "social", "governance", "annual report", "sustainability report"]
            
            # Initial base name selection
            # If text is empty or super generic, prefer aria/title
            is_text_generic = not text or text.lower() in generic_terms or len(text) < 4
            
            base_text = text
            if is_text_generic:
                if aria: base_text = aria
                elif title: base_text = title
                elif alt_text: base_text = alt_text
            
            # If we have basic text but attributes are much better/longer
            elif aria and len(aria) > len(text) + 5:
                base_text = aria
                
            if not base_text: base_text = "Unknown Link"

            # 4. Contextual Enhancement Pipeline
            # A. Check URL for Year (often reliable: .../2023/report.pdf)
            year_url = extract_year(href)
            if year_url and year_url not in base_text:
                base_text = f"{base_text} ({year_url})"

            # B. Check Preceding Header (for grouped lists)
            # Only do this if text is somewhat generic or short
            if len(base_text) < 30 or any(t in base_text.lower() for t in generic_terms):
                header = get_preceding_header(node)
                if header and len(header) < 50: # Don't prepend massive headers
                    # Clean header
                    import re
                    header = re.sub(r'\s+', ' ', header).strip()
                    # Avoid duplication (e.g. Header="2023 Report", Name="2023 Report")
                    if header.lower() not in base_text.lower():
                        base_text = f"{header} - {base_text}"

            # C. Check Parent Content (last resort for year)
            if not extract_year(base_text):
                ctx = get_parent_context(node)
                y = extract_year(ctx)
                if y and y not in base_text:
                     base_text = f"{base_text} ({y})"
            
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
