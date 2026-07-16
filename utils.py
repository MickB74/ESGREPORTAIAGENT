"""
Shared utility functions for ESG Report AI Agent.
Eliminates duplication between app.py and esg_scraper.py.
"""

import re
import random
import time
import requests
import certifi
from urllib.parse import urlparse
from config import (
    COMPANY_STOPWORDS, JUNK_PHRASES, BLOCKED_DOMAINS,
    GENERIC_LINK_TERMS, JUNK_PATTERNS,
    USER_AGENTS, REQUEST_HEADERS_BASE, MAX_RETRIES, RETRY_BACKOFF_S,
)


def get_significant_token(name):
    """Returns the most significant part of a company name for verification."""
    parts = name.lower().replace(".", "").replace(",", "").split()
    significant = [p for p in parts if p not in COMPANY_STOPWORDS and len(p) > 2]
    if significant:
        return significant[0]
    return name.split()[0].lower()


def is_likely_official_domain(url, company_name):
    """Check if a domain is likely an official corporate site (not a news/finance site)."""
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return False
    if any(b in domain for b in BLOCKED_DOMAINS):
        return False
    return True


def clean_title(text):
    """Clean scraped titles by removing SVG/sketch artifacts and junk."""
    if not text:
        return "ESG Report"

    for junk in JUNK_PHRASES:
        text = text.replace(junk, " ")

    text = " ".join(text.split())

    if len(text) < 5:
        return "ESG Report"

    return text


def extract_year(text):
    """Extract 4-digit year (2020-2030) from text."""
    years = re.findall(r"\b(202[0-9]|203[0])\b", str(text))
    return years[0] if years else None


def clean_link_text(text, junk_patterns=None):
    """Remove junk patterns (opens in new window, etc.) from link text."""
    if junk_patterns is None:
        junk_patterns = JUNK_PATTERNS
    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def is_text_generic(text):
    """Check if link text is too generic to be useful."""
    if not text:
        return True
    return any(term in text.lower() for term in GENERIC_LINK_TERMS) or len(text) < 4


def is_report_link(text, url):
    """Determine if a link is likely an ESG report based on text and URL keywords."""
    text_lower = text.lower()

    negative_terms = [
        "policy", "charter", "code of conduct", "guidelines", "framework",
        "presentation", "investor presentation", "earnings", "quarterly",
        "q1", "q2", "q3", "slide", "webcast",
    ]
    if any(term in text_lower for term in negative_terms):
        return False

    has_report_keyword = any(
        w in text_lower
        for w in ["report", "sustainability", "esg", "annual", "integrated", "csr"]
    )
    return has_report_keyword


def filter_relevant_links(links, pdfs_only=False):
    """
    Shared filtering logic for scraper results.
    Separates PDFs from non-PDFs and filters non-PDFs for relevance.
    Returns (pdf_links, relevant_non_pdfs).
    """
    from config import HEADER_FOOTER_TERMS, RELEVANT_LINK_KEYWORDS, MIN_NON_PDF_SCORE

    pdf_links = [l for l in links if l["url"].lower().endswith(".pdf")]
    non_pdf_links = [l for l in links if not l["url"].lower().endswith(".pdf")]

    if pdfs_only:
        return pdf_links, []

    relevant_non_pdfs = [
        l for l in non_pdf_links
        if (
            l.get("score", 0) >= MIN_NON_PDF_SCORE
            and not (
                any(term in l.get("text", "").lower() for term in HEADER_FOOTER_TERMS)
                and not any(kw in l.get("text", "").lower() for kw in RELEVANT_LINK_KEYWORDS)
            )
        )
    ]

    return pdf_links, relevant_non_pdfs


def robust_get(url, timeout=10, stream=False):
    """
    Make an HTTP GET with rotating user-agents, realistic headers, and retry
    with exponential backoff on 403/429/5xx responses.
    """
    headers = {**REQUEST_HEADERS_BASE, "User-Agent": random.choice(USER_AGENTS)}
    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url, headers=headers, timeout=timeout,
                stream=stream, verify=certifi.where(),
            )
            if resp.status_code in (403, 429, 503):
                wait = RETRY_BACKOFF_S * (2 ** attempt) + random.uniform(0.5, 1.5)
                print(f"[robust_get] {resp.status_code} on {url}, retrying in {wait:.1f}s")
                time.sleep(wait)
                headers["User-Agent"] = random.choice(USER_AGENTS)
                continue
            return resp
        except requests.exceptions.SSLError:
            try:
                resp = requests.get(
                    url, headers=headers, timeout=timeout, stream=stream,
                )
                return resp
            except Exception as e:
                last_exc = e
        except Exception as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_S * (2 ** attempt))
    raise last_exc or requests.exceptions.ConnectionError(f"Failed after {MAX_RETRIES + 1} attempts: {url}")
