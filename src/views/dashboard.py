"""
Operations Dashboard View — Premium Redesign.
Clean executive cockpit for B2B travel refund operations.
Uses Plus Jakarta Sans + JetBrains Mono, tinted-shadow token system,
asymmetric KPI layout with integrated health gauge, horizontal pipeline
stepper, carrier data table, and executive RCA summary.
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st
import altair as alt
from src.api_client import api_client


# ---------------------------------------------------------------------------
# Metrics Computation via REST API Client
# ---------------------------------------------------------------------------
def calculate_dashboard_metrics(
    support_df: Optional[pd.DataFrame] = None,
    finance_df: Optional[pd.DataFrame] = None,
    escalations_df: Optional[pd.DataFrame] = None,
    window_filter: str = "All (Feb–Jun 2026)"
) -> Dict[str, Any]:
    """Fetches operational metrics from backend REST API with fallback."""
    return api_client.get_dashboard_metrics(window=window_filter)


# ---------------------------------------------------------------------------
# CSS Token System
# ---------------------------------------------------------------------------
def inject_dashboard_styles() -> None:
    """Injects the dashboard-specific structural CSS over the global theme."""
    st.markdown("""
    <style>
    /* ── Section Label ── */
    .dash-section-label {
        font-family: var(--font-mono);
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--clr-text-secondary);
        margin-bottom: 6px;
        padding-left: 2px;
    }

    /* ── KPI Hero Card (Health Gauge) ── */
    .kpi-hero {
        background: var(--clr-surface);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--clr-border);
        border-radius: var(--radius-md);
        padding: 24px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        transition: all 0.3s ease;
    }
    .kpi-hero:hover {
        border-color: var(--clr-border-highlight);
        background: var(--clr-surface-hover);
        box-shadow: 0 0 20px var(--clr-accent-subtle);
    }

    /* ── KPI Stat Card ── */
    .kpi-stat {
        background: var(--clr-surface);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--clr-border);
        border-radius: var(--radius-md);
        padding: 16px 20px;
        transition: all 0.3s ease;
    }
    .kpi-stat:hover {
        transform: translateY(-2px);
        background: var(--clr-surface-hover);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }
    .kpi-stat-label {
        font-family: var(--font-mono);
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--clr-text-secondary);
        margin-bottom: 6px;
    }
    .kpi-stat-value {
        font-family: var(--font-sans);
        font-size: 28px;
        font-weight: 600;
        line-height: 1.1;
        margin-bottom: 4px;
        color: var(--clr-text-primary);
    }
    .kpi-stat-delta {
        font-family: var(--font-mono);
        font-size: 12px;
        font-weight: 500;
        opacity: 0.8;
    }

    /* ── Pipeline Corridor ── */
    .pipeline-corridor-card {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--clr-surface);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--clr-border);
        border-radius: var(--radius-md);
        padding: 24px 32px;
        gap: 16px;
        transition: all 0.3s ease;
    }
    .pipeline-corridor-card:hover {
        border-color: var(--clr-accent-subtle);
        box-shadow: 0 0 20px var(--clr-accent-subtle);
    }
    .pipeline-node {
        flex: 1;
        display: flex;
        flex-direction: column;
    }
    .pipeline-connector {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        color: var(--clr-accent);
        padding: 0 16px;
        position: relative;
    }
    .pipeline-connector::before {
        content: '';
        position: absolute;
        width: 100%;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--clr-accent-subtle), transparent);
        z-index: 0;
    }
    .pipeline-connector svg {
        z-index: 1;
        background: var(--clr-bg);
        border-radius: 50%;
        padding: 2px;
        box-shadow: 0 0 10px var(--clr-accent-subtle);
        animation: pulse-arrow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }
    @keyframes pulse-arrow {
        0%, 100% { transform: translateX(-2px); opacity: 0.6; box-shadow: 0 0 5px var(--clr-accent-subtle); }
        50% { transform: translateX(4px); opacity: 1; box-shadow: 0 0 15px var(--clr-accent); }
    }
    .pipeline-node-label {
        font-family: var(--font-mono);
        font-size: 10px;
        font-weight: 500;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--clr-text-secondary);
        margin-bottom: 8px;
    }
    .pipeline-node-title {
        font-family: var(--font-sans);
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 12px;
    }
    .pipeline-node-metric {
        font-family: var(--font-sans);
        font-size: 28px;
        font-weight: 600;
        line-height: 1.2;
    }
    .pipeline-node-sub {
        font-family: var(--font-mono);
        font-size: 12px;
        color: var(--clr-text-secondary);
        margin-top: 4px;
    }
    .pipeline-node-note {
        font-family: var(--font-sans);
        font-size: 12px;
        color: var(--clr-text-secondary);
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px dashed var(--clr-border);
    }

    /* ── Carrier ── */
    .carrier-badge {
        font-family: var(--font-mono);
        font-size: 10px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: var(--radius-sm);
        letter-spacing: 0.04em;
    }
    .carrier-bar-bg {
        width: 100%;
        height: 6px;
        background: rgba(255,255,255,0.1);
        border-radius: 3px;
        overflow: hidden;
    }
    .carrier-bar-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.6s cubic-bezier(0.32, 0.72, 0, 1);
        box-shadow: 0 0 8px currentColor;
    }
    .carrier-pct {
        font-family: var(--font-mono);
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 4px;
    }

    /* ── Analytics Section ── */
    .analytics-card-title {
        font-family: var(--font-sans);
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 4px;
    }
    .analytics-card-sub {
        font-family: var(--font-mono);
        font-size: 11px;
        color: var(--clr-text-secondary);
        margin-bottom: 14px;
    }

    /* ── RCA Executive Grid ── */
    .rca-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
    }
    .rca-insight-card {
        background: var(--clr-surface);
        backdrop-filter: blur(16px);
        border: 1px solid var(--clr-border);
        border-radius: var(--radius-md);
        padding: 24px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        transition: transform 0.2s, border-color 0.2s;
    }
    .rca-insight-card:hover {
        transform: translateY(-4px);
        border-color: var(--clr-border-highlight);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    }
    
    /* ── Leaderboard ── */
    .leaderboard-row {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        border-bottom: 1px solid var(--clr-border);
        gap: 12px;
        transition: background 0.2s;
    }
    .leaderboard-row:hover {
        background: var(--clr-surface-hover);
    }
    .leaderboard-row:last-child {
        border-bottom: none;
    }
    .leaderboard-rank {
        font-family: var(--font-mono);
        font-size: 14px;
        color: var(--clr-text-secondary);
        width: 24px;
    }
    .leaderboard-name {
        font-family: var(--font-sans);
        font-size: 15px;
        font-weight: 500;
        flex: 1;
    }
    .leaderboard-badge {
        font-family: var(--font-mono);
        font-size: 12px;
        background: rgba(255, 42, 84, 0.15);
        color: var(--clr-danger);
        padding: 4px 12px;
        border-radius: 99px;
        font-weight: 600;
        text-align: center;
        min-width: 80px;
    }
    .rca-icon {
        width: 36px;
        height: 36px;
        border-radius: var(--radius-sm);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        flex-shrink: 0;
    }
    .rca-item-label {
        font-family: var(--font-mono);
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 3px;
    }
    .rca-item-title {
        font-family: var(--font-sans);
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 4px;
    }
    .rca-item-desc {
        font-family: var(--font-sans);
        font-size: 13px;
        color: var(--clr-text-secondary);
        line-height: 1.5;
    }

    /* ── Section Divider ── */
    .section-gap {
        height: 32px;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
def render_dashboard_header() -> str:
    """Renders the simplified page header with status pill and time-window filter."""
    header_col, status_col = st.columns([3, 1])
    with header_col:
        st.markdown(
            '<div class="dash-section-label">SSOT Pipeline</div>',
            unsafe_allow_html=True
        )
        st.title("Operations Dashboard")
    with status_col:
        st.markdown(
            '<div style="text-align: right; padding-top: 18px;">'
            '<span class="status-pill">'
            '● Live Stream '
            '<span class="status-dot"></span>'
            'SSOT Active'
            '</span>'
            '</div>',
            unsafe_allow_html=True
        )

    window_options = [
        "All (Feb–Jun 2026)",
        "Last 30 Days (June Snapshot)",
        "Q1 2026 (Feb–Mar)",
        "Q2 2026 (Apr–Jun)"
    ]
    selected_window = st.segmented_control(
        "Filter Period",
        options=window_options,
        default=window_options[0],
        label_visibility="collapsed"
    ) or window_options[0]

    return selected_window


# ---------------------------------------------------------------------------
# KPI Cards — Asymmetric with Integrated Health Gauge
# ---------------------------------------------------------------------------
def render_kpi_cards(metrics: Dict[str, Any]) -> None:
    """Renders high-end asymmetric Bento Grid layout for KPIs."""
    st.markdown("""
    <style>
    .doppel-shell {
        background: rgba(255,255,255,0.02);
        padding: 6px;
        border-radius: 24px;
        border: 1px solid rgba(255,255,255,0.05);
        height: 100%;
    }
    .doppel-core {
        background: #050505;
        border-radius: 18px;
        padding: 24px;
        box-shadow: inset 0 1px 1px rgba(255,255,255,0.08);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .eyebrow {
        border-radius: 9999px;
        padding: 4px 10px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        font-weight: 600;
        width: fit-content;
        margin-bottom: 16px;
    }
    .eyebrow-green { background: rgba(0,230,118,0.1); color: #00E676; }
    .eyebrow-red { background: rgba(255,42,84,0.1); color: #FF2A54; }
    .eyebrow-yellow { background: rgba(255,214,0,0.1); color: #FFD600; }
    .eyebrow-blue { background: rgba(0,240,255,0.1); color: #00F0FF; }
    
    .val-text {
        font-size: 2.5rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        color: white;
        line-height: 1.1;
    }
    .sub-text {
        font-size: 13px;
        color: #94A3B8;
        margin-top: 8px;
    }
    .health-val { font-size: 4rem; letter-spacing: -0.04em; }
    
    @media (max-width: 768px) {
        .bento-grid { grid-template-columns: 1fr !important; }
        .bento-large { grid-column: span 1 !important; grid-row: span 1 !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    html = f"""<div class="bento-grid" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px;">
<div style="grid-column: span 2; grid-row: span 2;" class="doppel-shell bento-large">
<div class="doppel-core" style="background: linear-gradient(145deg, #050505 0%, #0a0f12 100%);">
<div class="eyebrow eyebrow-green">Pipeline Health</div>
<div class="val-text health-val">{metrics['health_pct']}%</div>
<div class="sub-text">
<span style="color: #00E676;">● {metrics['healthy_count']}</span> / {metrics['total_pipeline']} clean handoffs
</div>
<div style="margin-top:24px; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow:hidden;">
<div style="width: {metrics['health_pct']}%; height: 100%; background: #00E676; border-radius: 2px;"></div>
</div>
</div>
</div>
<div style="grid-column: span 1;" class="doppel-shell">
<div class="doppel-core">
<div class="eyebrow eyebrow-red">Escalations</div>
<div class="val-text">{metrics['total_escalations']}</div>
<div class="sub-text">6.5× monthly surge</div>
</div>
</div>
<div style="grid-column: span 1;" class="doppel-shell">
<div class="doppel-core">
<div class="eyebrow eyebrow-yellow">Avg TTR</div>
<div class="val-text">{metrics['avg_ttr']}d</div>
<div class="sub-text">Target: ≤ 2 days</div>
</div>
</div>
<div style="grid-column: span 1;" class="doppel-shell">
<div class="doppel-core">
<div class="eyebrow eyebrow-yellow">Exposure</div>
<div class="val-text">{metrics['deduction_mismatches']}</div>
<div class="sub-text">₹14.8L contested</div>
</div>
</div>
<div style="grid-column: span 1;" class="doppel-shell">
<div class="doppel-core">
<div class="eyebrow eyebrow-blue">Hours Saved</div>
<div class="val-text">142h</div>
<div class="sub-text">78% Automation Rate</div>
</div>
</div>
</div>"""
    st.markdown(html, unsafe_allow_html=True)

    # Action buttons below KPIs
    _, btn1, btn2, _ = st.columns([2.5, 1, 1, 1.5])
    with btn1:
        if st.button("Reconcile", type="primary", use_container_width=True, key="btn_dash_recon"):
            st.switch_page(st.session_state.pages["reconciliation"])
    with btn2:
        if st.button("Triage", use_container_width=True, key="btn_dash_triage"):
            st.switch_page(st.session_state.pages["triage"])


# ---------------------------------------------------------------------------
# Pipeline Corridor — Unified Google Material Stepper
# ---------------------------------------------------------------------------
def render_pipeline_corridor(metrics: Dict[str, Any]) -> None:
    """Renders the 3-hop pipeline using a single unified Flexbox card."""
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-section-label">Settlement corridor</div>', unsafe_allow_html=True)

    audited = metrics['total_pipeline'] - metrics['dropped_handoffs']
    hop3_color = 'var(--clr-success)' if metrics['health_pct'] >= 80 else 'var(--clr-warning)' if metrics['health_pct'] >= 60 else 'var(--clr-danger)'
    
    chevron = '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>'''

    st.markdown(f"""<div class="doppel-shell">
<div class="doppel-core" style="flex-direction: row; gap: 16px; padding: 24px; align-items: center;">
    <!-- Node 1 -->
    <div style="flex: 1; text-align: left;">
        <div class="eyebrow eyebrow-blue" style="margin-bottom: 12px;">Inbound Intake</div>
        <div class="val-text" style="color: #00F0FF; font-size: 2rem; margin-bottom: 4px;">{metrics['total_pipeline']}</div>
        <div class="sub-text" style="margin-top: 0; margin-bottom: 12px;">Total claims</div>
        <div style="font-size: 11px; color: #94A3B8; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px;">WhatsApp · Email · Web</div>
    </div>
    <div style="color: rgba(255,255,255,0.2); flex-shrink: 0;">{chevron}</div>
    <!-- Node 2 -->
    <div style="flex: 1; text-align: left;">
        <div class="eyebrow eyebrow-yellow" style="margin-bottom: 12px;">Route Validation</div>
        <div class="val-text" style="color: #FFD600; font-size: 2rem; margin-bottom: 4px;">{audited}</div>
        <div class="sub-text" style="margin-top: 0; margin-bottom: 12px;">Audited tickets</div>
        <div style="font-size: 11px; color: #FF2A54; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px;">−{metrics['dropped_handoffs']} dropped before Finance sync</div>
    </div>
    <div style="color: rgba(255,255,255,0.2); flex-shrink: 0;">{chevron}</div>
    <!-- Node 3 -->
    <div style="flex: 1; text-align: left;">
        <div class="eyebrow eyebrow-green" style="margin-bottom: 12px;">Banking Payout</div>
        <div class="val-text" style="color: #00E676; font-size: 2rem; margin-bottom: 4px;">{metrics['healthy_count']}</div>
        <div class="sub-text" style="margin-top: 0; margin-bottom: 12px;">Clean settlements</div>
        <div style="font-size: 11px; color: #FFD600; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px;">{metrics['deduction_mismatches']} mismatches · ₹14.8L variance</div>
    </div>
</div>
</div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Carrier Health — Streamlit-native layout
# ---------------------------------------------------------------------------
def render_carrier_health() -> None:
    """Renders carrier health using Streamlit columns with small styled HTML."""
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-section-label">Carrier health</div>', unsafe_allow_html=True)

    carriers = [
        {"name": "IndiGo (6E)", "type": "Domestic", "type_color": "#34a853",
         "fee": "₹600", "sla": "24h", "pct": 92},
        {"name": "SpiceJet (SG)", "type": "Regional", "type_color": "#1a73e8",
         "fee": "₹800", "sla": "36h", "pct": 84},
        {"name": "Air India (AI)", "type": "Mixed", "type_color": "#fbbc04",
         "fee": "₹1,200", "sla": "48h", "pct": 78},
        {"name": "Emirates (EK)", "type": "International", "type_color": "#ea4335",
         "fee": "₹1,800", "sla": "72h", "pct": 69},
    ]

    with st.container(border=True):
        for c in carriers:
            bar_color = "var(--clr-success)" if c["pct"] >= 85 else "var(--clr-accent)" if c["pct"] >= 75 else "var(--clr-warning)" if c["pct"] >= 70 else "var(--clr-danger)"
            c_name, c_badge, c_fee, c_sla, c_bar = st.columns([2, 1.5, 1, 1, 2])
            with c_name:
                st.markdown(f'<div style="font-weight: 600; padding-top: 6px;">{c["name"]}</div>', unsafe_allow_html=True)
            with c_badge:
                st.markdown(
                    f'<span class="carrier-badge" style="color: {c["type_color"]}; '
                    f'background: {c["type_color"]}18;">{c["type"].upper()}</span>',
                    unsafe_allow_html=True
                )
            with c_fee:
                st.markdown(f'<div style="font-family: var(--font-mono); font-size: 13px; font-variant-numeric: tabular-nums; padding-top: 6px;">{c["fee"]}</div>', unsafe_allow_html=True)
            with c_sla:
                st.markdown(f'<div style="font-family: var(--font-mono); font-size: 13px; padding-top: 6px;">{c["sla"]}</div>', unsafe_allow_html=True)
            with c_bar:
                st.markdown(
                    f'<div class="carrier-pct" style="color: {bar_color};">{c["pct"]}%</div>'
                    f'<div class="carrier-bar-bg"><div class="carrier-bar-fill" '
                    f'style="width: {c["pct"]}%; background: {bar_color};"></div></div>',
                    unsafe_allow_html=True
                )


# ---------------------------------------------------------------------------
# Analytics — Tighter 3-Panel Layout
# ---------------------------------------------------------------------------
def render_analytics(escalations_df: Optional[pd.DataFrame] = None) -> None:
    """Renders escalation trend, root cause, and top agencies in a clean layout."""
    if escalations_df is None or escalations_df.empty:
        raw_escs = api_client.get_escalations()
        escalations_df = pd.DataFrame(raw_escs) if raw_escs else pd.DataFrame()

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    
    # ── Top Section: At-Risk Partners (Interactive) ──
    with st.container(border=True):
        ag_h1, ag_h2 = st.columns([4, 1])
        with ag_h1:
            st.markdown("""
            <div class="analytics-card-title">At-risk partners (Select row to filter)</div>
            <div class="analytics-card-sub">Top 5 B2B agencies · 51% of disputes</div>
            """, unsafe_allow_html=True)
        with ag_h2:
            st.page_link(st.session_state.pages["partners"], label="View", icon="↗️")
        
        top_mock = [
            {"Agency": "Peak Journeys", "Disputes": 19},
            {"Agency": "BlueJet Tours", "Disputes": 19},
            {"Agency": "TripHub", "Disputes": 16},
            {"Agency": "GoFly Holidays", "Disputes": 14},
            {"Agency": "Metro Yatra", "Disputes": 13}
        ]
        
        # Create pure HTML leaderboard
        html = '<div class="doppel-shell" style="margin-top: 8px;"><div class="doppel-core" style="padding: 12px; background: #050505; border-radius: calc(24px - 6px);">'
        html += '<div style="display: flex; flex-direction: column;">'
        for i, row in enumerate(top_mock):
            html += f'''<div class="leaderboard-row" style="border-bottom: 1px solid rgba(255,255,255,0.05); border-radius: 0;">
<div class="leaderboard-rank" style="color: #94A3B8; font-family: var(--font-mono); width: 30px;">#{i+1}</div>
<div class="leaderboard-name" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: white; flex: 1;">{row["Agency"]}</div>
<div class="eyebrow eyebrow-red" style="margin-bottom: 0;">{row["Disputes"]} Disputes</div>
</div>'''
        html += '</div></div></div>'
        st.markdown(html, unsafe_allow_html=True)
        
        st.markdown('<div class="section-gap" style="height: 16px;"></div>', unsafe_allow_html=True)
        selected_agency = st.pills("Filter Analysis by Agency", ["All"] + [r["Agency"] for r in top_mock], default="All")
        if selected_agency == "All":
            selected_agency = None

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    view_mode = st.pills("Analysis Dimension", ["Volume", "Financial Impact"], default="Volume")

    col_trend, col_cause = st.columns([2, 1], gap="medium")

    with col_trend:
        with st.container(border=True):
            title_text = f"Dispute trajectory ({view_mode.lower()})"
            if selected_agency:
                title_text += f" - {selected_agency}"
            
            st.markdown(f"""
            <div class="analytics-card-title">{title_text}</div>
            <div class="analytics-card-sub">Feb – Jun 2026 · 6.5× acceleration</div>
            """, unsafe_allow_html=True)
            if view_mode == "Volume":
                df_trend = pd.DataFrame({"Month": ["Feb", "Mar", "Apr", "May", "Jun"], "Metric": [12, 28, 41, 56, 78]})
                fmt, label = "Q", "Disputes"
            else:
                df_trend = pd.DataFrame({"Month": ["Feb", "Mar", "Apr", "May", "Jun"], "Metric": [2.4, 5.6, 8.2, 11.2, 14.8]})
                fmt, label = "Q", "Value (Lakhs)"
            
            if selected_agency:
                df_trend["Metric"] = df_trend["Metric"] * 0.25 # Mock filter
                
            base = alt.Chart(df_trend).encode(
                x=alt.X("Month", sort=None, axis=alt.Axis(labelAngle=0, grid=False, domain=False, tickColor='transparent', labelColor='#94A3B8')),
                y=alt.Y("Metric", title=label, axis=alt.Axis(gridColor='rgba(255,255,255,0.05)', domain=False, labelColor='#94A3B8')),
                tooltip=["Month", alt.Tooltip("Metric", title=label, format=".1f" if view_mode=="Financial Impact" else "d")]
            )
            
            # Create a gradient area chart
            area1 = base.mark_area(
                line={'color': '#00F0FF', 'strokeWidth': 3},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color='rgba(0, 240, 255, 0.5)', offset=0), 
                           alt.GradientStop(color='rgba(0, 240, 255, 0.01)', offset=1)],
                    x1=1, x2=1, y1=0, y2=1
                )
            )
            
            points1 = base.mark_circle(color='#00F0FF', size=60, opacity=1)
            
            text1 = base.mark_text(align='center', baseline='bottom', dy=-15, color='#F8FAFC', fontWeight=600).encode(
                text=alt.Text('Metric:Q', format='.1f' if view_mode=="Financial Impact" else 'd')
            )
            
            c1 = (area1 + points1 + text1).properties(height=300).interactive()
            c1 = c1.configure_view(strokeWidth=0).configure_axis(grid=False)
            st.altair_chart(c1, use_container_width=True)

    with col_cause:
        with st.container(border=True):
            cause_h1, cause_h2 = st.columns([3, 1])
            with cause_h1:
                st.markdown("""
                <div class="analytics-card-title">Root cause breakdown</div>
                <div class="analytics-card-sub">Top 4 discrepancy categories</div>
                """, unsafe_allow_html=True)
            with cause_h2:
                st.page_link(st.session_state.pages["triage"], label="Log", icon="↗️")
                
            df_cause = pd.DataFrame({
                "Cause": ["Deductions", "Dropped", "Off-Tracker", "Carrier"],
                "Count": [149, 100, 42, 24],
                "Value": [14.8, 9.2, 3.4, 1.8]
            })
            if selected_agency:
                df_cause["Count"] = df_cause["Count"] * 0.25 # Mock filter
                df_cause["Value"] = df_cause["Value"] * 0.25 # Mock filter
                
            y_col = "Count" if view_mode == "Volume" else "Value"
            
            donut = alt.Chart(df_cause).mark_arc(innerRadius=70, cornerRadius=6, stroke="#0B1121", strokeWidth=2).encode(
                theta=alt.Theta(f"{y_col}:Q", sort=None),
                color=alt.Color("Cause:N", scale=alt.Scale(
                    domain=["Deductions", "Dropped", "Off-Tracker", "Carrier"],
                    range=["#FFD600", "#00F0FF", "#FF2A54", "#00E676"]
                ), legend=alt.Legend(title="Category", labelColor="#94A3B8", titleColor="#F8FAFC", orient="bottom")),
                tooltip=["Cause", alt.Tooltip(f"{y_col}:Q", format=".1f" if view_mode=="Financial Impact" else "d")]
            )
            
            c2 = donut.properties(height=300).interactive()
            c2 = c2.configure_view(strokeWidth=0)
            st.altair_chart(c2, use_container_width=True)

    with st.container(border=True):
        st.markdown("""
        <div class="analytics-card-title">Complaint distribution</div>
        <div class="analytics-card-sub">Pareto analysis · 72.6% in top 2 categories</div>
        """, unsafe_allow_html=True)
        pareto_df = pd.DataFrame({
            "Category": ["Silent Delay", "Ghost Ticket", "Short Payout", "Unlogged Msg", "No Reason"],
            "Count": [61, 32, 21, 17, 5]
        })
        if selected_agency:
            pareto_df["Count"] = pareto_df["Count"] * 0.25 # Mock filter
            
        # Calculate cumulative percentage for true Pareto
        pareto_df = pareto_df.sort_values(by="Count", ascending=False)
        pareto_df["CumPct"] = pareto_df["Count"].cumsum() / pareto_df["Count"].sum() * 100
        
        base = alt.Chart(pareto_df).encode(
            x=alt.X("Category", sort=None, axis=alt.Axis(labelAngle=-45, grid=False, domain=False, tickColor='transparent', labelColor='#94A3B8'))
        )
        
        # Bars for absolute volume
        bars3 = base.mark_bar(color="rgba(255, 42, 84, 0.2)", stroke="#FF2A54", strokeWidth=1, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            y=alt.Y("Count", axis=alt.Axis(gridColor='rgba(255,255,255,0.05)', domain=False, labelColor='#94A3B8')),
            tooltip=["Category", "Count"]
        )
        
        # Line for cumulative impact (80/20 rule)
        line3 = base.mark_line(color="#00F0FF", strokeWidth=3, point=alt.OverlayMarkDef(color="#00F0FF", size=60)).encode(
            y=alt.Y("CumPct", title="Cumulative %", scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(grid=False, domain=False, labelColor='#00F0FF', titleColor='#00F0FF', tickColor='transparent')),
            tooltip=["Category", "Count", alt.Tooltip("CumPct:Q", format=".1f", title="Cumulative %")]
        )
        
        # Layer them with independent Y axes
        c3 = alt.layer(bars3, line3).resolve_scale(y='independent').properties(height=260).interactive()
        c3 = c3.configure_view(strokeWidth=0).configure_axis(grid=False)
        st.altair_chart(c3, use_container_width=True)

