import json
import csv
import re
import os

CSV_FILE = "SP500ESGWebsites.csv"
OUTPUT_FILE = "company_map.json"

company_map = {}

def clean_company_name(name):
    """
    Remove legal entity suffixes to create a 'searchable' common name.
    e.g. "Apple Inc." -> "Apple"
    """
    # Remove contents in parentheses e.g. "Company (The)"
    name = re.sub(r'\(.*?\)', '', name)
    
    # Common suffixes
    suffixes = [
        " Inc.", " Inc", ", Inc.", ", Inc",
        " Corp.", " Corp", ", Corp.", ", Corp",
        " Corporation", ", Corporation",
        " Company", " Co.", " Co",
        " plc", " PLC",
        " Ltd.", " Ltd", ", Ltd.", ", Ltd",
        " Group", ", Group",
        " Incorporated", ", Incorporated",
        " Limited", ", Limited",
        " S.A.", " SA",
        " N.V.", " NV",
        " AG",
        " & Co."
    ]
    
    # Sort suffixes by length descending to catch longest matches first
    suffixes.sort(key=len, reverse=True)
    
    cleaned = name
    for suffix in suffixes:
        if cleaned.lower().endswith(suffix.lower()):
            cleaned = cleaned[:-len(suffix)]
            break
            
    return cleaned.strip()

if not os.path.exists(CSV_FILE):
    print(f"Error: {CSV_FILE} not found.")
    exit(1)

with open(CSV_FILE, 'r', encoding='utf-8', errors='replace') as f:
    # Use csv reader to handle quoted fields (descriptions) automatically
    reader = csv.reader(f)
    
    # Skip header
    try:
        header = next(reader)
    except StopIteration:
        print("Empty file")
        exit(1)

    count = 0
    for row in reader:
        # Expected row length is at least 6.
        # 0: Long Symbol
        # 1: Short Ticker (NVDA)
        # 2: CAPS NAME
        # 3: Description
        # 4: Company Name (NVIDIA Corporation)
        # 5: Website
        
        if len(row) < 6:
            continue
            
        ticker = row[1].strip()
        name = row[4].strip()
        website = row[5].strip()
        
        # Validation
        if not website.startswith("http"):
            continue
            
        # 1. Map Ticker (e.g. "nvda" -> url)
        if ticker:
            company_map[ticker.lower()] = website
            
        # 2. Map Full Name (e.g. "nvidia corporation" -> url)
        if name:
            company_map[name.lower()] = website
            
        # 3. Map Clean Name (e.g. "nvidia" -> url)
        cleaned = clean_company_name(name)
        if cleaned and len(cleaned) > 2 and cleaned.lower() != name.lower():
             company_map[cleaned.lower()] = website
             
        count += 1

# Save to json within the app structure
with open(OUTPUT_FILE, "w") as f:
    json.dump(company_map, f, indent=2)

print(f"Successfully processed {count} rows.")
print(f"Created {OUTPUT_FILE} with {len(company_map)} keys (tickers, full names, clean names).")
