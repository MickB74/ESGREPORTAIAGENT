"""
Batch ESG Report Scanner

Scans ~50 companies per run, finds ESG report URLs, downloads PDFs,
stores PDF files in Supabase Storage and metadata in MongoDB.
Designed to run as a daily GitHub Action that completes a full cycle
of all companies over ~11 days.

Usage:
    python scripts/batch_report_scanner.py [--batch-size 50] [--company SYMBOL]
"""

import os
import sys
import time
import argparse
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin

import certifi
from pymongo import MongoClient
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import robust_get, is_report_link, extract_year

SCAN_INTERVAL_DAYS = 30

# Report-type keywords, checked in priority order (first match wins).
# The slug becomes part of the stored filename.
REPORT_TYPE_RULES = [
    ("sustainability-report", ["sustainability report", "sustainability"]),
    ("esg-report", ["esg report", "esg"]),
    ("climate-report", ["climate", "tcfd", "cdp", "decarbonization", "net zero", "net-zero"]),
    ("environmental-report", ["environmental", "environment"]),
    ("impact-report", ["impact report", "impact"]),
    ("csr-report", ["corporate responsibility", "corporate-responsibility", "social responsibility", "csr"]),
    ("diversity-report", ["diversity", "inclusion", "dei", "human rights", "human-rights"]),
    ("governance-report", ["governance", "proxy"]),
    ("data-index", ["data index", "esg index", "sasb index", "gri index", "appendix", "metrics", "databook", "data-index"]),
    ("annual-report", ["annual report", "annual", "10-k", "10k"]),
]


def classify_report_type(title, url):
    """Return a short slug describing the report type, from title + URL keywords."""
    hay = f"{title or ''} {url or ''}".lower()
    for slug, keywords in REPORT_TYPE_RULES:
        if any(k in hay for k in keywords):
            return slug
    return "report"


def get_mongo_uri():
    env_uri = os.environ.get("MONGO_URI")
    if env_uri:
        return env_uri

    try:
        import toml
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".streamlit", "secrets.toml",
        )
        if os.path.exists(secrets_path):
            data = toml.load(secrets_path)
            if "MONGO_URI" in data:
                return data["MONGO_URI"]
            if "mongo" in data and "uri" in data["mongo"]:
                return data["mongo"]["uri"]
    except Exception as e:
        print(f"Error reading secrets: {e}")

    return None


