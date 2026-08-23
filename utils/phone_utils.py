"""Phone number normalization for duplicate comparison and display.

Normalization is deliberately lenient: it aims to produce a stable key for
duplicate detection (digits only, country-code aware where possible) rather
than a strictly validated E.164 number.
"""
from __future__ import annotations

import re

import phonenumbers

# Fallback ISO country name -> region code for the countries most likely to be
# used in this MVP. phonenumbers itself only understands region codes, not
# free-text country names, so we translate the common ones here.
_COUNTRY_NAME_TO_REGION = {
    "pakistan": "PK",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "india": "IN",
    "canada": "CA",
    "australia": "AU",
    "uae": "AE",
    "united arab emirates": "AE",
    "saudi arabia": "SA",
}


def _guess_region(country: str | None) -> str | None:
    if not country:
        return None
    return _COUNTRY_NAME_TO_REGION.get(country.strip().lower())


def normalize_phone(raw_phone: str | None, country: str | None = None) -> str | None:
    """Normalize a phone number to digits-only E.164-like form (e.g. 923001234567).

    Handles inputs like "+92 300 1234567", "0300-1234567", "92 300 1234567"
    all normalizing to the same key when a region hint is available.
    """
    if not raw_phone or not raw_phone.strip():
        return None

    region = _guess_region(country)

    try:
        parsed = phonenumbers.parse(raw_phone, region)
        if phonenumbers.is_possible_number(parsed):
            return str(parsed.country_code) + str(parsed.national_number)
    except phonenumbers.NumberParseException:
        pass

    # Fallback: strip everything but digits, drop a leading trunk zero.
    digits = re.sub(r"\D", "", raw_phone)
    digits = digits.lstrip("0") if len(digits) > 6 else digits
    return digits or None


def is_valid_phone(raw_phone: str | None) -> bool:
    if not raw_phone:
        return False
    digits = re.sub(r"\D", "", raw_phone)
    return 6 <= len(digits) <= 15
