# Comprehensive Prompt: Implement the Web Crawler Project in Python

## Role and Mission

You are an AI coding agent responsible for designing, implementing, testing, documenting, and preparing a university assignment for the course **Fundamentals of Information Retrieval and Search Engines**.

- **Target website:** `https://esam.ir/`
- **Target:** Save 10,000 successful, unique HTML pages, if technically possible and permitted by the website's policies.
- **Implementation language:** Python
- **Crawler mode:** Single-threaded. Do not use multithreading, multiprocessing, `asyncio`, or parallel requests.
- **Main statistics output:** A text file named `result.txt`, updated while the crawler runs and finalized when it stops.
- **Git repository:** The user's GitHub account. Connecting to GitHub must be your first project action.
- **Website language:** The target website is Persian-language. Account for Persian text, Unicode, right-to-left content, and URL encoding where relevant. Do not translate or alter page content unnecessarily; make any language-specific adjustments only when needed for correct crawling, storage, or reporting.

## 1. First Rule: Connect to GitHub Before Coding

Before creating project files or writing code:

1. Check whether an official GitHub integration/connector is available in your agent environment.
2. If GitHub is not connected, ask the user to connect and authenticate it through the environment's official authentication flow. Never ask for passwords, Personal Access Tokens, or login codes in chat, and never ask the user to place credentials in project files.
3. After connection, inspect the repositories available to you:
   - If the user already has a repository for this project, use it.
   - If no suitable repository exists, ask for the desired repository name and whether it should be public or private. Do not create a public repository without permission.
   - If your environment cannot create a repository or push commits, explain the limitation clearly and prepare the project in the local workspace. Do not claim that GitHub was connected or that anything was pushed if it was not.
4. Once the repository is confirmed, clone/open it and inspect its current status, branch, and files. If it contains existing work, do not delete or overwrite it without good reason; integrate changes carefully.
5. Make meaningful commits and push them to the user's repository if permission and tooling allow. Obtain permission before destructive actions or changing repository visibility.
6. Never commit secrets, tokens, cookies, sessions, `.env` files, or other sensitive information. Add an appropriate `.gitignore` if needed.

**Required order:** GitHub connection and repository review → design and planning → implementation → tests → controlled crawl → documentation and report.

## 2. Requirements from the University Assignment

The crawler must:

- Crawl and download HTML pages from the selected store website/domain.
- Aim to save 10,000 successful, unique HTML pages.
- Store each page's HTML so that its associated URL can be identified.
- Be single-threaded and include at least these components:
  - `Queue` or `URL Frontier`
  - `Fetcher`
  - `Parser`
  - `UChecker` (Unique URL Checker)
- Save only HTML pages in the page-output collection.
- It may include subdomains when discovered, but the domain policy must be explicit and configurable.
- Produce the information required for a presentation of approximately five minutes: architecture, language and platform, crawl runtime, output size, number of discovered URL occurrences including duplicates, queue length at the end, number of errors, and challenges/solutions.

If the website, technical environment, crawling policy, or network errors prevent the crawler from reaching 10,000 pages, report that honestly. Never fabricate results or bypass website restrictions to reach the target.

## 3. Pre-Crawl Checks and Responsible Crawling

Before sending a large number of requests to `esam.ir`:

1. Check `robots.txt` and the website's publicly available terms of use/crawling policy.
2. Use a small number of low-rate requests to inspect access, content types, redirects, HTML structure, and internal links.
3. Configure a conservative request rate. By default, use at most one request per second per host unless the website's policies require a stricter rate. Respect `Crawl-delay` or similar directives when supported by the implementation.
4. If `robots.txt` cannot be fetched or its status is ambiguous, behave conservatively. Stop and ask the user for guidance when needed. Inaccessibility of `robots.txt` is not permission to bypass site policies.
5. Do not bypass login requirements, CAPTCHAs, paywalls, access controls, rate limits, or anti-bot protections. Do not spoof a browser to deceive controls, change IP addresses to continue after blocking, or collect private data.
6. If you receive `403`, `429`, or clear signs of rate limiting, reduce the rate or stop. Respect `Retry-After` for `429` responses.
7. Set request timeouts. Keep retries limited and use conservative backoff for temporary failures.
8. Accept only HTTP/HTTPS links. Do not save files such as images, PDFs, CSS, JavaScript, fonts, or videos in the HTML-page collection.
9. Check redirects carefully. The final destination must comply with the allowed-domain policy. Do not send requests to unexpected external domains.
10. If sensitive or private data is encountered, do not extract or publish it. Store only public HTML needed for the assignment.

