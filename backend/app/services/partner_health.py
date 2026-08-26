"""
B2B Partner Health Matrix, Sentiment Scoring, and Churn Risk Telemetry Service.
Monitors travel partner frustration tone, revenue tiers, escalation frequencies,
and dispatches proactive partner retention outreach.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.models.escalation import Escalation
from backend.app.models.support import SupportTicket
from backend.app.models.audit import AuditLog
from backend.app.services.reconciliation import calculate_orphans_from_db


VIP_AGENCY_KEYWORDS = ["peak", "nomad", "global", "royal", "zenith"]


def determine_agency_tier(agency_name: str) -> str:
    """Classifies agency into VIP or Standard tier based on name profile."""
    name_lower = (agency_name or "").lower()
    if any(k in name_lower for k in VIP_AGENCY_KEYWORDS):
        return "VIP"
    return "Standard"


def analyze_partner_sentiment_scoring(text: str, agency_tier: str = "Standard") -> Dict[str, Any]:
    """
    NLP sentiment, urgency, and priority classification agent.
    Detects severe legal threats, frustration triggers, and maps priority based on agency tier.
    """
    lower = (text or "").lower()
    critical_keywords = [
        "legal", "court", "threat", "fraud", "police", "consumer",
        "2 hafte", "two weeks", "weeks", "lawyer", "loss"
    ]
    high_keywords = [
        "urgent", "immediately", "angry", "escalat", "unacceptable",
        "client is asking", "waiting", "dispute", "loss"
    ]

    is_critical = any(kw in lower for kw in critical_keywords)
    is_high = any(kw in lower for kw in high_keywords) or is_critical

    if not text or not text.strip():
        urgency = "Low"
        frustration_cat = "Routine Inquiry"
        sentiment_score = 0.0
    elif is_critical:
        urgency = "Critical"
        frustration_cat = "Legal / Severe Churn Risk"
        sentiment_score = -0.85
    elif is_high:
        urgency = "High"
        frustration_cat = "Prolonged Delay / Frustration"
        sentiment_score = -0.55
    elif "?" in lower or "status" in lower or "update" in lower or "when" in lower or "kahan" in lower:
        urgency = "Medium"
        frustration_cat = "Information Request"
        sentiment_score = -0.15
    else:
        urgency = "Low"
        frustration_cat = "Routine Inquiry"
        sentiment_score = 0.10

    tier_upper = (agency_tier or "Standard").upper()
    if tier_upper == "VIP" and urgency in ["Critical", "High"]:
        priority_rank = "P0 - Immediate"
    elif urgency == "Critical":
        priority_rank = "P0 - Immediate" if tier_upper in ["VIP", "STRATEGIC"] else "P1 - Urgent"
    elif urgency == "High":
        priority_rank = "P1 - Urgent" if tier_upper in ["VIP", "STRATEGIC"] else "P2 - Elevated"
    elif urgency == "Medium":
        priority_rank = "P2 - Elevated" if tier_upper in ["VIP", "STRATEGIC"] else "P3 - Standard"
    else:
        priority_rank = "P3 - Standard"

    rec_action = (
        "Instant Manager Escalation & Phone Outreach"
        if "P0" in priority_rank
        else "Queue in Fast-Track Triage"
    )

    return {
        "sentiment_score": sentiment_score,
        "urgency_level": urgency,
        "priority_rank": priority_rank,
        "frustration_category": frustration_cat,
        "agency_tier": agency_tier,
        "recommended_action": rec_action,
    }


def get_partner_health_matrix_data(db: Session) -> Dict[str, Any]:
    """
    Aggregates fleet-wide partner health telemetry across Escalations and Support Tickets.
    """
    escalations = db.query(Escalation).all()
    support_tickets = db.query(SupportTicket).all()
    missing_in_fin, _ = calculate_orphans_from_db(db)

    # Collect distinct agencies
    agency_names = set()
    for e in escalations:
        if e.agent:
            agency_names.add(e.agent.strip())
    for s in support_tickets:
        if s.agent:
            agency_names.add(s.agent.strip())

    if not agency_names:
        # Default baseline if DB is empty
        agency_names = {"Peak Journeys", "Nomad Travels", "Global Escapes", "Royal Voyager", "Zenith Holidays"}

    # Count unlogged payouts per agent
    from collections import Counter
    unlogged_by_agent = Counter([str(m.get("agent", "")).strip() for m in missing_in_fin])

    partners = []
    total_sentiment_sum = 0.0
    critical_vips_count = 0
    complaint_counter = Counter()

    for agency in sorted(agency_names):
        tier = determine_agency_tier(agency)
        agency_escs = [e for e in escalations if (e.agent or "").strip().lower() == agency.lower()]
        active_escs = len([e for e in agency_escs if (e.status or "").lower() in ["open", "pending", "in progress"]])

        # Sample messages & sentiment
        sample_msgs = [e.message for e in agency_escs if e.message][:3]
        if sample_msgs:
            combined_text = " ".join(sample_msgs)
            sent_res = analyze_partner_sentiment_scoring(combined_text, agency_tier=tier)
            sentiment_index = sent_res["sentiment_score"]
            bottleneck = sent_res["frustration_category"]
        else:
            sentiment_index = 0.10
            bottleneck = "Routine Inquiry"

        complaint_counter[bottleneck] += 1
        total_sentiment_sum += sentiment_index

        unlogged = unlogged_by_agent.get(agency, 0)
        last_date = str(agency_escs[-1].raised_on) if (agency_escs and agency_escs[-1].raised_on) else None

        # Determine risk status
        if tier == "VIP" and (sentiment_index < -0.40 or active_escs >= 3):
            risk_status = "CRITICAL (Immediate Churn Risk)"
            critical_vips_count += 1
        elif sentiment_index < -0.30 or active_escs >= 4 or unlogged >= 3:
            risk_status = "ELEVATED (SLA Delay)"
        else:
            risk_status = "STABLE"

        partners.append({
            "agency_name": agency,
            "revenue_tier": tier,
            "active_escalations": active_escs,
            "sentiment_index": round(sentiment_index, 2),
            "primary_bottleneck": bottleneck,
            "risk_status": risk_status,
            "sample_messages": sample_msgs,
            "unlogged_payouts": unlogged,
            "last_escalation_date": last_date,
        })

    # Sort: Critical VIPs first, then elevated, then stable
    status_order = {
        "CRITICAL (Immediate Churn Risk)": 0,
        "ELEVATED (SLA Delay)": 1,
        "STABLE": 2,
    }
    partners.sort(key=lambda p: (status_order.get(p["risk_status"], 3), -p["active_escalations"], p["sentiment_index"]))

    fleet_avg_sentiment = round(total_sentiment_sum / len(agency_names), 2) if agency_names else 0.0
    dominant_complaint = complaint_counter.most_common(1)[0][0] if complaint_counter else "Prolonged Delay / Frustration"

    summary_data = {
        "total_monitored_agencies": len(agency_names),
        "critical_vips_count": critical_vips_count,
        "critical_vips": critical_vips_count,
        "monitored_agencies": len(agency_names),
        "fleet_sentiment_index": fleet_avg_sentiment,
        "fleet_sentiment": fleet_avg_sentiment,
        "dominant_complaint": dominant_complaint,
    }

    return {
        "total_monitored_agencies": len(agency_names),
        "critical_vips_at_risk": critical_vips_count,
        "fleet_sentiment_index": fleet_avg_sentiment,
        "dominant_complaint": dominant_complaint,
        "summary": summary_data,
        "partners": partners,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_partner_agency_detail(db: Session, agency_name: str) -> Dict[str, Any]:
    """
    Fetches deep-dive telemetry profile for a specific agency.
    """
    matrix_data = get_partner_health_matrix_data(db)
    matched = next((p for p in matrix_data["partners"] if p["agency_name"].lower() == agency_name.lower()), None)
    if not matched:
        tier = determine_agency_tier(agency_name)
        matched = {
            "agency_name": agency_name,
            "revenue_tier": tier,
            "active_escalations": 0,
            "sentiment_index": 0.10,
            "primary_bottleneck": "General",
            "risk_status": "STABLE",
            "sample_messages": [],
            "unlogged_payouts": 0,
            "last_escalation_date": None,
        }

    tickets = db.query(SupportTicket).filter(SupportTicket.agent.ilike(f"%{agency_name}%")).all()
    associated_tickets = [t.to_dict(use_aliases=False) for t in tickets[:10]]

    return {
        "agency_name": matched["agency_name"],
        "revenue_tier": matched["revenue_tier"],
        "tier": matched["revenue_tier"],
        "active_escalations": matched["active_escalations"],
        "sentiment_index": matched["sentiment_index"],
        "primary_bottleneck": matched["primary_bottleneck"],
        "risk_status": matched["risk_status"],
        "recent_messages": matched["sample_messages"],
        "associated_tickets": associated_tickets,
        "recommended_action": "Instant Manager Escalation & Phone Outreach" if "CRITICAL" in matched["risk_status"] else "Monitor normally",
    }


def dispatch_partner_outreach_action(
    agency_name: str,
    outreach_type: str,
    custom_note: Optional[str] = None,
    user_id: str = "mgr_01"
) -> Dict[str, Any]:
    """
    Simulates / logs dispatch of a proactive partner reassurance intervention.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    action_desc = f"Dispatched {outreach_type} to {agency_name}. Custom Note: {custom_note or 'None'}."

    return {
        "success": True,
        "agency_name": agency_name,
        "outreach_type": outreach_type,
        "action_taken": action_desc,
        "timestamp": now_iso,
    }
