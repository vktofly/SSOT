"""
Support Ticket CRUD Router.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.database import get_db
from backend.app.models.support import SupportTicket
from backend.app.schemas.support import (
    SupportTicketCreate,
    SupportTicketUpdate,
    SupportTicketResponse,
)

router = APIRouter(prefix="/support-tickets", tags=["Support Tickets"])


@router.get("", response_model=List[SupportTicketResponse])
@router.get("/", response_model=List[SupportTicketResponse], include_in_schema=False)
def list_support_tickets(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. Pending, Closed, Processing)"),
    agent: Optional[str] = Query(None, description="Filter by travel agent name"),
    search: Optional[str] = Query(None, description="Search across ticket ID, agent, route, notes"),
    skip: int = Query(0, ge=0, description="Pagination skip"),
    limit: int = Query(100, ge=1, le=1000, description="Pagination limit"),
    db: Session = Depends(get_db),
):
    """Retrieve support tickets with optional filtering, search, and pagination."""
    query = db.query(SupportTicket)

    if status_filter:
        query = query.filter(SupportTicket.status.ilike(f"%{status_filter}%"))
    if agent:
        query = query.filter(SupportTicket.agent.ilike(f"%{agent}%"))
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                SupportTicket.ticket_id.ilike(search_pattern),
                SupportTicket.agent.ilike(search_pattern),
                SupportTicket.route.ilike(search_pattern),
                SupportTicket.notes.ilike(search_pattern),
            )
        )

    tickets = query.offset(skip).limit(limit).all()
    return tickets


@router.post("", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_support_ticket(
    payload: SupportTicketCreate,
    db: Session = Depends(get_db),
):
    """Create a new support ticket record."""
    norm_ticket_id = payload.ticket_id.strip().upper()
    existing = db.query(SupportTicket).filter(SupportTicket.ticket_id == norm_ticket_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Support ticket with ID '{norm_ticket_id}' already exists."
        )

    ticket_data = payload.model_dump(by_alias=False)
    ticket_data["ticket_id"] = norm_ticket_id
    ticket = SupportTicket(**ticket_data)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=SupportTicketResponse)
def get_support_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a single support ticket by its Ticket ID."""
    norm_ticket_id = ticket_id.strip().upper()
    ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == norm_ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found."
        )
    return ticket


@router.patch("/{ticket_id}", response_model=SupportTicketResponse)
@router.put("/{ticket_id}", response_model=SupportTicketResponse)
def update_support_ticket(
    ticket_id: str,
    payload: SupportTicketUpdate,
    db: Session = Depends(get_db),
):
    """Update fields on an existing support ticket."""
    norm_ticket_id = ticket_id.strip().upper()
    ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == norm_ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found."
        )

    update_data = payload.model_dump(exclude_unset=True, by_alias=False)
    for key, value in update_data.items():
        if value is not None:
            setattr(ticket, key, value)

    db.commit()
    db.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_200_OK)
def delete_support_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    """Delete a support ticket record by ID."""
    norm_ticket_id = ticket_id.strip().upper()
    ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == norm_ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found."
        )

    db.delete(ticket)
    db.commit()
    return {"success": True, "message": f"Support ticket '{ticket_id}' deleted successfully."}
