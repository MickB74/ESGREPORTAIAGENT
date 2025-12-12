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
        
        # Stream request to check size first
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5, stream=True)
        except requests.exceptions.Timeout:
            return None
        except Exception:
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
        
        # Content Check
        try:
            f = io.BytesIO(response.content)
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
            "title": title,
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

def save_link_to_file(title, url):
    links = load_links()
    # Check if exists
    for link in links:
        if link['href'] == url:
            return False # Already saved
    links.append({"title": title, "href": url})
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
def search_esg_info(company_name):
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


        # --- 0.5 Load Company Map (Knwon Hubs) ---
        known_url = None
        try:
            with open("company_map.json", "r") as f:
                cmap = json.load(f)
                if company_name.lower() in cmap:
                    known_url = cmap[company_name.lower()]
                    log(f"Found known sustainability hub: {known_url}")
        except:
             pass

        # --- 1. Official Domain Identification ---
        domain_query = f"{company_name} official corporate website"
        
        if known_url:
             # Fast Path: Use known URL as the "official domain" for hub scanning
             official_domain = known_url
             # Add to domain results to ensure it gets processed in hub scan
             domain_results = [{'href': known_url, 'title': f"{company_name} Sustainability Hub"}]
        else:
            log(f"Searching for domain: {domain_query}")
            try:
                domain_results = list(ddgs.text(domain_query, max_results=5, region='us-en'))
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


        # --- 2. Find ESG Website ---
        if official_domain:
            website_query = f"site:{official_domain} ESG sustainability"
        else:
            website_query = f"{company_name} official ESG sustainability website"
            
        log(f"Searching for website query: {website_query}")
        
        try:
            web_search_results = list(ddgs.text(website_query, max_results=10, region='us-en'))
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
            desc_results = list(ddgs.text(desc_query, max_results=1, region='us-en'))
            if desc_results:
                results['description'] = desc_results[0]['body']
        except Exception as e:
            log(f"Description search error: {e}")

        # --- 3. Report Discovery Strategy ---
        print("Starting Report Discovery...")

        # Strategy A: Direct Search (Verified)
        if official_domain:
            report_query = f"site:{official_domain} ESG sustainability report pdf"
        else:
            report_query = f"{company_name} ESG sustainability report pdf"
            
        log(f"Strategy A: Direct Search ({report_query})")
        
        try:
            report_search_results = list(ddgs.text(report_query, max_results=15, region='us-en')) # Fetch more to filter
            
            # Filter first by title/url
            candidates = []
            for res in report_search_results:
                if is_report_link(res['title'], res['href']):
                     candidates.append(res)

            # Verify content concurrently
            # REDUCED WORKERS TO 3
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name): c for c in candidates}
                for future in concurrent.futures.as_completed(futures):
                    verified_item = future.result()
                    if verified_item:
                        if verified_item['href'] not in [r['href'] for r in results['reports']]:
                            verified_item['source'] = "Direct Search"
                            results["reports"].append(verified_item)
                            if len(results["reports"]) >= 6: break
        except Exception as e:
            print(f"Strategy A error: {e}")

        # Strategy B: "Nearby" Hub Discovery (Verified)
        if len(results["reports"]) < 6 and results.get("website"):
            log("Strategy B: Scanning ESG Website for Report Hubs...")
            try:
                web_url = results["website"]["href"]
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = requests.get(web_url, headers=headers, timeout=5)
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    links = soup.find_all('a', href=True)
                    
                    # Hub Candidates
                    hub_candidates = []
                    
                    # 1. Scrape current page 
                    page_candidates = []
                    for link in links:
                        href = link['href']
                        text = clean_title(link.get_text(strip=True))
                        if href.startswith('/'):
                            parsed = urlparse(web_url)
                            href = f"{parsed.scheme}://{parsed.netloc}{href}"
                        
                        if is_report_link(text, href):
                            page_candidates.append({'href': href, 'title': text})
                        
                        # Hub detection
                        if len(results["reports"]) < 6:
                             if 'reports' in text.lower() or 'archive' in text.lower() or 'downloads' in text.lower():
                                 if href not in esg_hub_urls:
                                     esg_hub_urls.append(href)
                                     hub_candidates.append(href)

                    # Verify page candidates
                    # REDUCED WORKERS TO 2
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                        futures = {executor.submit(verify_pdf_content, c['href'], c['title'], company_name): c for c in page_candidates}
                        for future in concurrent.futures.as_completed(futures):
                            verified_item = future.result()
                            if verified_item:
                                if verified_item['href'] not in [r['href'] for r in results['reports']]:
                                    verified_item['source'] = "ESG Page Scrape"
                                    results["reports"].append(verified_item)
                                    if len(results["reports"]) >= 6: break

                    # 2. Scrape Hubs (if needed)
                    if len(results["reports"]) < 6 and hub_candidates:
                         def scrape_and_verify_hub(hub_url):
                            found = []
                            try:
                                log(f"  Visiting Hub: {hub_url}")
                                hub_resp = requests.get(hub_url, headers=headers, timeout=5)
                                if hub_resp.status_code == 200:
                                    hub_soup = BeautifulSoup(hub_resp.content, 'html.parser')
                                    hub_links = hub_soup.find_all('a', href=True)
                                    
                                    h_candidates = []
                                    for h_link in hub_links:
                                        h_href = h_link['href']
                                        h_text = clean_title(h_link.get_text(strip=True))
                                        
                                        if h_href.startswith('/'):
                                            parsed = urlparse(hub_url)
                                            h_href = f"{parsed.scheme}://{parsed.netloc}{h_href}"
                                        
                                        if is_report_link(h_text, h_href):
                                            h_candidates.append({'href': h_href, 'title': h_text})
                                    
                                    # Verify inner candidates
                                    for hc in h_candidates:
                                        v = verify_pdf_content(hc['href'], hc['title'], company_name)
                                        if v:
                                            v['source'] = "Hub Scrape"
                                            found.append(v)
                            except:
                                pass
                            return found

                         # REDUCED WORKERS TO 2
                         with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                            futures = {executor.submit(scrape_and_verify_hub, url): url for url in hub_candidates[:3]}
                            for future in concurrent.futures.as_completed(futures):
                                hub_results = future.result()
                                for item in hub_results:
                                     if item['href'] not in [r['href'] for r in results['reports']]:
                                          results["reports"].append(item)
                                          if len(results["reports"]) >= 8: break
                                if len(results["reports"]) >= 6: break

            except Exception as e:
                print(f"Strategy B error: {e}")

        # Strategy C: ResponsibilityReports.com (Already trusted, but could verify)
        if len(results["reports"]) < 6:  
             log("Strategy C: ResponsibilityReports.com Fallback")
             rr_query = f"site:responsibilityreports.com {company_name} ESG report"
             try:
                 rr_results = list(ddgs.text(rr_query, max_results=3, region='us-en'))
                 
                 # Just take top result if it looks good, usually trustworthy
                 for res in rr_results:
                     if res['href'] not in [r['href'] for r in results['reports']]:
                         # Optional: Verify this too if we want to be super strict
                         # But RR is usually correct.
                         results["reports"].append({
                             "title": f"ResponsibilityReports: {res['title']}",
                             "href": res['href'],
                             "body": "Sourced from ResponsibilityReports.com",
                             "source": "ResponsibilityReports"
                         })
                         if len(results["reports"]) >= 6: break
             except Exception as e:
                 print(f"Strategy C error: {e}")
        
        # --- 4. CDP Submission (Verified) ---
        cdp_query = f"{company_name} CDP climate change questionnaire pdf"
        log(f"Searching for CDP: {cdp_query}")
        
        try:
            cdp_search_results = list(ddgs.text(cdp_query, max_results=8, region='us-en'))
            
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
                 ungc_results = list(ddgs.text(ungc_query, max_results=4, region='us-en'))
                 
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

