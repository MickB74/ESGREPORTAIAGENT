import json
import requests
import os
import sys
import re

def sanitize_filename(name):
    """Make valid filename from title"""
    # Keep alpha, digit, space, dash
    clean = re.sub(r'[^a-zA-Z0-9 \-]', '', name)
    # Collapse spaces
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:100] # Limit length

def ingest_reports(json_file):
    if not os.path.exists(json_file):
        print(f"Error: {json_file} does not exist.")
        return

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            
        reports = data.get('reports', [])
        cdp = data.get('cdp', [])
        all_docs = reports + cdp
        
        company_name = data.get('company', 'Unknown')
        print(f"Processing {len(all_docs)} documents for {company_name}...")
        
        # Create output dir
        output_dir = "rag_docs"
        os.makedirs(output_dir, exist_ok=True)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        downloaded_count = 0
        for doc in all_docs:
            url = doc.get('href')
            title = doc.get('title', 'untitled')
            
            if not url: continue
            
            # Create filename: "Company_Title.pdf"
            safe_title = sanitize_filename(title)
            safe_company = sanitize_filename(company_name)
            filename = f"{safe_company}_{safe_title}.pdf"
            filepath = os.path.join(output_dir, filename)
            
            if os.path.exists(filepath):
                print(f"Skipping (exists): {filename}")
                continue
                
            print(f"Downloading: {title}...")
            try:
                resp = requests.get(url, headers=headers, timeout=15, stream=True)
                if resp.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"  -> Saved to {filepath}")
                    downloaded_count += 1
                else:
                    print(f"  -> Failed (Status {resp.status_code})")
            except Exception as e:
                print(f"  -> Failed error: {e}")

        print(f"\nIngestion Complete. Downloaded {downloaded_count} new files.")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_reports.py <path_to_esg_data.json>")
    else:
        ingest_reports(sys.argv[1])
