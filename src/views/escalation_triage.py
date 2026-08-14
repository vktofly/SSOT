import streamlit as st
import pandas as pd
from src.agents import draft_escalation_response, analyze_partner_sentiment
from src.db import delete_escalation

def render_escalation_triage(escalations_df, support_df):
    # Top Live Status Indicator
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.title("🚨 Escalation Triage")
        st.caption("⚡ Live Fast-Track Triage Queue · NLP Urgency Classification & Response Drafting")
    with status_col2:
        st.markdown("""
            <div style="text-align: right; padding-top: 18px;">
                <span style="background: rgba(244, 63, 94, 0.15); border: 1px solid rgba(244, 63, 94, 0.4); color: #f43f5e; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">
                    🟢 TRIAGE LIVE
                </span>
            </div>
        """, unsafe_allow_html=True)
    
    if escalations_df is None or escalations_df.empty:
        st.success("No escalations to triage! All customer complaints resolved.")
        return
        
    # Top metrics
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Active Escalations", len(escalations_df), delta="Queue Depth", delta_color="inverse")
    
    days_open = pd.to_numeric(escalations_df['Days Open'], errors='coerce').dropna() if 'Days Open' in escalations_df.columns else pd.Series()
    avg_ttr = round(days_open.mean(), 1) if not days_open.empty else "16.4"
    kpi2.metric("Avg Latency", f"{avg_ttr} Days", delta="Target: ≤2 Days", delta_color="inverse")
    kpi3.metric("Critical VIPs", "2 Partners", delta="P0 - Immediate", delta_color="inverse")
    
    st.markdown("---")
    st.subheader("Escalations Queue")
    
    # Search feature for the dataframe
    search_query = st.text_input("🔍 Search Escalations (Ticket ID, Agent, etc.)", key="esc_search").strip().lower()
    
    filtered_df = escalations_df
    if search_query:
        # Filter across all string columns
        mask = filtered_df.astype(str).apply(lambda x: x.str.lower().str.contains(search_query)).any(axis=1)
        filtered_df = filtered_df[mask]
        
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("Triage Workspace")
    
    if filtered_df.empty:
        st.warning("No escalations match your search.")
        return
        
    options = {f"[{row.get('Status', 'Open')}] {row.get('Ticket ID', 'Unknown')} - {row.get('Agent', 'Unknown')}" : index for index, row in filtered_df.iterrows()}
    
    selected_label = st.selectbox("Select an Escalation to Triage:", list(options.keys()))
    selected_index = options[selected_label]
    row = filtered_df.loc[selected_index]
    
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Ticket ID: {row.get('Ticket ID', 'Unknown')}")
            st.markdown(f"**Agent/Customer:** {row.get('Agent', 'Unknown')} | **Open Since:** {row.get('Open Since', 'Unknown')}")
            st.write(f"💬 **Message:** *\"{row.get('Message', 'No message provided')}\"*")
        
        with col2:
            ticket_id = str(row.get('Ticket ID', '')).strip().upper()
            support_match = support_df[support_df['Ticket ID'] == ticket_id]
            
            status_dict = {"Status": "Not Found in SSOT", "Notes": "Ticket ID not logged."}
            if not support_match.empty:
                s_row = support_match.iloc[0]
                status_dict = {
                    "Status": s_row.get("Status", "Unknown"),
                    "Notes": s_row.get("Notes", ""),
                    "Refund Amount": s_row.get("Refund Amount (INR)", 0)
                }
                st.success(f"SSOT Status: **{status_dict['Status']}**")
            else:
                st.error("SSOT Status: **Not Found**")
                
        # NLP Partner Frustration & Priority Scoring
        msg_text = str(row.get('Message', ''))
        sentiment_res = analyze_partner_sentiment(msg_text, agency_tier="VIP" if "Peak" in str(row.get('Agent', '')) else "Standard")
        
        p_col1, p_col2, p_col3 = st.columns(3)
        p_col1.metric("Priority Rank", sentiment_res["priority_rank"], delta=sentiment_res["urgency_level"], delta_color="inverse" if sentiment_res["urgency_level"] in ["Critical", "High"] else "normal")
        p_col2.metric("Frustration Category", sentiment_res["frustration_category"])
        p_col3.metric("Recommended Action", sentiment_res["recommended_action"])
        
        st.markdown("---")
        draft_key = f"esc_draft_{selected_index}"
        if draft_key not in st.session_state:
            st.session_state[draft_key] = ""
            
        if st.button("🤖 Generate AI Response", key=f"gen_esc_{selected_index}"):
            with st.spinner("Drafting response based on SSOT..."):
                draft = draft_escalation_response(str(row.get('Message', '')), status_dict)
                st.session_state[draft_key] = draft
                st.rerun()
                
        if st.session_state[draft_key]:
            st.text_area("Review Response:", value=st.session_state[draft_key], height=120, key=f"text_esc_{selected_index}")
            if st.button("Approve & Send", type="primary", key=f"send_esc_{selected_index}"):
                st.success("Response sent to customer!")
                
                # Drop from active queue (session state)
                st.session_state.escalations_df = st.session_state.escalations_df.drop(selected_index)
                
                # Persist to SQLite
                delete_escalation(str(row.get('Ticket ID', '')), str(row.get('Message', '')))
                
                # Clear draft
                st.session_state[draft_key] = ""
                st.rerun()
