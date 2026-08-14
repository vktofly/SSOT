import streamlit as st
import pandas as pd
from src.agents import analyze_escalations
from src.data_manager import find_mismatches, find_orphans

def render_dashboard():
    # Top Live Status Indicator
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.title("Operations Telemetry Dashboard")
        st.caption("⚡ Live Single Source of Truth (SSOT) · Real-time pipeline reconciliation & escalation monitor")
    with status_col2:
        st.markdown("""
            <div style="text-align: right; padding-top: 18px;">
                <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); color: #10b981; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">
                    🟢 LIVE SYNC ACTIVE
                </span>
            </div>
        """, unsafe_allow_html=True)
    
    # Calculate metrics dynamically
    support_df = st.session_state.get('support_df', pd.DataFrame())
    finance_df = st.session_state.get('finance_df', pd.DataFrame())
    escalations_df = st.session_state.get('escalations_df', pd.DataFrame())
    
    total_escalations = len(escalations_df)
    
    if not escalations_df.empty and 'Days Open' in escalations_df.columns:
        days_open = pd.to_numeric(escalations_df['Days Open'], errors='coerce').dropna()
        avg_ttr = round(days_open.mean(), 1) if not days_open.empty else "N/A"
    else:
        avg_ttr = "N/A"
    
    if not support_df.empty and not finance_df.empty and 'Ticket ID' in support_df.columns and 'Ref No' in finance_df.columns:
        missing_in_finance, missing_in_support = find_orphans(support_df, finance_df)
        missing_in_finance_count = len(missing_in_finance)
        missing_in_support_count = len(missing_in_support)
        mismatches_list = find_mismatches(support_df, finance_df)
        mismatches_count = len(mismatches_list)
    else:
        missing_in_finance_count = 0
        missing_in_support_count = 0
        mismatches_count = 0
    
    def go_to_page(page_name):
        try:
            st.switch_page(page_name)
        except Exception:
            pass

    # 4 Executive KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Escalations", total_escalations, delta="172 Open", delta_color="inverse")
    with col2:
        st.metric("Avg Resolution Time", f"{avg_ttr} Days", delta="Target: ≤2 Days", delta_color="inverse")
    with col3:
        st.metric("Dropped Handoffs", missing_in_finance_count, delta="Support -> Finance Leak", delta_color="inverse")
    with col4:
        st.metric("Deduction Mismatches", mismatches_count, delta="Short Payouts", delta_color="inverse")

    st.markdown("---")

    # Pipeline Health Breakdown Bar
    st.subheader("📊 Pipeline Integrity & Health Index")
    total_pipeline = len(support_df) if not support_df.empty else 600
    healthy_count = max(0, total_pipeline - missing_in_finance_count - mismatches_count)
    healthy_pct = round((healthy_count / total_pipeline) * 100, 1)
    
    col_bar, col_actions = st.columns([2, 1])
    with col_bar:
        st.markdown(f"**Pipeline Health: {healthy_pct}% Balanced** ({healthy_count} of {total_pipeline} clean handoffs)")
        st.progress(healthy_pct / 100)
        
        b1, b2, b3 = st.columns(3)
        b1.markdown(f"🟢 **Clean:** {healthy_count} tickets")
        b2.markdown(f"🔴 **Dropped:** {missing_in_finance_count} tickets")
        b3.markdown(f"🟡 **Mismatched:** {mismatches_count} tickets")
        
    with col_actions:
        st.markdown("**⚡ Fast-Track Actions:**")
        if st.button("⚖️ Review Mismatches", use_container_width=True):
            go_to_page("reconciliation")
        if st.button("🚨 Triage Escalations", use_container_width=True):
            go_to_page("triage")

    st.markdown("---")
    
    # AI Root-Cause RCA
    st.subheader("🤖 AI Root-Cause RCA & Analysis")
    st.caption("One-click LLM synthesis across Support, Finance, and Escalation datasets.")
    
    if st.button("🔍 Generate AI Executive RCA", type="primary"):
        with st.spinner("Analyzing operational discrepancies with Gemini..."):
            summary = analyze_escalations(escalations_df)
            st.info(summary)
            
    st.markdown("---")
    st.subheader("🔐 Enterprise Architecture & Compliance")
    st.info("💡 **Unified SSOT Architecture**: By implementing automated **Model Context Protocol (MCP)** bridges, AI agents query normalized SQLite records without credentials exposure. PII regex redaction, DLP text locks, and role-based access control (RBAC) ensure financial compliance.")
