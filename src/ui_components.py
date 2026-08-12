import streamlit as st
import pandas as pd
from datetime import datetime
from src.agents import parse_informal_message, draft_reconciliation_message, analyze_escalations, fuzzy_match_metadata, batch_fuzzy_match_metadata, draft_escalation_response
from src.db import delete_escalation, update_support_status, insert_support_record, update_ticket_id
from src.data_manager import load_data, find_mismatches, find_orphans
from src.config import HAS_API_KEY

def render_dashboard():
    st.title("Operations Telemetry Dashboard")
    st.markdown("Real-time view of refund pipeline health and escalation metrics.")
    
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
        # Count tickets in Support that are missing in Finance and vice-versa
        missing_in_finance, missing_in_support = find_orphans(support_df, finance_df)
        missing_in_finance_count = len(missing_in_finance)
        missing_in_support_count = len(missing_in_support)
        mismatches = len(find_mismatches(support_df, finance_df))
    else:
        missing_in_finance_count = 0
        missing_in_support_count = 0
        mismatches = 0
    
    def go_to_database(query):
        st.session_state._current_page = "🗄️ Database Explorer"
        st.session_state._nav_version = st.session_state.get("_nav_version", 0) + 1
        st.session_state.global_search_query = query

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Escalations", total_escalations, delta="High Volume", delta_color="inverse")
    with col2:
        st.metric("Avg Time to Resolution", f"{avg_ttr} Days", delta="Dynamic", delta_color="off")
    with col3:
        st.metric("Dropped (Support -> Finance)", missing_in_finance_count, delta="Leakage", delta_color="inverse")
        if missing_in_finance_count > 0:
            with st.expander("View Tickets"):
                for i, m in enumerate(missing_in_finance[:5]):
                    tid = str(m['Ticket ID'])
                    st.button(f"🔍 {tid}", key=f"dash_drop_{i}_{tid}", on_click=go_to_database, args=(tid,))
                if missing_in_finance_count > 5:
                    st.caption(f"+ {missing_in_finance_count - 5} more...")
    with col4:
        st.metric("Unlogged (Finance -> Support)", missing_in_support_count, delta="Silent Payouts", delta_color="inverse")
        if missing_in_support_count > 0:
            with st.expander("View Tickets"):
                for i, m in enumerate(missing_in_support[:5]):
                    ref = str(m['Ref No'])
                    st.button(f"🔍 {ref}", key=f"dash_unlog_{i}_{ref}", on_click=go_to_database, args=(ref,))
                if missing_in_support_count > 5:
                    st.caption(f"+ {missing_in_support_count - 5} more...")
    
    st.markdown("---")
    
    st.subheader("🤖 AI Executive Summary")
    st.markdown("Generate a quick root-cause analysis of the recent escalation volume.")
    if st.button("🔍 Generate AI Executive Summary", type="primary"):
        with st.spinner("Analyzing escalation data with Gemini..."):
            summary = analyze_escalations(escalations_df)
            st.info(summary)
            
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
    if "processed_today" not in st.session_state:
        st.session_state.processed_today = 0

