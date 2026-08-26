"""
Pydantic Schemas for Audit Logs.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class AuditLogBase(BaseModel):
    user_id: str
    user_role: str
    action: str
    details: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True
    )


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogResponse(AuditLogBase):
    id: int
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
