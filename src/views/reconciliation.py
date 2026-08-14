import streamlit as st
import pandas as pd
from datetime import datetime
from src.agents import (
    draft_reconciliation_message, batch_fuzzy_match_metadata,
    generate_proactive_notification, lookup_airline_penalty
)
from src.db import update_support_status, update_ticket_id
from src.data_manager import find_mismatches, find_orphans

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
    raw_mismatches = find_mismatches(support_df, finance_df)
    missing_in_finance, missing_in_support = find_orphans(support_df, finance_df)
    init_reconciliation_state(raw_mismatches)

    # Top Live Status Indicator
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.title("⚖️ Reconciliation Agent (HITL Workflow)")
        st.caption("⚡ Human-In-The-Loop Discrepancy Matching · Fee Verification & Auto-Drafting")
    with status_col2:
        st.markdown("""
            <div style="text-align: right; padding-top: 18px;">
                <span style="background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); color: #f59e0b; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">
                    🟢 HITL RECON ACTIVE
                </span>
            </div>
        """, unsafe_allow_html=True)
        
    col_kpi1, col_kpi2, col_kpi3, col_export = st.columns([1, 1, 1, 1])
    pending_mismatches = [m for m in raw_mismatches if m['Ticket ID'] not in st.session_state.resolved_tickets]
    col_kpi1.metric("Pending Mismatches", len(pending_mismatches), delta="Requires Review", delta_color="inverse" if len(pending_mismatches) > 0 else "normal")
    col_kpi2.metric("Dropped in Finance", len(missing_in_finance), delta="100 Orphaned", delta_color="inverse")
    col_kpi3.metric("Resolved in Session", len(st.session_state.resolved_tickets), delta="Committed", delta_color="normal")
    with col_export:
        st.markdown("<div style='padding-top: 12px;'></div>", unsafe_allow_html=True)
        csv_data = support_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Export Clean SSOT",
            data=csv_data,
            file_name="Reconciled_SSOT.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["💸 Deduction Mismatches", "🔗 Orphaned Tickets & AI Linkage", "📢 Proactive Notification Bot"])
    
    with tab1:
        pending_mismatches = [m for m in raw_mismatches if m['Ticket ID'] not in st.session_state.resolved_tickets]
        
        if pending_mismatches:
            total_mismatches = len(raw_mismatches)
            pending_count = len(pending_mismatches)
            resolved_count = total_mismatches - pending_count
            
            progress = resolved_count / total_mismatches
            st.progress(progress, text=f"Resolved {resolved_count} of {total_mismatches} tickets")
            
            def handle_approve_send(ticket_id, mismatch_record, final_draft):
                st.session_state.resolved_tickets.add(ticket_id)
                
                # Update Support DB
                sdf = st.session_state.support_df
                if ticket_id in sdf['Ticket ID'].values:
                    idx = sdf.index[sdf['Ticket ID'] == ticket_id].tolist()[0]
                    sdf.at[idx, 'Status'] = 'Client Notified'
                    current_notes = sdf.at[idx, 'Notes']
                    if pd.isna(current_notes):
                        current_notes = ""
                    new_notes = f"{current_notes} | Finance Deduction: {mismatch_record['Reason']}".strip(" |")
                    sdf.at[idx, 'Notes'] = new_notes
                    
                    # Persist to SQLite
                    update_support_status(ticket_id, 'Client Notified', new_notes)
                
                log_action(f"Email dispatched to {mismatch_record['Agent']} regarding Ticket {ticket_id}. SSOT Status updated to 'Client_Notified'.")
                st.session_state['show_success_toast'] = True
                
            with st.expander("🛠️ Optional: Batch Resolve All Discrepancies"):
                st.markdown("Use this to automatically generate drafts and send emails for ALL pending deduction mismatches at once.")
                if st.button("🚀 Batch Process All Pending", type="primary"):
                    with st.spinner("Processing all pending tickets..."):
                        count = 0
                        for pending_m in pending_mismatches:
                            p_tid = str(pending_m['Ticket ID'])
                            draft = draft_reconciliation_message(
                                pending_m['Agent'], pending_m['Route'], p_tid, 
                                pending_m['Support Amount'], pending_m['Finance Amount'], 
                                pending_m['Deduction'], pending_m['Reason']
                            )
                            handle_approve_send(p_tid, pending_m, draft)
                            count += 1
                        st.success(f"Successfully processed {count} tickets.")
                        st.rerun()

            st.markdown("---")
            st.markdown("**Individual Review (Default Workflow)**")
            
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
                
                # Airline Policy RAG lookup
                route_str = m.get('Route', '')
                policy = lookup_airline_penalty(route_str)
                with st.expander(f"✈️ Airline Fare Rules ({policy['carrier']} - Sector {route_str or 'General'})", expanded=False):
                    st.markdown(f"**Carrier:** `{policy['carrier']}` | **Standard Fee:** `₹{policy['cancellation_fee']}` | **Standard SLA:** `{policy['sla_hours']} Hours`")
                    st.caption(f"📌 {policy['policy_notes']}")
                
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
                        
                if st.session_state[draft_key]:
                    edited_draft = st.text_area("Review Message:", value=st.session_state[draft_key], height=150, key=f"text_{tid}")
                    
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        st.button("Approve & Send", type="primary", key=f"send_draft_{tid}", on_click=handle_approve_send, args=(tid, m, edited_draft))
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
            for m in missing_in_finance[:5]:
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
                    chunk_size = 10
                    for i in range(0, len(missing_in_finance), chunk_size):
                        chunk = missing_in_finance[i:i+chunk_size]
                        
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
                                
                                if s_amt > 0 and f_amt > 0:
                                    if abs(s_amt - f_amt) <= max(s_amt, f_amt) * 0.20:
                                        keep = True
                                        break
                                
                                if f_words and s_words and len(f_words & s_words) > 0:
                                    keep = True
                                    break
                            
                            if keep:
                                filtered_finance.append(f_cand)
                        
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
                
                pending_matches = [m for m in st.session_state.batch_matches if m['support_ticket_id'] not in st.session_state.acted_matches]
                
                if not pending_matches:
                    st.success("All proposed linkages have been reviewed.")
                    if st.button("Clear Proposals"):
                        st.session_state.batch_matches = None
                        st.session_state.acted_matches.clear()
                        st.rerun()
                else:
                    agent_names = set()
                    for match in pending_matches:
                        s_id = match['support_ticket_id']
                        s_row = next((r for r in missing_in_finance if r['Ticket ID'] == s_id), None)
                        if s_row and s_row.get('Agent'):
                            agent_names.add(s_row['Agent'])
                    
                    selected_agents = st.multiselect("Filter by Support Agent Name:", list(agent_names), default=[])
                    
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
            
    with tab3:
        st.subheader("📢 Proactive Agent Notification Bot")
        st.markdown("Automate outbound status notifications to travel agents at key refund lifecycle milestones, preventing inbound status escalations.")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            stage = st.selectbox(
                "Lifecycle Milestone Event:",
                ["logged", "verified", "payout_done", "custom"],
                format_func=lambda x: {
                    "logged": "1. Request Logged (48h SLA Notice)",
                    "verified": "2. Finance Verification Complete",
                    "payout_done": "3. Payout Dispatched (With Fee Breakdown)",
                    "custom": "4. Custom Active Review Notice"
                }[x],
                key="proactive_stage_select"
            )
            
            channel = st.radio("Dispatch Channel:", ["WhatsApp", "Email"], horizontal=True, key="proactive_channel_radio")
            
            tickets_list = support_df['Ticket ID'].dropna().astype(str).tolist() if 'Ticket ID' in support_df.columns else []
            selected_ticket = st.selectbox("Select Associated Ticket:", tickets_list[:50], key="proactive_ticket_select") if tickets_list else ""
            
            t_row = support_df[support_df['Ticket ID'] == selected_ticket].iloc[0] if selected_ticket and not support_df[support_df['Ticket ID'] == selected_ticket].empty else {}
            
            agent_input = st.text_input("Travel Agent / Agency:", value=t_row.get("Agent", "Peak Journeys"), key="proactive_agent_input")
            route_input = st.text_input("Travel Route / Sector:", value=t_row.get("Route", "DEL-DXB"), key="proactive_route_input")
            amount_input = st.text_input("Refund Amount (INR):", value=str(t_row.get("Refund Amount (INR)", "5400")), key="proactive_amt_input")
            deduction_input = st.text_input("Airline Cancellation Fee (INR):", value="600" if stage == "payout_done" else "0", key="proactive_ded_input")
            
        with col2:
            st.markdown("### 📱 Outbound Message Preview")
            preview = generate_proactive_notification(
                ticket_id=selected_ticket,
                agent_name=agent_input,
                route=route_input,
                stage=stage,
                amount=amount_input,
                deduction=deduction_input,
                channel=channel
            )
            
            with st.container(border=True):
                st.markdown(f"**Headline:** `{preview['headline']}`")
                st.markdown(f"**Channel:** `{preview['channel']}` | **Recipient:** `{preview['recipient']}`")
                st.markdown("---")
                msg_content = st.text_area("Message Content:", value=preview['message'], height=160, key="proactive_msg_preview")
                
                if st.button("🚀 Approve & Dispatch Outbound Alert", type="primary", key="proactive_dispatch_btn"):
                    log_action(f"Proactive {channel} Alert Dispatched to {agent_input} for Ticket {selected_ticket} (Milestone: {stage}).")
                    st.success(f"✅ Outbound alert dispatched to {agent_input} via {channel}!")
                    st.session_state['show_success_toast'] = True
                    st.rerun()

            
    if st.session_state.get('show_success_toast', False):
        st.success("Message sent successfully! SSOT updated.")
        st.balloons()
        st.session_state['show_success_toast'] = False
        
    if st.session_state.system_logs:
        st.markdown("---")
        
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
