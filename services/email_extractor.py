"""Email extraction and selection from crawled HTML pages."""
from __future__ import annotations

import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

import config
from utils.validators import is_valid_email

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_MAILTO_RE = re.compile(r"mailto:([^?\"'>\s]+)", re.IGNORECASE)


def extract_emails_from_html(html: str) -> set[str]:
    """Extract candidate emails from visible text, raw HTML, and mailto: links."""
    found: set[str] = set()

    for match in _MAILTO_RE.findall(html):
        found.add(unquote(match).strip().lower())

    soup = BeautifulSoup(html, "lxml")
    visible_text = soup.get_text(separator=" ")
    for match in _EMAIL_RE.findall(visible_text):
        found.add(match.strip().lower())

    # Also scan raw HTML in case emails are hidden in data attributes/comments.
    for match in _EMAIL_RE.findall(html):
        found.add(match.strip().lower())

    return {email for email in found if is_valid_email(email)}


def select_primary_email(emails: set[str] | list[str]) -> str | None:
    """Pick the single best contact email, preferring business-relevant prefixes."""
    if not emails:
        return None

    emails_sorted = sorted(emails)

    for prefix in config.PRIORITY_EMAIL_PREFIXES:
        for email in emails_sorted:
            local_part = email.split("@", 1)[0].lower()
            if local_part == prefix or local_part.startswith(f"{prefix}."):
                return email

    generic_technical = ("webmaster", "postmaster", "admin", "root", "abuse", "noc")
    non_technical = [e for e in emails_sorted if e.split("@", 1)[0].lower() not in generic_technical]

    return (non_technical or emails_sorted)[0]
