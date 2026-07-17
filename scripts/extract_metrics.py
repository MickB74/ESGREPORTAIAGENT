"""
ESG Metric Extraction

Reads ESG report PDFs already stored in Supabase, sends each to Claude
(reading both text and charts via PDF vision), extracts a standardized
set of ESG metrics as structured JSON, and stores them in MongoDB
(collection: esg_metrics) for cross-company benchmarking.

Usage:
    python scripts/extract_metrics.py [--company AAPL] [--limit 5] [--force]

Requires:
    ANTHROPIC_API_KEY  (env var or .streamlit/secrets.toml)
    SUPABASE_URL / SUPABASE_KEY / SUPABASE_BUCKET
    MONGO_URI
"""

import os
import sys
import json
import argparse
from datetime import datetime

import certifi
from pymongo import MongoClient
from supabase import create_client
import anthropic

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Default extraction model. Override with EXTRACT_MODEL env var.
# claude-sonnet-5 is roughly half the cost of opus for this vision workload.
DEFAULT_MODEL = os.environ.get("EXTRACT_MODEL", "claude-opus-4-8")

# Per-1M-token pricing for cost projection (input, output)
PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

# The standardized metric schema every report is extracted into.
METRIC_SCHEMA = {
    "type": "object",
    "properties": {
        "reporting_year": {"type": ["integer", "null"], "description": "The fiscal/calendar year the reported data covers"},
        "scope1_emissions_tco2e": {"type": ["number", "null"], "description": "Scope 1 GHG emissions in metric tons CO2 equivalent"},
        "scope2_emissions_tco2e": {"type": ["number", "null"], "description": "Scope 2 GHG emissions (market-based if available) in tCO2e"},
        "scope3_emissions_tco2e": {"type": ["number", "null"], "description": "Scope 3 GHG emissions in tCO2e"},
        "renewable_energy_pct": {"type": ["number", "null"], "description": "Percentage of electricity/energy from renewable sources"},
        "net_zero_target_year": {"type": ["integer", "null"], "description": "Target year for net-zero emissions"},
        "interim_target_pct": {"type": ["number", "null"], "description": "Interim emissions reduction target percentage"},
        "interim_target_year": {"type": ["integer", "null"], "description": "Year the interim reduction target applies to"},
        "water_withdrawal_m3": {"type": ["number", "null"], "description": "Total water withdrawal in cubic meters"},
        "waste_diverted_pct": {"type": ["number", "null"], "description": "Percentage of waste diverted from landfill / recycled"},
        "board_diversity_pct": {"type": ["number", "null"], "description": "Percentage of board that is women or underrepresented groups"},
        "workforce_diversity_pct": {"type": ["number", "null"], "description": "Percentage of workforce that is women or underrepresented groups"},
        "reporting_framework": {"type": ["string", "null"], "description": "Reporting framework(s) used, e.g. GRI, SASB, TCFD"},
        "data_notes": {"type": "string", "description": "Brief notes: which figures came from charts vs text/tables, and any caveats"},
    },
    "required": [
        "reporting_year", "scope1_emissions_tco2e", "scope2_emissions_tco2e",
        "scope3_emissions_tco2e", "renewable_energy_pct", "net_zero_target_year",
        "interim_target_pct", "interim_target_year", "water_withdrawal_m3",
        "waste_diverted_pct", "board_diversity_pct", "workforce_diversity_pct",
        "reporting_framework", "data_notes",
    ],
    "additionalProperties": False,
}

EXTRACTION_PROMPT = """You are an ESG data analyst. Extract standardized sustainability metrics from this company's ESG/sustainability report.

Read BOTH the text/tables AND the charts and infographics — much of the quantitative data in these reports is only presented visually. When a value appears in a chart, read it as accurately as you can from the axis and data labels.

Rules:
- Report the most recent year's figure for each metric.
- Use the exact units specified in the schema (convert if the report uses different units).
- If a metric is not disclosed anywhere in the report, return null for it — do not guess or estimate a value that isn't supported by the report.
- In data_notes, briefly say which figures you read from charts (less certain) vs text/tables (more certain), and note any unit conversions or ambiguities.

Extract the metrics now."""


def _load_secret(key, default=None):
    val = os.environ.get(key)
    if val:
        return val
    try:
        import toml
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml")
        if os.path.exists(path):
            data = toml.load(path)
            return data.get(key, default)
    except Exception:
        pass
    return default


