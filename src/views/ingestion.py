"""
Ingestion Agent View Module.
Event-driven unstructured message ingestion, PII redaction, and Human-in-the-Loop review workspace.
Features:
- Single Raw Message Playground with live entity parse
- Interactive CSV / JSON Drag-and-Drop Batch File Ingestion
- Multi-Channel filtering and batch/single processing triggers
- Staged Human-In-The-Loop review with SSOT database association
"""
import io
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st
from src.agents import parse_informal_message
from src.db import insert_support_record

DEFAULT_SIMULATED_MESSAGES: List[Dict[str, str]] = [
    {
        "id": "MSG-BRIEF-01",
        "channel": "Email",
        "text": "Hi, I cancelled booking for DEL-DXB last week and was told I'd get a refund. I haven't received anything and I don't have any reference number. Please help, my client is asking. (Agency: Peak Journeys)"
    },
    {
        "id": "MSG-BRIEF-02",
        "channel": "WhatsApp",
        "text": "Bhai refund ka kya hua? BLR-MAA wala. 2 hafte ho gaye, koi jawab nahi. (Agency: Nomad Travel)"
    },
    {
        "id": "MSG-BRIEF-03",
        "channel": "Email",
        "text": "Finance says they never received several of the refunds I closed last month. I marked them done on my side. Not sure where they went. Need status on RF-1099 expected 5400 INR."
    }
]

def init_ingestion_state() -> None:
    """Initializes and normalizes session state containers for ingestion."""
    if "webhook_inbox_items" not in st.session_state:
        st.session_state.webhook_inbox_items = [dict(item) for item in DEFAULT_SIMULATED_MESSAGES]
    if "review_queue" not in st.session_state:
        st.session_state.review_queue = []
    if "processed_today" not in st.session_state:
        st.session_state.processed_today = 0
    if "channel_filter" not in st.session_state:
        st.session_state.channel_filter = "All"
    if "discard_confirm_idx" not in st.session_state:
        st.session_state.discard_confirm_idx = None

def render_ingestion_header() -> None:
    """Renders top header with live listener badge and telemetry KPI cards."""
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.markdown('<div class="dash-section-label">Intake Pipeline</div>', unsafe_allow_html=True)
        st.title("Ingestion Agent (Event-Driven)")
        st.caption("Live Webhook Ingestion · Automated PII Redaction & Structured Entity Extraction")
    with status_col2:
        st.markdown(
            '<div style="text-align: right; padding-top: 18px;">'
            '<span class="status-pill" style="background: rgba(52,168,83,0.1); border: 1px solid rgba(52,168,83,0.3); color: #34a853;">'
            '● Active '
            '<span class="status-dot" style="background: #34a853;"></span>'
            'Webhook Active'
            '</span>'
            '</div>',
            unsafe_allow_html=True
        )
    
    col1, col2, col3 = st.columns(3)
    inbox_len = len(st.session_state.webhook_inbox_items)
    review_len = len(st.session_state.review_queue)
    
    col1.metric("Live Webhook Inbox", inbox_len, delta="Incoming Stream", delta_color="off")
    col2.metric("Pending Human Review", review_len, delta="Awaiting Approval" if review_len > 0 else "Clear", delta_color="inverse" if review_len > 0 else "normal")
    col3.metric("Processed in Session", st.session_state.processed_today, delta="Committed to SSOT", delta_color="normal")
    st.markdown("---")

