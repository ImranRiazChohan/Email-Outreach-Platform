"""Google Places API (New) client.

Uses the Text Search (New) endpoint for discovery and the Place Details (New)
endpoint as a fallback when a search result is missing fields. Handles
pagination via `nextPageToken`, basic rate limiting, and error handling so a
single failed request never crashes the whole lead-generation run.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

import config
from logging_config import get_logger
from utils.address_utils import extract_country_city

logger = get_logger(__name__)

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.addressComponents,"
    "places.nationalPhoneNumber,places.internationalPhoneNumber,places.websiteUri,"
    "places.rating,places.userRatingCount,nextPageToken"
)
DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,addressComponents,nationalPhoneNumber,"
    "internationalPhoneNumber,websiteUri,rating,userRatingCount"
)

MAX_PAGES = 60  # Google Places New caps text search at ~60 results (3 pages of 20)
PAGE_TOKEN_DELAY_SECONDS = 2.0


class GooglePlacesError(Exception):
    """Raised when the Places API returns an unrecoverable error."""


@dataclass
class PlaceResult:
    google_place_id: str
    business_name: str
    formatted_address: Optional[str]
    country: Optional[str]
    city: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    rating: Optional[float]
    user_ratings_total: Optional[int]
    raw: dict[str, Any] = field(default_factory=dict)


def _api_key_headers(field_mask: str) -> dict[str, str]:
    if not config.GOOGLE_MAPS_API_KEY:
        raise GooglePlacesError("GOOGLE_MAPS_API_KEY is not configured. Set it in your .env file.")
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": config.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": field_mask,
    }


def _parse_place(raw_place: dict[str, Any]) -> PlaceResult:
    place_id = raw_place.get("id", "")
    display_name = (raw_place.get("displayName") or {}).get("text", "Unknown")
    formatted_address = raw_place.get("formattedAddress")
    address_components = raw_place.get("addressComponents", [])
    country, city = extract_country_city(address_components, formatted_address)

    phone = raw_place.get("nationalPhoneNumber") or raw_place.get("internationalPhoneNumber")

    return PlaceResult(
        google_place_id=place_id,
        business_name=display_name,
        formatted_address=formatted_address,
        country=country,
        city=city,
        phone=phone,
        website=raw_place.get("websiteUri"),
        rating=raw_place.get("rating"),
        user_ratings_total=raw_place.get("userRatingCount"),
        raw=raw_place,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def _post_search(client: httpx.Client, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post(TEXT_SEARCH_URL, headers=_api_key_headers(SEARCH_FIELD_MASK), json=body)
    if response.status_code == 429:
        logger.warning("Google Places API rate limited (429). Backing off.")
        raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
    if response.status_code >= 500:
        raise httpx.HTTPStatusError("Server error", request=response.request, response=response)
    if response.status_code >= 400:
        logger.error("Google Places API error %s: %s", response.status_code, response.text[:500])
        raise GooglePlacesError(f"Google Places API returned {response.status_code}: {response.text[:300]}")
    return response.json()


def search_places(keyword: str, country: str, city: str, *, max_results: int = 1000) -> Iterator[PlaceResult]:
    """Yield PlaceResult objects for a text query, transparently paginating.

    Stops after Google's own result cap (~60 for Text Search) or `max_results`,
    whichever comes first. Callers decide when they have "enough new leads"
    and can stop iterating early.
    """
    text_query = f"{keyword} in {city}, {country}"
    logger.info("Starting Google Places search: %r", text_query)

    yielded = 0
    page_token: Optional[str] = None

    with httpx.Client(timeout=20.0) as client:
        for page_number in range(1, MAX_PAGES + 1):
            body: dict[str, Any] = {"textQuery": text_query}
            if page_token:
                body["pageToken"] = page_token

            try:
                payload = _post_search(client, body)
            except GooglePlacesError:
                raise
            except Exception as exc:  # noqa: BLE001 - network/HTTP errors after retries exhausted
                logger.error("Google Places search failed on page %s: %s", page_number, exc)
                raise GooglePlacesError(str(exc)) from exc

            places = payload.get("places", [])
            logger.info("Google Places page %s returned %s results", page_number, len(places))

            for raw_place in places:
                if yielded >= max_results:
                    return
                yield _parse_place(raw_place)
                yielded += 1

            page_token = payload.get("nextPageToken")
            if not page_token or not places:
                break

            time.sleep(PAGE_TOKEN_DELAY_SECONDS)  # next page token needs a moment to become valid


def get_place_details(place_id: str) -> Optional[PlaceResult]:
    """Fetch full details for a single place. Used as a fallback/refresh path."""
    try:
        with httpx.Client(timeout=15.0) as client:
            url = PLACE_DETAILS_URL.format(place_id=place_id)
            response = client.get(url, headers=_api_key_headers(DETAILS_FIELD_MASK))
            if response.status_code >= 400:
                logger.error("Place details error %s for %s: %s", response.status_code, place_id, response.text[:300])
                return None
            return _parse_place(response.json())
    except Exception as exc:  # noqa: BLE001
        logger.error("Place details request failed for %s: %s", place_id, exc)
        return None
