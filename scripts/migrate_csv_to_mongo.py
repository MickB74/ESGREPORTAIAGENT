import streamlit as st
import pandas as pd
import sys
import os

# Add parent directory to path to import mongo_handler
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mongo_handler import MongoHandler

def migrate():
    print("🚀 Starting Migration: CSV -> MongoDB Atlas")
    
    # 1. Connect to Mongo
    # Hack: Load secrets manually or ensure they are present for this script
    # Since this runs as a subprocess or manually, we might need to handle secrets.
    # We'll rely on Streamlit secrets being available if run via 'streamlit run' or similar,
    # OR we rely on the fact that app.py initializes the handler.
    # Actually, for a standalone script, we need to read secrets.toml manually if not running via streamlit.
    
    # Simpler: We'll make this script compatible with 'streamlit run' for easy execution with secrets
    
    if "MONGO_URI" not in st.secrets:
        st.error("❌ MONGO_URI not found in secrets.")
        return

    mongo = MongoHandler()
    if not mongo.client:
        st.error("❌ Could not connect to MongoDB.")
        return

    # 2. Read CSV
    csv_file = "SP500ESGWebsites.csv"
    if not os.path.exists(csv_file):
        st.error(f"❌ '{csv_file}' not found.")
        return
        
    try:
        df = pd.read_csv(csv_file, encoding='utf-8', on_bad_lines='skip')
    except:
        df = pd.read_csv(csv_file, encoding='latin1', on_bad_lines='skip')
        
    print(f"📄 Read {len(df)} rows from CSV.")
    
    # 3. Transform
    # Clean up column names usually found in this file
    # Typical: Symbol, Symbol.1 (duplicate), Name, Company Description, Company Name, Website
    # We want standard keys: Symbol, Security, Name, Description, Website
    
    records = []
    for _, row in df.iterrows():
        # Heuristic for columns
        symbol = row.get('Symbol.1') if 'Symbol.1' in row else row.get('Symbol')
        if not symbol: continue
        
        name = row.get('Company Name') if 'Company Name' in row else row.get('Name')
        security = row.get('Security') if 'Security' in row else name # fallback
        
        # Ensure we have a valid record
        rec = {
            "Symbol": str(symbol).strip().upper(),
            "Security": str(name).strip(),
            "Company Name": str(name).strip(),
            "Company Description": str(row.get('Company Description', '')),
            "Website": str(row.get('Website', ''))
        }
        records.append(rec)
        
    # 4. Push to Mongo
    success, msg = mongo.bulk_write_companies(records)
    
    if success:
        st.success(f"✅ Migration Complete! {msg}")
        print(f"✅ Migration Complete! {msg}")
    else:
        st.error(f"❌ Migration Failed: {msg}")
        print(f"❌ Migration Failed: {msg}")

if __name__ == "__main__":
    migrate()
