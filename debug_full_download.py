import requests
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

url = "https://www.oracle.com/a/ocom/docs/corporate/air-pollutant-emissions.pdf"

# EXACT Headers from app.py
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print(f"Testing URL: {url}")
print(f"Headers: {headers}")

try:
    response = requests.get(
        url, 
        headers=headers, 
        timeout=30, 
        verify=False
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content Length: {len(response.content)}")
    
    if response.status_code == 200:
        print("✅ SUCCESS")
    else:
        print("❌ FAILED")
        print(response.text[:500])

except Exception as e:
    print(f"❌ ERROR: {e}")
