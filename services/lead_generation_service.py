"""Top-level orchestration for a single lead-generation run.

Wires together Google Places search, duplicate detection, website crawling,
contact extraction, lead scoring, website analysis, and service
recommendation behind one entry point so that Streamlit pages stay
presentation-only (see project rule: no business logic inside pages/).

Every saved lead also gets a website quality score and a set of recommended
services (AI Calling Agent / Website Chatbot / Website Development /
Website Redesign) with opportunity scores and reasons - see
services/website_analyzer.py and services/service_recommender.py.

Business rule: an email is mandatory. A business with no website, or whose
homepage crawl doesn't turn up an email, is discarded entirely - phone
number presence/absence doesn't matter either way. A discarded business is
never written to `leads`, so it is not covered by duplicate prevention and
could be encountered again in a future search.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Any, Callable, Optional

from database import crud
from database.connection import get_session
from database.models import CrawlStatus, LeadStatus, WebsiteAnalysisStatus
from logging_config import get_logger
from services import lead_scoring
from services.crawler import crawl_many
from services.duplicate_service import check_duplicate
from services.email_extractor import select_primary_email
from services.google_places import GooglePlacesError, PlaceResult, search_places
from services.phone_extractor import select_primary_phone
from services.service_recommender import recommend_services
from services.website_analyzer import analyze_website_html
from utils.phone_utils import normalize_phone
from utils.url_utils import normalize_domain

logger = get_logger(__name__)

CRAWL_BATCH_SIZE_MULTIPLIER = 3  # crawl in batches of (concurrency * this) candidates at a time
MAX_PLACES_PER_NEW_LEAD = 40  # safety cap on how many Google results we'll scan per requested lead
# (higher than a simple 1:1 ratio since most businesses are expected to be
# filtered out by the email-mandatory rule before ever being saved)


ProgressCallback = Callable[[str, dict], None]


@dataclass
class SearchProgress:
    requested_leads: int
    total_results_checked: int = 0
    duplicate_leads_skipped: int = 0
    new_leads_found: int = 0
    emails_found: int = 0
    phones_found: int = 0
    websites_crawled: int = 0


@dataclass
class SearchRunResult:
    search_history_id: int
    status: str
    progress: SearchProgress
    error_message: Optional[str] = None


def _emit(callback: Optional[ProgressCallback], event: str, payload: dict) -> None:
    if callback:
        try:
            callback(event, payload)
        except Exception:  # noqa: BLE001 - UI callback failures must never break the run
            logger.exception("Progress callback raised for event=%s", event)


def _save_place_as_lead(
    session,
    place: PlaceResult,
    *,
    email: str | None,
    website_phone: str | None,
    crawl_status: str,
    lead_status: str,
    website_analysis_status: str,
    analysis_data: dict[str, Any],
    website_quality_score: int | None,
):
    website_domain = normalize_domain(place.website)
    final_phone = place.phone or website_phone
    normalized_phone = normalize_phone(final_phone, place.country) if final_phone else None

    signals = lead_scoring.LeadSignals(
        has_website=bool(place.website),
        has_email=bool(email),
        has_phone=bool(final_phone),
        rating=place.rating,
        user_ratings_total=place.user_ratings_total,
    )
    score, priority = lead_scoring.score_lead(signals)

    recommendation = recommend_services(
        business_name=place.business_name,
        analysis_data=analysis_data,
        website_quality_score=website_quality_score,
        has_phone=bool(final_phone),
        user_ratings_total=place.user_ratings_total,
    )

    lead = crud.create_lead(
        session,
        google_place_id=place.google_place_id,
        business_name=place.business_name,
        country=place.country,
        city=place.city,
        full_address=place.formatted_address,
        google_phone=place.phone,
        website_phone=website_phone,
        final_phone=final_phone,
        normalized_phone=normalized_phone,
        email=email,
        website=place.website,
        website_domain=website_domain,
        rating=place.rating,
        user_ratings_total=place.user_ratings_total,
        lead_score=score,
        priority=priority,
        crawl_status=crawl_status,
        lead_status=lead_status,
    )

    return crud.update_lead(
        session,
        lead,
        website_analysis_status=website_analysis_status,
        website_quality_score=recommendation.website_quality_score,
        recommended_services=recommendation.recommended_services,
        service_recommendation_reason=recommendation.service_recommendation_reason,
        service_opportunity_scores=recommendation.service_opportunity_scores,
        website_analysis_data=recommendation.website_analysis_data,
        analyzed_at=dt.datetime.now(dt.timezone.utc),
    )


def _process_crawl_batch(
    candidates: list[PlaceResult],
    concurrency: int,
    progress: SearchProgress,
    callback: Optional[ProgressCallback],
) -> None:
    """Crawl a batch of candidate businesses' homepages and save the ones with an email.

    A candidate is saved only if the crawl turns up an email - phone
    presence/absence doesn't affect this decision either way. Discarded
    entirely if no email was found (crawl failed, or the page just has none).
    """
    if not candidates:
        return

    urls = [c.website for c in candidates if c.website]
    if not urls:
        return

    _emit(callback, "status", {"message": f"Crawling {len(urls)} homepages for contact info..."})
    outcomes = asyncio.run(crawl_many(urls, concurrency=concurrency))
    _emit(callback, "status", {"message": "Analyzing websites and recommending services..."})

    with get_session() as session:
        for candidate in candidates:
            outcome = outcomes.get(candidate.website)
            if outcome is None:
                continue
            progress.websites_crawled += 1

            primary_email = select_primary_email(outcome.emails) if outcome.status == CrawlStatus.COMPLETED else None
            if not primary_email:
                continue  # email-mandatory rule: discard entirely, do not save

            website_phone = select_primary_phone(outcome.phones)

            website_domain = normalize_domain(candidate.website)
            google_normalized_phone = normalize_phone(candidate.phone, candidate.country)

            dup = check_duplicate(
                session,
                google_place_id=candidate.google_place_id,
                website_domain=website_domain,
                normalized_phone=google_normalized_phone,
            )
            if dup.is_duplicate:
                progress.duplicate_leads_skipped += 1
                continue

            analysis_data, website_quality_score = analyze_website_html(
                outcome.html,
                https_enabled=bool(outcome.final_url and outcome.final_url.startswith("https://")),
                email_detected=True,
                phone_detected=bool(website_phone or candidate.phone),
                fetch_seconds=outcome.fetch_seconds,
                page_size_bytes=outcome.page_size_bytes,
            )

            lead = _save_place_as_lead(
                session,
                candidate,
                email=primary_email,
                website_phone=website_phone,
                crawl_status=outcome.status,
                lead_status=LeadStatus.ENRICHED,
                website_analysis_status=WebsiteAnalysisStatus.COMPLETED,
                analysis_data=analysis_data,
                website_quality_score=website_quality_score,
            )

            crawl_record = crud.create_crawl_result(session, lead_id=lead.id, website_url=candidate.website)
            crawl_record.emails_found = sorted(outcome.emails)
            crawl_record.phones_found = sorted(outcome.phones)
            crud.update_crawl_result(
                session,
                crawl_record,
                pages_crawled=outcome.pages_crawled,
                crawl_status=outcome.status,
                error_message=outcome.error_message,
            )

            progress.new_leads_found += 1
            progress.emails_found += 1
            if candidate.phone or website_phone:
                progress.phones_found += 1

    _emit(callback, "batch_progress", progress.__dict__.copy())


def run_lead_generation(
    keyword: str,
    country: str,
    city: str,
    requested_leads: int,
    *,
    crawl_concurrency: int = 5,
    progress_callback: Optional[ProgressCallback] = None,
) -> SearchRunResult:
    """Run a full search -> dedupe -> crawl -> save pipeline and return a summary.

    A business is saved only if it has a website AND its homepage crawl
    turns up an email; it's discarded otherwise, regardless of phone.
    """
    progress = SearchProgress(requested_leads=requested_leads)

    with get_session() as session:
        history = crud.create_search_history(
            session, keyword=keyword, country=country, city=city, requested_leads=requested_leads
        )
        search_id = history.id

    _emit(progress_callback, "status", {"message": "Searching Google Places..."})

    pending_candidates: list[PlaceResult] = []
    batch_size = max(1, crawl_concurrency * CRAWL_BATCH_SIZE_MULTIPLIER)
    max_places = min(5000, max(200, requested_leads * MAX_PLACES_PER_NEW_LEAD))

    error_message: Optional[str] = None

    try:
        for place in search_places(keyword, country, city, max_results=max_places):
            progress.total_results_checked += 1

            with get_session() as session:
                website_domain = normalize_domain(place.website)
                normalized_phone = normalize_phone(place.phone, place.country)

                dup = check_duplicate(
                    session,
                    google_place_id=place.google_place_id,
                    website_domain=website_domain,
                    normalized_phone=normalized_phone,
                )

                if dup.is_duplicate:
                    progress.duplicate_leads_skipped += 1
                elif place.website:
                    pending_candidates.append(place)
                # else: no website means no possible email source - discarded silently

            if progress.total_results_checked % 10 == 0:
                _emit(
                    progress_callback,
                    "status",
                    {
                        "message": (
                            f"Checked {progress.total_results_checked} results - "
                            f"{progress.new_leads_found} new, {progress.duplicate_leads_skipped} duplicates"
                        )
                    },
                )

            if len(pending_candidates) >= batch_size:
                batch, pending_candidates = pending_candidates, []
                _process_crawl_batch(batch, crawl_concurrency, progress, progress_callback)

            if progress.new_leads_found >= requested_leads:
                break

        if pending_candidates and progress.new_leads_found < requested_leads:
            _process_crawl_batch(pending_candidates, crawl_concurrency, progress, progress_callback)

    except GooglePlacesError as exc:
        logger.error("Lead generation failed for search_id=%s: %s", search_id, exc)
        error_message = str(exc)
    except Exception as exc:  # noqa: BLE001 - persist failure instead of crashing the app
        logger.exception("Unexpected error during lead generation for search_id=%s", search_id)
        error_message = str(exc)

    with get_session() as session:
        history = crud.get_search_history(session, search_id)
        crud.finalize_search_history(
            session,
            history,
            total_checked=progress.total_results_checked,
            duplicates_skipped=progress.duplicate_leads_skipped,
            new_leads_found=progress.new_leads_found,
            requested_leads=requested_leads,
            error_message=error_message,
        )
        status = history.status

    _emit(progress_callback, "status", {"message": "Completed" if not error_message else f"Failed: {error_message}"})

    return SearchRunResult(
        search_history_id=search_id,
        status=status,
        progress=progress,
        error_message=error_message,
    )
