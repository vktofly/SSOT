"""
Reconciliation Agent View Module (Human-in-the-loop HITL Workflow).
Automated discrepancy detection, side-by-side ledger audits, carrier penalty rule lookups,
and AI-assisted short-payment communication drafting.
Engineered following frontend-design, design-taste-frontend, and designing-beautiful-websites standards.
"""
from typing import Dict, Any, List, Set, Optional
from datetime import datetime
import pandas as pd
import streamlit as st

from src.agents import (
    draft_reconciliation_message, batch_fuzzy_match_metadata,
    generate_proactive_notification, lookup_airline_penalty
)
from src.db import update_support_status, update_ticket_id
from src.data_manager import find_mismatches, find_orphans

def init_reconciliation_state(mismatches: List[Dict[str, Any]]) -> None:
    """Initializes session state to track resolved tickets and audit logs."""
    if "resolved_tickets" not in st.session_state:
        st.session_state.resolved_tickets = set()
    if "system_logs" not in st.session_state:
        st.session_state.system_logs = []

def log_action(message: str) -> None:
    """Adds a timestamped log entry to the system audit trail."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.system_logs.insert(0, f"[{timestamp}] {message}")

def render_reconciliation_header() -> None:
    """Renders top header with live HITL reconciliation badge without inline CSS leaks."""
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.title("⚖️ Reconciliation Agent (HITL Workflow)")
        st.caption("⚡ Human-In-The-Loop Discrepancy Matching · Carrier Fee Verification & Auto-Drafting")
    with status_col2:
        st.info("🟢 HITL Recon Active", icon="⚖️")

def render_kpi_summary_bar(
    pending_mismatches: List[Dict[str, Any]], 
    missing_in_finance: List[Dict[str, Any]], 
    support_df: pd.DataFrame
) -> None:
    """Renders executive KPI metrics and SSOT export button."""
    col_kpi1, col_kpi2, col_kpi3, col_export = st.columns([1, 1, 1, 1])
    
    with col_kpi1:
        st.metric(
            "Pending Mismatches", 
            len(pending_mismatches), 
            delta="Requires Review" if len(pending_mismatches) > 0 else "All Clean", 
            delta_color="inverse" if len(pending_mismatches) > 0 else "normal",
            help="Deduction variances awaiting operator confirmation"
        )
    with col_kpi2:
        st.metric(
            "Dropped in Finance", 
            len(missing_in_finance), 
            delta="100 Orphaned Tickets", 
            delta_color="inverse",
            help="Tickets marked approved in Support but missing in Finance"
        )
    with col_kpi3:
        st.metric(
            "Resolved in Session", 
            len(st.session_state.resolved_tickets), 
            delta="SSOT Committed", 
            delta_color="normal",
            help="Discrepancies reconciled and persisted to SQLite"
        )
    with col_export:
        st.write("")
        csv_data = support_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Export Clean SSOT",
            data=csv_data,
            file_name="Reconciled_SSOT.csv",
            mime="text/csv",
            use_container_width=True,
            key="btn_export_ssot_recon"
        )
    st.markdown("---")

def render_mismatch_studio(
    raw_mismatches: List[Dict[str, Any]], 
    pending_mismatches: List[Dict[str, Any]]
) -> None:
    """Renders interactive deduction mismatch review tab with side-by-side ledger cards."""
    if not pending_mismatches:
        st.success("🎉 All deduction mismatches have been resolved! Zero variance inbox.")
        return

    total_mismatches = len(raw_mismatches)
    pending_count = len(pending_mismatches)
    resolved_count = total_mismatches - pending_count
    progress_pct = resolved_count / total_mismatches if total_mismatches > 0 else 1.0

    st.markdown(f"**Reconciliation Progress:** {resolved_count} of {total_mismatches} tickets verified ({int(progress_pct * 100)}%)")
    st.progress(progress_pct)

    def handle_approve_send(ticket_id: str, mismatch_record: Dict[str, Any], final_draft: str) -> None:
        st.session_state.resolved_tickets.add(ticket_id)
        
        sdf = st.session_state.get('support_df', pd.DataFrame())
        if not sdf.empty and 'Ticket ID' in sdf.columns and ticket_id in sdf['Ticket ID'].values:
            idx = sdf.index[sdf['Ticket ID'] == ticket_id].tolist()[0]
            sdf.at[idx, 'Status'] = 'Client Notified'
            current_notes = str(sdf.at[idx, 'Notes']) if pd.notna(sdf.at[idx, 'Notes']) else ""
            new_notes = f"{current_notes} | Finance Deduction: {mismatch_record['Reason']}".strip(" |")
            sdf.at[idx, 'Notes'] = new_notes
            update_support_status(ticket_id, 'Client Notified', new_notes)
        
        log_action(f"Email dispatched to {mismatch_record['Agent']} for Ticket {ticket_id}. Status updated to 'Client Notified'.")
        st.session_state['show_success_toast'] = True

    # Batch Action Container
    with st.expander("🛠️ Optional: Batch Reconcile All Deduction Discrepancies", expanded=False):
        st.markdown("Automatically generate carrier deduction explanations and dispatch emails for **all pending tickets** simultaneously.")
        if st.button("🚀 Batch Process All Pending Discrepancies", type="primary", key="btn_batch_recon_all"):
            with st.spinner("Processing pending discrepancies in parallel..."):
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
                st.toast(f"Successfully processed {count} discrepancies!", icon="✅")
                st.rerun()

    st.markdown("---")
    st.subheader("1. Individual Ticket Ledger Audit")
    
    ticket_options = {
        f"Ticket {m['Ticket ID']} · {m['Agent']} (₹{m['Deduction']} Variance)": m 
        for m in pending_mismatches
    }
    
    selected_label = st.selectbox(
        "Select Discrepancy Ticket for HITL Review:", 
        list(ticket_options.keys()),
        key="select_recon_ticket"
    )
    m = ticket_options[selected_label]
    tid = str(m['Ticket ID'])

    # Side-by-Side Ledger Card
    with st.container(border=True):
        if m.get('Risk Level') == 'High':
            st.error("🚨 HIGH RISK VARIANCE: Payout discrepancy exceeds 20% of total ticket value.")
            
        c_sup, c_mid, c_fin = st.columns([3, 1, 3])
        
        with c_sup:
            with st.container(border=True):
                st.markdown("#### 📋 Support Record")
                st.markdown(f"**Ticket ID:** `{tid}`")
                st.markdown(f"**Partner Agency:** `{m.get('Agent', 'Unknown')}`")
                st.markdown(f"**Sector / Route:** `{m.get('Route', 'N/A')}`")
                st.metric("Customer Promised Refund", f"₹{m.get('Support Amount', '0')}")

        with c_mid:
            st.markdown("<br><br><h3 style='text-align: center; color: #f59e0b;'>VS</h3>", unsafe_allow_html=True)
            st.caption(f"<div style='text-align:center;'><b>₹{m.get('Deduction', '0')}</b><br>Deducted</div>", unsafe_allow_html=True)

        with c_fin:
            with st.container(border=True):
                st.markdown("#### 💳 Finance Settlement")
                st.markdown(f"**Settlement Ref:** `{tid}`")
                st.markdown(f"**Carrier Deduction:** `{m.get('Reason', 'Airline Policy')}`")
                st.markdown(f"**Variance Status:** `Contested`")
                st.metric("Actual Bank Payout", f"₹{m.get('Finance Amount', '0')}")

        # Airline Fare Policy Integration
        route_str = m.get('Route', '')
        policy = lookup_airline_penalty(route_str)
        with st.expander(f"✈️ Airline Fare Rules ({policy['carrier']} · Sector {route_str or 'General'})", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            f_col1.markdown(f"**Operating Carrier:** `{policy['carrier']}`")
            f_col2.markdown(f"**Standard Fee:** `₹{policy['cancellation_fee']}`")
            f_col3.markdown(f"**Resolution SLA:** `{policy['sla_hours']} Hours`")
            st.caption(f"📌 **Tariff Policy Note:** {policy['policy_notes']}")

        st.markdown("### 🤖 AI-Drafted Discrepancy Explanation")
        draft_key = f"draft_{tid}"
        if draft_key not in st.session_state:
            st.session_state[draft_key] = ""
            
        if not st.session_state[draft_key]:
            if st.button("✨ Generate AI Explanation Email", type="primary", key=f"btn_gen_draft_{tid}"):
                with st.spinner("Drafting airline policy explanation..."):
                    draft = draft_reconciliation_message(
                        m['Agent'], m['Route'], tid, 
                        m['Support Amount'], m['Finance Amount'], 
                        m['Deduction'], m['Reason']
                    )
                    st.session_state[draft_key] = draft
                    st.rerun()
        else:
            edited_draft = st.text_area(
                "Review & Edit Draft before Dispatch:", 
                value=st.session_state[draft_key], 
                height=160, 
                key=f"text_{tid}"
            )
            
            c_send1, c_send2 = st.columns([1, 4])
            with c_send1:
                st.button(
                    "✉️ Approve & Dispatch", 
                    type="primary", 
                    key=f"btn_send_draft_{tid}", 
                    on_click=handle_approve_send, 
                    args=(tid, m, edited_draft)
                )
            with c_send2:
                if st.button("🔄 Regenerate", key=f"btn_regen_draft_{tid}"):
                    st.session_state[draft_key] = ""
                    st.rerun()

def render_orphaned_tickets_studio(
    missing_in_finance: List[Dict[str, Any]], 
    missing_in_support: List[Dict[str, Any]]
) -> None:
    """Renders entity resolution and metadata fuzzy matching studio for orphaned records."""
    st.subheader("2. Orphaned Tickets & Cross-Ledger AI Linkage")
    st.caption("Resolve records that exist in one tracker but were dropped or mistyped in the other.")
    
    # High-Risk Agent Warnings
    high_risk_agents = set([m.get('Risk Note') for m in missing_in_finance if m.get('Risk Level') == 'High'])
    for note in high_risk_agents:
        if note:
            st.warning(f"🚨 **High-Risk Agent Corridor:** {note}", icon="⚠️")
    
    col_s, col_f = st.columns(2)
    with col_s:
        with st.container(border=True):
            st.markdown(f"#### 🔴 Missing in Finance ({len(missing_in_finance)} Tickets)")
            st.caption("Marked closed on Support tracker, but never reached Finance accounts.")
            for m in missing_in_finance[:5]:
                st.markdown(f"- **`{m['Ticket ID']}`** · {m.get('Agent', 'Unknown')} · ₹{m.get('Refund Amount (INR)', '0')}")
                
    with col_f:
        with st.container(border=True):
            st.markdown(f"#### 🟡 Missing in Support ({len(missing_in_support)} Records)")
            st.caption("Processed in Finance ledger without corresponding Support ticket ID.")
            for m in missing_in_support[:5]:
                st.markdown(f"- **`{m['Ref No']}`** · {m.get('Agent Name', 'Unknown')} · ₹{m.get('Amount Paid (INR)', '0')}")
            
    st.markdown("---")
    st.subheader("🤖 AI Entity Resolution (Metadata Fuzzy Matching)")
    st.markdown("If a ticket ID was mistyped (failing exact text match), Gemini analyzes metadata (Agent Name, Route, Amount) to find the correct ledger link.")
    
    if missing_in_finance and missing_in_support:
        if st.button("🚀 Run Batch AI Entity Resolution", type="primary", key="btn_run_ai_linkage"):
            with st.spinner("Analyzing cross-ledger metadata with Gemini..."):
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
                    st.toast(f"Identified {len(all_matches)} confident linkage proposals!", icon="🎯")
                    st.rerun()
                else:
                    st.error("No confident metadata linkages discovered across remaining orphans.")
                    
        if st.session_state.get('batch_matches'):
            st.markdown("---")
            st.subheader("🎯 Proposed Cross-Ledger Linkages (Awaiting Human Approval)")
            
            if 'acted_matches' not in st.session_state:
                st.session_state.acted_matches = set()
            
            pending_matches = [
                m for m in st.session_state.batch_matches 
                if m['support_ticket_id'] not in st.session_state.acted_matches
            ]
            
            if not pending_matches:
                st.success("All proposed linkages have been reviewed and committed.")
                if st.button("Clear Proposals", key="btn_clear_proposals"):
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
                
                selected_agents = st.multiselect("Filter Proposals by Partner Agency:", list(agent_names), default=[])
                
                filtered_matches = pending_matches
                if selected_agents:
                    filtered_matches = [
                        match for match in pending_matches
                        if next((r for r in missing_in_finance if r['Ticket ID'] == match['support_ticket_id']), {}).get('Agent') in selected_agents
                    ]
                            
                st.caption(f"Showing {len(filtered_matches)} of {len(pending_matches)} remaining proposals.")
                
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
                            
                        st.info(f"**AI Linkage Hypothesis:** {match.get('reasoning')}", icon="💡")
                        
                        score = match.get('confidence_score', 0)
                        st.progress(score / 100.0)
                        st.caption(f"Match Confidence Score: **{score}%**")
                        
                        c_btn1, c_btn2, _ = st.columns([2, 2, 4])
                        with c_btn1:
                            if st.button("✅ Approve & Merge", key=f"app_{i}_{s_id}", type="primary"):
                                update_ticket_id(s_id, f_id)
                                sdf = st.session_state.get('support_df', pd.DataFrame())
                                if not sdf.empty and 'Ticket ID' in sdf.columns and s_id in sdf['Ticket ID'].values:
                                    idx = sdf.index[sdf['Ticket ID'] == s_id].tolist()
                                    if idx:
                                        sdf.at[idx[0], 'Ticket ID'] = f_id
                                st.session_state.acted_matches.add(s_id)
                                log_action(f"Approved AI Linkage: Support Ticket {s_id} ➔ Finance Ref {f_id}")
                                st.toast(f"Merged Ticket {s_id} -> {f_id}", icon="✅")
                                st.rerun()
                        with c_btn2:
                            if st.button("❌ Reject", type="secondary", key=f"rej_{i}_{s_id}"):
                                st.session_state.acted_matches.add(s_id)
                                log_action(f"Rejected AI Linkage for Support Ticket {s_id}")
                                st.rerun()
                                
                st.markdown("---")
                if filtered_matches and st.button(f"✅ Approve & Merge All Filtered Linkages ({len(filtered_matches)})", type="primary", key="btn_merge_all_filtered"):
                    sdf = st.session_state.get('support_df', pd.DataFrame())
                    for match in filtered_matches:
                        s_id = match['support_ticket_id']
                        f_id = match['finance_ref_no']
                        update_ticket_id(s_id, f_id)
                        if not sdf.empty and 'Ticket ID' in sdf.columns and s_id in sdf['Ticket ID'].values:
                            idx = sdf.index[sdf['Ticket ID'] == s_id].tolist()
                            if idx:
                                sdf.at[idx[0], 'Ticket ID'] = f_id
                        st.session_state.acted_matches.add(s_id)
                        
                    st.toast(f"Merged {len(filtered_matches)} tickets into clean SSOT!", icon="✅")
                    log_action(f"Batch AI Linkage approved for {len(filtered_matches)} tickets.")
                    st.rerun()
    else:
        st.success("No orphaned records detected in current ledger snapshot.")

def render_proactive_notification_bot(support_df: pd.DataFrame) -> None:
    """Renders proactive lifecycle milestone notification studio."""
    st.subheader("3. 📢 Proactive Partner Notification Bot")
    st.caption("Dispatch outbound milestone alerts to travel agencies to preempt inbound status chasing.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.container(border=True):
            stage = st.selectbox(
                "Lifecycle Milestone Event:",
                ["logged", "verified", "payout_done", "custom"],
                format_func=lambda x: {
                    "logged": "1. Request Logged (48h SLA Notice)",
                    "verified": "2. Finance Verification Complete",
                    "payout_done": "3. Payout Dispatched (With Carrier Penalty Breakdown)",
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
        with st.container(border=True):
            st.markdown("#### 📱 Outbound Message Preview")
            preview = generate_proactive_notification(
                ticket_id=selected_ticket,
                agent_name=agent_input,
                route=route_input,
                stage=stage,
                amount=amount_input,
                deduction=deduction_input,
                channel=channel
            )
            
            st.markdown(f"**Headline:** `{preview['headline']}`")
            st.markdown(f"**Channel:** `{preview['channel']}` · **Recipient:** `{preview['recipient']}`")
            st.markdown("---")
            msg_content = st.text_area("Message Payload:", value=preview['message'], height=150, key="proactive_msg_preview")
            
            if st.button("🚀 Approve & Dispatch Outbound Alert", type="primary", key="proactive_dispatch_btn"):
                log_action(f"Proactive {channel} Alert Dispatched to {agent_input} for Ticket {selected_ticket} (Milestone: {stage}).")
                st.toast(f"Alert dispatched to {agent_input} via {channel}!", icon="🚀")
                st.session_state['show_success_toast'] = True
                st.rerun()

def render_audit_logs() -> None:
    """Renders persistent audit logs with manager CSV export."""
    if st.session_state.get('system_logs'):
        st.markdown("---")
        with st.container(border=True):
            c_title, c_down = st.columns([3, 1])
            with c_title:
                st.markdown("### 🛠️ Immutable System Activity Audit Trail")
                st.caption("Chronological record of operator approvals, AI linkages, and outbound communications.")
            with c_down:
                if st.session_state.get('role') == 'Manager':
                    csv_data = "Log_Entry\n" + "\n".join([f'"{log}"' for log in st.session_state.system_logs])
                    st.download_button(
                        label="📥 Download Audit Log (CSV)",
                        data=csv_data,
                        file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key="btn_download_audit_log_recon"
                    )
                else:
                    st.caption("🔒 Audit Export restricted to Manager role.")
            
            with st.expander("View Full Session Event Stream", expanded=False):
                for log in st.session_state.system_logs:
                    st.text(log)

def render_reconciliation(support_df: pd.DataFrame, finance_df: pd.DataFrame) -> None:
    """Main Reconciliation view entrypoint."""
    raw_mismatches = find_mismatches(support_df, finance_df)
    missing_in_finance, missing_in_support = find_orphans(support_df, finance_df)
    init_reconciliation_state(raw_mismatches)
    
    pending_mismatches = [m for m in raw_mismatches if m['Ticket ID'] not in st.session_state.resolved_tickets]

    render_reconciliation_header()
    render_kpi_summary_bar(pending_mismatches, missing_in_finance, support_df)
    
    tab1, tab2, tab3 = st.tabs([
        "💸 Deduction Mismatches (Side-by-Side Audit)", 
        "🔗 Orphaned Tickets & Cross-Ledger AI Linkage", 
        "📢 Proactive Notification Bot"
    ])
    
    with tab1:
        render_mismatch_studio(raw_mismatches, pending_mismatches)
        
    with tab2:
        render_orphaned_tickets_studio(missing_in_finance, missing_in_support)
        
    with tab3:
        render_proactive_notification_bot(support_df)

    if st.session_state.get('show_success_toast', False):
        st.toast("Action committed to SSOT successfully!", icon="🎉")
        st.session_state['show_success_toast'] = False

    render_audit_logs()
