"""Service Opportunity Recommendation Engine.

Given a business's website analysis data (services/website_analyzer.py) plus
its contact/rating signals, computes a 0-100 opportunity score for each of
the four services this platform sells, decides which ones are worth
actively recommending, and gets a human-readable reason for each score from
services/gemini_client.py. Scoring itself is 100% rule-based and never
depends on the AI call succeeding, so recommendations stay deterministic.

Kept isolated behind `recommend_services()` so the scoring model can evolve
(or be swapped for something fancier) without touching callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import config
from database.models import ServiceOpportunityLevel, ServiceType
from services.gemini_client import generate_reasons


@dataclass
class ServiceRecommendationResult:
    website_quality_score: int | None
    website_analysis_data: dict[str, Any]
    service_opportunity_scores: dict[str, int]
    service_recommendation_reason: dict[str, str]
    recommended_services: list[str]


def opportunity_level(score: int) -> str:
    if score >= config.SERVICE_RECOMMEND_THRESHOLD:
        return ServiceOpportunityLevel.RECOMMENDED
    if score >= config.SERVICE_POTENTIAL_THRESHOLD:
        return ServiceOpportunityLevel.POTENTIAL
    return ServiceOpportunityLevel.NOT_RECOMMENDED


def _score_ai_calling_agent(
    analysis_data: dict[str, Any], *, has_phone: bool, user_ratings_total: int | None
) -> int:
    # A website cannot tell us whether an AI calling agent already exists, so
    # this is always framed as an "opportunity" driven by call/inquiry
    # volume signals, never as "no AI calling agent detected".
    if not has_phone:
        return 10

    score = 40
    if analysis_data.get("booking_language_detected"):
        score += 25
    if analysis_data.get("call_to_action_detected"):
        score += 10
    if analysis_data.get("contact_form_detected"):
        score += 10
    if user_ratings_total and user_ratings_total > config.RATING_COUNT_THRESHOLD:
        score += 10
    if not analysis_data.get("website_exists", True):
        score += 5  # phone is likely their primary/only contact channel
    return min(100, score)


def _score_website_chatbot(analysis_data: dict[str, Any]) -> int:
    if not analysis_data.get("website_exists", True):
        return 0  # nowhere to install a chatbot yet
    if analysis_data.get("chatbot_detected"):
        return 15

    score = 50
    if analysis_data.get("contact_form_detected"):
        score += 15
    if analysis_data.get("call_to_action_detected"):
        score += 10
    if analysis_data.get("phone_number_detected"):
        score += 10
    if analysis_data.get("booking_language_detected"):
        score += 10
    return min(100, score)


def _score_website_development(analysis_data: dict[str, Any]) -> int:
    return 0 if analysis_data.get("website_exists", True) else 100


def _score_website_redesign(analysis_data: dict[str, Any], quality_score: int | None) -> int:
    if not analysis_data.get("website_exists", True) or quality_score is None:
        return 0  # nothing to redesign

    # Piecewise-linear, anchored to the "Suggested categories" quality bands
    # (Good 80-100 / Average 60-79 / Poor 40-59 / Very Poor 0-39) so a Poor
    # or Very Poor site always lands in the "recommended" opportunity tier,
    # while a Good site always lands well below it.
    if quality_score >= 80:
        return max(0, round(30 - (quality_score - 80) * 1.5))
    if quality_score >= 60:
        return round(50 - (quality_score - 60))
    if quality_score >= 40:
        return round(70 + (59 - quality_score) * 0.5)
    return min(100, round(85 + (39 - quality_score) * 0.4))


def recommend_services(
    *,
    business_name: str,
    analysis_data: dict[str, Any],
    website_quality_score: int | None,
    has_phone: bool,
    user_ratings_total: int | None,
) -> ServiceRecommendationResult:
    """Compute opportunity scores/recommendations for all four services.

    `analysis_data` must at least contain `website_exists`; pass the full
    dict from services/website_analyzer.py when a website was crawled, or
    `{"website_exists": False}` when there is none. The reason text (only)
    comes from Gemini, with an automatic rule-based fallback if that call is
    unavailable or fails - see services/gemini_client.py.
    """
    scores = {
        ServiceType.AI_CALLING_AGENT: _score_ai_calling_agent(
            analysis_data, has_phone=has_phone, user_ratings_total=user_ratings_total
        ),
        ServiceType.WEBSITE_CHATBOT: _score_website_chatbot(analysis_data),
        ServiceType.WEBSITE_DEVELOPMENT: _score_website_development(analysis_data),
        ServiceType.WEBSITE_REDESIGN: _score_website_redesign(analysis_data, website_quality_score),
    }

    recommended = [s for s in ServiceType.ALL if scores[s] >= config.SERVICE_RECOMMEND_THRESHOLD]

    reasons = generate_reasons(
        business_name=business_name,
        services=ServiceType.ALL,
        signals=analysis_data,
        scores=scores,
    )

    return ServiceRecommendationResult(
        website_quality_score=website_quality_score,
        website_analysis_data=analysis_data,
        service_opportunity_scores=scores,
        service_recommendation_reason=reasons,
        recommended_services=recommended,
    )
