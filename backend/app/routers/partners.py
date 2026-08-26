"""
FastAPI Router for Partner Health Matrix & Airline Policy RAG Endpoints (Milestone 3).
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.core.rbac import require_manager, require_operator, get_current_user
from backend.app.schemas.auth import UserProfile
from backend.app.schemas.partners import (
    PartnerMatrixResponse,
    PartnerDetailResponse,
    PartnerSentimentAnalysisRequest,
    PartnerSentimentAnalysisResponse,
    PartnerOutreachRequest,
    PartnerOutreachResponse,
    PolicyRuleResponse,
    PolicyRuleListResponse,
    PredictSLABreachRequest,
    PredictSLABreachResponse,
)
from backend.app.services.partner_health import (
    get_partner_health_matrix_data,
    get_partner_agency_detail,
    analyze_partner_sentiment_scoring,
    dispatch_partner_outreach_action,
)
from backend.app.services.policy import (
    lookup_airline_fare_policy,
    get_all_policy_rules,
    evaluate_sla_breach_risk,
)

router = APIRouter(tags=["Partner Health Matrix & Policy RAG"])


# ---------------------------------------------------------------------------
# Partner Health & Churn Risk Matrix Endpoints (Manager Only)
# ---------------------------------------------------------------------------

@router.get(
    "/partners/matrix",
    response_model=PartnerMatrixResponse,
    summary="Get Partner Health & Churn Risk Matrix (Manager Only)",
)
def get_partner_matrix(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Returns aggregated fleet-wide B2B partner health profiles, sentiment indices, and churn risk levels.
    """
    return get_partner_health_matrix_data(db)


@router.get(
    "/partners/policies",
    response_model=PolicyRuleListResponse,
    summary="List All Registered Airline Policies (Manager/Operator)",
)
def get_policies_list(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_operator),
):
    """
    Returns all registered airline sector cancellation penalty rules.
    """
    rules = get_all_policy_rules()
    return {"items": rules, "total": len(rules)}


@router.get(
    "/partners/policies/{route}",
    response_model=PolicyRuleResponse,
    summary="Get Policy Rule by Route (Manager/Operator)",
)
def get_policy_by_route(
    route: str,
    carrier: Optional[str] = Query(None, description="Optional carrier name override"),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_operator),
):
    """
    Retrieves airline fare cancellation policy for a specific flight sector.
    """
    return lookup_airline_fare_policy(route=route, carrier=carrier)


@router.get(
    "/partners/policy",
    response_model=PolicyRuleResponse,
    summary="Query Airline Policy via Params (Operator/Manager)",
)
def query_policy(
    route: str = Query(..., description="Flight sector (e.g. DEL-DXB)"),
    carrier: Optional[str] = Query(None, description="Optional carrier"),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_operator),
):
    """
    Query parameter based lookup for airline cancellation penalty rules.
    """
    return lookup_airline_fare_policy(route=route, carrier=carrier)


@router.get(
    "/partners/{agency_name}",
    response_model=PartnerDetailResponse,
    summary="Get Partner Agency Profile (Manager Only)",
)
def get_agency_detail(
    agency_name: str,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Retrieves detailed operational profile and recent ticket history for a single travel partner.
    """
    return get_partner_agency_detail(db, agency_name=agency_name)


@router.post(
    "/partners/sentiment-analysis",
    response_model=PartnerSentimentAnalysisResponse,
    summary="Evaluate Message Tone & Urgency (Operator/Manager)",
)
def post_sentiment_analysis(
    payload: PartnerSentimentAnalysisRequest,
    current_user: UserProfile = Depends(require_operator),
):
    """
    Runs NLP sentiment scoring, urgency classification, and priority ranking on inbound text.
    """
    return analyze_partner_sentiment_scoring(
        text=payload.message,
        agency_tier=payload.agency_tier,
    )


@router.post(
    "/partners/outreach",
    response_model=PartnerOutreachResponse,
    summary="Dispatch Partner Outreach Action (Manager Only)",
)
def post_partner_outreach(
    payload: PartnerOutreachRequest,
    current_user: UserProfile = Depends(require_manager),
):
    """
    Dispatches a proactive reassurance outreach intervention for an at-risk partner.
    """
    return dispatch_partner_outreach_action(
        agency_name=payload.agency_name,
        outreach_type=payload.outreach_type,
        custom_note=payload.custom_note,
        user_id=current_user.user_id,
    )


# ---------------------------------------------------------------------------
# Policy & SLA Forecaster Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/policy/airline-penalty",
    response_model=PolicyRuleResponse,
    summary="Lookup Airline Fare Penalty Rule",
)
def lookup_airline_penalty_endpoint(
    route: str = Query(..., description="Flight sector (e.g. DEL-DXB)"),
    carrier: Optional[str] = Query(None, description="Optional carrier"),
    current_user: UserProfile = Depends(require_operator),
):
    """
    RAG lookup for airline fare cancellation penalty rules.
    """
    return lookup_airline_fare_policy(route=route, carrier=carrier)


@router.post(
    "/policy/predict-sla-breach",
    response_model=PredictSLABreachResponse,
    summary="Predictive SLA Breach Forecaster",
)
def predict_sla_breach_endpoint(
    payload: PredictSLABreachRequest,
    current_user: UserProfile = Depends(require_operator),
):
    """
    Evaluates whether an active ticket exceeds or approaches the 72h SLA turnaround threshold.
    """
    ticket_dict = {
        "Ticket ID": payload.ticket_id,
        "Request Date": payload.request_date,
        "Status": payload.status,
    }
    cur_date = payload.current_date or "2026-06-30"
    res = evaluate_sla_breach_risk(ticket_dict, current_date=cur_date)
    return {
        "ticket_id": res["ticket_id"],
        "is_breached": res["is_breached"],
        "hours_elapsed": res["hours_elapsed"],
        "risk_level": res["risk_level"],
        "warning": res["warning"],
    }
