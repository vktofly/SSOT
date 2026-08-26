"""
Pydantic Schemas for Operations Metrics & Executive RCA Services (Milestone 3).
Defines contracts for Operational KPIs, Cockpit Metrics, Root Cause Analysis,
Historical Trend Telemetry, SLA Breach Forecasting, and Carrier Performance.
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class WindowFilterEnum(str, Enum):
    ALL = "All (Feb–Jun 2026)"
    LAST_30_DAYS = "Last 30 Days"
    LAST_7_DAYS = "Last 7 Days"
    QUARTER_TO_DATE = "Quarter-to-Date"


class SLARiskLevelEnum(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    RESOLVED = "Resolved"


# ---------------------------------------------------------------------------
# Dashboard Sub-component Schemas
# ---------------------------------------------------------------------------

class DashboardSummary(BaseModel):
    """Core KPI telemetry figures."""
    total_escalations: int = Field(..., description="Total escalations count")
    avg_ttr: float = Field(..., description="Mean time to resolution in days")
    dropped_handoffs: int = Field(..., description="Orphaned tickets missing in Finance")
    deduction_mismatches: int = Field(..., description="Discrepancy count between Support and Finance")
    total_pipeline: int = Field(..., description="Total support ticket volume")
    healthy_count: int = Field(..., description="Count of clean, non-disputed tickets")
    health_pct: float = Field(..., description="Pipeline health percentage (0-100%)")
    financial_exposure_inr: float = Field(0.0, description="Total INR value of contested deductions")
    manual_hours_saved: float = Field(120.0, description="Estimated manual triage hours saved by automation")
    automation_rate_pct: float = Field(84.5, description="Percentage of workflows processed autonomously")


class CorridorNode(BaseModel):
    """Settlement Corridor node metrics."""
    intake_claims: int = Field(..., description="Total intake claims recorded in support")
    audited_tickets: int = Field(..., description="Tickets passed through initial audit")
    dropped_before_sync: int = Field(..., description="Tickets dropped before reaching banking/finance")
    clean_settlements: int = Field(..., description="Tickets settled without discrepancy")
    mismatch_count: int = Field(..., description="Tickets with payout variance")


class MonthlyTrendItem(BaseModel):
    """Historical monthly trajectory item."""
    month: str = Field(..., description="Month label (e.g. 'Feb', 'Mar')")
    tickets: int = Field(..., description="Support tickets processed")
    escalations: int = Field(..., description="Escalations raised")
    exposure_inr: float = Field(..., description="Contested financial exposure (INR)")
    avg_ttr_days: float = Field(..., description="Average resolution turnaround in days")


class RootCauseItem(BaseModel):
    """Discrepancy / escalation root cause categorization."""
    cause: str = Field(..., description="Root cause label (e.g. 'Deductions', 'Dropped', 'Off-Tracker')")
    count: int = Field(..., description="Incident occurrence count")
    exposure_inr: float = Field(..., description="Associated financial exposure in INR")
    percentage: float = Field(..., description="Share of total root cause volume (%)")


class ParetoItem(BaseModel):
    """Pareto analysis category."""
    category: str = Field(..., description="Pareto category description")
    count: int = Field(..., description="Complaint count")
    percentage: float = Field(..., description="Category percentage (%)")
    cumulative_percentage: float = Field(..., description="Cumulative percentage (%)")


class CarrierHealthItem(BaseModel):
    """Carrier operational health score."""
    carrier: str = Field(..., description="Airline carrier name")
    health_score: float = Field(..., description="Operational health score (0-100%)")
    avg_penalty_inr: float = Field(..., description="Average cancellation penalty in INR")
    resolution_sla_hours: int = Field(..., description="Average turnaround SLA in hours")
    dispute_rate_pct: float = Field(..., description="Partner dispute rate (%)")


# ---------------------------------------------------------------------------
# Dashboard Metrics Response (Unified Contract)
# ---------------------------------------------------------------------------

class DashboardMetricsResponse(BaseModel):
    """Cockpit KPI telemetry aggregated across Support, Finance, and Escalation datasets."""
    total_escalations: int = Field(..., description="Total volume of partner escalations logged")
    avg_ttr: float = Field(..., description="Average Time-to-Resolution in days across open/resolved escalations")
    dropped_handoffs: int = Field(..., description="Volume of support tickets approved but dropped before Finance payout")
    deduction_mismatches: int = Field(..., description="Volume of financial discrepancies between Support refund and Finance payout")
    total_pipeline: int = Field(..., description="Total support ticket volume in the current window")
    healthy_count: int = Field(..., description="Tickets flowing seamlessly without handoff drop or payout mismatch")
    health_pct: float = Field(..., description="Pipeline health percentage score (0.0 to 100.0%)")
    financial_exposure_inr: float = Field(0.0, description="Total financial exposure in INR")
    open_escalations: int = Field(0, description="Count of currently active/open escalations")
    pending_refunds: int = Field(0, description="Count of support tickets in 'Pending' status")
    window_filter: str = Field(WindowFilterEnum.ALL.value, description="Active temporal window filter applied")
    sla_breaches_count: int = Field(0, description="Number of active tickets exceeding the 72-hour SLA threshold")
    timestamp: str = Field(..., description="ISO 8601 timestamp when metrics were calculated")
    summary: Optional[DashboardSummary] = Field(None, description="Detailed summary metrics")
    corridor: Optional[CorridorNode] = Field(None, description="Settlement pipeline corridor nodes")
    trend: List[MonthlyTrendItem] = Field(default_factory=list, description="Monthly dispute trajectory")
    root_causes: List[RootCauseItem] = Field(default_factory=list, description="Distribution of root causes")
    complaint_distribution: List[ParetoItem] = Field(default_factory=list, description="Pareto complaint breakdown")
    carriers: List[CarrierHealthItem] = Field(default_factory=list, description="Carrier health metrics")
    at_risk_partners: List[Dict[str, Any]] = Field(default_factory=list, description="Partners requiring immediate retention outreach")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# ---------------------------------------------------------------------------
# Executive Root Cause Analysis (RCA) Schemas
# ---------------------------------------------------------------------------

class RCAMetricsResponse(BaseModel):
    """Executive AI Root Cause Analysis aggregating incident distributions and systematic failure patterns."""
    total_escalations: int = Field(..., description="Total escalation count analyzed")
    top_agencies: Dict[str, int] = Field(
        default_factory=dict,
        description="Top agencies involved in escalations with incident counts"
    )
    status_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of escalations by status ('Open', 'Pending Partner', 'Resolved')"
    )
    avg_days_open: float = Field(..., description="Mean escalation lifecycle latency in days")
    key_patterns: List[str] = Field(
        default_factory=list,
        description="Identified systemic bottleneck categories (e.g. 'Unlogged Reference Numbers', 'Carrier Fee Dispute')"
    )
    executive_summary: str = Field(..., description="Concise, bulleted executive briefing synthesised by AI Analyst")
    summary: Optional[str] = Field(None, description="Direct accessor for executive_summary string")
    key_findings: List[str] = Field(default_factory=list, description="Key operational findings")
    projected_outcome: Optional[str] = Field(None, description="Projected outcome of remediation")
    generated_at: str = Field(..., description="ISO 8601 timestamp of analysis generation")
    ai_model_used: str = Field("gemini-3.5-flash", description="AI model utilized for synthesis (or 'Mock/RuleEngine')")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# Alias RCASynthesisResponse to RCAMetricsResponse
RCASynthesisResponse = RCAMetricsResponse


# ---------------------------------------------------------------------------
# Trend Telemetry Schemas
# ---------------------------------------------------------------------------

class TrendDataPoint(BaseModel):
    """Single chronological telemetry data point for operational dashboards."""
    date: str = Field(..., description="Date or period bucket identifier (e.g. '2026-05-15' or '2026-W20')")
    total_tickets: int = Field(0, description="Volume of support tickets received")
    refunds_processed: int = Field(0, description="Volume of finance payouts completed")
    escalations_raised: int = Field(0, description="Volume of partner escalations created")
    discrepancy_count: int = Field(0, description="Count of payout variances detected")
    avg_ttr_days: float = Field(0.0, description="Average time to resolution on that date")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class TrendsResponse(BaseModel):
    """Time-series trend collection for multi-period operational monitoring."""
    window: str = Field(..., description="Evaluated time window range")
    points: List[TrendDataPoint] = Field(default_factory=list, description="Ordered time series telemetry points")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Aggregate summary metrics over the trend span")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# ---------------------------------------------------------------------------
# SLA Breach Forecaster Schemas
# ---------------------------------------------------------------------------

class SLABreachItem(BaseModel):
    """Predictive SLA breach evaluation for an individual ticket."""
    ticket_id: str = Field(..., alias="Ticket ID", description="Target ticket ID")
    agent: Optional[str] = Field(None, alias="Agent", description="Associated travel agency")
    route: Optional[str] = Field(None, alias="Route", description="Flight route")
    refund_amount: float = Field(0.0, alias="Refund Amount (INR)", description="Promised refund amount")
    request_date: Optional[str] = Field(None, alias="Request Date", description="Original request date string")
    hours_elapsed: int = Field(..., description="Hours elapsed since ticket creation")
    is_breached: bool = Field(..., description="True if hours_elapsed exceeds standard 72h SLA")
    risk_level: str = Field(..., description="Risk tier: 'Low' (<48h), 'Medium' (48-72h), 'High' (>=72h), 'Resolved'")
    warning: str = Field(..., description="Diagnostic warning message or SLA status indicator")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class SLABreachResponse(BaseModel):
    """Collection response of SLA breach telemetry across all active support tickets."""
    total_checked: int = Field(..., description="Total tickets evaluated")
    breached_count: int = Field(..., description="Count of tickets currently in breach (>72h)")
    high_risk_count: int = Field(..., description="Count of tickets approaching or in breach")
    items: List[SLABreachItem] = Field(default_factory=list, description="Individual ticket SLA evaluations")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# ---------------------------------------------------------------------------
# Carrier Performance Schemas
# ---------------------------------------------------------------------------

class CarrierPerformanceItem(BaseModel):
    """Aggregated operational reliability and policy friction metrics per airline carrier."""
    carrier: str = Field(..., description="Airline carrier name (e.g. 'Emirates', 'Air India', 'IndiGo')")
    total_sectors: int = Field(..., description="Number of monitored flight routes operated")
    average_fee: float = Field(..., description="Average cancellation penalty charged (INR)")
    avg_sla_hours: int = Field(..., description="Average resolution SLA turnaround in hours")
    dispute_rate_pct: float = Field(..., description="Percentage of tickets encountering partner dispute")


class CarrierPerformanceResponse(BaseModel):
    """Fleet-wide carrier performance and tariff impact telemetry."""
    carriers: List[CarrierPerformanceItem] = Field(default_factory=list, description="Carrier breakdown records")
    dominant_dispute_carrier: Optional[str] = Field(None, description="Carrier responsible for highest dispute volume")
