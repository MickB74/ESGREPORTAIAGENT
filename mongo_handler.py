import streamlit as st
import pymongo
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import time
import certifi

class MongoHandler:
    def __init__(self):
        """
        Initialize connection to MongoDB Atlas.
        Requires st.secrets["MONGO_URI"].
        """
        self.client = None
        self.db = None
        
        try:
            uri = st.secrets["MONGO_URI"]
            # Connect with server selection timeout to fail fast if config is wrong
            # Use certifi for SSL certificate verification to prevent handshake errors
            # Adding tlsAllowInvalidCertificates=True as a fallback for strict cloud environments
            self.client = MongoClient(
                uri, 
                serverSelectionTimeoutMS=5000,
                tlsCAFile=certifi.where(),
                tlsAllowInvalidCertificates=True
            )
            
            # Default database name (can be anything, e.g. 'esg_agent')
            self.db = self.client.esg_agent
            
            # Test connection
            self.client.server_info()
            print("✅ Connected to MongoDB Atlas")
            
        except Exception as e:
            st.error(f"❌ MongoDB Connection Failed: {e}")
            self.client = None

    # -------------------------------------------------------------------------
    # GENERIC HELPERS
    # -------------------------------------------------------------------------
    def _get_collection(self, collection_name: str):
        if self.db is not None:
            return self.db[collection_name]
        return None

    # -------------------------------------------------------------------------
    # UNIFIED CRUD OPERATIONS
    # -------------------------------------------------------------------------
    def get_all_links(self, collection_name: str) -> list:
        """
        Retrieve all documents from a specific collection (saved_links or verified_links).
        """
        col = self._get_collection(collection_name)
        if col is None: return []

        try:
            # Sort by timestamp descending
            cursor = col.find({}, {'_id': 0}).sort("timestamp", -1)
            return list(cursor)
        except Exception as e:
            st.error(f"Read Error ({collection_name}): {e}")
            return []

    def save_link(self, collection_name: str, link_data: dict) -> tuple[bool, str]:
        """
        Upsert a link document based on 'url'.
        """
        col = self._get_collection(collection_name)
        if col is None: return False, "No DB Connection"

        try:
            url = link_data.get('url')
            if not url: return False, "URL is required"

            # Add timestamp if new
            if 'timestamp' not in link_data or not link_data['timestamp']:
                link_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Upsert (Update if exists, Insert if not)
            col.update_one(
                {'url': url},
                {'$set': link_data},
                upsert=True
            )
            
            # Clear cache to reflect updates immediately if listing uses cache
            st.cache_data.clear()
            
            return True, "Saved to MongoDB Atlas"
        except Exception as e:
            return False, f"Save Error: {e}"

    def delete_link(self, collection_name: str, url: str) -> bool:
        """
        Delete a document by URL.
        """
        col = self._get_collection(collection_name)
        if col is None: return False

        try:
            result = col.delete_one({'url': url})
            return result.deleted_count > 0
        except Exception as e:
            st.error(f"Delete Error: {e}")
            return False

    def get_stats(self, collection_name: str) -> dict:
        """Get count of documents and unique companies."""
        col = self._get_collection(collection_name)
        if col is None: return {"total": 0, "companies": 0}
        
        try:
            total = col.count_documents({})
            companies = len(col.distinct("company"))
            return {"total": total, "companies": companies}
        except Exception:
            return {"total": 0, "companies": 0}

    # -------------------------------------------------------------------------
    # HUB OVERRIDES
    # -------------------------------------------------------------------------
    def get_company_hub(self, company: str) -> str:
        """Get the verified hub URL for a company if exists."""
        col = self._get_collection("company_hubs")
        if col is None: return None
        
        try:
            doc = col.find_one({"company": company.lower()})
            return doc.get('url') if doc else None
        except Exception:
            return None

    def save_company_hub(self, company: str, url: str) -> tuple[bool, str]:
        """Save a verified hub URL for a company (overrides defaults)."""
        col = self._get_collection("company_hubs")
        if col is None: return False, "No DB Connection"
        
        try:
            col.update_one(
                {'company': company.lower()},
                {'$set': {
                    'company': company.lower(), 
                    'url': url,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }},
                upsert=True
            )
            return True, "Hub updated in Cloud DB."
        except Exception as e:
            return False, f"Error: {e}"
