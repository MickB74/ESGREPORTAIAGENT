
import json
import os
import streamlit as st
import toml
from pymongo import MongoClient
import certifi

def get_mongo_uri():
    # 1. Try Streamlit secrets
    try:
        if hasattr(st, "secrets"):
            if "MONGO_URI" in st.secrets:
                return st.secrets["MONGO_URI"]
            if "mongo" in st.secrets and "uri" in st.secrets["mongo"]:
                return st.secrets["mongo"]["uri"]
    except:
        pass
    
    # 2. Try parsing .streamlit/secrets.toml with toml library
    try:
        secrets_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            data = toml.load(secrets_path)
            if "MONGO_URI" in data:
                return data["MONGO_URI"]
    except Exception as e:
        print(f"Error reading secrets file: {e}")

    return None

def import_data():
    print("🚀 Starting Import...")
    
    # 1. Load Data
    try:
        with open("re100_companies.json", "r") as f:
            companies = json.load(f)
        print(f"✅ Loaded {len(companies)} companies from JSON.")
    except FileNotFoundError:
        print("❌ 're100_companies.json' not found. Run the scraper first.")
        return

    # 2. Connect to Mongo
    uri = get_mongo_uri()
    if not uri:
        print("❌ MONGO_URI not found in .streamlit/secrets.toml")
        print("Please add it like this:\nMONGO_URI = 'mongodb+srv://user:pass@...'")
        return

    try:
        client = MongoClient(uri, tlsCAFile=certifi.where())
        db = client.esg_agent
        collection = db.re100_companies
        
        # Test connection
        client.admin.command('ping')
        print("✅ Connected to MongoDB.")
        
        # 3. Upsert
        print("Upserting data...")
        count = 0
        for comp in companies:
            collection.update_one(
                {"company_name": comp["company_name"]},
                {"$set": comp},
                upsert=True
            )
            count += 1
        print(f"🎉 Successfully imported {count} companies into 're100_companies' collection!")
        
    except Exception as e:
        print(f"❌ Connection/Import Error: {e}")

if __name__ == "__main__":
    import_data()