# ---------------------------------------------------------------------------
# RCA Section — Executive Summary Card & Dialog
# ---------------------------------------------------------------------------
@st.dialog("AI Root Cause Synthesis", width="large")
def run_ai_rca(window_str: str = "All"):
    st.write("Synthesizing operational discrepancies with Gemini...")
    with st.spinner("Analyzing cross-ledger dependencies..."):
        summary = api_client.generate_ai_rca(window=window_str)
    st.info(summary)
    if st.button("Close Window", use_container_width=True):
        st.rerun()

def render_rca_section(window_str: str = "All") -> None:
    """Renders AI root-cause analysis as a CSS grid of insight cards."""
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-section-label">AI Root Cause Synthesis</div>', unsafe_allow_html=True)

    st.markdown("""<div class="rca-grid">
<div class="doppel-shell">
<div class="doppel-core" style="padding: 20px;">
<div class="eyebrow eyebrow-red">Intake Handoff Failure</div>
<div class="val-text" style="font-size: 1.5rem; margin-bottom: 8px;">100 tickets dropped</div>
<div class="sub-text" style="margin-top: 0;">
Support closed tickets before Finance confirmation, leaving agency partners in silent limbo with no status updates.
</div>
</div>
</div>
<div class="doppel-shell">
<div class="doppel-core" style="padding: 20px;">
<div class="eyebrow eyebrow-yellow">Deduction Variance</div>
<div class="val-text" style="font-size: 1.5rem; margin-bottom: 8px;">₹14.8L contested</div>
<div class="sub-text" style="margin-top: 0;">
149 airline penalty deduction mismatches applied without pre-disclosure to agencies. Financial exposure growing monthly.
</div>
</div>
</div>
<div class="doppel-shell">
<div class="doppel-core" style="padding: 20px;">
<div class="eyebrow eyebrow-blue">Projected Outcome</div>
<div class="val-text" style="font-size: 1.5rem; margin-bottom: 8px;">&lt; 4h resolution</div>
<div class="sub-text" style="margin-top: 0;">
8.2× SLA improvement achievable with zero added headcount through automated SSOT pipeline matching.
</div>
</div>
</div>
</div>""", unsafe_allow_html=True)

    with st.container():
        st.markdown("<br/>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Generate On-Demand AI RCA", type="primary", key="btn_run_rca", use_container_width=True, icon="✨"):
                run_ai_rca(window_str)


