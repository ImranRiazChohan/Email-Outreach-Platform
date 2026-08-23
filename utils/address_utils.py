"""Helpers for extracting country/city from Google Places address components."""
from __future__ import annotations

from typing import Any


def extract_country_city(address_components: list[dict[str, Any]] | None, formatted_address: str | None) -> tuple[str | None, str | None]:
    """Pull country and city out of Google's structured addressComponents.

    Falls back to a best-effort split of the formatted address if structured
    components are unavailable (e.g. legacy responses).
    """
    country: str | None = None
    city: str | None = None

    for component in address_components or []:
        types = component.get("types", [])
        long_text = component.get("longText") or component.get("long_name")
        if "country" in types:
            country = long_text
        elif "locality" in types and not city:
            city = long_text
        elif "administrative_area_level_2" in types and not city:
            city = long_text
        elif "postal_town" in types and not city:
            city = long_text

    if not city:
        for component in address_components or []:
            types = component.get("types", [])
            if "administrative_area_level_1" in types:
                city = component.get("longText") or component.get("long_name")
                break

    if (not country or not city) and formatted_address:
        parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
        if not country and parts:
            country = parts[-1]
        if not city and len(parts) >= 2:
            city = parts[-2]

    return country, city
