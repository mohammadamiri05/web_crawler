from __future__ import annotations

from pathlib import Path

import pytest

from crawler import Crawler, is_html_response, normalize_url, allowed_domain, extract_links


@pytest.fixture
def sample_html() -> str:
    return '''
    <html><body>
      <a href="/products/1">Product</a>
      <a href="https://esam.ir/about#team">About</a>
      <a href="javascript:alert(1)">Bad</a>
      <a href="mailto:test@example.com">Mail</a>
      <a href="https://esam.ir.example.com/evil">External-like</a>
      <a href="/">Home</a>
    </body></html>
    '''


def test_normalize_url_relative_and_fragment() -> None:
    result = normalize_url("/about#section", "https://esam.ir/")
    assert result == "https://esam.ir/about"


def test_rejects_non_http_schemes() -> None:
    assert normalize_url("javascript:alert(1)", "https://esam.ir/") is None
    assert normalize_url("mailto:test@example.com", "https://esam.ir/") is None
    assert normalize_url("data:text/plain,hi", "https://esam.ir/") is None


def test_allowed_domain_policy() -> None:
    assert allowed_domain("https://esam.ir/about") is True
    assert allowed_domain("https://shop.esam.ir/about") is True
    assert allowed_domain("https://esam.ir.example.com/about") is False
    assert allowed_domain("https://example.com/about") is False


def test_duplicate_url_is_not_enqueued_twice() -> None:
    frontier = Crawler.seed_frontier("https://esam.ir/")
    repeated = ["https://esam.ir/", "https://esam.ir/#top", "/", "https://esam.ir/"]
    for url in repeated:
        frontier.enqueue(url, base_url="https://esam.ir/")
    assert len(frontier) == 1


def test_extract_links_from_html(sample_html: str) -> None:
    links = extract_links(sample_html, "https://esam.ir/")
    assert "https://esam.ir/products/1" in links
    assert "https://esam.ir/about" in links
    assert "https://esam.ir/" in links
    assert all(not link.startswith("javascript:") for link in links)


def test_is_html_response() -> None:
    assert is_html_response("text/html; charset=utf-8") is True
    assert is_html_response("application/xhtml+xml") is True
    assert is_html_response("application/pdf") is False
    assert is_html_response("") is False


def test_save_manifest_and_error_methods(tmp_path: Path) -> None:
    crawler = Crawler(base_dir=tmp_path)
    crawler.output_dir.mkdir(parents=True, exist_ok=True)
    crawler.pages_dir.mkdir(parents=True, exist_ok=True)
    crawler.write_manifest_header()
    crawler.write_errors_header()
    assert (tmp_path / "output" / "manifest.csv").exists()
    assert (tmp_path / "output" / "errors.csv").exists()


def test_resume_uses_next_free_page_number(tmp_path: Path) -> None:
    pages_dir = tmp_path / "output" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "1.html").write_text("x", encoding="utf-8")
    (pages_dir / "2.html").write_text("y", encoding="utf-8")

    crawler = Crawler(base_dir=tmp_path)
    assert crawler.next_file_name() == "3.html"


def test_resume_keeps_seen_urls_and_queue_state(tmp_path: Path) -> None:
    crawler = Crawler(base_dir=tmp_path)
    crawler.frontier.enqueue("https://esam.ir/about")
    crawler.frontier.enqueue("https://esam.ir/about")
    crawler._save_state()

    resumed = Crawler(base_dir=tmp_path)
    queued = list(resumed.frontier.queue)
    assert len(queued) == len(set(queued))
    assert queued.count("https://esam.ir/about") == 1
    assert "https://esam.ir/about" in resumed.frontier.seen
