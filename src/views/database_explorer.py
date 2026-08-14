import streamlit as st
import pandas as pd

def render_database_explorer(support_df, finance_df, escalations_df):
    # Top Live Status Indicator
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.title("🗄️ Database Explorer")
        st.caption("⚡ Unified Single Source of Truth · Cross-department relational database explorer")
    with status_col2:
        st.markdown("""
            <div style="text-align: right; padding-top: 18px;">
                <span style="background: rgba(147, 51, 234, 0.15); border: 1px solid rgba(147, 51, 234, 0.4); color: #c084fc; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">
                    🟢 SQLITE SYNCED
                </span>
            </div>
        """, unsafe_allow_html=True)
        
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    c1.metric("Support Records", len(support_df) if not support_df.empty else 0, delta="Inbound Requests", delta_color="off")
    c2.metric("Finance Records", len(finance_df) if not finance_df.empty else 0, delta="Payout Actuals", delta_color="off")
    c3.metric("Escalation Records", len(escalations_df) if not escalations_df.empty else 0, delta="Partner Complaints", delta_color="off")
    with c4:
        st.markdown("<div style='padding-top: 12px;'></div>", unsafe_allow_html=True)
        if st.session_state.get('role') == 'Manager':
            csv = support_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Unified SSOT", data=csv, file_name="unified_ssot.csv", mime="text/csv", use_container_width=True)
            
    st.markdown("---")
    
    search_query = st.text_input("🔍 Global Ticket Search (Enter Ticket ID, Agent Name, Route, etc.)", key="global_search_query").strip()
    
    if search_query:
        # Filter all dataframes dynamically
        support_view = support_df[support_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]
        finance_view = finance_df[finance_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]
        escalations_view = escalations_df[escalations_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]
    else:
        support_view = support_df
        finance_view = finance_df
        escalations_view = escalations_df

    # Frontend Data Masking (Least Privilege)
    if st.session_state.get('role') == 'Junior':
        st.warning("🔒 **Junior Role Active**: Sensitive financial and PII data is masked.")
        def mask_sensitive_data(df):
            masked_df = df.copy()
            if 'Agent' in masked_df.columns:
                masked_df['Agent'] = masked_df['Agent'].apply(lambda x: str(x)[:2] + '***' + str(x)[-1:] if len(str(x)) > 3 else '***')
            if 'Support Amount' in masked_df.columns:
                masked_df['Support Amount'] = '[HIDDEN]'
            if 'Finance Amount' in masked_df.columns:
                masked_df['Finance Amount'] = '[HIDDEN]'
            return masked_df
            
        support_view = mask_sensitive_data(support_view)
        finance_view = mask_sensitive_data(finance_view)
        escalations_view = mask_sensitive_data(escalations_view)

    tab1, tab2, tab3 = st.tabs(["Support Tracker (600 Rows)", "Finance Tracker (500 Rows)", "Escalations Log (172 Rows)"])
    
    with tab1:
        st.subheader("Support Tracker (B2B Agent Bookings)")
        st.dataframe(support_view, use_container_width=True, hide_index=True)
        
    with tab2:
        st.subheader("Finance Tracker (Actuals & Deductions)")
        st.dataframe(finance_view, use_container_width=True, hide_index=True)
        
    with tab3:
        st.subheader("Escalations & Anomalies")
        st.dataframe(escalations_view, use_container_width=True, hide_index=True)
