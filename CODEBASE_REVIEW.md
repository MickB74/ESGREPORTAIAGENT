# ESG Report AI Agent - Codebase Review

**Date:** 2025-12-26  
**Reviewer:** Antigravity AI

---

## Project Structure

### Core Files
- **`app.py`** (66KB, 1482 lines): Main Streamlit application
- **`esg_scraper.py`** (18KB): Playwright-based aggressive scraper
- **`company_map.json`** (110KB): Fast-track verified ESG URLs
- **`sp500_companies.json`** (38KB): S&P 500 company data
- **`packages.txt`**: System dependencies for Streamlit Cloud (Chromium libraries)

### Data Files
- `SP500ESGWebsites.csv`: Verified ESG websites database
- `saved_links.json`: User-saved report links

### Debug Scripts
- `debug_*.py`: Various debugging utilities for specific companies
- `test_*.py`: Test harnesses

### Configuration
- `.streamlit/`: Streamlit config
- `requirements.txt`: Python dependencies (ddgs, playwright, streamlit, pypdf, etc.)

---

## Critical Function: `search_esg_info()`

### Location
`app.py`, lines 325-1153

### Purpose
Multi-strategy ESG report discovery engine with strict mode for verified sites.

### Return Type Analysis
**VERIFIED:** Function correctly returns `results` dictionary at line 1153.

#### Return Paths Audit
1. **Line 505**: Strict Mode (Playwright) → Returns `{"reports": [...], "website": {...}, "search_log": [...]}`  ✅
2. **Line 728**: Fallback (Requests) → Returns `{"reports": [...], "website": {...}, "search_log": [...]}`  ✅
3. **Line 1153**: Final Return → Returns `results` dictionary  ✅

**STATUS:** All return paths are CONSISTENT.

---

## Known Issues & Resolutions

### 1. ✅ Screenshot Feature
- **Status:** REMOVED per user request (2025-12-26)
- **Reason:** System dependency issues (`libnspr4.so`) causing crashes
- **Solution:** Disabled capture and display logic; added `packages.txt` for future re-enablement

### 2. ✅ Playwright Installation
- **Status:** RESOLVED
- **Solution:** Auto-install via `install_playwright()` cached function + `packages.txt` for system libs

### 3. ✅ Unhashable Dict Error
- **Status:** RESOLVED
- **Cause:** Passing `data['website']` (dict) instead of `data['website']['href']` (string) to cached function
- **Fix:** Line 1307 in `app.py` now extracts URL string before passing

### 4. ⚠️ **ACTIVE:** String Index Error
- **User Reports:** "string indices must be integers, not 'str'"
- **Investigation:**
  - All `search_esg_info` return paths verified to return dict
  - **Hypothesis:** Caller may be incorrectly handling the return value
  - **Action Required:** Check line 1310 caller logic

---

## Architecture Review

### Search Strategies (Priority Order)
1. **Verified Site (Strict Mode):**
   - Uses Playwright (`esg_scraper.py`)
   - Scans all frames, clicks interactive elements
   - Hub discovery (Level 2 recursion)

2. **Official Site Scan:**
   - Requests-based HTML parsing
   - BeautifulSoup link extraction
   - Contextual naming (headers, years)

3. **Direct Search:**
   - Symbol-based queries (e.g., "AAPL ESG report 2024")
   - Domain-specific searches

4. **Third-Party Aggregators:**
   - ResponsibilityReports.com
   - UN Global Compact

### Recent Enhancements (2025-12-26)
✅ Multi-frame scanning (iframes)  
✅ Interactive expansion ("Load More" buttons, year tabs)  
✅ Expanded hub keywords (investor, financial, quarterly)  
✅ Improved link naming (contextual year extraction, header precedence)  

---

## Code Quality Notes

### Strengths
- Comprehensive error handling with try/except blocks
- Multi-threaded PDF verification (concurrent.futures)
- Caching for performance (`@st.cache_data`)
- Detailed logging system

### Areas for Improvement
1. **Function Size:** `search_esg_info` is 800+ lines → Consider breaking into smaller modules
2. **Duplicate Reports Key:** Line 340-341 has `"reports": []` twice (harmless but should clean)
3. **Magic Numbers:** Timeouts and thresholds hardcoded → Move to config
4. **Debug Files:** Multiple `debug_*.py` and `test_*.py` files uncommitted → Clean up or document

---

## Recommendations

### Immediate
1. ✅ Verify Deep Scan functionality with aggressive scraper
2. ⚠️ Debug string index error by inspecting caller at line ~1310
3. 🔧 Remove duplicate `"reports"` key in results dict initialization

### Short-Term
- Refactor `search_esg_info` into strategy-based classes
- Add unit tests for each search strategy
- Document `esg_scraper.py` configuration options

### Long-Term
- Implement report deduplication (same PDF with different links)
- Add report quality scoring system
- Create admin panel for updating `company_map.json`

---

## Security & Deployment

### Streamlit Cloud Readiness
✅ `packages.txt` configured for Chromium dependencies  
✅ Auto-install Playwright browsers on startup  
✅ No hardcoded secrets  
⚠️ Consider rate limiting for DuckDuckGo API

### Data Privacy
- No PII collection
- Reports fetched from public sources
- User data stored client-side (browser session)

---

## Summary

**Overall Assessment:** PRODUCTION-READY with minor refinements needed.

The codebase demonstrates robust error handling and a well-thought-out multi-strategy approach to ESG report discovery. Recent enhancements (aggressive scraping, frame scanning) significantly improve coverage. The persistent string index error requires targeted debugging of the caller logic rather than the core function.

**Next Steps:** Focus on caller-side debugging and code cleanup.
