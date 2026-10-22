# Web Crawler Project for esam.ir

## Objective

This project implements a single-threaded Python crawler for the university assignment on information retrieval and search engines. The goal is to save up to 10,000 successful, unique HTML pages from the target domain, while respecting the website's policies, robots rules, and network limits.

A "successful, unique page" means:

- the URL is accepted by the domain policy
- the response is valid HTML
- the page was not already scheduled or saved under the same normalized URL
- the page was saved as a standalone HTML file in the output directory with a readable name such as `1.html`, `2.html`, `3.html`

## GitHub status

This environment does not currently expose a working GitHub integration or repository access to the agent. The workspace is therefore prepared locally, and no repository was created or pushed without explicit user permission. This is a limitation of the runtime environment rather than a code issue.

## Architecture

```text
Seed URL
   |
   v
URL Frontier (FIFO queue)
   |
   +--> UChecker (deduplication + state tracking)
   |
   +--> Fetcher (requests + timeout + rate limit + redirect policy)
   |
   +--> Parser (BeautifulSoup anchor extraction)
   |
   +--> Output Manager (HTML files + manifest + errors log)
   |
   +--> Metrics / result.txt live reporting
```

### Components

- Queue / URL Frontier: FIFO queue for pending URLs, using a unique normalized set to avoid duplicates.
- Fetcher: downloads HTML pages with conservative timeouts and network handling.
- Parser: extracts internal links from HTML and normalizes them before re-queueing.
- UChecker: prevents duplicate scheduling, tracks unique URLs, and applies the domain policy.
- Output Manager: writes HTML pages and a manifest entry for each saved resource.

## Python and library versions

- Python: 3.14.8 (checked in this environment)
- requests: 2.34.2
- beautifulsoup4: 4.15.0
- pytest: 9.1.1

## Installation

### Windows

```powershell
cd "E:\University\t7\جست و جوی وب\HW1\web-crawler"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Linux / macOS

```bash
cd /path/to/web-crawler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Configuration

The important values live in `config.py`:

- `SEED_URL = "https://esam.ir/"`
- `TARGET_PAGES = 10000`
- `REQUEST_TIMEOUT_SECONDS = 20`
- `REQUEST_DELAY_SECONDS = 1.0`
- `ALLOWED_DOMAINS = {"esam.ir"}`
- `ALLOW_SUBDOMAINS = True`
- `USER_AGENT` is a conservative custom user-agent string

The project is intentionally single-threaded and avoids concurrency tools.

## Responsible crawling policy

- Respect `robots.txt` when it is reachable.
- Use a conservative rate of one request per second per host by default.
- Accept only `http` and `https` links.
- Ignore `javascript:`, `mailto:`, `data:`, and fragment-only URLs.
- Reject external domains and similar non-allowed hosts.
- Stop or slow down on `403`, `429`, or repeated network problems.
- Save only HTML responses and reject PDFs, images, CSS, JS, and similar media.
- Do not store secrets, cookies, or sensitive data.

## Output structure

```text
web-crawler/
├── crawler.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
├── result.txt
├── tests/
│   └── test_crawler.py
└── output/
    ├── pages/
    ├── manifest.csv
    └── errors.csv
```

The downloaded HTML files are intentionally not committed by default because the repository should stay lightweight. The `.gitignore` file prevents large output from being tracked. Local artifacts are kept in the `output/` folder, and each saved page is named in a readable sequential pattern such as `1.html`, `2.html`, `3.html`.

## Running the crawler

From the project directory:

```powershell
python crawler.py --max-pages 2
```

Or use the default target count:

```powershell
python crawler.py
```

The script keeps `result.txt` updated while running and writes a final report at the end.

## Tests

Run the automated tests with:

```powershell
python -m pytest -q
```

The current test suite covers:

- relative URL normalization
- fragment removal
- rejecting non-HTTP schemes
- allowed-domain checks
- deduplication of repeated URLs
- HTML link extraction
- HTML vs non-HTML response detection
- manifest creation header setup

## Metrics and result.txt

The tracked counters include:

- `successful_html_pages_saved`
- `urls_processed_attempted`
- `unique_urls_scheduled`
- `links_extracted_total`
- `duplicate_urls_skipped`
- `urls_rejected_by_domain`
- `urls_rejected_by_robots_policy`
- `http_success`
- `http_errors`
- `network_errors_timeouts`
- `non_html_responses`
- `redirects`
- `parser_or_storage_errors`
- `total_errors`
- `queue_length_current`
- `queue_length_at_end`
- `html_output_size_bytes`

Definition of discovered URLs with duplicates:

- `links_extracted_total` = extracted `href` occurrences before deduplication and domain filtering
- `unique_urls_scheduled` = unique normalized URLs added to the queue
- `duplicate_urls_skipped` = repeated URLs that were not queue-added again

## Real results from the latest run

A small smoke crawl was run against the live site with `--max-pages 2`.

Observed results:

- status: `COMPLETED`
- successful HTML pages saved: 2
- URLs attempted: 2
- URLs scheduled (unique): 58
- Total link occurrences extracted (including duplicates): 108
- Duplicate URLs skipped: 40
- HTTP successful responses: 2
- Total errors: 0
- HTML output size: 117,315 bytes (114.57 KB)

This shows the crawler is functioning in a conservative, live environment. A full 10,000-page crawl was not performed in this session because the prompt requires a staged, responsible approach and the project should not bypass site limitations.

## Reproducing the run

1. Activate the virtual environment.
2. Run:
   ```powershell
   python crawler.py --max-pages 2
   ```
3. Review the generated report in `result.txt`.
4. Inspect the manifest in `output/manifest.csv` and any errors in `output/errors.csv`.

## Notes and limitations

- This is a coursework crawler and not a production-grade search engine.
- The project keeps output local for practical repository safety.
- If a full 10,000-page crawl is required by the instructor, it should be run only after a careful site-policy review and with explicit permission to continue beyond the smoke-test stage.
