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
    
def migrate():
    print("🚀 Starting Migration: CSV -> MongoDB Atlas")
    
    # 1. Connect to Mongo
    # Robust Secret Loading
    uri = st.secrets.get("MONGO_URI")
    if not uri and "mongo" in st.secrets:
         uri = st.secrets["mongo"].get("uri")
         
    if not uri:
        st.error("❌ MONGO_URI not found in secrets (checked 'MONGO_URI' and 'mongo.uri').")
        return

    # Initialize Handler with global st.mongo if available or new
    # We can't easily inject the URI into MongoHandler if it expects st.secrets["MONGO_URI"] hardcoded.
    # So we must ensure st.secrets has it, or we instantiate pymongo manually here.
    # Manual is safer for a script.
    
    try:
        import pymongo
        import certifi
        client = pymongo.MongoClient(uri, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
        # Verify connection
        client.admin.command('ping')
        print("✅ Connected to MongoDB.")
        
        # Get DB (default from URI or specific)
        db = client.get_default_database()
        
    except Exception as e:
        st.error(f"❌ Could not connect to MongoDB: {e}")
        return

    # 2. Read CSV
    csv_file = "SP500ESGWebsites.csv"
    if not os.path.exists(csv_file):
        st.error(f"❌ '{csv_file}' not found in {os.getcwd()}.")
        return
        
    try:
        df = pd.read_csv(csv_file, encoding='utf-8', on_bad_lines='skip')
    except:
        df = pd.read_csv(csv_file, encoding='latin1', on_bad_lines='skip')
        
    st.info(f"📄 Read {len(df)} rows from CSV.")
    print(f"📄 Read {len(df)} rows from CSV.")
    
    # 3. Transform
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
            "Security": str(security).strip(),
            "Company Name": str(name).strip(),
            "Company Description": str(row.get('Company Description', '')),
            "Website": str(row.get('Website', ''))
        }
        records.append(rec)
        
    # 4. Push to Mongo (Directly using pymongo to avoid handler dependency/complexity)
    try:
        col = db["companies"]
        # Clear old
        col.delete_many({})
        # Insert
        if records:
            col.insert_many(records)
            msg = f"Inserted {len(records)} companies."
            success = True
        else:
            msg = "No records to insert."
            success = False
            
    except Exception as e:
        success = False
        msg = str(e)
    
    if success:
        st.success(f"✅ Migration Complete! {msg}")
        print(f"✅ Migration Complete! {msg}")
        with open("migration.log", "w") as f:
            f.write(f"SUCCESS: {msg}")
    else:
        st.error(f"❌ Migration Failed: {msg}")
        print(f"❌ Migration Failed: {msg}")
        with open("migration.log", "w") as f:
            f.write(f"FAILURE: {msg}")

if __name__ == "__main__":
    migrate()
