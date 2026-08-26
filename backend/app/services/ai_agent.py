import re
import time
from typing import Dict, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
# from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

# from backend.app.config import settings

class EscalationState(TypedDict):
    raw_message: str
    channel: str
    agency_name: Optional[str]
    agency_tier: str
    
    # Extraction output
    reference_id: Optional[str]
    route: Optional[str]
    intent: Optional[str]
    expected_amount: Optional[float]
    missing_reference: bool
    confidence_score: int
    
    # Routing & Sentiment
    priority_rank: str
    urgency_level: str
    hitl_required: bool
    hitl_reason: Optional[str]
    
    # SSOT & Policy
    ssot_status: Optional[Dict[str, Any]]
    policy_fee: Optional[float]
    
    # Response
    draft_response: str
    guardrail_passed: bool
    
    # Audit Trace
    audit_trace: list[Dict[str, Any]]

# RAG Knowledge Base
AIRLINE_POLICY_KB = {
    "DEL-DXB": {"carrier": "Emirates", "fee": 3500},
    "BLR-MAA": {"carrier": "IndiGo", "fee": 1500},
    "DEL-SIN": {"carrier": "Singapore Airlines", "fee": 4000},
    "DEL-BOM": {"carrier": "Air India", "fee": 2000},
    "COK-DXB": {"carrier": "Air India Express", "fee": 3000},
    "MAA-CMB": {"carrier": "SriLankan Airlines", "fee": 2500}
}
VALID_SECTORS = list(AIRLINE_POLICY_KB.keys()) + ["HYD-BKK", "DEL-CCU", "GOI-BOM", "BOM-BKK", "BLR-DXB", "PNQ-DEL", "DEL-KTM"]

def redact_pii(text: str) -> str:
    text = re.sub(r'\b\d{10,12}\b', '[REDACTED_PHONE]', text)
    text = re.sub(r'\S+@\S+\.\S+', '[REDACTED_EMAIL]', text)
    text = re.sub(r'\b(?:\d[ -]*?){13,16}\b', '[REDACTED_CARD]', text)
    return text

def extract_entities(state: EscalationState) -> EscalationState:
    t0 = time.time()
    raw = state["raw_message"]
    safe_text = redact_pii(raw)
    
    # Extraction logic
    ref_match = re.search(r'\b(RF-?\d{3,5})\b', safe_text, re.IGNORECASE)
    reference_id = ref_match.group(1).upper().replace(" ", "") if ref_match else None
    if reference_id and "-" not in reference_id:
        reference_id = f"RF-{reference_id[2:]}"

    route = None
    for sec in VALID_SECTORS:
        if sec in safe_text.upper():
            route = sec
            break

    amt_match = re.search(r'(?:₹|INR|rs\.?|amount\s*of)\s*(\d[\d,]*)', safe_text, re.IGNORECASE)
    amount = float(amt_match.group(1).replace(",", "")) if amt_match else None

    lower = safe_text.lower()
    if "deduct" in lower or "short" in lower or "paid only" in lower or "dispute" in lower:
        intent = "discrepancy_explanation"
    elif "status" in lower or "update" in lower or "when" in lower or "kahan" in lower:
        intent = "status_update"
    else:
        intent = "new_refund_intake"

    missing_ref = reference_id is None
    confidence = 85 if (reference_id and route) else 60 if (reference_id or route) else 40

    # Ensure audit trace is initialized
    if "audit_trace" not in state or state["audit_trace"] is None:
        state["audit_trace"] = []

    state["reference_id"] = reference_id
    state["route"] = route
    state["intent"] = intent
    state["expected_amount"] = amount
    state["missing_reference"] = missing_ref
    state["confidence_score"] = confidence
    
    state["audit_trace"].append({
        "node": "redact_pii_and_extract",
        "timestamp": f"{time.time() - t0:.3f}s",
        "status": "COMPLETED",
        "metadata": {"confidence": confidence, "intent": intent}
    })
    
    return state