def render_payload_injector_tabs() -> None:
    """Renders tabbed custom playground for raw manual entry and drag-and-drop batch upload."""
    st.subheader("Ingestion Testing & Batch Upload Studio")
    tab_single, tab_batch = st.tabs(["Single Message Playground", "Drag-and-Drop Batch File Ingestion"])
    
    with tab_single:
        st.caption("Inject informal messages across multiple communication channels or run instant AI extraction tests.")
        c1, c2 = st.columns([2, 1])
        with c1:
            custom_text = st.text_area(
                "Inbound Raw Text",
                value="",
                placeholder="e.g., Passenger Rohit cancelled BLR-GOI flight RF-1082, expecting full refund of 4200 INR via WhatsApp.",
                help="Enter any informal message to test PII masking and structured entity parsing",
                key="single_raw_input"
            )
        with c2:
            custom_channel = st.selectbox(
                "Source Channel", 
                ["WhatsApp", "Email", "Phone", "Portal", "OTA API"],
                key="single_chan_select"
            )
            preview_btn = st.button("Test Live Parse", use_container_width=True, key="btn_live_parse")
            inject_btn = st.button("Inject to Live Queue", type="primary", use_container_width=True, key="btn_inject_single")

        if preview_btn and custom_text.strip():
            with st.spinner("Executing LLM entity extraction & PII guardrails..."):
                extracted = parse_informal_message(custom_text)
                extracted["source_channel"] = custom_channel
                st.success("Extraction Complete")
                st.json(extracted)

        if inject_btn and custom_text.strip():
            new_id = f"MSG-{1000 + len(st.session_state.webhook_inbox_items) + st.session_state.processed_today + 1}"
            st.session_state.webhook_inbox_items.append({
                "id": new_id,
                "channel": custom_channel,
                "text": custom_text.strip()
            })
            st.toast(f"Injected payload {new_id} to queue.")
            st.rerun()

    with tab_batch:
        st.caption("Upload `.csv` or `.json` files containing batch ticket payloads or customer communication dumps.")
        uploaded_file = st.file_uploader(
            "Upload Batch Payloads (CSV / JSON)", 
            type=["csv", "json"], 
            help="CSV must have 'text' or 'message' column. JSON should be an array of objects or message strings."
        )
        
        if uploaded_file is not None:
            parsed_batch_items: List[Dict[str, str]] = []
            try:
                if uploaded_file.name.endswith(".csv"):
                    df_upload = pd.read_csv(uploaded_file)
                    text_col = next((c for c in df_upload.columns if c.lower() in ["text", "message", "raw_text", "body", "notes"]), None)
                    if not text_col:
                        st.error(f"CSV requires a 'text' or 'message' column. Found columns: {list(df_upload.columns)}")
                    else:
                        chan_col = next((c for c in df_upload.columns if c.lower() in ["channel", "source"]), None)
                        for i, row in df_upload.iterrows():
                            raw_msg = str(row[text_col]).strip()
                            if raw_msg and raw_msg.lower() != "nan":
                                c_val = str(row[chan_col]) if chan_col and str(row[chan_col]).lower() != "nan" else "OTA API"
                                item_id = f"CSV-{1000 + len(parsed_batch_items) + 1}"
                                parsed_batch_items.append({
                                    "id": item_id,
                                    "channel": c_val,
                                    "text": raw_msg
                                })
                elif uploaded_file.name.endswith(".json"):
                    json_data = json.load(uploaded_file)
                    if isinstance(json_data, list):
                        for idx, entry in enumerate(json_data):
                            if isinstance(entry, dict):
                                msg = entry.get("text") or entry.get("message") or str(entry)
                                chan = entry.get("channel") or "JSON Batch"
                                item_id = entry.get("id") or f"JSON-{1000 + idx + 1}"
                                parsed_batch_items.append({"id": str(item_id), "channel": str(chan), "text": str(msg)})
                            elif isinstance(entry, str):
                                parsed_batch_items.append({"id": f"JSON-{1000 + idx + 1}", "channel": "JSON Batch", "text": entry})
                    else:
                        st.error("JSON must contain a top-level array of message objects or strings.")
                        
                if parsed_batch_items:
                    st.success(f"Successfully validated **{len(parsed_batch_items)}** records from `{uploaded_file.name}`.")
                    st.dataframe(pd.DataFrame(parsed_batch_items), use_container_width=True, height=180)
                    
                    b_col1, _ = st.columns([2, 3])
                    with b_col1:
                        if st.button(f"Enqueue All {len(parsed_batch_items)} Records", type="primary", use_container_width=True, key="btn_enqueue_batch"):
                            st.session_state.webhook_inbox_items.extend(parsed_batch_items)
                            st.toast(f"Ingested {len(parsed_batch_items)} records from {uploaded_file.name}.")
                            st.rerun()
            except Exception as ex:
                st.error(f"Error parsing uploaded file: {str(ex)}")
    st.markdown("---")

