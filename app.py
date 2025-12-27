import streamlit as st
from duckduckgo_search import DDGS
import time
import datetime
import json
import os
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd
import difflib
# MongoDB Handler
from mongo_handler import MongoHandler

# Initialize MongoDB Handler
if "mongo" not in st.session_state:
    st.session_state.mongo = MongoHandler()
mongo_db = st.session_state.mongo

# --- App Configuration (Must be first!)# Main App
st.set_page_config(page_title="ESG Report AI Agent", layout="wide")

st.title("ESG Report AI Agent 🤖 (v2.0)")
st.markdown("---")
# --- Auto-Install Playwright Browsers (for Cloud Env) ---
@st.cache_resource
def install_playwright():
    import subprocess
    import sys
    try:
        # Check if we need to install (skip if already done in session, handled by cache_resource)
        # But we need to handle system deps which might need sudo/apt, which we can't do here easily.
        # However, 'playwright install --with-deps' tries to install OS deps.
        # On Streamlit Cloud, we might not have sudo.
        # We will try 'playwright install chromium' first (browsers only).
        print("Installing Playwright browsers...")
        
        # 1. Install Browsers
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        
        # 2. Optional: Install Deps (often fails without sudo, but worth a try (dry run? no))
        # subprocess.run([sys.executable, "-m", "playwright", "install-deps", "chromium"], check=False)
        
        print("Playwright installation complete.")
    except Exception as e:
        print(f"Error installing Playwright: {e}")

install_playwright()

# ... (rest of imports/code) ...



# Helper to checking if domain is likely an official site (heuristic)
# Helper to checking if domain is likely an official site (heuristic)
def search_web(query, max_results, ddgs_instance=None):
    """
    Wrapper for DuckDuckGo search.
    Returns list of dicts: {'title': str, 'href': str, 'body': str}
    """
    if not ddgs_instance:
        with DDGS() as ddgs:
            try:
                return list(ddgs.text(query, max_results=max_results, region='us-en'))
            except Exception as e:
                print(f"DuckDuckGo Error: {e}")
                return []
    
    try:
        return list(ddgs_instance.text(query, max_results=max_results, region='us-en'))
    except Exception as e:
        print(f"DuckDuckGo Error: {e}")
        return []


# Helper to checking if domain is likely an official site (heuristic)
def is_likely_official_domain(url, company_name):
    try:
        domain = urlparse(url).netloc.lower()
    except:
        return False
    # Block list of common non-corporate domains
    block_list = [
        'wikipedia.org', 'bloomberg.com', 'reuters.com', 'yahoo.com', 
        'finance.yahoo.com', 'wsj.com', 'cnbc.com', 'forbes.com', 
        'investopedia.com', 'morningstar.com', 'marketwatch.com', 
        'motleyfool.com', 'seekingalpha.com', 'barrons.com',
        'bing.com' # Filter out search engine ad links
    ]
    if any(b in domain for b in block_list):
        return False
    return True

def get_significant_token(name):
    """Returns the most significant part of a company name for verification."""
    stopwords = ['the', 'inc', 'corp', 'corporation', 'company', 'ltd', 'limited', 'group', 'holdings', 'plc', 'nv', 'sa', 'ag']
    parts = name.lower().replace('.', '').replace(',', '').split()
    significant = [p for p in parts if p not in stopwords and len(p) > 2] # >2 chars
    if significant:
        return significant[0] # Return first significant word (e.g. "Gap" from "The Gap Inc")
    return name.split()[0].lower() # Fallback

def verify_pdf_content(url, title, company_name, context="report"):
    """
    Downloads PDF and verifies:
    1. File size > 50KB
    2. Company name on Page 1-3
    3. "Report" keywords on Page 1-3
    """
    import io
    import pypdf
    
    # Helper for logging (print to stdout for now, handled by main loop logging usually)
    def log_v(msg):
        print(f"[VERIFY] {msg}")

    try:
        log_v(f"Verifying ({context}): {url}")
        
        # Robust Headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }

        # Stream request to check headers first
        try:
            from urllib3.exceptions import InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
            response = requests.get(url, headers=headers, timeout=10, stream=True)
        except requests.exceptions.SSLError:
             response = requests.get(url, headers=headers, timeout=10, stream=True, verify=False)
        except Exception:
            return None

        # Content Type Check
        c_type = response.headers.get('Content-Type', '').lower()
        
        # ALLOW HTML now (User request: "all links from the main part of the page")
        is_pdf = 'pdf' in c_type or 'application/octet-stream' in c_type
        is_html = 'text/html' in c_type
        
        if not is_pdf and not is_html:
            response.close()
            return None
            
        # If HTML, just verify it's reachable and return (don't parse PDF)
        if is_html:
             response.close()
             # We trust the link text filtering done before this call
             return {
                 "title": title,
                 "href": url,
                 "body": "Webpage Report / Resource"
             }

        # Size Check
        content_length = response.headers.get('Content-Length')
        if content_length:
            size_bytes = int(content_length)
            if size_bytes < 50000: # 50KB
                response.close()
                return None
            # OPTIMIZATION: If > 20MB, assume it's a report (save bandwidth)
            if size_bytes > 20 * 1024 * 1024:
                 response.close()
                 return {
                     "title": title,
                     "href": url,
                     "body": "Verified Large PDF Report"
                 }
        
        # Content Download
        try:
            # Read only start to check magic bytes
            chunk = response.raw.read(4)
            if chunk != b'%PDF':
                response.close()
                return None
            
            # Read rest
            pdf_data = chunk + response.raw.read()
            f = io.BytesIO(pdf_data)
        except Exception as e:
            response.close()
            return None
        
        response.close()
        
        try:
            reader = pypdf.PdfReader(f)
        except:
            return None
        
        if len(reader.pages) == 0:
            return None
        
        # --- TITLE ENHANCEMENT LOGIC ---
        final_title = title # Default to link text
        
        # 1. Try PDF Metadata
        pdf_title = None
        try:
            if reader.metadata and reader.metadata.title:
                meta_t = reader.metadata.title.strip()
                if len(meta_t) > 5 and "micros" not in meta_t.lower() and "untitled" not in meta_t.lower():
                     pdf_title = meta_t
        except: pass
        
        # 2. Try Filename from URL
        url_filename = os.path.basename(urlparse(url).path)
        clean_filename = url_filename.replace('.pdf', '').replace('-', ' ').replace('_', ' ').title()
        
        # 3. Decision Logic
        # Is the original link text generic?
        generic_terms = ['report', 'download', 'pdf', 'click here', 'view', 'full report', 'read more', 'file']
        is_generic = False
        if len(title) < 10 or any(title.lower() == g for g in generic_terms):
            is_generic = True
            
        if pdf_title:
            # Metadata is usually best if it exists
            final_title = pdf_title
        elif is_generic and len(clean_filename) > 5:
            # Fallback to filename if link text is bad
            final_title = clean_filename
            
        # Refine: Ensure year is present if possible
        import re
        year_match = re.search(r'(20[12][0-9])', final_title)
        if not year_match:
             # Try to find year in URL or Original Text to append
             y_url = re.search(r'(20[12][0-9])', url)
             if y_url:
                 final_title = f"{final_title} ({y_url.group(1)})"
        
        # Check first 3 pages
        pages_to_check = min(3, len(reader.pages))
        text_content = ""
        for i in range(pages_to_check):
            try:
                text_content += reader.pages[i].extract_text().lower() + " "
            except:
                pass
        
        # Check Company Name (SMARTER)
        sig_token = get_significant_token(company_name) 
        if sig_token not in text_content:
            log_v(f"[SKIP] Company token '{sig_token}' not found.")
            return None
            
        # Check Company Name (SMARTER)
        sig_token = get_significant_token(company_name) 
        if sig_token not in text_content:
            log_v(f"[SKIP] Company token '{sig_token}' not found.")
            return None
            
        # Check Keywords (Context specific)
        report_keywords = ['report', 'sustainability', 'esg', 'annual', 'review', 'fiscal', 'summary']
        if not any(k in text_content for k in report_keywords):
            return None
        
        log_v(f"[MATCH] Verified: {url}")
        return {
            "title": final_title,
            "href": url,
            "body": "Verified PDF Report"
        }

    except Exception as e:
        return None

