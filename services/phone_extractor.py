"""Phone number extraction from crawled HTML pages."""
from __future__ import annotations

import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from utils.phone_utils import is_valid_phone

_TEL_RE = re.compile(r"tel:([^\"'>\s]+)", re.IGNORECASE)
# Loosely matches international/local phone formats: +92 300 1234567, (021) 111-222-333, etc.
_PHONE_RE = re.compile(r"(\+?\d[\d\-\s().]{6,17}\d)")


def extract_phones_from_html(html: str) -> set[str]:
    """Extract candidate phone numbers from tel: links and visible text."""
    found: set[str] = set()

    for match in _TEL_RE.findall(html):
        found.add(unquote(match).strip())

    soup = BeautifulSoup(html, "lxml")
    visible_text = soup.get_text(separator=" ")
    for match in _PHONE_RE.findall(visible_text):
        candidate = match.strip()
        if is_valid_phone(candidate):
            found.add(candidate)

    return {p for p in found if is_valid_phone(p)}


def select_primary_phone(phones: set[str] | list[str]) -> str | None:
    if not phones:
        return None
    # Prefer numbers with an explicit country code (+) as they're less ambiguous.
    with_plus = sorted(p for p in phones if p.strip().startswith("+"))
    if with_plus:
        return with_plus[0]
    return sorted(phones)[0]
