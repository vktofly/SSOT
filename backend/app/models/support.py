"""
Support Ticket ORM Model.
"""
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Float, Text
from backend.app.database import Base


class SupportTicket(Base):
    __tablename__ = "support_tracker"

    ticket_id = Column("Ticket ID", String(50), primary_key=True, index=True)
    agent = Column("Agent", String(150), nullable=False, index=True)
    route = Column("Route", String(50), nullable=True)
    refund_amount = Column("Refund Amount (INR)", Float, default=0.0)
    request_date = Column("Request Date", String(30), nullable=True)
    last_updated = Column("Last Updated", String(30), nullable=True)
    status = Column("Status", String(50), default="Pending", index=True)
    handled_by = Column("Handled By", String(100), nullable=True)
    channel = Column("Channel", String(50), default="WhatsApp")
    notes = Column("Notes", Text, nullable=True)

    def to_dict(self, use_aliases: bool = True) -> Dict[str, Any]:
        """Convert ORM model to dictionary with alias or snake_case keys."""
        if use_aliases:
            return {
                "Ticket ID": self.ticket_id,
                "Agent": self.agent,
                "Route": self.route,
                "Refund Amount (INR)": self.refund_amount,
                "Request Date": self.request_date,
                "Last Updated": self.last_updated,
                "Status": self.status,
                "Handled By": self.handled_by,
                "Channel": self.channel,
                "Notes": self.notes,
            }
        return {
            "ticket_id": self.ticket_id,
            "agent": self.agent,
            "route": self.route,
            "refund_amount": self.refund_amount,
            "request_date": self.request_date,
            "last_updated": self.last_updated,
            "status": self.status,
            "handled_by": self.handled_by,
            "channel": self.channel,
            "notes": self.notes,
        }