# ---------------------------------------------------------------------------
# Main Entrypoint
# ---------------------------------------------------------------------------
def render_dashboard() -> None:
    """Main Operations Dashboard view entrypoint."""
    inject_dashboard_styles()

    selected_window = render_dashboard_header()
    metrics = api_client.get_dashboard_metrics(window=selected_window)

    render_kpi_cards(metrics)
    render_pipeline_corridor(metrics)
    render_rca_section(selected_window)
    
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    
    # Interactive Tabs wrapper for deep-dive sections
    t_analytics, t_health = st.tabs(["Risk Analytics", "Carrier SLA Health"])
    
    with t_analytics:
        render_analytics()
        
    with t_health:
        render_carrier_health()

    st.markdown("<br/>", unsafe_allow_html=True)
    
    with st.expander("💬 Operations Copilot"):
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [{"role": "assistant", "content": "Hello! I am your Operations Copilot. How can I help you analyze the SSOT data today?"}]
        
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        if prompt := st.chat_input("Ask AI about this data..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.chat_message("user").markdown(prompt)
            # Dummy response
            resp = "I can see that Peak Journeys has the most disputes. I recommend reaching out to them to clarify the deduction policies."
            st.session_state.chat_history.append({"role": "assistant", "content": resp})
            st.chat_message("assistant").markdown(resp)

    st.markdown("<br/><br/>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Explore Raw Datasets", type="secondary", use_container_width=True, key="btn_dash_to_db", icon="🔍"):
            st.switch_page(st.session_state.pages["database"])
