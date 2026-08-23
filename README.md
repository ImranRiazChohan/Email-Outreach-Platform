# Lead Generation & Enrichment Platform

A local MVP web application for finding businesses via Google Maps, permanently
deduplicating them, enriching them with emails/phones scraped from their
websites, scoring them, analyzing their websites to recommend which of our
services to pitch them, and managing the resulting leads — all through a
Streamlit UI backed by SQLite.

## Project Overview

Given a **keyword**, **country**, **city**, and a **required number of leads**,
the app searches Google Places (New), skips every business already saved from
a previous search (by place ID, website domain, or phone number), crawls the
websites of new businesses to extract emails and phone numbers, scores each
lead, and stores everything permanently in SQLite.

The single most important rule: **a lead that has already been generated and
saved must never appear again as a new lead in any future search.**

## Features

- Google Places API (New) search with automatic pagination
- Permanent, three-layer duplicate detection (place ID → website domain →
  normalized phone)
- Async, concurrency-limited homepage-only website crawling
- Email and phone extraction with smart primary-contact selection
- A business is only saved if it has a website with a discoverable email —
  phone number presence/absence never affects that decision
- Rule-based lead scoring and HIGH/MEDIUM/LOW prioritization
- **Website Analysis & Service Recommendation**: every crawled website is
  scored 0-100 for quality and analyzed for chatbot/contact-form/CTA/mobile
  signals, producing an opportunity score (0-100) and a recommendation for
  each of four services (AI Calling Agent, Website Chatbot, Website
  Development, Website Redesign), with a human-readable reason for each
- Dashboard with metrics, charts, and service-opportunity counts
- Filterable, searchable, paginated leads table with an editable detail view
- Per-run search history tracked internally (duplicate/new-lead accounting,
  used to mark a run COMPLETED/PARTIAL/FAILED)
- Resilient to API failures, dead websites, SSL errors, and timeouts

## Architecture

```
Streamlit Pages  →  Services (business logic)  →  Database (SQLAlchemy/SQLite)
                  →  Utils (normalization/validation)
                  →  Google Places API / target websites (HTTPX)
```

