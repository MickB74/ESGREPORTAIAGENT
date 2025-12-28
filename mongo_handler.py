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

    # -------------------------------------------------------------------------
    # COMPANY MANAGEMENT (S&P 500)
    # -------------------------------------------------------------------------
    def get_all_companies(self) -> list:
        """Retrieve all companies for the dropdown."""
        col = self._get_collection("companies")
        if col is None: return []
        
        try:
            # Sort by Security name
            cursor = col.find({}, {'_id': 0}).sort("Security", 1)
            return list(cursor)
        except Exception:
            return []

    def save_company(self, company_data: dict) -> tuple[bool, str]:
        """Upsert a company record."""
        col = self._get_collection("companies")
        if col is None: return False, "No DB Connection"
        
        try:
            # Use Symbol as unique key
            symbol = company_data.get('Symbol')
            if not symbol: return False, "Symbol is required"
            
            # Prepare update data
            # Remove created_at from company_data if present to avoid overwriting with None
            update_payload = {k: v for k, v in company_data.items() if k != 'created_at'}
            
            update_data = {
                '$set': {
                    **update_payload,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                '$setOnInsert': {
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
            col.update_one(
                {'Symbol': symbol},
                update_data,
                upsert=True
            )
            # Clear cache
            st.cache_data.clear()
            return True, "Company saved to Cloud DB."
        except Exception as e:
            return False, f"Save Error: {e}"

    def bulk_write_companies(self, companies_list: list) -> tuple[bool, str]:
        """Bulk write for migration."""
        col = self._get_collection("companies")
        if col is None: return False, "No DB Connection"
        
        try:
            # Clear existing? Maybe safer to just upsert.
            # For migration, let's replace all to be clean if it's a "reset"
            # But normally we'd upsert. Let's do delete_many({}) first for a clean migration?
            # User might want to keep existing, but this is a migration task.
            # Let's assume clean slate for migration script usage.
            col.delete_many({})
            
            if companies_list:
                col.insert_many(companies_list)
            return True, f"Successfully imported {len(companies_list)} companies."
            return True, f"Successfully imported {len(companies_list)} companies."
        except Exception as e:
            return False, f"Bulk Error: {e}"
    
    def migrate_companies_from_csv(self, csv_path="SP500ESGWebsites.csv") -> tuple[bool, str]:
        """
        One-time migration helper: Read CSV and populate companies collection.
        """
        import os
        if not os.path.exists(csv_path):
            return False, f"CSV file not found: {csv_path}"
        
        try:
            # Read CSV
            df = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='skip')
        except:
            try:
                df = pd.read_csv(csv_path, encoding='latin1', on_bad_lines='skip')
            except Exception as e:
                return False, f"CSV Read Error: {e}"
        
        # Transform rows
        records = []
        for _, row in df.iterrows():
            symbol = row.get('Symbol.1') if 'Symbol.1' in row else row.get('Symbol')
            if not symbol or pd.isna(symbol):
                continue
            
            name = row.get('Company Name') if 'Company Name' in row else row.get('Name')
            security = row.get('Security') if 'Security' in row else name
            
            rec = {
                "Symbol": str(symbol).strip().upper(),
                "Security": str(security).strip() if security else "",
                "Company Name": str(name).strip() if name else "",
                "Company Description": str(row.get('Company Description', '')),
                "Website": str(row.get('Website', ''))
            }
            records.append(rec)
        
        if not records:
            return False, "No valid records found in CSV"
        
        # Use existing bulk write
        return self.bulk_write_companies(records)