# Function to clean scraped titles
def clean_title(text):
    if not text:
        return "ESG Report"
    
    # Remove common junk from scraping icons/svgs
    junk_phrases = [
        "PDFCreated with Sketch.", 
        "backgroundLayer", 
        "Created with Sketch",
        "Shape",
        "Path"
    ]
    
    for junk in junk_phrases:
        text = text.replace(junk, " ")
        
    # Collapse whitespace
    text = " ".join(text.split())
    
    # If text became empty or too short, fallback
    if len(text) < 5:
        return "ESG Report"
        
    return text

# --- Saved Links Logic ---
LINKS_FILE = os.path.join(os.path.dirname(__file__), "saved_links.json")

def load_links_from_disk():
    if not os.path.exists(LINKS_FILE):
        return []
    try:
        with open(LINKS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

# Initialize Session State for Saved Links
if 'saved_links' not in st.session_state:
    st.session_state['saved_links'] = load_links_from_disk()

def save_links_to_disk():
    """Syncs session state to disk."""
    try:
        with open(LINKS_FILE, "w") as f:
            json.dump(st.session_state['saved_links'], f)
        return True
    except Exception as e:
        print(f"Error saving links: {e}")
        return False

def save_link_to_file(title, url, description=None, symbol=None, company=None):
    # Use Session State as Source of Truth
    links = st.session_state['saved_links']
    
    # Check if exists and update
    for link in links:
        if link['href'] == url:
            link['title'] = title
            if description:
                link['description'] = description
            if symbol:
                link['symbol'] = symbol
            if company:
                link['company'] = company
            save_links_to_disk() # Sync
            return True # Updated existing
    
    new_link = {"title": title, "href": url}
    if description:
        new_link["description"] = description
    if symbol:
        new_link["symbol"] = symbol
    if company:
        new_link["company"] = company
        
    links.append(new_link)
    save_links_to_disk() # Sync
    return True

def delete_link_by_url(target_url):
    print(f"[DEBUG] Attempting to delete: '{target_url}'")
    target_clean = target_url.strip()
    
    initial_count = len(st.session_state['saved_links'])
    
    # Filter out the matching URL (creating a new list)
    st.session_state['saved_links'] = [
        link for link in st.session_state['saved_links'] 
        if link.get('href', '').strip() != target_clean
    ]
    
    new_count = len(st.session_state['saved_links'])
    
    if new_count < initial_count:
        print(f"[DEBUG] Deleted {initial_count - new_count} link(s). New count: {new_count}")
        save_links_to_disk()
        return True
        
    print(f"[DEBUG] NO MATCH FOUND for '{target_clean}'. Count remains {initial_count}.")
    return False

# Function to perform searches
# Function to perform searches
def search_esg_info(company_name, fetch_reports=True, known_website=None, symbol=None, strict_mode=False):

    import concurrent.futures
    import datetime
    import io
    import pypdf

    def log(msg):
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    # ... (proceed to web search) ...
    results = {
        "company": company_name,
        "description": None,
        "timestamp": datetime.datetime.now().isoformat(),
        "website": None,
        "reports": [],
        "symbol": symbol,
        "search_log": []
    }
    
    official_domain = None
    esg_hub_urls = [] 


    log("Starting search...")
    # Add initial context to log
    results["search_log"].append(f"Starting search for: {company_name} (Known Symbol: {symbol}, Fetch Reports: {fetch_reports})")

    with DDGS() as ddgs:
        # --- 0. Shared Helpers ---
        
        def is_report_link(text, url):
            text_lower = text.lower()

            url_lower = url.lower()
            
            # 1. Negative Filters (Strong Rejection)
            negative_terms = ['policy', 'charter', 'code of conduct', 'guidelines', 'framework', 'presentation', 'investor presentation', 'earnings', 'quarterly', 'q1', 'q2', 'q3', 'slide', 'webcast']
            if any(term in text_lower for term in negative_terms):
                return False

            # 2. Positive Filters (Must have "Report" intent)
            # Strict: Must have [Year] or "Report"
            has_report_keyword = any(w in text_lower for w in ['report', 'sustainability', 'esg', 'annual', 'integrated', 'csr'])
            if not has_report_keyword:
                return False
                
            return True


        # --- 0.5 Load Company Map (Known Hubs) ---
        known_url = None
        resolved_name = None
        
        if known_website:
            results["website"] = known_website
            # Handle both string URL and dict with 'href' key
            if isinstance(known_website, str):
                known_url = known_website
            elif isinstance(known_website, dict):
                known_url = known_website.get('href')
            resolved_name = company_name
            log(f"Using known website: {known_url}")
        else:
            # --- OVERRIDE: Check Custom MongoDB Hubs FIRST ---
            custom_hub = None
            if "mongo" in st.session_state:
                custom_hub = st.session_state.mongo.get_company_hub(company_name)
            
            if custom_hub:
                known_url = custom_hub
                resolved_name = company_name
                log(f"Found CUSTOM verified hub (Database Override): {known_url}")
            else:
                try:
                    with open("company_map.json", "r") as f:
                        cmap = json.load(f)
                    
                    # 1. Exact Match
                    if company_name.lower() in cmap:
                        known_url = cmap[company_name.lower()]
                        resolved_name = company_name
                        log(f"Found known sustainability hub (exact): {known_url}")
                    else:
                        # 2. Fuzzy Match
                        matches = difflib.get_close_matches(company_name.lower(), cmap.keys(), n=1, cutoff=0.6)
                        if matches:
                            resolved_name = matches[0]
                            known_url = cmap[resolved_name]
                            log(f"Found known sustainability hub (fuzzy '{resolved_name}'): {known_url}")
                            
                except Exception as e:
                    log(f"Map lookup error: {e}")

        # [MOVED] Saved links display logic moved to main UI loop

        # --- 1. Official Domain Identification ---
        domain_query = f"{company_name} official corporate website"
        official_homepage_url = None
        
        if known_url:
             # Fast Path: Use known URL as the "official domain" for hub scanning
             official_domain = urlparse(known_url).netloc
             # Add to domain results to ensure it gets processed in hub scan
             domain_results = [{'href': known_url, 'title': f"{resolved_name.title()} Sustainability Hub"}]
        else:
            log(f"Searching for domain: {domain_query}")
            results["search_log"].append(f"Domain Search: \"{domain_query}\"")
            try:
                domain_results = search_web(domain_query, max_results=5, ddgs_instance=ddgs)
            except:
                domain_results = []
        
        # Process domain results (either from Search or Fast Path)
        for res in domain_results:
                url = res['href']
                title = res['title']
                
                if url.lower().endswith('.pdf'): continue
                if not is_likely_official_domain(url, company_name): continue
                
                domain_str = urlparse(url).netloc.lower()
                company_parts = company_name.lower().split()
                
                is_domain_match = False
                for part in company_parts:
                    if len(part) > 2 and part in domain_str:
                        is_domain_match = True
                        break
                
                if not is_domain_match: continue

                if company_name.split()[0].lower() in title.lower():
                     official_domain = domain_str
                     official_homepage_url = url
                     log(f"Identified official domain: {official_domain}")
                     break



        # --- 2. Find ESG Website (Refined) ---
        website_query = None
        if known_url:
            # Trusted Source
            results["website"] = {
                "title": f"{resolved_name} Sustainability Hub (Verified Site)",
                "href": known_url,
                "body": "Official verified sustainability page."
            }
        else:
            # Discovery
            if official_domain:
                website_query = f"site:{official_domain} ESG sustainability"
            else:
                website_query = f"{company_name} official ESG sustainability website"
                
    # If STRICT MODE (Verified Site Scan), try Playwright FIRST for better results (JS, Deep Scan)
    if strict_mode:
        print("   🚀 Strict Mode: using Playwright Scraper first...")
        try:
             # Lazy load
            from esg_scraper import ESGScraper
            
            # Configure flexible waiter
            wait_tag = "body"
            # Known configs
            if "homedepot" in known_website: wait_tag = ".views-element-container"
            
            scraper = ESGScraper(headless=True)
            # Create a site config on the fly
            site_config = [{
                "url": known_website, 
                "name": "Verified_Site_Scan",
                "wait_for": wait_tag 
            }]
            
            # RUN SCRAPER - use different variable name to avoid overwriting results dict
            scraper_results = scraper.run(site_config)
            
            if scraper_results and scraper_results.get("Verified_Site_Scan"):
                # Playwright found stuff!
                links = scraper_results.get("Verified_Site_Scan")
                if isinstance(links, dict): links = [links]
                
                # Convert to our app's format
                import pandas as pd
                candidates = []
                for l in links:
                    candidates.append({'title': l['text'], 'href': l['url']})
                
                if candidates:
                    print(f"   ✅ Playwright found {len(candidates)} reports.")
                    df = pd.DataFrame(candidates)
                    # Must return strict dictionary structure to match rest of app
                    return {
                        "reports": df.to_dict('records'),
                        "website": {"title": "Verified Site", "href": known_website, "body": "Verified Playwright Scan"},
                        "search_log": ["Strict Mode: Playwright Deep Scan"]
                    }

        except Exception as e:
            print(f"   ⚠️ Playwright Scan failed: {e}. Falling back to standard requests.")
            # Fall through to standard requests logic below

    # --- Standard Requests Logic (Fallback or Normal Mode) ---
    search_results = []
    if not strict_mode and website_query:
        log(f"Searching for website query: {website_query}")
        # Only do web search if we are NOT in strict mode and have a query
        search_results = search_web(website_query, max_results=3, ddgs_instance=ddgs)
    
    # If strict mode, we start with just the known website
    if strict_mode and known_website:
        search_results = [{'href': known_website, 'title': 'Verified Site'}]

    potential_domains = []
    
    # If we have a known website, prioritize it
    if known_website and not strict_mode: # If strict mode, we ALREADY handled it above OR we are falling back to it
         potential_domains.append(known_website) # We will scan it below
    
    # Add search results
    for res in search_results:
        potential_domains.append(res['href'])

    # Deduplicate
    # Keep order
    unique_domains = []
    seen = set()
    for d in potential_domains:
        if d not in seen:
            unique_domains.append(d)
            seen.add(d)

    # 3. Deep Scan (Requests-based)
    all_reports = []
    max_scan = 1 if strict_mode else 3
    
    for url in unique_domains[:max_scan]:
        try:
            domain = urlparse(url).netloc
            if not strict_mode:
                if not is_likely_official_domain(url, company_name):
                    continue
            
            print(f"   Scanning (Requests): {url}...")
            # Use requests to get HTML
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1'
                }
                resp = requests.get(url, headers=headers, timeout=15)
                
                # AUTOMATIC BYPASS: If 403 Forbidden, use Playwright
                if resp.status_code in [403, 401, 429, 503]:
                    print(f"   ⚠️ Access Denied ({resp.status_code}). Engaging Playwright Bypass...")
                    st.toast(f"Bot detected via requests. Switching to stealth Playwright... 🕵️‍♂️")
                    
                    from esg_scraper import ESGScraper
                    scraper = ESGScraper(headless=True)
                    # Run single site config
                    # Note: We rely on scraper to handle the "wait_for" logic (defaults to body)
                    res_map = scraper.run([{'url': url, 'name': 'fallback_target'}])
                    
                    if res_map and 'fallback_target' in res_map:
                        found_links = res_map['fallback_target']
                        # Convert to app format and add to results
                        for fl in found_links:
                             all_reports.append({
                                 'title': fl.get('text', 'Unknown'),
                                 'href': fl.get('url', '#'),
                                 'body': 'Extracted via Stealth Mode'
                             })
                    continue # Skip standard parsing
                    
                page_content = resp.text
                page_url = resp.url # Effective URL
                
                parsed_base = urlparse(page_url) # Re-parse for current page
                primary_domain = parsed_base.netloc

                def normalize_href(base, href):
                    if not href:
                        return None
                    if href.startswith("mailto:") or href.startswith("javascript:"):
                        return None
                    if href.startswith("#"):
                        return None
                    if href.startswith("//"):
                        return f"{parsed_base.scheme}:{href}"
                    if href.startswith("http"):
                        return href
                    return urljoin(base, href)

                def collect_links(page_url, html_text):
                    soup = BeautifulSoup(html_text, 'html.parser')
                    pdf_candidates = []
                    hubs = []
                    for link in soup.find_all('a', href=True):
                        raw_href = link['href']
                        normalized = normalize_href(page_url, raw_href)
                        if not normalized:
                            continue

                        link_domain = urlparse(normalized).netloc
                        if link_domain and primary_domain and primary_domain not in link_domain:
                            continue

                        # --- Enhanced Name Extraction with Year Detection & Headers ---
                        import re
                        
                        def extract_year_bs(text):
                            years = re.findall(r'\b(202[0-9]|203[0])\b', str(text))
                            return years[0] if years else None
                        
                        def get_preceding_header_bs(element):
                            """Traverses backwards/up to find nearest header"""
                            try:
                                current = element.parent
                                for _ in range(4): # Limit depth
                                    if not current: break
                                    prev = current.find_previous_sibling()
                                    while prev:
                                        if prev.name and prev.name.startswith('h') and len(prev.name) == 2:
                                            return prev.get_text(strip=True)
                                        prev = prev.find_previous_sibling()
                                    current = current.parent
                            except:
                                return None
                            return None

                        def get_parent_context_bs(element):
                            """Get parent context for year/info extraction"""
                            parent = element.parent
                            for _ in range(2):  # Go up 2 levels
                                if parent and parent.name in ['div', 'p', 'li', 'td', 'section', 'article']:
                                    parent_text = parent.get_text(strip=True)
                                    if parent_text and len(parent_text) < 200:
                                        return parent_text
                                parent = parent.parent if parent else None
                            return ""
                        
                        visible_text = link.get_text(strip=True)
                        aria = link.get('aria-label', '').strip()
                        title_attr = link.get('title', '').strip()
                        
                        alt_text = ""
                        img_tag = link.find('img')
                        if img_tag:
                            alt_text = img_tag.get('alt', '').strip()

                        # Pick the most descriptive name
                        generic_terms = ["download", "pdf", "click here", "read more", "view", "report", "file", "link", "sustainability", "esg", "annual", "environmental", "social", "governance", "annual report", "sustainability report"]
                        
                        is_text_generic = not visible_text or visible_text.lower() in generic_terms or len(visible_text) < 4
                        
                        # 1. Base Name Selection
                        candidate_text = visible_text
                        if is_text_generic:
                            if aria: candidate_text = aria
                            elif title_attr: candidate_text = title_attr
                            elif alt_text: candidate_text = alt_text
                        elif aria and len(aria) > len(visible_text) + 5:
                            candidate_text = aria
                        
                        if not candidate_text: candidate_text = "Unknown Web Resource"

                        # 2. Contextual Enhancement Pipeline
                        # A. Check URL for Year
                        year_url = extract_year_bs(normalized)
                        if year_url and year_url not in candidate_text:
                            candidate_text = f"{candidate_text} ({year_url})"

                        # B. Check Preceding Header (if generic)
                        if len(candidate_text) < 30 or any(t in candidate_text.lower() for t in generic_terms):
                            header = get_preceding_header_bs(link)
                            if header and len(header) < 50:
                                header = re.sub(r'\s+', ' ', header).strip()
                                if header.lower() not in candidate_text.lower():
                                    candidate_text = f"{header} - {candidate_text}"

                        # C. Check Parent Content (last resort for year)
                        if not extract_year_bs(candidate_text):
                            context = get_parent_context_bs(link)
                            year = extract_year_bs(context)
                            if year and year not in candidate_text:
                                candidate_text = f"{candidate_text} ({year})"
                            
                        text = clean_title(candidate_text)
                        if not text: text = "Unknown Web Resource"

                        # BROADENED SCOPE: Check both PDF and HTML for relevance
                        is_pdf = normalized.lower().endswith('.pdf')
                        
                        # 1. Relevance Check (Keywords)
                        if is_report_link(text, normalized):
                            
                            # 2. Negative Filter
                            is_negative = False
                            neg_terms = ['policy', 'charter', 'code of conduct', 'guidelines', 'presentation']
                            for n in neg_terms:
                                if n in text.lower(): is_negative = True
                            
                            if not is_negative:
                                pdf_candidates.append({'href': normalized, 'title': text})
                            
                            # If it's a report link, we don't treat it as a hub to traverse?
                            # Actually, maybe we should still traverse if it's a hub-like page?
                            # But for now, let's capture it.
                            continue

                        if is_pdf:
                             # If it is a PDF but failed is_report_link (maybe missing keyword?), 
                             # we might still want it if we are desperate, but is_report_link is the gatekeeper.
                             pass

                        lower_text = text.lower()
                        hub_keywords = ['report', 'archive', 'download', 'library', 'sustainability', 'esg', 'impact', 'responsibility', 'csr']
                        if any(k in lower_text for k in hub_keywords):
                            hubs.append(normalized)

                    return pdf_candidates, hubs

                scan_candidates, hub_links_to_follow = collect_links(page_url, page_content)

                if scan_candidates:
                    log(f"    Found {len(scan_candidates)} potential PDFs on {page_url}")
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name): c for c in scan_candidates}
                        for future in concurrent.futures.as_completed(futures):
                            v = future.result()
                            if v and v['href'] not in [r['href'] for r in results['reports']]:
                                v['source'] = "Official Site"
                                results["reports"].append(v)
                                all_reports.append(v) # Add to all_reports for return
            except Exception as e:
                log(f"  Requests scan failed for {url}: {e}")
        except Exception as e:
            log(f"  Error processing domain {url}: {e}")
    
    # If we found reports via requests, return them in proper structure
    if all_reports:
        return {
            "reports": all_reports,
            "website": {"title": "Scanned Site", "href": unique_domains[0] if unique_domains else known_website, "body": "Scanned via fallback"},
            "search_log": ["Fallback: Requests-based scan"]
        }
    
    # Fallback to homepage if no ESG site found and not in strict mode
    if not results.get("website") and official_homepage_url and not strict_mode:
        log(f"ESG specific site not found. Falling back to homepage: {official_homepage_url}")
        results["website"] = {
            "title": f"{company_name} Official Homepage",
            "href": official_homepage_url,
            "body": "Official company homepage (ESG section not explicitly found)."
        }
            
        # --- 2.5 Find Company Description ---
        try:
            desc_query = f"{company_name} company description summary"
            results["search_log"].append(f"Description Search: \"{desc_query}\"")
            desc_results = search_web(desc_query, max_results=1, ddgs_instance=ddgs)
            if desc_results:
                results['description'] = desc_results[0]['body']
        except Exception as e:
            log(f"Description search error: {e}")

        # --- 3. Report Discovery ---
        if not fetch_reports:
             log("Skipping report discovery (Step 1 complete).")
             return results
             
        print("Starting Report Discovery...")

        # PRIORITY STRATEGY: Scan The Official Hub (Verified Site)
        # We do this FIRST to ensure authoritative reports are top of list.
        if results.get("website"):
            log("Strategy Priority: Scanning ESG Website for Reports...")
            try:
                web_url = results["website"]["href"]
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                parsed_base = urlparse(web_url)
                primary_domain = parsed_base.netloc

                def normalize_href(base, href):
                    if not href:
                        return None
                    if href.startswith("mailto:") or href.startswith("javascript:"):
                        return None
                    if href.startswith("#"):
                        return None
                    if href.startswith("//"):
                        return f"{parsed_base.scheme}:{href}"
                    if href.startswith("http"):
                        return href
                    return urljoin(base, href)

                def collect_links(page_url, html_text):
                    soup = BeautifulSoup(html_text, 'html.parser')
                    pdf_candidates = []
                    hubs = []
                    for link in soup.find_all('a', href=True):
                        raw_href = link['href']
                        normalized = normalize_href(page_url, raw_href)
                        if not normalized:
                            continue

                        link_domain = urlparse(normalized).netloc
                        if link_domain and primary_domain and primary_domain not in link_domain:
                            continue

                        # --- Enhanced Name Extraction with Year Detection & Headers ---
                        import re
                        
                        def extract_year_bs(text):
                            years = re.findall(r'\b(202[0-9]|203[0])\b', str(text))
                            return years[0] if years else None
                        
                        def get_preceding_header_bs(element):
                            """Traverses backwards/up to find nearest header"""
                            try:
                                current = element.parent
                                for _ in range(4): # Limit depth
                                    if not current: break
                                    prev = current.find_previous_sibling()
                                    while prev:
                                        if prev.name and prev.name.startswith('h') and len(prev.name) == 2:
                                            return prev.get_text(strip=True)
                                        prev = prev.find_previous_sibling()
                                    current = current.parent
                            except:
                                return None
                            return None

                        def get_parent_context_bs(element):
                            """Get parent context for year/info extraction"""
                            parent = element.parent
                            for _ in range(2):  # Go up 2 levels
                                if parent and parent.name in ['div', 'p', 'li', 'td', 'section', 'article']:
                                    parent_text = parent.get_text(strip=True)
                                    if parent_text and len(parent_text) < 200:
                                        return parent_text
                                parent = parent.parent if parent else None
                            return ""
                        
                        visible_text = link.get_text(strip=True)
                        aria = link.get('aria-label', '').strip()
                        title_attr = link.get('title', '').strip()
                        
                        alt_text = ""
                        img_tag = link.find('img')
                        if img_tag:
                            alt_text = img_tag.get('alt', '').strip()

                        # Pick the most descriptive name
                        generic_terms = ["download", "pdf", "click here", "read more", "view", "report", "file", "link", "sustainability", "esg", "annual", "environmental", "social", "governance", "annual report", "sustainability report"]
                        
                        is_text_generic = not visible_text or visible_text.lower() in generic_terms or len(visible_text) < 4
                        
                        # 1. Base Name Selection
                        candidate_text = visible_text
                        if is_text_generic:
                            if aria: candidate_text = aria
                            elif title_attr: candidate_text = title_attr
                            elif alt_text: candidate_text = alt_text
                        elif aria and len(aria) > len(visible_text) + 5:
                            candidate_text = aria
                        
                        if not candidate_text: candidate_text = "Unknown Web Resource"

                        # 2. Contextual Enhancement Pipeline
                        # A. Check URL for Year
                        year_url = extract_year_bs(normalized)
                        if year_url and year_url not in candidate_text:
                            candidate_text = f"{candidate_text} ({year_url})"

                        # B. Check Preceding Header (if generic)
                        if len(candidate_text) < 30 or any(t in candidate_text.lower() for t in generic_terms):
                            header = get_preceding_header_bs(link)
                            if header and len(header) < 50:
                                header = re.sub(r'\s+', ' ', header).strip()
                                if header.lower() not in candidate_text.lower():
                                    candidate_text = f"{header} - {candidate_text}"

                        # C. Check Parent Content (last resort for year)
                        if not extract_year_bs(candidate_text):
                            context = get_parent_context_bs(link)
                            year = extract_year_bs(context)
                            if year and year not in candidate_text:
                                candidate_text = f"{candidate_text} ({year})"
                            
                        text = clean_title(candidate_text)
                        if not text: text = "Unknown Web Resource"

                        # BROADENED SCOPE: Check both PDF and HTML for relevance
                        is_pdf = normalized.lower().endswith('.pdf')
                        
                        # 1. Relevance Check (Keywords)
                        if is_report_link(text, normalized):
                            
                            # 2. Negative Filter
                            is_negative = False
                            neg_terms = ['policy', 'charter', 'code of conduct', 'guidelines', 'presentation']
                            for n in neg_terms:
                                if n in text.lower(): is_negative = True
                            
                            if not is_negative:
                                pdf_candidates.append({'href': normalized, 'title': text})
                            
                            # If it's a report link, we don't treat it as a hub to traverse?
                            # Actually, maybe we should still traverse if it's a hub-like page?
                            # But for now, let's capture it.
                            continue

                        if is_pdf:
                             # If it is a PDF but failed is_report_link (maybe missing keyword?), 
                             # we might still want it if we are desperate, but is_report_link is the gatekeeper.
                             pass

                        lower_text = text.lower()
                        hub_keywords = ['report', 'archive', 'download', 'library', 'sustainability', 'esg', 'impact', 'responsibility', 'csr']
                        if any(k in lower_text for k in hub_keywords):
                            hubs.append(normalized)

                    return pdf_candidates, hubs

                hubs_to_visit = [web_url]
                visited_hubs = set()
                found_on_main = 0
                max_hubs = 5

                while hubs_to_visit and len(visited_hubs) < max_hubs:
                    current_hub = hubs_to_visit.pop(0)
                    if current_hub in visited_hubs:
                        continue
                    visited_hubs.add(current_hub)

                    try:
                        log(f"  Scanning hub: {current_hub}")
                        resp = requests.get(current_hub, headers=headers, timeout=6)
                    except Exception as e:
                        log(f"  Hub request failed: {e}")
                        continue

                    if resp.status_code != 200:
                        continue

                    scan_candidates, hub_links_to_follow = collect_links(current_hub, resp.text)

                    if scan_candidates:
                        log(f"    Found {len(scan_candidates)} potential PDFs on {current_hub}")
                        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                            futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name): c for c in scan_candidates}
                            for future in concurrent.futures.as_completed(futures):
                                v = future.result()
                                if v and v['href'] not in [r['href'] for r in results['reports']]:
                                    v['source'] = "Official Site"
                                    results["reports"].append(v)
                                    found_on_main += 1

                    if found_on_main < 5:
                        for h in hub_links_to_follow:
                            if h not in visited_hubs and h not in hubs_to_visit and len(hubs_to_visit) < max_hubs:
                                hubs_to_visit.append(h)

            except Exception as e:
                print(f"Priority Strategy Error: {e}")
                
            # FALLBACK: If scraping failed (403) or found nothing, search THE SITE via Google/DDG.
            # This handles blocked sites (like CBRE) where we know the domain is correct.
            if len(results["reports"]) == 0 and results.get("website"):
                 log("Priority Strategy Fallback: Site is blocked or empty. Searching SITE via engine...")
                 try:
                     web_url = results["website"]["href"]
                     domain = urlparse(web_url).netloc
                     # Targeted search on the specific trusted domain
                     site_query = f"site:{domain} ESG sustainability report pdf"
                     log(f"  Fallback Site Search: {site_query}")
                     results["search_log"].append(f"Hub Fallback Search: \"{site_query}\"")
                     
                     site_results = search_web(site_query, max_results=6, ddgs_instance=ddgs)
                     
                     fallback_candidates = []
                     for res in site_results:
                         if is_report_link(res['title'], res['href']):
                             fallback_candidates.append(res)
                             
                     if fallback_candidates:
                         # Use ThreadPool for faster verification
                         with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                            futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name): c for c in fallback_candidates}
                            for future in concurrent.futures.as_completed(futures):
                                v = future.result()
                                if v:
                                    if v['href'] not in [r['href'] for r in results['reports']]:
                                        v['source'] = "Official Site Search" # Trusted source
                                        results["reports"].append(v)
                 except Exception as e:
                     log(f"Fallback Site Search Error: {e}")
 
        if strict_mode and results.get("website"):
            log("Strict Mode: Skipping external search strategies (B, C, D). Returning only direct findings.")
            
            # --- STRICT MODE ENHANCEMENT: Playwright Scraper ---
            # If standard scraper found nothing (e.g. 403 or JS site), use Playwright
            if len(results["reports"]) == 0:
                log("Strict Mode: Basic scraper returned 0 results. Attempting Deep Browser Scan (Playwright)...")
                try:
                    # Initialize Playwright Scraper (Headless)
                    from esg_scraper import ESGScraper
                    scraper = ESGScraper(headless=True)
                    
                    # Create a "dummy" config for this specific on-the-fly scan
                    temp_config = {
                        "url": results["website"]["href"],
                        "name": company_name,
                        "wait_until": "domcontentloaded",
                        "wait_for": "body" 
                    }
                    
                    # Use a synchronized call - we might need to handle the loop if already running?
                    # Streamlit runs in a thread, so sync_playwright should be fine.
                    # We reuse the logic from esg_scraper.py but we need a context.
                    # Actually ESGScraper.run uses sync_playwright() context manager. 
                    # We can't easily jump into the middle of it without refactoring esg_scraper OR just instantiating it.
                    # Let's use the .run() method but with just ONE site.
                    
                    scrape_results = scraper.run(sites_config=[temp_config])
                    
                    if scrape_results and company_name in scrape_results:
                         # It found something!
                         found_links = scrape_results[company_name]
                         
                         # Deduplicate and Limit
                         seen_urls = set(r['href'] for r in results["reports"])
                         count_added = 0
                         
                         # Filter out obvious duplicates and limit count
                         unique_found = []
                         for link in found_links:
                             if link['url'] not in seen_urls:
                                 unique_found.append(link)
                                 seen_urls.add(link['url'])
                         
                         # Iterate through unique found links (limited to top 20)
                         for link in unique_found[:20]:
                             pw_report = {
                                 "title": link['text'],
                                 "href": link['url'],
                                 "body": "Detected via Deep Browser Scan",
                                 "source": "Deep Browser Scan"
                             }
                             results["reports"].append(pw_report)
                             log(f"Playwright found report: {pw_report['title']}")
                             
                         log(f"Deep Scan: Added {len(unique_found[:20])} unique reports (filtered from {len(found_links)})")
                         
                except Exception as e:
                    log(f"Playwright Scan Error: {e}")

            return results
 
        # SECONDARY STRATEGY: Direct Search (Fill gaps)
        # Optimization: SKIP if we already have good results (> 3)
        if len(results["reports"]) < 4:
            report_queries = []
            if symbol:
                # Prioritize recent report years individually for clearer matches
                report_queries = [
                    f"{symbol} ESG report 2024",
                    f"{symbol} ESG report 2023"
                ]
                log("Strategy B: Direct Search by Symbol (year-by-year)")
            elif official_domain:
                report_queries = [f"site:{official_domain} ESG sustainability report pdf"]
            else:
                report_queries = [f"{company_name} ESG sustainability report pdf"]
            try:
                for report_query in report_queries:
                    if len(results["reports"]) >= 8:
                        break

                    log(f"Strategy B: Direct Search ({report_query})")
                    results["search_log"].append(f"Direct Report Search: \"{report_query}\"")
                    report_search_results = search_web(report_query, max_results=8, ddgs_instance=ddgs)

                    candidates = []
                    for res in report_search_results:
                        if is_report_link(res['title'], res['href']):
                             # Don't re-add what we already found
                             if res['href'] not in [r['href'] for r in results['reports']]:
                                candidates.append(res)

                    if candidates:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                            futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name): c for c in candidates}
                            for future in concurrent.futures.as_completed(futures):
                                verified_item = future.result()
                                if verified_item:
                                    if verified_item['href'] not in [r['href'] for r in results['reports']]:
                                        verified_item['source'] = "Web Search"
                                        results["reports"].append(verified_item)
                                        if len(results["reports"]) >= 8: break # Cap total
                    # Avoid hammering the API; respect one-query-at-a-time intent
                    time.sleep(0.3)
            except Exception as e:
                print(f"Strategy B error: {e}")

        # Strategy C: ResponsibilityReports.com
        if len(results["reports"]) < 4:  
             log("Strategy C: ResponsibilityReports.com Fallback")
             rr_query = f"site:responsibilityreports.com {company_name} ESG report"
             results["search_log"].append(f"ResponsibilityReports Search: \"{rr_query}\"")
             try:
                 rr_results = search_web(rr_query, max_results=3, ddgs_instance=ddgs)
                 for res in rr_results:
                     if res['href'] not in [r['href'] for r in results['reports']]:
                         results["reports"].append({
                             "title": f"ResponsibilityReports: {res['title']}",
                             "href": res['href'],
                             "body": "Sourced from ResponsibilityReports.com",
                             "source": "ResponsibilityReports"
                         })
                         if len(results["reports"]) >= 6: break
             except Exception as e:
                 print(f"Strategy C error: {e}")
        


        # --- 5. UN Global Compact (COP) ---
        if len(results["reports"]) < 8:
             ungc_query = f"site:unglobalcompact.org {company_name} Communication on Progress pdf"
             log(f"Searching UN Global Compact: {ungc_query}")
             results["search_log"].append(f"UNGC Search: \"{ungc_query}\"")
             try:
                 ungc_results = search_web(ungc_query, max_results=4, ddgs_instance=ddgs)
                 
                 ungc_candidates = []
                 for res in ungc_results:
                     if res['href'].lower().endswith('.pdf'):
                         ungc_candidates.append(res)
                 
                 # Verify UNGC
                 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                     futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name): c for c in ungc_candidates}
                     for future in concurrent.futures.as_completed(futures):
                         verified_item = future.result()
                         if verified_item:
                             if verified_item['href'] not in [r['href'] for r in results['reports']]:
                                 verified_item['source'] = "UN Global Compact"
                                 results["reports"].append(verified_item)
             except Exception as e:
                 log(f"UNGC search error: {e}")

    # --- Sorting: Newest First ---
    def extract_year(text):
        if not text: return 0
        import re
        
        # 1. Full Year (e.g. 2023, 2024)
        match = re.search(r'20[12][0-9]', text)
        if match:
            return int(match.group(0))
            
        # 2. Fiscal Year Short (e.g. FY23, FY24)
        match_fy = re.search(r'FY([2-9][0-9])', text, re.IGNORECASE)
        if match_fy:
            return 2000 + int(match_fy.group(1))
            
        return 0
    
    # Sort reports by year descending (newest on top)
    results["reports"].sort(key=lambda x: extract_year(x['title']), reverse=True)
    


    return results