- **pages/** contain presentation logic only — no direct DB or API calls.
- **services/** contain all business logic (search orchestration, duplicate
  detection, crawling, extraction, scoring).
- **database/** contains SQLAlchemy models, the engine/session factory, and
  CRUD helpers — the only layer that touches SQL.
- **utils/** contains pure, dependency-light helper functions (normalization,
  validation) reused across services.

Because all persistence goes through SQLAlchemy Core/ORM with a single
`DATABASE_URL`, migrating from SQLite to PostgreSQL later only requires
changing that URL — no other code changes are needed.

## Project Structure

```
.
├── app.py                       # Streamlit entry point
├── config.py                    # Centralized configuration (env-driven)
├── logging_config.py            # Shared logging setup
├── pages/
│   ├── 1_Dashboard.py
│   ├── 2_Generate_Leads.py
│   └── 3_Leads.py
├── database/
│   ├── connection.py             # Engine, session factory, init_db()
│   ├── models.py                 # Lead, SearchHistory, CrawlResult
│   └── crud.py                   # All DB read/write operations
├── services/
│   ├── google_places.py          # Google Places API (New) client
│   ├── duplicate_service.py      # 3-layer duplicate detection
│   ├── crawler.py                # Async website crawler
│   ├── email_extractor.py
│   ├── phone_extractor.py
│   ├── lead_scoring.py           # Rule-based scoring/priority
│   ├── website_analyzer.py       # Rule-based website feature detection + quality score
│   ├── service_recommender.py    # Service opportunity scoring engine
│   ├── gemini_client.py          # Gemini wrapper (recommendation reason text only)
│   └── lead_generation_service.py# Orchestrates the full pipeline
├── utils/
│   ├── url_utils.py               # Domain/URL normalization
│   ├── phone_utils.py             # Phone normalization
│   ├── address_utils.py           # Country/city extraction
│   ├── ui.py                      # Streamlit theming/pill/stat-card helpers
│   └── validators.py
├── data/
│   └── leads.db                  # Created automatically on first run
├── tests/
│   ├── test_duplicates.py
│   ├── test_normalization.py
│   ├── test_extractors.py
│   ├── test_website_analyzer.py
│   └── test_service_recommender.py
├── .env.example
├── requirements.txt
└── README.md
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Google Places API (New) key | — (required) |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///data/leads.db` |
| `MAX_CONCURRENT_CRAWLS` | Max concurrent website requests | `5` |
| `CRAWL_TIMEOUT_SECONDS` | Per-request timeout | `10` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `GEMINI_API_KEY` | Gemini API key — used only to write recommendation "reason" text | — (optional; falls back to canned reasons if unset) |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.5-flash-lite` |
| `GEMINI_TEMPERATURE` | Gemini sampling temperature | `0.7` |
| `GEMINI_MAX_TOKENS` | Gemini max output tokens | `4096` |
| `SERVICE_RECOMMEND_THRESHOLD` | Opportunity score ≥ this → actively recommended | `70` |
| `SERVICE_POTENTIAL_THRESHOLD` | Opportunity score in `[this, RECOMMEND)` → potential opportunity | `50` |
| `WEBSITE_REDESIGN_QUALITY_THRESHOLD` | Below this website quality score, a redesign is considered | `60` |

Never commit a real `.env` file or hardcode API keys in source.

## Google Places API Setup

1. Create/select a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable **Places API (New)** (not the legacy Places API).
3. Create an API key and restrict it to Places API (New).
4. Put the key in `.env` as `GOOGLE_MAPS_API_KEY`.

The app calls the Text Search (New) and Place Details (New) REST endpoints
directly via HTTPX — no deprecated client libraries are used.

## How To Run

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (typically `http://localhost:8501`).

Run the test suite:

```bash
pytest
```

## Database Information

SQLite database file: `data/leads.db` (created automatically on first run via
`init_db()`). Three tables:

- **leads** — permanent master table, one row per unique business
  (`UNIQUE(google_place_id)`). Beyond contact/scoring fields, it also carries
  the website analysis result: `website_analysis_status`,
  `website_quality_score`, `recommended_services` (JSON list),
  `service_recommendation_reason` (JSON map), `service_opportunity_scores`
  (JSON map), `website_analysis_data` (JSON map), `analyzed_at`.
- **search_history** — one row per lead-generation run, with duplicate/new
  counts and status (`RUNNING` / `COMPLETED` / `PARTIAL` / `FAILED`).
- **crawl_results** — one row per website crawl attempt, storing all emails
  and phones found (JSON) plus crawl status/errors.

There is no migration framework (Alembic is out of MVP scope). Instead,
`init_db()` runs a small schema-sync step on every startup that adds any
model columns missing from an already-existing SQLite database via
`ALTER TABLE ... ADD COLUMN` — so pulling code with new `Lead` fields onto an
existing `data/leads.db` just works without manually recreating the database.

## Duplicate Detection Logic

Checked in order, cheapest and most authoritative first:

1. **`google_place_id`** — exact match → always skip (enforced by a DB unique
   constraint as a hard backstop).
2. **normalized website domain** — `https://www.example.com/`,
   `http://example.com`, and `www.example.com` all normalize to `example.com`;
   a match means the business already exists under a different search.
3. **normalized phone number** — `+92 300 1234567`, `0300-1234567`, and
   `92 300 1234567` all normalize to the same key; a match means the business
   already exists.

Only businesses that pass all three checks are counted toward the user's
requested lead quantity. The search keeps paginating Google Places until
either the requested count of **new** leads is reached or Google has no more
results to offer (in which case the search is marked `PARTIAL`).

## Website Crawling Logic

Crawling is intentionally shallow — **homepage only, no internal-link
following**:

1. Fetch the homepage only (one request, with an HTTP fallback if HTTPS
   fails, bounded by `CRAWL_TIMEOUT_SECONDS`). If the request fails
   certificate verification, it is retried once without verification —
   corporate networks and some hosts intercept TLS with a self-signed
   certificate, which otherwise blocks every crawl outright even though the
   site itself is fine.
2. Extract emails from **anywhere on that homepage** — visible text, raw
   HTML, and `mailto:` links (footer included, but not limited to it).
3. Extract phone numbers from anywhere on the homepage (visible text and
   `tel:` links).
4. Pick one **primary email** (preferring `sales@` / `contact@` / `info@` /
   `hello@` / `business@` over generic technical addresses) and one primary
   phone number; all discovered values are stored as JSON in `crawl_results`.
5. A website that fails, times out, or has a bad certificate never stops the
   run — it's simply discarded (see the email-mandatory rule below) and the
   pipeline continues with the next business.

Crawling runs asynchronously (HTTPX + asyncio) with a configurable concurrency
cap (`MAX_CONCURRENT_CRAWLS`, default 5) so the app stays responsive.

### Email Is Mandatory

A business is only saved as a lead if it has a website **and** that
website's homepage crawl turns up an email. Phone number presence or
absence never affects this decision either way — it's still captured and
stored on the lead when available, it's just not a requirement:

- No website at all → discarded, not saved, not counted (no possible email
  source, regardless of any phone number Google provided).
- Website, homepage crawl finds an email → saved, `lead_status` set to
  `ENRICHED`. Any phone found (Google's or the website's) is stored too.
- Website, but the crawl fails or the homepage has no email → discarded,
  not saved, not counted, even if a phone number was available.

Because a discarded business is never written to `leads`, it is **not**
protected by the duplicate-prevention rule — it may be re-checked (and
re-crawled) in a future search. Only businesses that make it into the
database (i.e. have an email) are permanently deduplicated.

## Website Analysis & Service Recommendation

After a lead is saved, its crawled homepage (or lack of one) is analyzed to
answer: **what service should we sell to this customer, and why?** The four
services this platform can pitch are `AI Calling Agent`, `Website Chatbot`,
`Website Development`, and `Website Redesign` — a lead can end up with zero,
one, or several of them recommended.

All scoring and feature detection is deterministic, rule-based HTML analysis
(`services/website_analyzer.py`, `services/service_recommender.py`) — **no
AI call is involved in deciding a score.** Gemini (`services/gemini_client.py`)
is used for exactly one thing: writing the short, human-readable *reason*
text behind an already-computed score. If `GEMINI_API_KEY` is unset, the
Gemini call fails, or its response is malformed, a canned rule-based reason
template is used instead — recommendations are always fully populated either
way.

### Website Quality Score (0-100)

| Signal | Points |
|---|---|
| HTTPS enabled | 10 |
| Mobile friendly (viewport meta tag) | 20 |
| Working navigation (`<nav>` or a header with 3+ links) | 10 |
| Clear call-to-action text detected | 10 |
| Contact info available (email or phone found) | 10 |
| Contact form available | 10 |
| Good page structure (3+ semantic HTML5 tags) | 10 |
| Modern visual structure (0-100 sub-score × 10%) | up to 10 |
| Good performance (0-100 sub-score × 10%) | up to 10 |

Categories: 80-100 Good · 60-79 Average · 40-59 Poor · 0-39 Very Poor.

### Per-Service Opportunity Logic

- **Website Development** — binary: `100` if there is no website (or it
  could not be reached at all during crawling), otherwise `0`. No further
  crawling happens for a business with no website.
- **Website Chatbot** — checked against known chat-widget signatures
  (Intercom, Tawk.to, Crisp, Drift, Zendesk Chat, HubSpot Chat, Freshchat,
  LiveChat, Messenger/WhatsApp widgets, generic chat containers/iframes). If
  one is found, the opportunity score is low; otherwise it scales up with
  contact-form/CTA/phone/booking-language signals.
- **AI Calling Agent** — the platform never claims "no AI calling agent
  exists" (a website can't reveal a business's internal phone system). It
  only reports an *opportunity*, scaled up by phone presence, booking/
  appointment language, contact forms, CTAs, and review volume.
- **Website Redesign** — scaled inversely to `website_quality_score`,
  anchored to the quality bands above so a Poor/Very Poor site always lands
  in the "recommended" tier and a Good site always lands well below it.

### Recommendation Thresholds

Configurable via `SERVICE_RECOMMEND_THRESHOLD` (default 70) and
`SERVICE_POTENTIAL_THRESHOLD` (default 50):

```
score >= 70   -> Recommended   (shown in the main "Recommended Services" column)
50-69         -> Potential Opportunity
< 50          -> Not Recommended
```

## Known MVP Limitations

- No authentication, multi-user support, or team management.
- No email sending, campaign management, or CRM integration.
- No PostgreSQL, Celery, or Redis — SQLite and in-process async only (the
  codebase is structured so PostgreSQL is a drop-in `DATABASE_URL` change).
- Google Places Text Search (New) caps results at roughly 60 per query; if a
  keyword/location combination genuinely doesn't have enough unique
  businesses, the search will complete with `PARTIAL` status rather than the
  full requested count.
- Contact extraction is heuristic (regex/keyword based), not AI-based —
  occasional false positives/negatives on emails and phone numbers are
  expected, by design, for this MVP.
- Website analysis uses no headless browser or rendering engine — it inspects
  static HTML only. `modern_design_score` and `performance_score` are
  therefore approximations (HTML5/CSS/favicon presence, and fetch
  time/page size respectively), not a real Lighthouse-style audit.
  Chatbot/contact-form/CTA detection is pattern-based and can occasionally
  miss a heavily-JavaScript-rendered widget or produce a false positive.
