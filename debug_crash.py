import streamlit as st
# Mock session state to avoid errors if app.py relies on it
if 'esg_data' not in st.session_state: st.session_state.esg_data = {}

from app import search_esg_info

print("Running search for CBRE (should trigger fallback)...")
try:
    results = search_esg_info("CBRE", provider="Google")
    print("\nSearch finished successfully.")
    print(f"Reports found: {len(results.get('reports', []))}")
except Exception as e:
    print(f"\nCRASH DETECTED: {e}")
    import traceback
    traceback.print_exc()
