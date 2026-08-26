"""
Pydantic Schemas for Finance Records.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class FinanceRecordBase(BaseModel):
    ref_no: str = Field(..., alias="Ref No")
    agent_name: str = Field(..., alias="Agent Name")
    sector: Optional[str] = Field(None, alias="Sector")
    amount_paid: float = Field(0.0, alias="Amount Paid (INR)")
    deduction: float = Field(0.0, alias="Deduction (INR)")
    received_on: Optional[str] = Field(None, alias="Received On")
    processed_on: Optional[str] = Field(None, alias="Processed On")
    payout_status: str = Field("Pending Payout", alias="Payout Status")
    approved_by: Optional[str] = Field(None, alias="Approved By")
    remarks: Optional[str] = Field(None, alias="Remarks")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class FinanceRecordCreate(FinanceRecordBase):
    pass


class FinanceRecordUpdate(BaseModel):
    payout_status: Optional[str] = Field(None, alias="Payout Status")
    remarks: Optional[str] = Field(None, alias="Remarks")
    approved_by: Optional[str] = Field(None, alias="Approved By")
    amount_paid: Optional[float] = Field(None, alias="Amount Paid (INR)")
    deduction: Optional[float] = Field(None, alias="Deduction (INR)")
    processed_on: Optional[str] = Field(None, alias="Processed On")
    sector: Optional[str] = Field(None, alias="Sector")
    agent_name: Optional[str] = Field(None, alias="Agent Name")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class FinanceRecordResponse(FinanceRecordBase):
    pass


class FinanceRecordListResponse(BaseModel):
    items: List[FinanceRecordResponse]
    total: int
    skip: int
    limit: int
