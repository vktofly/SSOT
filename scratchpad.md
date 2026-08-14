# 🧠 Project Scratchpad: BharatTrip SSOT

## Core Problem Statement
Customer and agent refund escalations climbed over 2 months while refund volume stayed flat. Root cause: Operational disconnect between Support and Finance tracking sheets, uncommunicated fee deductions, and informal WhatsApp/Email requests bypassing formal trackers.

## Key Empirical Metrics
- **Support Records**: 600
- **Finance Records**: 500
- **Dropped Handoffs**: 100 tickets in Support with no Finance record
- **Short Payments**: 149 cases where Payout < Support Refund Amount
- **Escalation Volume**: 172 records (avg resolution time 16.4 days)

## Architectural Constraints & Decisions
1. **SSOT Database**: SQLite database `data/ssot.db` unifying Support, Finance, and Escalation records under normalized schemas.
2. **AI Safety & Privacy**: Pre-LLM Regex PII masking for phone numbers, emails, and credit cards; post-LLM validation for airport sector codes.
3. **HITL Mandate**: LLM generates draft communications and extraction objects; operators hold exclusive approval authority for state mutations.
4. **RBAC Rules**: `Manager` (full access to metrics, reconciliation, and raw data) vs `Operator` (masked data, escalation triage focus).

## Security & Hardening Controls
- **Data Privacy (PII)**: Pre-inference regex scrubber for Phone Numbers, Emails, and Credit Cards (`src/agents.py`).
- **SQL Hardening**: 100% Parameterized queries (`src/db.py`) mitigating SQL Injection.
- **DLP Controls**: UI-level CSS selection locks preventing mass exfiltration.
- **AI Guardrails**: Sector validation whitelist and low-confidence human fallback routing.
- **Audit Trails**: Non-repudiation audit logging for every operator action.

