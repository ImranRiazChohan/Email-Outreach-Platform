"""URL and domain normalization helpers used for duplicate detection and crawling."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse


def normalize_domain(url: str | None) -> str | None:
    """Normalize a URL down to a bare, comparable domain.

    https://www.example.com/  ->  example.com
    http://example.com        ->  example.com
    www.example.com           ->  example.com
    """
    if not url or not url.strip():
        return None

    candidate = url.strip()
    if "://" not in candidate:
        candidate = f"//{candidate}"

    parsed = urlparse(candidate)
    host = (parsed.netloc or parsed.path).lower().strip("/")
    host = host.split("/")[0]
    host = host.split(":")[0]  # drop port
    if host.startswith("www."):
        host = host[4:]

    return host or None


def normalize_url(url: str | None) -> str | None:
    """Ensure a URL has a scheme and no trailing slash, for use as a crawl seed."""
    if not url or not url.strip():
        return None

    candidate = url.strip()
    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    path = parsed.path.rstrip("/")
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return normalized


def resolve_link(base_url: str, href: str) -> str:
    """Resolve a possibly-relative href against a base URL."""
    return urljoin(base_url, href)


def is_same_domain(url: str, domain: str) -> bool:
    return normalize_domain(url) == domain
