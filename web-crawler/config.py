from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
PAGES_DIR = OUTPUT_DIR / "pages"
MANIFEST_PATH = OUTPUT_DIR / "manifest.csv"
ERRORS_PATH = OUTPUT_DIR / "errors.csv"
RESULT_PATH = BASE_DIR / "result.txt"
STATE_PATH = BASE_DIR / "crawl_state.json"

SEED_URL = "https://esam.ir/"
TARGET_PAGES = 10_000
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 2
ALLOW_SUBDOMAINS = True
ALLOWED_DOMAINS = {"esam.ir"}
USER_AGENT = "Mozilla/5.0 (compatible; WebCrawlerBot/1.0; +https://example.invalid)"
MAX_DEPTH = None