# Function to load S&P 500 companies
@st.cache_data
def load_sp500_companies():
    # Attempt to load from MongoDB first
    if "mongo" in st.session_state:
        return st.session_state.mongo.get_all_companies()
    return []

# Load companies (This will now pull from Cloud)
companies_data = load_sp500_companies()
companies_options = []
if companies_data:
    companies_options = [f"{c['Security']} ({c['Symbol']})" for c in companies_data]


# --- Company Selection UI ---

if 'company_input' not in st.session_state:
    st.session_state.company_input = ""
if 'company_symbol' not in st.session_state:
    st.session_state.company_symbol = None

def update_input_from_select():
    selection = st.session_state.sp500_selector
    if selection and selection != "Select from S&P 500 (Optional)...":
        # Extract name part: "Apple Inc. (AAPL)" -> "Apple Inc."
        parts = selection.rsplit('(', 1)
        if len(parts) == 2:
            name = parts[0].strip()
            sym = parts[1].replace(')', '').strip()
            st.session_state.company_input = name
            st.session_state.company_symbol = sym

# --- Shared Helpers & Data ---
# Prepare Symbol Map for Auto-fill (Global Scope for both tabs)
sym_map = {}
if companies_data:
    for c in companies_data:
        sym_map[c['Security'].lower()] = c['Symbol']

