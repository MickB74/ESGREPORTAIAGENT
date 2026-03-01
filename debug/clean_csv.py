import pandas as pd
import csv

input_file = "SP500ESGWebsites.csv"

print(f"Cleaning {input_file}...")

valid_rows = []
try:
    # Try reading as latin1 first since we know it has issues
    with open(input_file, 'r', encoding='latin1', errors='replace') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
            valid_rows.append(header)
        except StopIteration:
            pass
        
        for i, row in enumerate(reader):
            # Check for empty rows (all empty strings)
            if not any(field.strip() for field in row):
                continue
            
            # Check for correct column count (approx)
            if len(row) >= 6:
                # Keep first 6 columns to allow for some malformation fixes
                valid_rows.append(row[:6])
                
    # Save back as UTF-8
    with open(input_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(valid_rows)
        
    print(f"Success! Cleaned file has {len(valid_rows)} rows.")

except Exception as e:
    print(f"Error cleaning file: {e}")
