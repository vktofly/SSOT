"""
Tests for SQLAlchemy models and database hydration script.
"""
from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.escalation import Escalation
from backend.app.models.audit import AuditLog
from backend.app.scripts.seed_db import clean_money_string, clean_str, normalize_id, seed_database


def test_clean_money_string_variants():
    """Verify clean_money_string handles all currency formatting edge cases."""
    assert clean_money_string("10,200") == 10200.0
    assert clean_money_string("₹15,500.50") == 15500.50
    assert clean_money_string("INR 3,400") == 3400.0
    assert clean_money_string("$500") == 500.0
    assert clean_money_string(0) == 0.0
    assert clean_money_string(None) == 0.0
    assert clean_money_string("") == 0.0
    assert clean_money_string("nan") == 0.0
    assert clean_money_string("-") == 0.0


def test_clean_str_variants():
    """Verify clean_str handles string stripping and null/nan conversion."""
    assert clean_str("  DEL-BOM  ") == "DEL-BOM"
    assert clean_str(None) is None
    assert clean_str("nan") is None
    assert clean_str("   ") is None


def test_normalize_id_variants():
    """Verify normalize_id handles space normalization and uppercase conversion."""
    assert normalize_id("RF 1750") == "RF-1750"
    assert normalize_id("rf 1123") == "RF-1123"
    assert normalize_id("RF-1001") == "RF-1001"
    assert normalize_id("ESC 801") == "ESC-801"
    assert normalize_id("esc-999") == "ESC-999"
    assert normalize_id(None) is None
    assert normalize_id("nan") is None
    assert normalize_id("") is None


def test_models_to_dict(sample_support_ticket, sample_finance_record, sample_escalation):
    """Verify model to_dict methods produce both alias and snake_case representations."""
    support_dict_alias = sample_support_ticket.to_dict(use_aliases=True)
    assert support_dict_alias["Ticket ID"] == "RF-9999"
    assert support_dict_alias["Refund Amount (INR)"] == 12500.0

    support_dict_snake = sample_support_ticket.to_dict(use_aliases=False)
    assert support_dict_snake["ticket_id"] == "RF-9999"
    assert support_dict_snake["refund_amount"] == 12500.0

    finance_dict_alias = sample_finance_record.to_dict(use_aliases=True)
    assert finance_dict_alias["Ref No"] == "RF-9999"
    assert finance_dict_alias["Amount Paid (INR)"] == 11000.0

    escalation_dict_alias = sample_escalation.to_dict(use_aliases=True)
    assert escalation_dict_alias["Escalation ID"] == "ESC-999"
    assert escalation_dict_alias["Message"] == "Deduction disputed by partner agency."


def test_seed_database_execution(db_session):
    """Verify seed_database populates in-memory database cleanly from CSVs."""
    counts = seed_database(db=db_session, force=True, data_dir="data")
    assert counts["support"] > 700
    assert counts["finance"] > 600
    assert counts["escalations"] > 100

    # Verify query
    tickets = db_session.query(SupportTicket).limit(10).all()
    assert len(tickets) == 10
    assert tickets[0].ticket_id.startswith("RF")
