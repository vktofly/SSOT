"""
FastAPI Router for Discrepancy & Reconciliation Endpoints (Milestone 3).
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.core.rbac import require_manager, require_operator, get_current_user
from backend.app.schemas.auth import UserProfile
from backend.app.schemas.reconciliation import (
    MismatchItem,
    MismatchListResponse,
    OrphanResponse,
    ReconciliationSummary,
    ResolveMismatchRequest,
    ResolveMismatchResponse,
    LinkOrphanRequest,
    LinkOrphanResponse,
    BatchResolveMismatchesRequest,
    BatchResolveMismatchesResponse,
    AIEntityResolutionRequest,
    AIEntityResolutionResponse,
    DraftExplanationRequest,
    DraftExplanationResponse,
    ProactiveNotificationRequest,
    ProactiveNotificationResponse,
)
from backend.app.services.reconciliation import (
    calculate_mismatches_from_db,
    calculate_orphans_from_db,
    get_reconciliation_summary,
    resolve_discrepancy,
    link_orphan_ticket,
    batch_resolve_discrepancies,
    fuzzy_match_orphans,
    draft_discrepancy_explanation,
    generate_lifecycle_notification,
)

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation & Discrepancies"])


@router.get(
    "/mismatches",
    response_model=List[MismatchItem],
    summary="List Discrepancy Mismatches (Manager Only)",
)
def get_mismatches(
    risk_level: Optional[str] = Query(None, description="Optional risk tier filter ('Normal' or 'High')"),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Retrieves all financial variances between Support Ticket promised refunds and Finance bank payouts.
    """
    return calculate_mismatches_from_db(db, risk_level_filter=risk_level)


@router.get(
    "/orphans",
    response_model=OrphanResponse,
    summary="List Orphaned Support and Finance Records (Manager Only)",
)
def get_orphans(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Detects tickets missing in the corresponding ledger:
    - missing_in_finance: Approved Support tickets with no Finance payout record.
    - missing_in_support: Finance payouts executed without an originating Support ticket.
    """
    missing_in_fin, missing_in_sup = calculate_orphans_from_db(db)
    from collections import Counter
    agent_counts = Counter([str(m.get("agent", "Unknown")) for m in missing_in_fin])
    high_risk_agents = [agent for agent, count in agent_counts.items() if count > 2 and agent != "Unknown"]

    return {
        "missing_in_finance": missing_in_fin,
        "missing_in_support": missing_in_sup,
        "total_missing_finance": len(missing_in_fin),
        "total_missing_support": len(missing_in_sup),
        "high_risk_agents": high_risk_agents,
    }


@router.get(
    "/summary",
    response_model=ReconciliationSummary,
    summary="Reconciliation Cockpit Summary (Manager Only)",
)
def get_summary(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Returns executive metrics summarizing total discrepancies, orphans, and fleet financial variance.
    """
    return get_reconciliation_summary(db)


@router.post(
    "/resolve-mismatch",
    response_model=ResolveMismatchResponse,
    summary="Settle Single Discrepancy (Manager Only)",
)
@router.post(
    "/resolve",
    response_model=ResolveMismatchResponse,
    include_in_schema=False,
)
def resolve_mismatch_endpoint(
    payload: ResolveMismatchRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Settles a financial discrepancy, mutates SupportTicket status, and writes an audit log.
    """
    return resolve_discrepancy(
        db=db,
        ticket_id=payload.ticket_id,
        new_status=payload.status,
        notes=payload.notes,
        user_id=current_user.user_id,
        user_role=current_user.role,
        resolution_type=payload.resolution_type,
        adjusted_amount=payload.adjusted_amount,
        send_communication=payload.send_communication,
        communication_draft=payload.communication_draft,
    )


@router.post(
    "/batch-resolve",
    response_model=BatchResolveMismatchesResponse,
    summary="Batch Resolve Multiple Discrepancies (Manager Only)",
)
def batch_resolve_endpoint(
    payload: BatchResolveMismatchesRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Settles multiple discrepancies simultaneously with transaction safety.
    """
    return batch_resolve_discrepancies(
        db=db,
        ticket_ids=payload.ticket_ids,
        resolution_type=payload.resolution_type,
        new_status=payload.status,
        auto_draft_explanations=payload.auto_draft_explanations,
        user_id=current_user.user_id,
        user_role=current_user.role,
    )


@router.post(
    "/link-orphan",
    response_model=LinkOrphanResponse,
    summary="Link Orphan Record (Manager Only)",
)
@router.post(
    "/merge-orphan",
    response_model=LinkOrphanResponse,
    include_in_schema=False,
)
def link_orphan_endpoint(
    payload: LinkOrphanRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Links an orphaned Support ticket with an unlinked Finance record and logs to audit trail.
    """
    return link_orphan_ticket(
        db=db,
        support_ticket_id=payload.support_ticket_id,
        finance_ref_no=payload.finance_ref_no,
        user_id=current_user.user_id,
        user_role=current_user.role,
        notes=payload.notes,
    )


@router.post(
    "/fuzzy-match-orphans",
    summary="AI Metadata Linkage for Orphans (Manager Only)",
)
def fuzzy_match_orphans_endpoint(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_manager),
):
    """
    Finds high-confidence links between orphaned tickets using Agent, Route, and Amount similarity.
    """
    matches = fuzzy_match_orphans(db, threshold=0.70)
    missing_fin, missing_sup = calculate_orphans_from_db(db)
    return {
        "matches": matches,
        "total_matches": len(matches),
        "unmatched_support_count": max(0, len(missing_fin) - len(matches)),
        "unmatched_finance_count": max(0, len(missing_sup) - len(matches)),
    }


@router.post(
    "/draft-explanation",
    response_model=DraftExplanationResponse,
    summary="AI Draft Tariff Deduction Explanation",
)
@router.post(
    "/draft-message",
    response_model=DraftExplanationResponse,
    include_in_schema=False,
)
def draft_explanation_endpoint(
    payload: DraftExplanationRequest,
    current_user: UserProfile = Depends(require_operator),
):
    """
    Generates a partner email explaining carrier cancellation fees and tariff deductions.
    """
    return draft_discrepancy_explanation(
        agent=payload.agent,
        route=payload.route or "DEL-DXB",
        ticket_id=payload.ticket_id,
        support_amt=payload.support_amount,
        finance_amt=payload.finance_amount,
        deduction=payload.deduction,
        reason=payload.reason,
    )


@router.post(
    "/proactive-notification",
    response_model=ProactiveNotificationResponse,
    summary="Generate Proactive Lifecycle Notification",
)
@router.post(
    "/proactive-alert",
    response_model=ProactiveNotificationResponse,
    include_in_schema=False,
)
def proactive_notification_endpoint(
    payload: ProactiveNotificationRequest,
    current_user: UserProfile = Depends(require_operator),
):
    """
    Generates a multi-channel proactive lifecycle update notification for travel partners.
    """
    return generate_lifecycle_notification(
        ticket_id=payload.ticket_id,
        agent_name=payload.agent_name,
        route=payload.route,
        stage=payload.stage,
        amount=payload.amount,
        deduction=payload.deduction,
        channel=payload.channel,
    )
