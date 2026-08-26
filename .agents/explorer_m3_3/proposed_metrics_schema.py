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
# Dashboard Metrics Schemas
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
    open_escalations: int = Field(0, description="Count of currently active/open escalations")
    pending_refunds: int = Field(0, description="Count of support tickets in 'Pending' status")
    window_filter: str = Field(WindowFilterEnum.ALL.value, description="Active temporal window filter applied")
    sla_breaches_count: int = Field(0, description="Number of active tickets exceeding the 72-hour SLA threshold")
    timestamp: str = Field(..., description="ISO 8601 timestamp when metrics were calculated")

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
    generated_at: str = Field(..., description="ISO 8601 timestamp of analysis generation")
    ai_model_used: str = Field("gemini-3.5-flash", description="AI model utilized for synthesis (or 'Mock/RuleEngine')")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


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
