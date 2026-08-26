"""
Pytest configuration and shared fixtures for backend testing.
"""
import os
import time
import json
import base64
import hmac
import hashlib
from typing import Optional, Dict, Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.database import Base, get_db
from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.escalation import Escalation
from backend.app.models.audit import AuditLog
from backend.app.scripts.seed_db import seed_database

# In-memory SQLite for fast, isolated testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def _urlsafe_b64encode(data: bytes) -> str:
    """Encodes bytes to base64url string without trailing '=' padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def generate_jwt_token(
    claims: Optional[Dict[str, Any]] = None,
    role: str = "Operator",
    secret: Optional[str] = None,
    exp_delta: int = 3600,
) -> str:
    """
    Generates a valid HMAC-SHA256 (HS256) signed JWT bearer token.
    Compatible with decode_and_verify_test_jwt and RFC 7519 standards.
    """
    secret_key = secret or getattr(settings, "JWT_SECRET", "dev_secret_key_bharattrip_2026")
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())

    default_sub = "user_mgr_01" if role == "Manager" else "user_op_01"
    default_email = "manager@bharattrip.com" if role == "Manager" else "operator@bharattrip.com"

    payload = {
        "sub": default_sub,
        "email": default_email,
        "role": role,
        "iat": now,
        "exp": now + exp_delta,
    }
    if claims:
        payload.update(claims)
        if "iat" not in claims:
            payload["iat"] = now
        if "exp" not in claims and exp_delta != 3600:
            payload["exp"] = now + exp_delta

    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    header_b64 = _urlsafe_b64encode(header_json)
    payload_b64 = _urlsafe_b64encode(payload_json)

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _urlsafe_b64encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


@pytest.fixture(scope="function")
def db_session():
    """Create fresh database tables and session for each test function."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def seeded_db(db_session: Session):
    """
    Populates in-memory database with baseline seed records from CSVs
    and ensures canonical reference records exist for multi-milestone integration tests.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data")
    seed_database(db=db_session, force=True, data_dir=data_dir)

    # Ensure canonical reference tickets exist for integration tests
    rf1001 = db_session.query(SupportTicket).filter_by(ticket_id="RF-1001").first()
    if not rf1001:
        rf1001 = SupportTicket(
            ticket_id="RF-1001",
            agent="Peak Journeys",
            route="DEL-BOM",
            refund_amount=15000.0,
            request_date="25-05-2026",
            last_updated="31-05-2026",
            status="Pending",
            handled_by="Aditi M.",
            channel="WhatsApp",
            notes="refund requested, informed agent",
        )
        db_session.add(rf1001)
    else:
        rf1001.agent = "Peak Journeys"

    rf1002 = db_session.query(SupportTicket).filter_by(ticket_id="RF-1002").first()
    if not rf1002:
        rf1002 = SupportTicket(
            ticket_id="RF-1002",
            agent="GoFly Holidays",
            route="BLR-MAA",
            refund_amount=8500.0,
            request_date="26-05-2026",
            last_updated="01-06-2026",
            status="Refund Done",
            handled_by="Faizan K.",
            channel="WhatsApp",
            notes="Processed and completed",
        )
        db_session.add(rf1002)
    else:
        rf1002.status = "Refund Done"
        rf1002.route = "BLR-MAA"

    db_session.commit()
    return db_session


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_manager_token() -> str:
    """Returns a valid signed JWT bearer token with Manager role."""
    return generate_jwt_token(role="Manager")


@pytest.fixture
def mock_operator_token() -> str:
    """Returns a valid signed JWT bearer token with Operator role."""
    return generate_jwt_token(role="Operator")


@pytest.fixture
def mock_expired_token() -> str:
    """Returns an expired JWT bearer token."""
    return generate_jwt_token(claims={"exp": int(time.time()) - 3600})


@pytest.fixture
def manager_auth_headers(mock_manager_token: str) -> dict:
    """HTTP headers dict with Bearer token for Manager role."""
    return {"Authorization": f"Bearer {mock_manager_token}"}


@pytest.fixture
def operator_auth_headers(mock_operator_token: str) -> dict:
    """HTTP headers dict with Bearer token for Operator role."""
    return {"Authorization": f"Bearer {mock_operator_token}"}


@pytest.fixture
def sample_support_ticket(db_session):
    """Inserts a sample SupportTicket for tests."""
    ticket = SupportTicket(
        ticket_id="RF-9999",
        agent="Alpha Travels",
        route="DEL-BOM",
        refund_amount=12500.0,
        request_date="01-06-2026",
        last_updated="05-06-2026",
        status="Pending",
        handled_by="Agent A",
        channel="WhatsApp",
        notes="Urgent processing required",
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)
    return ticket


@pytest.fixture
def sample_finance_record(db_session):
    """Inserts a sample FinanceRecord for tests."""
    record = FinanceRecord(
        ref_no="RF-9999",
        agent_name="Alpha Travels",
        sector="DEL-BOM",
        amount_paid=11000.0,
        deduction=1500.0,
        received_on="02-06-2026",
        processed_on="06-06-2026",
        payout_status="Refund Done",
        approved_by="N. Iyer",
        remarks="Deduction applied per policy",
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture
def sample_escalation(db_session):
    """Inserts a sample Escalation for tests."""
    esc = Escalation(
        escalation_id="ESC-999",
        raised_on="05-06-2026",
        ticket_id="RF-9999",
        raised_by="Agent",
        agent="Alpha Travels",
        channel="Email",
        message="Deduction disputed by partner agency.",
        status="Open",
        resolved_on=None,
        days_open=3.0,
    )
    db_session.add(esc)
    db_session.commit()
    db_session.refresh(esc)
    return esc
