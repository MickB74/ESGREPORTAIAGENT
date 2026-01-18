
import os
import sys
import time
import re
from pymongo import MongoClient
import certifi
from playwright.sync_api import sync_playwright
import pandas as pd

# Try to load secrets
def get_mongo_uri():
    # 1. Try Streamlit secrets (if running via streamlit)
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "MONGO_URI" in st.secrets:
                return st.secrets["MONGO_URI"]
            if "mongo" in st.secrets and "uri" in st.secrets["mongo"]:
                return st.secrets["mongo"]["uri"]
    except:
        pass
    
    # 2. Try parsing .streamlit/secrets.toml with toml library
    try:
        import toml
        secrets_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            data = toml.load(secrets_path)
            if "MONGO_URI" in data:
                return data["MONGO_URI"]
            if "mongo" in data and "uri" in data["mongo"]:
                return data["mongo"]["uri"]
    except Exception as e:
        print(f"Error reading secrets with toml: {e}")

    # 3. Environment variable
    env_uri = os.environ.get("MONGO_URI")
    if env_uri: return env_uri

    # 4. Fallback to Localhost
    print("⚠️ MONGO_URI not found in secrets or env. Defaulting to localhost.")
    return "mongodb://localhost:27017"

def scrape_re100():
    print("🚀 Starting RE100 Scraper...")
    
    mongo_uri = get_mongo_uri()
    if not mongo_uri:
        print("❌ Error: Could not find MONGO_URI in secrets or environment.")
        return

    # Connect to MongoDB
    try:
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
        db = client.esg_agent # Using the same DB as the app
        collection = db.re100_companies
        print("✅ Connected to MongoDB.")
    except Exception as e:
        print(f"❌ MongoDB Connection Failed: {e}")
        return

    # Scrape with Playwright
    companies = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        
        base_url = "https://www.there100.org/re100-members"
        page_num = 0
        
        while True:
            url = f"{base_url}?page={page_num}"
            print(f"Scanning {url}...")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Wait for the view content to load
                page.wait_for_selector(".views-element-container", timeout=10000)
            except Exception as e:
                print(f"Navigation error or timeout on page {page_num}: {e}")
                break

            # Check if there are members on the screen
            # Based on the chunk viewed, specific selectors might be needed.
            # It seems to list companies. Let's try to find them.
            # A common Drupal pattern is .views-row or similar.
            
            # Extract content using evaluate for robustness
            page_data = page.evaluate("""() => {
                const items = [];
                // Select all 'top' rows that are NOT the detail rows
                // The logical rows are pairs: tr.s-member-re100-row-top (main) and tr.s-member-re100-row-top.s-member-re100-row-bottom (details)
                // But looking at the HTML, the main row only has 's-member-re100-row-top'
                // The second row has 's-member-re100-row-top s-member-re100-row-bottom'
                
                const rows = document.querySelectorAll('tr.s-member-re100-row-top:not(.s-member-re100-row-bottom)');
                
                rows.forEach(row => {
                     const nameEl = row.querySelector('.re100-members-table-title-text');
                     const linkEl = row.querySelector('.views-field-title a');
                     const targetEl = row.querySelector('.views-field-field-target-year');
                     const industryEl = row.querySelector('.views-field-field-industry');
                     const hqEl = row.querySelector('.views-field-field-headquarters');
                     
                     // Get description from next sibling row
                     let desc = "";
                     const nextRow = row.nextElementSibling;
                     if (nextRow && nextRow.classList.contains('s-member-re100-row-bottom')) {
                         const descEl = nextRow.querySelector('.s-member-re100-row-bottom__details');
                         if (descEl) desc = descEl.innerText.trim();
                     }
                     
                     if (nameEl) {
                         items.push({
                             name: nameEl.innerText.trim(),
                             website: linkEl ? linkEl.href : null,
                             target_year_col: targetEl ? targetEl.innerText.trim() : null,
                             industry: industryEl ? industryEl.innerText.trim() : null,
                             hq: hqEl ? hqEl.innerText.trim() : null,
                             description: desc
                         });
                     }
                });
                
                return items;
            }""")
            
            if not page_data:
                print(f"No data found on page {page_num}. Stopping.")
                break
                
            print(f"Found {len(page_data)} companies on page {page_num}.")
            
            # Post-process and add to list
            for item in page_data:
                # Use target year from column if available
                target_year = item.get("target_year_col")
                if target_year and not target_year.isdigit(): target_year = None # Clean if needed
                
                company_doc = {
                    "company_name": item["name"],
                    "description": item["description"],
                    "website": item["website"],
                    "target_year": target_year,
                    "industry": item.get("industry"),
                    "hq": item.get("hq"),
                    "source": "RE100 Website",
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                companies.append(company_doc)
            
            # Check for next page
            # If we found less than X items, maybe last page?
            # Or check for "Next" button specifically.
            next_disabled = page.locator(".pager__item--next.is-disabled").count() > 0
            if next_disabled:
                print("Next button disabled. Reached end.")
                break
            
            # Basic check: if we got 0 items (handled above), or loop limit
            if page_num > 50: # Safety break
                print("Safety limit reached (50 pages).")
                break
                
            page_num += 1
            time.sleep(1) # Be nice
        
        browser.close()

    print(f"Total Companies Scraped: {len(companies)}")

    # Save to JSON backup
    import json
    try:
        with open("re100_companies.json", "w") as f:
            json.dump(companies, f, indent=2)
        print("✅ Saved scraped data to re100_companies.json")
    except Exception as e:
        print(f"❌ Failed to save JSON: {e}")
    
    # Upsert to MongoDB
    if companies:
        print("Upserting to MongoDB...")
        try:
            # Check connection first
            client.admin.command('ping')
            
            count = 0
            for comp in companies:
                # Use name as key
                collection.update_one(
                    {"company_name": comp["company_name"]},
                    {"$set": comp},
                    upsert=True
                )
                count += 1
            print(f"✅ Successfully processed {count} records in 're100_companies' collection.")
        except Exception as e:
            print(f"❌ MongoDB Write Failed (Server likely not running): {e}")
    else:
        print("⚠️ No companies found to save.")

if __name__ == "__main__":
    scrape_re100()
