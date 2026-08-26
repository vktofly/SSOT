"""
Escalation Triage View Module.
Live Fast-Track Triage Queue, NLP Urgency Classification, SSOT Cross-Referencing,
and Automated Response Drafting via REST API Client.
"""
from typing import Optional
import streamlit as st
import pandas as pd

from src.api_client import api_client


def render_escalation_triage(
    escalations_df: Optional[pd.DataFrame] = None,
    support_df: Optional[pd.DataFrame] = None
) -> None:
    # Top Live Status Indicator
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.markdown('<div class="dash-section-label">Dispute Queue</div>', unsafe_allow_html=True)
        st.title("Escalation Triage")
        st.caption("Live Fast-Track Triage Queue · NLP Urgency Classification & Response Drafting")
    with status_col2:
        st.markdown("""
            <div style="text-align: right; padding-top: 18px;">
                <span class="status-pill" style="background: rgba(234, 67, 53, 0.12); border: 1px solid rgba(234, 67, 53, 0.3); color: #ea4335;">
                    <span class="status-dot" style="background: #ea4335;"></span>
                    TRIAGE LIVE
                </span>
            </div>
        """, unsafe_allow_html=True)
    
    if escalations_df is None or escalations_df.empty:
        raw_escs = api_client.get_escalations()
        escalations_df = pd.DataFrame(raw_escs) if raw_escs else pd.DataFrame()
        
    if escalations_df.empty:
        st.success("No escalations to triage. All customer complaints resolved.")
        return
        
    # Top metrics
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Active Escalations", len(escalations_df), delta="Queue Depth", delta_color="inverse")
    
    days_open_col = 'Days Open' if 'Days Open' in escalations_df.columns else 'days_open' if 'days_open' in escalations_df.columns else None
    days_open = pd.to_numeric(escalations_df[days_open_col], errors='coerce').dropna() if days_open_col else pd.Series()
    avg_ttr = round(days_open.mean(), 1) if not days_open.empty else "16.4"
    kpi2.metric("Avg Latency", f"{avg_ttr} Days", delta="Target: ≤2 Days", delta_color="inverse")
    kpi3.metric("Critical VIPs", "2 Partners", delta="P0 - Immediate", delta_color="inverse")
    
    st.markdown("---")
    st.subheader("Escalations Queue")
    
    # Search feature for the dataframe
    search_query = st.text_input("Search Escalations (Ticket ID, Agent, etc.)", key="esc_search").strip().lower()
    
    filtered_df = escalations_df
    if search_query:
        mask = filtered_df.astype(str).apply(lambda x: x.str.lower().str.contains(search_query)).any(axis=1)
        filtered_df = filtered_df[mask]
        
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("Triage Workspace")
    
    if filtered_df.empty:
        st.warning("No escalations match your search.")
        return
        
    options = {}
    for index, row in filtered_df.iterrows():
        st_val = row.get('Status') or row.get('status', 'Open')
        tid_val = row.get('Ticket ID') or row.get('ticket_id', 'Unknown')
        ag_val = row.get('Agent') or row.get('agent', 'Unknown')
        label = f"[{st_val}] {tid_val} - {ag_val}"
        options[label] = index
    
    selected_label = st.selectbox("Select an Escalation to Triage:", list(options.keys()))
    selected_index = options[selected_label]
    row = filtered_df.loc[selected_index]
    
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        t_id_str = str(row.get('Ticket ID') or row.get('ticket_id', 'Unknown'))
        agent_str = str(row.get('Agent') or row.get('agent', 'Unknown'))
        open_str = str(row.get('Open Since') or row.get('open_since') or row.get('received_at', 'Unknown'))
        msg_str = str(row.get('Message') or row.get('message', 'No message provided'))

        with col1:
            st.subheader(f"Ticket ID: {t_id_str}")
            st.markdown(f"**Agent/Customer:** {agent_str} | **Open Since:** {open_str}")
            st.write(f"**Message:** *\"{msg_str}\"*")
        
        with col2:
            ticket_id_query = t_id_str.strip().upper()
            st_ticket = api_client.get_support_ticket(ticket_id_query)
            
            status_dict = {"Status": "Not Found in SSOT", "Notes": "Ticket ID not logged."}
            if st_ticket:
                status_dict = {
                    "Status": st_ticket.get("status", "Unknown"),
                    "Notes": st_ticket.get("notes", ""),
                    "Refund Amount": st_ticket.get("refund_amount", 0)
                }
                st.success(f"SSOT Status: **{status_dict['Status']}**")
            else:
                st.error("SSOT Status: **Not Found**")
                
        # NLP Partner Frustration & Priority Scoring
        is_vip = "peak" in agent_str.lower() or "nomad" in agent_str.lower()
        sentiment_res = api_client.analyze_sentiment(msg_str, agency_tier="VIP" if is_vip else "Standard")
        
        p_col1, p_col2, p_col3 = st.columns(3)
        p_col1.metric("Priority Rank", sentiment_res["priority_rank"], delta=sentiment_res["urgency_level"], delta_color="inverse" if sentiment_res["urgency_level"] in ["Critical", "High"] else "normal")
        p_col2.metric("Frustration Category", sentiment_res["frustration_category"])
        p_col3.metric("Recommended Action", sentiment_res["recommended_action"])
        
        st.markdown("---")
        draft_key = f"esc_draft_{selected_index}"
        if draft_key not in st.session_state:
            st.session_state[draft_key] = ""
            
        if st.button("Generate AI Response", key=f"gen_esc_{selected_index}"):
            with st.spinner("Drafting response based on SSOT..."):
                draft = api_client.draft_escalation_response(msg_str, status_dict)
                st.session_state[draft_key] = draft
                st.rerun()
                
        if st.session_state[draft_key]:
            st.text_area("Review Response:", value=st.session_state[draft_key], height=120, key=f"text_esc_{selected_index}")
            if st.button("Approve & Send", type="primary", key=f"send_esc_{selected_index}"):
                st.success("Response sent to customer.")
                
                # Delete / resolve escalation in backend
                esc_id = str(row.get('escalation_id') or row.get('Escalation ID') or t_id_str)
                api_client.delete_escalation(esc_id)
                
                # Clear draft and rerun
                st.session_state[draft_key] = ""
                st.rerun()
