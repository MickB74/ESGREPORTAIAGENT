import pandas as pd
import os
from datetime import datetime

CSV_FILE = os.path.join(os.path.dirname(__file__), "verified_links.csv")

def init_csv():
    """Initialize the CSV file with headers if it doesn't exist."""
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=["Timestamp", "Company", "Title", "Label", "URL", "Description"])
        df.to_csv(CSV_FILE, index=False)

def save_link(company, title, url, label, description=""):
    """Appends a link to the CSV file."""
    try:
        init_csv()
        
        # Check for duplicates?
        # For simple append, maybe just append.
        new_row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Company": company,
            "Title": title,
            "Label": label,
            "URL": url,
            "Description": description
        }
        
        # Load existing to check duplicate URL?
        df = pd.read_csv(CSV_FILE)
        if url in df['URL'].values:
            # Update label?
            df.loc[df['URL'] == url, 'Label'] = label
            df.to_csv(CSV_FILE, index=False)
            return True, "Updated existing link label."
        else:
            # Append
            row_df = pd.DataFrame([new_row])
            row_df.to_csv(CSV_FILE, mode='a', header=False, index=False)
            return True, "Saved to CSV."
            
    except Exception as e:
        return False, f"CSV Error: {e}"

def get_links(company_name):
    """Fetches links for a company from CSV."""
    if not os.path.exists(CSV_FILE):
        return [], None
        
    try:
        df = pd.read_csv(CSV_FILE)
        if "Company" not in df.columns:
            return [], "Invalid CSV format"
            
        # Filter (case insensitive)
        # Handle NaN values in Company column safely
        mask = df["Company"].fillna("").str.contains(company_name, case=False, na=False)
        filtered = df[mask]
        
        return filtered.to_dict('records'), None
    except Exception as e:
        return [], f"Read Error: {e}"