If you cannot confidently determine the site's crawling policy, ask the user before a large crawl and run only a small test first.

## 4. Expected Architecture

Build a simple architecture that is easy to explain and defend in class:

1. **Seed URL:** Start at `https://esam.ir/`.
2. **Queue / URL Frontier:** Use a FIFO queue such as `collections.deque` for URLs waiting to be processed.
3. **URL Normalizer:**
   - Convert relative links to absolute URLs with `urllib.parse.urljoin`.
   - Remove fragments with `urldefrag`.
   - Apply limited, safe URL normalization.
   - Do not arbitrarily remove or reorder query strings; they may identify different resources.
   - Accept only `http` and `https` schemes.
4. **URL Filter:**
   - Validate the hostname by parsing it, not by using `startswith`.
   - Permit `esam.ir` and its subdomains only according to an explicit configured policy.
   - Do not accidentally allow similar but unrelated domains such as `esam.ir.example.com`.
   - Make subdomain inclusion/exclusion configurable.
5. **UChecker:**
   - Use a `set` of normalized unique URLs.
   - Register URLs when they are enqueued, not only after downloading, so the same URL is not queued repeatedly.
   - Track URL states separately, for example `scheduled`, `fetched`, `failed`, and `skipped`.
6. **Robots / Politeness Checker:**
   - Check `robots.txt` rules using a clearly identified User-Agent.
   - Enforce a delay between requests to the same host.
   - Since the crawler is single-threaded, do not start the next request until it is allowed by the schedule.
7. **Fetcher:**
   - Use `requests`.
   - Make timeouts configurable.
   - Handle network errors, HTTP errors, redirects, and encoding issues.
   - Re-check the final URL's domain after redirects.
   - Accept a response for storage only if its status is acceptable and its content type indicates HTML.
8. **HTML Content Check:**
   - Inspect `Content-Type`; `text/html` is acceptable.
   - Do not store non-HTML responses in the page collection.
   - If Content-Type is missing or unreliable, define and document a cautious policy rather than assuming the response is HTML.
9. **Parser:**
   - Use `BeautifulSoup` to extract `<a href="...">` links.
   - Ignore empty links and `mailto:`, `javascript:`, `tel:`, `data:`, and fragment-only links.
   - Normalize and filter links, then pass new URLs to UChecker/the queue.
10. **Output Manager:**
    - Save each downloaded HTML page in its own file.
    - Record the original/final URL, status code, content type, byte size, fetch time, and depth in a manifest.
11. **Metrics / Logger:**
    - Track required counters and update `result.txt` throughout execution.
12. **Main Controller:**
    - Manage the single-threaded main loop.
    - Check stopping conditions.
    - Write output and the final report on normal completion or controlled failure.

Avoid unnecessary complexity. For an educational project, clear functions and simple modularity are preferable to a heavyweight architecture.

## 5. Tools and Technical Constraints

Use:

- Python 3
- `requests`
- `beautifulsoup4`
- Standard libraries such as `collections`, `urllib.parse`, `urllib.robotparser`, `pathlib`, `time`, `datetime`, `csv`, `json`, `logging`, `hashlib`, and `argparse`

Do not use Scrapy, Selenium, Playwright, or concurrency tools in the main implementation. The assignment is intended to demonstrate the core crawler components and single-threaded operation.

Create a `requirements.txt`. Document the Python and library versions in the README. If you add another dependency, explain why it is needed.

## 6. Suggested Project Structure

