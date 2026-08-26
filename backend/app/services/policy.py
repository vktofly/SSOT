"""
Airline Fare Policy RAG & SLA Forecaster Service.
Manages airline cancellation penalty rules, sector lookups, fallbacks,
and predictive 72-hour SLA breach forecasting.
"""
from typing import Optional, List, Dict, Any
import pandas as pd


AIRLINE_POLICY_KB: Dict[str, Dict[str, Any]] = {
    "DEL-DXB": {
        "route": "DEL-DXB",
        "carrier": "Emirates",
        "cancellation_fee": 3500.0,
        "policy_notes": "Flat ₹3,500 international sector cancellation fee per passenger.",
        "sla_hours": 48,
        "sector_type": "International",
        "is_registered": True,
    },
    "BLR-MAA": {
        "route": "BLR-MAA",
        "carrier": "IndiGo",
        "cancellation_fee": 1500.0,
        "policy_notes": "Standard domestic fee ₹1,500 per passenger.",
        "sla_hours": 24,
        "sector_type": "Domestic",
        "is_registered": True,
    },
    "DEL-SIN": {
        "route": "DEL-SIN",
        "carrier": "Singapore Airlines",
        "cancellation_fee": 4000.0,
        "policy_notes": "Tier-1 International: ₹4,000 deduction per passenger.",
        "sla_hours": 48,
        "sector_type": "International",
        "is_registered": True,
    },
    "DEL-BOM": {
        "route": "DEL-BOM",
        "carrier": "Air India",
        "cancellation_fee": 2000.0,
        "policy_notes": "Metro trunk route: ₹2,000 standard deduction.",
        "sla_hours": 24,
        "sector_type": "Domestic",
        "is_registered": True,
    },
    "COK-DXB": {
        "route": "COK-DXB",
        "carrier": "Air India Express",
        "cancellation_fee": 3000.0,
        "policy_notes": "Gulf sector flat fee ₹3,000 + GST.",
        "sla_hours": 48,
        "sector_type": "International",
        "is_registered": True,
    },
    "MAA-CMB": {
        "route": "MAA-CMB",
        "carrier": "SriLankan Airlines",
        "cancellation_fee": 2500.0,
        "policy_notes": "Regional international: ₹2,500 deduction per passenger.",
        "sla_hours": 48,
        "sector_type": "International",
        "is_registered": True,
    },
}


def lookup_airline_fare_policy(route: str, carrier: Optional[str] = None) -> Dict[str, Any]:
    """
    RAG lookup for airline fare cancellation penalty rules.
    Normalizes sector input and gracefully falls back to International (₹3,500/48h) or Domestic (₹2,000/24h) policies.
    """
    clean_route = (route or "").strip().upper()
    
    if clean_route in AIRLINE_POLICY_KB:
        policy = AIRLINE_POLICY_KB[clean_route].copy()
        if carrier:
            policy["carrier"] = carrier
        return policy

    # Detect international sector via destination codes
    intl_airports = ["DXB", "SIN", "BKK", "KUL", "CMB", "KTM", "LHR", "JFK", "AUH", "DOH", "FRA", "CDG"]
    is_intl = any(code in clean_route for code in intl_airports)

    default_carrier = carrier or ("Emirates / Air India" if is_intl else "IndiGo / Air India")
    default_fee = 3500.0 if is_intl else 2000.0
    sla = 48 if is_intl else 24
    sector_type = "International" if is_intl else "Domestic"

    return {
        "route": clean_route or "UNSPECIFIED",
        "carrier": default_carrier,
        "cancellation_fee": default_fee,
        "policy_notes": f"Standard {sector_type} sector fare policy: flat ₹{default_fee:,.0f} deduction per passenger.",
        "sla_hours": sla,
        "sector_type": sector_type,
        "is_registered": False,
    }


def get_all_policy_rules() -> List[Dict[str, Any]]:
    """
    Returns all registered airline sector cancellation penalty rules.
    """
    return list(AIRLINE_POLICY_KB.values())


def evaluate_sla_breach_risk(ticket: Dict[str, Any], current_date: str = "2026-06-30") -> Dict[str, Any]:
    """
    Evaluates predictive SLA breach risk against the 72-hour threshold.
    Closed/settled tickets are marked safe ('Resolved').
    Open tickets open for >=72 hours are flagged 'High' risk with breach status True.
    """
    ticket_id = str(ticket.get("Ticket ID") or ticket.get("ticket_id") or "Unknown")
    logged_date_str = ticket.get("Request Date") or ticket.get("request_date")
    status_str = str(ticket.get("Status") or ticket.get("status") or "Pending").lower()

    if any(s in status_str for s in ["resolved", "closed", "refund done", "settled"]):
        return {
            "ticket_id": ticket_id,
            "agent": ticket.get("Agent") or ticket.get("agent"),
            "route": ticket.get("Route") or ticket.get("route"),
            "refund_amount": float(ticket.get("Refund Amount (INR)") or ticket.get("refund_amount") or 0.0),
            "request_date": logged_date_str,
            "hours_elapsed": 0,
            "is_breached": False,
            "risk_level": "Resolved",
            "warning": "Ticket already closed or settled.",
        }

    try:
        cur_dt = pd.to_datetime(current_date)
        if logged_date_str:
            log_dt = pd.to_datetime(logged_date_str, errors="coerce")
            if pd.isna(log_dt):
                log_dt = cur_dt - pd.Timedelta(days=4)
        else:
            log_dt = cur_dt - pd.Timedelta(days=4)
        elapsed_hours = max(0, int((cur_dt - log_dt).total_seconds() / 3600))
    except Exception:
        elapsed_hours = 96

    is_breached = elapsed_hours >= 72
    if elapsed_hours >= 72:
        risk_level = "High"
    elif elapsed_hours >= 48:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "ticket_id": ticket_id,
        "agent": ticket.get("Agent") or ticket.get("agent"),
        "route": ticket.get("Route") or ticket.get("route"),
        "refund_amount": float(ticket.get("Refund Amount (INR)") or ticket.get("refund_amount") or 0.0),
        "request_date": logged_date_str,
        "hours_elapsed": elapsed_hours,
        "is_breached": is_breached,
        "risk_level": risk_level,
        "warning": f"⚠️ Latency {elapsed_hours}h exceeds 72h threshold!" if is_breached else "Within standard SLA window.",
    }