def get_symbol_from_map(company_name):
    if not company_name: return None
    clean_name = company_name.strip().lower()
    # 1. Exact Match
    if clean_name in sym_map:
        return sym_map[clean_name]
    # 2. Substring Match (Strong)
    # Check if the input is a meaningful substring of a company name
    # e.g. "Disney" in "The Walt Disney Company"
    if len(clean_name) > 3:
        for name, sym in sym_map.items():
            if clean_name in name:
                return sym
                
    # 3. Fuzzy Match
    import difflib
    matches = difflib.get_close_matches(clean_name, sym_map.keys(), n=1, cutoff=0.6)
    if matches:
        return sym_map[matches[0]]
    return None

# --- SIDEBAR STATUS ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/leaf.png", width=60)
    st.title("ESG Agent v2.2 🌿")
    st.markdown("---")
    
    # DB Status
    if "mongo" in st.session_state and st.session_state.mongo.client:
        st.success("🟢 **Cloud DB Online**")
    else:
        st.error("🔴 **Cloud DB Offline**")
    st.markdown("---")

# --- TABS LAYOUT ---
tab_intro, tab_search, tab_db, tab_data = st.tabs(["🏠 Introduction", "🔍 Search & Analyze", "📂 User Saved Links", "⚙️ Data Manager"])