Use the structure below unless the repository already has a suitable organization; do not restructure an existing repository without a good reason.

```text
web-crawler/
├── crawler.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
├── result.txt
└── output/
    ├── pages/
    │   ├── 000001.html
    │   ├── 000002.html
    │   └── ...
    ├── manifest.csv
    └── errors.csv
```

- `crawler.py`: main loop and crawler components.
- `config.py`: seed URL, target count, timeout, request delay, domain policy, and output paths.
- `result.txt`: live and final report.
- `output/pages/`: only successful, accepted HTML files.
- `manifest.csv`: maps each HTML file to its URL and metadata.
- `errors.csv`: records download and processing errors.
- `README.md`: installation, usage, architecture, policies, and results.
- `.gitignore`: prevents large output, caches, virtual environments, and secrets from being committed.

To avoid an excessively large repository, do not commit downloaded HTML pages or other bulky crawl outputs by default. Keep them locally and explain this in the README. Commit code, non-sensitive configuration, a small sample report, and documentation to GitHub. If the instructor requires all crawl output, document a separate, safe handoff method.

## 7. Queue Behavior and Stopping Conditions

Set `TARGET_PAGES = 10000`. This means 10,000 successful, permitted, unique HTML files—not 10,000 requests and not 10,000 extracted links.

- Register the seed as scheduled.
- On each loop iteration, take one URL from the front of the queue.
- Never enqueue or fetch the same normalized URL more than once.
- If the response qualifies, save the HTML and increment `successful_html_pages`.
- Normalize/filter extracted links and enqueue new URLs.
- Stop when 10,000 successful HTML pages have been saved. Do not discard any remaining queue items; record the queue length at the stop point.
- If the queue becomes empty before the target is reached, set the status to `INCOMPLETE_QUEUE_EXHAUSTED`.
- If the user or system stops the crawl, record the stop status and flush the report as far as possible.
- If an unrecoverable error occurs, write the final report and honestly report the error.
- Prevent infinite crawling. Use URL policies and conservative limits to control dynamic URLs and potentially infinite calendar/filter pages.
- Implement `max_depth` or other optional limits only as configurable settings. If enabled, record them in the final report because they may prevent the crawler from reaching 10,000 pages.

## 8. Critical Requirements for `result.txt`

The `result.txt` file **must be updated while the crawler is running**, not created only at the end. Flush the report to disk periodically (for example, every few seconds) and after important events so the latest statistics are preserved if the program stops. Avoid rewriting the report on every request without control; periodic updates are sufficient.

Initialize the file with information for the new run. During execution, report at least:

- Project name
- Target seed URL
- Allowed-domain policy
- Python version and platform
- Start timestamp
- Elapsed runtime
- Target number of HTML pages
- Number of successful HTML pages saved
- Total URLs enqueued
- Number of unique URLs scheduled
- Total extracted link occurrences, **including duplicates**
- Number of duplicate URLs detected
- Number of URLs rejected because they are outside the allowed domain
- Number of URLs rejected by robots/policy
- Number of URLs processed/attempted
- Number of successful HTTP responses
- Number of HTTP errors
- Number of network errors/timeouts
- Number of non-HTML responses
- Number of redirects
- Number of parser or storage errors
- Total errors, with a clear definition of which categories it includes
- Current queue length and **queue length at the end**
- Total stored HTML size in bytes and readable units (KB/MB)
- Total output size, if calculated
- Average request duration, if accurately measured
- Requests per second or average crawl rate, if it can genuinely be calculated from recorded data
- Last URL being processed, if appropriate
- Run status: `RUNNING`, `COMPLETED`, `INCOMPLETE_QUEUE_EXHAUSTED`, `STOPPED`, or `FAILED`
- Important errors, restrictions, and challenges that actually occurred
- End timestamp

At the end, `result.txt` must contain a clear, readable final report. Use measured values only. Write `N/A` for values that were not measured; never invent statistics.

### Definition of “Discovered URLs Including Duplicates”

Define this metric precisely and document it. Recommended definitions:

