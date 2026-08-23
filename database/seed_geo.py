"""One-time seed of the countries/cities reference tables from data/countries_cities.json."""
from __future__ import annotations

import json

from sqlalchemy import func, select

import config
from database.connection import get_session
from database.models import City, Country
from logging_config import get_logger

logger = get_logger(__name__)

_GEO_DATA_PATH = config.BASE_DIR / "data" / "countries_cities.json"


def seed_countries_and_cities() -> None:
    """Populate `countries`/`cities` from the bundled JSON, skipping if already seeded."""
    with get_session() as session:
        already_seeded = session.scalar(select(func.count(Country.id))) or 0
        if already_seeded:
            return

        with open(_GEO_DATA_PATH, encoding="utf-8") as f:
            countries = json.load(f)

        for entry in countries:
            country = Country(name=entry["name"])
            session.add(country)
            session.flush()
            city_names = dict.fromkeys(entry.get("cities") or [])  # dedupe, preserve order
            if city_names:
                session.bulk_insert_mappings(
                    City,
                    [{"country_id": country.id, "name": city_name} for city_name in city_names],
                )

        logger.info("Seeded %d countries and their cities", len(countries))