def render_ingestion():
    st.title("📥 Ingestion Agent (Event-Driven)")
    st.markdown("Simulates a background AI process that automatically reads from a webhook inbox and stages structured data for human review.")
    
    init_ingestion_state()
    
    # Top-level metrics for enterprise feel
    col1, col2, col3 = st.columns(3)
    col1.metric("Live Webhook Inbox", len(st.session_state.webhook_inbox))
    col2.metric("Pending Human Review", len(st.session_state.review_queue))
    col3.metric("Processed Today", st.session_state.processed_today)

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
                    if st.button("Ingest", key=f"ingest_single_{i}", width="stretch"):
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
    st.subheader("2. Inbox Zero Review")
    if not st.session_state.review_queue:
        st.info("No tickets awaiting review.")
    else:
        low_confidence = any(r.get("confidence_score", 100) < 80 for r in st.session_state.review_queue)
        if low_confidence:
            st.warning("⚠️ Some extractions had low AI confidence. Please review carefully.")
            
        total_remaining = len(st.session_state.review_queue)
        st.markdown(f"**{total_remaining} tickets pending review.**")

        # The st.selectbox natively supports type-to-search, so we don't need a separate search bar
        ticket_options = {f"Queue Index {i+1} | Agent: {r.get('agent_name', 'Unknown')} | Route: {r.get('route', 'Unknown')}": i for i, r in enumerate(st.session_state.review_queue)}
        
        selected_label = st.selectbox("Select a ticket to review:", list(ticket_options.keys()), key="ingest_select")
        selected_index = ticket_options[selected_label]
        r = st.session_state.review_queue[selected_index]
        
        with st.container(border=True):
            st.subheader(f"🎫 Ingested Ticket #{selected_index + 1}")
            
            if "error" in r:
                st.error(f"⚠️ AI Parsing Failed: {r['error']}")
            else:
                st.markdown(f"**AI Confidence Score:** `{r.get('confidence_score', 'N/A')}%` — Review the extracted details below.")
            
            # Database lookup
            support_db = st.session_state.get('support_db', pd.DataFrame())
            db_record = None
            ref_id_val = r.get("reference_id")
            ref_id_val = ref_id_val if ref_id_val is not None else ""
            agent_val = r.get("agent_name")
            agent_val = agent_val if agent_val is not None else ""
            route_val = r.get("route")
            route_val = route_val if route_val is not None else ""
            
            if ref_id_val and 'Ticket ID' in support_db.columns:
                matches = support_db[support_db['Ticket ID'] == ref_id_val]
                if not matches.empty:
                    db_record = matches.iloc[0]
            elif agent_val and route_val and 'Agent' in support_db.columns and 'Route' in support_db.columns:
                matches = support_db[(support_db['Agent'].str.contains(agent_val, case=False, na=False)) & 
                                     (support_db['Route'].str.contains(route_val, case=False, na=False))]
                if not matches.empty:
                    db_record = matches.iloc[0]
            
            # Use columns for a more premium, balanced layout similar to the metrics in Reconciliation
            col1, col2 = st.columns(2)
            
            with col1:
                # Ensure we handle None if the LLM explicitly returns null
                new_agent = st.text_input(f"🏢 Agent Name{' ✨' if agent_val else ''}", value=agent_val, key=f"agent_{selected_index}")
                
                intent_options = ["status_update", "new_refund", "other"]
                current_intent = r.get("intent", "other")
                if current_intent not in intent_options:
                    intent_options.append(current_intent)
                new_intent = st.selectbox(f"🎯 Intent{' ✨' if current_intent != 'other' else ''}", options=intent_options, index=intent_options.index(current_intent), key=f"intent_{selected_index}")
                
                new_ref_id = st.text_input(f"🏷️ Reference ID / PNR{' ✨' if ref_id_val else ''}", value=ref_id_val, key=f"ref_id_{selected_index}")
                
                wait_time_val = r.get("elapsed_wait_time")
                wait_time_val = wait_time_val if wait_time_val is not None else ""
                new_wait_time = st.text_input(f"⏱️ Elapsed Wait Time{' ✨' if wait_time_val else ''}", value=wait_time_val, key=f"wait_{selected_index}")
                
            with col2:
                new_route = st.text_input(f"✈️ Route{' ✨' if route_val else ''}", value=route_val, key=f"route_{selected_index}")
                
                urgency_options = ["High", "Medium", "Low", "Unknown"]
                current_urgency = r.get("urgency", "Unknown")
                if current_urgency not in urgency_options:
                    urgency_options.append(current_urgency)
                new_urgency = st.selectbox(f"🚨 Urgency{' ✨' if current_urgency != 'Unknown' else ''}", options=urgency_options, index=urgency_options.index(current_urgency), key=f"urgency_{selected_index}")
                
                refund_val = r.get("expected_refund_amount")
                refund_val = str(refund_val) if refund_val is not None else ""
                new_refund = st.text_input(f"💰 Expected Refund (₹){' ✨' if refund_val else ''}", value=refund_val, key=f"refund_{selected_index}")
                
                channel_options = ["WhatsApp", "Email", "Phone", "Unknown"]
                current_channel = r.get("source_channel", "Unknown")
                if current_channel not in channel_options:
                    channel_options.append(current_channel)
                new_channel = st.selectbox(f"📡 Source Channel{' ✨' if current_channel != 'Unknown' else ''}", options=channel_options, index=channel_options.index(current_channel), key=f"channel_{selected_index}")
            
            new_missing_ref = st.checkbox(f"Missing Reference Number / PNR{' ✨' if 'missing_reference' in r else ''}", value=bool(r.get("missing_reference", False)), key=f"ref_{selected_index}")
            
            st.markdown("---")
            
            with st.expander("More Fields (Database Linked)", expanded=True):
                if db_record is not None:
                    st.success("✅ Match found in database.")
                    col3, col4 = st.columns(2)
                    with col3:
                        st.text_input("📅 Request Date", value=str(db_record.get('Request Date', '')), disabled=True)
                        st.text_input("💳 Status", value=str(db_record.get('Status', '')), disabled=True)
                    with col4:
                        st.text_input("📝 Notes", value=str(db_record.get('Notes', '')), disabled=True)
                        st.text_input("👨‍💼 Handled By", value=str(db_record.get('Handled By', '')), disabled=True)
                else:
                    st.info("No matching record found in the SSOT Database. These fields will be generated when approved.")
            
            st.markdown("---")
            
            col_btn, _ = st.columns([1, 3])
            with col_btn:
                if st.button("Approve & Save to SSOT", type="primary", key=f"approve_{selected_index}", width="stretch"):
                    # Append or update in support_df
                    support_df = st.session_state.support_df
                    
                    new_row = {
                        'Ticket ID': new_ref_id,
                        'Agent': new_agent,
                        'Route': new_route,
                        'Refund Amount (INR)': new_refund,
                        'Request Date': datetime.now().strftime("%d-%b-%Y"),
                        'Last Updated': datetime.now().strftime("%d-%b-%Y"),
                        'Status': 'Processing',
                        'Handled By': 'AI Ingestion',
                        'Channel': new_channel,
                        'Notes': f"Intent: {new_intent}, Urgency: {new_urgency}"
                    }
                    
                    if new_ref_id and 'Ticket ID' in support_df.columns and new_ref_id in support_df['Ticket ID'].values:
                        idx = support_df.index[support_df['Ticket ID'] == new_ref_id].tolist()[0]
                        for k, v in new_row.items():
                            support_df.at[idx, k] = v
                    else:
                        new_df = pd.DataFrame([new_row])
                        st.session_state.support_df = pd.concat([support_df, new_df], ignore_index=True)
                    
                    # Persist to SQLite
                    insert_support_record(new_row)
                    
                    st.session_state.processed_today += 1
                    
                    # Remove from queue
                    st.session_state.review_queue.pop(selected_index)
                    st.success("Ticket successfully committed to the SSOT database!")
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
    
    col_desc, col_export = st.columns([3, 1])
    with col_desc:
        st.markdown("Identifies financial discrepancies and drafts explanatory messages for human review (Human-in-the-loop).")
    with col_export:
        csv_data = support_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Export Clean SSOT",
            data=csv_data,
            file_name="Reconciled_SSOT.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    raw_mismatches = find_mismatches(support_df, finance_df)
    missing_in_finance, missing_in_support = find_orphans(support_df, finance_df)
    init_reconciliation_state(raw_mismatches)
    
    tab1, tab2 = st.tabs(["💸 Deduction Mismatches", "🔗 Orphaned Tickets & AI Linkage"])
    
    with tab1:
        # Filter out tickets that have been marked as resolved in this session
        pending_mismatches = [m for m in raw_mismatches if m['Ticket ID'] not in st.session_state.resolved_tickets]
        
        if pending_mismatches:
            total_mismatches = len(raw_mismatches)
            pending_count = len(pending_mismatches)
            resolved_count = total_mismatches - pending_count
            
            progress = resolved_count / total_mismatches
            st.progress(progress, text=f"Resolved {resolved_count} of {total_mismatches} tickets")
            
            # Allow the user to select which ticket to review to prioritize high-value items (selectbox is natively searchable)
            ticket_options = {f"Ticket {m['Ticket ID']} | Agent: {m['Agent']} | Deduction: ₹{m['Deduction']}": m for m in pending_mismatches}
            
            selected_label = st.selectbox("Select a ticket to review:", list(ticket_options.keys()))
            m = ticket_options[selected_label]
            
            with st.container(border=True):
                tid = str(m['Ticket ID'])
                if m.get('Risk Level') == 'High':
                    st.error("🚨 HIGH RISK (Difference > 20%)")
                st.subheader(f"Ticket: {tid} | Agent: {m['Agent']}")
                colA, colB, colC = st.columns(3)
                colA.metric("Support Quoted", f"₹{m['Support Amount']}")
                colB.metric("Finance Paid", f"₹{m['Finance Amount']}")
                colC.metric("Deduction", f"₹{m['Deduction']}", delta=m['Reason'], delta_color="off")
                
                st.markdown("### 🤖 AI Drafted Explanation")
                    
                draft_key = f"draft_{tid}"
                if draft_key not in st.session_state:
                    st.session_state[draft_key] = ""
                    
                if st.button("Generate Draft", key=f"gen_draft_{tid}"):
                    with st.spinner("Drafting response..."):
                        draft = draft_reconciliation_message(
                            m['Agent'], m['Route'], tid, 
                            m['Support Amount'], m['Finance Amount'], 
                            m['Deduction'], m['Reason']
                        )
                        st.session_state[draft_key] = draft
                        st.rerun()
                        
                if st.session_state[draft_key]:
                    edited_draft = st.text_area("Review Message:", value=st.session_state[draft_key], height=150, key=f"text_{tid}")
                    
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("Approve & Send", type="primary", key=f"send_draft_{tid}"):
                            st.session_state.resolved_tickets.add(tid)
                                
                            
                            # Update Support DB
                            support_df = st.session_state.support_df
                            if tid in support_df['Ticket ID'].values:
                                idx = support_df.index[support_df['Ticket ID'] == tid].tolist()[0]
                                support_df.at[idx, 'Status'] = 'Client Notified'
                                current_notes = support_df.at[idx, 'Notes']
                                if pd.isna(current_notes):
                                    current_notes = ""
                                new_notes = f"{current_notes} | Finance Deduction: {m['Reason']}".strip(" |")
                                support_df.at[idx, 'Notes'] = new_notes
                                
                                # Persist to SQLite
                                update_support_status(tid, 'Client Notified', new_notes)
                            
                            log_action(f"Email dispatched to {m['Agent']} regarding Ticket {tid}. SSOT Status updated to 'Client_Notified'.")
                            st.session_state['show_success_toast'] = True
                            st.rerun()
        else:
            st.success("🎉 All discrepancies have been resolved! Inbox zero.")
        
    with tab2:
        st.subheader("Orphaned Tickets")
        st.markdown("These tickets exist in one tracker but are missing in the other.")
        
        # Display High-Risk Agent Warnings
        high_risk_agents = set([m.get('Risk Note') for m in missing_in_finance if m.get('Risk Level') == 'High'])
        for note in high_risk_agents:
            if note:
                st.warning(f"🚨 **High-Risk Agent Detected:** {note}")
        
        
        col_s, col_f = st.columns(2)
        with col_s:
            st.info(f"**Missing in Finance ({len(missing_in_finance)})**")
            for m in missing_in_finance[:5]:  # Display top 5
                st.markdown(f"- **{m['Ticket ID']}** | {m.get('Agent', 'Unknown')} | ₹{m.get('Refund Amount (INR)', '0')}")
        with col_f:
            st.warning(f"**Missing in Support ({len(missing_in_support)})**")
            for m in missing_in_support[:5]:
                st.markdown(f"- **{m['Ref No']}** | {m.get('Agent Name', 'Unknown')} | ₹{m.get('Amount Paid (INR)', '0')}")
                
        st.markdown("---")
        st.subheader("🤖 AI Entity Resolution (Metadata Linkage)")
        st.markdown("If a ticket ID was typed incorrectly (and failed exact/fuzzy text match), use the LLM to find the most probable match based on metadata (Agent Name, Route, Amount).")
        
        if missing_in_finance and missing_in_support:
            if st.button("🚀 Run Batch AI Linkage", type="primary"):
                with st.spinner("Analyzing metadata across orphaned tickets in batches..."):
                    all_matches = []
                    # Process in chunks of 10 to avoid token limits
                    chunk_size = 10
                    for i in range(0, len(missing_in_finance), chunk_size):
                        chunk = missing_in_finance[i:i+chunk_size]
                        
                        # Pre-filter Finance candidates for this chunk to save tokens
                        filtered_finance = []
                        for f_cand in missing_in_support:
                            try:
                                f_amt = float(str(f_cand.get('Amount Paid (INR)', '0')).replace(',', ''))
                            except ValueError:
                                f_amt = 0.0
                            
                            f_agent = str(f_cand.get('Agent Name', '')).lower()
                            f_words = set(w for w in f_agent.split() if len(w) > 2)
                            
                            keep = False
                            for s_cand in chunk:
                                try:
                                    s_amt = float(str(s_cand.get('Refund Amount (INR)', '0')).replace(',', ''))
                                except ValueError:
                                    s_amt = 0.0
                                
                                s_agent = str(s_cand.get('Agent', '')).lower()
                                s_words = set(w for w in s_agent.split() if len(w) > 2)
                                
                                # Condition 1: Amount is within 20%
                                if s_amt > 0 and f_amt > 0:
                                    if abs(s_amt - f_amt) <= max(s_amt, f_amt) * 0.20:
                                        keep = True
                                        break
                                
                                # Condition 2: Agent name has overlapping words
                                if f_words and s_words and len(f_words & s_words) > 0:
                                    keep = True
                                    break
                            
                            if keep:
                                filtered_finance.append(f_cand)
                        
                        # Only call LLM if there are plausible candidates
                        if filtered_finance:
                            matches = batch_fuzzy_match_metadata(chunk, filtered_finance)
                            if matches:
                                all_matches.extend(matches)
                            
                    if all_matches:
                        st.session_state.batch_matches = all_matches
                        st.rerun()
                    else:
                        st.error("No confident matches found across all orphans.")
                        
            if st.session_state.get('batch_matches'):
                st.subheader("🤖 Proposed Linkages (Awaiting Approval)")
                
                if 'acted_matches' not in st.session_state:
                    st.session_state.acted_matches = set()
                
                # Filter matches to ones not acted upon
                pending_matches = [m for m in st.session_state.batch_matches if m['support_ticket_id'] not in st.session_state.acted_matches]
                
                if not pending_matches:
                    st.success("All proposed linkages have been reviewed.")
                    if st.button("Clear Proposals"):
                        st.session_state.batch_matches = None
                        st.session_state.acted_matches.clear()
                        st.rerun()
                else:
                    # Collect agent names for filtering
                    agent_names = set()
                    for match in pending_matches:
                        s_id = match['support_ticket_id']
                        s_row = next((r for r in missing_in_finance if r['Ticket ID'] == s_id), None)
                        if s_row and s_row.get('Agent'):
                            agent_names.add(s_row['Agent'])
                    
                    selected_agents = st.multiselect("Filter by Support Agent Name:", list(agent_names), default=[])
                    
                    # Apply filter
                    filtered_matches = pending_matches
                    if selected_agents:
                        filtered_matches = []
                        for match in pending_matches:
                            s_id = match['support_ticket_id']
                            s_row = next((r for r in missing_in_finance if r['Ticket ID'] == s_id), None)
                            if s_row and s_row.get('Agent') in selected_agents:
                                filtered_matches.append(match)
                                
                    st.write(f"Showing {len(filtered_matches)} of {len(pending_matches)} remaining proposals.")
                    
                    for i, match in enumerate(filtered_matches):
                        s_id = match['support_ticket_id']
                        f_id = match['finance_ref_no']
                        
                        s_row = next((r for r in missing_in_finance if r['Ticket ID'] == s_id), {})
                        f_row = next((r for r in missing_in_support if r['Ref No'] == f_id), {})
                        
                        with st.container(border=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Support Ticket (Missing in Finance):** `{s_id}`")
                                st.write(f"Agent: {s_row.get('Agent', 'Unknown')} | Amount: ₹{s_row.get('Refund Amount (INR)', '0')} | Route: {s_row.get('Sector', 'Unknown')}")
                            with col2:
                                st.markdown(f"**Proposed Finance Record:** `{f_id}`")
                                st.write(f"Agent: {f_row.get('Agent Name', 'Unknown')} | Amount: ₹{f_row.get('Amount Paid (INR)', '0')} | Route: {f_row.get('Route', 'Unknown')}")
                                
                            st.info(f"**AI Reasoning:** {match.get('reasoning')}")
                            
                            score = match.get('confidence_score', 0)
                            color = "🟢 High" if score >= 90 else "🟡 Medium" if score >= 70 else "🔴 Low"
                            st.progress(score / 100, text=f"**Confidence:** {score}% ({color})")
                            
                            c_btn1, c_btn2, _ = st.columns([1, 1, 3])
                            with c_btn1:
                                if st.button("✅ Approve & Merge", key=f"app_{i}_{s_id}"):
                                    update_ticket_id(s_id, f_id)
                                    idx = st.session_state.support_df.index[st.session_state.support_df['Ticket ID'] == s_id].tolist()
                                    if idx:
                                        st.session_state.support_df.at[idx[0], 'Ticket ID'] = f_id
                                    st.session_state.acted_matches.add(s_id)
                                    log_action(f"Approved AI Linkage: {s_id} -> {f_id}")
                                    st.rerun()
                            with c_btn2:
                                if st.button("❌ Reject", type="secondary", key=f"rej_{i}_{s_id}"):
                                    st.session_state.acted_matches.add(s_id)
                                    log_action(f"Rejected AI Linkage: {s_id} -> {f_id}")
                                    st.rerun()
                                    
                    st.markdown("---")
                    if filtered_matches and st.button(f"✅ Approve & Merge All Filtered Linkages ({len(filtered_matches)})", type="primary"):
                        for match in filtered_matches:
                            s_id = match['support_ticket_id']
                            f_id = match['finance_ref_no']
                            update_ticket_id(s_id, f_id)
                            idx = st.session_state.support_df.index[st.session_state.support_df['Ticket ID'] == s_id].tolist()
                            if idx:
                                st.session_state.support_df.at[idx[0], 'Ticket ID'] = f_id
                            st.session_state.acted_matches.add(s_id)
                            
                        st.success(f"Successfully linked {len(filtered_matches)} tickets! SSOT updated permanently.")
                        log_action(f"Batch AI Linkage approved for {len(filtered_matches)} tickets.")
                        st.rerun()
        else:
            st.success("No orphaned tickets to match!")
            
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
    
    col1, col2 = st.columns([4, 1])
    with col1:
        search_query = st.text_input("🔍 Global Ticket Search (Enter Ticket ID, Agent Name, etc.)", key="global_search_query").strip()
    with col2:
        if st.session_state.get('role') == 'Manager':
            csv = support_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Unified SSOT", data=csv, file_name="unified_ssot.csv", mime="text/csv", use_container_width=True)
    
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
        st.dataframe(support_view, width="stretch")
        
    with tab2:
        st.subheader("Finance Tracker (Actuals & Deductions)")
        st.dataframe(finance_view, width="stretch")
        
    with tab3:
        st.subheader("Escalations & Anomalies")
        st.dataframe(escalations_view, width="stretch")

def render_escalation_triage(escalations_df, support_df):
    st.title("🚨 Escalation Triage")
    st.markdown("AI-assisted workflow for drafting responses to customer escalations based on the SSOT.")
    
    if escalations_df is None or escalations_df.empty:
        st.success("No escalations to triage!")
        return
        
    st.info(f"**{len(escalations_df)} Escalations found in the queue.**")
    
    # Show entire data
    st.subheader("Escalations Queue")
    
    # Search feature for the dataframe
    search_query = st.text_input("🔍 Search Escalations (Ticket ID, Agent, etc.)", key="esc_search").strip().lower()
    
    filtered_df = escalations_df
    if search_query:
        # Filter across all string columns
        mask = filtered_df.astype(str).apply(lambda x: x.str.lower().str.contains(search_query)).any(axis=1)
        filtered_df = filtered_df[mask]
        
    st.dataframe(filtered_df, width="stretch")
    
    st.markdown("---")
    st.subheader("Triage Workspace")
    
    if filtered_df.empty:
        st.warning("No escalations match your search.")
        return
        
    # Dropdown to select an escalation to triage
    # Use index to uniquely identify the row, but show Ticket ID and Agent in the label
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
            # Look up status in SSOT
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
