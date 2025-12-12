from duckduckgo_search import DDGS
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

def get_domain(url):
    try:
        return urlparse(url).netloc
    except:
        return ""

def test(company):
    print(f"\n{'='*40}")
    print(f"Testing for: {company}")
    print(f"{'='*40}")
    
    # We can just import the actual function from app.py to test it directly!
    # But first we need to make sure app.py is importable (it has st. calls at top level?)
    # app.py has st calls at top level, so importing it might execute them and fail/warn.
    # It's better to copy the critical logic or mock st.
    # Actually, let's just copy the logic effectively for the debug script, 
    # OR we can wrap the app.py logic in a `if __name__ == "__main__":` block? 
    # No, app.py is a streamlit app.
    
    # Let's just run the search_esg_info from app.py by importing it.
    # Streamlit scripts often execute on import. 
    # A better approach for the future refactor would be to move logic to a separate file.
    # For now, I will reimplement a simplified version here to verify the CONCEPTS work,
    # or I will try to see if I can import it.
    
    # Let's try importing it. If it fails, I'll paste the logic.
    try:
        from app import search_esg_info
        print("Successfully imported search_esg_info")
        results = search_esg_info(company)
        print("\nResults found:")
        print(f"Website: {results['website']['href'] if results['website'] else 'None'}")
        print(f"Reports ({len(results['reports'])}):")
        for r in results['reports']:
            print(f" - [{r.get('source', 'Unknown')}] {r['title'][:50]}... -> {r['href']}")
            
    except ImportError:
        print("Could not import app.py correctly (likely due to top-level code).")
    except Exception as e:
        print(f"Error running search: {e}")

if __name__ == "__main__":
    # We need to mock streamlit for the import to work without erroring on st.set_page_config?
    # Actually, st commands usually just warn or do nothing if no server is running.
    # Let's try.
    import streamlit
    # Mocking basic st stuff to avoid errors if possible
    
    test("Apple")
    test("ExxonMobil")
    test("3M")


