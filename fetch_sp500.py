import pandas as pd
import json
import requests
from io import StringIO

def fetch_sp500_companies():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Wrap HTML content in StringIO to avoid FutureWarning about passing literal html string
        html_data = StringIO(response.text)
        tables = pd.read_html(html_data)
        
        # The first table is usually the S&P 500 list
        sp500_df = tables[0]
        
        # Select relevant columns: 'Symbol' and 'Security'
        companies = sp500_df[['Symbol', 'Security']].to_dict(orient='records')
        
        # Save to JSON
        with open('sp500_companies.json', 'w') as f:
            json.dump(companies, f, indent=4)
            
        print(f"Successfully fetched {len(companies)} companies and saved to sp500_companies.json")
        
    except Exception as e:
        print(f"Error fetching S&P 500 list: {e}")

if __name__ == "__main__":
    fetch_sp500_companies()