def sentiment_and_routing(state: EscalationState) -> EscalationState:
    t0 = time.time()
    safe_text = redact_pii(state["raw_message"]).lower()
    tier = state.get("agency_tier", "Standard").upper()
    
    critical_keywords = ["legal", "court", "threat", "fraud", "police", "consumer", "lawyer", "loss"]
    high_keywords = ["urgent", "immediately", "angry", "escalat", "unacceptable", "waiting", "client is asking"]
    
    is_critical = any(kw in safe_text for kw in critical_keywords)
    is_high = any(kw in safe_text for kw in high_keywords) or is_critical
    
    if is_critical:
        urgency = "Critical"
    elif is_high:
        urgency = "High"
    elif "?" in safe_text or "status" in safe_text:
        urgency = "Medium"
    else:
        urgency = "Low"
        
    if tier in ["VIP", "STRATEGIC"] and urgency in ["Critical", "High"]:
        rank = "P0 - Immediate"
    elif urgency == "Critical":
        rank = "P0 - Immediate" if tier == "VIP" else "P1 - Urgent"
    elif urgency == "High":
        rank = "P1 - Urgent" if tier in ["VIP", "STRATEGIC"] else "P2 - Elevated"
    elif urgency == "Medium":
        rank = "P2 - Elevated" if tier in ["VIP", "STRATEGIC"] else "P3 - Standard"
    else:
        rank = "P3 - Standard"
        
    state["urgency_level"] = urgency
    state["priority_rank"] = rank
    
    hitl = state["missing_reference"] or state["confidence_score"] < 70 or rank == "P0 - Immediate"
    reason = None
    if state["missing_reference"]:
        reason = "Missing booking reference ID or PNR."
    elif rank == "P0 - Immediate":
        reason = "P0 Critical VIP escalation requires manual Manager outreach."
    elif state["confidence_score"] < 70:
        reason = "Low extraction confidence."
        
    state["hitl_required"] = hitl
    state["hitl_reason"] = reason
    
    state["audit_trace"].append({
        "node": "sentiment_and_routing",
        "timestamp": f"{time.time() - t0:.3f}s",
        "status": "COMPLETED",
        "metadata": {"priority_rank": rank, "urgency": urgency}
    })
    
    return state

def policy_and_draft_response(state: EscalationState) -> EscalationState:
    t0 = time.time()
    
    ref_id = state["reference_id"]
    route = state["route"] or "DEL-DXB"
    ssot = state.get("ssot_status")
    
    policy = AIRLINE_POLICY_KB.get(route, {"carrier": "Carrier", "fee": 2000})
    state["policy_fee"] = policy["fee"]
    
    if ssot:
        st_val = ssot.get("status", "Pending")
        notes_val = ssot.get("notes", "")
        draft = f"Dear Partner, regarding ticket {ref_id} ({route}): your refund is currently {st_val}. {notes_val} Best regards, BharatTrip Operations."
    elif state["intent"] == "discrepancy_explanation":
        draft = f"Dear Partner, for ticket {ref_id} ({route}), the deduction of ₹{policy['fee']} reflects the standard {policy['carrier']} cancellation fee. Payout was processed accordingly. Best regards, BharatTrip Operations."
    else:
        draft = f"Hello, we have received your request regarding {route}. Our team is reviewing the records and will update you within SLA. Best, BharatTrip Operations."
        
    state["draft_response"] = draft
    
    state["audit_trace"].append({
        "node": "policy_lookup",
        "timestamp": f"{time.time() - t0:.3f}s",
        "status": "COMPLETED",
        "metadata": {"carrier": policy["carrier"], "cancellation_fee": policy["fee"]}
    })
    
    return state

def guardrail_reflection(state: EscalationState) -> EscalationState:
    t0 = time.time()
    draft = state.get("draft_response", "")
    
    has_pii = bool(re.search(r'\b\d{10,12}\b', draft) or re.search(r'\S+@\S+\.\S+', draft))
    sentence_count = len([s for s in re.split(r'[.!?]+', draft) if s.strip()])
    too_long = sentence_count > 4
    
    passed = not has_pii and not too_long
    state["guardrail_passed"] = passed
    
    feedback = []
    if has_pii: feedback.append("PII leakage detected.")
    if too_long: feedback.append("Response too long.")
    
    if not passed:
        state["hitl_required"] = True
        state["hitl_reason"] = state["hitl_reason"] or " | ".join(feedback)
        
    state["audit_trace"].append({
        "node": "guardrail_reflection",
        "timestamp": f"{time.time() - t0:.3f}s",
        "status": "COMPLETED" if passed else "FLAGGED",
        "metadata": {"guardrail_passed": passed}
    })
    
    if state["hitl_required"]:
        state["audit_trace"].append({
            "node": "hitl_interrupt",
            "timestamp": f"{time.time() - t0:.3f}s",
            "status": "INTERRUPT",
            "metadata": {"reason": state["hitl_reason"]}
        })
        
    return state

# Define LangGraph
workflow = StateGraph(EscalationState)
workflow.add_node("extract", extract_entities)
workflow.add_node("route", sentiment_and_routing)
workflow.add_node("draft", policy_and_draft_response)
workflow.add_node("guardrail", guardrail_reflection)

workflow.set_entry_point("extract")
workflow.add_edge("extract", "route")
workflow.add_edge("route", "draft")
workflow.add_edge("draft", "guardrail")
workflow.add_edge("guardrail", END)

escalation_app = workflow.compile()
