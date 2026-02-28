"""
Centralized configuration for the ESG Report AI Agent.
All magic numbers, keyword lists, and thresholds in one place.
"""

# --- Timeouts (milliseconds for Playwright, seconds for requests) ---
PLAYWRIGHT_NAV_TIMEOUT_MS = 90000
PLAYWRIGHT_HUB_TIMEOUT_MS = 45000
PLAYWRIGHT_SCREENSHOT_TIMEOUT_MS = 10000
PLAYWRIGHT_CLICK_TIMEOUT_MS = 3000
PLAYWRIGHT_NETWORKIDLE_TIMEOUT_MS = 5000
PLAYWRIGHT_COOKIE_TIMEOUT_MS = 2000

REQUESTS_TIMEOUT_S = 10
REQUESTS_HUB_TIMEOUT_S = 6
REQUESTS_DOWNLOAD_TIMEOUT_S = 30

# --- Page Load Delays (seconds) ---
LAZY_LOAD_WAIT_S = 2
PAGE_SETTLE_WAIT_S = 3
DYNAMIC_CONTENT_WAIT_S = 5

# --- Size Thresholds (bytes) ---
MIN_PDF_SIZE_BYTES = 50_000           # 50KB - skip tiny "PDFs"
SKIP_VERIFY_SIZE_BYTES = 20_971_520   # 20MB - assume large files are valid

# --- Search Limits ---
MAX_REPORTS_TOTAL = 8
MAX_HUBS_TO_VISIT = 5
MAX_SCAN_URLS_STRICT = 1
MAX_SCAN_URLS_NORMAL = 3
MAX_SEARCH_RESULTS = 8
MAX_DEEP_SCAN_REPORTS = 20
THREAD_POOL_WORKERS = 3

# --- Scoring ---
MIN_LINK_SCORE = 1
MIN_NON_PDF_SCORE = 2
PDF_SCORE_BOOST = 3

# --- Browser Configuration ---
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1920, "height": 1080}
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-http2",
    "--no-sandbox",
    "--disable-setuid-sandbox",
]

# --- Keyword Lists ---
REPORT_KEYWORDS = [
    "report", "esg", "sustainability", "csr", "annual", "impact",
    "environmental", "social", "governance", "climate", "carbon",
    "diversity", "inclusion", "responsibility", "stewardship",
    "citizenship", "community", "ethics", "transparency",
    "2024", "2025", "2023", "tcfd",
]

NEGATIVE_KEYWORDS = [
    "policy", "charter", "code of conduct", "guidelines", "framework",
    "presentation", "investor presentation", "earnings", "quarterly",
    "q1", "q2", "q3", "slide", "webcast",
]

EXCLUDE_KEYWORDS = [
    "login", "career", "job", "apply", "search", "contact",
    "privacy policy", "terms", "cookie", "faq", "about us",
]

HUB_KEYWORDS = [
    "archive", "library", "downloads", "all reports", "past reports",
    "previous reports", "resources", "investor", "financial", "filing",
    "result", "quarterly", "annual", "sustainability", "esg",
]

HEADER_FOOTER_TERMS = [
    "home", "about", "contact", "careers", "privacy", "terms",
    "cookie", "sitemap", "search", "logo", "menu", "nav",
]

RELEVANT_LINK_KEYWORDS = [
    "report", "sustainability", "esg", "transparency", "responsibility",
    "governance", "annual", "impact", "climate", "diversity", "disclosure",
]

GENERIC_LINK_TERMS = [
    "download", "pdf", "click here", "read more", "view", "report",
    "file", "link", "learn more", "see more", "details", "here",
    "more info", "accessibility", "opens in",
]

REPORT_VERIFICATION_KEYWORDS = [
    "report", "sustainability", "esg", "annual", "review", "fiscal", "summary",
]

# --- Domain Block List ---
BLOCKED_DOMAINS = [
    "wikipedia.org", "bloomberg.com", "reuters.com", "yahoo.com",
    "finance.yahoo.com", "wsj.com", "cnbc.com", "forbes.com",
    "investopedia.com", "morningstar.com", "marketwatch.com",
    "motleyfool.com", "seekingalpha.com", "barrons.com",
    "bing.com",
]

# --- Company Name Stopwords ---
COMPANY_STOPWORDS = [
    "the", "inc", "corp", "corporation", "company", "ltd", "limited",
    "group", "holdings", "plc", "nv", "sa", "ag",
]

# --- Title Cleaning ---
JUNK_PHRASES = [
    "PDFCreated with Sketch.",
    "backgroundLayer",
    "Created with Sketch",
    "Shape",
    "Path",
]

JUNK_PATTERNS = [
    r"\(opens in (?:a )?new (?:window|tab)\)",
    r"opens in (?:a )?new (?:window|tab)",
    r"\[read more\]",
    r"►", r"◄", r"📄",
]

# --- Playwright "Load More" Selectors ---
EXPAND_SELECTORS = [
    "button:has-text('Show More')",
    "button:has-text('Load More')",
    "button:has-text('View All')",
    "a:has-text('Show More')",
    "a:has-text('Load More')",
    "div[role='button']:has-text('Show More')",
    "div[onclick]:has-text('Show More')",
]
