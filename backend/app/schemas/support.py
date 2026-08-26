"""
Pydantic Schemas for Support Tickets.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class SupportTicketBase(BaseModel):
    ticket_id: str = Field(..., alias="Ticket ID")
    agent: str = Field(..., alias="Agent")
    route: Optional[str] = Field(None, alias="Route")
    refund_amount: float = Field(0.0, alias="Refund Amount (INR)")
    request_date: Optional[str] = Field(None, alias="Request Date")
    last_updated: Optional[str] = Field(None, alias="Last Updated")
    status: str = Field("Pending", alias="Status")
    handled_by: Optional[str] = Field(None, alias="Handled By")
    channel: str = Field("WhatsApp", alias="Channel")
    notes: Optional[str] = Field(None, alias="Notes")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class SupportTicketCreate(SupportTicketBase):
    pass


class SupportTicketUpdate(BaseModel):
    status: Optional[str] = Field(None, alias="Status")
    notes: Optional[str] = Field(None, alias="Notes")
    refund_amount: Optional[float] = Field(None, alias="Refund Amount (INR)")
    handled_by: Optional[str] = Field(None, alias="Handled By")
    agent: Optional[str] = Field(None, alias="Agent")
    route: Optional[str] = Field(None, alias="Route")
    channel: Optional[str] = Field(None, alias="Channel")
    last_updated: Optional[str] = Field(None, alias="Last Updated")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class SupportTicketResponse(SupportTicketBase):
    pass


class SupportTicketListResponse(BaseModel):
    items: List[SupportTicketResponse]
    total: int
    skip: int
    limit: int
