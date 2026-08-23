"""Dashboard: summary metrics and charts across all saved leads."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from database import crud
from database.connection import get_session, init_db
from utils.ui import CHART_COLOR_SEQUENCE, inject_theme, stat_card

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
init_db()
inject_theme()

st.title("📊 Dashboard")

with get_session() as session:
    metrics = crud.dashboard_metrics(session)
    city_rows = crud.leads_by_city(session)
    priority_rows = crud.leads_by_priority(session)
    status_rows = crud.leads_by_status(session)
    time_rows = crud.leads_over_time(session)
    service_opportunity_counts = crud.service_opportunity_counts(session)

cols = st.columns(5)
with cols[0]:
    stat_card("👥", "Total Leads", f"{metrics['total_leads']:,}", color="indigo")
with cols[1]:
    stat_card("🏠", "New Today", f"{metrics['new_leads_today']:,}", color="green")
with cols[2]:
    pct_email = (metrics["leads_with_email"] / metrics["total_leads"] * 100) if metrics["total_leads"] else 0
    stat_card("✉️", "Leads With Email", f"{metrics['leads_with_email']:,}", f"{pct_email:.0f}% of total", color="blue")
with cols[3]:
    pct_phone = (metrics["leads_with_phone"] / metrics["total_leads"] * 100) if metrics["total_leads"] else 0
    stat_card("📞", "Leads With Phone", f"{metrics['leads_with_phone']:,}", f"{pct_phone:.0f}% of total", color="green")
with cols[4]:
    pct_high = (metrics["high_priority_leads"] / metrics["total_leads"] * 100) if metrics["total_leads"] else 0
    stat_card("⭐", "High Priority Leads", f"{metrics['high_priority_leads']:,}", f"{pct_high:.0f}% of total", color="amber")

st.write("")
stat_card("🌐", "Leads With Website", f"{metrics['leads_with_website']:,}", color="slate")

st.divider()
st.subheader("🎯 Service Opportunities")
st.caption("How many leads in the database are a strong match for each service we sell.")

svc_cols = st.columns(4)
svc_colors = {
    "AI Calling Agent": ("📞", "indigo"),
    "Website Chatbot": ("💬", "blue"),
    "Website Development": ("🏗️", "amber"),
    "Website Redesign": ("🎨", "rose"),
}
for col, (service, (icon, color)) in zip(svc_cols, svc_colors.items()):
    with col:
        stat_card(icon, f"{service} Opportunities", f"{service_opportunity_counts.get(service, 0):,}", color=color)

with st.container(border=True):
    st.markdown("**Service Opportunities by Service Type**")
    df_services = pd.DataFrame(
        {"Service": list(service_opportunity_counts.keys()), "Leads": list(service_opportunity_counts.values())}
    )
    if df_services["Leads"].sum() > 0:
        fig = px.bar(df_services, x="Service", y="Leads", color_discrete_sequence=CHART_COLOR_SEQUENCE)
        fig.update_layout(margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No analyzed leads yet.")

st.divider()

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    with st.container(border=True):
        st.subheader("Leads by City")
        if city_rows:
            df_city = pd.DataFrame(city_rows, columns=["City", "Leads"])
            fig = px.bar(df_city, x="City", y="Leads", color_discrete_sequence=CHART_COLOR_SEQUENCE)
            fig.update_layout(margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No leads yet.")

with chart_col2:
    with st.container(border=True):
        st.subheader("Leads by Priority")
        if priority_rows:
            df_priority = pd.DataFrame(priority_rows, columns=["Priority", "Leads"])
            fig = px.pie(df_priority, names="Priority", values="Leads", color_discrete_sequence=CHART_COLOR_SEQUENCE, hole=0.45)
            fig.update_layout(margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No leads yet.")

chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    with st.container(border=True):
        st.subheader("Leads by Status")
        if status_rows:
            df_status = pd.DataFrame(status_rows, columns=["Status", "Leads"])
            fig = px.bar(df_status, x="Status", y="Leads", color_discrete_sequence=CHART_COLOR_SEQUENCE)
            fig.update_layout(margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No leads yet.")

with chart_col4:
    with st.container(border=True):
        st.subheader("Leads Generated Over Time")
        if time_rows:
            df_time = pd.DataFrame(time_rows, columns=["Date", "Leads"])
            fig = px.line(df_time, x="Date", y="Leads", markers=True, color_discrete_sequence=CHART_COLOR_SEQUENCE)
            fig.update_layout(margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No leads yet.")