def connect_mongo(uri):
    client = MongoClient(uri, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
    client.admin.command("ping")
    return client


def get_pdfs_to_process(db, supa, bucket, company=None, limit=None, force=False):
    """Find downloaded PDF reports in MongoDB that have a Supabase storage URL."""
    query = {"type": "pdf", "downloaded": True, "storage_url": {"$ne": None}}
    if company:
        query["symbol"] = company.upper()

    reports = list(db.esg_reports.find(query, {"_id": 0}))

    # Skip ones already extracted unless --force
    if not force:
        done = set(db.esg_metrics.distinct("url"))
        reports = [r for r in reports if r.get("url") not in done]

    if limit:
        reports = reports[:limit]
    return reports


def download_pdf_bytes(supa, bucket, storage_url):
    """Download PDF bytes from Supabase using the storage path parsed from the public URL."""
    # public_url looks like: .../object/public/<bucket>/<path>
    marker = f"/public/{bucket}/"
    idx = storage_url.find(marker)
    if idx == -1:
        return None
    path = storage_url[idx + len(marker):]
    return supa.storage.from_(bucket).download(path)


def extract_metrics(client, model, pdf_bytes, company_name):
    """Send a PDF to Claude and get back structured ESG metrics + token usage."""
    uploaded = client.beta.files.upload(
        file=("report.pdf", pdf_bytes, "application/pdf"),
        betas=["files-api-2025-04-14"],
    )

    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=4096,
            betas=["files-api-2025-04-14"],
            output_config={"format": {"type": "json_schema", "schema": METRIC_SCHEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "file", "file_id": uploaded.id}},
                    {"type": "text", "text": f"Company: {company_name}\n\n{EXTRACTION_PROMPT}"},
                ],
            }],
        )
    finally:
        try:
            client.beta.files.delete(uploaded.id, betas=["files-api-2025-04-14"])
        except Exception:
            pass

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    metrics = json.loads(text)
    return metrics, response.usage


def project_costs(input_tokens, output_tokens):
    """Project the cost of this extraction across models."""
    lines = []
    for m, (in_price, out_price) in PRICING.items():
        cost = input_tokens / 1_000_000 * in_price + output_tokens / 1_000_000 * out_price
        lines.append(f"    {m}: ${cost:.4f}/report  ->  500 reports = ${cost*500:.0f}  (batch -50% = ${cost*500*0.5:.0f})")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract ESG metrics from stored PDFs")
    parser.add_argument("--company", type=str, help="Extract a single company by symbol")
    parser.add_argument("--limit", type=int, help="Max number of reports to process")
    parser.add_argument("--force", action="store_true", help="Re-extract even if already done")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Extraction model")
    args = parser.parse_args()

    print("=" * 60)
    print("ESG Metric Extraction")
    print(f"Model: {args.model}")
    print(f"Started: {datetime.now(tz=None).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    api_key = _load_secret("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not found (set env var or add to .streamlit/secrets.toml).")
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    mongo_uri = _load_secret("MONGO_URI")
    supa_url = _load_secret("SUPABASE_URL", "").strip()
    supa_key = "".join(c for c in (_load_secret("SUPABASE_KEY", "") or "").strip() if ord(c) < 128)
    bucket = (_load_secret("SUPABASE_BUCKET", "esg_reports") or "esg_reports").strip()

    if not (mongo_uri and supa_url and supa_key):
        print("Missing MONGO_URI / SUPABASE_URL / SUPABASE_KEY.")
        sys.exit(1)

    mongo = connect_mongo(mongo_uri)
    db = mongo.esg_agent
    supa = create_client(supa_url, supa_key)
    print("Connected to MongoDB and Supabase.\n")

    reports = get_pdfs_to_process(db, supa, bucket, args.company, args.limit, args.force)
    if not reports:
        print("No PDFs to process (all extracted, or none match).")
        mongo.close()
        return

    print(f"{len(reports)} report(s) to process.\n")

    total_in = total_out = 0
    for i, report in enumerate(reports):
        symbol = report.get("symbol", "?")
        name = report.get("company_name", symbol)
        print(f"[{i+1}/{len(reports)}] {name} ({symbol})")

        try:
            pdf_bytes = download_pdf_bytes(supa, bucket, report["storage_url"])
            if not pdf_bytes:
                print("    Could not download PDF from Supabase. Skipping.")
                continue

            print(f"    PDF size: {len(pdf_bytes)/1024/1024:.1f} MB — extracting...")
            metrics, usage = extract_metrics(client, args.model, pdf_bytes, name)

            total_in += usage.input_tokens
            total_out += usage.output_tokens

            db.esg_metrics.update_one(
                {"url": report["url"]},
                {"$set": {
                    "symbol": symbol,
                    "company_name": name,
                    "url": report["url"],
                    "storage_url": report.get("storage_url"),
                    "metrics": metrics,
                    "model": args.model,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "extracted_at": datetime.now(tz=None).strftime("%Y-%m-%d %H:%M:%S"),
                }},
                upsert=True,
            )

            print(f"    Tokens: {usage.input_tokens:,} in / {usage.output_tokens:,} out")
            filled = sum(1 for k, v in metrics.items() if k != "data_notes" and v is not None)
            print(f"    Metrics found: {filled}/{len(metrics)-1}")
            print(f"    e.g. Scope1={metrics.get('scope1_emissions_tco2e')}, "
                  f"Renewable%={metrics.get('renewable_energy_pct')}, "
                  f"NetZero={metrics.get('net_zero_target_year')}")

        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("EXTRACTION COMPLETE")
    print(f"Reports processed: {len(reports)}")
    print(f"Total tokens: {total_in:,} in / {total_out:,} out")
    if reports:
        avg_in = total_in // max(1, len(reports))
        avg_out = total_out // max(1, len(reports))
        print(f"\nProjected cost per report (avg {avg_in:,} in / {avg_out:,} out):")
        print(project_costs(avg_in, avg_out))
    print("=" * 60)

    mongo.close()


if __name__ == "__main__":
    main()
