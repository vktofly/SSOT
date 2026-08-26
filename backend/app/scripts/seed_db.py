"""
Database Seeding & CSV-to-SQLite Hydration Script.
Parses baseline CSV datasets in data/ and populates data/ssot.db using SQLAlchemy ORM.
"""
import os
import re
import math
import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.database import engine, SessionLocal, Base
from backend.app.models.support import SupportTicket
from backend.app.models.finance import FinanceRecord
from backend.app.models.escalation import Escalation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def clean_money_string(value: Any) -> float:
    """Sanitizes monetary string representations removing currency symbols, commas, and whitespace."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return 0.0
        return float(value)
    
    val_str = str(value).replace(',', '').replace('₹', '').replace('INR', '').replace('$', '').strip()
    if not val_str or val_str.lower() in ('nan', 'none', 'null', '-', ''):
        return 0.0
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return 0.0


def clean_str(value: Any) -> Optional[str]:
    """Sanitizes strings by stripping whitespace and converting nan to None."""
    if value is None:
        return None
    val_str = str(value).strip()
    if not val_str or val_str.lower() in ('nan', 'none', 'null', ''):
        return None
    return val_str


def normalize_id(value: Any) -> Optional[str]:
    """
    Sanitizes and normalizes identifier keys, replacing spaces with hyphens
    (e.g., 'RF 1750' -> 'RF-1750', 'ESC 801' -> 'ESC-801').
    """
    val = clean_str(value)
    if not val:
        return None
    val = val.upper()
    val = re.sub(r'^(RF|ESC)\s+', r'\1-', val)
    return val


CANONICAL_AGENCIES: Dict[str, str] = {
    "sunrise trips": "Sunrise Trips",
    "wander agency": "Wander Agency",
    "skyline travels": "Skyline Travels",
    "ziptrip": "ZipTrip",
    "metro yatra": "Metro Yatra",
    "bluejet tours": "BlueJet Tours",
    "voyage desk": "Voyage Desk",
    "triphub": "TripHub",
    "gofly holidays": "GoFly Holidays",
    "peak journeys": "Peak Journeys",
    "nomad travel": "Nomad Travel",
    "global wings": "Global Wings",
    "orbit travels": "Orbit Travels",
    "pinnacle getaways": "Pinnacle Getaways",
    "coral voyages": "Coral Voyages",
    "lotus travel co": "Lotus Travel Co",
    "himalaya holidays": "Himalaya Holidays",
    "deccanfly": "DeccanFly",
    "kaveri tours": "Kaveri Tours",
    "anand travels": "Anand Travels",
    "safarnama travel": "SafarNama Travel",
    "yatri junction": "Yatri Junction",
}


def clean_agency_name(value: Any) -> Optional[str]:
    """Sanitizes agency names, removing extra whitespace and standardizing canonical casing."""
    val = clean_str(value)
    if not val:
        return None
    normalized_key = re.sub(r'\s+', ' ', val).strip().lower()
    if normalized_key in CANONICAL_AGENCIES:
        return CANONICAL_AGENCIES[normalized_key]
    return re.sub(r'\s+', ' ', val).strip().title()


def parse_support_csv(file_path: str) -> List[Dict[str, Any]]:
    """Parses and sanitizes data/Support_Tracker.csv."""
    if not os.path.exists(file_path):
        logger.warning("Support tracker CSV not found at: %s", file_path)
        return []

    df = pd.read_csv(file_path, skiprows=1)
    if 'Ticket ID' not in df.columns and len(df.columns) > 1:
        df.columns = df.iloc[0]
        df = df.drop(0)

    record_map: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        raw_ticket_id = normalize_id(row.get('Ticket ID'))
        if not raw_ticket_id:
            continue
        
        ticket_id = raw_ticket_id
        agent = clean_agency_name(row.get('Agent')) or "Unknown Agent"
        route = clean_str(row.get('Route'))
        refund_amount = clean_money_string(row.get('Refund Amount (INR)'))
        request_date = clean_str(row.get('Request Date'))
        last_updated = clean_str(row.get('Last Updated'))
        status = clean_str(row.get('Status')) or "Pending"
        handled_by = clean_str(row.get('Handled By'))
        channel = clean_str(row.get('Channel')) or "WhatsApp"
        notes = clean_str(row.get('Notes'))

        record_map[ticket_id] = {
            "ticket_id": ticket_id,
            "agent": agent,
            "route": route,
            "refund_amount": refund_amount,
            "request_date": request_date,
            "last_updated": last_updated,
            "status": status,
            "handled_by": handled_by,
            "channel": channel,
            "notes": notes,
        }
    return list(record_map.values())


def parse_finance_csv(file_path: str) -> List[Dict[str, Any]]:
    """Parses and sanitizes data/Finance_Tracker.csv."""
    if not os.path.exists(file_path):
        logger.warning("Finance tracker CSV not found at: %s", file_path)
        return []

    df = pd.read_csv(file_path, skiprows=1)
    if 'Ref No' not in df.columns and len(df.columns) > 1:
        df.columns = df.iloc[0]
        df = df.drop(0)

    record_map: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        raw_ref_no = normalize_id(row.get('Ref No'))
        if not raw_ref_no:
            continue

        ref_no = raw_ref_no
        agent_name = clean_agency_name(row.get('Agent Name')) or "Unknown Agent"
        sector = clean_str(row.get('Sector'))
        amount_paid = clean_money_string(row.get('Amount Paid (INR)'))
        deduction = clean_money_string(row.get('Deduction (INR)'))
        received_on = clean_str(row.get('Received On'))
        processed_on = clean_str(row.get('Processed On'))
        payout_status = clean_str(row.get('Payout Status')) or "Pending Payout"
        approved_by = clean_str(row.get('Approved By'))
        remarks = clean_str(row.get('Remarks'))

        record_map[ref_no] = {
            "ref_no": ref_no,
            "agent_name": agent_name,
            "sector": sector,
            "amount_paid": amount_paid,
            "deduction": deduction,
            "received_on": received_on,
            "processed_on": processed_on,
            "payout_status": payout_status,
            "approved_by": approved_by,
            "remarks": remarks,
        }
    return list(record_map.values())


def parse_escalations_csv(file_path: str) -> List[Dict[str, Any]]:
    """Parses and sanitizes data/Escalations.csv."""
    if not os.path.exists(file_path):
        logger.warning("Escalations CSV not found at: %s", file_path)
        return []

    df = pd.read_csv(file_path, skiprows=1)
    if 'Escalation ID' not in df.columns and len(df.columns) > 1:
        df.columns = df.iloc[0]
        df = df.drop(0)

    # Normalize columns
    col_map = {
        'Related Ticket / Ref': 'Ticket ID',
        'Agent / Team': 'Agent',
        'Complaint': 'Message'
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    record_map: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        raw_esc_id = normalize_id(row.get('Escalation ID'))
        if not raw_esc_id:
            continue

        escalation_id = raw_esc_id
        raised_on = clean_str(row.get('Raised On'))
        raw_ticket_id = normalize_id(row.get('Ticket ID'))
        ticket_id = raw_ticket_id if raw_ticket_id else None
        raised_by = clean_str(row.get('Raised By')) or "Agent"
        agent = clean_agency_name(row.get('Agent')) or "Unknown Agent"
        channel = clean_str(row.get('Channel')) or "Email"
        message = clean_str(row.get('Message')) or "No complaint message provided"
        status = clean_str(row.get('Status')) or "Open"
        resolved_on = clean_str(row.get('Resolved On'))
        
        days_open_val = row.get('Days Open')
        days_open = clean_money_string(days_open_val)

        record_map[escalation_id] = {
            "escalation_id": escalation_id,
            "raised_on": raised_on,
            "ticket_id": ticket_id,
            "raised_by": raised_by,
            "agent": agent,
            "channel": channel,
            "message": message,
            "status": status,
            "resolved_on": resolved_on,
            "days_open": days_open,
        }
    return list(record_map.values())


def seed_database(
    db: Optional[Session] = None,
    force: bool = False,
    data_dir: str = "data"
) -> Dict[str, int]:
    """
    Creates all database tables and seeds them with data parsed from CSV files.
    """
    Base.metadata.create_all(bind=engine)

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    counts = {"support": 0, "finance": 0, "escalations": 0}

    try:
        support_count = db.query(SupportTicket).count()
        finance_count = db.query(FinanceRecord).count()
        escalation_count = db.query(Escalation).count()

        if force or support_count == 0:
            if force and support_count > 0:
                db.query(SupportTicket).delete()
                db.commit()
            
            support_records = parse_support_csv(os.path.join(data_dir, "Support_Tracker.csv"))
            for item in support_records:
                ticket = SupportTicket(**item)
                db.add(ticket)
                counts["support"] += 1
            db.commit()
            logger.info("Seeded %d support tickets.", counts["support"])
        else:
            counts["support"] = support_count

        if force or finance_count == 0:
            if force and finance_count > 0:
                db.query(FinanceRecord).delete()
                db.commit()

            finance_records = parse_finance_csv(os.path.join(data_dir, "Finance_Tracker.csv"))
            for item in finance_records:
                rec = FinanceRecord(**item)
                db.add(rec)
                counts["finance"] += 1
            db.commit()
            logger.info("Seeded %d finance records.", counts["finance"])
        else:
            counts["finance"] = finance_count

        if force or escalation_count == 0:
            if force and escalation_count > 0:
                db.query(Escalation).delete()
                db.commit()

            escalation_records = parse_escalations_csv(os.path.join(data_dir, "Escalations.csv"))
            for item in escalation_records:
                esc = Escalation(**item)
                db.add(esc)
                counts["escalations"] += 1
            db.commit()
            logger.info("Seeded %d escalations.", counts["escalations"])
        else:
            counts["escalations"] = escalation_count

        return counts
    finally:
        if own_session:
            db.close()


def main():
    logger.info("Starting SSOT database hydration from CSV baselines...")
    res = seed_database(force=True)
    logger.info("Hydration complete! Seeded counts: %s", res)


if __name__ == "__main__":
    main()