# ====================
# TAB 0: INTRODUCTION
# ====================
with tab_intro:
    st.markdown("""
    ### Welcome to the ESG Report AI Agent 🤖
    
    This powerful tool helps you discover, analyze, and manage Environmental, Social, and Governance (ESG) reports for companies, with a focus on S&P 500 data.
    
    ---
    
    #### 🚀 Key Features & How to Use
    
    **1. 🔍 Search & Analyze** (Main Tab)
    *   **Find Reports**: Enter a company name or select from the S&P 500 list to automatically find their official ESG/Sustainability Hub.
    *   **Deep Scan**: Use the "Deep Scan" feature to crawl verified hubs using advanced browser automation (Playwright) to uncover hidden PDF reports.
    *   **Direct Save**: Save any report directly to your permanent "User Saved Links" database.
    
    **2. 📂 User Saved Links**
    *   View, export, and manage all your saved findings.
    *   This is your permanent cloud database (synced to MongoDB).
    
    **3. ⚙️ Data Manager**
    *   View and edit the underlying S&P 500 dataset (`SP500ESGWebsites.csv`).
    *   Add new companies manually to the system.
    """)
    st.info("💡 **Tip:** Use the sidebar to verify your Cloud DB status!")

# ====================
# TAB 1: SEARCH
# ====================
with tab_search:
    st.subheader("Find ESG Reports")
    
    # ... (Search UI kept as is) ...

    # Display Logic (Check Session State)
    if 'esg_data' in st.session_state and st.session_state.esg_data:
        data = st.session_state.esg_data
        
        # ... (Export and Header UI kept as is) ...
        
        # Display Website
        # ... (Website UI kept as is) ...

        # ... (Reports Loop) ...
        # (We need to jump to the loop to inject the auto-fill logic)
        pass # Placeholder for diff context matching

