"""CRUD helpers. All functions take an explicit SQLAlchemy Session so callers
control transaction boundaries via database.connection.get_session().
"""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database.models import City, Country, CrawlResult, CrawlStatus, Lead, SearchHistory, SearchStatus, ServiceType


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def get_lead_by_place_id(session: Session, google_place_id: str) -> Optional[Lead]:
    return session.scalar(select(Lead).where(Lead.google_place_id == google_place_id))


def get_lead_by_website_domain(session: Session, website_domain: str) -> Optional[Lead]:
    return session.scalar(select(Lead).where(Lead.website_domain == website_domain))


def get_lead_by_normalized_phone(session: Session, normalized_phone: str) -> Optional[Lead]:
    return session.scalar(select(Lead).where(Lead.normalized_phone == normalized_phone))


def get_lead(session: Session, lead_id: int) -> Optional[Lead]:
    return session.get(Lead, lead_id)


def create_lead(session: Session, **fields: Any) -> Lead:
    lead = Lead(**fields)
    session.add(lead)
    session.flush()
    return lead


def update_lead(session: Session, lead: Lead, **fields: Any) -> Lead:
    for key, value in fields.items():
        setattr(lead, key, value)
    session.flush()
    return lead


def list_leads(
    session: Session,
    *,
    country: str | None = None,
    city: str | None = None,
    priority: str | None = None,
    lead_status: str | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_website: bool | None = None,
    min_rating: float | None = None,
    search_text: str | None = None,
    limit: int = 50,
    offset: int = 0,
    order_desc: bool = True,
) -> tuple[list[Lead], int]:
    """Return (page of leads, total matching count) applying all provided filters."""
    stmt = select(Lead)
    conditions = []

    if country:
        conditions.append(Lead.country == country)
    if city:
        conditions.append(Lead.city == city)
    if priority:
        conditions.append(Lead.priority == priority)
    if lead_status:
        conditions.append(Lead.lead_status == lead_status)
    if has_email is True:
        conditions.append(Lead.email.is_not(None))
    elif has_email is False:
        conditions.append(Lead.email.is_(None))
    if has_phone is True:
        conditions.append(Lead.final_phone.is_not(None))
    elif has_phone is False:
        conditions.append(Lead.final_phone.is_(None))
    if has_website is True:
        conditions.append(Lead.website.is_not(None))
    elif has_website is False:
        conditions.append(Lead.website.is_(None))
    if min_rating is not None:
        conditions.append(Lead.rating >= min_rating)
    if search_text:
        like = f"%{search_text.strip()}%"
        conditions.append(
            or_(
                Lead.business_name.ilike(like),
                Lead.email.ilike(like),
                Lead.final_phone.ilike(like),
                Lead.website.ilike(like),
            )
        )

    if conditions:
        stmt = stmt.where(*conditions)

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    order_col = Lead.created_at.desc() if order_desc else Lead.created_at.asc()
    stmt = stmt.order_by(order_col).limit(limit).offset(offset)
    leads = list(session.scalars(stmt).all())
    return leads, total


def distinct_countries(session: Session) -> list[str]:
    rows = session.scalars(select(Lead.country).where(Lead.country.is_not(None)).distinct()).all()
    return sorted(r for r in rows if r)


def distinct_cities(session: Session, country: str | None = None) -> list[str]:
    stmt = select(Lead.city).where(Lead.city.is_not(None)).distinct()
    if country:
        stmt = stmt.where(Lead.country == country)
    rows = session.scalars(stmt).all()
    return sorted(r for r in rows if r)


# ---------------------------------------------------------------------------
# Countries / cities reference data
# ---------------------------------------------------------------------------

def list_all_countries(session: Session) -> list[str]:
    rows = session.scalars(select(Country.name).order_by(Country.name)).all()
    return list(rows)


def list_cities_for_country(session: Session, country_name: str) -> list[str]:
    stmt = (
        select(City.name)
        .join(Country, City.country_id == Country.id)
        .where(Country.name == country_name)
        .order_by(City.name)
    )
    rows = session.scalars(stmt).all()
    return list(rows)


# ---------------------------------------------------------------------------
# Dashboard aggregates
# ---------------------------------------------------------------------------

def dashboard_metrics(session: Session) -> dict[str, Any]:
    total_leads = session.scalar(select(func.count(Lead.id))) or 0

    today_start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = session.scalar(select(func.count(Lead.id)).where(Lead.created_at >= today_start)) or 0

    with_email = session.scalar(select(func.count(Lead.id)).where(Lead.email.is_not(None))) or 0
    with_phone = session.scalar(select(func.count(Lead.id)).where(Lead.final_phone.is_not(None))) or 0
    with_website = session.scalar(select(func.count(Lead.id)).where(Lead.website.is_not(None))) or 0
    high_priority = session.scalar(select(func.count(Lead.id)).where(Lead.priority == "HIGH")) or 0

    return {
        "total_leads": total_leads,
        "new_leads_today": new_today,
        "leads_with_email": with_email,
        "leads_with_phone": with_phone,
        "leads_with_website": with_website,
        "high_priority_leads": high_priority,
    }


