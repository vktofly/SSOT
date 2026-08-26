"""
Reconciliation Agent View Module (Human-in-the-loop HITL Workflow).
Automated discrepancy detection, side-by-side ledger audits, carrier penalty rule lookups,
and AI-assisted short-payment communication drafting.
Decoupled to communicate entirely via REST API Client.
"""
from typing import Dict, Any, List, Set, Optional
from datetime import datetime
import pandas as pd
import streamlit as st

from src.api_client import api_client


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
        st.markdown('<div class="dash-section-label">Discrepancy Engine</div>', unsafe_allow_html=True)
        st.title("Reconciliation Agent (HITL Workflow)")
        st.caption("Human-In-The-Loop Discrepancy Matching · Carrier Fee Verification & Auto-Drafting")
    with status_col2:
        st.markdown(
            '<div style="text-align: right; padding-top: 18px;">'
            '<span class="status-pill" style="background: rgba(52,168,83,0.1); border: 1px solid rgba(52,168,83,0.3); color: #34a853;">'
            '● Active '
            '<span class="status-dot" style="background: #34a853;"></span>'
            'HITL Recon Active'
            '</span>'
            '</div>',
            unsafe_allow_html=True
        )


def render_kpi_summary_bar(
    pending_mismatches: List[Dict[str, Any]], 
    missing_in_finance: List[Dict[str, Any]], 
    support_df: Optional[pd.DataFrame] = None
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
            delta=f"{len(missing_in_finance)} Orphaned Tickets", 
            delta_color="inverse" if len(missing_in_finance) > 0 else "normal",
            help="Tickets marked approved in Support but missing in Finance"
        )
    with col_kpi3:
        st.metric(
            "Resolved in Session", 
            len(st.session_state.resolved_tickets), 
            delta="SSOT Committed", 
            delta_color="normal",
            help="Discrepancies reconciled and persisted to backend"
        )
    with col_export:
        st.write("")
        if support_df is not None and not support_df.empty:
            csv_data = support_df.to_csv(index=False).encode('utf-8')
        else:
            tickets = api_client.get_support_tickets()
            csv_data = pd.DataFrame(tickets).to_csv(index=False).encode('utf-8') if tickets else b"Ticket ID,Agent,Status\n"
        st.download_button(
            label="Export Clean SSOT",
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
        st.success("All deduction mismatches have been resolved. Zero variance inbox.")
        return

    total_mismatches = len(raw_mismatches)
    pending_count = len(pending_mismatches)
    resolved_count = total_mismatches - pending_count
    progress_pct = resolved_count / total_mismatches if total_mismatches > 0 else 1.0

    st.markdown(f"**Reconciliation Progress:** {resolved_count} of {total_mismatches} tickets verified ({int(progress_pct * 100)}%)")
    st.progress(progress_pct)

    def handle_approve_send(ticket_id: str, mismatch_record: Dict[str, Any], final_draft: str) -> None:
        st.session_state.resolved_tickets.add(ticket_id)
        
        reason = mismatch_record.get('reason') or mismatch_record.get('Reason', 'Tariff deduction')
        new_notes = f"Finance Deduction: {reason}"
        try:
            api_client.resolve_mismatch(
                ticket_id=ticket_id,
                new_status="Client Notified",
                notes=new_notes,
                resolution_type="Accept Deduction",
                send_communication=True,
                communication_draft=final_draft
            )
        except Exception as err:
            st.error(f"Error resolving mismatch: {err}")
        
        agent_name = mismatch_record.get('agent') or mismatch_record.get('Agent', 'Partner')
        log_action(f"Email dispatched to {agent_name} for Ticket {ticket_id}. Status updated to 'Client Notified'.")
        st.session_state['show_success_toast'] = True

    # Batch Action Container
    with st.expander("Optional: Batch Reconcile All Deduction Discrepancies", expanded=False):
        st.markdown("Automatically generate carrier deduction explanations and dispatch emails for **all pending tickets** simultaneously.")
        if st.button("Batch Process All Pending Discrepancies", type="primary", key="btn_batch_recon_all"):
            with st.spinner("Processing pending discrepancies in parallel..."):
                count = 0
                for pending_m in pending_mismatches:
                    p_tid = str(pending_m.get('ticket_id') or pending_m.get('Ticket ID'))
                    draft = api_client.draft_reconciliation_explanation(pending_m)
                    handle_approve_send(p_tid, pending_m, draft)
                    count += 1
                st.toast(f"Successfully processed {count} discrepancies.")
                st.rerun()

    st.markdown("---")
    st.subheader("Individual Ticket Ledger Audit")
    
    ticket_options = {}
    for m in pending_mismatches:
        t_id = m.get('ticket_id') or m.get('Ticket ID')
        agent = m.get('agent') or m.get('Agent')
        ded = m.get('deduction') or m.get('Deduction')
        label = f"Ticket {t_id} · {agent} (₹{ded} Variance)"
        ticket_options[label] = m
    
    selected_label = st.selectbox(
        "Select Discrepancy Ticket for HITL Review:", 
        list(ticket_options.keys()),
        key="select_recon_ticket"
    )
    m = ticket_options[selected_label]
    tid = str(m.get('ticket_id') or m.get('Ticket ID'))

    # Side-by-Side Ledger Card
    with st.container(border=True):
        risk_lvl = m.get('risk_level') or m.get('Risk Level')
        if risk_lvl == 'High':
            st.error("HIGH RISK VARIANCE: Payout discrepancy exceeds 20% of total ticket value.")
            
        c_sup, c_mid, c_fin = st.columns([3, 1, 3])
        
        with c_sup:
            with st.container(border=True):
                st.markdown("#### Support Record")
                st.markdown(f"**Ticket ID:** `{tid}`")
                st.markdown(f"**Partner Agency:** `{m.get('agent') or m.get('Agent', 'Unknown')}`")
                st.markdown(f"**Sector / Route:** `{m.get('route') or m.get('Route', 'N/A')}`")
                st.metric("Customer Promised Refund", f"₹{m.get('support_amount') or m.get('Support Amount', '0')}")

        with c_mid:
            st.markdown("<br><br><h3 style='text-align: center; color: var(--google-text-secondary);'>VS</h3>", unsafe_allow_html=True)
            st.caption(f"<div style='text-align:center;'><b>₹{m.get('deduction') or m.get('Deduction', '0')}</b><br>Deducted</div>", unsafe_allow_html=True)

        with c_fin:
            with st.container(border=True):
                st.markdown("#### Finance Settlement")
                st.markdown(f"**Settlement Ref:** `{tid}`")
                st.markdown(f"**Carrier Deduction:** `{m.get('reason') or m.get('Reason', 'Airline Policy')}`")
                st.markdown(f"**Variance Status:** `Contested`")
                st.metric("Actual Bank Payout", f"₹{m.get('finance_amount') or m.get('Finance Amount', '0')}")

        # Airline Fare Policy Integration
        route_str = m.get('route') or m.get('Route', '')
        policy = api_client.lookup_airline_policy(route_str)
        with st.expander(f"Airline Fare Rules ({policy.get('carrier', 'Carrier')} · Sector {route_str or 'General'})", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            f_col1.markdown(f"**Operating Carrier:** `{policy.get('carrier')}`")
            f_col2.markdown(f"**Standard Fee:** `₹{policy.get('cancellation_fee')}`")
            f_col3.markdown(f"**Resolution SLA:** `{policy.get('sla_hours')} Hours`")
            st.caption(f"**Tariff Policy Note:** {policy.get('policy_notes')}")

        st.markdown("### AI-Drafted Discrepancy Explanation")
        draft_key = f"draft_{tid}"
        if draft_key not in st.session_state:
            st.session_state[draft_key] = ""
            
        if not st.session_state[draft_key]:
            if st.button("Generate AI Explanation Email", type="primary", key=f"btn_gen_draft_{tid}"):
                with st.spinner("Drafting airline policy explanation..."):
                    draft = api_client.draft_reconciliation_explanation(m)
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
                    "Approve & Dispatch", 
                    type="primary", 
                    key=f"btn_send_draft_{tid}", 
                    on_click=handle_approve_send, 
                    args=(tid, m, edited_draft)
                )
            with c_send2:
                if st.button("Regenerate", key=f"btn_regen_draft_{tid}"):
                    st.session_state[draft_key] = ""
                    st.rerun()


def render_orphaned_tickets_studio(
    missing_in_finance: List[Dict[str, Any]], 
    missing_in_support: List[Dict[str, Any]]
) -> None:
    """Renders entity resolution and metadata fuzzy matching studio for orphaned records."""
    st.subheader("Orphaned Tickets & Cross-Ledger AI Linkage")
    st.caption("Resolve records that exist in one tracker but were dropped or mistyped in the other.")
    
    col_orph1, col_orph2 = st.columns([3, 1])
    with col_orph2:
        if st.button("Parse Missing Emails (Ingestion)", use_container_width=True, key="btn_jump_ingest"):
            if "pages" in st.session_state and "ingestion" in st.session_state.pages:
                st.switch_page(st.session_state.pages["ingestion"])
    
    with col_orph1:
        # High-Risk Agent Warnings
        high_risk_agents = set([m.get('risk_note') or m.get('Risk Note') for m in missing_in_finance if (m.get('risk_level') or m.get('Risk Level')) == 'High'])
        for note in high_risk_agents:
            if note:
                st.warning(f"**High-Risk Agent Corridor:** {note}")
    
    col_s, col_f = st.columns(2)
    with col_s:
        with st.container(border=True):
            st.markdown(f"#### Missing in Finance ({len(missing_in_finance)} Tickets)")
            st.caption("Marked closed on Support tracker, but never reached Finance accounts.")
            for m in missing_in_finance[:5]:
                t_id = m.get('ticket_id') or m.get('Ticket ID')
                ag = m.get('agent') or m.get('Agent', 'Unknown')
                amt = m.get('amount') or m.get('Refund Amount (INR)', '0')
                st.markdown(f"- **`{t_id}`** · {ag} · ₹{amt}")
                
    with col_f:
        with st.container(border=True):
            st.markdown(f"#### Missing in Support ({len(missing_in_support)} Records)")
            st.caption("Processed in Finance ledger without corresponding Support ticket ID.")
            for m in missing_in_support[:5]:
                ref = m.get('ref_no') or m.get('Ref No')
                ag = m.get('agent') or m.get('Agent Name', 'Unknown')
                amt = m.get('amount') or m.get('Amount Paid (INR)', '0')
                st.markdown(f"- **`{ref}`** · {ag} · ₹{amt}")
            
    st.markdown("---")
    st.subheader("AI Entity Resolution (Metadata Fuzzy Matching)")
    st.markdown("If a ticket ID was mistyped (failing exact text match), metadata matching discovers candidate linkages.")
    
    if missing_in_finance and missing_in_support:
        if st.button("Run Batch AI Entity Resolution", type="primary", key="btn_run_ai_linkage"):
            with st.spinner("Analyzing cross-ledger metadata..."):
                matches = api_client.fuzzy_match_orphans()
                if matches:
                    st.session_state.batch_matches = matches
                    st.toast(f"Identified {len(matches)} confident linkage proposals.")
                    st.rerun()
                else:
                    st.error("No confident metadata linkages discovered across remaining orphans.")
                    
        if st.session_state.get('batch_matches'):
            st.markdown("---")
            st.subheader("Proposed Cross-Ledger Linkages (Awaiting Human Approval)")
            
            if 'acted_matches' not in st.session_state:
                st.session_state.acted_matches = set()
            
            pending_matches = [
                m for m in st.session_state.batch_matches 
                if m.get('support_ticket_id') not in st.session_state.acted_matches
            ]
            
            if not pending_matches:
                st.success("All proposed linkages have been reviewed and committed.")
                if st.button("Clear Proposals", key="btn_clear_proposals"):
                    st.session_state.batch_matches = None
                    st.session_state.acted_matches.clear()
                    st.rerun()
            else:
                for i, match in enumerate(pending_matches):
                    s_id = match.get('support_ticket_id')
                    f_id = match.get('finance_ref_no')
                    
                    with st.container(border=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Support Ticket (Missing in Finance):** `{s_id}`")
                            st.write(f"Agent: {match.get('agent', 'Unknown')}")
                        with col2:
                            st.markdown(f"**Proposed Finance Record:** `{f_id}`")
                            st.write(f"Rationale: {match.get('match_rationale')}")
                            
                        score = int(float(match.get('confidence_score', 0)) * 100)
                        st.progress(score / 100.0)
                        st.caption(f"Match Confidence Score: **{score}%**")
                        
                        c_btn1, c_btn2, _ = st.columns([2, 2, 4])
                        with c_btn1:
                            if st.button("Approve & Merge", key=f"app_{i}_{s_id}", type="primary"):
                                api_client.merge_orphan_linkage(s_id, f_id)
                                st.session_state.acted_matches.add(s_id)
                                log_action(f"Approved AI Linkage: Support Ticket {s_id} -> Finance Ref {f_id}")
                                st.toast(f"Merged Ticket {s_id} -> {f_id}")
                                st.rerun()
                        with c_btn2:
                            if st.button("Reject", type="secondary", key=f"rej_{i}_{s_id}"):
                                st.session_state.acted_matches.add(s_id)
                                log_action(f"Rejected AI Linkage for Support Ticket {s_id}")
                                st.rerun()
    else:
        st.success("No orphaned records detected in current ledger snapshot.")


def render_proactive_notification_bot(support_df: Optional[pd.DataFrame] = None) -> None:
    """Renders proactive lifecycle milestone notification studio."""
    st.subheader("Proactive Partner Notification Bot")
    st.caption("Dispatch outbound milestone alerts to travel agencies to preempt inbound status chasing.")
    
    tickets_list = []
    if support_df is not None and not support_df.empty and 'Ticket ID' in support_df.columns:
        tickets_list = support_df['Ticket ID'].dropna().astype(str).tolist()
    else:
        raw_tickets = api_client.get_support_tickets(limit=50)
        tickets_list = [t['ticket_id'] for t in raw_tickets if 'ticket_id' in t]

    col1, col2 = st.columns([1, 1])
    with col1:
        with st.container(border=True):
            stage = st.selectbox(
                "Lifecycle Milestone Event:",
                ["logged", "verified", "payout_done", "custom"],
                format_func=lambda x: {
                    "logged": "Request Logged (48h SLA Notice)",
                    "verified": "Finance Verification Complete",
                    "payout_done": "Payout Dispatched (With Carrier Penalty Breakdown)",
                    "custom": "Custom Active Review Notice"
                }[x],
                key="proactive_stage_select"
            )
            
            channel = st.radio("Dispatch Channel:", ["WhatsApp", "Email"], horizontal=True, key="proactive_channel_radio")
            selected_ticket = st.selectbox("Select Associated Ticket:", tickets_list[:50], key="proactive_ticket_select") if tickets_list else "RF-1001"
            
            agent_input = st.text_input("Travel Agent / Agency:", value="Peak Journeys", key="proactive_agent_input")
            route_input = st.text_input("Travel Route / Sector:", value="DEL-DXB", key="proactive_route_input")
            amount_input = st.text_input("Refund Amount (INR):", value="5400", key="proactive_amt_input")
            deduction_input = st.text_input("Airline Cancellation Fee (INR):", value="600" if stage == "payout_done" else "0", key="proactive_ded_input")
            
    with col2:
        with st.container(border=True):
            st.markdown("#### Outbound Message Preview")
            preview = api_client.send_proactive_alert(
                ticket_id=selected_ticket,
                agent_name=agent_input,
                route=route_input,
                stage=stage,
                amount=amount_input,
                deduction=deduction_input,
                channel=channel
            )
            
            st.markdown(f"**Delivery Channel:** `{channel}`")
            st.text_area("Live Message Body:", value=preview.get("message", ""), height=150, key="proactive_preview_area")
            
            if st.button(f"Dispatch Outbound {channel} Alert", type="primary", key="btn_dispatch_proactive"):
                log_action(f"Dispatched {channel} proactive alert to {agent_input} for Ticket {selected_ticket}.")
                st.toast(f"Outbound {channel} alert sent successfully.")


def render_audit_logs() -> None:
    """Renders persistent audit logs with manager CSV export."""
    if st.session_state.get('system_logs'):
        st.markdown("---")
        with st.container(border=True):
            c_title, c_down = st.columns([3, 1])
            with c_title:
                st.markdown("### Immutable System Activity Audit Trail")
                st.caption("Chronological record of operator approvals, AI linkages, and outbound communications.")
            with c_down:
                if st.session_state.get('role') == 'Manager':
                    csv_data = "Log_Entry\n" + "\n".join([f'"{log}"' for log in st.session_state.system_logs])
                    st.download_button(
                        label="Download Audit Log (CSV)",
                        data=csv_data,
                        file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key="btn_download_audit_log_recon"
                    )
                else:
                    st.caption("Audit Export restricted to Manager role.")
            
            with st.expander("View Full Session Event Stream", expanded=False):
                for log in st.session_state.system_logs:
                    st.text(log)


def render_reconciliation(
    support_df: Optional[pd.DataFrame] = None,
    finance_df: Optional[pd.DataFrame] = None
) -> None:
    """Main Reconciliation view entrypoint."""
    raw_mismatches = api_client.get_reconciliation_mismatches()
    orphans = api_client.get_reconciliation_orphans()
    missing_in_finance = orphans.get("missing_in_finance", [])
    missing_in_support = orphans.get("missing_in_support", [])

    init_reconciliation_state(raw_mismatches)
    
    pending_mismatches = [
        m for m in raw_mismatches 
        if (m.get('ticket_id') or m.get('Ticket ID')) not in st.session_state.resolved_tickets
    ]

    render_reconciliation_header()
    render_kpi_summary_bar(pending_mismatches, missing_in_finance, support_df)
    
    tab1, tab2, tab3 = st.tabs([
        "Deduction Mismatches (Side-by-Side Audit)", 
        "Orphaned Tickets & Cross-Ledger AI Linkage", 
        "Proactive Notification Bot"
    ])
    
    with tab1:
        render_mismatch_studio(raw_mismatches, pending_mismatches)
        
    with tab2:
        render_orphaned_tickets_studio(missing_in_finance, missing_in_support)
        
    with tab3:
        render_proactive_notification_bot(support_df)

    if st.session_state.get('show_success_toast', False):
        st.toast("Action committed to SSOT successfully.")
        st.session_state['show_success_toast'] = False

    render_audit_logs()
