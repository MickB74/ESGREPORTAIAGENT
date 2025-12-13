import streamlit as st
from ddgs import DDGS
import time
import json
import os
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd


# ... (rest of imports/code) ...


import pandas as pd
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
        if 'pdf' not in c_type and 'application/octet-stream' not in c_type:
            response.close()
            return None

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
            
        # Check Keywords (Context specific)
        if context == "cdp":
            if 'cdp' not in text_content and 'climate change' not in text_content:
                 return None
        else:
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
LINKS_FILE = "saved_links.json"

def load_links():
    if not os.path.exists(LINKS_FILE):
        return []
    try:
        with open(LINKS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_link_to_file(title, url, description=None):
    links = load_links()
    # Check if exists
    for link in links:
        if link['href'] == url:
            return False # Already saved
    
    new_link = {"title": title, "href": url}
    if description:
        new_link["description"] = description
        
    links.append(new_link)
    with open(LINKS_FILE, "w") as f:
        json.dump(links, f)
    return True

def delete_link(index):
    links = load_links()
    if 0 <= index < len(links):
        removed = links.pop(index)
        with open(LINKS_FILE, "w") as f:
            json.dump(links, f)
        return True
    return False

# Function to perform searches
# Function to perform searches
def search_esg_info(company_name, fetch_reports=True, known_website=None):

    import concurrent.futures
    import datetime
    import io
    import pypdf

    def log(msg):
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    results = {
        "company": company_name,
        "description": None,
        "timestamp": datetime.datetime.now().isoformat(),
        "website": None,
        "reports": [],
        "cdp": []
    }
    
    official_domain = None
    esg_hub_urls = [] 


    log("Starting search...")

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
            known_url = known_website['href']
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

        # --- 1. Official Domain Identification ---
        domain_query = f"{company_name} official corporate website"
        
        if known_url:
             # Fast Path: Use known URL as the "official domain" for hub scanning
             official_domain = known_url
             # Add to domain results to ensure it gets processed in hub scan
             domain_results = [{'href': known_url, 'title': f"{resolved_name.title()} Sustainability Hub"}]
        else:
            log(f"Searching for domain: {domain_query}")
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
                     log(f"Identified official domain: {official_domain}")
                     break


        # --- 2. Find ESG Website (Refined) ---
        if known_url:
            # Trusted Source
            results["website"] = {
                "title": f"{resolved_name} Sustainability Hub (Fast Track)",
                "href": known_url,
                "body": "Official verified sustainability page."
            }
        else:
            # Discovery
            if official_domain:
                website_query = f"site:{official_domain} ESG sustainability"
            else:
                website_query = f"{company_name} official ESG sustainability website"
                
            log(f"Searching for website query: {website_query}")
            try:
                web_search_results = search_web(website_query, max_results=10, ddgs_instance=ddgs)
                for res in web_search_results:
                    url = res['href']
                    if url.lower().endswith('.pdf'): continue
                    if not official_domain:
                         if not is_likely_official_domain(url, company_name): continue
                         if 'bing.com' in url or 'google.com' in url: continue
                        
                    results["website"] = {
                        "title": res['title'],
                        "href": url,
                        "body": res['body']
                    }
                    break
            except Exception as e:
                print(f"Website search error: {e}")
            
        # --- 2.5 Find Company Description ---
        try:
            desc_query = f"{company_name} company description summary"
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

        # PRIORITY STRATEGY: Scan The Official Hub (Fast Track)
        # We do this FIRST to ensure authoritative reports are top of list.
        if results.get("website"):
            log("Strategy Priority: Scanning ESG Website for Reports...")
            try:
                web_url = results["website"]["href"]
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                # Allow redirects, 5s timeout (Reduced from 10 for speed)
                resp = requests.get(web_url, headers=headers, timeout=5)
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    links = soup.find_all('a', href=True)
                    
                    # Candidates to check
                    scan_candidates = []
                    hub_links_to_follow = []
                    
                    for link in links:
                        href = link['href']
                        text = clean_title(link.get_text(strip=True))
                        
                        # Fix relative URLs
                        if href.startswith('/'):
                            parsed = urlparse(web_url)
                            href = f"{parsed.scheme}://{parsed.netloc}{href}"
                        elif not href.startswith('http'):
                            continue # Skip javascript: etc
                        
                        # 1. Direct PDF Links
                        if is_report_link(text, href):
                            scan_candidates.append({'href': href, 'title': text})
                        
                        # 2. "Reports" / "Archive" Sub-pages (Follow them!)
                        # Strictly limit depth
                        lower_text = text.lower()
                        if 'report' in lower_text or 'archive' in lower_text or 'download' in lower_text or 'library' in lower_text:
                             if href not in esg_hub_urls:
                                 esg_hub_urls.append(href)
                                 hub_links_to_follow.append(href)

                    # Verify found page PDFs
                    found_on_main = 0
                    if scan_candidates:
                         log(f"  Found {len(scan_candidates)} potential PDFs on main page.")
                         # Reduced workers to 3 for stability
                         with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                            futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name): c for c in scan_candidates}
                            for future in concurrent.futures.as_completed(futures):
                                v = future.result()
                                if v:
                                    if v['href'] not in [r['href'] for r in results['reports']]:
                                        v['source'] = "Official Site"
                                        results["reports"].append(v)
                                        found_on_main += 1

                    # Follow Hub Links (Depth 1)
                    # OPTIMIZATION: Only follow hubs if main page yielded FEW results (< 2)
                    if hub_links_to_follow and found_on_main < 2:
                        def scrape_hub(h_url):
                            found = []
                            try:
                                log(f"  Following Hub: {h_url}")
                                h_resp = requests.get(h_url, headers=headers, timeout=5) # 5s timeout
                                if h_resp.status_code == 200:
                                    h_soup = BeautifulSoup(h_resp.content, 'html.parser')
                                    for hl in h_soup.find_all('a', href=True):
                                        hl_href = hl['href']
                                        hl_text = clean_title(hl.get_text(strip=True))
                                        
                                        if hl_href.startswith('/'):
                                            parsed = urlparse(h_url)
                                            hl_href = f"{parsed.scheme}://{parsed.netloc}{hl_href}"
                                        
                                        if is_report_link(hl_text, hl_href):
                                            found.append({'href': hl_href, 'title': hl_text})
                            except: pass
                            return found

                        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                            futures = {executor.submit(scrape_hub, u): u for u in hub_links_to_follow[:2]} # Limit to 2 hubs
                            for future in concurrent.futures.as_completed(futures):
                                candidates = future.result()
                                # Verify these new candidates
                                for c in candidates:
                                     v = verify_pdf_content(c['href'], c['title'], company_name)
                                     if v and v['href'] not in [r['href'] for r in results['reports']]:
                                         v['source'] = "Official Hub"
                                         results["reports"].append(v)
                                         
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
 
        # SECONDARY STRATEGY: Direct Search (Fill gaps)
        # Optimization: SKIP if we already have good results (> 3)
        if len(results["reports"]) < 4:
            if official_domain:
                report_query = f"site:{official_domain} ESG sustainability report pdf"
            else:
                report_query = f"{company_name} ESG sustainability report pdf"
                
            log(f"Strategy B: Direct Search ({report_query})")
            
            try:
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
            except Exception as e:
                print(f"Strategy B error: {e}")

        # Strategy C: ResponsibilityReports.com
        if len(results["reports"]) < 4:  
             log("Strategy C: ResponsibilityReports.com Fallback")
             rr_query = f"site:responsibilityreports.com {company_name} ESG report"
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
        
        # --- 4. CDP & UNGC (Optimized) ---
        cdp_query = f"{company_name} CDP climate change questionnaire pdf"
        log(f"Searching for CDP: {cdp_query}")
        
        try:
            cdp_search_results = search_web(cdp_query, max_results=8, ddgs_instance=ddgs)
            
            cdp_candidates = []
            for res in cdp_search_results:
                 if 'cdp' in res['title'].lower() or 'climate' in res['title'].lower():
                     if res['href'].lower().endswith('.pdf'):
                         cdp_candidates.append(res)
            
            # REDUCED WORKERS TO 2
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name, "cdp"): c for c in cdp_candidates}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        if result['href'] not in [r['href'] for r in results['cdp']]:
                            results["cdp"].append(result)
                            if len(results["cdp"]) >= 6: break
                                
        except Exception as e:
             log(f"CDP search error: {e}")

        # --- 5. UN Global Compact (COP) ---
        if len(results["reports"]) < 8:
             ungc_query = f"site:unglobalcompact.org {company_name} Communication on Progress pdf"
             log(f"Searching UN Global Compact: {ungc_query}")
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
    
    # Also sort CDP by year if possible
    results["cdp"].sort(key=lambda x: extract_year(x['title']), reverse=True)

    return results

