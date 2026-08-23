"""Central application configuration, loaded once from environment/.env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'leads.db').as_posix()}")

MAX_CONCURRENT_CRAWLS: int = int(os.getenv("MAX_CONCURRENT_CRAWLS", "5"))
CRAWL_TIMEOUT_SECONDS: float = float(os.getenv("CRAWL_TIMEOUT_SECONDS", "10"))

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Gemini is used ONLY to write the human-readable "reason" text behind each
# service recommendation. All scores/detection are deterministic/rule-based
# (see services/website_analyzer.py and services/service_recommender.py) so
# recommendations stay stable and reproducible even if the AI call fails.
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))

# Service opportunity score thresholds (0-100). Configurable per the product
# spec: >=RECOMMEND -> actively recommended, POTENTIAL..RECOMMEND-1 -> shown
# as a potential opportunity, below POTENTIAL -> not recommended.
SERVICE_RECOMMEND_THRESHOLD: int = int(os.getenv("SERVICE_RECOMMEND_THRESHOLD", "70"))
SERVICE_POTENTIAL_THRESHOLD: int = int(os.getenv("SERVICE_POTENTIAL_THRESHOLD", "50"))

# Below this website_quality_score, a Website Redesign is considered.
WEBSITE_REDESIGN_QUALITY_THRESHOLD: int = int(os.getenv("WEBSITE_REDESIGN_QUALITY_THRESHOLD", "60"))

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

PRIORITY_EMAIL_PREFIXES = ["sales", "contact", "info", "hello", "business"]

RATING_COUNT_THRESHOLD = 50
STRONG_RATING_THRESHOLD = 4.0
