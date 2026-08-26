"""
Unified Database Explorer View Module.
Cross-department relational database explorer, global text search, PII masking for Junior roles,
and SSOT CSV exports via REST API Client.
"""
from typing import Dict, Any, Optional
import pandas as pd
import streamlit as st

from src.api_client import api_client


def mask_sensitive_data(df: pd.DataFrame) -> pd.DataFrame:
    """Applies role-based data masking (least privilege) for junior roles."""
    masked_df = df.copy()
    if 'Agent' in masked_df.columns:
        masked_df['Agent'] = masked_df['Agent'].apply(
            lambda x: str(x)[:2] + '***' + str(x)[-1:] if len(str(x)) > 3 else '***'
        )
    if 'agent' in masked_df.columns:
        masked_df['agent'] = masked_df['agent'].apply(
            lambda x: str(x)[:2] + '***' + str(x)[-1:] if len(str(x)) > 3 else '***'
        )
    if 'Agent Name' in masked_df.columns:
        masked_df['Agent Name'] = masked_df['Agent Name'].apply(
            lambda x: str(x)[:2] + '***' + str(x)[-1:] if len(str(x)) > 3 else '***'
        )
    if 'agent_name' in masked_df.columns:
        masked_df['agent_name'] = masked_df['agent_name'].apply(
            lambda x: str(x)[:2] + '***' + str(x)[-1:] if len(str(x)) > 3 else '***'
        )
    if 'Support Amount' in masked_df.columns:
        masked_df['Support Amount'] = '[HIDDEN]'
    if 'refund_amount' in masked_df.columns:
        masked_df['refund_amount'] = '[HIDDEN]'
    if 'Finance Amount' in masked_df.columns:
        masked_df['Finance Amount'] = '[HIDDEN]'
    if 'amount_paid' in masked_df.columns:
        masked_df['amount_paid'] = '[HIDDEN]'
    if 'Amount Paid (INR)' in masked_df.columns:
        masked_df['Amount Paid (INR)'] = '[HIDDEN]'
    if 'Refund Amount (INR)' in masked_df.columns:
        masked_df['Refund Amount (INR)'] = '[HIDDEN]'
    return masked_df


def render_database_explorer_header() -> None:
    """Renders top header with live synchronization indicator and injects minimalist CSS."""
    st.markdown("""
    <style>
    /* Minimalist UI - Warm Monochrome & Flat Bento Grid */
    .minimal-bg {
        background-color: #FBFBFA;
    }
    .minimal-card {
        background: #FFFFFF;
        border: 1px solid #EAEAEA;
        border-radius: 8px;
        padding: 24px;
        box-shadow: none;
    }
    .minimal-tag {
        border-radius: 9999px;
        padding: 4px 10px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
        width: fit-content;
        margin-bottom: 12px;
    }
    .tag-blue { background: #E1F3FE; color: #1F6C9F; }
    .tag-green { background: #EDF3EC; color: #346538; }
    .tag-red { background: #FDEBEC; color: #9F2F2D; }
    .tag-yellow { background: #FBF3DB; color: #956400; }
    
    .minimal-val {
        font-family: 'SF Pro Display', 'Geist Sans', 'Helvetica Neue', sans-serif;
        font-size: 2.5rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        color: #111111;
        line-height: 1.1;
    }
    .minimal-sub {
        font-family: 'SF Pro Display', 'Geist Sans', 'Helvetica Neue', sans-serif;
        font-size: 13px;
        color: #787774;
        margin-top: 8px;
    }
    .minimal-label {
        font-family: 'Geist Mono', 'SF Mono', monospace;
        font-size: 12px;
        color: #787774;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .minimal-title {
        font-family: 'Lyon Text', 'Newsreader', 'Playfair Display', serif;
        font-size: 2.5rem;
        color: #111111;
        letter-spacing: -0.02em;
        line-height: 1.1;
    }
    </style>
    """, unsafe_allow_html=True)

    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.markdown('<div class="minimal-label">SSOT Explorer</div>', unsafe_allow_html=True)
        st.markdown('<div class="minimal-title">Database Explorer</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #787774; font-size: 14px; margin-top: 8px;">Unified Single Source of Truth · Cross-department relational database explorer</div>', unsafe_allow_html=True)
    with status_col2:
        st.markdown(
            '<div style="text-align: right; padding-top: 18px;">'
            '<span class="minimal-tag tag-green" style="display: inline-block;">'
            '● REST API Synced'
            '</span>'
            '</div>',
            unsafe_allow_html=True
        )