# We need to target the TAB 2 block to remove the local sym_map and use the global one

# ... Using multi_replace might be cleaner but let's try to target specific blocks. 
# Actually, I will insert the sym_map definition BEFORE the tabs first.

    st.subheader("Find ESG Reports")
    
    # 1. Main Text Input (Free Text)
    company_name = st.text_input(
        "Enter Company Name (Type anything):", 
        key="company_input"
    )

    # 2. Helper Selectbox (S&P 500)
    companies_options_clean = [f"{c['Security']} ({c['Symbol']})" for c in companies_data]
    companies_options_clean.sort()
    companies_options_clean.insert(0, "Select from S&P 500 (Optional)...")

    st.selectbox(
        "Or pick from S&P 500 list to auto-fill:", 
        options=companies_options_clean, 
        key="sp500_selector",
        on_change=update_input_from_select
    )

    # 3. Search Button
    if st.button("Search 🔎", type="primary", use_container_width=True):
        if not company_name:
            st.warning("Please enter a company name.")
        else:
            # Clear previous results if new search
            if 'current_company' in st.session_state and st.session_state.current_company != company_name:
                st.session_state.esg_data = None
            
            st.session_state.current_company = company_name
            with st.spinner(f"Searching for '{company_name}'..."):
                # Pass explicit None if no symbol to avoid confusion
                sym = st.session_state.company_symbol if st.session_state.company_symbol else None
                data = search_esg_info(company_name, fetch_reports=True, symbol=sym)
                st.session_state.esg_data = data
                st.rerun()

    # Display Logic (Check Session State)
    if 'esg_data' in st.session_state and st.session_state.esg_data:
        data = st.session_state.esg_data
        
        # Export Button
        json_str = json.dumps(data, indent=4)
        st.download_button(
            label="Download Analysis (JSON)",
            data=json_str,
            file_name=f"{st.session_state.current_company}_esg_data.json",
            mime="application/json",
            key="download_json_1"
        )

        # Display Auto-Resolve Notice
        if data.get('resolved_from'):
            st.info(f"ℹ️ **Note**: Search defaulted to **{data['company']}** (S&P 500) based on your input '{data['resolved_from']}'. This ensures we find the official reports for the major public company.")

        # --- DEBUG LOGS ---
        if data.get("search_log"):
            with st.expander("🔍 Search Debug Logs (Terms Used)"):
                for log_item in data["search_log"]:
                    st.code(log_item, language="text")

        st.divider()
        
        if data.get('description'):
            st.caption("COMPANY PROFILE")
            st.info(data['description'])
        
        # Display Website
        # --- Verified Hub Section (New Editable Logic) ---
        st.subheader("🌐 ESG / Sustainability Website")
        web = data.get("website")
        
        col_web, col_edit = st.columns([0.85, 0.15])
        with col_web:
             if web:
                 # Check if it's a custom override for label
                 is_custom = mongo_db.get_company_hub(data.get('company',""))
                 prefix = "🛡️ **Custom Hub:**" if is_custom else "**🌐 Verified ESG Hub:**"
                 st.markdown(f"{prefix} [{web['title']}]({web['href']})")
                 if web.get('body'): st.caption(web['body'])
             else:
                 st.warning("⚠️ No Verified ESG Hub found for this company.")
                 
        with col_edit:
             btn_label = "✏️ Edit" if web else "➕ Add"
             if st.button(btn_label, key="top_edit_hub", help="Set or Correct the Verified Hub URL"):
                 st.session_state.show_hub_editor_top = True
        
        # Editor (Top)
        if st.session_state.get("show_hub_editor_top"):
            with st.expander("Configure Verified Site URL", expanded=True):
                st.info("Provide the correct direct URL to the company's ESG/Sustainability Hub or Reports page.")
                current_val = web['href'] if web else ""
                new_hub_url = st.text_input("Correct URL:", value=current_val, placeholder="https://www.company.com/sustainability", key="input_hub_top")
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("💾 Save & Re-Scan", type="primary", key="save_hub_top"):
                        if new_hub_url:
                            # Save to Company Hubs DB
                            c_name = st.session_state.get("current_company", data.get("company", "Unknown"))
                            success, msg = mongo_db.save_company_hub(c_name, new_hub_url)
                            if success:
                                st.success("✅ Hub Updated! Refreshing...")
                                st.session_state.show_hub_editor_top = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("Please enter a URL")
                with c2:
                     if st.button("Cancel", key="cancel_hub_top"):
                         st.session_state.show_hub_editor_top = False
                         st.rerun()

        # --- Saved Bookmarks (Manual) ---
        # Display these BELOW the verified hub as requested
        try:
            bk_company = data.get("company", st.session_state.current_company)
            # Filter from all saved links (in memory for now)
            all_bks = mongo_db.get_all_links("saved_links")
            saved_bks = [l for l in all_bks if l.get('company', '').lower() == bk_company.lower()]
            
            if saved_bks:
                st.markdown("---")
                st.caption("🔖 **Your Bookmarked Links:**")
                for i, row in enumerate(saved_bks):
                    lbl = row.get('Label') or row.get('Title') or "Link"
                    sym_badge = f"**[{row['symbol']}]** " if row.get('symbol') else ""
                    st.markdown(f"- {sym_badge}[{lbl}]({row['URL']})  `{row.get('Timestamp', '')[:10]}`")
        except Exception as e:
            print(f"Bookmark error: {e}")



        
        # --- STEP 2 TRIGGER (Deep Scan) ---
        # Offer deep scan if we have a verified site (Always visible now)
        if web:
            st.divider()
            
            # Dynamic Label
            btn_label = "📄 Fetch Reports & Data" if not data["reports"] else "🕵️ Deep Scan Verified Site"
            
            st.info(f"ℹ️ Verified Hub Found. click '{btn_label}' to crawl {web['title']} for all PDF links.")
            
            if st.button(btn_label, type="primary", use_container_width=True):
                 with st.spinner(f"Deep scanning {web['title']}..."):
                     try:
                         # ENABLE STRICT MODE: User wants ONLY internal links from this page
                         # SCREENSHOT CAPTURE
                         screenshot_path = None
                         try:
                             import os, uuid
                             from playwright.sync_api import sync_playwright
                             
                             screenshot_dir = "/tmp/esg_screenshots"
                             os.makedirs(screenshot_dir, exist_ok=True)
                             
                             safe_name = "".join(c for c in st.session_state.current_company if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:30]
                             screenshot_filename = f"{safe_name}_{uuid.uuid4().hex[:6]}.png"
                             screenshot_path = os.path.join(screenshot_dir, screenshot_filename)
                             
                             with sync_playwright() as p:
                                 browser = p.chromium.launch(headless=True)
                                 page = browser.new_page()
                                 page.goto(web['href'], timeout=30000, wait_until="domcontentloaded")
                                 page.wait_for_timeout(2000)
                                 page.screenshot(path=screenshot_path, full_page=False)
                                 browser.close()
                             # print(f"✅ Screenshot: {screenshot_path}")
                         except Exception as e:
                             print(f"⚠️ Screenshot failed: {e}")
                             screenshot_path = None

                         
                         # FIX: Pass the URL string
                         url_to_scan = web['href']
                         
                         new_data = search_esg_info(st.session_state.current_company, fetch_reports=True, known_website=url_to_scan, symbol=data.get('symbol'), strict_mode=True)
                         
                         # Defensive: Ensure new_data is a dict
                         if not isinstance(new_data, dict):
                             st.error(f"Internal error: Unexpected data type returned: {type(new_data)}")
                             st.stop()
                         
                         new_data['description'] = data.get('description') # Preserve description
                         new_data['screenshot'] = screenshot_path  # Add screenshot path
                         
                         st.session_state.esg_data = new_data
                         st.rerun()
                     
                     except Exception as e:
                         st.error(f"Deep scan failed: {e}")
                         import traceback
                         st.code(traceback.format_exc())
        else:
             st.info("No specific ESG website found.")
        
        st.divider()
        
        st.subheader("📄 Recent ESG Reports")
        web = data.get("website")
        
        # Screenshot logic
        import os
        if web and data.get('screenshot') and os.path.exists(data['screenshot']):
            st.markdown("**📸 Page Preview:**")
            st.image(data['screenshot'], use_column_width=True)
        


        
        if data["reports"]:
            for idx, report in enumerate(data["reports"]):
                # 2 Columns: Info, Save
                r_col, r_save = st.columns([0.7, 0.3])
                
                with r_col:
                    st.markdown(f"**{idx+1}. [{report['title']}]({report['href']})**")
                    # Display full URL
                    st.caption(f"🔗 {report['href']}")
                    # Use .get() for optional 'body' key
                    if report.get('body'):
                        st.caption(report['body'])
                
                with r_save:
                    # Label Input (Auto-fill with Title)
                    # Use a unique key based on index
                    # Default value is the report title
                    user_label = st.text_input("Label", value=report['title'], key=f"lbl_{idx}", placeholder="Label (e.g. 2024 Report)", label_visibility="collapsed")
                    
                    # Symbol Input
                    # 1. Try data source
                    def_sym = data.get('symbol', '')
                    # 2. Try global map if missing
                    if not def_sym:
                        # Try to resolve from company name
                        c_current = st.session_state.get('current_company', '')
                        resolved = get_symbol_from_map(c_current)
                        if resolved:
                            def_sym = resolved
                            
                    user_symbol = st.text_input("Symbol", value=def_sym if def_sym else "", key=f"sym_{idx}", placeholder="Stock Symbol (Optional)", label_visibility="collapsed")
                    
                    # Note Input
                    user_note = st.text_input("Note", value="", key=f"note_{idx}", placeholder="Note (Optional)", label_visibility="collapsed")
                    
                    # Save Button
                    if st.button("Save 💾", key=f"save_rep_{idx}", use_container_width=True):
                        # Determine Label
                        final_label = user_label if user_label else report['title']
                        final_desc = user_note if user_note else report.get('body', '')
                        final_sym = user_symbol

                        # Use search term as company name for better grouping
                        c_name = st.session_state.get('current_company', "Unknown")

                        # 1. Save to MongoDB (Verified Links Collection)
                        success, msg = mongo_db.save_link("verified_links", {
                            "company": c_name,
                            "title": report['title'],
                            "url": report['href'],
                            "label": final_label,
                            "description": final_desc,
                            "symbol": final_sym,
                            "source": "Search Result"
                        })
                        
                        
                        if success:
                            st.success(f"Saved to User Database as '{final_label}'")
                            # Force rerun to update sidebar immediately
                            time.sleep(0.5) # Slight delay to let user see success message
                            st.rerun()
                        else:
                            st.error(f"DB Error: {msg}")
                        
        else:
            st.info("No PDF reports loaded yet.")

    st.markdown("---")
    st.markdown("Build with ❤️ using Streamlit and DuckDuckGo Search")

