"""
Audit Log ORM Model.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, Text, DateTime
from backend.app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    user_id = Column(String(100), nullable=False)
    user_role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "action": self.action,
            "details": self.details,
        }
