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
            url_lower = url.lower()
            text_lower = text.lower()
            
            if '.pdf' not in url_lower:
                return False
                
            # NEGATIVE KEYWORDS (Strict Filtering)
            negative_terms = [
                'policy', 'guideline', 'charter', 'code of conduct', 'code-of-conduct',
                'presentation', 'earnings', 'fact sheet', 'factsheet', 'release', 
                'summary', 'highlight', 'index', 'appendix', 'proxy', 'letter'
            ]
            if any(term in text_lower or term in url_lower for term in negative_terms):
                # Allow exceptions if "annual report" or "sustainability report" is explicitly in title
                if "annual report" not in text_lower and "sustainability report" not in text_lower:
                    return False

            # POSITIVE KEYWORDS
            # Must have at least one from Group A AND one from Group B
            group_a = ['esg', 'sustainability', 'climate', 'integrated', 'impact', 'csr', 'annual', 'responsibility', 'environment']
            group_b = ['report', 'review', 'year', '2020', '2021', '2022', '2023', '2024', '2025']
            
            has_a = any(term in text_lower for term in group_a) or any(term in url_lower for term in group_a)
            has_b = any(term in text_lower for term in group_b) or any(term in url_lower for term in group_b)
            
            return has_a and has_b

        def verify_pdf_content(url, title, context="report"):
            """
            Downloads PDF and verifies:
            1. File size > 50KB
            2. Company name on Page 1-3
            3. "Report" keywords on Page 1-3
            """
            try:
                log(f"  Verifying ({context}): {url}")
                
                # Stream request to check size first
                response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, stream=True)
                
                # Size Check
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) < 50000: # 50KB
                    log(f"  [SKIP] File too small ({content_length} bytes): {url}")
                    response.close()
                    return None
                
                # Content Check
                f = io.BytesIO(response.content)
                reader = pypdf.PdfReader(f)
                
                if len(reader.pages) == 0:
                    return None
                    
                # Check first 3 pages
                pages_to_check = min(3, len(reader.pages))
                text_content = ""
                for i in range(pages_to_check):
                    text_content += reader.pages[i].extract_text().lower() + " "
                
                # Check Company Name
                company_first_word = company_name.split()[0].lower()
                if company_first_word not in text_content:
                    log(f"  [SKIP] Company name '{company_first_word}' not found in first {pages_to_check} pages: {url}")
                    return None
                    
                # Check Keywords (Context specific)
                if context == "cdp":
                    if 'cdp' not in text_content and 'climate change' not in text_content:
                         log(f"  [SKIP] CDP keywords not found: {url}")
                         return None
                else:
                    report_keywords = ['report', 'sustainability', 'esg', 'annual', 'review', 'fiscal', 'summary']
                    if not any(k in text_content for k in report_keywords):
                        log(f"  [SKIP] Report keywords not found: {url}")
                        return None
                
                log(f"  [MATCH] Verified: {url}")
                return {
                    "title": title,
                    "href": url,
                    "body": "Verified PDF Report"
                }

            except Exception as e:
                log(f"  Verification failed for {url}: {e}")
                return None

        # --- 1. Official Domain Identification ---
        domain_query = f"{company_name} official corporate website"
        log(f"Searching for domain: {domain_query}")
        
        try:
            domain_results = list(ddgs.text(domain_query, max_results=5, region='us-en'))
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
        except Exception as e:
            log(f"Domain identification error: {e}")

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
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(verify_pdf_content, c['href'], c['title']): c for c in candidates}
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
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        futures = {executor.submit(verify_pdf_content, c['href'], c['title']): c for c in page_candidates}
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
                                        v = verify_pdf_content(hc['href'], hc['title'])
                                        if v:
                                            v['source'] = "Hub Scrape"
                                            found.append(v)
                            except:
                                pass
                            return found

                         with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
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

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(verify_pdf_content, c['href'], c['title'], "cdp"): c for c in cdp_candidates}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        if result['href'] not in [r['href'] for r in results['cdp']]:
                            results["cdp"].append(result)
                            if len(results["cdp"]) >= 6: break
                                
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
