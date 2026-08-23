"""Entry point for the Lead Generation & Enrichment Platform Streamlit app."""
from __future__ import annotations

import streamlit as st

from database.connection import init_db
from utils.ui import inject_theme

st.set_page_config(
    page_title="Lead Generation & Enrichment Platform",
    page_icon="📇",
    layout="wide",
)

init_db()
inject_theme()

st.title("📇 Lead Generation & Enrichment Platform")
st.markdown(
    """
    Welcome. Use the sidebar to navigate:

    - **Dashboard** — overview metrics and charts across all saved leads.
    - **Generate Leads** — search Google Places for a keyword/country/city and
      generate new, deduplicated, enriched leads.
    - **Leads** — browse, filter, search, and manage every lead ever saved.

    Leads saved here are **permanent** — a business that has already been
    found once will never be returned again as a "new" lead in a future
    search.
    """
)
