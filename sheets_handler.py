import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# Define scope
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def connect_to_sheet():
    """Authenticates with Google Sheets API using st.secrets."""
    if "google_sheets" not in st.secrets:
        return None, "Missing [google_sheets] in secrets.toml"

    try:
        # Create credentials object from secrets dict
        creds_dict = dict(st.secrets["google_sheets"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        # Open the specific sheet (create if doesn't exist? No, better Open by name)
        # We'll use a standard name "ESG_Report_Database"
        sheet_name = "ESG_Report_Database"
        try:
            sheet = client.open(sheet_name).sheet1
        except gspread.SpreadsheetNotFound:
            # Create it if possible
            try:
                sh = client.create(sheet_name)
                sheet = sh.sheet1
                # Initialize headers
                sheet.append_row(["Timestamp", "Company", "Title", "Label", "URL", "Description"])
            except Exception as e:
                return None, f"Could not create sheet '{sheet_name}': {e}"
        
        return sheet, None
    except Exception as e:
        return None, f"Auth Error: {e}"

def save_link_to_sheet(company, title, url, label, description=""):
    """Saves a single link to the Google Sheet."""
    sheet, error = connect_to_sheet()
    if error:
        return False, error
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [timestamp, company, title, label, url, description]
    
    try:
        sheet.append_row(row)
        return True, "Saved to Google Sheet"
    except Exception as e:
        return False, f"Write Error: {e}"

def get_links_from_sheet(company_name):
    """Fetches links for a specific company."""
    sheet, error = connect_to_sheet()
    if error:
        return [], error
        
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Filter by company (fuzzy match?)
        # For now, exact match or substring
        if df.empty:
            return [], None
            
        # Clean naming
        # Ensure columns exist
        if "Company" not in df.columns:
            return [], "Invalid Sheet Format"
            
        # Filter (case insensitive)
        filtered = df[df["Company"].str.contains(company_name, case=False, na=False)]
        
        # Convert to list of dicts
        results = filtered.to_dict('records')
        return results, None
        
    except Exception as e:
        return [], f"Read Error: {e}"
