import json
import difflib

try:
    with open("company_map.json", "r") as f:
        cmap = json.load(f)
        
    query = "appel"
    print(f"Query: {query}")
    
    # 1. Exact
    if query in cmap:
        print("Exact match found!")
    else:
        print("No exact match.")
        
    # 2. Fuzzy
    matches = difflib.get_close_matches(query, cmap.keys(), n=3, cutoff=0.6)
    print(f"Matches (cutoff=0.6): {matches}")
    
    if matches:
        k = matches[0]
        v = cmap[k]
        print(f"Selected: {k} -> {v}")

except Exception as e:
    print(e)
