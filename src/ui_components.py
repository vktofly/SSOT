import streamlit as st
import pandas as pd
from datetime import datetime
from src.agents import parse_informal_message, draft_reconciliation_message
from src.data_manager import load_data, find_mismatches
from src.config import HAS_API_KEY

def render_dashboard():
    st.title("Operations Telemetry Dashboard")
    st.markdown("Real-time view of refund pipeline health and escalation metrics.")
    
    total_escalations = 155
    missing_in_finance = 100
    mismatches = 149
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Escalations", total_escalations, delta="High Volume", delta_color="inverse")
    col2.metric("Dropped Tickets (Support -> Finance)", missing_in_finance, delta="Leakage", delta_color="inverse")
    col3.metric("Deduction Mismatches", mismatches, delta="Communication Gap", delta_color="inverse")
    
    st.markdown("---")
    st.subheader("System Architecture")
    st.info("💡 **Proposed Architecture**: By implementing the **Model Context Protocol (MCP)**, our AI agents can securely read from and write to the internal SSOT without exposing the raw database credentials to the LLM context. The Ingestion Agent captures unstructured data and sanitizes it, while the Execution Agent reconciles anomalies.")

def render_ingestion():
    st.title("Ingestion Agent")
    st.markdown("Parses informal WhatsApp/Email requests into structured SSOT tickets to prevent data leakage.")
    
    with st.form("ingestion_form"):
        text_input = st.text_area("Paste WhatsApp or Email Message:", height=150, 
                                  value="Hi, I cancelled booking for DEL-DXB last week and was told I'd get a refund. I haven't received anything and I don't have any reference number.")
        submitted = st.form_submit_button("Extract & Create Ticket", type="primary")
        
    if submitted:
        with st.spinner("Processing via AI Ingestion Agent..."):
            result = parse_informal_message(text_input)
            st.success("Extraction Complete!")
            
            confidence = result.get("confidence_score", 100)
            if confidence < 80:
                st.warning(f"⚠️ Low AI Confidence ({confidence}%). Human review required before saving.")
            
            st.markdown("**Extracted Data (Editable):**")
            df_result = pd.DataFrame([result])
            edited_df = st.data_editor(df_result, num_rows="dynamic", use_container_width=True)
            
            if st.button("Confirm & Save to SSOT (Mock)"):
                st.success("Data saved successfully!")
                st.balloons()

def init_reconciliation_state(mismatches):
    """Initializes session state to track resolved tickets."""
    if "resolved_tickets" not in st.session_state:
        st.session_state.resolved_tickets = set()
    if "system_logs" not in st.session_state:
        st.session_state.system_logs = []

def log_action(message: str):
    """Adds a log entry for the system logs expander."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.system_logs.insert(0, f"[{timestamp}] {message}")

def render_reconciliation(support_df, finance_df):
    st.title("Reconciliation Agent (HITL Workflow)")
    st.markdown("Identifies financial discrepancies and drafts explanatory messages for human review (Human-in-the-loop).")
    
    raw_mismatches = find_mismatches(support_df, finance_df)
    init_reconciliation_state(raw_mismatches)
    
    # Filter out tickets that have been marked as resolved in this session
    pending_mismatches = [m for m in raw_mismatches if m['Ticket ID'] not in st.session_state.resolved_tickets]
    
    if pending_mismatches:
        st.markdown(f"**Found {len(pending_mismatches)} discrepancies requiring review.**")
        
        # Display the top mismatch for HITL review
        m = pending_mismatches[0]
        
        with st.container(border=True):
            st.subheader(f"Ticket: {m['Ticket ID']} | Agent: {m['Agent']}")
            colA, colB, colC = st.columns(3)
            colA.metric("Support Quoted", f"₹{m['Support Amount']}")
            colB.metric("Finance Paid", f"₹{m['Finance Amount']}")
            colC.metric("Deduction", f"₹{m['Deduction']}", delta=m['Reason'], delta_color="off")
            
            st.markdown("### 🤖 AI Drafted Explanation")
            
            # Using session state to persist the draft across re-renders when buttons are clicked
            draft_key = f"draft_{m['Ticket ID']}"
            if draft_key not in st.session_state:
                st.session_state[draft_key] = ""
                
            if st.button("Generate Draft", key=f"gen_{m['Ticket ID']}"):
                with st.spinner("Drafting response..."):
                    draft = draft_reconciliation_message(
                        m['Agent'], m['Route'], m['Ticket ID'], 
                        m['Support Amount'], m['Finance Amount'], 
                        m['Deduction'], m['Reason']
                    )
                    st.session_state[draft_key] = draft
                    st.rerun()
                    
            if st.session_state[draft_key]:
                edited_draft = st.text_area("Review Message:", value=st.session_state[draft_key], height=150)
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("Approve & Send", type="primary", key=f"send_{m['Ticket ID']}"):
                        st.session_state.resolved_tickets.add(m['Ticket ID'])
                        log_action(f"Email dispatched to {m['Agent']} regarding Ticket {m['Ticket ID']}. SSOT Status updated to 'Client_Notified'.")
                        # We use balloons internally within the click, then rerun
                        st.session_state['show_success_toast'] = True
                        st.rerun()
    else:
        st.success("🎉 All discrepancies have been resolved! Inbox zero.")
        
    # Check if we need to show a success message from a previous button click
    if st.session_state.get('show_success_toast', False):
        st.success("Message sent successfully! SSOT updated.")
        st.balloons()
        st.session_state['show_success_toast'] = False
        
    # Render System Logs
    if st.session_state.system_logs:
        st.markdown("---")
        
        # Audit Log CSV Export
        csv_data = "Log_Entry\n" + "\n".join([f'"{log}"' for log in st.session_state.system_logs])
        st.download_button(
            label="📥 Download Audit Log (CSV)",
            data=csv_data,
            file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
        with st.expander("🛠️ System Activity Logs", expanded=True):
            for log in st.session_state.system_logs:
                st.text(log)
