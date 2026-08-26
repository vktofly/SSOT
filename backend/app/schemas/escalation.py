"""
Pydantic Schemas for Escalations.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class EscalationBase(BaseModel):
    escalation_id: str = Field(..., alias="Escalation ID")
    raised_on: Optional[str] = Field(None, alias="Raised On")
    ticket_id: Optional[str] = Field(None, alias="Ticket ID")
    raised_by: str = Field("Agent", alias="Raised By")
    agent: str = Field(..., alias="Agent")
    channel: str = Field("Email", alias="Channel")
    message: str = Field(..., alias="Message")
    status: str = Field("Open", alias="Status")
    resolved_on: Optional[str] = Field(None, alias="Resolved On")
    days_open: float = Field(0.0, alias="Days Open")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class EscalationCreate(EscalationBase):
    pass


class EscalationUpdate(BaseModel):
    status: Optional[str] = Field(None, alias="Status")
    resolved_on: Optional[str] = Field(None, alias="Resolved On")
    days_open: Optional[float] = Field(None, alias="Days Open")
    message: Optional[str] = Field(None, alias="Message")
    ticket_id: Optional[str] = Field(None, alias="Ticket ID")
    raised_by: Optional[str] = Field(None, alias="Raised By")
    agent: Optional[str] = Field(None, alias="Agent")
    channel: Optional[str] = Field(None, alias="Channel")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class EscalationResponse(EscalationBase):
    pass


class EscalationListResponse(BaseModel):
    items: List[EscalationResponse]
    total: int
    skip: int
    limit: int