def render_database_kpis(
    support_df: pd.DataFrame, 
    finance_df: pd.DataFrame, 
    escalations_df: pd.DataFrame
) -> None:
    """Renders minimalist Bento grid row count metrics with manager export action."""
    
    html = f"""<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; margin-top: 32px;">
<div class="minimal-card">
<div class="minimal-tag tag-blue">Support Records</div>
<div class="minimal-val">{len(support_df) if not support_df.empty else 0}</div>
<div class="minimal-sub">Inbound Claims</div>
</div>
<div class="minimal-card">
<div class="minimal-tag tag-yellow">Finance Records</div>
<div class="minimal-val">{len(finance_df) if not finance_df.empty else 0}</div>
<div class="minimal-sub">Bank Settlements</div>
</div>
<div class="minimal-card">
<div class="minimal-tag tag-red">Escalation Records</div>
<div class="minimal-val">{len(escalations_df) if not escalations_df.empty else 0}</div>
<div class="minimal-sub">Partner Disputes</div>
</div>
</div>"""
    st.markdown(html, unsafe_allow_html=True)
    
    col_empty, col_btn = st.columns([4, 1])
    with col_btn:
        if st.session_state.get('role') == 'Manager':
            csv = support_df.to_csv(index=False).encode('utf-8') if not support_df.empty else b""
            st.download_button(
                "Export Unified SSOT", 
                data=csv, 
                file_name="unified_ssot.csv", 
                mime="text/csv", 
                use_container_width=True,
                key="btn_export_unified_db"
            )
        else:
            st.caption("Export reserved for Managers.")
            
    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)


def render_database_explorer(
    support_df: Optional[pd.DataFrame] = None, 
    finance_df: Optional[pd.DataFrame] = None, 
    escalations_df: Optional[pd.DataFrame] = None
) -> None:
    """Main Database Explorer view entrypoint."""
    render_database_explorer_header()
    
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    with st.container():
        search_col, badge_col = st.columns([3, 1])
        with search_col:
            search_query = st.text_input(
                "Global Ticket & Entity Search", 
                placeholder="Enter Ticket ID (RF-1099), Agency Name, Route (DEL-DXB), or Status...",
                key="global_search_query"
            ).strip()
        with badge_col:
            st.write("")
            st.caption("Live multi-table indexing across all 3 datasets")
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    
    # Load on-demand from API client if not provided
    if support_df is None or support_df.empty:
        raw_sup = api_client.get_support_tickets(search=search_query or None)
        support_df = pd.DataFrame(raw_sup) if raw_sup else pd.DataFrame()
    elif search_query:
        support_df = support_df[support_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False, regex=False)).any(axis=1)]

    if finance_df is None or finance_df.empty:
        if st.session_state.get('role') == 'Manager':
            raw_fin = api_client.get_finance_records(search=search_query or None)
            finance_df = pd.DataFrame(raw_fin) if raw_fin else pd.DataFrame()
        else:
            finance_df = pd.DataFrame([{"Notice": "Finance records restricted to Manager role."}])
    elif search_query:
        finance_df = finance_df[finance_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False, regex=False)).any(axis=1)]

    if escalations_df is None or escalations_df.empty:
        raw_esc = api_client.get_escalations(search=search_query or None)
        escalations_df = pd.DataFrame(raw_esc) if raw_esc else pd.DataFrame()
    elif search_query:
        escalations_df = escalations_df[escalations_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False, regex=False)).any(axis=1)]

    render_database_kpis(support_df, finance_df, escalations_df)

    if search_query:
        total_hits = len(support_df) + len(finance_df) + len(escalations_df)
        st.info(f"Found **{total_hits}** matching records across 3 tables for query `{search_query}`.")

    # Role-Based Access Control / Masking
    if st.session_state.get('role') == 'Operator':
        st.warning("**Operator Role Active**: Sensitive financial amounts and PII are masked by DLP policy.")
        support_view = mask_sensitive_data(support_df)
        finance_view = mask_sensitive_data(finance_df)
        escalations_view = mask_sensitive_data(escalations_df)
    else:
        support_view = support_df
        finance_view = finance_df
        escalations_view = escalations_df

    tab1, tab2, tab3 = st.tabs([
        f"Support Tracker ({len(support_view)} Rows)", 
        f"Finance Tracker ({len(finance_view)} Rows)", 
        f"Escalations Log ({len(escalations_view)} Rows)"
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
