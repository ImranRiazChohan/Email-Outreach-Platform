"""Website crawler for contact-information enrichment and website analysis.

Fetches only the business homepage (no internal-link following) and extracts
emails and phone numbers from anywhere on that page (visible text, raw HTML,
mailto:/tel: links). A single broken/slow/SSL-failing website can never stop
the overall lead-generation run - every failure is caught and recorded.

The raw HTML, final URL, fetch latency, and page size are also captured on
the outcome so services/website_analyzer.py can run its analysis without a
second network request to the same page.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx

import config
from database.models import CrawlStatus
from logging_config import get_logger
from services.email_extractor import extract_emails_from_html
from services.phone_extractor import extract_phones_from_html
from utils.url_utils import normalize_url

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LeadGenBot/1.0; +https://example.com/bot)"
    )
}


@dataclass
class CrawlOutcome:
    status: str
    emails: set[str] = field(default_factory=set)
    phones: set[str] = field(default_factory=set)
    pages_crawled: int = 0
    error_message: str | None = None
    html: str | None = None
    final_url: str | None = None
    fetch_seconds: float | None = None
    page_size_bytes: int | None = None


@dataclass
class _FetchResult:
    html: str
    final_url: str
    fetch_seconds: float
    page_size_bytes: int


async def _fetch(client: httpx.AsyncClient, url: str) -> _FetchResult | None:
    try:
        started = time.monotonic()
        response = await client.get(url, headers=_HEADERS, timeout=config.CRAWL_TIMEOUT_SECONDS, follow_redirects=True)
        elapsed = time.monotonic() - started
        if response.status_code >= 400:
            return None
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None
        return _FetchResult(
            html=response.text,
            final_url=str(response.url),
            fetch_seconds=elapsed,
            page_size_bytes=len(response.content),
        )
    except (httpx.TransportError, httpx.HTTPError, Exception):  # noqa: BLE001 - never let one page kill the crawl
        return None


async def _fetch_first_success(urls: list[str], *, verify: bool) -> _FetchResult | None:
    async with httpx.AsyncClient(verify=verify) as client:
        for url in urls:
            result = await _fetch(client, url)
            if result is not None:
                return result
    return None


async def crawl_website_async(website_url: str) -> CrawlOutcome:
    """Fetch only the homepage and extract emails/phones from anywhere on it."""
    seed_url = normalize_url(website_url)
    if not seed_url:
        return CrawlOutcome(status=CrawlStatus.NO_WEBSITE)

    urls_to_try = [seed_url]
    if seed_url.startswith("https://"):
        urls_to_try.append(seed_url.replace("https://", "http://", 1))

    result: _FetchResult | None = None
    try:
        result = await _fetch_first_success(urls_to_try, verify=True)
        if result is None:
            # Many networks (corporate proxies, some hosts) intercept TLS with
            # a self-signed certificate, which fails strict verification even
            # though the site itself is fine. Retry without verification
            # before giving up - this is a public marketing page, not a
            # sensitive transaction, so the risk tradeoff favors coverage.
            result = await _fetch_first_success(urls_to_try, verify=False)
    except Exception as exc:  # noqa: BLE001 - crawling must never raise into the caller
        logger.warning("Crawl failed for %s: %s", seed_url, exc)
        return CrawlOutcome(status=CrawlStatus.FAILED, error_message=str(exc))

    if result is None:
        return CrawlOutcome(status=CrawlStatus.FAILED, error_message=f"Failed to fetch {seed_url}")

    emails = extract_emails_from_html(result.html)
    phones = extract_phones_from_html(result.html)
    return CrawlOutcome(
        status=CrawlStatus.COMPLETED,
        emails=emails,
        phones=phones,
        pages_crawled=1,
        html=result.html,
        final_url=result.final_url,
        fetch_seconds=result.fetch_seconds,
        page_size_bytes=result.page_size_bytes,
    )


def crawl_website(website_url: str) -> CrawlOutcome:
    """Synchronous convenience wrapper for a single site (mainly for tests)."""
    return asyncio.run(crawl_website_async(website_url))


async def crawl_many(
    website_urls: list[str], *, concurrency: int | None = None
) -> dict[str, CrawlOutcome]:
    """Crawl multiple websites concurrently, bounded by a semaphore."""
    semaphore = asyncio.Semaphore(concurrency or config.MAX_CONCURRENT_CRAWLS)
    results: dict[str, CrawlOutcome] = {}

    async def _bounded_crawl(url: str) -> None:
        async with semaphore:
            results[url] = await crawl_website_async(url)

    await asyncio.gather(*(_bounded_crawl(url) for url in website_urls))
    return results