# ==========================================


# ==========================================
# TAB 2: USER SAVED LINKS (MongoDB)
# ==========================================
with tab_db:
    st.header("📂 User Saved Links")
    st.markdown("All links saved to your permanent **MongoDB Atlas** database.")
    
    # --- MAINTENANCE / ADMIN ---
    with st.expander("🛠️ Admin & Maintenance"):
        st.caption("Manage internal data files and maps.")
        c_m1, c_m2 = st.columns([0.7, 0.3])
        with c_m1:
            st.info("ℹ️ **Company Map**: Based on `SP500ESGWebsites.csv`. If you edit the CSV file, rebuild the map here.")
        with c_m2:
            if st.button("🔄 Rebuild Company Map", help="Runs scripts/build_company_map.py"):
                with st.spinner("Rebuilding map from CSV..."):
                    try:
                        import subprocess
                        import sys
                        # Run the script
                        result = subprocess.run([sys.executable, "scripts/build_company_map.py"], capture_output=True, text=True)
                        if result.returncode == 0:
                            st.success("✅ Map Rebuilt Successfully!")
                            st.toast("Map updated! Reloading...")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"Failed: {result.stderr}")
                    except Exception as e:
                        st.error(f"Error running script: {e}")

    st.divider()

    # Get MongoDB stats
    v_links = mongo_db.get_all_links("verified_links")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Verified Links", len(v_links))
    with col2:
        unique_companies = len(set(l.get('company', '').lower() for l in v_links if l.get('company')))
        st.metric("Unique Companies", unique_companies)
    
    # --- Manual Entry Form ---
    with st.expander("➕ Add New Link Manually"):
        with st.form("manual_add_mongo_form"):
            st.caption("Add a link directly to MongoDB.")
            c_url = st.text_input("URL (Required)", placeholder="https://example.com/report.pdf")
            
            c1, c2, c3 = st.columns([0.4, 0.2, 0.4])
            with c1:
                c_company = st.text_input("Company Name", placeholder="e.g. Acme Corp")
            with c2:
                c_symbol = st.text_input("Symbol", placeholder="e.g. ACME")
            with c3:
                c_title = st.text_input("Title", placeholder="e.g. 2024 Sustainability Report")
                
            c_label = st.text_input("Label (Short)", placeholder="e.g. 2024 Report")
            c_desc = st.text_area("Description / Notes", height=60, placeholder="Optional details...")
            
            if st.form_submit_button("Save to MongoDB", use_container_width=True):
                if not c_url:
                    st.warning("⚠️ URL is required")
                else:
                    success, msg = mongo_db.save_link("verified_links", {
                        "company": c_company if c_company else "Manual Entry",
                        "title": c_title if c_title else "Saved Link",
                        "url": c_url,
                        "label": c_label if c_label else "Link",
                        "description": c_desc,
                        "symbol": c_symbol,
                        "source": "Manual"
                    })
                    if success:
                        st.success("✅ Saved to MongoDB!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Error: {msg}")
    
    st.divider()
    
    if len(v_links) > 0:
        # Convert to DataFrame for display
        df = pd.DataFrame(v_links)
        
        # Reorder columns
        desired_cols = ['timestamp', 'company', 'symbol', 'title', 'label', 'url', 'description', 'source']
        available_cols = [c for c in desired_cols if c in df.columns]
        df = df[available_cols]
        
        # Download button
        csv_export = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Export to CSV",
            data=csv_export,
            file_name=f"verified_links_export_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
        
        # Interactive table
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("URL"),
            },
            hide_index=True
        )
    else:
        st.info("ℹ️ Database is empty. Save links from search results to populate it!")