def render_incoming_queue() -> None:
    """Renders filtered webhook inbox with batch and single parse triggers."""
    q_col1, q_col2 = st.columns([3, 1])
    with q_col1:
        st.subheader("Incoming Unstructured Queue")
    with q_col2:
        channels = ["All", "WhatsApp", "Email", "Portal", "Phone", "OTA API", "JSON Batch"]
        current_selection = st.session_state.channel_filter
        if current_selection not in channels:
            channels.append(current_selection)
        selected_chan = st.selectbox("Filter Channel", channels, index=channels.index(current_selection))
        if selected_chan != st.session_state.channel_filter:
            st.session_state.channel_filter = selected_chan
            st.rerun()

    items = st.session_state.webhook_inbox_items
    if st.session_state.channel_filter != "All":
        filtered_items = [item for item in items if item.get("channel") == st.session_state.channel_filter]
    else:
        filtered_items = items

    if not items:
        with st.container(border=True):
            st.success("**Inbox Zero**: All incoming webhook events have been processed.")
            st.caption("New messages received from travel agencies or direct travelers will appear here automatically.")
            if st.button("Inject Default Test Payloads", key="reinject_btn"):
                st.session_state.webhook_inbox_items = [dict(item) for item in DEFAULT_SIMULATED_MESSAGES]
                st.rerun()
        return

    if not filtered_items:
        st.info(f"No incoming messages matching filter **{st.session_state.channel_filter}**.")
        return

    with st.container(border=True):
        for idx, item in enumerate(filtered_items):
            msg_col, chan_col, btn_col = st.columns([4, 1.2, 1.2])
            with msg_col:
                st.markdown(f"**{item.get('id', 'MSG')}:** *\"{item.get('text', '')}\"*")
            with chan_col:
                st.caption(f"Channel: `{item.get('channel', 'Unknown')}`")
            with btn_col:
                if st.button("Parse Entity", key=f"ingest_single_{item.get('id')}", use_container_width=True):
                    with st.spinner("Extracting..."):
                        result = parse_informal_message(item.get("text", ""))
                        result["source_channel"] = item.get("channel", "Unknown")
                        result["inbound_id"] = item.get("id")
                        st.session_state.review_queue.append(result)
                        st.session_state.webhook_inbox_items.remove(item)
                        st.toast(f"Parsed {item.get('id')} into verification queue.")
                        st.rerun()
            if idx < len(filtered_items) - 1:
                st.divider()

    c_batch, _ = st.columns([2, 3])
    with c_batch:
        if st.button("Batch Parse Visible Messages", type="primary", use_container_width=True):
            with st.spinner(f"Processing batch of {len(filtered_items)} messages with PII redaction..."):
                for item in list(filtered_items):
                    result = parse_informal_message(item.get("text", ""))
                    result["source_channel"] = item.get("channel", "Unknown")
                    result["inbound_id"] = item.get("id")
                    st.session_state.review_queue.append(result)
                    st.session_state.webhook_inbox_items.remove(item)
                st.toast(f"Batch parsed {len(filtered_items)} messages successfully.")
                st.rerun()

