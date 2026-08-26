"""
Escalations CRUD Router.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.database import get_db
from backend.app.models.escalation import Escalation
from backend.app.schemas.escalation import (
    EscalationCreate,
    EscalationUpdate,
    EscalationResponse,
)

router = APIRouter(prefix="/escalations", tags=["Escalations"])


@router.get("", response_model=List[EscalationResponse])
@router.get("/", response_model=List[EscalationResponse], include_in_schema=False)
def list_escalations(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. Open, Resolved, In Review)"),
    agent: Optional[str] = Query(None, description="Filter by travel agent name"),
    channel: Optional[str] = Query(None, description="Filter by channel (e.g. Email, WhatsApp, Phone)"),
    ticket_id: Optional[str] = Query(None, description="Filter by related Ticket ID"),
    search: Optional[str] = Query(None, description="Search across escalation ID, ticket ID, agent, message"),
    skip: int = Query(0, ge=0, description="Pagination skip"),
    limit: int = Query(100, ge=1, le=1000, description="Pagination limit"),
    db: Session = Depends(get_db),
):
    """Retrieve partner escalations with optional filtering, search, and pagination."""
    query = db.query(Escalation)

    if status_filter:
        query = query.filter(Escalation.status.ilike(f"%{status_filter}%"))
    if agent:
        query = query.filter(Escalation.agent.ilike(f"%{agent}%"))
    if channel:
        query = query.filter(Escalation.channel.ilike(f"%{channel}%"))
    if ticket_id:
        query = query.filter(Escalation.ticket_id.ilike(f"%{ticket_id}%"))
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Escalation.escalation_id.ilike(search_pattern),
                Escalation.ticket_id.ilike(search_pattern),
                Escalation.agent.ilike(search_pattern),
                Escalation.message.ilike(search_pattern),
            )
        )

    escalations = query.offset(skip).limit(limit).all()
    return escalations


@router.post("", response_model=EscalationResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=EscalationResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_escalation(
    payload: EscalationCreate,
    db: Session = Depends(get_db),
):
    """Create a new escalation record."""
    norm_esc_id = payload.escalation_id.strip().upper()
    existing = db.query(Escalation).filter(Escalation.escalation_id == norm_esc_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Escalation with ID '{norm_esc_id}' already exists."
        )

    esc_data = payload.model_dump(by_alias=False)
    esc_data["escalation_id"] = norm_esc_id
    if esc_data.get("ticket_id"):
        esc_data["ticket_id"] = esc_data["ticket_id"].strip().upper()
    
    escalation = Escalation(**esc_data)
    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    return escalation


@router.get("/{escalation_id}", response_model=EscalationResponse)
def get_escalation(
    escalation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a single escalation by its Escalation ID."""
    norm_esc_id = escalation_id.strip().upper()
    escalation = db.query(Escalation).filter(Escalation.escalation_id == norm_esc_id).first()
    if not escalation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Escalation '{escalation_id}' not found."
        )
    return escalation


@router.patch("/{escalation_id}", response_model=EscalationResponse)
@router.put("/{escalation_id}", response_model=EscalationResponse)
def update_escalation(
    escalation_id: str,
    payload: EscalationUpdate,
    db: Session = Depends(get_db),
):
    """Update fields on an existing escalation record."""
    norm_esc_id = escalation_id.strip().upper()
    escalation = db.query(Escalation).filter(Escalation.escalation_id == norm_esc_id).first()
    if not escalation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Escalation '{escalation_id}' not found."
        )

    update_data = payload.model_dump(exclude_unset=True, by_alias=False)
    for key, value in update_data.items():
        if value is not None:
            if key == "ticket_id" and isinstance(value, str):
                value = value.strip().upper()
            setattr(escalation, key, value)

    db.commit()
    db.refresh(escalation)
    return escalation


@router.delete("/{escalation_id}", status_code=status.HTTP_200_OK)
def delete_escalation(
    escalation_id: str,
    db: Session = Depends(get_db),
):
    """Delete an escalation record by ID."""
    norm_esc_id = escalation_id.strip().upper()
    escalation = db.query(Escalation).filter(Escalation.escalation_id == norm_esc_id).first()
    if not escalation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Escalation '{escalation_id}' not found."
        )

    db.delete(escalation)
    db.commit()
    return {"success": True, "message": f"Escalation '{escalation_id}' deleted successfully."}

from pydantic import BaseModel

class ResolveRequest(BaseModel):
    raw_message: str
    channel: str = "WhatsApp"
    agency_name: Optional[str] = None
    agency_tier: str = "Standard"

@router.post("/resolve")
def resolve_escalation(
    payload: ResolveRequest,
    db: Session = Depends(get_db)
):
    from backend.app.services.ai_agent import escalation_app
    
    # Run the langgraph workflow
    initial_state = {
        "raw_message": payload.raw_message,
        "channel": payload.channel,
        "agency_name": payload.agency_name,
        "agency_tier": payload.agency_tier,
        "audit_trace": []
    }
    
    final_state = escalation_app.invoke(initial_state)
    
    return {
        "escalation_id": f"ESC-FLOW-AUTO",
        "priority_rank": final_state.get("priority_rank"),
        "urgency_level": final_state.get("urgency_level"),
        "extracted_entities": {
            "reference_id": final_state.get("reference_id"),
            "route": final_state.get("route"),
            "expected_refund_amount": final_state.get("expected_amount"),
            "intent": final_state.get("intent"),
            "missing_reference": final_state.get("missing_reference"),
            "confidence_score": final_state.get("confidence_score"),
        },
        "draft_response": final_state.get("draft_response"),
        "hitl_required": final_state.get("hitl_required"),
        "hitl_reason": final_state.get("hitl_reason"),
        "audit_trace": final_state.get("audit_trace"),
    }