# --- TAB 1: Search Interface ---
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

    if st.button("Find Reports", type="primary"):
        if not company_name:
            st.warning("Please enter a company name.")
        else:
            with st.spinner(f"Searching for {company_name}'s ESG data..."):
                try:
                    # Run search
                    data = search_esg_info(company_name)
                    # Store in session state
                    st.session_state.esg_data = data
                    st.session_state.current_company = company_name
                    st.success("Search complete!")
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
                    if save_link_to_file(data['website']['title'], data['website']['href']):
                        st.success("Saved!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("Exists")
        else:
            st.info("No specific ESG website found.")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Display Reports
            st.subheader("📄 Recent ESG Reports")
            if data["reports"]:
                for idx, report in enumerate(data["reports"]):
                    r_col, r_save = st.columns([0.8, 0.2])
                    with r_col:
                        st.markdown(f"**{idx+1}. [{report['title']}]({report['href']})**")
                        st.caption(report['body'])
                    with r_save:
                        if st.button("Save", key=f"save_rep_{idx}"):
                            if save_link_to_file(report['title'], report['href']):
                                st.success("Saved!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.warning("Exists")
            else:
                st.info("No PDF reports found immediately.")

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
                 # Try to find ticker
                 ticker_col = "Symbol.1" if "Symbol.1" in final_df.columns else "Symbol"
                 cols_to_show = [ticker_col, "Company Name", "Website"]
                 # Filter only existing
                 cols_to_show = [c for c in cols_to_show if c in final_df.columns]
                 final_df = final_df[cols_to_show]
                 
                 # Rename for display
                 rename_map = {ticker_col: "Ticker"}
                 final_df = final_df.rename(columns=rename_map)

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


# --- Sidebar: Saved Links ---
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
