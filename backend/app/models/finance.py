"""
Finance Record ORM Model.
"""
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Float, Text
from backend.app.database import Base


class FinanceRecord(Base):
    __tablename__ = "finance_tracker"

    ref_no = Column("Ref No", String(50), primary_key=True, index=True)
    agent_name = Column("Agent Name", String(150), nullable=False, index=True)
    sector = Column("Sector", String(50), nullable=True)
    amount_paid = Column("Amount Paid (INR)", Float, default=0.0)
    deduction = Column("Deduction (INR)", Float, default=0.0)
    received_on = Column("Received On", String(30), nullable=True)
    processed_on = Column("Processed On", String(30), nullable=True)
    payout_status = Column("Payout Status", String(50), default="Pending Payout", index=True)
    approved_by = Column("Approved By", String(100), nullable=True)
    remarks = Column("Remarks", Text, nullable=True)

    def to_dict(self, use_aliases: bool = True) -> Dict[str, Any]:
        """Convert ORM model to dictionary with alias or snake_case keys."""
        if use_aliases:
            return {
                "Ref No": self.ref_no,
                "Agent Name": self.agent_name,
                "Sector": self.sector,
                "Amount Paid (INR)": self.amount_paid,
                "Deduction (INR)": self.deduction,
                "Received On": self.received_on,
                "Processed On": self.processed_on,
                "Payout Status": self.payout_status,
                "Approved By": self.approved_by,
                "Remarks": self.remarks,
            }
        return {
            "ref_no": self.ref_no,
            "agent_name": self.agent_name,
            "sector": self.sector,
            "amount_paid": self.amount_paid,
            "deduction": self.deduction,
            "received_on": self.received_on,
            "processed_on": self.processed_on,
            "payout_status": self.payout_status,
            "approved_by": self.approved_by,
            "remarks": self.remarks,
        }
