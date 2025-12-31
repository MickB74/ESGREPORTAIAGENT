import requests

url = "https://www.oracle.com/a/ocom/docs/corporate/air-pollutant-emissions.pdf"
headers = {"User-Agent": "Mozilla/5.0"}
try:
    r = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('Content-Type')}")
    print(f"Content-Length: {len(r.content)}")
    if len(r.content) < 1000:
        print(f"Content preview: {r.content[:200]}")
except Exception as e:
    print(f"Error: {e}")
