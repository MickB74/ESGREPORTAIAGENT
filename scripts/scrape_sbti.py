
import os
import time
import json
import pandas as pd
from playwright.sync_api import sync_playwright
from pymongo import MongoClient
import certifi
import shutil

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
    except Exception as e:
        print(f"Error reading secrets with toml: {e}")

    # 3. Environment variable
    env_uri = os.environ.get("MONGO_URI")
    if env_uri: return env_uri
    
    return None

def scrape_sbti():
    print("🚀 Starting SBTi Scraper...")
    
    mongo_uri = get_mongo_uri()
    if not mongo_uri:
        print("❌ Error: MONGO_URI not found.")
        return

    # Connect to MongoDB
    try:
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
        db = client.esg_agent
        collection = db.sbti_companies
        print("✅ Connected to MongoDB.")
    except Exception as e:
        print(f"❌ MongoDB Connection Failed: {e}")
        return

    # Direct Download URL found in HTML inspection
    # https://files.sciencebasedtargets.org/production/files/companies-excel.xlsx
    download_file = "sbti_data.xlsx"
    url = "https://files.sciencebasedtargets.org/production/files/companies-excel.xlsx"
    print(f"Downloading from {url}...")
    
    try:
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        with open(download_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ Saved to {download_file}")
        
    except ImportError:
        print("Installing requests...")
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
        # Retry once
        response = requests.get(url, stream=True)
        with open(download_file, "wb") as f:
             for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return

    # Process Excel File
    if os.path.exists(download_file):
        print("Processing Excel file...")
        try:
            # Need openpyxl
            try:
                import openpyxl
            except ImportError:
                print("Installing openpyxl...")
                import subprocess, sys
                subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
            
            df = pd.read_excel(download_file)
            print(f"Loaded {len(df)} rows.")
            
            # Clean / Normalize Columns
            # Expected columns in SBTi data usually: 
            # 'Company Name', 'ISIN', 'LEI', 'Target Status', 'Near term - Target Status', 'Net zero - Target Status', etc.
            # We'll normalize to snake_case for DB
            
            df.columns = [str(c).lower().strip().replace(" ", "_").replace("-", "_").replace("__", "_") for c in df.columns]
            
            # Rename critical columns if needed for consistency
            if 'company_name' not in df.columns and 'company' in df.columns:
                df.rename(columns={'company': 'company_name'}, inplace=True)
                
            records = df.to_dict('records')
            
            # Upsert
            print(f"Upserting {len(records)} records to MongoDB...")
            count = 0
            for vid, rec in enumerate(records):
                # Clean NaNs
                clean_rec = {k: v for k, v in rec.items() if pd.notna(v)}
                clean_rec["source"] = "SBTi Dashboard"
                clean_rec["scraped_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Use Company Name + ISIN as key if possible, else just Name
                # Name is best for now as primary key for linking
                c_name = clean_rec.get("company_name", "Unknown")
                
                if c_name != "Unknown":
                    collection.update_one(
                        {"company_name": c_name},
                        {"$set": clean_rec},
                        upsert=True
                    )
                    count += 1
            
            print(f"🎉 Successfully imported {count} SBTi records!")
            
            # Cleanup
            os.remove(download_file)
            print("Cleaned up temp file.")
            
        except Exception as e:
            print(f"❌ Excel Processing Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ File not found after download attempt.")

if __name__ == "__main__":
    scrape_sbti()
