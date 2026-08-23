"""Thin Gemini wrapper - used ONLY to phrase the human-readable "reason" text
behind each service recommendation. All opportunity scores and feature
detection are computed elsewhere by deterministic, rule-based logic (see
services/website_analyzer.py and services/service_recommender.py); Gemini
never decides a score, it only explains one that's already been calculated.

Never raises: a missing/invalid API key, quota error, or network failure
always falls back to a canned, rule-based reason template so a lead's
recommendation is still fully populated even if the AI call is unavailable.
"""
from __future__ import annotations

import json
from typing import Any

import config
from logging_config import get_logger

logger = get_logger(__name__)

_client: Any = None
_client_init_attempted = False

_PROMPT_TEMPLATE = """You are a sales analyst for an agency that sells four services to local businesses:
- AI Calling Agent
- Website Chatbot
- Website Development
- Website Redesign

For the business below, write ONE short, specific, sales-team-friendly reason (1-2 sentences) for EACH service listed, explaining why it received its opportunity score. Base the reason only on the signals given - do not invent facts. Do not mention the numeric score in the text.

Return strict JSON with exactly these keys: {service_names}. Each value is the reason string for that service.

Business name: {business_name}
Detected website/business signals: {signals_json}
Opportunity scores (0-100): {scores_json}
"""


def _get_client() -> Any:
    global _client, _client_init_attempted
    if _client_init_attempted:
        return _client
    _client_init_attempted = True

    if not config.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY not set - service recommendation reasons will use rule-based templates.")
        return None

    try:
        from google import genai

        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to initialize Gemini client - falling back to rule-based reasons.")
        _client = None
    return _client


def generate_reasons(
    *, business_name: str, services: list[str], signals: dict[str, Any], scores: dict[str, int]
) -> dict[str, str]:
    """Return {service_name: reason_text} for every service in `services`.

    Falls back to a deterministic canned reason per service if Gemini is
    unavailable, misconfigured, returns malformed output, or errors out.
    """
    client = _get_client()
    if client is not None:
        try:
            prompt = _PROMPT_TEMPLATE.format(
                service_names=", ".join(services),
                business_name=business_name,
                signals_json=json.dumps(signals, default=str),
                scores_json=json.dumps({s: scores.get(s, 0) for s in services}),
            )
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config={
                    "temperature": config.GEMINI_TEMPERATURE,
                    "max_output_tokens": config.GEMINI_MAX_TOKENS,
                    "response_mime_type": "application/json",
                },
            )
            parsed = json.loads(response.text)
            if isinstance(parsed, dict) and all(s in parsed and parsed[s] for s in services):
                return {s: str(parsed[s]).strip() for s in services}
            logger.warning("Gemini reason response missing expected keys, using fallback reasons.")
        except Exception:  # noqa: BLE001
            logger.exception("Gemini reason generation failed, using fallback reasons.")

    return {service: fallback_reason(service, signals, scores.get(service, 0)) for service in services}


def fallback_reason(service: str, signals: dict[str, Any], score: int) -> str:
    """Deterministic canned reason, used when Gemini is unavailable or fails."""
    recommend = score >= config.SERVICE_RECOMMEND_THRESHOLD
    potential = config.SERVICE_POTENTIAL_THRESHOLD <= score < config.SERVICE_RECOMMEND_THRESHOLD
    website_exists = signals.get("website_exists", True)

    if service == "AI Calling Agent":
        if recommend:
            return (
                "The business appears to rely heavily on customer calls and inquiries. AI call "
                "automation could help handle repetitive inquiries, lead qualification, appointment "
                "scheduling, or customer follow-ups."
            )
        if potential:
            return (
                "The business shows some phone or inquiry-based interaction signals, so AI call "
                "automation could help with a portion of inbound inquiries."
            )
        return "Limited phone or inquiry-based interaction signals were found, so call automation is a lower priority here."

    if service == "Website Chatbot":
        if not website_exists:
            return "There is no website yet, so a chatbot has nowhere to be installed until one is built."
        if signals.get("chatbot_detected"):
            return "A chatbot or live chat widget is already present on the website, so this is a lower-priority opportunity."
        if recommend:
            return (
                "No chatbot or live chat functionality was detected. The website relies on traditional "
                "contact methods and may benefit from automated customer engagement and lead capture."
            )
        if potential:
            return "No chatbot was detected, but the site shows only moderate signals for automated engagement."
        return "No strong signals suggest an immediate need for a chatbot on this website."

    if service == "Website Development":
        if not website_exists:
            return (
                "No active business website was found. The business may benefit from a professional "
                "website to establish an online presence and capture customer inquiries."
            )
        if signals.get("website_analysis_status") == "FAILED":
            return "The business's website could not be reached during analysis, so a reliable rebuild may be needed."
        return "The business already has a working website, so a new website build is not required."

    if service == "Website Redesign":
        if not website_exists:
            return "There is no website yet, so a redesign does not apply until one is built."
        if recommend:
            return (
                "The website shows multiple quality issues including outdated structure, weak calls to "
                "action, poor mobile experience, or other usability problems. A redesign may improve the "
                "customer experience and lead conversion."
            )
        if potential:
            return "The website has a few quality gaps that a redesign could address, though the overall issues are moderate."
        return "The website meets most modern quality standards, so a redesign is a low priority right now."

    return "No specific signals were available to explain this recommendation."
