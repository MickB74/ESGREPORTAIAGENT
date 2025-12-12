import streamlit as st
from ddgs import DDGS
import time
import json
import os
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

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

# Function to perform searches
def search_esg_info(company_name):
    import concurrent.futures
    import datetime

    def log(msg):
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    results = {
        "website": None,
        "reports": [],
        "cdp": []
    }
    
    official_domain = None
    esg_hub_urls = [] # Potential "Report Hubs"

    log("Starting search...")

    with DDGS() as ddgs:
        # 1. Official Domain Identification
        domain_query = f"{company_name} official corporate website"
        log(f"Searching for domain: {domain_query}")
        
        try:
            domain_results = list(ddgs.text(domain_query, max_results=5, region='us-en'))
            for res in domain_results:
                url = res['href']
                title = res['title']
                
                if url.lower().endswith('.pdf'):
                    continue
                
                if not is_likely_official_domain(url, company_name):
                    continue
                
                domain_str = urlparse(url).netloc.lower()
                company_parts = company_name.lower().split()
                
                is_domain_match = False
                for part in company_parts:
                    if len(part) > 2 and part in domain_str:
                        is_domain_match = True
                        break
                
                if not is_domain_match:
                     log(f"Skipping {domain_str} - name mismatch")
                     continue

                if company_name.split()[0].lower() in title.lower():
                     official_domain = domain_str
                     log(f"Identified official domain: {official_domain}")
                     break
        except Exception as e:
            log(f"Domain identification error: {e}")

        # 2. Find ESG Website
        if official_domain:
            website_query = f"site:{official_domain} ESG sustainability"
        else:
            website_query = f"{company_name} official ESG sustainability website"
            
        log(f"Searching for website query: {website_query}")
        
        try:
            web_search_results = list(ddgs.text(website_query, max_results=10, region='us-en'))
            for res in web_search_results:
                url = res['href']
                if url.lower().endswith('.pdf'):
                    continue
                if not official_domain:
                     if not is_likely_official_domain(url, company_name):
                        continue
                     if 'bing.com' in url or 'google.com' in url:
                        continue
                    
                results["website"] = {
                    "title": res['title'],
                    "href": url,
                    "body": res['body']
                }
                break
        except Exception as e:
            print(f"Website search error: {e}")
            
        # 3. Report Discovery Strategy
        print("Starting Report Discovery...")
        
        # Helper to check if link is report-like
        def is_report_link(text, url):
            url_lower = url.lower()
            text_lower = text.lower()
            if '.pdf' not in url_lower:
                return False
            # Check for keywords
            if 'esg' in text_lower or 'sustainability' in text_lower or 'climate' in text_lower or 'annual' in text_lower:
                 if 'report' in text_lower:
                     return True
            # Check for year patterns near 'report'
            if 'report' in url_lower and ('202' in url_lower or '202' in text_lower):
                return True
            return False

        # Strategy A: Direct Search (Existing)
        if official_domain:
            report_query = f"site:{official_domain} ESG sustainability report pdf"
        else:
            report_query = f"{company_name} ESG sustainability report pdf"
            
        log(f"Strategy A: Direct Search ({report_query})")
        
        try:
            report_search_results = list(ddgs.text(report_query, max_results=10, region='us-en'))
            for res in report_search_results:
                url = res['href']
                title = res['title']
                if '.pdf' in url.lower():
                     if url not in [r['href'] for r in results['reports']]:
                        results["reports"].append({
                            "title": title,
                            "href": url,
                            "body": res['body'],
                            "source": "Direct Search"
                        })
                if len(results["reports"]) >= 6:
                    break
        except Exception as e:
            print(f"Strategy A error: {e}")

        # Strategy B: "Nearby" Hub Discovery (New) - OPTIMIZED
        if len(results["reports"]) < 6 and results.get("website"):
            log("Strategy B: Scanning ESG Website for Report Hubs...")
            try:
                web_url = results["website"]["href"]
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = requests.get(web_url, headers=headers, timeout=5) # Reduced timeout
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    links = soup.find_all('a', href=True)
                    
                    # 1. Scrape current page for PDFs first
                    for link in links:
                        href = link['href']
                        text = clean_title(link.get_text(strip=True))
                        if href.startswith('/'):
                            parsed = urlparse(web_url)
                            href = f"{parsed.scheme}://{parsed.netloc}{href}"
                        
                        if is_report_link(text, href):
                            if href not in [r['href'] for r in results['reports']]:
                                results["reports"].append({
                                    "title": text,
                                    "href": href,
                                    "body": "Found on ESG Homepage",
                                    "source": "ESG Page Scrape"
                                })

                    # 2. Look for "Report Hub" sub-pages if we still need reports
                    if len(results["reports"]) < 6:
                        hub_candidates = []
                        for link in links:
                            text = link.get_text(strip=True).lower()
                            href = link['href']
                            # Keywords for hubs
                            if 'reports' in text or 'archive' in text or 'downloads' in text or 'library' in text or 'performance' in text:
                                if href.startswith('/'):
                                    parsed = urlparse(web_url)
                                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                                
                                # Avoid external links for hubs usually
                                if official_domain and official_domain not in href and 'http' in href:
                                    continue
                                    
                                if href not in esg_hub_urls:
                                    esg_hub_urls.append(href)
                                    hub_candidates.append(href)
                        
                        # Use concurrency for hubs
                        def scrape_hub(hub_url):
                            found = []
                            try:
                                print(f"  Visiting Hub: {hub_url}")
                                hub_resp = requests.get(hub_url, headers=headers, timeout=5)
                                if hub_resp.status_code == 200:
                                    hub_soup = BeautifulSoup(hub_resp.content, 'html.parser')
                                    hub_links = hub_soup.find_all('a', href=True)
                                    for h_link in hub_links:
                                        h_href = h_link['href']
                                        h_text = clean_title(h_link.get_text(strip=True))
                                        
                                        if h_href.startswith('/'):
                                            parsed = urlparse(hub_url)
                                            h_href = f"{parsed.scheme}://{parsed.netloc}{h_href}"
                                        
                                        if is_report_link(h_text, h_href):
                                            found.append({
                                                "title": h_text if h_text else "Report (Hub)",
                                                "href": h_href,
                                                "body": f"Found on {hub_url}",
                                                "source": "Hub Scrape"
                                            })
                            except:
                                pass
                            return found

                        if hub_candidates:
                            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                                # Visit top 3 likely hubs concurrently
                                futures = {executor.submit(scrape_hub, url): url for url in hub_candidates[:3]}
                                for future in concurrent.futures.as_completed(futures):
                                    hub_results = future.result()
                                    for item in hub_results:
                                         if item['href'] not in [r['href'] for r in results['reports']]:
                                              results["reports"].append(item)
                                              if len(results["reports"]) >= 8: break # internal limit
                                    if len(results["reports"]) >= 6: break # main limit

            except Exception as e:
                print(f"Strategy B error: {e}")

        # Strategy C: ResponsibilityReports.com Fallback (New) - OPTIMIZED
        if len(results["reports"]) < 6:  
             log("Strategy C: ResponsibilityReports.com Fallback")
             rr_query = f"site:responsibilityreports.com {company_name} ESG report"
             try:
                 rr_results = list(ddgs.text(rr_query, max_results=3, region='us-en'))
                 
                 def scrape_rr(rr_url):
                     found = []
                     if 'responsibilityreports.com' in rr_url:
                         # Optimization: If the search result IS a PDF, don't scrape it, just take it!
                         if rr_url.lower().endswith('.pdf'):
                             log(f"  RR Result is direct PDF: {rr_url}")
                             found.append({
                                 "title": f"{company_name} Report (ResponsibilityReports)",
                                 "href": rr_url,
                                 "body": "Sourced from responsibilityreports.com",
                                 "source": "ResponsibilityReports"
                             })
                             return found

                         try:
                             log(f"  Checking RR Page: {rr_url}")
                             # Use stream=True to avoid downloading large files if we hit a PDF by accident
                             rr_resp = requests.get(rr_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5, stream=True)
                             
                             # Check content type if possible, or just proceed if HTML
                             content_type = rr_resp.headers.get('Content-Type', '').lower()
                             if 'pdf' in content_type:
                                 # It's a PDF we didn't catch by extension?
                                 log(f"  RR Page is actually PDF (Content-Type): {rr_url}")
                                 rr_resp.close() # Close connection
                                 return found 

                             # Only Read content if text/html
                             if rr_resp.status_code == 200:
                                 # Limit content read to avoid huge pages? usually fine for HTML.
                                 # RR pages are small.
                                 html_content = rr_resp.content # This reads everything. stream=True needs explicit read or .content access.
                                 rr_soup = BeautifulSoup(html_content, 'html.parser')
                                 rr_links = rr_soup.find_all('a', href=True)
                                 for rrl in rr_links:
                                     rrh = rrl['href']
                                     rrt = clean_title(rrl.get_text(strip=True))
                                     
                                     if rrh.startswith('/'):
                                         rrh = f"https://www.responsibilityreports.com{rrh}"
                                     
                                     if '.pdf' in rrh.lower() or 'click here to download' in rrt.lower():
                                         found.append({
                                             "title": f"{company_name} Report (ResponsibilityReports)",
                                             "href": rrh,
                                             "body": "Sourced from responsibilityreports.com",
                                             "source": "ResponsibilityReports"
                                         })
                         except Exception as e:
                             log(f"  RR Scrape error: {e}")
                     return found

                 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                      futures = {executor.submit(scrape_rr, res['href']): res for res in rr_results}
                      for future in concurrent.futures.as_completed(futures):
                          rr_items = future.result()
                          for item in rr_items:
                              if item['href'] not in [r['href'] for r in results['reports']]:
                                   results["reports"].append(item)
                                   if len(results["reports"]) >= 6: break

             except Exception as e:
                 print(f"Strategy C error: {e}")
        
        # 4. CDP Submission
        cdp_query = f"{company_name} CDP climate change questionnaire pdf"
        log(f"Searching for CDP: {cdp_query}")
        
        try:
            cdp_results = list(ddgs.text(cdp_query, max_results=6, region='us-en'))
            
            def verify_cdp_pdf(res):
                url = res['href']
                title = res['title']
                
                # Basic filter: must look like a CDP report
                if 'cdp' not in title.lower() and 'climate change' not in title.lower() and 'questionnaire' not in title.lower():
                    return None
                
                if not url.lower().endswith('.pdf'):
                    return None

                try:
                    import pypdf
                    import io
                    
                    log(f"  Verifying CDP PDF: {url}")
                    # Download PDF content (with timeout)
                    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    if response.status_code == 200:
                        f = io.BytesIO(response.content)
                        reader = pypdf.PdfReader(f)
                        if len(reader.pages) > 0:
                            first_page_text = reader.pages[0].extract_text().lower()
                            # Check if company name (or first part of it) is in the first page
                            company_first_word = company_name.split()[0].lower()
                            
                            if company_first_word in first_page_text:
                                log(f"  [MATCH] Found company name '{company_first_word}' in PDF: {url}")
                                return {
                                    "title": title,
                                    "href": url,
                                    "body": res['body']
                                }
                            else:
                                log(f"  [SKIP] Company name '{company_first_word}' NOT found on Page 1: {url}")
                except Exception as e:
                    log(f"  PDF Verification failed for {url}: {e}")
                
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(verify_cdp_pdf, res): res for res in cdp_results}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        if result['href'] not in [r['href'] for r in results['cdp']]:
                            results["cdp"].append(result)
                            if len(results["cdp"]) >= 6:
                                break
                                
        except Exception as e:
             log(f"CDP search error: {e}")

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

# Sort alphabetically
companies_options.sort()

# Add special options
CUSTOM_OPTION = "Enter Custom Company Name..."
SELECT_OPTION = "Select a company..."
companies_options.insert(0, CUSTOM_OPTION)
companies_options.insert(0, SELECT_OPTION)

st.title("🌿 ESG Report Finder Agent")
st.markdown("Enter a company name below to find their recent ESG reports, sustainability website, and CDP submissions.")

# Selection UI
selected_option = st.selectbox("Choose a company from S&P 500 or enter custom:", companies_options)

company_name = ""

if selected_option == CUSTOM_OPTION:
    company_name = st.text_input("Enter Company Name", placeholder="e.g., Apple, Microsoft, ExxonMobil")
elif selected_option != SELECT_OPTION:
    # Extract company name from "Name (Ticker)" format
    # We'll just use the full string for search as it usually works well, 
    # or we can split it. Let's try using the name part.
    # Format: "3M (MMM)" -> split by " (" -> take first part
    company_name = selected_option.split(" (")[0]

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
    
    st.divider()
    
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