# ==========================================
# TAB 4: DATA MANAGER (MongoDB Companies)
# ==========================================
with tab_data:
    st.header("⚙️ Data manager")
    st.caption("Manage the master list of S&P 500 companies used for search suggestions. Synced to **MongoDB Atlas**.")

    # --- ADD NEW COMPANY FORM ---
    with st.expander("➕ Add New Company", expanded=False):
        st.caption("Add a new company to the global list.")
        with st.form("add_company_mongo_form"):
            c1, c2 = st.columns(2)
            new_ticker = c1.text_input("Ticker Symbol", placeholder="e.g. TSLA", max_chars=10).strip().upper()
            new_name = c2.text_input("Company Name", placeholder="e.g. Tesla Inc.").strip()
            new_website = st.text_input("Website URL", placeholder="e.g. https://www.tesla.com/impact")
            
            submitted = st.form_submit_button("Save to MongoDB")
            
            if submitted:
                if not new_ticker or not new_name:
                    st.error("❌ Ticker and Name are required.")
                else:
                    success, msg = mongo_db.save_company({
                        "Symbol": new_ticker,
                        "Security": new_name,
                        "Company Name": new_name,
                        "Website": new_website
                    })
                    if success:
                        st.success("✅ Added! Refreshing...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)

    st.divider()
    
    # --- DISPLAY TABLE ---
    if companies_data:
        df_co = pd.DataFrame(companies_data)
        
        # Filter Logic
        filter_q = st.text_input("🔎 Search Companies", placeholder="Type symbol or name...", key="dm_filter_mongo")
        if filter_q:
            mask = df_co.apply(lambda r: filter_q.lower() in str(r).lower(), axis=1)
            df_display = df_co[mask]
        else:
            df_display = df_co
            
        st.dataframe(
            df_display, 
            use_container_width=True,
            hide_index=True 
        )
        st.caption(f"Showing {len(df_display)} companies.")
    else:
        st.warning("⚠️ No companies found in MongoDB.")
        if st.button("🚀 Run Initial Migration (CSV -> Mongo)"):
             with st.spinner("Migrating data... this may take 30s..."):
                 try:
                     import sys
                     import subprocess
                     # We reuse the script we made
                     res = subprocess.run([sys.executable, "scripts/migrate_csv_to_mongo.py"], capture_output=True, text=True)
                     if "Migration Complete" in res.stdout or "Migration Complete" in res.stderr:
                         st.success("✅ Migration Done! Reloading...")
                         time.sleep(2)
                         st.rerun()
                     else:
                         st.error(f"Migration output: {res.stdout} / {res.stderr}")
                 except Exception as e:
                     st.error(f"Migration failed: {e}")