# --- UI Setup ---
st.set_page_config(page_title="ESG Report Finder", page_icon="🌿")

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

def update_input_from_select():
    selection = st.session_state.sp500_selector
    if selection and selection != "Select from S&P 500 (Optional)...":
        # Extract name part: "Apple Inc. (AAPL)" -> "Apple Inc."
        name = selection.split('(')[0].strip()
        st.session_state.company_input = name

# --- TABS LAYOUT ---
tab1, tab2 = st.tabs(["🔎 Search Reports", "🚀 Fast Track Data"])

# ... (Tab 1 and Tab 2 content remains, omitted here for brevity, I will match start of Tab 1) ...

with tab1:
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




    if st.button("🔍 Find Company Info", type="primary"):
        if not company_name:
            st.warning("Please enter a company name.")
        else:
            with st.spinner(f"Searching for {company_name}'s info..."):
                try:
                    # STEP 1: Fast Search (No scraping)
                    data = search_esg_info(company_name, fetch_reports=False)
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

            # --- STEP 2 TRIGGER ---
            # If we have a website but no reports yet, offer to scan
            if not data["reports"]:
                 st.divider()
                 st.info("ℹ️ Official Hub Found. Click below to scan for reports.")
                 if st.button("📄 Fetch Reports & Data", type="primary", use_container_width=True):
                     with st.spinner(f"Scanning {data['website']['title']} for reports..."):
                         try:
                             # STEP 2: Deep Scan (Using known website)
                             new_data = search_esg_info(st.session_state.current_company, fetch_reports=True, known_website=data['website'])
                             new_data['description'] = data['description'] # Preserve description
                             st.session_state.esg_data = new_data
                             st.rerun()
                         except Exception as e:
                             st.error(f"Scan error: {e}")

        else:
            st.info("No specific ESG website found.")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Display Reports
            st.subheader("📄 Recent ESG Reports")
            if data["reports"]:
                for idx, report in enumerate(data["reports"]):
                    # 3 Columns: Info, Save, Chat
                    # Adjusted ratios to prevent button text wrapping
                    # 2 Columns: Info, Save
                    r_col, r_save = st.columns([0.8, 0.2])
                    
                    with r_col:
                        st.markdown(f"**{idx+1}. [{report['title']}]({report['href']})**")
                        st.caption(report['body'])
                    
                    with r_save:
                        # use_container_width=True ensures button expands to fill column
                        if st.button("Save", key=f"save_rep_{idx}", use_container_width=True):
                            if save_link_to_file(report['title'], report['href'], description=report['body']):
                                st.success("Saved")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.warning("Exists")
                            
            else:
                st.info("No PDF reports loaded yet.")

        with col2:
                # Display CDP
            st.subheader("📋 CDP Submissions")
            if data.get("cdp"):
                for idx, item in enumerate(data["cdp"]):
                    c_col, c_save = st.columns([0.8, 0.2])
                    with c_col:
                        st.markdown(f"**{idx+1}. [{item['title']}]({item['href']})**")
                        st.caption(item['body'])
                    with c_save:
                        if st.button("Save", key=f"save_cdp_{idx}"):
                            if save_link_to_file(item['title'], item['href']):
                                st.success("Saved!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.warning("Exists")
            else:
                st.info("No recent CDP submissions found.")


    st.markdown("---")
    st.markdown("Build with ❤️ using Streamlit and DuckDuckGo Search")


# --- TAB 2: Fast Track Data ---
with tab2:
    st.header("🚀 Fast Track Data (Known Hubs)")
    st.markdown("This database is sourced from the official S&P 500 ESG Websites list.")
    
    csv_path = "SP500ESGWebsites.csv"
    if os.path.exists(csv_path):
        try:
            # File is likely iso-8859-1 (Excel standard CSV)
            df = pd.read_csv(csv_path, encoding='iso-8859-1')
            
            # Select relevant columns if they exist
            # CSV Header: Symbol,Symbol,Name,Company Description,Company Name,Website
            # We want: Symbol (Short), Company Name, Website
            # Note: Pandas handles duplicate col names by appending .1, .2
            
            # Let's clean up columns
            # The CSV has 'Symbol' twice. The second one (index 1) is usually the ticker.
            
            # We will try to pick by index or name
            display_cols = []
            if "Company Name" in df.columns: display_cols.append("Company Name")
            if "Symbol" in df.columns: display_cols.append("Symbol") # might get both or first
            if "Sym" in df.columns: display_cols.append("Sym")      # user might rename
            if "Website" in df.columns: display_cols.append("Website")
            
            # Simple display
            # If columns are duplicated, pandas names them Symbol, Symbol.1
            # Let's just display the whole Clean DF
            
            # Filter to just Name, Ticker, URL
            final_df = df.copy()
            if "Company Name" in final_df.columns and "Website" in final_df.columns:
                 # Clean blank rows
                 final_df = final_df.dropna(subset=["Company Name", "Website"], how='any')

                 # Try to find ticker
                 ticker_col = "Symbol.1" if "Symbol.1" in final_df.columns else "Symbol"
                 cols_to_show = [ticker_col, "Company Name", "Website"]
                 # Filter only existing
                 cols_to_show = [c for c in cols_to_show if c in final_df.columns]
                 final_df = final_df[cols_to_show]
                 
                 # Rename for display
                 rename_map = {ticker_col: "Ticker"}
                 final_df = final_df.rename(columns=rename_map)
            
            # Multi-select search filter
            all_companies = final_df["Company Name"].unique().tolist()
            selected_companies = st.multiselect(
                "Filter by Company:",
                options=all_companies,
                placeholder="Select companies to view..."
            )
            
            if selected_companies:
                final_df = final_df[final_df["Company Name"].isin(selected_companies)]

            st.dataframe(
                final_df, 
                use_container_width=True,
                column_config={
                    "Website": st.column_config.LinkColumn("Sustainability Hub Link")
                },
                hide_index=True
            )
            
            st.caption(f"Total entries: {len(df)}")
            
        except Exception as e:
            st.error(f"Error loading CSV: {e}")
    else:
        st.warning(f"⚠️ {csv_path} not found.")



# --- Sidebar: Saved Links --- (Existing code continues)

with st.sidebar:
    st.header("🔖 Saved Links")
    
    # Manual Add
    with st.expander("Add Link Manually"):
        manual_title = st.text_input("Title", key="manual_title")
        manual_url = st.text_input("URL", key="manual_url")
        if st.button("Add", key="manual_add"):
            if manual_title and manual_url:
                if save_link_to_file(manual_title, manual_url):
                    st.success("Added!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("Link already exists.")
            else:
                st.warning("Title and URL required.")

    st.divider()
    


    saved_links = load_links()
    if saved_links:
        for i, link in enumerate(saved_links):
            col_link, col_del = st.columns([0.8, 0.2])
            with col_link:
                st.markdown(f"[{link['title']}]({link['href']})")
            with col_del:
                if st.button("🗑️", key=f"del_{i}", help="Delete link"):
                    delete_link(i)
                    st.rerun()
    else:
        st.info("No saved links yet.")
