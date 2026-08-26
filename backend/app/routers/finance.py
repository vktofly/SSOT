"""
Finance Record CRUD Router.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.database import get_db
from backend.app.core.rbac import require_role
from backend.app.models.finance import FinanceRecord
from backend.app.schemas.finance import (
    FinanceRecordCreate,
    FinanceRecordUpdate,
    FinanceRecordResponse,
)

router = APIRouter(
    prefix="/finance-records",
    tags=["Finance Records"],
    dependencies=[Depends(require_role(["Manager"]))],
)



@router.get("", response_model=List[FinanceRecordResponse])
@router.get("/", response_model=List[FinanceRecordResponse], include_in_schema=False)
def list_finance_records(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by payout status (e.g. Refund Done, Pending Payout, Declined)"),
    payout_status: Optional[str] = Query(None, description="Explicit payout status filter"),
    agent_name: Optional[str] = Query(None, description="Filter by travel agent name"),
    search: Optional[str] = Query(None, description="Search across ref no, agent name, sector, remarks"),
    skip: int = Query(0, ge=0, description="Pagination skip"),
    limit: int = Query(100, ge=1, le=1000, description="Pagination limit"),
    db: Session = Depends(get_db),
):
    """Retrieve finance settlement records with optional filtering, search, and pagination."""
    query = db.query(FinanceRecord)

    effective_status = payout_status or status_filter
    if effective_status:
        query = query.filter(FinanceRecord.payout_status.ilike(f"%{effective_status}%"))
    if agent_name:
        query = query.filter(FinanceRecord.agent_name.ilike(f"%{agent_name}%"))
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                FinanceRecord.ref_no.ilike(search_pattern),
                FinanceRecord.agent_name.ilike(search_pattern),
                FinanceRecord.sector.ilike(search_pattern),
                FinanceRecord.remarks.ilike(search_pattern),
            )
        )

    records = query.offset(skip).limit(limit).all()
    return records


@router.post("", response_model=FinanceRecordResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=FinanceRecordResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_finance_record(
    payload: FinanceRecordCreate,
    db: Session = Depends(get_db),
):
    """Create a new finance settlement record."""
    norm_ref_no = payload.ref_no.strip().upper()
    existing = db.query(FinanceRecord).filter(FinanceRecord.ref_no == norm_ref_no).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Finance record with Ref No '{norm_ref_no}' already exists."
        )

    record_data = payload.model_dump(by_alias=False)
    record_data["ref_no"] = norm_ref_no
    record = FinanceRecord(**record_data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{ref_no}", response_model=FinanceRecordResponse)
def get_finance_record(
    ref_no: str,
    db: Session = Depends(get_db),
):
    """Retrieve a single finance record by its Ref No."""
    norm_ref_no = ref_no.strip().upper()
    record = db.query(FinanceRecord).filter(FinanceRecord.ref_no == norm_ref_no).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finance record '{ref_no}' not found."
        )
    return record


@router.patch("/{ref_no}", response_model=FinanceRecordResponse)
@router.put("/{ref_no}", response_model=FinanceRecordResponse)
def update_finance_record(
    ref_no: str,
    payload: FinanceRecordUpdate,
    db: Session = Depends(get_db),
):
    """Update fields on an existing finance record."""
    norm_ref_no = ref_no.strip().upper()
    record = db.query(FinanceRecord).filter(FinanceRecord.ref_no == norm_ref_no).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finance record '{ref_no}' not found."
        )

    update_data = payload.model_dump(exclude_unset=True, by_alias=False)
    for key, value in update_data.items():
        if value is not None:
            setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return record


@router.delete("/{ref_no}", status_code=status.HTTP_200_OK)
def delete_finance_record(
    ref_no: str,
    db: Session = Depends(get_db),
):
    """Delete a finance record by Ref No."""
    norm_ref_no = ref_no.strip().upper()
    record = db.query(FinanceRecord).filter(FinanceRecord.ref_no == norm_ref_no).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finance record '{ref_no}' not found."
        )

    db.delete(record)
    db.commit()
    return {"success": True, "message": f"Finance record '{ref_no}' deleted successfully."}
