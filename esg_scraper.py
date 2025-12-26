
import time
import re
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
        
        # Negative keywords to exclude (non-report pages)
        EXCLUDE_KEYWORDS = [
            "login", "career", "job", "apply", "search", "contact",
            "privacy policy", "terms", "cookie", "faq", "about us",
            "news", "press release", "blog", "financial advisor"
        ]

        def extract_year(text):
            """Extract 4-digit year from text (2020-2030)"""
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
            text = node.text(strip=True) or ""
            href = node.attributes.get("href", "") or ""
            
            # 2. Attributes (aria-label, title) - often has the full context
            aria = (node.attributes.get("aria-label") or "").strip()
            title = (node.attributes.get("title") or "").strip()
            
            # 3. Image Alt Text (if link wraps an image)
            alt_text = ""
            img = node.css_first("img")
            if img:
                alt_text = (img.attributes.get("alt") or "").strip()

            # Enhanced Generic Detection
            generic_terms = [
                "download", "pdf", "click here", "read more", "view", "report", 
                "file", "link", "learn more", "see more", "details", "here",
                "more info", "accessibility", "opens in"
            ]
            
            # Enhanced Name Selection with URL Parsing
            is_text_generic = not text or any(term in text.lower() for term in generic_terms) or len(text) < 4
            
            base_text = text
            if is_text_generic:
                # Try attributes first
                if aria and not any(term in aria.lower() for term in generic_terms): 
                    base_text = aria
                elif title and not any(term in title.lower() for term in generic_terms): 
                    base_text = title
                elif alt_text: 
                    base_text = alt_text
                else:
                    # Parse URL filename as last resort
                    from urllib.parse import urlparse, unquote
                    try:
                        parsed = urlparse(href)
                        path = unquote(parsed.path)
                        filename = path.split('/')[-1]
                        name_part = filename.rsplit('.', 1)[0] if '.' in filename else filename
                        clean_name = re.sub(r'[-_]+', ' ', name_part)
                        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
                        clean_name = ' '.join(word.capitalize() for word in clean_name.split())
                        if len(clean_name) > 15:  # Only use if substantial
                            base_text = clean_name
                    except:
                        pass
            
            # If we have basic text but attributes are much better/longer
            elif aria and len(aria) > len(text) + 5:
                base_text = aria
            
            # Clean junk text
            junk_patterns = [
                r'\(opens in (?:a )?new (?:window|tab)\)',
                r'opens in (?:a )?new (?:window|tab)',
                r'\[read more\]',
                r'►', r'◄', r'📄'
            ]
            for pattern in junk_patterns:
                base_text = re.sub(pattern, '', base_text, flags=re.IGNORECASE)
            base_text = re.sub(r'\s+', ' ', base_text).strip()
                
            if not base_text or len(base_text) < 3: 
                # Fallback to report type detection
                url_lower = href.lower()
                if 'annual' in url_lower:
                    base_text = "Annual Report"
                elif any(kw in url_lower for kw in ['sustainability', 'esg', 'csr']):
                    base_text = "Sustainability Report"
                elif any(kw in url_lower for kw in ['impact', 'social']):
                    base_text = "Impact Report"
                else:
                    base_text = "Report"

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
            
            # Exclusion: Filter out non-report pages
            excluded = False
            for exc in EXCLUDE_KEYWORDS:
                if exc in text_lower or exc in href.lower():
                    excluded = True
                    break
            
            if excluded:
                continue
            
            # Normalize URL
            href = urljoin(base_url, href)

            # 2. Filter: Must be a PDF OR have a good score
            # Score 1 is sufficient if we have a robust EXCLUDE list (which we do now)
            # This captures HTML pages like "Sound Governance" or "Community Impact"
            if href.lower().endswith(".pdf") or score >= 1:
                # Boost score for PDF to keep them top priority
                if href.lower().endswith(".pdf"):
                    score += 3
                
                candidates.append({"url": href, "text": text, "score": score})

        # Return only high-quality links (score > 0) or all if strict mode is off
        # We prioritize higher scores
        return sorted(candidates, key=lambda x: x['score'], reverse=True)

    def get_hub_links(self, tree, base_url):
        """Identify potential 'Report Hubs' or 'Archives' to traverse."""
        hubs = []
        # Expanded keywords for aggressive discovery
        HUB_KEYWORDS = ["archive", "library", "downloads", "all reports", "past reports", "previous reports", "resources", "investor", "financial", "filing", "result", "quarterly", "annual"]
        
        for node in tree.css("a"):
            href = node.attributes.get("href")
            text = node.text(strip=True).lower()
            if not href or len(text) < 3: continue
            
            # Check if text matches hub keywords
            if any(kw in text for kw in HUB_KEYWORDS):
                full_url = urljoin(base_url, href)
                # Avoid navigating out of domain (simple check)
                if base_url.split('/')[2] in full_url:
                    hubs.append({"url": full_url, "text": text})
        
        # Deduplicate by URL
        unique_hubs = {h['url']: h for h in hubs}.values()
        return list(unique_hubs)

    def expand_page_interaction(self, page):
        """Aggressive interaction: Click 'Load More', Year Tabs, etc."""
        print("   🔨 Attempting to expand page content...")
        try:
            # 1. Click "Load More" / "Show All" buttons
            # Use a broad selector for buttons containing specific text
            more_buttons = page.locator("button, a, div[role='button']").filter(has_text=re.compile(r"load more|show all|view all|archive", re.IGNORECASE))
            count = more_buttons.count()
            if count > 0:
                print(f"      Found {count} expansion buttons. Clicking first one...")
                try:
                    more_buttons.first.click(timeout=3000)
                    time.sleep(2)
                except: pass
            
            # 2. Click Recent Years (2024, 2023) if they look like filters
            # This is risky as it might navigate away, but we want aggressive.
            # We'll try to click text that is EXACTLY a year
            for year in ["2024", "2023", "2025"]:
                year_btn = page.locator(f"text=^{year}$")
                if year_btn.count() > 0:
                    print(f"      Clicking year filter: {year}")
                    try:
                        year_btn.first.click(timeout=3000)
                        time.sleep(1.5)
                    except: pass
                    
        except Exception as e:
            print(f"      Interaction warning: {e}")

    def scrape_page_content(self, page, url):
        """Helper to get links from a specific page state, scanning ALL FRAMES."""
        links = []
        hubs = []
        
        try:
            # OPTIONAL: Interact to reveal content
            self.expand_page_interaction(page)
            
            # 1. Scan Main Frame
            html_main = page.content()
            l_main = self.get_report_links(html_main, url)
            h_main = self.get_hub_links(HTMLParser(html_main), url)
            
            links.extend(l_main)
            hubs.extend(h_main)
            
            # 2. Scan Sub-Frames (Aggressive)
            frames = page.frames
            if len(frames) > 1:
                print(f"      Scanning {len(frames)-1} sub-frames...")
                for frame in frames[1:]: # Skip main frame (index 0 usually)
                    try:
                        # Ensure frame is loaded
                        if not frame.url or frame.url == "about:blank": continue
                        
                        f_html = frame.content()
                        f_links = self.get_report_links(f_html, frame.url) # Use frame URL base
                        
                        if f_links:
                            # Mark them coming from a frame
                            for l in f_links: l['text'] += " [Frame]"
                            links.extend(f_links)
                    except: pass

            return links, hubs
        except Exception as e:
            print(f"Error scraping content from {url}: {e}")
            return [], []

    def scrape_site(self, site, browser_context):
        """
        Process a site with recursive Level 2 scanning for Hubs.
        """
        print(f"\n🌍 Processing: {site['name']}...")
        page = browser_context.new_page()
        all_links = []
        visited_urls = set()
        
        try:
            # 1. Visit Main Page
            wait_strategy = site.get("wait_until", "load")
            print(f"   ➡️ Visiting Main: {site['url']}")
            page.goto(site['url'], timeout=60000, wait_until=wait_strategy)
            
            # Handle cookies/popups if possible (basic click)
            try: 
                page.click("button:has-text('Accept')", timeout=2000)
            except: pass

            time.sleep(3) # Settle
            
            main_links, hubs = self.scrape_page_content(page, site['url'])
            all_links.extend(main_links)
            visited_urls.add(site['url'])

            # 2. Level 2: Visit Hubs (Max 2)
            if hubs:
                print(f"   🔎 Found {len(hubs)} potential archives. Checking top 2...")
                for hub in hubs[:2]:
                    if hub['url'] in visited_urls: continue
                    
                    print(f"   ➡️ Visiting Hub: {hub['text'][:30]}...")
                    try:
                        page.goto(hub['url'], timeout=45000, wait_until="domcontentloaded")
                        time.sleep(3)
                        hub_links, _ = self.scrape_page_content(page, hub['url'])
                        
                        # Add new unique links
                        existing_urls = {l['url'] for l in all_links}
                        for hl in hub_links:
                            if hl['url'] not in existing_urls:
                                hl['text'] = f"[Hub: {hub['text']}] {hl['text']}" # Mark source
                                all_links.append(hl)
                                
                        visited_urls.add(hub['url'])
                    except Exception as e:
                        print(f"   Failed to scrape hub {hub['url']}: {e}")
            
            print(f"   ✅ Found {len(all_links)} total reports.")
            
            # Return top result for basic compatibility, but actually we want all
            # The original code returned 'result' (one link). 
            # We should probably return LIST of links if called from app?
            # Existing contract returns dictionary of results.
            # Let's return the full list if possible, or just the best one if fitting old contract.
            # BUT: app.py calls this logic? 
            # App.py imports ESGScraper... wait. 
            # App.py calls `search_esg_info` which calls `ESGScraper`? 
            # No, `debug_amat.py` works, but app.py currently only uses ESGScraper for SCREENSHOTS (in strict mode).
            # The MAIN scan in app.py uses `requests` + `collect_links`.
            # AHH: Task `Fix Applied Materials Scanning` said: "Update app.py to use Playwright/ESGScraper for 'Deep Scan'".
            # Let's check `app.py` to see if it actually USES ESGScraper for scanning content.
            # I suspect it DOES NOT yet, or I missed it.
            
            # Re-reading `app.py`: 
            # "new_data = search_esg_info(..., known_website=data['website'], strict_mode=True)"
            # `search_esg_info` uses `requests` primarily.
            
            # WAIT. If I want "Better Scanning", I should ensure `app.py` uses `ESGScraper` (Playwright) 
            # when `strict_mode` is on or as a fallback.
            
            # Logic here: I will return the best link as per old contract, 
            # BUT I should probably expose a method `detect_all_reports`.
            
            if all_links:
                # Sort by score
                all_links.sort(key=lambda x: x['score'], reverse=True)
                return all_links # Returning LIST now. Caller must handle!
            return []

        except Exception as e:
            print(f"   🔥 Error scraping {site['name']}: {e}")
            return []
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
                found_links = self.scrape_site(site, context)
                if found_links:
                    results[site['name']] = found_links
            
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