def get_supabase_config():
    """Get Supabase URL, key, and bucket name from env or secrets."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    bucket = os.environ.get("SUPABASE_BUCKET", "esg_reports")

    if url and key:
        return url, key, bucket

    try:
        import toml
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".streamlit", "secrets.toml",
        )
        if os.path.exists(secrets_path):
            data = toml.load(secrets_path)
            url = url or data.get("SUPABASE_URL")
            key = key or data.get("SUPABASE_KEY")
            bucket = data.get("SUPABASE_BUCKET", bucket)
    except Exception as e:
        print(f"Error reading Supabase secrets: {e}")

    return url, key, bucket


def connect_mongo(uri):
    client = MongoClient(uri, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
    client.admin.command("ping")
    return client


def get_batch(db, batch_size):
    """Get the next batch of companies to scan, prioritizing those never scanned or least recently scanned."""
    cutoff = datetime.now(tz=None) - timedelta(days=SCAN_INTERVAL_DAYS)

    companies = list(db.companies.find({}, {"_id": 0}))
    if not companies:
        return []

    scanned = {}
    for doc in db.esg_reports.find({}, {"symbol": 1, "scanned_at": 1, "_id": 0}):
        sym = doc.get("symbol")
        ts = doc.get("scanned_at")
        if sym:
            existing = scanned.get(sym)
            if not existing or (ts and ts > existing):
                scanned[sym] = ts

    never_scanned = []
    stale = []
    for c in companies:
        sym = c.get("Symbol")
        if not sym:
            continue
        last = scanned.get(sym)
        if not last:
            never_scanned.append(c)
        elif isinstance(last, str):
            try:
                if datetime.strptime(last, "%Y-%m-%d %H:%M:%S") < cutoff:
                    stale.append(c)
            except ValueError:
                stale.append(c)
        elif last < cutoff:
            stale.append(c)

    batch = never_scanned[:batch_size]
    remaining = batch_size - len(batch)
    if remaining > 0:
        batch.extend(stale[:remaining])

    return batch


def search_reports_ddg(company_name, symbol):
    """Search DuckDuckGo for ESG report PDFs."""
    from duckduckgo_search import DDGS

    queries = [
        f"{company_name} ESG sustainability report PDF 2024",
        f"{company_name} ESG sustainability report PDF 2023",
        f"{symbol} annual sustainability report PDF",
    ]

    found = []
    seen_urls = set()

    with DDGS() as ddgs:
        for query in queries:
            try:
                results = list(ddgs.text(query, max_results=5, region="us-en"))
                for r in results:
                    url = r.get("href", "")
                    if url and url not in seen_urls and is_report_link(r.get("title", ""), url):
                        seen_urls.add(url)
                        found.append({
                            "title": r.get("title", ""),
                            "url": url,
                            "snippet": r.get("body", ""),
                        })
            except Exception as e:
                print(f"  Search error for '{query}': {e}")
            time.sleep(1)

    return found


def download_and_store_pdf(url, company_symbol, company_name, title, supabase_client, bucket_name):
    """Download a PDF and store it in Supabase Storage. Returns (public_url, file_size) or (None, None)."""
    try:
        resp = robust_get(url, timeout=30, stream=True)
        if resp.status_code != 200:
            return None, None

        content_type = resp.headers.get("Content-Type", "").lower()
        if "pdf" not in content_type and "octet-stream" not in content_type:
            resp.close()
            return None, None

        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) < 50_000:
            resp.close()
            return None, None

        chunks = []
        for chunk in resp.iter_content(chunk_size=8192):
            chunks.append(chunk)
        pdf_data = b"".join(chunks)

        file_size = len(pdf_data)
        if file_size < 50_000:
            return None, None

        # Build a descriptive filename: SYMBOL_report-type[_year]_hash.pdf
        report_type = classify_report_type(title, url)
        year = extract_year(f"{title} {url}")
        url_hash = hashlib.md5(url.encode()).hexdigest()[:6]
        parts = [company_symbol, report_type]
        if year:
            parts.append(year)
        parts.append(url_hash)
        filename = "_".join(parts) + ".pdf"
        storage_path = f"{company_symbol}/{filename}"

        supabase_client.storage.from_(bucket_name).upload(
            storage_path,
            pdf_data,
            file_options={"content-type": "application/pdf", "x-upsert": "true"},
        )

        # Get public URL
        public_url = supabase_client.storage.from_(bucket_name).get_public_url(storage_path)

        print(f"    Stored in Supabase: {storage_path} ({file_size / 1024:.0f} KB)")
        return public_url, file_size

    except Exception as e:
        import traceback
        print(f"    Download/store failed: {e}")
        traceback.print_exc()
        return None, None


def _is_direct_pdf(url):
    """True if a URL points directly at a PDF file."""
    u = url.lower().split("?")[0]
    return u.endswith(".pdf")


def find_pdfs_on_page(page_url, company_name):
    """Fetch a landing/hub page and return direct PDF links found on it.

    Big companies host their ESG report behind a landing page rather than
    linking the PDF directly. This follows that page one level deep and
    pulls out the actual report PDFs.
    Returns a list of {title, url} dicts.
    """
    found = []
    try:
        resp = robust_get(page_url, timeout=12)
        if resp.status_code != 200 or "html" not in resp.headers.get("Content-Type", "").lower():
            return found

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        parsed = urlparse(page_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        seen = set()
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            text = link.get_text(strip=True)

            # Resolve relative URLs
            if href.startswith("//"):
                href = f"{parsed.scheme}:{href}"
            elif href.startswith("/"):
                href = base + href
            elif not href.startswith("http"):
                # relative to current path
                href = urljoin(page_url, href)

            if not _is_direct_pdf(href) or href in seen:
                continue
            seen.add(href)

            # Keep only links that look like a report (by anchor text or URL)
            if is_report_link(text or href, href):
                found.append({"title": text or f"{company_name} ESG Report", "url": href})

        # Cap per page to avoid grabbing dozens of ancillary PDFs
        return found[:5]
    except Exception as e:
        print(f"      Landing-page scan error ({page_url[:60]}): {e}")
        return found


def scan_company(company, supabase_client, bucket_name):
    """Scan a single company for ESG reports."""
    name = company.get("Company Name", "Unknown")
    symbol = company.get("Symbol", "UNK")
    website = company.get("Website", "")

    print(f"\n{'='*60}")
    print(f"Scanning: {name} ({symbol})")
    print(f"{'='*60}")

    reports = []

    # Strategy 1: Search via DuckDuckGo
    print("  Strategy 1: Web search...")
    search_results = search_reports_ddg(name, symbol)
    print(f"  Found {len(search_results)} candidate links")

    # Strategy 2: Scan official website if available
    if website:
        print(f"  Strategy 2: Scanning official site ({website})...")
        try:
            resp = robust_get(website, timeout=10)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    text = link.get_text(strip=True)
                    if href.startswith("/"):
                        parsed = urlparse(website)
                        href = f"{parsed.scheme}://{parsed.netloc}{href}"
                    if _is_direct_pdf(href) and is_report_link(text or href, href):
                        if href not in [r["url"] for r in search_results]:
                            search_results.append({
                                "title": text or "ESG Report",
                                "url": href,
                                "snippet": "Found on official website",
                            })
        except Exception as e:
            print(f"    Site scan error: {e}")

    # Split candidates into direct PDFs vs landing pages
    direct_pdfs = []   # list of {title, url, snippet}
    landing_pages = [] # list of {title, url, snippet}
    seen_pdf_urls = set()

    for result in search_results:
        url = result["url"]
        if _is_direct_pdf(url) or "pdf" in url.lower():
            if url not in seen_pdf_urls:
                seen_pdf_urls.add(url)
                direct_pdfs.append(result)
        else:
            landing_pages.append(result)

    # Strategy 3: Follow landing pages to find embedded PDFs
    if landing_pages:
        print(f"  Strategy 3: Following {min(len(landing_pages), 5)} landing page(s) for embedded PDFs...")
        for lp in landing_pages[:5]:
            for pdf in find_pdfs_on_page(lp["url"], name):
                if pdf["url"] not in seen_pdf_urls:
                    seen_pdf_urls.add(pdf["url"])
                    direct_pdfs.append({
                        "title": pdf["title"],
                        "url": pdf["url"],
                        "snippet": f"Found on landing page: {lp['url'][:80]}",
                    })
            time.sleep(0.5)
        print(f"  PDF candidates after following pages: {len(direct_pdfs)}")

    # Download all direct-PDF candidates and store in Supabase
    for result in direct_pdfs:
        public_url, file_size = download_and_store_pdf(
            result["url"], symbol, name, result["title"], supabase_client, bucket_name,
        )
        reports.append({
            "title": result["title"],
            "url": result["url"],
            "snippet": result.get("snippet", ""),
            "type": "pdf",
            "report_type": classify_report_type(result["title"], result["url"]),
            "report_year": extract_year(f"{result['title']} {result['url']}"),
            "downloaded": public_url is not None,
            "storage_url": public_url,
            "file_size": file_size,
        })

    # Keep landing pages as webpage records (useful even if no PDF was extractable)
    for lp in landing_pages:
        reports.append({
            "title": lp["title"],
            "url": lp["url"],
            "snippet": lp.get("snippet", ""),
            "type": "webpage",
            "downloaded": False,
        })

    print(f"  Total reports found: {len(reports)}")
    pdfs_stored = sum(1 for r in reports if r.get("downloaded"))
    print(f"  PDFs stored in Supabase: {pdfs_stored}")

    return reports


def save_results(db, company, reports):
    """Save scan results to MongoDB."""
    symbol = company.get("Symbol", "UNK")
    name = company.get("Company Name", "Unknown")
    now = datetime.now(tz=None).strftime("%Y-%m-%d %H:%M:%S")

    for report in reports:
        doc = {
            "symbol": symbol,
            "company_name": name,
            "title": report["title"],
            "url": report["url"],
            "snippet": report.get("snippet", ""),
            "type": report.get("type", "unknown"),
            "report_type": report.get("report_type"),
            "report_year": report.get("report_year"),
            "downloaded": report.get("downloaded", False),
            "storage_url": report.get("storage_url"),
            "file_size": report.get("file_size"),
            "scanned_at": now,
            "source": "batch_scanner",
        }
        db.esg_reports.update_one(
            {"url": report["url"], "symbol": symbol},
            {"$set": doc},
            upsert=True,
        )

    if not reports:
        db.esg_reports.update_one(
            {"symbol": symbol, "type": "scan_marker"},
            {"$set": {
                "symbol": symbol,
                "company_name": name,
                "title": "No reports found",
                "url": "",
                "type": "scan_marker",
                "scanned_at": now,
                "source": "batch_scanner",
            }},
            upsert=True,
        )


def main():
    parser = argparse.ArgumentParser(description="Batch ESG Report Scanner")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of companies per run")
    parser.add_argument("--company", type=str, help="Scan a single company by symbol (e.g. AAPL)")
    args = parser.parse_args()

    print("=" * 60)
    print("ESG Batch Report Scanner")
    print(f"Started: {datetime.now(tz=None).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Connect to MongoDB (metadata)
    mongo_uri = get_mongo_uri()
    if not mongo_uri:
        print("MONGO_URI not found.")
        sys.exit(1)

    try:
        client = connect_mongo(mongo_uri)
        db = client.esg_agent
        print("Connected to MongoDB.")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        sys.exit(1)

    # Connect to Supabase (file storage)
    supa_url, supa_key, bucket_name = get_supabase_config()
    if not supa_url or not supa_key:
        print("SUPABASE_URL / SUPABASE_KEY not found.")
        sys.exit(1)

    # Strip any invisible/non-ASCII chars from credentials
    supa_url = supa_url.strip()
    supa_key = "".join(c for c in supa_key.strip() if ord(c) < 128)
    bucket_name = bucket_name.strip()

    print(f"Key is_ascii={supa_key.isascii()}, key_len={len(supa_key)}")
    supabase_client = create_client(supa_url, supa_key)
    print(f"Connected to Supabase (bucket len={len(bucket_name)}, has_underscore={'_' in bucket_name}).")

    if args.company:
        company = db.companies.find_one({"Symbol": args.company.upper()}, {"_id": 0})
        if not company:
            print(f"Company '{args.company}' not found in database.")
            sys.exit(1)
        batch = [company]
    else:
        batch = get_batch(db, args.batch_size)

    if not batch:
        print("No companies need scanning (all scanned within the last 30 days).")
        client.close()
        return

    print(f"\nBatch: {len(batch)} companies to scan")

    total_reports = 0
    total_pdfs = 0

    for i, company in enumerate(batch):
        print(f"\n[{i+1}/{len(batch)}]", end="")
        try:
            reports = scan_company(company, supabase_client, bucket_name)
            save_results(db, company, reports)
            total_reports += len(reports)
            total_pdfs += sum(1 for r in reports if r.get("downloaded"))
        except Exception as e:
            print(f"  ERROR scanning {company.get('Symbol')}: {e}")
            import traceback
            traceback.print_exc()

        if i < len(batch) - 1:
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"SCAN COMPLETE")
    print(f"Companies scanned: {len(batch)}")
    print(f"Total reports found: {total_reports}")
    print(f"PDFs stored in Supabase: {total_pdfs}")
    print(f"{'='*60}")

    client.close()


if __name__ == "__main__":
    main()
