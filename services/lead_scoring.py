"""Rule-based lead scoring and prioritization for the MVP.

Kept isolated from the rest of the app so it can be swapped for an
AI-based scoring model later without touching callers - they only depend on
`score_lead(...)` returning a (score, priority) pair.
"""
from __future__ import annotations

from dataclasses import dataclass

import config
from database.models import LeadPriority

SCORE_WEBSITE = 15
SCORE_EMAIL = 30
SCORE_PHONE = 20
SCORE_STRONG_RATING = 10
SCORE_RATING_VOLUME = 10


@dataclass
class LeadSignals:
    has_website: bool
    has_email: bool
    has_phone: bool
    rating: float | None
    user_ratings_total: int | None


def score_lead(signals: LeadSignals) -> tuple[int, str]:
    """Return (lead_score, priority) for the given contact/quality signals."""
    score = 0
    if signals.has_website:
        score += SCORE_WEBSITE
    if signals.has_email:
        score += SCORE_EMAIL
    if signals.has_phone:
        score += SCORE_PHONE
    if signals.rating is not None and signals.rating >= config.STRONG_RATING_THRESHOLD:
        score += SCORE_STRONG_RATING
    if signals.user_ratings_total is not None and signals.user_ratings_total > config.RATING_COUNT_THRESHOLD:
        score += SCORE_RATING_VOLUME

    priority = _determine_priority(signals)
    return score, priority


def _determine_priority(signals: LeadSignals) -> str:
    strong_rating = signals.rating is not None and signals.rating >= config.STRONG_RATING_THRESHOLD

    if (not signals.has_website and signals.has_phone) or (
        signals.has_website and signals.has_email and signals.has_phone and strong_rating
    ):
        return LeadPriority.HIGH

    if signals.has_email or signals.has_phone:
        return LeadPriority.MEDIUM

    return LeadPriority.LOW
