"""Shared Streamlit theming and small presentational helpers.

Kept separate from business logic (see services/) - this module only ever
touches how things look, never what the data means. Uses Streamlit's native
bordered containers/columns/metrics wherever possible; raw HTML/CSS is used
only for purely-informational elements (stat cards, colored pills) that have
no interactive widgets, so it can't break Streamlit's own event handling.
"""
from __future__ import annotations

import html

import streamlit as st

_PALETTE: dict[str, tuple[str, str]] = {
    "indigo": ("#EEF2FF", "#4F46E5"),
    "green": ("#ECFDF5", "#059669"),
    "blue": ("#EFF6FF", "#2563EB"),
    "amber": ("#FFFBEB", "#D97706"),
    "rose": ("#FFF1F2", "#E11D48"),
    "slate": ("#F1F5F9", "#475569"),
}

PRIORITY_COLORS = {"HIGH": "rose", "MEDIUM": "amber", "LOW": "slate"}
STATUS_COLORS = {
    "NEW": "blue",
    "ENRICHED": "indigo",
    "QUALIFIED": "green",
    "CONTACTED": "amber",
    "REPLIED": "green",
    "INTERESTED": "green",
    "NOT_INTERESTED": "slate",
    "INVALID": "rose",
}

CHART_COLOR_SEQUENCE = ["#4F46E5", "#059669", "#2563EB", "#D97706", "#E11D48", "#0891B2"]

SERVICE_COLORS = {
    "AI Calling Agent": "indigo",
    "Website Chatbot": "blue",
    "Website Development": "amber",
    "Website Redesign": "rose",
}

OPPORTUNITY_LEVEL_COLORS = {
    "RECOMMENDED": "green",
    "POTENTIAL": "amber",
    "NOT_RECOMMENDED": "slate",
}


def inject_theme() -> None:
    """Inject the app-wide look: dark sidebar with an active-page highlight,
    rounded cards, and pill badges. Safe to call once per page render."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            background-color: #0F172A;
        }
        [data-testid="stSidebar"] * {
            color: #E2E8F0 !important;
        }
        [data-testid="stSidebarNav"] a {
            border-radius: 8px;
            margin: 2px 8px;
        }
        [data-testid="stSidebarNav"] a:hover {
            background-color: rgba(79, 70, 229, 0.25);
        }
        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background-color: #4F46E5;
        }
        [data-testid="stSidebarNav"] a[aria-current="page"] span {
            color: #FFFFFF !important;
        }

        .stat-card {
            border-radius: 14px;
            padding: 1.1rem 1.25rem;
            height: 100%;
        }
        .stat-icon { font-size: 1.4rem; margin-bottom: 0.4rem; }
        .stat-value { font-size: 1.9rem; font-weight: 700; line-height: 1.1; }
        .stat-label { font-size: 0.85rem; color: #475569; margin-top: 0.2rem; }
        .stat-delta { font-size: 0.78rem; color: #64748B; margin-top: 0.3rem; }

        .pill {
            display: inline-block;
            padding: 0.15rem 0.65rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            white-space: nowrap;
        }

        .lead-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
        .lead-table th {
            text-align: left;
            padding: 0.5rem 0.6rem;
            color: #475569;
            font-weight: 600;
            border-bottom: 1px solid #E2E8F0;
        }
        .lead-table td {
            padding: 0.55rem 0.6rem;
            border-bottom: 1px solid #F1F5F9;
            vertical-align: middle;
        }
        .lead-table tr:hover td { background-color: #F8FAFC; }
        .lead-table a { color: #4F46E5; text-decoration: none; }
        .lead-table a:hover { text-decoration: underline; }

        .step-row { display: flex; align-items: center; padding: 0.35rem 0; }
        .step-check {
            width: 1.4rem; height: 1.4rem; border-radius: 999px;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 0.8rem; margin-right: 0.6rem; flex-shrink: 0;
        }
        .step-done { background-color: #ECFDF5; color: #059669; }
        .step-pending { background-color: #F1F5F9; color: #94A3B8; }
        .step-label { flex-grow: 1; color: #0F172A; }
        .step-count { color: #64748B; font-size: 0.85rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def stat_card(icon: str, label: str, value: object, delta: str | None = None, color: str = "indigo") -> None:
    """Render a single colored stat card (icon + big number + label)."""
    bg, fg = _PALETTE.get(color, _PALETTE["indigo"])
    delta_html = f'<div class="stat-delta">{html.escape(delta)}</div>' if delta else ""
    st.markdown(
        f"""
        <div class="stat-card" style="background:{bg};">
            <div class="stat-icon">{icon}</div>
            <div class="stat-value" style="color:{fg};">{html.escape(str(value))}</div>
            <div class="stat-label">{html.escape(label)}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _pill(text: str, color_key: str) -> str:
    bg, fg = _PALETTE.get(color_key, _PALETTE["slate"])
    return f'<span class="pill" style="background:{bg};color:{fg};">{html.escape(text)}</span>'


def priority_pill(priority: str | None) -> str:
    if not priority:
        return ""
    return _pill(priority, PRIORITY_COLORS.get(priority, "slate"))


def status_pill(status: str | None) -> str:
    if not status:
        return ""
    return _pill(status, STATUS_COLORS.get(status, "slate"))


def service_pill(service: str) -> str:
    return _pill(service, SERVICE_COLORS.get(service, "slate"))


def opportunity_level_pill(level: str, label: str | None = None) -> str:
    return _pill(label or level.replace("_", " ").title(), OPPORTUNITY_LEVEL_COLORS.get(level, "slate"))


def step_row(label: str, done: bool, count_text: str | None = None) -> str:
    """One row of the Generate Leads progress checklist (informational only)."""
    check_class = "step-done" if done else "step-pending"
    mark = "&#10003;" if done else "&#9675;"
    count_html = f'<span class="step-count">{html.escape(count_text)}</span>' if count_text else ""
    return (
        f'<div class="step-row">'
        f'<span class="step-check {check_class}">{mark}</span>'
        f'<span class="step-label">{html.escape(label)}</span>'
        f"{count_html}"
        f"</div>"
    )
