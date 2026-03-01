"""Tests to verify config.py constants are valid and consistent."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    REPORT_KEYWORDS, EXCLUDE_KEYWORDS, HUB_KEYWORDS,
    BLOCKED_DOMAINS, COMPANY_STOPWORDS, BROWSER_ARGS,
    USER_AGENT, VIEWPORT, EXPAND_SELECTORS,
    MIN_PDF_SIZE_BYTES, SKIP_VERIFY_SIZE_BYTES,
    PLAYWRIGHT_NAV_TIMEOUT_MS, REQUESTS_TIMEOUT_S,
    GENERIC_LINK_TERMS, JUNK_PATTERNS, JUNK_PHRASES,
    HEADER_FOOTER_TERMS, RELEVANT_LINK_KEYWORDS,
)


class TestConfigIntegrity:
    def test_report_keywords_are_lowercase(self):
        for kw in REPORT_KEYWORDS:
            assert kw == kw.lower(), f"Keyword '{kw}' should be lowercase"

    def test_exclude_keywords_are_lowercase(self):
        for kw in EXCLUDE_KEYWORDS:
            assert kw == kw.lower(), f"Keyword '{kw}' should be lowercase"

    def test_blocked_domains_are_lowercase(self):
        for d in BLOCKED_DOMAINS:
            assert d == d.lower(), f"Domain '{d}' should be lowercase"

    def test_no_duplicate_report_keywords(self):
        assert len(REPORT_KEYWORDS) == len(set(REPORT_KEYWORDS))

    def test_no_duplicate_blocked_domains(self):
        assert len(BLOCKED_DOMAINS) == len(set(BLOCKED_DOMAINS))

    def test_size_thresholds_ordered(self):
        assert MIN_PDF_SIZE_BYTES < SKIP_VERIFY_SIZE_BYTES

    def test_timeouts_positive(self):
        assert PLAYWRIGHT_NAV_TIMEOUT_MS > 0
        assert REQUESTS_TIMEOUT_S > 0

    def test_viewport_has_dimensions(self):
        assert "width" in VIEWPORT
        assert "height" in VIEWPORT
        assert VIEWPORT["width"] > 0
        assert VIEWPORT["height"] > 0

    def test_user_agent_not_empty(self):
        assert len(USER_AGENT) > 20

    def test_browser_args_are_strings(self):
        for arg in BROWSER_ARGS:
            assert isinstance(arg, str)
            assert arg.startswith("--")

    def test_expand_selectors_not_empty(self):
        assert len(EXPAND_SELECTORS) > 0

    def test_keyword_lists_not_empty(self):
        assert len(REPORT_KEYWORDS) > 0
        assert len(EXCLUDE_KEYWORDS) > 0
        assert len(HUB_KEYWORDS) > 0
        assert len(BLOCKED_DOMAINS) > 0
        assert len(GENERIC_LINK_TERMS) > 0
        assert len(JUNK_PATTERNS) > 0
        assert len(JUNK_PHRASES) > 0
        assert len(HEADER_FOOTER_TERMS) > 0
        assert len(RELEVANT_LINK_KEYWORDS) > 0