def render_review_workspace() -> None:
    """Renders the Human-In-The-Loop review and database commit interface."""
    st.markdown("---")
    st.subheader("Human-In-The-Loop Verification Queue")
    
    if not st.session_state.review_queue:
        with st.container(border=True):
            st.info("**Verification Queue Empty**: No parsed tickets currently awaiting review.")
            st.caption("Parse inbound messages from the queue above to stage tickets for HITL validation.")
        return

    low_confidence = any(r.get("confidence_score", 100) < 80 for r in st.session_state.review_queue)
    if low_confidence:
        st.warning("**Confidence Warning**: One or more records flagged low AI extraction confidence (< 80%). Verify fields before commit.")

    ticket_options = {
        f"Item #{i+1} | {r.get('agent_name', 'Unknown Agency')} | Route: {r.get('route', 'Unknown')} ({r.get('confidence_score', 85)}% Conf)": i 
        for i, r in enumerate(st.session_state.review_queue)
    }
    
    selected_label = st.selectbox("Select ticket to inspect:", list(ticket_options.keys()), key="ingest_select")
    selected_idx = ticket_options[selected_label]
    r = st.session_state.review_queue[selected_idx]
    
    with st.container(border=True):
        col_hdr1, col_hdr2 = st.columns([2, 1])
        with col_hdr1:
            st.markdown(f"### Staged Ticket #{selected_idx + 1}")
        
        conf_score = int(r.get("confidence_score", 85))
        with col_hdr2:
            st.progress(conf_score / 100.0, text=f"AI Confidence: {conf_score}%")
        
        st.caption("PII automatically masked at ingestion boundary before LLM processing.")
        
        # Database pre-match lookup
        support_db = st.session_state.get('support_df', pd.DataFrame())
        db_record = None
        ref_id_val = r.get("reference_id") or ""
        agent_val = r.get("agent_name") or ""
        route_val = r.get("route") or ""
        
        if ref_id_val and 'Ticket ID' in support_db.columns:
            matches = support_db[support_db['Ticket ID'] == ref_id_val]
            if not matches.empty:
                db_record = matches.iloc[0]
        elif agent_val and route_val and 'Agent' in support_db.columns and 'Route' in support_db.columns:
            matches = support_db[(support_db['Agent'].str.contains(agent_val, case=False, na=False)) & 
                                 (support_db['Route'].str.contains(route_val, case=False, na=False))]
            if not matches.empty:
                db_record = matches.iloc[0]
        
        # Logical fieldsets
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown("**Partner & Route Identity**")
                new_agent = st.text_input(
                    "Agency / Partner Name", 
                    value=agent_val, 
                    help="Travel agency name or passenger identifier",
                    key=f"agent_{selected_idx}"
                )
                new_route = st.text_input(
                    "Travel Route (Origin-Dest)", 
                    value=route_val, 
                    help="Airport IATA codes (e.g. DEL-DXB, BOM-LHR)",
                    key=f"route_{selected_idx}"
                )
                new_ref_id = st.text_input(
                    "Booking Reference / PNR", 
                    value=ref_id_val, 
                    help="Existing reference or ticket number if available",
                    key=f"ref_id_{selected_idx}"
                )
                channel_opts = ["WhatsApp", "Email", "Phone", "Portal", "OTA API", "JSON Batch", "Unknown"]
                curr_chan = r.get("source_channel", "WhatsApp")
                if curr_chan not in channel_opts:
                    channel_opts.append(curr_chan)
                new_channel = st.selectbox(
                    "Inbound Channel", 
                    options=channel_opts, 
                    index=channel_opts.index(curr_chan), 
                    help="Source communication channel",
                    key=f"channel_{selected_idx}"
                )
            
        with col2:
            with st.container(border=True):
                st.markdown("**Financial & Priority Classification**")
                intent_opts = ["status_update", "new_refund", "other"]
                curr_intent = r.get("intent", "status_update")
                if curr_intent not in intent_opts:
                    intent_opts.append(curr_intent)
                new_intent = st.selectbox(
                    "Identified Intent", 
                    options=intent_opts, 
                    index=intent_opts.index(curr_intent), 
                    help="Primary goal extracted from message text",
                    key=f"intent_{selected_idx}"
                )
                urgency_opts = ["High", "Medium", "Low", "Unknown"]
                curr_urgency = r.get("urgency", "Medium")
                if curr_urgency not in urgency_opts:
                    urgency_opts.append(curr_urgency)
                new_urgency = st.selectbox(
                    "Urgency Classification", 
                    options=urgency_opts, 
                    index=urgency_opts.index(curr_urgency), 
                    help="Priority level for support team SLA tracking",
                    key=f"urgency_{selected_idx}"
                )
                refund_val = str(r.get("expected_refund_amount") or "0")
                new_refund = st.text_input(
                    "Expected Refund Amount (₹)", 
                    value=refund_val, 
                    help="Claimed refund amount in INR",
                    key=f"refund_{selected_idx}"
                )
                new_wait = st.text_input(
                    "Reported Wait Duration", 
                    value=r.get("elapsed_wait_time") or "", 
                    help="Time elapsed since original customer request",
                    key=f"wait_{selected_idx}"
                )
            
        st.markdown("---")
        
        with st.expander("SSOT Database Association", expanded=True):
            if db_record is not None:
                st.success("Prior record located in SSOT database. Update will attach to existing history.")
                c_db1, c_db2 = st.columns(2)
                with c_db1:
                    st.text_input("Logged Request Date", value=str(db_record.get('Request Date', '')), disabled=True)
                    st.text_input("Current SSOT Status", value=str(db_record.get('Status', '')), disabled=True)
                with c_db2:
                    st.text_input("Existing Notes", value=str(db_record.get('Notes', '')), disabled=True)
                    st.text_input("Owner Department", value=str(db_record.get('Handled By', '')), disabled=True)
            else:
                st.info("No previous record found. A new SSOT entry will be registered upon approval.")
                
        st.markdown("---")
        
        btn_col1, btn_col2, _ = st.columns([2, 1.5, 2.5])
        with btn_col1:
            if st.button("Approve & Commit to SSOT", type="primary", key=f"approve_{selected_idx}", use_container_width=True):
                support_df = st.session_state.support_df
                
                new_record: Dict[str, Any] = {
                    'Ticket ID': new_ref_id if new_ref_id else f"RF-{1000 + len(support_df)}",
                    'Agent': new_agent or "Direct Traveler",
                    'Route': new_route or "General",
                    'Refund Amount (INR)': new_refund,
                    'Request Date': datetime.now().strftime("%d-%b-%Y"),
                    'Last Updated': datetime.now().strftime("%d-%b-%Y"),
                    'Status': 'Processing',
                    'Handled By': 'AI Ingestion',
                    'Channel': new_channel,
                    'Notes': f"Intent: {new_intent}, Urgency: {new_urgency}"
                }
                
                target_id = new_record['Ticket ID']
                if target_id and 'Ticket ID' in support_df.columns and target_id in support_df['Ticket ID'].values:
                    idx = support_df.index[support_df['Ticket ID'] == target_id].tolist()[0]
                    for k, v in new_record.items():
                        support_df.at[idx, k] = v
                else:
                    new_df = pd.DataFrame([new_record])
                    st.session_state.support_df = pd.concat([support_df, new_df], ignore_index=True)
                
                insert_support_record(new_record)
                st.session_state.processed_today += 1
                st.session_state.review_queue.pop(selected_idx)
                st.session_state.discard_confirm_idx = None
                st.toast("Ticket successfully committed to SSOT database.")
                st.rerun()
                
        with btn_col2:
            if st.session_state.discard_confirm_idx == selected_idx:
                if st.button("Confirm Discard", key=f"confirm_discard_{selected_idx}", type="secondary", use_container_width=True):
                    st.session_state.review_queue.pop(selected_idx)
                    st.session_state.discard_confirm_idx = None
                    st.toast("Item discarded from queue.")
                    st.rerun()
            else:
                if st.button("Discard Item", key=f"discard_{selected_idx}", use_container_width=True):
                    st.session_state.discard_confirm_idx = selected_idx
                    st.rerun()

def render_ingestion() -> None:
    """Main Ingestion Agent view entrypoint."""
    init_ingestion_state()
    render_ingestion_header()
    render_payload_injector_tabs()
    render_incoming_queue()
    render_review_workspace()
