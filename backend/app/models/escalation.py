"""
Escalation ORM Model.
"""
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Float, Text
from backend.app.database import Base


class Escalation(Base):
    __tablename__ = "escalations"

    escalation_id = Column("Escalation ID", String(50), primary_key=True, index=True)
    raised_on = Column("Raised On", String(30), nullable=True)
    ticket_id = Column("Ticket ID", String(50), nullable=True, index=True)
    raised_by = Column("Raised By", String(50), default="Agent")
    agent = Column("Agent", String(150), nullable=False, index=True)
    channel = Column("Channel", String(50), default="Email")
    message = Column("Message", Text, nullable=False)
    status = Column("Status", String(50), default="Open", index=True)
    resolved_on = Column("Resolved On", String(30), nullable=True)
    days_open = Column("Days Open", Float, default=0.0)

    def to_dict(self, use_aliases: bool = True) -> Dict[str, Any]:
        """Convert ORM model to dictionary with alias or snake_case keys."""
        if use_aliases:
            return {
                "Escalation ID": self.escalation_id,
                "Raised On": self.raised_on,
                "Ticket ID": self.ticket_id,
                "Raised By": self.raised_by,
                "Agent": self.agent,
                "Channel": self.channel,
                "Message": self.message,
                "Status": self.status,
                "Resolved On": self.resolved_on,
                "Days Open": self.days_open,
            }
        return {
            "escalation_id": self.escalation_id,
            "raised_on": self.raised_on,
            "ticket_id": self.ticket_id,
            "raised_by": self.raised_by,
            "agent": self.agent,
            "channel": self.channel,
            "message": self.message,
            "status": self.status,
            "resolved_on": self.resolved_on,
            "days_open": self.days_open,
        }
