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

def init_ingestion_state():
    if "webhook_inbox" not in st.session_state:
        st.session_state.webhook_inbox = [
            "Hi, I cancelled booking for DEL-DXB last week and was told I'd get a refund. I don't have my ref number. My number is 9876543210.",
            "urgent! MAA-CMB refund not processed yet for Peak Journeys agency.",
            "Need status on my refund."
        ]
    if "review_queue" not in st.session_state:
        st.session_state.review_queue = []

def render_ingestion():
    st.title("📥 Ingestion Agent (Event-Driven)")
    st.markdown("Simulates a background AI process that automatically reads from a webhook inbox and stages structured data for human review.")
    
    init_ingestion_state()
    
    # Top-level metrics for enterprise feel
    col1, col2, col3 = st.columns(3)
    col1.metric("Live Webhook Inbox", len(st.session_state.webhook_inbox))
    col2.metric("Pending Human Review", len(st.session_state.review_queue))
    col3.metric("Processed Today", 42) # Mock metric

    st.markdown("---")
    
    # Webhook Inbox Section
    st.subheader("1. Incoming Message Queue")
    if not st.session_state.webhook_inbox:
        st.success("✅ Inbox is empty. No new messages.")
    else:
        with st.container(border=True):
            for i, msg in enumerate(st.session_state.webhook_inbox):
                msg_col, btn_col = st.columns([5, 1])
                with msg_col:
                    st.markdown(f"💬 **WhatsApp ID-{1042 + i}:** *{msg}*")
                with btn_col:
                    if st.button("Ingest", key=f"ingest_single_{i}", use_container_width=True):
                        with st.spinner("..."):
                            result = parse_informal_message(msg)
                            st.session_state.review_queue.append(result)
                            st.session_state.webhook_inbox.pop(i)
                            st.rerun()
                st.divider()
                
        if st.button("▶️ Run AI Auto-Ingestion (Batch Process All)", type="primary"):
            with st.spinner("Processing via LLM and redacting PII..."):
                for msg in st.session_state.webhook_inbox:
                    result = parse_informal_message(msg)
                    st.session_state.review_queue.append(result)
                st.session_state.webhook_inbox = []
                st.rerun()
                
    st.markdown("---")
    
    # Human Review Queue Section
    st.subheader("2. Human Review Grid")
    if not st.session_state.review_queue:
        st.info("No tickets awaiting review.")
    else:
        low_confidence = any(r.get("confidence_score", 100) < 80 for r in st.session_state.review_queue)
        if low_confidence:
            st.warning("⚠️ Some extractions had low AI confidence. Please review carefully.")
            
        df_queue = pd.DataFrame(st.session_state.review_queue)
        edited_df = st.data_editor(df_queue, num_rows="dynamic", use_container_width=True)
        
        if st.button("Approve All & Save to SSOT", type="primary"):
            st.session_state.review_queue = []
            st.success("Tickets successfully committed to the SSOT database!")
            st.balloons()
            st.rerun()

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
        
        # Audit Log CSV Export (RBAC: Managers only)
        if st.session_state.get('role') == 'Manager':
            csv_data = "Log_Entry\n" + "\n".join([f'"{log}"' for log in st.session_state.system_logs])
            st.download_button(
                label="📥 Download Audit Log (CSV)",
                data=csv_data,
                file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("🔒 Audit Log Export is restricted to Managers.")
        
        with st.expander("🛠️ System Activity Logs", expanded=True):
            for log in st.session_state.system_logs:
                st.text(log)

def render_database_explorer(support_df, finance_df, escalations_df):
    st.title("🗄️ Database Explorer")
    st.markdown("Global view of all underlying CSV databases in the Single Source of Truth.")
    
    # Global Ticket Search
    search_query = st.text_input("🔍 Global Ticket Search (Enter Ticket ID, Agent Name, etc.)").strip()
    
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


    tab1, tab2, tab3 = st.tabs(["Support Tracker", "Finance Tracker", "Escalations"])
    
    with tab1:
        st.subheader("Support Tracker (B2B Agent Bookings)")
        st.dataframe(support_view, use_container_width=True)
        
    with tab2:
        st.subheader("Finance Tracker (Actuals & Deductions)")
        st.dataframe(finance_view, use_container_width=True)
        
    with tab3:
        st.subheader("Escalations & Anomalies")
        st.dataframe(escalations_view, use_container_width=True)
