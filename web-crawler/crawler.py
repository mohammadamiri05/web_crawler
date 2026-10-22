from __future__ import annotations

import csv
import hashlib
import json
import logging
import platform
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

import config


INVALID_SCHEMES = {"javascript:", "mailto:", "tel:", "data:"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    """Normalize a URL to a safe absolute HTTP(S) value."""
    if url is None:
        return None
    value = str(url).strip()
    if not value:
        return None
    if value.startswith("#"):
        return None
    if any(value.lower().startswith(prefix) for prefix in INVALID_SCHEMES):
        return None

    try:
        if base_url and not value.startswith(("http://", "https://")):
            value = urljoin(base_url, value)
        split = urlsplit(value)
    except Exception:
        return None

    scheme = split.scheme.lower()
    if scheme not in {"http", "https"}:
        return None

    if not split.netloc:
        return None

    normalized = urldefrag(value)[0]
    final = urlunsplit(
        (
            split.scheme.lower(),
            split.netloc.lower(),
            split.path or "/",
            split.query,
            "",
        )
    )
    return final


def allowed_domain(url: str, allowed_domains: set[str] | None = None, allow_subdomains: bool = True) -> bool:
    """Check if a URL belongs to the configured allowed domain policy."""
    if allowed_domains is None:
        allowed_domains = set(config.ALLOWED_DOMAINS)
    if not url:
        return False
    parsed_url = urlsplit(url)
    host = parsed_url.hostname.lower() if parsed_url.hostname else ""
    if not host:
        return False
    if host in allowed_domains:
        return True
    if allow_subdomains:
        for domain in allowed_domains:
            if host == domain or host.endswith(f".{domain}"):
                return True
    return False


def is_html_response(content_type: str | None) -> bool:
    if not content_type:
        return False
    media_type = content_type.lower().split(";", 1)[0].strip()
    return media_type in {"text/html", "application/xhtml+xml"}


def extract_links(html: str, base_url: str) -> list[str]:
    """Return normalized HTML links from a page."""
    links: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("a", href=True):
        href = tag.get("href")
        if not href or not isinstance(href, str):
            continue
        normalized = normalize_url(href, base_url)
        if normalized:
            links.append(normalized)
    return links


class URLFrontier:
    """Single-threaded FIFO queue with unique URL tracking."""

    def __init__(self) -> None:
        self.queue: deque[str] = deque()
        self.seen: set[str] = set()
        self.state: dict[str, str] = {}

    @classmethod
    def from_seed(cls, url: str) -> "URLFrontier":
        instance = cls()
        instance.enqueue(url)
        return instance

    def enqueue(self, url: str, base_url: str | None = None) -> bool:
        normalized = normalize_url(url, base_url)
        if not normalized:
            return False
        if normalized in self.seen:
            return False
        self.seen.add(normalized)
        self.state[normalized] = "scheduled"
        self.queue.append(normalized)
        return True

    def dequeue(self) -> str | None:
        if not self.queue:
            return None
        url = self.queue.popleft()
        self.state[url] = "dequeued"
        return url

    def __len__(self) -> int:
        return len(self.queue)


class Crawler:
    """Small single-threaded crawler for the assignment."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else config.BASE_DIR
        self.output_dir = self.base_dir / "output"
        self.pages_dir = self.output_dir / "pages"
        self.manifest_path = self.output_dir / "manifest.csv"
        self.errors_path = self.output_dir / "errors.csv"
        self.result_path = self.base_dir / "result.txt"
        self.state_path = self.base_dir / "crawl_state.json"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)

        self.frontier = URLFrontier()
        self.successful_html_pages = 0
        self.total_urls_enqueued = 0
        self.unique_urls_scheduled = 0
        self.links_extracted_total = 0
        self.duplicate_urls_skipped = 0
        self.domain_rejected = 0
        self.robots_rejected = 0
        self.processed_urls = 0
        self.http_success = 0
        self.http_errors = 0
        self.network_errors = 0
        self.non_html_responses = 0
        self.redirects = 0
        self.parser_errors = 0
        self.storage_errors = 0
        self.total_errors = 0
        self.queue_length_at_end = 0
        self.current_url = ""
        self.start_time = time.monotonic()
        self.run_start = datetime.now(timezone.utc)
        self.status = "RUNNING"
        self.challenges: list[str] = []
        self.notes: list[str] = []
        self.last_error: str = "N/A"
        self.output_size_bytes = 0
        self.manifest_rows: list[dict[str, Any]] = []
        self.next_file_index = self._detect_next_file_index()

        self._load_manifest_rows()
        self._restore_state()

        self.write_manifest_header()
        self.write_errors_header()
        self.write_result()

    def _load_manifest_rows(self) -> None:
        if not self.manifest_path.exists():
            return
        with self.manifest_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                file_name = (row.get("file_name") or "").strip()
                requested_url = (row.get("requested_url") or "").strip()
                final_url = (row.get("final_url") or "").strip()
                if file_name:
                    self.manifest_rows.append(row)
                    if final_url:
                        self.frontier.seen.add(final_url)
                    if requested_url:
                        self.frontier.seen.add(requested_url)
                if file_name and file_name.endswith(".html") and file_name not in {"", "N/A"}:
                    numeric_name = file_name.rsplit(".", 1)[0]
                    if numeric_name.isdigit():
                        self.next_file_index = max(self.next_file_index, int(numeric_name) + 1)

    def _already_saved_url(self, url: str | None) -> bool:
        if not url:
            return False
        for row in self.manifest_rows:
            if (row.get("requested_url") == url) or (row.get("final_url") == url):
                return True
        return False

    def _restore_state(self) -> None:
        if not self.state_path.exists():
            if not self.frontier.seen:
                self.frontier.enqueue(config.SEED_URL)
            return
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            self.frontier.enqueue(config.SEED_URL)
            return

        queue = data.get("queue", [])
        seen = set(data.get("seen", []))
        self.frontier = URLFrontier()
        self.frontier.queue = deque(queue)
        self.frontier.seen = seen
        self.frontier.state = data.get("state", {})

        self.successful_html_pages = int(data.get("successful_html_pages", 0))
        self.total_urls_enqueued = int(data.get("total_urls_enqueued", 0))
        self.unique_urls_scheduled = int(data.get("unique_urls_scheduled", 0))
        self.links_extracted_total = int(data.get("links_extracted_total", 0))
        self.duplicate_urls_skipped = int(data.get("duplicate_urls_skipped", 0))
        self.domain_rejected = int(data.get("domain_rejected", 0))
        self.robots_rejected = int(data.get("robots_rejected", 0))
        self.processed_urls = int(data.get("processed_urls", 0))
        self.http_success = int(data.get("http_success", 0))
        self.http_errors = int(data.get("http_errors", 0))
        self.network_errors = int(data.get("network_errors", 0))
        self.non_html_responses = int(data.get("non_html_responses", 0))
        self.redirects = int(data.get("redirects", 0))
        self.parser_errors = int(data.get("parser_errors", 0))
        self.storage_errors = int(data.get("storage_errors", 0))
        self.total_errors = int(data.get("total_errors", 0))
        self.output_size_bytes = int(data.get("output_size_bytes", 0))
        self.current_url = data.get("current_url", "")
        self.status = data.get("status", "RUNNING")
        self.last_error = data.get("last_error", "N/A")
        self.notes = list(data.get("notes", []))
        self.challenges = list(data.get("challenges", []))

        if not self.frontier.queue:
            self.frontier.enqueue(config.SEED_URL)

    def _save_state(self) -> None:
        state = {
            "queue": list(self.frontier.queue),
            "seen": sorted(self.frontier.seen),
            "state": self.frontier.state,
            "successful_html_pages": self.successful_html_pages,
            "total_urls_enqueued": self.total_urls_enqueued,
            "unique_urls_scheduled": self.unique_urls_scheduled,
            "links_extracted_total": self.links_extracted_total,
            "duplicate_urls_skipped": self.duplicate_urls_skipped,
            "domain_rejected": self.domain_rejected,
            "robots_rejected": self.robots_rejected,
            "processed_urls": self.processed_urls,
            "http_success": self.http_success,
            "http_errors": self.http_errors,
            "network_errors": self.network_errors,
            "non_html_responses": self.non_html_responses,
            "redirects": self.redirects,
            "parser_errors": self.parser_errors,
            "storage_errors": self.storage_errors,
            "total_errors": self.total_errors,
            "output_size_bytes": self.output_size_bytes,
            "current_url": self.current_url,
            "status": self.status,
            "last_error": self.last_error,
            "notes": self.notes,
            "challenges": self.challenges,
        }
        with self.state_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)

    def _detect_next_file_index(self) -> int:
        existing_numbers = []
        for page_file in self.pages_dir.glob("*.html"):
            if page_file.stem.isdigit():
                existing_numbers.append(int(page_file.stem))
        return max(existing_numbers, default=0) + 1

    def next_file_name(self) -> str:
        file_name = f"{self.next_file_index}.html"
        self.next_file_index += 1
        return file_name

    @staticmethod
    def seed_frontier(seed_url: str) -> URLFrontier:
        return URLFrontier.from_seed(seed_url)

    def write_manifest_header(self) -> None:
        if not self.manifest_path.exists():
            with self.manifest_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    "file_name",
                    "requested_url",
                    "final_url",
                    "status_code",
                    "content_type",
                    "size_bytes",
                    "depth",
                    "fetched_at",
                    "sha256",
                ])

    def write_errors_header(self) -> None:
        if not self.errors_path.exists():
            with self.errors_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["timestamp", "url", "error_type", "status_code", "message"])

    def log_error(self, url: str, error_type: str, status_code: int | None = None, message: str = "") -> None:
        self.total_errors += 1
        self.last_error = message or error_type
        timestamp = now_iso()
        with self.errors_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([timestamp, url, error_type, status_code or "", message])

    def register_manifest(self, file_name: str, requested_url: str, final_url: str, status_code: int, content_type: str, size_bytes: int, depth: int, sha256: str) -> None:
        if self._already_saved_url(requested_url) or self._already_saved_url(final_url):
            return
        row = {
            "file_name": file_name,
            "requested_url": requested_url,
            "final_url": final_url,
            "status_code": status_code,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "depth": depth,
            "fetched_at": now_iso(),
            "sha256": sha256,
        }
        self.manifest_rows.append(row)
        with self.manifest_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([
                row["file_name"],
                row["requested_url"],
                row["final_url"],
                row["status_code"],
                row["content_type"],
                row["size_bytes"],
                row["depth"],
                row["fetched_at"],
                row["sha256"],
            ])

    def check_robots(self, url: str) -> bool:
        try:
            split = urlsplit(url)
            host = split.hostname or ""
            robots_url = f"{split.scheme}://{host}/robots.txt"
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.read()
            user_agent = config.USER_AGENT
            return parser.can_fetch(user_agent, url)
        except Exception:
            self.notes.append("Robots.txt could not be checked; using cautious defaults.")
            return True

    def _request_url(self, url: str) -> requests.Response:
        headers = {"User-Agent": config.USER_AGENT}
        response = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        return response

    def fetch_page(self, url: str, depth: int = 0) -> tuple[bool, str | None, str | None, int | None, str | None, int | None]:
        self.processed_urls += 1
        if not self.check_robots(url):
            self.robots_rejected += 1
            self.log_error(url, "robots_disallowed", None, "Blocked by robots.txt or policy")
            return False, None, None, None, None, None

        try:
            response = self._request_url(url)
        except requests.exceptions.Timeout:
            self.network_errors += 1
            self.log_error(url, "timeout", None, "Request timed out")
            return False, None, None, None, None, None
        except requests.exceptions.RequestException as exc:
            self.network_errors += 1
            self.log_error(url, "network_error", None, str(exc))
            return False, None, None, None, None, None

        final_url = response.url
        if response.history:
            self.redirects += 1

        if response.status_code >= 400:
            self.http_errors += 1
            self.log_error(url, "http_error", response.status_code, f"HTTP {response.status_code}")
            return False, final_url, response.headers.get("Content-Type"), response.status_code, None, None

        if not allowed_domain(final_url, config.ALLOWED_DOMAINS, config.ALLOW_SUBDOMAINS):
            self.domain_rejected += 1
            self.log_error(final_url, "domain_rejected", response.status_code, "Final URL outside allowed domain")
            return False, final_url, response.headers.get("Content-Type"), response.status_code, None, None

        content_type = response.headers.get("Content-Type")
        if not is_html_response(content_type):
            self.non_html_responses += 1
            self.log_error(final_url, "non_html", response.status_code, f"Skipped non-HTML content type: {content_type}")
            return False, final_url, content_type, response.status_code, None, None

        self.http_success += 1
        if self._already_saved_url(final_url) or self._already_saved_url(url):
            self.notes.append(f"Skipped duplicate page already in manifest: {final_url}")
            return False, final_url, content_type, response.status_code, None, None

        html = response.text
        file_name = self.next_file_name()
        file_path = self.pages_dir / file_name
        try:
            file_path.write_bytes(html.encode("utf-8"))
        except Exception as exc:
            self.storage_errors += 1
            self.log_error(final_url, "storage_error", response.status_code, str(exc))
            return False, final_url, content_type, response.status_code, None, None

        sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
        byte_size = file_path.stat().st_size
        self.output_size_bytes += byte_size
        self.successful_html_pages += 1
        self.register_manifest(file_name, url, final_url, response.status_code, content_type, byte_size, depth, sha256)
        self._save_state()
        return True, final_url, content_type, response.status_code, html, byte_size

    def fetch_and_parse(self, url: str, depth: int = 0) -> list[str]:
        self.current_url = url
        self.write_result()
        success, final_url, content_type, status_code, html, _ = self.fetch_page(url, depth)
        if not success or html is None:
            return []

        try:
            links = extract_links(html, final_url or url)
            self.links_extracted_total += len(links)
            for href in links:
                if allowed_domain(href, config.ALLOWED_DOMAINS, config.ALLOW_SUBDOMAINS):
                    enqueued = self.frontier.enqueue(href, base_url=final_url or url)
                    if enqueued:
                        self.total_urls_enqueued += 1
                        self.unique_urls_scheduled += 1
                    else:
                        self.duplicate_urls_skipped += 1
                else:
                    self.domain_rejected += 1
            self._save_state()
            return links
        except Exception:
            self.parser_errors += 1
            self.log_error(url, "parser_error", status_code, "Failed to parse HTML for anchor extraction")
            return []

    def write_result(self) -> None:
        elapsed_seconds = max((time.monotonic() - self.start_time), 0.0)
        now_value = datetime.now(timezone.utc)
        all_metrics = {
            "project_name": "web-crawler",
            "target_url": config.SEED_URL,
            "allowed_domain_policy": "esam.ir and configured subdomains",
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "start_timestamp": self.run_start.isoformat(),
            "elapsed_runtime_seconds": round(elapsed_seconds, 2),
            "target_successful_html_pages": config.TARGET_PAGES,
            "successful_html_pages_saved": self.successful_html_pages,
            "urls_enqueued_total": self.total_urls_enqueued,
            "unique_urls_scheduled": self.unique_urls_scheduled,
            "links_extracted_total": self.links_extracted_total,
            "duplicate_urls_skipped": self.duplicate_urls_skipped,
            "urls_rejected_by_domain": self.domain_rejected,
            "urls_rejected_by_robots_policy": self.robots_rejected,
            "urls_processed_attempted": self.processed_urls,
            "http_success": self.http_success,
            "http_errors": self.http_errors,
            "network_errors_timeouts": self.network_errors,
            "non_html_responses": self.non_html_responses,
            "redirects": self.redirects,
            "parser_or_storage_errors": self.parser_errors + self.storage_errors,
            "total_errors": self.total_errors,
            "queue_length_current": len(self.frontier),
            "queue_length_at_end": self.queue_length_at_end,
            "html_output_size_bytes": self.output_size_bytes,
            "html_output_size_human": self.format_bytes(self.output_size_bytes),
            "output_directory": str(self.output_dir),
            "manifest_path": str(self.manifest_path),
            "errors_path": str(self.errors_path),
            "current_url": self.current_url,
            "status": self.status,
            "last_error": self.last_error,
            "challenges": " | ".join(self.challenges) if self.challenges else "N/A",
            "notes": " | ".join(self.notes) if self.notes else "N/A",
            "time_now": now_value.isoformat(),
        }

        lines = [
            "WEB CRAWLER - LIVE REPORT",
            "========================",
            f"Target URL: {all_metrics['target_url']}",
            f"Allowed domains: {all_metrics['allowed_domain_policy']}",
            f"Language: Python {all_metrics['python_version']}",
            f"Crawler mode: Single-threaded",
            f"Status: {all_metrics['status']}",
            "",
            f"Start time: {all_metrics['start_timestamp']}",
            f"Current time: {all_metrics['time_now']}",
            f"Elapsed time: {all_metrics['elapsed_runtime_seconds']} seconds",
            "",
            f"Target successful HTML pages: {all_metrics['target_successful_html_pages']}",
            f"Successful HTML pages saved: {all_metrics['successful_html_pages_saved']}",
            f"URLs attempted: {all_metrics['urls_processed_attempted']}",
            f"URLs scheduled (unique): {all_metrics['unique_urls_scheduled']}",
            f"Total link occurrences extracted (including duplicates): {all_metrics['links_extracted_total']}",
            f"Duplicate URLs skipped: {all_metrics['duplicate_urls_skipped']}",
            f"URLs rejected by domain filter: {all_metrics['urls_rejected_by_domain']}",
            f"URLs rejected by robots/policy: {all_metrics['urls_rejected_by_robots_policy']}",
            f"HTTP successful responses: {all_metrics['http_success']}",
            f"HTTP errors: {all_metrics['http_errors']}",
            f"Network errors/timeouts: {all_metrics['network_errors_timeouts']}",
            f"Non-HTML responses skipped: {all_metrics['non_html_responses']}",
            f"Redirects: {all_metrics['redirects']}",
            f"Parser/storage errors: {all_metrics['parser_or_storage_errors']}",
            f"Total errors: {all_metrics['total_errors']}",
            f"Current queue length: {all_metrics['queue_length_current']}",
            f"Queue length at end: {all_metrics['queue_length_at_end']}",
            f"HTML output size (bytes): {all_metrics['html_output_size_bytes']}",
            f"HTML output size (human-readable): {all_metrics['html_output_size_human']}",
            f"Output directory: {all_metrics['output_directory']}",
            f"Manifest path: {all_metrics['manifest_path']}",
            f"Errors log path: {all_metrics['errors_path']}",
            f"Platform: {all_metrics['platform']}",
            f"Current URL: {all_metrics['current_url'] or 'N/A'}",
            f"Last error: {all_metrics['last_error']}",
            f"Challenges: {all_metrics['challenges']}",
            f"Notes / limitations: {all_metrics['notes']}",
        ]
        self.result_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._save_state()

    @staticmethod
    def format_bytes(value: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        size = float(value)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{value} B"

    def run(self, max_pages: int | None = None) -> None:
        deadline = max_pages or config.TARGET_PAGES
        self.status = "RUNNING"
        last_flush = time.monotonic()

        while self.frontier.queue and self.successful_html_pages < deadline:
            self.current_url = self.frontier.dequeue() or ""
            if not self.current_url:
                continue
            self.fetch_and_parse(self.current_url, depth=0)

            if time.monotonic() - last_flush > 2:
                self.write_result()
                last_flush = time.monotonic()

            time.sleep(config.REQUEST_DELAY_SECONDS)

        self._save_state()

        if self.successful_html_pages >= deadline:
            self.status = "COMPLETED"
            self.queue_length_at_end = len(self.frontier)
            self.write_result()
            return

        if not self.frontier.queue:
            self.status = "INCOMPLETE_QUEUE_EXHAUSTED"
            self.queue_length_at_end = 0
            self.write_result()
            return

        self.status = "STOPPED"
        self.queue_length_at_end = len(self.frontier)
        self.write_result()


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-threaded web crawler for esam.ir")
    parser.add_argument("--max-pages", type=int, default=config.TARGET_PAGES, help="Maximum successful HTML pages to save before stopping.")
    parser.add_argument("--seed", type=str, default=config.SEED_URL, help="Seed URL to start crawling from.")
    args = parser.parse_args()

    crawler = Crawler()
    if args.seed and not crawler.state_path.exists():
        crawler.frontier = URLFrontier.from_seed(args.seed)
    crawler.run(max_pages=args.max_pages)


if __name__ == "__main__":
    import argparse

    main()
