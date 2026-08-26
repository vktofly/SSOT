"""
Partner Health & Churn Risk Matrix View.
Displays live B2B agency sentiment telemetry, VIP retention warnings,
and fast-track outreach dispatch via REST API client.
"""
from typing import Optional
import streamlit as st
import pandas as pd

from src.api_client import api_client


def render_partner_matrix(
    escalations_df: Optional[pd.DataFrame] = None,
    support_df: Optional[pd.DataFrame] = None
) -> None:
    st.markdown('<div class="dash-section-label">Partner Intelligence</div>', unsafe_allow_html=True)
    st.title("Partner Health & Churn Risk Matrix")
    st.caption("Live B2B Agency Sentiment Telemetry · VIP Partner Retention & Early Warning Churn Radar")
    
    matrix_resp = api_client.get_partner_matrix()
    partners_list = matrix_resp.get("partners", [])
    summary_dict = matrix_resp.get("summary", {})

    if not partners_list:
        st.success("No active partner escalations. All agency health scores are optimal (100% green).")
        return
        
    summary_rows = []
    agency_stats = {}
    for p in partners_list:
        agent_name = p.get("agency_name") or p.get("Agency Name", "Unknown")
        tier = p.get("revenue_tier") or p.get("Revenue Tier", "Standard")
        active_escs = p.get("active_escalations") or p.get("Active Escalations", 0)
        sent_idx = float(p.get("sentiment_index") or p.get("Sentiment Index", 0.0))
        bottleneck = p.get("primary_bottleneck") or p.get("Primary Bottleneck", "General")
        risk_status = p.get("risk_status") or p.get("Risk Status", "STABLE")

        summary_rows.append({
            "Agency Name": agent_name,
            "Revenue Tier": tier,
            "Active Escalations": active_escs,
            "Sentiment Index": sent_idx,
            "Primary Bottleneck": bottleneck,
            "Risk Status": risk_status,
        })
        agency_stats[agent_name] = {
            "Agent": agent_name,
            "Tier": tier,
            "Escalations": active_escs,
            "Sentiment": sent_idx,
            "Bottleneck": bottleneck,
            "Sample_Messages": p.get("sample_messages", []),
        }

    summary_df = pd.DataFrame(summary_rows)
    
    total_agencies = summary_dict.get("total_monitored_agencies") or len(summary_df)
    critical_vips = summary_dict.get("critical_vips_count") or len(summary_df[summary_df["Risk Status"].str.contains("CRITICAL", na=False)])
    overall_sentiment = summary_dict.get("fleet_sentiment_index") or (round(summary_df["Sentiment Index"].mean(), 2) if not summary_df.empty else 0.0)
    dominant_complaint = summary_dict.get("dominant_complaint", "Fee Deductions")
    
    # 4 Executive Telemetry Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Monitored Agencies", total_agencies, delta="Active Partners", delta_color="off")
    c2.metric("Critical VIPs at Risk", critical_vips, delta="High Priority Action", delta_color="inverse" if critical_vips > 0 else "normal")
    c3.metric("Fleet Sentiment Index", f"{overall_sentiment}", delta="Scale: -1.0 to +1.0", delta_color="inverse" if overall_sentiment < 0 else "normal")
    c4.metric("Dominant Complaint", dominant_complaint, delta="Dispute Corridor", delta_color="inverse")
    
    st.markdown("---")
    st.subheader("Partner Telemetry & Retention Leaderboard")
    
    # Render stylized data grid
    st.dataframe(
        summary_df,
        column_config={
            "Sentiment Index": st.column_config.ProgressColumn(
                "Sentiment Index",
                help="NLP Sentiment Score mapped to -1.0 to +1.0 range",
                format="%.2f",
                min_value=-1.0,
                max_value=1.0,
            ),
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("Partner Drill-Down & Fast Outreach")
    
    selected_agency = st.selectbox("Select Partner Agency for Incident Review:", list(agency_stats.keys()))
    if selected_agency:
        p_data = agency_stats[selected_agency]
        with st.container(border=True):
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.markdown(f"### {selected_agency} (`{p_data['Tier']} Partner`)")
                st.markdown(f"**Total Escalations Logged:** `{p_data['Escalations']}`")
                st.markdown("**Recent Inbound Communications:**")
                samples = p_data.get("Sample_Messages", [])
                if samples:
                    for sample in samples[:3]:
                        st.caption(f"*\"{sample}\"*")
                else:
                    st.caption("*No recorded complaints on file. Standard operational health.*")
            with col_b:
                st.markdown("### Fast-Track Actions")
                if st.button(f"Launch VIP Reassurance Dispatch", type="primary", use_container_width=True):
                    api_client.dispatch_partner_outreach(selected_agency, action_type="VIP Reassurance")
                    st.success(f"Proactive VIP account manager outreach scheduled for {selected_agency}.")
                    st.session_state['show_success_toast'] = True
                    st.rerun()
                if st.button("Jump to Reconciliation Queue", use_container_width=True):
                    if "pages" in st.session_state and "reconciliation" in st.session_state.pages:
                        st.switch_page(st.session_state.pages["reconciliation"])
                if st.button("Jump to Escalation Triage", use_container_width=True):
                    if "pages" in st.session_state and "triage" in st.session_state.pages:
                        st.switch_page(st.session_state.pages["triage"])
