"""Unit tests for shared utility functions."""

import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import (
    get_significant_token,
    is_likely_official_domain,
    clean_title,
    extract_year,
    is_report_link,
    filter_relevant_links,
    is_text_generic,
    clean_link_text,
)


class TestGetSignificantToken:
    def test_simple_company(self):
        assert get_significant_token("Apple Inc") == "apple"

    def test_company_with_stopwords(self):
        assert get_significant_token("The Gap Inc") == "gap"

    def test_company_all_stopwords(self):
        # Falls back to first word
        assert get_significant_token("The Inc") == "the"

    def test_company_with_punctuation(self):
        assert get_significant_token("S.P. Global Corp") == "global"

    def test_single_word(self):
        assert get_significant_token("Tesla") == "tesla"

    def test_holdings_stripped(self):
        assert get_significant_token("Berkshire Holdings Group") == "berkshire"


class TestIsLikelyOfficialDomain:
    def test_blocks_wikipedia(self):
        assert is_likely_official_domain("https://en.wikipedia.org/wiki/Apple", "Apple") is False

    def test_blocks_bloomberg(self):
        assert is_likely_official_domain("https://www.bloomberg.com/quote/AAPL", "Apple") is False

    def test_allows_corporate_domain(self):
        assert is_likely_official_domain("https://www.apple.com/environment/", "Apple") is True

    def test_allows_sustainability_subdomain(self):
        assert is_likely_official_domain("https://sustainability.google.com/", "Google") is True

    def test_invalid_url(self):
        assert is_likely_official_domain("not-a-url", "Test") is True  # No domain to block

    def test_blocks_yahoo_finance(self):
        assert is_likely_official_domain("https://finance.yahoo.com/quote/AAPL", "Apple") is False

    def test_blocks_seekingalpha(self):
        assert is_likely_official_domain("https://seekingalpha.com/symbol/AAPL", "Apple") is False


class TestCleanTitle:
    def test_removes_sketch_artifacts(self):
        result = clean_title("2024 Report PDFCreated with Sketch. backgroundLayer")
        assert "Sketch" not in result
        assert "backgroundLayer" not in result
        assert "2024 Report" in result

    def test_returns_fallback_for_empty(self):
        assert clean_title("") == "ESG Report"
        assert clean_title(None) == "ESG Report"

    def test_returns_fallback_for_short(self):
        assert clean_title("Hi") == "ESG Report"

    def test_collapses_whitespace(self):
        assert clean_title("  2024    ESG   Report  ") == "2024 ESG Report"

    def test_preserves_good_title(self):
        assert clean_title("Apple 2024 Sustainability Report") == "Apple 2024 Sustainability Report"


class TestExtractYear:
    def test_finds_year(self):
        assert extract_year("2024 ESG Report") == "2024"

    def test_finds_first_year(self):
        assert extract_year("2023-2024 Report") == "2023"

    def test_no_year(self):
        assert extract_year("ESG Report") is None

    def test_year_in_url(self):
        assert extract_year("https://example.com/reports/2025/sustainability.pdf") == "2025"

    def test_ignores_non_year_numbers(self):
        assert extract_year("Report 1999") is None  # Out of 2020-2030 range

    def test_year_2030(self):
        assert extract_year("Goals for 2030") == "2030"


class TestIsReportLink:
    def test_sustainability_report(self):
        assert is_report_link("2024 Sustainability Report", "https://example.com/report.pdf") is True

    def test_esg_report(self):
        assert is_report_link("ESG Annual Report", "https://example.com/esg.pdf") is True

    def test_rejects_policy(self):
        assert is_report_link("Privacy Policy", "https://example.com/policy.pdf") is False

    def test_rejects_earnings(self):
        assert is_report_link("Q3 Earnings Presentation", "https://example.com/q3.pdf") is False

    def test_rejects_charter(self):
        assert is_report_link("Board Charter", "https://example.com/charter.pdf") is False

    def test_rejects_no_keywords(self):
        assert is_report_link("Click here to download", "https://example.com/file.pdf") is False

    def test_integrated_report(self):
        assert is_report_link("Integrated Annual Report 2024", "https://example.com/ir.pdf") is True

    def test_csr_report(self):
        assert is_report_link("CSR Report", "https://example.com/csr.pdf") is True


class TestFilterRelevantLinks:
    def _make_link(self, url, text="Report", score=3):
        return {"url": url, "text": text, "score": score}

    def test_separates_pdfs(self):
        links = [
            self._make_link("https://example.com/report.pdf"),
            self._make_link("https://example.com/sustainability"),
        ]
        pdfs, non_pdfs = filter_relevant_links(links)
        assert len(pdfs) == 1
        assert len(non_pdfs) == 1

    def test_pdfs_only_mode(self):
        links = [
            self._make_link("https://example.com/report.pdf"),
            self._make_link("https://example.com/sustainability"),
        ]
        pdfs, non_pdfs = filter_relevant_links(links, pdfs_only=True)
        assert len(pdfs) == 1
        assert len(non_pdfs) == 0

    def test_filters_low_score_non_pdfs(self):
        links = [
            self._make_link("https://example.com/page", "Sustainability Report", score=3),
            self._make_link("https://example.com/other", "Some link", score=1),
        ]
        pdfs, non_pdfs = filter_relevant_links(links)
        assert len(non_pdfs) == 1
        assert non_pdfs[0]["text"] == "Sustainability Report"

    def test_filters_header_footer_junk(self):
        links = [
            self._make_link("https://example.com/careers", "Careers", score=2),
            self._make_link("https://example.com/report", "ESG Report 2024", score=3),
        ]
        pdfs, non_pdfs = filter_relevant_links(links)
        assert len(non_pdfs) == 1
        assert non_pdfs[0]["text"] == "ESG Report 2024"


class TestIsTextGeneric:
    def test_empty_is_generic(self):
        assert is_text_generic("") is True
        assert is_text_generic(None) is True

    def test_short_is_generic(self):
        assert is_text_generic("PDF") is True

    def test_download_is_generic(self):
        assert is_text_generic("Download PDF") is True

    def test_report_keyword_is_generic(self):
        # "report" is in GENERIC_LINK_TERMS, so any text containing it is flagged
        assert is_text_generic("Apple 2024 Sustainability Report") is True

    def test_specific_company_name_not_generic(self):
        assert is_text_generic("Apple Environmental Commitment 2024") is False


class TestCleanLinkText:
    def test_removes_new_window(self):
        result = clean_link_text("Report (opens in a new window)")
        assert "opens in" not in result
        assert "Report" in result

    def test_removes_new_tab(self):
        result = clean_link_text("Download opens in new tab")
        assert "opens in" not in result

    def test_collapses_whitespace(self):
        result = clean_link_text("  Too   many   spaces  ")
        assert result == "Too many spaces"
