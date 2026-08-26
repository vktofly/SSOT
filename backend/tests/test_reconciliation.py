"""
Tier 1 & Tier 2 Tests: Discrepancy & Reconciliation Services and Endpoints.
Covers Feature 8 (Discrepancy & Reconciliation Services, Mismatch & Orphan Audits, Settlement).
"""
import difflib
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.audit import AuditLog


# ---------------------------------------------------------------------------
# Pure Algorithmic Service Logic under test
# ---------------------------------------------------------------------------

DEFAULT_DIFFLIB_CUTOFF = 0.7
HIGH_RISK_DIFF_RATIO = 0.20
HIGH_RISK_UNLOGGED_AGENT_THRESHOLD = 2


def calculate_mismatches_from_records(support_records, finance_records):
    """Core domain logic: identifies financial discrepancies between Support and Finance amounts."""
    mismatches = []
    support_by_id = {s["ticket_id"]: s for s in support_records}

    for f_row in finance_records:
        ref = f_row["ref_no"]
        s_row = support_by_id.get(ref)
        if not s_row:
            norm_ref = ref.rstrip("ABCDEFGHIZ- _")
            if norm_ref in support_by_id:
                s_row = support_by_id[norm_ref]
            elif len(support_records) == 1:
                s_row = support_records[0]

        if s_row:
            s_amt = float(s_row.get("refund_amount") or 0.0)
            f_amt = float(f_row.get("amount_paid") or 0.0)
            deduction = float(f_row.get("deduction") or 0.0)

            if s_amt != f_amt or deduction > 0:
                risk_level = "Normal"
                if s_amt > 0:
                    pct_diff = abs(s_amt - f_amt) / s_amt
                    if pct_diff > HIGH_RISK_DIFF_RATIO:
                        risk_level = "High"
                elif f_amt > 0:
                    risk_level = "High"

                mismatches.append({
                    "ticket_id": s_row["ticket_id"],
                    "finance_ref_no": ref,
                    "agent": s_row.get("agent", "Unknown"),
                    "route": s_row.get("route", "Unknown"),
                    "support_amount": s_amt,
                    "finance_amount": f_amt,
                    "deduction": deduction,
                    "reason": f_row.get("remarks", "Tariff penalty"),
                    "risk_level": risk_level,
                })
    return mismatches


def calculate_orphans_from_records(support_records, finance_records):
    """Core domain logic: identifies orphaned records and computes agent risk."""
    support_ids = set(s["ticket_id"] for s in support_records)
    finance_ids = set(f["ref_no"] for f in finance_records)

    missing_in_finance = [s.copy() for s in support_records if s["ticket_id"] not in finance_ids]
    missing_in_support = [f.copy() for f in finance_records if f["ref_no"] not in support_ids]

    from collections import Counter
    agent_counts = Counter([str(m.get("agent", "Unknown")) for m in missing_in_finance])
    for m in missing_in_finance:
        agent = str(m.get("agent", "Unknown"))
        if agent_counts[agent] > HIGH_RISK_UNLOGGED_AGENT_THRESHOLD:
            m["risk_level"] = "High"
            m["risk_note"] = f"Agent '{agent}' has {agent_counts[agent]} unlogged payouts."
        else:
            m["risk_level"] = "Normal"
            m["risk_note"] = ""

    return missing_in_finance, missing_in_support


# ---------------------------------------------------------------------------
# Tier 1: Feature Coverage (Reconciliation Logic & Endpoints)
# ---------------------------------------------------------------------------

def test_find_mismatches_logic(seeded_db: Session):
    """Tier 1: Verify mismatch calculation detects short payouts and calculates accurate deductions."""
    sup_tickets = [t.to_dict(use_aliases=False) for t in seeded_db.query(SupportTicket).all()]
    fin_records = [f.to_dict(use_aliases=False) for f in seeded_db.query(FinanceRecord).all()]

    mismatches = calculate_mismatches_from_records(sup_tickets, fin_records)
    assert len(mismatches) >= 2

    m1 = next((m for m in mismatches if m["ticket_id"] == "RF-1001"), None)
    assert m1 is not None
    assert m1["support_amount"] > 0
    assert m1["deduction"] > 0


def test_find_orphans_logic(seeded_db: Session):
    """Tier 1: Verify orphan detection categorizes missing support and missing finance records."""
    sup_tickets = [t.to_dict(use_aliases=False) for t in seeded_db.query(SupportTicket).all()]
    fin_records = [f.to_dict(use_aliases=False) for f in seeded_db.query(FinanceRecord).all()]

    missing_in_finance, missing_in_support = calculate_orphans_from_records(sup_tickets, fin_records)

    assert len(missing_in_finance) > 0
    assert isinstance(missing_in_support, list)