- `links_extracted_total`: total number of `href` link occurrences extracted from processed HTML pages, before deduplication and before domain filtering.
- `urls_enqueued_total`: total number of URLs actually added to the queue for the first time.
- `unique_urls_scheduled`: number of unique normalized URLs scheduled during the run.
- `duplicate_urls_skipped`: number of times a duplicate URL was detected and not enqueued again.

Do not conflate these values. Report each separately in `result.txt`. If the assignment sheet or instructor defines a metric differently, follow that definition and explain it in the README.

### Suggested `result.txt` Layout

The following values are examples of report structure only and must not be presented as real results:

```text
WEB CRAWLER - FINAL REPORT
=========================
Target URL: https://esam.ir/
Allowed domains: esam.ir and configured subdomains
Website language: Persian
Language: Python
Crawler mode: Single-threaded
Status: RUNNING / COMPLETED / INCOMPLETE_QUEUE_EXHAUSTED / STOPPED / FAILED

Start time:
End time:
Elapsed time:

Target successful HTML pages: 10000
Successful HTML pages saved:
URLs attempted:
URLs scheduled (unique):
Total link occurrences extracted (including duplicates):
Duplicate URLs skipped:
URLs rejected by domain filter:
URLs disallowed by robots/policy:
Successful HTTP responses:
HTTP errors:
Network errors/timeouts:
Non-HTML responses skipped:
Redirects:
Parser/storage errors:
Total errors (definition documented):

Queue length currently:
Queue length at end:

HTML output size (bytes):
HTML output size (human-readable):
Output directory:
Manifest path:
Errors log path:

Python version:
Operating system/platform:
Dependencies:

Challenges encountered:
Solutions applied:
Notes / limitations:
```

Keep this as a live status report during execution. At the end, write final values and the end timestamp. Update the report in a `finally` block where practical so it survives crashes as far as possible. Periodic checkpoints can help with abrupt system shutdowns.

## 9. Requirements for `manifest.csv` and `errors.csv`

### `manifest.csv`

Include at least these columns:

```text
file_name,requested_url,final_url,status_code,content_type,size_bytes,depth,fetched_at,sha256
```

- `file_name`: name of the saved file.
- `requested_url`: URL taken from the queue.
- `final_url`: final URL after redirects, if any.
- `status_code`: HTTP status code.
- `content_type`: response content type.
- `size_bytes`: number of bytes saved.
- `depth`: URL depth from the seed, if depth tracking is implemented.
- `fetched_at`: fetch timestamp.
- `sha256`: hash of the saved content, for integrity checks and helping identify byte-identical content.

Every row must correspond to a real, existing file. Save HTML with appropriate encoding and record its URL in the manifest; do not modify the HTML body just to inject metadata.

### `errors.csv`

Include at least these columns:

```text
timestamp,url,error_type,status_code,message
```

Do not log sensitive data, authentication headers, cookies, or private content.

## 10. Mandatory Tests Before a Full Crawl

Use mock responses or synthetic HTML wherever possible to avoid unnecessary requests to the real site. Test at least:

1. Resolving relative links to absolute URLs.
2. Removing fragments and identifying equivalent URLs.
3. Rejecting `javascript:`, `mailto:`, `data:`, and other non-HTTP/HTTPS schemes.
4. Rejecting external domains and similar but unauthorized domains such as `esam.ir.example.com`.
5. Correct subdomain behavior according to configuration.
6. Preventing a URL from being enqueued more than once.
7. Extracting links from HTML with BeautifulSoup.
8. Accepting `text/html` and rejecting PDFs, images, and other non-HTML responses.
9. Handling timeouts, DNS errors, connection failures, and HTTP error codes.
10. Checking redirects outside the allowed domain and not following them when unauthorized.
11. Respecting `robots.txt` and the request delay.
12. Saving HTML and validating the associated manifest row.
13. Correctly calculating output size.
14. Updating `result.txt` during execution and reporting queue length correctly.
15. Stopping exactly when the target is reached or the queue is exhausted.
16. Verifying that the implementation is truly single-threaded and creates no workers or concurrent requests.
17. Testing recovery or report writing during a controlled stop.

