"""SQLAlchemy ORM models for the lead generation platform.

Plain strings (not native SQL enums) are used for status/priority columns so
that migrating from SQLite to PostgreSQL later requires no enum-type dance.
Valid values are documented as class-level constants next to each column.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class LeadStatus:
    NEW = "NEW"
    ENRICHED = "ENRICHED"
    QUALIFIED = "QUALIFIED"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    INVALID = "INVALID"

    ALL = [NEW, ENRICHED, QUALIFIED, CONTACTED, REPLIED, INTERESTED, NOT_INTERESTED, INVALID]


class LeadPriority:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    ALL = [HIGH, MEDIUM, LOW]


class CrawlStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NO_WEBSITE = "NO_WEBSITE"

    ALL = [PENDING, PROCESSING, COMPLETED, FAILED, NO_WEBSITE]


class SearchStatus:
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

    ALL = [RUNNING, COMPLETED, PARTIAL, FAILED]


class WebsiteAnalysisStatus:
    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NO_WEBSITE = "NO_WEBSITE"

    ALL = [PENDING, ANALYZING, COMPLETED, FAILED, NO_WEBSITE]


class ServiceType:
    """The four services this platform can pitch to a lead."""

    AI_CALLING_AGENT = "AI Calling Agent"
    WEBSITE_CHATBOT = "Website Chatbot"
    WEBSITE_DEVELOPMENT = "Website Development"
    WEBSITE_REDESIGN = "Website Redesign"

    ALL = [AI_CALLING_AGENT, WEBSITE_CHATBOT, WEBSITE_DEVELOPMENT, WEBSITE_REDESIGN]


class ServiceOpportunityLevel:
    RECOMMENDED = "RECOMMENDED"
    POTENTIAL = "POTENTIAL"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("google_place_id", name="uq_leads_google_place_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    google_place_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    business_name: Mapped[str] = mapped_column(String(500), nullable=False)

    country: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    full_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    google_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    final_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    normalized_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    website: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    website_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    user_ratings_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default=LeadPriority.LOW, index=True)

    crawl_status: Mapped[str] = mapped_column(String(20), nullable=False, default=CrawlStatus.PENDING)
    lead_status: Mapped[str] = mapped_column(String(20), nullable=False, default=LeadStatus.NEW, index=True)

    # --- Website Analysis & Service Recommendation ---
    website_analysis_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WebsiteAnalysisStatus.PENDING, index=True
    )
    website_quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recommended_services_json: Mapped[str] = mapped_column(
        "recommended_services", Text, nullable=False, default="[]"
    )
    service_recommendation_reason_json: Mapped[str] = mapped_column(
        "service_recommendation_reason", Text, nullable=False, default="{}"
    )
    service_opportunity_scores_json: Mapped[str] = mapped_column(
        "service_opportunity_scores", Text, nullable=False, default="{}"
    )
    website_analysis_data_json: Mapped[str] = mapped_column(
        "website_analysis_data", Text, nullable=False, default="{}"
    )
    analyzed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    crawl_results: Mapped[list["CrawlResult"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )

    @property
    def recommended_services(self) -> list[str]:
        return json.loads(self.recommended_services_json) if self.recommended_services_json else []

    @recommended_services.setter
    def recommended_services(self, value: list[str]) -> None:
        self.recommended_services_json = json.dumps(value or [])

    @property
    def service_recommendation_reason(self) -> dict[str, str]:
        return json.loads(self.service_recommendation_reason_json) if self.service_recommendation_reason_json else {}

    @service_recommendation_reason.setter
    def service_recommendation_reason(self, value: dict[str, str]) -> None:
        self.service_recommendation_reason_json = json.dumps(value or {})

    @property
    def service_opportunity_scores(self) -> dict[str, int]:
        return json.loads(self.service_opportunity_scores_json) if self.service_opportunity_scores_json else {}

    @service_opportunity_scores.setter
    def service_opportunity_scores(self, value: dict[str, int]) -> None:
        self.service_opportunity_scores_json = json.dumps(value or {})

    @property
    def website_analysis_data(self) -> dict[str, Any]:
        return json.loads(self.website_analysis_data_json) if self.website_analysis_data_json else {}

    @website_analysis_data.setter
    def website_analysis_data(self, value: dict[str, Any]) -> None:
        self.website_analysis_data_json = json.dumps(value or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "google_place_id": self.google_place_id,
            "business_name": self.business_name,
            "country": self.country,
            "city": self.city,
            "full_address": self.full_address,
            "google_phone": self.google_phone,
            "website_phone": self.website_phone,
            "final_phone": self.final_phone,
            "normalized_phone": self.normalized_phone,
            "email": self.email,
            "website": self.website,
            "website_domain": self.website_domain,
            "rating": self.rating,
            "user_ratings_total": self.user_ratings_total,
            "lead_score": self.lead_score,
            "priority": self.priority,
            "crawl_status": self.crawl_status,
            "lead_status": self.lead_status,
            "website_analysis_status": self.website_analysis_status,
            "website_quality_score": self.website_quality_score,
            "recommended_services": self.recommended_services,
            "service_recommendation_reason": self.service_recommendation_reason,
            "service_opportunity_scores": self.service_opportunity_scores,
            "website_analysis_data": self.website_analysis_data,
            "analyzed_at": self.analyzed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    country: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)

    requested_leads: Mapped[int] = mapped_column(Integer, nullable=False)

    total_results_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_leads_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_leads_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SearchStatus.RUNNING)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CrawlResult(Base):
    __tablename__ = "crawl_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)

    website_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    emails_found_json: Mapped[str] = mapped_column("emails_found", Text, nullable=False, default="[]")
    phones_found_json: Mapped[str] = mapped_column("phones_found", Text, nullable=False, default="[]")

    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    crawl_status: Mapped[str] = mapped_column(String(20), nullable=False, default=CrawlStatus.PENDING)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    crawled_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="crawl_results")

    @property
    def emails_found(self) -> list[str]:
        return json.loads(self.emails_found_json) if self.emails_found_json else []

    @emails_found.setter
    def emails_found(self, value: list[str]) -> None:
        self.emails_found_json = json.dumps(value or [])

    @property
    def phones_found(self) -> list[str]:
        return json.loads(self.phones_found_json) if self.phones_found_json else []

    @phones_found.setter
    def phones_found(self, value: list[str]) -> None:
        self.phones_found_json = json.dumps(value or [])