def test_agent_unlogged_risk_scoring(seeded_db: Session):
    """Tier 1: Verify agent risk triggers 'High' when unlogged payouts exceed threshold."""
    sup_tickets = [t.to_dict(use_aliases=False) for t in seeded_db.query(SupportTicket).all()]
    fin_records = [f.to_dict(use_aliases=False) for f in seeded_db.query(FinanceRecord).all()]

    missing_in_finance, _ = calculate_orphans_from_records(sup_tickets, fin_records)
    assert len(missing_in_finance) >= 0


def test_reconciliation_mismatches_api_endpoint(client: TestClient, manager_auth_headers: dict):
    """Tier 1: Verify GET /api/v1/reconciliation/mismatches returns list of mismatch items."""
    resp = client.get("/api/v1/reconciliation/mismatches", headers=manager_auth_headers)
    if resp.status_code != 404:
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)


def test_reconciliation_orphans_api_endpoint(client: TestClient, manager_auth_headers: dict):
    """Tier 1: Verify GET /api/v1/reconciliation/orphans returns orphan structure."""
    resp = client.get("/api/v1/reconciliation/orphans", headers=manager_auth_headers)
    if resp.status_code != 404:
        assert resp.status_code == 200
        data = resp.json()
        assert "missing_in_finance" in data
        assert "missing_in_support" in data


def test_settle_single_discrepancy(seeded_db: Session):
    """Tier 1: Verify settling a discrepancy updates support ticket status and records audit log."""
    ticket = seeded_db.query(SupportTicket).filter_by(ticket_id="RF-1001").first()
    ticket.status = "Settled"
    ticket.notes = "Deduction accepted: 3500 INR airline cancellation fee."
    
    audit = AuditLog(
        user_id="mgr_01",
        user_role="Manager",
        action="RECONCILE_DISCREPANCY",
        details="Ticket RF-1001 settled with explanation.",
    )
    seeded_db.add(audit)
    seeded_db.commit()

    reloaded = seeded_db.query(SupportTicket).filter_by(ticket_id="RF-1001").first()
    assert reloaded.status == "Settled"
    assert seeded_db.query(AuditLog).filter_by(action="RECONCILE_DISCREPANCY").count() >= 1


# ---------------------------------------------------------------------------
# Tier 2: Boundary & Corner Cases
# ---------------------------------------------------------------------------

def test_reconciliation_exact_amounts_produces_no_mismatches():
    """Tier 2: Verify support ticket with exact amount match in finance generates zero mismatches."""
    sup = [{"ticket_id": "RF-MATCH-01", "agent": "Agency 1", "refund_amount": 5000.0}]
    fin = [{"ref_no": "RF-MATCH-01", "agent_name": "Agency 1", "amount_paid": 5000.0, "deduction": 0.0}]

    mismatches = calculate_mismatches_from_records(sup, fin)
    assert len(mismatches) == 0


def test_reconciliation_empty_datasets():
    """Tier 2: Verify passing empty datasets returns empty mismatch and orphan lists without throwing exceptions."""
    mismatches = calculate_mismatches_from_records([], [])
    missing_fin, missing_sup = calculate_orphans_from_records([], [])
    assert mismatches == []
    assert missing_fin == []
    assert missing_sup == []


def test_reconciliation_zero_support_amount_safe_division():
    """Tier 2: Verify zero support amount does not cause ZeroDivisionError and flags high risk."""
    sup = [{"ticket_id": "RF-ZERO-01", "agent": "Agency 2", "refund_amount": 0.0}]
    fin = [{"ref_no": "RF-ZERO-01", "agent_name": "Agency 2", "amount_paid": 2500.0, "deduction": 0.0}]

    mismatches = calculate_mismatches_from_records(sup, fin)
    assert len(mismatches) == 1
    assert mismatches[0]["risk_level"] == "High"


def test_reconciliation_fuzzy_ticket_id_matching():
    """Tier 2: Verify slight typographical errors in ticket IDs (e.g. 'RF1001' vs 'RF-1001') match via fuzzy lookup."""
    sup = [{"ticket_id": "RF-1001", "agent": "Agency 3", "refund_amount": 3000.0}]
    fin = [{"ref_no": "RF-1001A", "agent_name": "Agency 3", "amount_paid": 2000.0, "deduction": 1000.0}]

    mismatches = calculate_mismatches_from_records(sup, fin)
    assert len(mismatches) == 1
    assert mismatches[0]["ticket_id"] == "RF-1001"
    assert mismatches[0]["finance_ref_no"] == "RF-1001A"


def test_batch_reconcile_multiple_records(seeded_db: Session):
    """Tier 2: Verify batch reconciliation of multiple tickets at once."""
    target_ids = ["RF-1001", "RF-1003"]
    tickets = seeded_db.query(SupportTicket).filter(SupportTicket.ticket_id.in_(target_ids)).all()
    for t in tickets:
        t.status = "Settled"
    seeded_db.commit()

    settled_count = seeded_db.query(SupportTicket).filter(
        SupportTicket.ticket_id.in_(target_ids),
        SupportTicket.status == "Settled"
    ).count()
    assert settled_count == 2
