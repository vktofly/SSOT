"""
Pydantic Schemas for Partner Health Matrix & Airline Policy Services (Milestone 3).
Defines contracts for B2B Partner Telemetry, Churn Risk Matrix, Sentiment Analysis,
Proactive Outreach Actions, and Airline Fare Policy RAG lookups.
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class RevenueTierEnum(str, Enum):
    VIP = "VIP"
    STRATEGIC = "Strategic"
    STANDARD = "Standard"


class PartnerRiskStatusEnum(str, Enum):
    CRITICAL = "CRITICAL (Immediate Churn Risk)"
    ELEVATED = "ELEVATED (SLA Delay)"
    STABLE = "STABLE"
    OPTIMAL = "OPTIMAL"


class UrgencyLevelEnum(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class PriorityRankEnum(str, Enum):
    P0_IMMEDIATE = "P0 - Immediate"
    P1_URGENT = "P1 - Urgent"
    P2_ELEVATED = "P2 - Elevated"
    P3_STANDARD = "P3 - Standard"


# ---------------------------------------------------------------------------
# Fleet & Partner Health Matrix Schemas
# ---------------------------------------------------------------------------

class FleetSummary(BaseModel):
    """Aggregate fleet-level health statistics."""
    total_monitored_agencies: int = Field(..., description="Total agencies evaluated")
    critical_vips_count: int = Field(0, description="Count of critical VIP agencies at risk")
    critical_vips: int = Field(0, description="Alias for critical_vips_count")
    monitored_agencies: int = Field(0, description="Alias for total_monitored_agencies")
    fleet_sentiment_index: float = Field(0.0, description="Average sentiment across all partners (-1.0 to 1.0)")
    fleet_sentiment: float = Field(0.0, description="Alias for fleet_sentiment_index")
    dominant_complaint: str = Field("Routine Inquiries", description="Top systemic bottleneck across partners")


class PartnerHealthItem(BaseModel):
    """Aggregated health, sentiment, and risk telemetry for a single B2B travel partner."""
    agency_name: str = Field(..., alias="Agency Name", description="Unique travel agency name")
    revenue_tier: str = Field(RevenueTierEnum.STANDARD.value, alias="Revenue Tier", description="Tier ('VIP', 'Strategic', 'Standard')")
    active_escalations: int = Field(0, alias="Active Escalations", description="Count of open escalations involving this agency")
    sentiment_index: float = Field(
        0.0,
        alias="Sentiment Index",
        ge=-1.0,
        le=1.0,
        description="NLP sentiment score ranging from -1.0 (severe frustration) to +1.0 (positive)"
    )
    primary_bottleneck: str = Field(
        "General",
        alias="Primary Bottleneck",
        description="Dominant frustration category (e.g. 'Legal / Severe Churn Risk', 'Prolonged Delay', 'Fee Deductions')"
    )
    risk_status: str = Field(
        PartnerRiskStatusEnum.STABLE.value,
        alias="Risk Status",
        description="Assigned retention risk level"
    )
    sample_messages: List[str] = Field(default_factory=list, description="Recent representative escalation excerpts")
    unlogged_payouts: int = Field(0, description="Count of orphan tickets missing in Finance ledger for this agency")
    last_escalation_date: Optional[str] = Field(None, description="Most recent escalation date logged")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class PartnerMatrixResponse(BaseModel):
    """Full B2B Partner Health Matrix response for executive retention telemetry."""
    total_monitored_agencies: int = Field(..., description="Total count of active partner agencies evaluated")
    critical_vips_at_risk: int = Field(..., description="Count of high-revenue VIP agencies flagged with critical risk")
    fleet_sentiment_index: float = Field(..., description="Overall average sentiment index across all monitored partners")
    dominant_complaint: str = Field(..., description="Top aggregate complaint across the fleet")
    summary: Optional[FleetSummary] = Field(None, description="Detailed fleet summary stats")
    partners: List[PartnerHealthItem] = Field(default_factory=list, description="Ranked list of partner health profiles")
    generated_at: str = Field(..., description="ISO 8601 timestamp of matrix generation")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class PartnerDetailResponse(BaseModel):
    """Deep-dive profile response for a single partner agency."""
    agency_name: str = Field(..., description="Agency name")
    revenue_tier: str = Field("Standard", description="Agency revenue tier")
    tier: str = Field("Standard", description="Alias for revenue_tier")
    active_escalations: int = Field(0, description="Active escalation count")
    sentiment_index: float = Field(0.0, description="Partner sentiment index (-1.0 to 1.0)")
    primary_bottleneck: str = Field("General", description="Primary operational bottleneck")
    risk_status: str = Field("STABLE", description="Calculated churn risk tier")
    recent_messages: List[str] = Field(default_factory=list, description="Recent escalation messages")
    associated_tickets: List[Dict[str, Any]] = Field(default_factory=list, description="Active support tickets")
    recommended_action: str = Field("Monitor normally", description="Recommended retention action")


# ---------------------------------------------------------------------------
# Sentiment & Frustration Scoring Schemas
# ---------------------------------------------------------------------------

class PartnerSentimentAnalysisRequest(BaseModel):
    """Request payload for running NLP sentiment analysis on inbound communication."""
    message: str = Field(..., description="Inbound email, WhatsApp, or chat message text")
    agency_name: Optional[str] = Field(None, description="Optional agency name to contextualize revenue tier")
    agency_tier: str = Field(RevenueTierEnum.STANDARD.value, description="Partner revenue tier ('VIP', 'Strategic', 'Standard')")


class PartnerSentimentAnalysisResponse(BaseModel):
    """NLP sentiment, urgency, and priority classification result."""
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="Computed sentiment index (-1.0 to 1.0)")
    urgency_level: str = Field(..., description="Urgency classification ('Critical', 'High', 'Medium', 'Low')")
    priority_rank: str = Field(..., description="Triage priority rank ('P0 - Immediate', 'P1 - Urgent', 'P2 - Elevated', 'P3 - Standard')")
    frustration_category: str = Field(..., description="Identified root cause (e.g. 'Legal / Severe Churn Risk', 'Prolonged Delay')")
    agency_tier: str = Field(..., description="Evaluated agency tier")
    recommended_action: str = Field(..., description="Actionable recommendation (e.g. 'Instant Manager Escalation & Phone Outreach')")


# ---------------------------------------------------------------------------
# Proactive Outreach Schemas
# ---------------------------------------------------------------------------

class PartnerOutreachRequest(BaseModel):
    """Request to initiate proactive outreach or schedule reassurance dispatch."""
    agency_name: str = Field(..., description="Target travel partner agency")
    outreach_type: str = Field(
        "VIP Reassurance",
        description="Type of intervention: 'VIP Reassurance', 'SLA Delay Apology', 'Ledger Settlement Summary'"
    )
    custom_note: Optional[str] = Field(None, description="Optional custom instructions for outreach communication")


class PartnerOutreachResponse(BaseModel):
    """Confirmation of dispatched outreach action."""
    success: bool = Field(..., description="Dispatch status indicator")
    agency_name: str = Field(..., description="Target agency name")
    outreach_type: str = Field(..., description="Dispatched outreach category")
    action_taken: str = Field(..., description="Description of logged CRM/audit action")
    timestamp: str = Field(..., description="ISO 8601 timestamp of dispatch")


# ---------------------------------------------------------------------------
# Airline Fare Policy RAG Schemas
# ---------------------------------------------------------------------------

class PolicyRuleResponse(BaseModel):
    """Retrieved airline cancellation penalty, resolution SLA, and tariff rule."""
    route: str = Field(..., description="Sector or route code (e.g. 'DEL-DXB', 'BLR-MAA')")
    carrier: str = Field(..., description="Operating airline carrier (e.g. 'Emirates', 'IndiGo')")
    cancellation_fee: float = Field(..., description="Standard cancellation deduction per passenger (INR)")
    policy_notes: str = Field(..., description="Official carrier tariff condition notes")
    sla_hours: int = Field(..., description="Contracted resolution turnaround time in hours")
    sector_type: str = Field("Domestic", description="Sector classification ('Domestic' or 'International')")
    is_registered: bool = Field(True, description="True if route is explicitly defined in policy knowledge base; False if default fallback applied")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# Alias AirlinePolicyResponse to PolicyRuleResponse
AirlinePolicyResponse = PolicyRuleResponse


class PolicyRuleListResponse(BaseModel):
    """Collection response of all registered airline sector penalty rules."""
    items: List[PolicyRuleResponse] = Field(default_factory=list, description="Registered airline tariff policies")
    total: int = Field(0, description="Total registered sectors")


class PolicyRuleLookupRequest(BaseModel):
    """Query payload for route-specific penalty rule lookup."""
    route: str = Field(..., description="Origin-Destination flight sector (e.g. 'DEL-BOM', 'COK-DXB')")
    carrier: Optional[str] = Field(None, description="Optional carrier name override")


# ---------------------------------------------------------------------------
# SLA Breach Prediction Schemas
# ---------------------------------------------------------------------------

class PredictSLABreachRequest(BaseModel):
    """Request to predict SLA breach risk for a ticket."""
    ticket_id: str = Field(..., description="Target ticket ID")
    request_date: Optional[str] = Field(None, description="Date logged in support")
    status: Optional[str] = Field("Pending", description="Current ticket status")
    current_date: Optional[str] = Field("2026-06-30", description="Reference baseline date for simulation")


class PredictSLABreachResponse(BaseModel):
    """Response containing predicted SLA breach outcome."""
    ticket_id: str = Field(..., description="Target ticket ID")
    is_breached: bool = Field(..., description="True if SLA exceeds 72 hours")
    hours_elapsed: int = Field(..., description="Hours elapsed since ticket creation")
    risk_level: str = Field(..., description="Risk level ('Low', 'Medium', 'High', 'Resolved')")
    warning: str = Field(..., description="Warning message or status indicator")
