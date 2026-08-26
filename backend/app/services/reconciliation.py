"""
Discrepancy & Reconciliation Business Logic Service.
Handles DB-backed ledger mismatch audits, orphan detection, HITL discrepancy settlement,
orphan ticket linking, fuzzy metadata discovery, and automated notification drafting.
"""
import difflib
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.audit import AuditLog
from backend.app.services.policy import lookup_airline_fare_policy


DEFAULT_DIFFLIB_CUTOFF = 0.70
HIGH_RISK_VARIANCE_RATIO = 0.20
HIGH_RISK_UNLOGGED_AGENT_THRESHOLD = 2


def calculate_mismatches_from_db(
    db: Session,
    risk_level_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Computes financial discrepancies between Support Tickets and Finance Records in the database.
    Matches primarily on exact Ticket ID == Ref No, with fuzzy difflib fallback.
    Identifies short payouts, tariff deductions, and risk tiering (>20% difference flags 'High').
    """
    support_records = db.query(SupportTicket).all()
    finance_records = db.query(FinanceRecord).all()

    if not support_records or not finance_records:
        return []

    support_by_id = {s.ticket_id: s for s in support_records if s.ticket_id}
    support_ids = list(support_by_id.keys())

    mismatches = []
    for f_row in finance_records:
        ref = f_row.ref_no
        if not ref:
            continue

        s_ticket = support_by_id.get(ref)
        if not s_ticket:
            close_matches = difflib.get_close_matches(ref, support_ids, n=1, cutoff=DEFAULT_DIFFLIB_CUTOFF)
            if close_matches:
                s_ticket = support_by_id.get(close_matches[0])

        if s_ticket:
            s_amt = float(s_ticket.refund_amount or 0.0)
            f_amt = float(f_row.amount_paid or 0.0)
            deduction = float(f_row.deduction or 0.0)
            if deduction == 0.0 and s_amt != f_amt:
                deduction = abs(s_amt - f_amt)

            if s_amt != f_amt:
                risk_level = "Normal"
                risk_note = ""
                if s_amt > 0:
                    variance_ratio = abs(s_amt - f_amt) / s_amt
                    if variance_ratio > HIGH_RISK_VARIANCE_RATIO:
                        risk_level = "High"
                        risk_note = f"High variance ({variance_ratio:.1%}) exceeds 20% tolerance."
                elif f_amt > 0:
                    risk_level = "High"
                    risk_note = "Support record had ₹0 promised amount while payout was executed."

                if risk_level_filter and risk_level.lower() != risk_level_filter.lower():
                    continue

                mismatches.append({
                    "ticket_id": s_ticket.ticket_id,
                    "finance_ref_no": ref,
                    "agent": s_ticket.agent or f_row.agent_name or "Unknown",
                    "route": s_ticket.route or "Unknown",
                    "support_amount": s_amt,
                    "finance_amount": f_amt,
                    "deduction": deduction,
                    "reason": f_row.remarks or "Carrier penalty or deduction applied",
                    "risk_level": risk_level,
                    "risk_note": risk_note,
                    "status": s_ticket.status or "Pending",
                })

    return mismatches


def calculate_orphans_from_db(
    db: Session
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Identifies orphaned records in the database:
    - missing_in_finance: Support tickets approved/logged but missing in Finance ledger.
    - missing_in_support: Finance payouts recorded without an originating Support ticket.
    Computes agent risk scores: flags 'High' risk if an agency has >2 unlogged payouts.
    """
    support_records = db.query(SupportTicket).all()
    finance_records = db.query(FinanceRecord).all()

    if not support_records and not finance_records:
        return [], []

    support_ids = [s.ticket_id for s in support_records if s.ticket_id]
    finance_ids = [f.ref_no for f in finance_records if f.ref_no]

    missing_in_finance = []
    missing_in_support = []

    for s in support_records:
        sid = s.ticket_id
        if not sid:
            continue
        if sid not in finance_ids:
            close = difflib.get_close_matches(sid, finance_ids, n=1, cutoff=DEFAULT_DIFFLIB_CUTOFF)
            if not close:
                missing_in_finance.append({
                    "ticket_id": s.ticket_id,
                    "agent": s.agent or "Unknown",
                    "route": s.route or "Unknown",
                    "amount": float(s.refund_amount or 0.0),
                    "request_date": s.request_date or "",
                    "status": s.status or "Pending",
                    "source_ledger": "Support",
                })

    for f in finance_records:
        ref = f.ref_no
        if not ref:
            continue
        if ref not in support_ids:
            close = difflib.get_close_matches(ref, support_ids, n=1, cutoff=DEFAULT_DIFFLIB_CUTOFF)
            if not close:
                missing_in_support.append({
                    "ref_no": f.ref_no,
                    "agent": f.agent_name or "Unknown",
                    "amount": float(f.amount_paid or 0.0),
                    "processed_on": f.processed_on or "",
                    "status": f.payout_status or "Processed",
                    "source_ledger": "Finance",
                })

    # Agent unlogged risk scoring
    from collections import Counter
    agent_counts = Counter([str(m.get("agent", "Unknown")) for m in missing_in_finance])
    for m in missing_in_finance:
        agent = str(m.get("agent", "Unknown"))
        count = agent_counts[agent]
        if count > HIGH_RISK_UNLOGGED_AGENT_THRESHOLD:
            m["risk_level"] = "High"
            m["risk_note"] = f"Agent '{agent}' has {count} unlogged payouts."
        else:
            m["risk_level"] = "Normal"
            m["risk_note"] = ""

    return missing_in_finance, missing_in_support


def get_reconciliation_summary(db: Session) -> Dict[str, Any]:
    """
    Computes summary telemetry across support, finance, and discrepancy domains.
    """
    total_sup = db.query(SupportTicket).count()
    total_fin = db.query(FinanceRecord).count()

    mismatches = calculate_mismatches_from_db(db)
    missing_in_fin, missing_in_sup = calculate_orphans_from_db(db)

    total_mismatches = len(mismatches)
    pending_mismatches = len([m for m in mismatches if m.get("status") in ["Pending", "Disputed", "Open"]])
    resolved_mismatches = len([m for m in mismatches if m.get("status") in ["Settled", "Client Notified", "Refund Done"]])
    fleet_variance = sum(float(m.get("deduction") or 0.0) for m in mismatches)
    high_risk_count = len([m for m in mismatches if m.get("risk_level") == "High"])

    return {
        "total_support_records": total_sup,
        "total_finance_records": total_fin,
        "total_mismatches": total_mismatches,
        "pending_mismatches": pending_mismatches,
        "resolved_mismatches": resolved_mismatches,
        "total_orphans_in_finance": len(missing_in_fin),
        "total_orphans_in_support": len(missing_in_sup),
        "fleet_variance_inr": round(fleet_variance, 2),
        "high_risk_discrepancies_count": high_risk_count,
    }


def resolve_discrepancy(
    db: Session,
    ticket_id: str,
    new_status: str,
    notes: Optional[str],
    user_id: str,
    user_role: str,
    resolution_type: Optional[str] = "Accept Deduction",
    adjusted_amount: Optional[float] = None,
    send_communication: bool = False,
    communication_draft: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves a single ledger mismatch, mutates the support ticket status, and records an immutable audit log.
    """
    ticket = db.query(SupportTicket).filter_by(ticket_id=ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found."
        )

    ticket.status = new_status
    if notes:
        existing_notes = ticket.notes or ""
        ticket.notes = f"{existing_notes} | {notes}".strip(" |")

    if adjusted_amount is not None:
        ticket.refund_amount = adjusted_amount

    audit_details = (
        f"Ticket {ticket_id} resolved with action '{resolution_type}'. Status changed to '{new_status}'. "
        f"Notes: {notes or 'N/A'}. Comm sent: {send_communication}."
    )
    if communication_draft:
        audit_details += f" Draft recorded: {communication_draft[:100]}..."

    audit_log = AuditLog(
        user_id=user_id,
        user_role=user_role,
        action="RECONCILE_DISCREPANCY",
        details=audit_details,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(ticket)
    db.refresh(audit_log)

    return {
        "success": True,
        "ticket_id": ticket_id,
        "new_status": new_status,
        "notes": ticket.notes or "",
        "audit_id": audit_log.id,
        "message": f"Successfully settled discrepancy for ticket {ticket_id}.",
    }


def link_orphan_ticket(
    db: Session,
    support_ticket_id: str,
    finance_ref_no: str,
    user_id: str,
    user_role: str,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Links an orphaned Support Ticket with an unlinked Finance Record and writes to audit logs.
    """
    s_ticket = db.query(SupportTicket).filter_by(ticket_id=support_ticket_id).first()
    f_record = db.query(FinanceRecord).filter_by(ref_no=finance_ref_no).first()

    if not s_ticket and not f_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Neither Support ticket '{support_ticket_id}' nor Finance record '{finance_ref_no}' found."
        )

    # Link the records: if finance record has a typo ref_no, update it to support_ticket_id
    if f_record:
        f_record.ref_no = support_ticket_id
        if s_ticket and s_ticket.agent:
            f_record.agent_name = s_ticket.agent

    if s_ticket:
        s_ticket.notes = (s_ticket.notes or "") + f" | Linked to Finance Ref {finance_ref_no}."

    audit_log = AuditLog(
        user_id=user_id,
        user_role=user_role,
        action="LINK_ORPHAN_RECORD",
        details=f"Linked Support ticket {support_ticket_id} with Finance Ref {finance_ref_no}. Notes: {notes or 'N/A'}",
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return {
        "success": True,
        "support_ticket_id": support_ticket_id,
        "finance_ref_no": finance_ref_no,
        "message": f"Successfully linked support ticket {support_ticket_id} with finance record {finance_ref_no}.",
        "audit_id": audit_log.id,
    }


def batch_resolve_discrepancies(
    db: Session,
    ticket_ids: List[str],
    resolution_type: str,
    new_status: str,
    auto_draft_explanations: bool,
    user_id: str,
    user_role: str
) -> Dict[str, Any]:
    """
    Batch resolves multiple discrepancies simultaneously with transaction safety.
    """
    resolved_ids = []
    failed_ids = []

    for tid in ticket_ids:
        ticket = db.query(SupportTicket).filter_by(ticket_id=tid).first()
        if ticket:
            ticket.status = new_status
            note = f"Batch reconciled ({resolution_type})."
            if auto_draft_explanations:
                policy = lookup_airline_fare_policy(ticket.route or "DEL-DXB")
                note += f" Applied policy for {policy['carrier']}."
            ticket.notes = (ticket.notes or "") + f" | {note}"
            resolved_ids.append(tid)
        else:
            failed_ids.append(tid)

    if resolved_ids:
        audit_log = AuditLog(
            user_id=user_id,
            user_role=user_role,
            action="BATCH_RECONCILE_DISCREPANCIES",
            details=f"Batch reconciled {len(resolved_ids)} tickets to '{new_status}'. Action: {resolution_type}. IDs: {resolved_ids}",
        )
        db.add(audit_log)
        db.commit()

    return {
        "success": len(resolved_ids) > 0,
        "resolved_count": len(resolved_ids),
        "resolved_ticket_ids": resolved_ids,
        "failed_ticket_ids": failed_ids,
        "message": f"Successfully resolved {len(resolved_ids)} of {len(ticket_ids)} tickets in batch.",
    }


def fuzzy_match_orphans(
    db: Session,
    threshold: float = 0.70
) -> List[Dict[str, Any]]:
    """
    Runs fuzzy metadata matching across orphaned Support Tickets and Finance Records based on Agent, Route, and Amount.
    """
    missing_fin, missing_sup = calculate_orphans_from_db(db)
    matches = []

    for s in missing_fin:
        s_agent = (s.get("agent") or "").strip().lower()
        s_amt = float(s.get("amount") or 0.0)
        s_id = s.get("ticket_id")

        for f in missing_sup:
            f_agent = (f.get("agent") or "").strip().lower()
            f_amt = float(f.get("amount") or 0.0)
            f_ref = f.get("ref_no")

            # Check agent similarity
            ratio = difflib.SequenceMatcher(None, s_agent, f_agent).ratio() if s_agent and f_agent else 0.0
            amt_match = abs(s_amt - f_amt) < 10.0 if s_amt > 0 else False

            score = 0.0
            rationale_parts = []
            if ratio >= 0.75:
                score += 0.50
                rationale_parts.append(f"Agent name similarity {ratio:.0%}")
            if amt_match:
                score += 0.40
                rationale_parts.append("Identical payout amount")
            if s_id and f_ref and difflib.SequenceMatcher(None, s_id, f_ref).ratio() > 0.6:
                score += 0.20
                rationale_parts.append("Reference string similarity")

            if score >= threshold:
                matches.append({
                    "support_ticket_id": s_id,
                    "finance_ref_no": f_ref,
                    "agent": s.get("agent") or f.get("agent") or "Partner",
                    "confidence_score": min(round(score, 2), 1.0),
                    "match_rationale": " & ".join(rationale_parts) or "High metadata correlation",
                })

    return matches


def draft_discrepancy_explanation(
    agent: str,
    route: str,
    ticket_id: str,
    support_amt: float,
    finance_amt: float,
    deduction: float,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a professional partner email explaining a carrier tariff deduction.
    """
    policy = lookup_airline_fare_policy(route or "DEL-DXB")
    carrier = policy.get("carrier", "Carrier")
    fee = policy.get("cancellation_fee", deduction)

    subject = f"Refund Settlement Update: Ticket {ticket_id} ({route or 'Sector'})"
    draft_body = (
        f"Dear {agent or 'Partner'},\n\n"
        f"Regarding your refund inquiry for ticket {ticket_id} on sector {route or 'N/A'}:\n"
        f"The gross refund amount of ₹{support_amt:,.2f} was adjusted by a cancellation fee of ₹{deduction:,.2f} "
        f"per official {carrier} tariff rules. The net payout of ₹{finance_amt:,.2f} has been processed "
        f"directly to your registered account.\n\n"
        f"Carrier Tariff Remark: {reason or policy.get('policy_notes', 'Standard sector cancellation deduction.')}\n\n"
        f"Please let us know if you require further assistance.\n\n"
        f"Best regards,\n"
        f"BharatTrip Operations Team"
    )

    return {
        "ticket_id": ticket_id,
        "recipient_agent": agent,
        "subject": subject,
        "draft_body": draft_body,
        "draft": draft_body,
        "carrier_policy_applied": f"{carrier} Fare Rules: ₹{fee:,.0f} deduction per passenger.",
    }


def generate_lifecycle_notification(
    ticket_id: str,
    agent_name: str,
    route: str,
    stage: str,
    amount: Optional[str] = None,
    deduction: Optional[str] = None,
    channel: str = "WhatsApp"
) -> Dict[str, Any]:
    """
    Generates a multi-channel lifecycle notification for travel partners.
    """
    amt_str = f" of {amount}" if amount else ""
    ded_str = f" (deduction: {deduction})" if deduction else ""

    if channel.lower() == "whatsapp":
        msg = f"🔔 *BharatTrip Update*: Ticket {ticket_id} ({route}) is now at stage *{stage}*{amt_str}{ded_str}. Thank you for your patience."
    elif channel.lower() == "email":
        msg = (
            f"Dear {agent_name},\n\n"
            f"This is an automated lifecycle update regarding ticket {ticket_id} ({route}).\n"
            f"Current Status: {stage}{amt_str}{ded_str}.\n\n"
            f"Warm regards,\nBharatTrip Support"
        )
    else:
        msg = f"Ticket {ticket_id} [{route}] status updated to {stage}{amt_str}{ded_str}."

    return {
        "success": True,
        "ticket_id": ticket_id,
        "agent_name": agent_name,
        "stage": stage,
        "channel": channel,
        "message": msg,
        "draft_text": msg,
    }