def leads_by_city(session: Session, limit: int = 15) -> list[tuple[str, int]]:
    stmt = (
        select(Lead.city, func.count(Lead.id))
        .where(Lead.city.is_not(None))
        .group_by(Lead.city)
        .order_by(func.count(Lead.id).desc())
        .limit(limit)
    )
    return list(session.execute(stmt).all())


def leads_by_priority(session: Session) -> list[tuple[str, int]]:
    stmt = select(Lead.priority, func.count(Lead.id)).group_by(Lead.priority)
    return list(session.execute(stmt).all())


def leads_by_status(session: Session) -> list[tuple[str, int]]:
    stmt = select(Lead.lead_status, func.count(Lead.id)).group_by(Lead.lead_status)
    return list(session.execute(stmt).all())


def service_opportunity_counts(session: Session) -> dict[str, int]:
    """Count how many leads have each service in their `recommended_services`."""
    rows = session.scalars(select(Lead.recommended_services_json)).all()
    counter: Counter[str] = Counter({service: 0 for service in ServiceType.ALL})
    for raw in rows:
        if not raw:
            continue
        for service in json.loads(raw):
            if service in counter:
                counter[service] += 1
    return dict(counter)


def leads_over_time(session: Session, days: int = 30) -> list[tuple[dt.date, int]]:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = session.scalars(select(Lead.created_at).where(Lead.created_at >= since)).all()
    counts: dict[dt.date, int] = {}
    for created_at in rows:
        day = created_at.date()
        counts[day] = counts.get(day, 0) + 1
    return sorted(counts.items())


# ---------------------------------------------------------------------------
# Search history
# ---------------------------------------------------------------------------

def create_search_history(
    session: Session, *, keyword: str, country: str, city: str, requested_leads: int
) -> SearchHistory:
    record = SearchHistory(
        keyword=keyword,
        country=country,
        city=city,
        requested_leads=requested_leads,
        status=SearchStatus.RUNNING,
    )
    session.add(record)
    session.flush()
    return record


def update_search_history(session: Session, record: SearchHistory, **fields: Any) -> SearchHistory:
    for key, value in fields.items():
        setattr(record, key, value)
    session.flush()
    return record


def finalize_search_history(
    session: Session,
    record: SearchHistory,
    *,
    total_checked: int,
    duplicates_skipped: int,
    new_leads_found: int,
    requested_leads: int,
    error_message: str | None = None,
) -> SearchHistory:
    if error_message:
        status = SearchStatus.FAILED
    elif new_leads_found >= requested_leads:
        status = SearchStatus.COMPLETED
    else:
        status = SearchStatus.PARTIAL

    return update_search_history(
        session,
        record,
        total_results_checked=total_checked,
        duplicate_leads_skipped=duplicates_skipped,
        new_leads_found=new_leads_found,
        completed_at=dt.datetime.now(dt.timezone.utc),
        status=status,
        error_message=error_message,
    )


def list_search_history(session: Session, limit: int = 100, offset: int = 0) -> tuple[list[SearchHistory], int]:
    total = session.scalar(select(func.count(SearchHistory.id))) or 0
    stmt = select(SearchHistory).order_by(SearchHistory.started_at.desc()).limit(limit).offset(offset)
    records = list(session.scalars(stmt).all())
    return records, total


def get_search_history(session: Session, search_id: int) -> Optional[SearchHistory]:
    return session.get(SearchHistory, search_id)


# ---------------------------------------------------------------------------
# Crawl results
# ---------------------------------------------------------------------------

def create_crawl_result(session: Session, *, lead_id: int, website_url: str | None) -> CrawlResult:
    record = CrawlResult(lead_id=lead_id, website_url=website_url, crawl_status=CrawlStatus.PENDING)
    session.add(record)
    session.flush()
    return record


def update_crawl_result(session: Session, record: CrawlResult, **fields: Any) -> CrawlResult:
    for key, value in fields.items():
        setattr(record, key, value)
    session.flush()
    return record


def get_crawl_results_for_lead(session: Session, lead_id: int) -> list[CrawlResult]:
    stmt = select(CrawlResult).where(CrawlResult.lead_id == lead_id).order_by(CrawlResult.crawled_at.desc())
    return list(session.scalars(stmt).all())
