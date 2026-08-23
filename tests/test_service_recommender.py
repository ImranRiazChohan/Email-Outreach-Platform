import config
from database.models import ServiceOpportunityLevel, ServiceType
from services.service_recommender import (
    _score_website_chatbot,
    _score_website_development,
    _score_website_redesign,
    opportunity_level,
    recommend_services,
)


def test_opportunity_level_boundaries():
    assert opportunity_level(config.SERVICE_RECOMMEND_THRESHOLD) == ServiceOpportunityLevel.RECOMMENDED
    assert opportunity_level(config.SERVICE_RECOMMEND_THRESHOLD - 1) == ServiceOpportunityLevel.POTENTIAL
    assert opportunity_level(config.SERVICE_POTENTIAL_THRESHOLD) == ServiceOpportunityLevel.POTENTIAL
    assert opportunity_level(config.SERVICE_POTENTIAL_THRESHOLD - 1) == ServiceOpportunityLevel.NOT_RECOMMENDED


def test_website_development_score_no_website_vs_website():
    assert _score_website_development({"website_exists": False}) == 100
    assert _score_website_development({"website_exists": True}) == 0


def test_website_chatbot_score_detected_vs_not():
    detected = _score_website_chatbot({"website_exists": True, "chatbot_detected": True})
    not_detected = _score_website_chatbot({
        "website_exists": True,
        "chatbot_detected": False,
        "contact_form_detected": True,
        "call_to_action_detected": True,
        "phone_number_detected": True,
        "booking_language_detected": True,
    })
    assert detected < config.SERVICE_POTENTIAL_THRESHOLD
    assert not_detected >= config.SERVICE_RECOMMEND_THRESHOLD

    no_website = _score_website_chatbot({"website_exists": False})
    assert no_website == 0


def test_website_redesign_score_high_quality_vs_low_quality():
    good_site_score = _score_website_redesign({"website_exists": True}, 90)
    poor_site_score = _score_website_redesign({"website_exists": True}, 20)
    no_website_score = _score_website_redesign({"website_exists": False}, None)

    assert good_site_score < config.SERVICE_POTENTIAL_THRESHOLD
    assert poor_site_score >= config.SERVICE_RECOMMEND_THRESHOLD
    assert no_website_score == 0


def test_recommend_services_no_website_only_recommends_development():
    result = recommend_services(
        business_name="Test Biz",
        analysis_data={"website_exists": False},
        website_quality_score=None,
        has_phone=True,
        user_ratings_total=10,
    )
    assert result.recommended_services == [ServiceType.WEBSITE_DEVELOPMENT]
    assert result.service_opportunity_scores[ServiceType.WEBSITE_DEVELOPMENT] == 100
    # every service must have a reason, even ones not recommended
    assert set(result.service_recommendation_reason.keys()) == set(ServiceType.ALL)
    assert all(isinstance(v, str) and v for v in result.service_recommendation_reason.values())


def test_recommend_services_poor_website_recommends_redesign_and_chatbot():
    analysis_data = {
        "website_exists": True,
        "chatbot_detected": False,
        "contact_form_detected": True,
        "call_to_action_detected": True,
        "phone_number_detected": True,
        "booking_language_detected": True,
    }
    result = recommend_services(
        business_name="Poor Site Biz",
        analysis_data=analysis_data,
        website_quality_score=25,
        has_phone=True,
        user_ratings_total=100,
    )
    assert ServiceType.WEBSITE_REDESIGN in result.recommended_services
    assert ServiceType.WEBSITE_CHATBOT in result.recommended_services
    assert ServiceType.WEBSITE_DEVELOPMENT not in result.recommended_services
    for score in result.service_opportunity_scores.values():
        assert 0 <= score <= 100
