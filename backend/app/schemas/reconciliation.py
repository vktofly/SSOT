"""
Pydantic Schemas for Discrepancy & Reconciliation Services (Milestone 3).
Defines contracts for Ledger Mismatch Audits, Orphan Detection, Discrepancy Resolution,
Batch Processing, AI Entity Resolution, and Communication Drafting.
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class RiskLevelEnum(str, Enum):
    NORMAL = "Normal"
    HIGH = "High"


class MismatchStatusEnum(str, Enum):
    PENDING = "Pending"
    SETTLED = "Settled"
    DISPUTED = "Disputed"
    CLIENT_NOTIFIED = "Client Notified"


class ResolutionTypeEnum(str, Enum):
    ACCEPT_DEDUCTION = "Accept Deduction"
    CONTEST_DEDUCTION = "Contest Deduction"
    SPLIT_DIFFERENCE = "Split Difference"
    WRITE_OFF = "Write Off"
    MANUAL_ADJUSTMENT = "Manual Adjustment"


# ---------------------------------------------------------------------------
# Mismatch Schemas
# ---------------------------------------------------------------------------

class MismatchItem(BaseModel):
    """Single financial variance item between Support Ticket and Finance Record."""
    ticket_id: str = Field(..., alias="Ticket ID", description="Canonical Support ticket ID (e.g. RF-1001)")
    finance_ref_no: str = Field(..., alias="Finance Ref No", description="Matched Finance settlement reference number")
    agent: str = Field(..., alias="Agent", description="Travel agency name")
    route: Optional[str] = Field(None, alias="Route", description="Flight sector/route (e.g. DEL-DXB)")
    support_amount: float = Field(..., alias="Support Amount", description="Refund amount promised in support tracker (INR)")
    finance_amount: float = Field(..., alias="Finance Amount", description="Actual bank payout amount recorded in finance tracker (INR)")
    deduction: float = Field(..., alias="Deduction", description="Carrier penalty / deduction applied (INR)")
    reason: Optional[str] = Field(None, alias="Reason", description="Finance remarks or carrier penalty reason")
    risk_level: str = Field(RiskLevelEnum.NORMAL.value, alias="Risk Level", description="Risk tier ('Normal' or 'High' if variance >20%)")
    risk_note: Optional[str] = Field("", alias="Risk Note", description="Detailed risk justification")
    status: str = Field(MismatchStatusEnum.PENDING.value, alias="Status", description="Current discrepancy status")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class MismatchListResponse(BaseModel):
    """List response for discrepancy ledger mismatches."""
    items: List[MismatchItem] = Field(default_factory=list, description="List of detected financial discrepancies")
    total: int = Field(0, description="Total number of discrepancy items")
    high_risk_count: int = Field(0, description="Count of high-risk variances (>20% difference)")
    total_variance_inr: float = Field(0.0, description="Cumulative sum of deduction variances across all items (INR)")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# ---------------------------------------------------------------------------
# Orphan Schemas
# ---------------------------------------------------------------------------

class OrphanTicketItem(BaseModel):
    """Item representing a ticket present in one ledger but dropped/missing in the other."""
    ticket_id: Optional[str] = Field(None, alias="Ticket ID", description="Support ticket ID if present in Support")
    ref_no: Optional[str] = Field(None, alias="Ref No", description="Finance ref number if present in Finance")
    agent: Optional[str] = Field(None, alias="Agent", description="Agency name associated with the orphaned record")
    route: Optional[str] = Field(None, alias="Route", description="Flight sector/route")
    amount: float = Field(0.0, alias="Amount (INR)", description="Monetary value associated with the record (INR)")
    request_date: Optional[str] = Field(None, alias="Request Date", description="Date logged in support")
    processed_on: Optional[str] = Field(None, alias="Processed On", description="Date processed in finance")
    status: Optional[str] = Field(None, alias="Status", description="Status in source tracker")
    risk_level: str = Field(RiskLevelEnum.NORMAL.value, alias="Risk Level", description="'High' if agency has >=2 unlogged payouts")
    risk_note: Optional[str] = Field("", alias="Risk Note", description="Explanation for high risk classification")
    source_ledger: str = Field(..., alias="Source Ledger", description="'Support' (missing in finance) or 'Finance' (missing in support)")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class OrphanResponse(BaseModel):
    """Comprehensive orphan audit telemetry cross-matching Support and Finance."""
    missing_in_finance: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Tickets approved in Support tracker but missing corresponding Finance settlement"
    )
    missing_in_support: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Finance payouts executed without an originating Support ticket ID"
    )
    total_missing_finance: int = Field(0, description="Total count of tickets dropped before Finance ledger")
    total_missing_support: int = Field(0, description="Total count of unlinked Finance payouts")
    high_risk_agents: List[str] = Field(
        default_factory=list,
        description="Agencies flagged with multiple (>2) unlogged payout occurrences"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# ---------------------------------------------------------------------------
# Summary & Resolution Schemas
# ---------------------------------------------------------------------------

class ReconciliationSummary(BaseModel):
    """Executive reconciliation overview metrics for financial control."""
    total_support_records: int = Field(..., description="Total records in support tracker table")
    total_finance_records: int = Field(..., description="Total records in finance tracker table")
    total_mismatches: int = Field(..., description="Total detected payout discrepancies")
    pending_mismatches: int = Field(..., description="Discrepancies awaiting HITL review")
    resolved_mismatches: int = Field(..., description="Discrepancies resolved and committed to SSOT")
    total_orphans_in_finance: int = Field(..., description="Support tickets missing in Finance")
    total_orphans_in_support: int = Field(..., description="Finance records missing in Support")
    fleet_variance_inr: float = Field(..., description="Aggregate monetary difference across all mismatches (INR)")
    high_risk_discrepancies_count: int = Field(..., description="Count of discrepancies exceeding high risk threshold")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class ResolveMismatchRequest(BaseModel):
    """Request payload for resolving a single ledger discrepancy."""
    ticket_id: str = Field(..., alias="Ticket ID", description="Support ticket ID to settle")
    resolution_type: str = Field(
        ResolutionTypeEnum.ACCEPT_DEDUCTION.value,
        alias="Resolution Type",
        description="Action type: 'Accept Deduction', 'Contest Deduction', 'Split Difference', 'Write Off'"
    )
    finance_ref_no: Optional[str] = Field(None, alias="Finance Ref No", description="Associated finance reference")
    adjusted_amount: Optional[float] = Field(None, alias="Adjusted Amount (INR)", description="New agreed refund amount if adjusted")
    status: str = Field("Settled", alias="Status", description="New status to set on SupportTicket ('Settled' or 'Client Notified')")
    notes: Optional[str] = Field(None, alias="Notes", description="Audit notes explaining deduction acceptance/contest")
    reason: Optional[str] = Field(None, alias="Reason", description="Carrier policy reason")
    send_communication: bool = Field(False, description="Whether to dispatch communication to travel partner")
    communication_draft: Optional[str] = Field(None, description="Approved communication body text to record in audit trail")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class ResolveMismatchResponse(BaseModel):
    """Response returned upon successfully resolving a discrepancy."""
    success: bool = Field(..., description="Operation success indicator")
    ticket_id: str = Field(..., description="Resolved ticket identifier")
    new_status: str = Field(..., description="Updated ticket status")
    notes: str = Field(..., description="Appended audit notes")
    audit_id: Optional[int] = Field(None, description="Created audit log record ID")
    message: str = Field(..., description="Human-readable confirmation message")


class LinkOrphanRequest(BaseModel):
    """Request payload for linking an orphaned Support ticket with a Finance settlement record."""
    support_ticket_id: str = Field(..., alias="Support Ticket ID", description="Orphaned Support ticket ID")
    finance_ref_no: str = Field(..., alias="Finance Ref No", description="Orphaned Finance record reference number")
    notes: Optional[str] = Field(None, description="Optional justification note for the manual audit trail")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class LinkOrphanResponse(BaseModel):
    """Response returned upon linking an orphaned record."""
    success: bool = Field(..., description="Operation success flag")
    support_ticket_id: str = Field(..., description="Linked Support ticket ID")
    finance_ref_no: str = Field(..., description="Linked Finance reference number")
    message: str = Field(..., description="Status explanation message")
    audit_id: Optional[int] = Field(None, description="Generated AuditLog ID")


class BatchResolveMismatchesRequest(BaseModel):
    """Request payload for batch reconciliation of multiple tickets simultaneously."""
    ticket_ids: List[str] = Field(..., description="List of Ticket IDs to settle in batch")
    resolution_type: str = Field(
        ResolutionTypeEnum.ACCEPT_DEDUCTION.value,
        description="Resolution type to apply to all selected tickets"
    )
    status: str = Field("Client Notified", description="New target status for all resolved tickets")
    auto_draft_explanations: bool = Field(True, description="Whether to auto-generate airline policy explanation notes")


class BatchResolveMismatchesResponse(BaseModel):
    """Response returned after executing batch reconciliation."""
    success: bool = Field(..., description="Batch execution success flag")
    resolved_count: int = Field(..., description="Number of tickets successfully settled")
    resolved_ticket_ids: List[str] = Field(default_factory=list, description="IDs of tickets successfully resolved")
    failed_ticket_ids: List[str] = Field(default_factory=list, description="IDs of tickets that failed resolution")
    message: str = Field(..., description="Batch summary status message")


# ---------------------------------------------------------------------------
# AI Entity Resolution & Communication Drafting
# ---------------------------------------------------------------------------

class AIEntityResolutionMatch(BaseModel):
    """AI-discovered link between an orphaned Support ticket and a Finance record."""
    support_ticket_id: str = Field(..., description="Unlinked Support ticket ID")
    finance_ref_no: str = Field(..., description="Suggested Finance reference number")
    agent: str = Field(..., description="Travel partner agency name")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Match confidence score (0.0 to 1.0)")
    match_rationale: str = Field(..., description="Reasoning based on Agent, Sector, and Amount alignment")


class AIEntityResolutionRequest(BaseModel):
    """Request payload for running AI fuzzy metadata linkage on orphaned records."""
    missing_in_finance_ticket_ids: Optional[List[str]] = Field(
        None,
        description="Specific subset of orphaned support ticket IDs to link. If omitted, runs on all orphans."
    )
    threshold: float = Field(0.70, ge=0.5, le=1.0, description="Confidence threshold cutoff for accepting matches")


class AIEntityResolutionResponse(BaseModel):
    """Response containing discovered metadata links for orphaned records."""
    matches: List[AIEntityResolutionMatch] = Field(default_factory=list, description="Discovered candidate matches")
    total_matches: int = Field(0, description="Total number of high-confidence matches found")
    unmatched_support_count: int = Field(0, description="Support tickets remaining unlinked")
    unmatched_finance_count: int = Field(0, description="Finance records remaining unlinked")


class DraftExplanationRequest(BaseModel):
    """Request payload for generating an AI discrepancy explanation email for a partner."""
    ticket_id: str = Field(..., alias="Ticket ID", description="Support ticket ID")
    agent: str = Field(..., alias="Agent", description="Partner agency name")
    route: Optional[str] = Field(None, alias="Route", description="Flight sector/route (e.g. DEL-DXB)")
    support_amount: float = Field(..., alias="Support Amount", description="Amount promised to customer (INR)")
    finance_amount: float = Field(..., alias="Finance Amount", description="Amount paid by finance (INR)")
    deduction: float = Field(..., alias="Deduction", description="Deduction amount (INR)")
    reason: Optional[str] = Field(None, alias="Reason", description="Carrier penalty or remarks")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# Alias DraftReconciliationMessageRequest to DraftExplanationRequest for backwards compatibility
DraftReconciliationMessageRequest = DraftExplanationRequest


class DraftExplanationResponse(BaseModel):
    """Response containing AI-drafted discrepancy communication."""
    ticket_id: str = Field(..., description="Target ticket ID")
    recipient_agent: str = Field(..., description="Target travel partner")
    subject: str = Field(..., description="Email subject line")
    draft_body: str = Field(..., description="Formatted email message body explaining carrier tariff deduction")
    carrier_policy_applied: Optional[str] = Field(None, description="Summary of applied airline cancellation rule")
    draft: Optional[str] = Field(None, description="Convenience accessor for draft_body")


# Alias DraftReconciliationMessageResponse to DraftExplanationResponse
DraftReconciliationMessageResponse = DraftExplanationResponse


class ProactiveNotificationRequest(BaseModel):
    """Request payload for generating a multi-channel proactive lifecycle notification."""
    ticket_id: str = Field(..., description="Target Support ticket ID")
    agent_name: str = Field(..., description="Partner travel agency name")
    route: str = Field(..., description="Flight sector (e.g. DEL-DXB)")
    stage: str = Field("Pending Bank Transfer", description="Lifecycle milestone stage")
    amount: Optional[str] = Field(None, description="Gross or net refund amount string")
    deduction: Optional[str] = Field(None, description="Applied tariff deduction string")
    channel: str = Field("WhatsApp", description="Delivery channel ('WhatsApp', 'Email', 'Portal')")


class ProactiveNotificationResponse(BaseModel):
    """Response containing drafted proactive notification text."""
    success: bool = Field(..., description="Dispatch or draft success flag")
    ticket_id: str = Field(..., description="Target ticket ID")
    agent_name: str = Field(..., description="Target agency name")
    stage: str = Field(..., description="Notification stage")
    channel: str = Field(..., description="Delivery channel")
    message: str = Field(..., description="Formatted outbound message body")
    draft_text: str = Field(..., description="Raw template string")