Use `pytest` if helpful. If you add a testing dependency, document it in the dependency file(s) and README.

## 11. Staged Execution Plan

Do not start a full crawl without testing first.

1. **Smoke test:** Use a few URLs to check connectivity and site structure.
2. **Small crawl:** Crawl no more than approximately 20–50 successful pages using the same domain, robots, and rate-limit policies.
3. Verify that saved pages are actually HTML, duplicate URLs were not stored, the manifest is correct, statistics match the real files, and `result.txt` updates during execution.
4. If everything works, prepare for the 10,000-page run.
5. Before the long run, assess disk space, error rate, output size, and a realistic runtime estimate.
6. Run the full crawl only within the website's policies and at a conservative rate.
7. If site restrictions, `429`, `403`, policy changes, or repeated errors occur, slow down or stop. Do not bypass controls to reach the target count.
8. At the end, verify `result.txt` and the CSV files against the saved files. If fewer than 10,000 pages were saved, report the exact reason and an incomplete status.

## 12. Documentation and Deliverables

The `README.md` must include:

- Assignment objective and the definition of a “successful, unique page.”
- Crawler architecture and the roles of Queue, Fetcher, Parser, and UChecker.
- Python and library versions.
- Installation and virtual-environment instructions for Windows and Linux.
- Command(s) to run the crawler.
- Explanations of important settings: seed, target count, timeout, delay, domain/subdomain policy, and output directory.
- `robots.txt` handling and responsible crawling policy.
- Structure of `output/`, `manifest.csv`, `errors.csv`, and `result.txt`.
- Precise definitions of all counters.
- How to run tests.
- Real results from the latest run, or an explicit statement that a full crawl was not run.
- Actual limitations and challenges.
- Instructions for reproducing the run.

Add an “Architecture” section or file, optionally with an ASCII or Mermaid diagram. Keep the code readable, use meaningful names, add type hints where useful, and document key functions with docstrings.

## 13. Final Acceptance Checklist

The project is ready for submission when:

- [ ] GitHub is connected and the actual repository status is known.
- [ ] The project runs in Python and dependencies are documented.
- [ ] The crawler is single-threaded.
- [ ] Queue, Fetcher, Parser, and UChecker are implemented and explainable.
- [ ] The `esam.ir` domain policy and subdomain rules are correctly enforced.
- [ ] URL normalization and deduplication are tested.
- [ ] `robots.txt` and crawl politeness are respected.
- [ ] Only qualifying HTML pages are saved.
- [ ] Every saved page can be traced to its URL in the manifest.
- [ ] `result.txt` updates during execution and is complete at the end.
- [ ] All required metrics are included, with clear counter definitions.
- [ ] Final queue length and actual output size are calculated.
- [ ] Errors are logged and no statistics are fabricated.
- [ ] Tests are run and their results reported.
- [ ] The README and a five-minute presentation guide are ready.
- [ ] Large outputs and secrets have not been accidentally committed to GitHub.

## 14. Behavioral Instructions for the AI Agent

- Connect to GitHub and inspect the appropriate repository first; only then begin implementation.
- If GitHub access, the repository name, or permission to create a repository is missing, ask only for the essential information needed and wait for the user's response.
- If no GitHub integration is available, state that limitation honestly; never pretend to have connected.
- Check site policies and run a small test before a full crawl.
- For tasks you can perform, do not only provide a plan: create the files, run the code, execute tests, and fix issues.
- Never report a result or metric without measuring it.
- If the environment or website policies prevent a 10,000-page crawl, report the reason, actual page count, queue status, and next practical step.
- At the end, provide a summary of created files, tests run, GitHub status, the location of `result.txt`, and whether the target of 10,000 pages was reached.
- Get permission before destructive actions, deleting data, changing repository visibility, or making a repository public.

**Start now: first check the GitHub connection status and repository access. Do not begin implementation until this step is complete.**
