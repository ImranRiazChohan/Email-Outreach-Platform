"""Leads: browse, filter, search, and manage every saved lead."""
from __future__ import annotations

import html

import streamlit as st

from database import crud
from database.connection import get_session, init_db
from database.models import LeadPriority, LeadStatus, ServiceType
from services.service_recommender import opportunity_level
from utils.ui import inject_theme, opportunity_level_pill, priority_pill, service_pill, status_pill

st.set_page_config(page_title="Leads", page_icon="📋", layout="wide")
init_db()
inject_theme()

st.title("📋 Leads")

PAGE_SIZE = 25

if "leads_page" not in st.session_state:
    st.session_state.leads_page = 0
if "selected_lead_id" not in st.session_state:
    st.session_state.selected_lead_id = None

with get_session() as session:
    countries = crud.distinct_countries(session)
    cities = crud.distinct_cities(session)

with st.container(border=True):
    st.markdown("**🔎 Filters**")
    f1, f2, f3, f4 = st.columns(4)
    country = f1.selectbox("Country", ["All"] + countries)
    city = f2.selectbox("City", ["All"] + cities)
    priority = f3.selectbox("Priority", ["All"] + LeadPriority.ALL)
    lead_status = f4.selectbox("Lead Status", ["All"] + LeadStatus.ALL)

    f5, f6, f7, f8 = st.columns(4)
    has_email = f5.selectbox("Has Email", ["All", "Yes", "No"])
    has_phone = f6.selectbox("Has Phone", ["All", "Yes", "No"])
    has_website = f7.selectbox("Has Website", ["All", "Yes", "No"])
    min_rating = f8.slider("Minimum Rating", 0.0, 5.0, 0.0, 0.5)

    search_text = st.text_input("Search by Business Name, Email, Phone, or Website")


def _tri(value: str) -> bool | None:
    return {"Yes": True, "No": False}.get(value)


with get_session() as session:
    leads, total = crud.list_leads(
        session,
        country=None if country == "All" else country,
        city=None if city == "All" else city,
        priority=None if priority == "All" else priority,
        lead_status=None if lead_status == "All" else lead_status,
        has_email=_tri(has_email),
        has_phone=_tri(has_phone),
        has_website=_tri(has_website),
        min_rating=min_rating or None,
        search_text=search_text or None,
        limit=PAGE_SIZE,
        offset=st.session_state.leads_page * PAGE_SIZE,
    )
    lead_dicts = [lead.to_dict() for lead in leads]

st.write("")
st.caption(f"Showing {len(lead_dicts)} of {total:,} leads matching your filters.")

if lead_dicts:

    def _link(url: str | None, text: str | None = None) -> str:
        if not url:
            return "-"
        safe_url = html.escape(url, quote=True)
        label = html.escape(text or url)
        href = safe_url if safe_url.startswith(("http://", "https://", "mailto:")) else f"https://{safe_url}"
        return f'<a href="{href}" target="_blank">{label}</a>'

    rows_html = []
    for lead in lead_dicts:
        email_href = f"mailto:{lead['email']}" if lead["email"] else None
        rating_text = f"⭐ {lead['rating']:.1f}" if lead["rating"] else "-"
        services_html = " ".join(service_pill(s) for s in lead["recommended_services"]) or "-"
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(lead['business_name'])}</td>"
            f"<td>{html.escape(lead['city'] or '-')}</td>"
            f"<td>{_link(email_href, lead['email'])}</td>"
            f"<td>{_link(lead['website'])}</td>"
            f"<td>{rating_text}</td>"
            f"<td>{lead['lead_score']}</td>"
            f"<td>{priority_pill(lead['priority'])}</td>"
            f"<td>{status_pill(lead['lead_status'])}</td>"
            f"<td>{services_html}</td>"
            "</tr>"
        )

    table_html = f"""
    <table class="lead-table">
        <thead>
            <tr>
                <th>Business Name</th><th>City</th><th>Email</th>
                <th>Website</th><th>Rating</th><th>Score</th><th>Priority</th><th>Status</th>
                <th>Recommended Services</th>
            </tr>
        </thead>
        <tbody>{''.join(rows_html)}</tbody>
    </table>
    """
    with st.container(border=True):
        st.markdown(table_html, unsafe_allow_html=True)
else:
    st.info("No leads match the current filters.")

nav1, nav2, nav3 = st.columns([1, 2, 1])
if nav1.button("⬅ Previous", disabled=st.session_state.leads_page == 0):
    st.session_state.leads_page -= 1
    st.rerun()
