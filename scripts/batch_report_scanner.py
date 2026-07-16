"""
Batch ESG Report Scanner

Scans ~50 companies per run, finds ESG report URLs, downloads PDFs,
and stores metadata in MongoDB. Designed to run as a daily GitHub Action
that completes a full cycle of all companies over ~11 days.

Usage:
    python scripts/batch_report_scanner.py [--batch-size 50] [--company SYMBOL]
"""

import os
import sys
import time
import json
import argparse
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlparse

import certifi
import requests
import pandas as pd
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import robust_get, is_report_link
from config import USER_AGENTS

DOWNLOAD_DIR = os.environ.get("REPORT_DOWNLOAD_DIR", "downloaded_reports")
SCAN_INTERVAL_DAYS = 30


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


def download_pdf(url, company_symbol, download_dir):
    """Download a PDF and return the local path, or None on failure."""
    try:
        resp = robust_get(url, timeout=30, stream=True)
        if resp.status_code != 200:
            return None

        content_type = resp.headers.get("Content-Type", "").lower()
        if "pdf" not in content_type and "octet-stream" not in content_type:
            resp.close()
            return None

        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) < 50_000:
            resp.close()
            return None

        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"{company_symbol}_{url_hash}.pdf"
        filepath = os.path.join(download_dir, filename)

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(filepath)
        if file_size < 50_000:
            os.remove(filepath)
            return None

        print(f"    Downloaded: {filename} ({file_size / 1024:.0f} KB)")
        return filepath

    except Exception as e:
        print(f"    Download failed: {e}")
        return None


def scan_company(company, download_dir):
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
                    if href.lower().endswith(".pdf") and is_report_link(text or href, href):
                        if href not in [r["url"] for r in search_results]:
                            search_results.append({
                                "title": text or "ESG Report",
                                "url": href,
                                "snippet": "Found on official website",
                            })
        except Exception as e:
            print(f"    Site scan error: {e}")

    # Download PDFs
    for result in search_results:
        url = result["url"]
        if not url.lower().endswith(".pdf") and "pdf" not in url.lower():
            reports.append({
                "title": result["title"],
                "url": url,
                "snippet": result.get("snippet", ""),
                "type": "webpage",
                "downloaded": False,
            })
            continue

        filepath = download_pdf(url, symbol, download_dir)
        reports.append({
            "title": result["title"],
            "url": url,
            "snippet": result.get("snippet", ""),
            "type": "pdf",
            "downloaded": filepath is not None,
            "local_path": filepath,
            "file_size": os.path.getsize(filepath) if filepath else None,
        })

    print(f"  Total reports found: {len(reports)}")
    pdfs_downloaded = sum(1 for r in reports if r.get("downloaded"))
    print(f"  PDFs downloaded: {pdfs_downloaded}")

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
            "downloaded": report.get("downloaded", False),
            "file_size": report.get("file_size"),
            "scanned_at": now,
            "source": "batch_scanner",
        }
        db.esg_reports.update_one(
            {"url": report["url"], "symbol": symbol},
            {"$set": doc},
            upsert=True,
        )

    # Mark company as scanned even if no reports found
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
    print(f"Started: {datetime.now(tz=None).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)

    mongo_uri = get_mongo_uri()
    if not mongo_uri:
        print("MONGO_URI not found. Set it as an environment variable or in .streamlit/secrets.toml")
        sys.exit(1)

    try:
        client = connect_mongo(mongo_uri)
        db = client.esg_agent
        print("Connected to MongoDB.")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        sys.exit(1)

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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
        return

    print(f"\nBatch: {len(batch)} companies to scan")
    print(f"Download directory: {os.path.abspath(DOWNLOAD_DIR)}")

    total_reports = 0
    total_pdfs = 0

    for i, company in enumerate(batch):
        print(f"\n[{i+1}/{len(batch)}]", end="")
        try:
            reports = scan_company(company, DOWNLOAD_DIR)
            save_results(db, company, reports)
            total_reports += len(reports)
            total_pdfs += sum(1 for r in reports if r.get("downloaded"))
        except Exception as e:
            print(f"  ERROR scanning {company.get('Symbol')}: {e}")
            import traceback
            traceback.print_exc()

        # Rate limiting between companies
        if i < len(batch) - 1:
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"SCAN COMPLETE")
    print(f"Companies scanned: {len(batch)}")
    print(f"Total reports found: {total_reports}")
    print(f"PDFs downloaded: {total_pdfs}")
    print(f"{'='*60}")

    client.close()


if __name__ == "__main__":
    main()
