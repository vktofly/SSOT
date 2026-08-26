"""
FastAPI Router for Operations Metrics & RCA Endpoints (Milestone 3).
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.core.rbac import require_manager
from backend.app.schemas.auth import UserProfile
from backend.app.schemas.metrics import (
    DashboardMetricsResponse,
    RCAMetricsResponse,
    TrendsResponse,
    SLABreachResponse,
    CarrierPerformanceResponse,
)
from backend.app.services.metrics import (
    calculate_dashboard_telemetry,
    generate_rca_synthesis_report,
    calculate_operational_trends,
    calculate_carrier_performance,
    evaluate_sla_breaches,
)

router = APIRouter(prefix="/metrics", tags=["Operations Metrics & RCA"])


@router.get(
    "/dashboard",
    response_model=DashboardMetricsResponse,
    summary="Get Operations Dashboard Telemetry (Manager Only)",
)
def get_dashboard_metrics(
    window: str = Query("All (Feb–Jun 2026)", description="Temporal window filter"),
    agency: Optional[str] = Query(None, description="Optional agency filter"),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Returns aggregated KPI telemetry across Support, Finance, and Escalation datasets.
    """
    return calculate_dashboard_telemetry(db, window_filter=window, agency_filter=agency)


@router.get(
    "/rca",
    response_model=RCAMetricsResponse,
    summary="Get AI Root Cause Analysis (Manager Only)",
)
def get_rca(
    window: str = Query("All", description="Temporal filter for RCA"),
    force_refresh: bool = Query(False, description="Force fresh AI analysis synthesis"),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Synthesizes executive root cause briefing combining agency concentrations, latency, and failure modes.
    """
    return generate_rca_synthesis_report(db, window=window, force_refresh=force_refresh)


@router.post(
    "/rca-synthesis",
    response_model=RCAMetricsResponse,
    summary="Synthesize AI Root Cause Analysis (Manager Only)",
)
def post_rca_synthesis(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    POST endpoint for triggering fresh AI RCA synthesis.
    """
    window = payload.get("window", "All")
    return generate_rca_synthesis_report(db, window=window, force_refresh=True)


@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Get Historical Trend Telemetry (Manager Only)",
)
def get_trends(
    window: str = Query("All", description="Time window for trends"),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Returns time-series telemetry data points across monthly operational cycles.
    """
    return calculate_operational_trends(db, window=window)


@router.get(
    "/sla-breaches",
    response_model=SLABreachResponse,
    summary="Predictive SLA Breach Telemetry (Manager Only)",
)
def get_sla_breaches(
    current_date: str = Query("2026-06-30", description="Reference baseline date"),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Evaluates all active support tickets against the 72-hour turnaround threshold.
    """
    return evaluate_sla_breaches(db, current_date=current_date)


@router.get(
    "/carrier-performance",
    response_model=CarrierPerformanceResponse,
    summary="Carrier Operational Reliability Telemetry (Manager Only)",
)
def get_carrier_performance(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Returns carrier reliability, dispute rates, and average penalty metrics per airline.
    """
    return calculate_carrier_performance(db)
