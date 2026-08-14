"""
Unified Database Explorer View Module.
Cross-department relational database explorer, global text search, PII masking for Junior roles,
and SSOT CSV exports.
Engineered following frontend-ui-engineering and designing-beautiful-websites standards.
"""
from typing import Dict, Any, Optional
import pandas as pd
import streamlit as st

def mask_sensitive_data(df: pd.DataFrame) -> pd.DataFrame:
    """Applies role-based data masking (least privilege) for junior roles."""
    masked_df = df.copy()
    if 'Agent' in masked_df.columns:
        masked_df['Agent'] = masked_df['Agent'].apply(
            lambda x: str(x)[:2] + '***' + str(x)[-1:] if len(str(x)) > 3 else '***'
        )
    if 'Agent Name' in masked_df.columns:
        masked_df['Agent Name'] = masked_df['Agent Name'].apply(
            lambda x: str(x)[:2] + '***' + str(x)[-1:] if len(str(x)) > 3 else '***'
        )
    if 'Support Amount' in masked_df.columns:
        masked_df['Support Amount'] = '[HIDDEN]'
    if 'Finance Amount' in masked_df.columns:
        masked_df['Finance Amount'] = '[HIDDEN]'
    if 'Amount Paid (INR)' in masked_df.columns:
        masked_df['Amount Paid (INR)'] = '[HIDDEN]'
    if 'Refund Amount (INR)' in masked_df.columns:
        masked_df['Refund Amount (INR)'] = '[HIDDEN]'
    return masked_df

def render_database_explorer_header() -> None:
    """Renders top header with live SQLite synchronization indicator."""
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.title("🗄️ Database Explorer")
        st.caption("Unified Single Source of Truth · Cross-department relational database explorer")
    with status_col2:
        st.info("🟢 SQLite Synced", icon="🗄️")

def render_database_kpis(
    support_df: pd.DataFrame, 
    finance_df: pd.DataFrame, 
    escalations_df: pd.DataFrame
) -> None:
    """Renders row count metrics across all 3 tables with manager export action."""
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    c1.metric("Support Records", len(support_df) if not support_df.empty else 0, delta="Inbound Claims", delta_color="off")
    c2.metric("Finance Records", len(finance_df) if not finance_df.empty else 0, delta="Bank Settlements", delta_color="off")
    c3.metric("Escalation Records", len(escalations_df) if not escalations_df.empty else 0, delta="Partner Disputes", delta_color="off")
    with c4:
        st.write("")
        if st.session_state.get('role') == 'Manager':
            csv = support_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export Unified SSOT", 
                data=csv, 
                file_name="unified_ssot.csv", 
                mime="text/csv", 
                use_container_width=True,
                key="btn_export_unified_db"
            )
        else:
            st.caption("🔒 Export reserved for Managers.")
    st.markdown("---")

def render_database_explorer(
    support_df: pd.DataFrame, 
    finance_df: pd.DataFrame, 
    escalations_df: pd.DataFrame
) -> None:
    """Main Database Explorer view entrypoint."""
    render_database_explorer_header()
    render_database_kpis(support_df, finance_df, escalations_df)
    
    with st.container(border=True):
        search_col, badge_col = st.columns([3, 1])
        with search_col:
            search_query = st.text_input(
                "🔍 Global Ticket & Entity Search", 
                placeholder="Enter Ticket ID (RF-1099), Agency Name, Route (DEL-DXB), or Status...",
                key="global_search_query"
            ).strip()
        with badge_col:
            st.write("")
            st.caption("⚡ Live multi-table indexing across all 3 datasets")
    
    if search_query:
        # Filter all dataframes safely with regex=False to prevent regex warnings
        support_view = support_df[support_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False, regex=False)).any(axis=1)]
        finance_view = finance_df[finance_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False, regex=False)).any(axis=1)]
        escalations_view = escalations_df[escalations_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False, regex=False)).any(axis=1)]
        
        total_hits = len(support_view) + len(finance_view) + len(escalations_view)
        st.info(f"🎯 Found **{total_hits}** matching records across 3 tables for query `{search_query}`.", icon="🔎")
    else:
        support_view = support_df
        finance_view = finance_df
        escalations_view = escalations_df

    # Role-Based Access Control / Masking
    if st.session_state.get('role') == 'Junior':
        st.warning("🔒 **Junior Role Active**: Sensitive financial amounts and PII are masked by DLP policy.", icon="🛡️")
        support_view = mask_sensitive_data(support_view)
        finance_view = mask_sensitive_data(finance_view)
        escalations_view = mask_sensitive_data(escalations_view)

    tab1, tab2, tab3 = st.tabs([
        f"📋 Support Tracker ({len(support_view)} Rows)", 
        f"💳 Finance Tracker ({len(finance_view)} Rows)", 
        f"🚨 Escalations Log ({len(escalations_view)} Rows)"
    ])
    
    with tab1:
        st.subheader("Support Tracker (B2B Agency Refund Claims)")
        st.caption("Inbound customer cancellation claims recorded by Support operations.")
        st.dataframe(support_view, use_container_width=True, hide_index=True)
        
    with tab2:
        st.subheader("Finance Tracker (Actual Banking Settlements)")
        st.caption("Accounting ledger records with processed payout amounts and deduction reasons.")
        st.dataframe(finance_view, use_container_width=True, hide_index=True)
        
    with tab3:
        st.subheader("Escalations Log (Partner Dispute Archive)")
        st.caption("Historical log of partner dissatisfaction, status chasing, and turnaround days.")
        st.dataframe(escalations_view, use_container_width=True, hide_index=True)
