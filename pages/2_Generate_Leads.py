"""Generate Leads: the main search -> dedupe -> enrich -> save workflow."""
from __future__ import annotations

import streamlit as st

from database.connection import get_session, init_db
from database.crud import list_all_countries, list_cities_for_country
from services.lead_generation_service import run_lead_generation
from utils.ui import inject_theme, stat_card, step_row
from utils.validators import validate_lead_generation_inputs

st.set_page_config(page_title="Generate Leads", page_icon="🔍", layout="wide")
init_db()
inject_theme()

st.title("🔍 Generate Leads")
st.caption(
    "Search Google Places for new businesses. Leads already saved in the database "
    "will never be counted or returned again."
)

STEP_ORDER = ["search", "dedupe", "crawl", "email", "phone", "analyze", "recommend", "save"]
STEP_LABELS = {
    "search": "Searching Google Places",
    "dedupe": "Checking duplicate leads",
    "crawl": "Crawling websites",
    "email": "Extracting emails",
    "phone": "Extracting phone numbers",
    "analyze": "Analyzing websites",
    "recommend": "Recommending services",
    "save": "Saving leads",
}

with get_session() as _session:
    ALL_COUNTRIES = list_all_countries(_session)

with st.container(border=True):
    col1, col2 = st.columns(2)
    country = col1.selectbox("Country", options=ALL_COUNTRIES, index=None, placeholder="Select a country")

    with get_session() as _session:
        cities_for_country = list_cities_for_country(_session, country) if country else []
    city = col2.selectbox(
        "City",
        options=cities_for_country,
        index=None,
        placeholder="Select a country first" if not country else "Select a city",
        disabled=not country,
    )

    with st.form("generate_leads_form"):
        keyword = st.text_input("Business Keyword", placeholder="e.g. Schools")
        required_leads = st.number_input(
            "Number of Leads Required", min_value=1, max_value=5000, value=50, step=10
        )
        submitted = st.form_submit_button("🚀 Generate Leads", type="primary", width="stretch")

if submitted:
    errors = validate_lead_generation_inputs(keyword, country, city, int(required_leads))
    if errors:
        for error in errors:
            st.error(error)
    else:
        st.write("")
        progress_header = st.empty()
        progress_placeholder = st.empty()
        metrics_placeholder = st.empty()

        step_state = {step: {"done": False, "count": None} for step in STEP_ORDER}

        def render_steps(label: str = "Running...") -> None:
            progress_header.markdown(f"**Lead Generation Progress** &nbsp; `{label}`")
            with progress_placeholder.container(border=True):
                rows_html = "".join(
                    step_row(STEP_LABELS[s], step_state[s]["done"], step_state[s]["count"]) for s in STEP_ORDER
                )
                st.markdown(rows_html, unsafe_allow_html=True)

        def render_metrics(progress: dict) -> None:
            with metrics_placeholder.container():
                c1, c2, c3 = st.columns(3)
                with c1:
                    stat_card("🔎", "Results Checked", progress.get("total_results_checked", 0), color="blue")
                with c2:
                    stat_card("🚫", "Duplicates Skipped", progress.get("duplicate_leads_skipped", 0), color="slate")
                with c3:
                    stat_card("✅", "New Leads Found", progress.get("new_leads_found", 0), color="green")
                c4, c5, c6 = st.columns(3)
                with c4:
                    stat_card("✉️", "Emails Found", progress.get("emails_found", 0), color="indigo")
                with c5:
                    stat_card("📞", "Phones Found", progress.get("phones_found", 0), color="amber")
                with c6:
                    stat_card("🌐", "Websites Crawled", progress.get("websites_crawled", 0), color="rose")

        def on_progress(event: str, payload: dict) -> None:
            if event == "status":
                message = payload["message"]
                if message.startswith("Searching Google Places"):
                    step_state["search"]["done"] = True
                elif message.startswith("Checked"):
                    step_state["search"]["done"] = True
                    step_state["dedupe"]["done"] = True
                    step_state["dedupe"]["count"] = message.replace("Checked ", "")
                elif message.startswith("Crawling"):
                    step_state["dedupe"]["done"] = True
                    step_state["crawl"]["done"] = True
                    step_state["crawl"]["count"] = message
                elif message.startswith("Analyzing"):
                    step_state["crawl"]["done"] = True
                    step_state["analyze"]["done"] = True
                    step_state["recommend"]["done"] = True
                elif message.startswith("Completed"):
                    for step in STEP_ORDER:
                        step_state[step]["done"] = True
                    render_steps("Completed")
                    return
                elif message.startswith("Failed"):
                    render_steps("Failed")
                    return
                render_steps()
            elif event == "batch_progress":
                step_state["crawl"]["done"] = True
                step_state["email"]["done"] = True
                step_state["email"]["count"] = f"{payload.get('emails_found', 0)} found"
                step_state["phone"]["done"] = True
                step_state["phone"]["count"] = f"{payload.get('phones_found', 0)} found"
                step_state["analyze"]["done"] = True
                step_state["recommend"]["done"] = True
                step_state["save"]["done"] = True
                step_state["save"]["count"] = f"{payload.get('new_leads_found', 0)} saved"
                render_steps()
                render_metrics(payload)

        render_steps()

        try:
            result = run_lead_generation(
                keyword.strip(),
                country.strip(),
                city.strip(),
                int(required_leads),
                progress_callback=on_progress,
            )
        except Exception as exc:  # noqa: BLE001 - surface any unexpected failure in the UI
            render_steps("Failed")
            st.error(f"Lead generation failed unexpectedly: {exc}")
        else:
            render_metrics(result.progress.__dict__)

            if result.error_message:
                st.error(f"Search failed: {result.error_message}")
            elif result.progress.new_leads_found >= result.progress.requested_leads:
                st.success(f"Found all {result.progress.new_leads_found} requested new leads.")
            else:
                st.warning(
                    f"Requested: {result.progress.requested_leads} — "
                    f"Available New Leads Found: {result.progress.new_leads_found}. "
                    "No more matching results were available from Google Places."
                )

            st.subheader("Search Summary")
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                stat_card("🎯", "Requested Leads", result.progress.requested_leads, color="indigo")
            with s2:
                stat_card("🔎", "Results Checked", result.progress.total_results_checked, color="blue")
            with s3:
                stat_card("🚫", "Duplicates Skipped", result.progress.duplicate_leads_skipped, color="slate")
            with s4:
                stat_card("✅", "New Leads Generated", result.progress.new_leads_found, color="green")
            st.caption(f"Search history record #{result.search_history_id} — status: {result.status}")
