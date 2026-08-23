"""Deterministic, rule-based website feature detection and quality scoring.

Everything here is regex/keyword/heuristic based on the already-crawled
homepage HTML (see services/crawler.py) - no AI call, no second network
request, no headless browser. This keeps website_quality_score and the
feature flags in website_analysis_data fully reproducible; only the
human-readable *reason* text (services/service_recommender.py) uses Gemini.

Because there is no real rendering engine involved, `modern_design_score`
and `performance_score` are necessarily approximations from static HTML
inspection and response timing/size - documented as an MVP limitation.
"""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

# Substrings/regex matched case-insensitively against raw HTML to spot an
# existing chat widget. Kept broad on purpose - false positives here just
# lower a score, they don't crash anything.
_CHATBOT_PATTERNS = [
    r"widget\.intercom\.io",
    r"intercomcdn",
    r"tawk\.to",
    r"embed\.tawk",
    r"crisp\.chat",
    r"client\.crisp\.chat",
    r"js\.driftt\.com",
    r"drift\.com/",
    r"zdassets\.com",
    r"zopim",
    r"js\.hs-scripts\.com",
    r"hubspot.*chat",
    r"freshchat",
    r"fw-widget",
    r"livechatinc\.com",
    r"livechat",
    r"messenger.*chat",
    r"facebook\.com/customer_chat",
    r"wa\.me/",
    r"whatsapp.*widget",
    r"chat[-_]?widget",
    r"chat[-_]?bubble",
    r"chatbot[-_]?container",
    r"id=[\"']chat",
    r"class=[\"'][^\"']*chat[^\"']*[\"']",
]
_CHATBOT_RE = re.compile("|".join(_CHATBOT_PATTERNS), re.IGNORECASE)

_CTA_PHRASES = [
    "book now", "book an appointment", "book a consultation", "schedule a",
    "schedule now", "get a quote", "get quote", "request a quote", "contact us",
    "call now", "call us", "request a demo", "get started", "sign up",
    "sign up now", "buy now", "order now", "reserve", "apply now",
    "request a callback", "request callback", "enquire now", "inquire now",
    "make an appointment", "get in touch",
]

_BOOKING_PHRASES = [
    "book an appointment", "book now", "schedule a", "schedule an", "consultation",
    "admissions", "enroll now", "enquiry", "inquiry", "request a callback",
    "request callback", "booking", "reservation", "make an appointment",
    "walk-in", "opening hours", "business hours", "working hours",
]

_SEMANTIC_TAGS = ["header", "nav", "main", "footer", "section", "article"]


def detect_chatbot(html: str) -> bool:
    return bool(_CHATBOT_RE.search(html))


def detect_contact_form(soup: BeautifulSoup) -> bool:
    for form in soup.find_all("form"):
        inputs = form.find_all("input")
        has_email_or_tel = any((inp.get("type") or "").lower() in ("email", "tel") for inp in inputs)
        has_textarea = bool(form.find("textarea"))
        if has_email_or_tel or has_textarea or len(inputs) >= 2:
            return True
    return False


def detect_cta(text_lower: str) -> bool:
    return any(phrase in text_lower for phrase in _CTA_PHRASES)


def detect_booking_language(text_lower: str) -> bool:
    return any(phrase in text_lower for phrase in _BOOKING_PHRASES)


def detect_mobile_friendly(soup: BeautifulSoup) -> bool:
    viewport = soup.find("meta", attrs={"name": "viewport"})
    return viewport is not None and "width" in (viewport.get("content") or "").lower()


def detect_navigation(soup: BeautifulSoup) -> bool:
    if soup.find("nav") is not None:
        return True
    header = soup.find("header")
    if header and len(header.find_all("a")) >= 3:
        return True
    return False


def detect_page_structure(soup: BeautifulSoup) -> bool:
    present = sum(1 for tag in _SEMANTIC_TAGS if soup.find(tag) is not None)
    return present >= 3


def calculate_modern_design_score(soup: BeautifulSoup) -> int:
    score = 0
    if detect_mobile_friendly(soup):
        score += 30
    semantic_count = sum(1 for tag in _SEMANTIC_TAGS if soup.find(tag) is not None)
    score += min(30, semantic_count * 5)
    if soup.find("link", attrs={"rel": "stylesheet"}) is not None:
        score += 20
    if soup.find("link", attrs={"rel": re.compile("icon", re.IGNORECASE)}) is not None:
        score += 20
    return min(100, score)


def calculate_performance_score(fetch_seconds: float | None, page_size_bytes: int | None) -> int:
    score = 100
    if fetch_seconds is not None:
        if fetch_seconds > 5:
            score -= 50
        elif fetch_seconds > 2:
            score -= 25
        elif fetch_seconds > 1:
            score -= 10
    if page_size_bytes is not None:
        kb = page_size_bytes / 1024
        if kb > 3000:
            score -= 40
        elif kb > 1500:
            score -= 20
        elif kb > 800:
            score -= 10
    return max(0, min(100, score))


def calculate_website_quality_score(analysis_data: dict[str, Any]) -> int:
    """Composite 0-100 score. See README for the weighting model."""
    score = 0.0
    if analysis_data.get("https_enabled"):
        score += 10
    if analysis_data.get("mobile_friendly"):
        score += 20
    if analysis_data.get("navigation_detected"):
        score += 10
    if analysis_data.get("call_to_action_detected"):
        score += 10
    if analysis_data.get("phone_number_detected") or analysis_data.get("email_detected"):
        score += 10
    if analysis_data.get("contact_form_detected"):
        score += 10
    if analysis_data.get("good_page_structure"):
        score += 10
    score += (analysis_data.get("modern_design_score", 0) / 100) * 10
    score += (analysis_data.get("performance_score", 0) / 100) * 10
    return round(max(0, min(100, score)))


def analyze_website_html(
    html: str,
    *,
    https_enabled: bool,
    email_detected: bool,
    phone_detected: bool,
    fetch_seconds: float | None,
    page_size_bytes: int | None,
) -> tuple[dict[str, Any], int]:
    """Run all detectors against crawled homepage HTML.

    Returns (website_analysis_data, website_quality_score).
    """
    soup = BeautifulSoup(html, "lxml")
    visible_text_lower = soup.get_text(separator=" ").lower()

    analysis_data: dict[str, Any] = {
        "website_exists": True,
        "https_enabled": https_enabled,
        "mobile_friendly": detect_mobile_friendly(soup),
        "chatbot_detected": detect_chatbot(html),
        "contact_form_detected": detect_contact_form(soup),
        "phone_number_detected": phone_detected,
        "email_detected": email_detected,
        "call_to_action_detected": detect_cta(visible_text_lower),
        "navigation_detected": detect_navigation(soup),
        "good_page_structure": detect_page_structure(soup),
        "booking_language_detected": detect_booking_language(visible_text_lower),
        "modern_design_score": calculate_modern_design_score(soup),
        "performance_score": calculate_performance_score(fetch_seconds, page_size_bytes),
    }
    quality_score = calculate_website_quality_score(analysis_data)
    return analysis_data, quality_score