total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
nav2.markdown(f"<div style='text-align:center'>Page {st.session_state.leads_page + 1} of {total_pages}</div>", unsafe_allow_html=True)
if nav3.button("Next ➡", disabled=(st.session_state.leads_page + 1) * PAGE_SIZE >= total):
    st.session_state.leads_page += 1
    st.rerun()

st.divider()
st.subheader("Lead Details")

lead_ids = [lead["id"] for lead in lead_dicts]
if lead_ids:
    selected_id = st.selectbox("Select a lead to view full details", lead_ids, format_func=lambda lid: next(
        (l["business_name"] for l in lead_dicts if l["id"] == lid), str(lid)
    ))

    lead_was_updated = False

    with get_session() as session:
        lead = crud.get_lead(session, selected_id)
        crawl_results = crud.get_crawl_results_for_lead(session, selected_id) if lead else []

        if lead:
            with st.container(border=True):
                header_col, badge_col = st.columns([4, 1])
                header_col.markdown(f"### {html.escape(lead.business_name)}")
                with badge_col:
                    st.markdown(priority_pill(lead.priority) + " " + status_pill(lead.lead_status), unsafe_allow_html=True)

                if lead.recommended_services:
                    st.markdown(
                        "**Recommended For:** " + " ".join(service_pill(s) for s in lead.recommended_services),
                        unsafe_allow_html=True,
                    )

                info_col, contact_col, lead_col = st.columns(3)
                with info_col:
                    st.markdown("**Business Information**")
                    st.write(f"Address: {lead.full_address or '-'}")
                    st.write(f"City: {lead.city or '-'}")
                    st.write(f"Country: {lead.country or '-'}")
                    st.write(f"Google Rating: {lead.rating or '-'} ({lead.user_ratings_total or 0} reviews)")

                with contact_col:
                    st.markdown("**Contact Information**")
                    st.write(f"Google Phone: {lead.google_phone or '-'}")
                    st.write(f"Website Phone: {lead.website_phone or '-'}")
                    st.write(f"Final Phone: {lead.final_phone or '-'}")
                    st.write(f"Email: {lead.email or '-'}")
                    st.write(f"Website: {lead.website or '-'}")

                with lead_col:
                    st.markdown("**Lead Information**")
                    st.write(f"Lead Score: {lead.lead_score}")

                    new_priority = st.selectbox(
                        "Priority", LeadPriority.ALL, index=LeadPriority.ALL.index(lead.priority)
                    )
                    new_status = st.selectbox(
                        "Lead Status", LeadStatus.ALL, index=LeadStatus.ALL.index(lead.lead_status)
                    )
                    if st.button("💾 Save Changes", width="stretch"):
                        crud.update_lead(session, lead, priority=new_priority, lead_status=new_status)
                        lead_was_updated = True

                st.markdown("**Crawling Information**")
                if crawl_results:
                    latest = crawl_results[0]
                    cr1, cr2, cr3, cr4 = st.columns(4)
                    cr1.write(f"Crawl Status: {latest.crawl_status}")
                    cr2.write(f"Pages Crawled: {latest.pages_crawled}")
                    cr3.write(f"Last Crawl: {latest.crawled_at}")
                    cr4.write(f"Error: {latest.error_message or '-'}")
                    st.write(f"All Emails Found: {', '.join(latest.emails_found) or '-'}")
                    st.write(f"All Phones Found: {', '.join(latest.phones_found) or '-'}")
                else:
                    st.write("No crawl performed for this lead.")

                st.markdown("**🎯 Service Opportunity Analysis**")
                if lead.website_analysis_status in ("PENDING", "ANALYZING"):
                    st.write("Website analysis has not completed for this lead yet.")
                else:
                    quality_text = (
                        f"{lead.website_quality_score}/100" if lead.website_quality_score is not None else "N/A"
                    )
                    st.write(f"Website Quality Score: {quality_text}")

                    scores = lead.service_opportunity_scores
                    reasons = lead.service_recommendation_reason
                    svc_cols = st.columns(4)
                    for col, service in zip(svc_cols, ServiceType.ALL):
                        score = scores.get(service, 0)
                        level = opportunity_level(score)
                        status_label = "Not Required" if service == ServiceType.WEBSITE_DEVELOPMENT and score == 0 else None
                        with col:
                            st.markdown(f"**{service}**")
                            st.write(f"Opportunity Score: {score}/100")
                            st.markdown(opportunity_level_pill(level, status_label), unsafe_allow_html=True)
                            st.caption(reasons.get(service, "-"))

    if lead_was_updated:
        st.success("Lead updated.")
        st.rerun()
else:
    st.info("No leads to show details for.")
