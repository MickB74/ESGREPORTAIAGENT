import streamlit as st
from ddgs import DDGS
import time
import json
import os
from urllib.parse import urlparse

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
        'motleyfool.com', 'seekingalpha.com', 'barrons.com'
    ]
    if any(b in domain for b in block_list):
        return False
    return True

# Function to perform searches
def search_esg_info(company_name):
    results = {
        "website": None,
        "reports": []
    }
    
    official_domain = None

    with DDGS() as ddgs:
        # 1. First, try to identify the official company domain
        # The user wants "a website from that company"
        domain_query = f"{company_name} official corporate website"
        print(f"Searching for domain: {domain_query}")
        
        try:
            domain_results = list(ddgs.text(domain_query, max_results=5, region='us-en'))
            for res in domain_results:
                url = res['href']
                title = res['title']
                
                # Check 1: Is it a PDF? Skip.
                if url.lower().endswith('.pdf'):
                    continue
                
                # Check 2: Heuristic blocklist
                if not is_likely_official_domain(url, company_name):
                    continue
                
                # Check 3: Title match (very loose) - skip if company name probably not in title
                # This helps avoid random unrelated sites if the search engine gets confused
                # We normalize simple check
                if company_name.split()[0].lower() in title.lower():
                     official_domain = urlparse(url).netloc
                     print(f"Identified official domain: {official_domain}")
                     break
        except Exception as e:
            print(f"Domain identification error: {e}")

        # 2. Find ESG Website
        # Strategy: If we have a domain, use site:domain. Else, use general search.
        if official_domain:
            website_query = f"site:{official_domain} ESG sustainability"
        else:
            website_query = f"{company_name} official ESG sustainability website"
            
        print(f"Searching for website query: {website_query}")
        
        try:
            web_search_results = list(ddgs.text(website_query, max_results=10, region='us-en'))
            # Filter results for the best candidate
            for res in web_search_results:
                url = res['href']
                
                # Prefer non-PDF for website
                if url.lower().endswith('.pdf'):
                    continue
                
                # If we didn't have a domain before, apply blocklist now
                if not official_domain and not is_likely_official_domain(url, company_name):
                    continue
                    
                results["website"] = {
                    "title": res['title'],
                    "href": url,
                    "body": res['body']
                }
                break
        except Exception as e:
            print(f"Website search error: {e}")

        # Small delay to be polite
        time.sleep(1)

        # 3. Find last 2 ESG reports (PDFs)
        # Using site:domain if available is usually cleaner for reports too
        if official_domain:
            report_query = f"site:{official_domain} ESG sustainability report pdf"
        else:
            report_query = f"{company_name} ESG sustainability report pdf"
            
        print(f"Searching for reports: {report_query}")
        
        try:
            report_search_results = list(ddgs.text(report_query, max_results=15, region='us-en'))
            
            for res in report_search_results:
                url = res['href']
                title = res['title']
                
                # Check for PDF extension
                if url.lower().endswith('.pdf'):
                     if url not in [r['href'] for r in results['reports']]:
                        results["reports"].append({
                            "title": title,
                            "href": url,
                            "body": res['body']
                        })
                
                if len(results["reports"]) >= 2:
                    break
        except Exception as e:
            print(f"Report search error: {e}")

        # Small delay
        time.sleep(1)

        # 4. Find latest CDP Submission (Climate Change Questionnaire)
        # CDP is usually hosted on cdp.net or external sites, so we DON'T restrict to company domain
        cdp_query = f"{company_name} CDP climate change questionnaire pdf"
        print(f"Searching for CDP: {cdp_query}")
        results["cdp"] = []

        try:
            cdp_results = list(ddgs.text(cdp_query, max_results=10, region='us-en'))
            for res in cdp_results:
                url = res['href']
                title = res['title']
                if 'cdp' in title.lower() or 'climate change' in title.lower() or 'questionnaire' in title.lower():
                     if url not in [r['href'] for r in results['cdp']]:
                        results["cdp"].append({
                            "title": title,
                            "href": url,
                            "body": res['body']
                        })
                if len(results["cdp"]) >= 2:
                    break
        except Exception as e:
             print(f"CDP search error: {e}")

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
                data = search_esg_info(company_name)
                
                st.success("Search complete!")
                
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
                    
            except Exception as e:
                st.error(f"An error occurred during search: {e}")


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
