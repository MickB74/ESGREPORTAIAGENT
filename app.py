import streamlit as st
from ddgs import DDGS
import time
import json
import os
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd
import difflib
import db_handler

# --- App Configuration (Must be first!) ---
st.set_page_config(page_title="ESG Report Finder", page_icon="🌿")

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

def save_link_to_file(title, url, description=None):
    # Use Session State as Source of Truth
    links = st.session_state['saved_links']
    
    # Check if exists and update
    for link in links:
        if link['href'] == url:
            link['title'] = title
            if description:
                link['description'] = description
            save_links_to_disk() # Sync
            return True # Updated existing
    
    new_link = {"title": title, "href": url}
    if description:
        new_link["description"] = description
        
    links.append(new_link)
    save_links_to_disk() # Sync
    return True

def delete_link(index):
    if 0 <= index < len(st.session_state['saved_links']):
        st.session_state['saved_links'].pop(index)
        save_links_to_disk() # Sync
        return True
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

    import db_handler # Import handler


    
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
            try:
                with open("company_map.json", "r") as f:
                    cmap = json.load(f)
                
                # 1. Exact Match
                if company_name.lower() in cmap:
                    known_url = cmap[company_name.lower()]
                    resolved_name = company_name
                    log(f"Found known sustainability hub (exact): {known_url}")
                else:
                    # 2. Fuzzy Match (Handle typos like 'appel' -> 'apple')
                    # Lowered cutoff to 0.6 to catch 'appel' -> 'apple' (ratio is 0.8 but better safe)
                    matches = difflib.get_close_matches(company_name.lower(), cmap.keys(), n=1, cutoff=0.6)
                    if matches:
                        resolved_name = matches[0]
                        known_url = cmap[resolved_name]
                        log(f"Found known sustainability hub (fuzzy '{resolved_name}'): {known_url}")
                        
            except Exception as e:
                 log(f"Map lookup error: {e}")

        # --- [MOVED] Check Google Sheets Database ---
        if resolved_name:
            st.markdown("---")
            res_col1, res_col2 = st.columns([0.8, 0.2])
            with res_col1:
                st.subheader(f"Results for: {resolved_name}")
            
            # Load from CSV
            try:
                # Use resolved_name which is now defined
                saved_csv_links, csv_error = db_handler.get_links_by_company(resolved_name)
                
                if csv_error: 
                    st.warning(f"CSV Error: {csv_error}")
                    
                if saved_csv_links:
                    with st.expander(f"📂 Saved Verified Links ({len(saved_csv_links)})", expanded=True):
                        for i, row in enumerate(saved_csv_links):
                            display_text = row.get('Label') if row.get('Label') else row.get('Title')
                            st.markdown(f"**{i+1}. [{display_text}]({row['URL']})**")
                            st.caption(f"📅 Saved: {row.get('Timestamp')} | 🏷️ {row.get('Title')}")
            except Exception as e:
                print(f"CSV error: {e}")

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
                         best_link = scrape_results[company_name]
                         # Convert to our format
                         pw_report = {
                             "title": best_link['text'],
                             "href": best_link['url'],
                             "body": "Detected via Deep Browser Scan",
                             "source": "Deep Browser Scan"
                         }
                         # Verify it? esg_scraper already checks keywords/PDF extension
                         # Let's optionally verify if we want to be safe, but 403 might block verification too!
                         # If the browser saw it, the link is likely valid.
                         results["reports"].append(pw_report)
                         log(f"Playwright found report: {pw_report['title']}")
                         
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
    try:
        with open('sp500_companies.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Load companies
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

# --- TABS LAYOUT ---
# --- TABS LAYOUT ---
tab_search, tab_saved, tab_db = st.tabs(["🔍 Search & Analyze", "🔖 My Saved Links", "📂 Verified Database"])

# ====================
# TAB 1: SEARCH
# ====================
with tab_search:
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
            mime="application/json"
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
        st.subheader("🌐 ESG / Sustainability Website")
        if data["website"]:
            col_web, col_save_web = st.columns([0.8, 0.2])
            with col_web:
                st.markdown(f"**[{data['website']['title']}]({data['website']['href']})**")
                st.caption(data['website']['body'])
            with col_save_web:
                if st.button("Save", key="save_web"):
                    if save_link_to_file(data['website']['title'], data['website']['href'], description=data['website']['body']):
                        st.success("Saved!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("Exists")


            # --- STEP 2 TRIGGER (Deep Scan) ---
            # Offer deep scan if we have a verified site (Always visible now)
            st.divider()
            
            # Dynamic Label: "Fetch" if empty, "Deep Scan" if we have some but want more
            btn_label = "📄 Fetch Reports & Data" if not data["reports"] else "🕵️ Deep Scan Verified Site"
            
            st.info(f"ℹ️ Verified Hub Found. click '{btn_label}' to crawl {data['website']['title']} for all PDF links.")
            
            if st.button(btn_label, type="primary", use_container_width=True):
                 with st.spinner(f"Deep scanning {data['website']['title']}..."):
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
                                 page.goto(data['website']['href'], timeout=30000, wait_until="domcontentloaded")
                                 page.wait_for_timeout(2000)
                                 page.screenshot(path=screenshot_path, full_page=False)
                                 browser.close()
                             print(f"✅ Screenshot: {screenshot_path}")
                         except Exception as e:
                             print(f"⚠️ Screenshot failed: {e}")
                             screenshot_path = None

                         
                         # FIX: Pass the URL string, not the dict object
                         url_to_scan = data['website']['href'] if isinstance(data.get('website'), dict) else data.get('website')
                         if not url_to_scan: url_to_scan = data.get('href') # Fallback
                         
                         new_data = search_esg_info(st.session_state.current_company, fetch_reports=True, known_website=url_to_scan, symbol=data.get('symbol'), strict_mode=True)
                         
                         # Defensive: Ensure new_data is a dict
                         if not isinstance(new_data, dict):
                             st.error(f"Internal error: Unexpected data type returned: {type(new_data)}")
                             st.error(f"Data content: {str(new_data)[:200]}")
                             st.stop()
                         
                         new_data['description'] = data.get('description') # Preserve description
                         new_data['screenshot'] = screenshot_path  # Add screenshot path (always None for now)

                          
                         # Merge with existing reports if we had some? 
                         # Actually search_esg_info returns a fresh list. 
                         # If we want to KEEP existing reports that were NOT found in deep scan (e.g. from Google),
                         # we might need merge logic. But usually Deep Scan is authoritative.
                         # Let's just trust the fresh scan for now, or maybe append?
                         # For now, replacing is cleaner to avoid duplicates, as deep scan *should* find everything on the site.
                         
                         st.session_state.esg_data = new_data
                         st.rerun()




    if st.button("🔍 Find Company Info", type="primary"):
        if not company_name:
            st.warning("Please enter a company name.")
        else:
            with st.spinner(f"Searching for {company_name}'s info..."):
                try:
                    # Resolve symbol if not set
                    search_symbol = st.session_state.get('company_symbol')
                    # If the name doesn't match the selected symbol's name (user edited text), try to re-resolve
                    # Simple check: if we have a list, try to find the match
                    if not search_symbol:
                        # Try to find in companies_data
                        c_lower = company_name.lower()
                        for c in companies_data:
                            if c['Security'].lower() == c_lower or c['Symbol'].lower() == c_lower:
                                search_symbol = c['Symbol']
                                break
                    
                    # STEP 1: Fast Search (No scraping)
                    data = search_esg_info(company_name, fetch_reports=False, symbol=search_symbol)
                    # Store in session state
                    st.session_state.esg_data = data
                    st.session_state.current_company = company_name
                    st.success("Company found!")
                except Exception as e:
                    st.error(f"An error occurred during search: {e}")

    # Display Logic (Check Session State)
    if 'esg_data' in st.session_state and st.session_state.esg_data:
        data = st.session_state.esg_data
        
        # Export Button
        json_str = json.dumps(data, indent=4)
        st.download_button(
            label="Download Analysis (JSON)",
            data=json_str,
            file_name=f"{st.session_state.current_company}_esg_data.json",
            mime="application/json"
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
        st.subheader("🌐 ESG / Sustainability Website")
        if data["website"]:
            col_web, col_save_web = st.columns([0.8, 0.2])
            with col_web:
                st.markdown(f"**[{data['website']['title']}]({data['website']['href']})**")
                st.caption(data['website']['body'])
            with col_save_web:
                if st.button("Save", key="save_web"):
                    if save_link_to_file(data['website']['title'], data['website']['href'], description=data['website']['body']):
                        st.success("Saved!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("Exists")


            # --- STEP 2 TRIGGER (Deep Scan) ---
            # Offer deep scan if we have a verified site (Always visible now)
            st.divider()
            
            # Dynamic Label: "Fetch" if empty, "Deep Scan" if we have some but want more
            btn_label = "📄 Fetch Reports & Data" if not data["reports"] else "🕵️ Deep Scan Verified Site"
            
            st.info(f"ℹ️ Verified Hub Found. click '{btn_label}' to crawl {data['website']['title']} for all PDF links.")
            
            if st.button(btn_label, type="primary", use_container_width=True):
                 with st.spinner(f"Deep scanning {data['website']['title']}..."):
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
                                 page.goto(data['website']['href'], timeout=30000, wait_until="domcontentloaded")
                                 page.wait_for_timeout(2000)
                                 page.screenshot(path=screenshot_path, full_page=False)
                                 browser.close()
                             print(f"✅ Screenshot: {screenshot_path}")
                         except Exception as e:
                             print(f"⚠️ Screenshot failed: {e}")
                             screenshot_path = None

                         
                         # FIX: Pass the URL string, not the dict object
                         url_to_scan = data['website']['href'] if isinstance(data.get('website'), dict) else data.get('website')
                         if not url_to_scan: url_to_scan = data.get('href') # Fallback
                         
                         new_data = search_esg_info(st.session_state.current_company, fetch_reports=True, known_website=url_to_scan, symbol=data.get('symbol'), strict_mode=True)
                         
                         # Defensive: Ensure new_data is a dict
                         if not isinstance(new_data, dict):
                             st.error(f"Internal error: Unexpected data type returned: {type(new_data)}")
                             st.error(f"Data content: {str(new_data)[:200]}")
                             st.stop()
                         
                         new_data['description'] = data.get('description') # Preserve description
                         new_data['screenshot'] = screenshot_path  # Add screenshot path (always None for now)

                          
                         # Merge with existing reports if we had some? 
                         # Actually search_esg_info returns a fresh list. 
                         # If we want to KEEP existing reports that were NOT found in deep scan (e.g. from Google),
                         # we might need merge logic. But usually Deep Scan is authoritative.
                         # Let's just trust the fresh scan for now, or maybe append?
                         # For now, replacing is cleaner to avoid duplicates, as deep scan *should* find everything on the site.
                         
                         st.session_state.esg_data = new_data
                         st.rerun()
                     except Exception as e:
                         import traceback
                         st.error(f"Scan error: {e}")
                         st.error(f"Error type: {type(e).__name__}")
                         with st.expander("Full Error Details"):
                             st.code(traceback.format_exc())

        else:
            st.info("No specific ESG website found.")
        
        st.divider()
        
        st.subheader("📄 Recent ESG Reports")
        web = data.get("website")
        if web:
            st.markdown(f"**🌐 Verified ESG Hub:** [{web['title']}]({web['href']})")
            st.caption(web.get('body', ''))
            
            # Display screenshot if available
            import os
            if data.get('screenshot') and os.path.exists(data['screenshot']):
                st.markdown("**📸 Page Preview:**")
                st.image(data['screenshot'], use_column_width=True)

        
        if data["reports"]:
            for idx, report in enumerate(data["reports"]):
                # 2 Columns: Info, Save
                r_col, r_save = st.columns([0.85, 0.15])
                
                with r_col:
                    st.markdown(f"**{idx+1}. [{report['title']}]({report['href']})**")
                    # Display full URL
                    st.caption(f"🔗 {report['href']}")
                    # Use .get() for optional 'body' key
                    if report.get('body'):
                        st.caption(report['body'])
                
                with r_save:
                    # Label Input
                    user_label = st.text_input("Label", value="", key=f"lbl_{idx}", placeholder="e.g. 2024 Report", label_visibility="collapsed")
                    
                    # Save Button
                    if st.button("Save 💾", key=f"save_rep_{idx}", use_container_width=True):
                        # Determine Label
                        final_label = user_label if user_label else report['title']

                        # 1. Save to Local (Sidebar) - Legacy
                        save_link_to_file(final_label, report['href'], description=report.get('body', ''))
                        
                        # 2. Save to CSV
                        success, msg = db_handler.save_link(
                            company=data['website']['title'] if data.get('website') else "Unknown",
                            title=report['title'],
                            url=report['href'],
                            label=final_label,
                            description=report.get('body', '')
                        )
                        
                        
                        if success:
                            st.success(f"Saved to CSV as '{final_label}'")
                            # Force rerun to update sidebar immediately
                            time.sleep(0.5) # Slight delay to let user see success message
                            st.rerun()
                        else:
                            st.error(f"CSV Error: {msg}")
                        
        else:
            st.info("No PDF reports loaded yet.")

    st.markdown("---")
    st.markdown("Build with ❤️ using Streamlit and DuckDuckGo Search")

# ==========================================
# TAB 2: MY SAVED LINKS (Sidebar Bookmarks)
# ==========================================
with tab_saved:
    st.header("🔖 My Saved Links")
    st.markdown("Quick bookmarks from your current session (stored in `saved_links.json`).")
    
    saved_links = st.session_state.get('saved_links', [])
    
    if len(saved_links) > 0:
        st.metric("Total Bookmarks", len(saved_links))
        st.divider()
        
        # Display as cards for better visual presentation
        for i, link in enumerate(saved_links):
            with st.container():
                col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
                
                with col1:
                    st.markdown(f"### [{link['title']}]({link['href']})")
                    if link.get('description'):
                        st.caption(link['description'])
                
                with col2:
                    if st.button("💾 Save to DB", key=f"save_db_{i}", help="Save to permanent database"):
                        success, msg = db_handler.save_link(
                            company="Bookmarked",
                            title=link['title'],
                            url=link['href'],
                            label=link['title'],
                            description=link.get('description', '')
                        )
                        if success:
                            st.toast("✅ Saved to database!")
                        else:
                            st.error(msg)
                
                with col3:
                    if st.button("🗑️ Delete", key=f"del_saved_{i}", help="Remove bookmark"):
                        delete_link(i)
                        st.rerun()
                
                st.divider()
        
        # Bulk actions
        st.subheader("Bulk Actions")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("💾 Save All to Database", use_container_width=True):
                success_count = 0
                for link in saved_links:
                    success, _ = db_handler.save_link(
                        company="Bookmarked",
                        title=link['title'],
                        url=link['href'],
                        label=link['title'],
                        description=link.get('description', '')
                    )
                    if success:
                        success_count += 1
                st.success(f"✅ Saved {success_count}/{len(saved_links)} links to database!")
        
        with col_b:
            if st.button("🗑️ Clear All Bookmarks", use_container_width=True):
                st.session_state['saved_links'] = []
                save_links_to_disk()
                st.rerun()
    else:
        st.info("ℹ️ No bookmarks yet. Use the sidebar 'Add Link Manually' or save links from search results!")

# ==========================================
# TAB 3: VERIFIED DATABASE
# ==========================================
with tab_db:
    st.header("📂 Verified Link Database")
    st.markdown("All links saved to your permanent SQLite database.")
    
    # Get database stats
    stats = db_handler.get_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Links", stats.get('total_links', 0))
    with col2:
        st.metric("Unique Companies", stats.get('unique_companies', 0))
    
    st.divider()
    
    # Load all links
    links, error = db_handler.get_all_links()
    
    if error:
        st.error(f"Error loading database: {error}")
    elif len(links) > 0:
        # Convert to DataFrame for display
        import pandas as pd
        df = pd.DataFrame(links)
        
        # Reorder columns for better display
        column_order = ['id', 'timestamp', 'company', 'label', 'title', 'url', 'description']
        df = df[column_order]
        
        # Download button
        csv_export = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Export to CSV",
            data=csv_export,
            file_name=f"verified_links_export_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
        
        # Interactive table
        st.data_editor(
            df,
            disabled=['id', 'timestamp'],  # Make ID and timestamp read-only
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "id": "ID",
                "timestamp": st.column_config.DatetimeColumn(
                    "Saved At",
                    format="D MMM YYYY, h:mm a"
                ),
                "company": "Company",
                "label": "Label",
                "title": "Title",
                "url": st.column_config.LinkColumn("URL"),
                "description": st.column_config.TextColumn(
                    "Description",
                    width="large"
                )
            },
            hide_index=True,
        )
        
        st.caption(f"Showing {len(links)} records from {db_handler.DB_FILE}")
    else:
        st.info("ℹ️ Database is empty. Save links from search results to populate it!")

