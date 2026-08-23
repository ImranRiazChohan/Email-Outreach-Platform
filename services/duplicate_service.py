"""Central duplicate-detection logic.

This is the single source of truth for the platform's most important rule:
a lead already saved in the database must never come back as "new" again.

Check order (cheapest / most authoritative first):
    1. google_place_id  -> exact, always skip if found
    2. website_domain   -> possible duplicate, treated as duplicate (same business)
    3. normalized_phone -> possible duplicate, treated as duplicate (same business)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from database import crud
from database.models import Lead
from logging_config import get_logger

logger = get_logger(__name__)


class DuplicateReason(str, Enum):
    NONE = "NONE"
    PLACE_ID = "PLACE_ID"
    WEBSITE_DOMAIN = "WEBSITE_DOMAIN"
    PHONE = "PHONE"


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    reason: DuplicateReason
    existing_lead: Optional[Lead] = None


def check_duplicate(
    session: Session,
    *,
    google_place_id: str,
    website_domain: str | None = None,
    normalized_phone: str | None = None,
) -> DuplicateCheckResult:
    """Determine whether a candidate business already exists as a lead."""
    existing = crud.get_lead_by_place_id(session, google_place_id)
    if existing:
        return DuplicateCheckResult(True, DuplicateReason.PLACE_ID, existing)

    if website_domain:
        existing = crud.get_lead_by_website_domain(session, website_domain)
        if existing:
            logger.info("Duplicate by website_domain=%s (existing lead id=%s)", website_domain, existing.id)
            return DuplicateCheckResult(True, DuplicateReason.WEBSITE_DOMAIN, existing)

    if normalized_phone:
        existing = crud.get_lead_by_normalized_phone(session, normalized_phone)
        if existing:
            logger.info("Duplicate by normalized_phone=%s (existing lead id=%s)", normalized_phone, existing.id)
            return DuplicateCheckResult(True, DuplicateReason.PHONE, existing)

    return DuplicateCheckResult(False, DuplicateReason.NONE, None)
