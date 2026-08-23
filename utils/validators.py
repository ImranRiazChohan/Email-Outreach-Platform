"""Shared input/data validators."""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico")
_JUNK_DOMAIN_FRAGMENTS = ("example.com", "sentry.io", "wixpress.com", "godaddy.com", "domain.com")
_JUNK_LOCAL_PARTS = ("noreply", "no-reply", "donotreply", "test", "example", "youremail")


def is_valid_email(email: str | None) -> bool:
    if not email or len(email) > 254:
        return False
    if not _EMAIL_RE.match(email):
        return False
    local, _, domain = email.partition("@")
    if any(email.lower().endswith(ext) for ext in _IMAGE_EXTENSIONS):
        return False
    if domain.lower() in _JUNK_DOMAIN_FRAGMENTS:
        return False
    if local.lower() in _JUNK_LOCAL_PARTS:
        return False
    return True


def validate_lead_generation_inputs(keyword: str, country: str, city: str, required_leads: int) -> list[str]:
    """Return a list of human-readable validation errors (empty list = valid)."""
    errors: list[str] = []
    if not keyword or not keyword.strip():
        errors.append("Business keyword is required.")
    if not country or not country.strip():
        errors.append("Country is required.")
    if not city or not city.strip():
        errors.append("City is required.")
    if required_leads is None or required_leads <= 0:
        errors.append("Required number of leads must be greater than zero.")
    if required_leads is not None and required_leads > 5000:
        errors.append("Required number of leads must be 5000 or fewer for a single search.")
    return errors
