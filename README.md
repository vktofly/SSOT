# ✈️ BharatTrip AI Escalation Resolver & SSOT Prototype

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://vktoflyss.streamlit.app/)

## 📌 Executive Summary
Customer and agent escalations regarding refunds are rising at BharatTrip. Our deep data reconciliation revealed **100 dropped tickets** and **149 deduction mismatches** caused by a severe operational disconnect between the Support and Finance trackers. 

This repository contains the prototype for a unified **Single Source of Truth (SSOT)** driven by a **Multi-Agent AI Architecture**. It leverages Large Language Models to ingest messy WhatsApp/Email messages, extract structured data, and orchestrate automated communications with external agents via a secure Human-In-The-Loop (HITL) approval process.

## 🔐 Enterprise-Grade Security Architecture
This prototype goes beyond functional LLM wrappers to demonstrate true enterprise readiness:
* **Identity Gateway & RBAC**: Dual-role authorization (`manager` vs `operator`).
* **Data Privacy (PII Masking)**: Sensitive identifiers (Phones, Emails, Credit Cards) are automatically redacted via RegEx prior to ingestion, and `operator` roles see dynamically masked UI views.
* **Data Loss Prevention (DLP)**: UI-level CSS injection prevents text selection and copying of sensitive fields in the reconciliation grids.
* **Auditability**: Secure CSV session logging to track all human-in-the-loop approvals.
* **AI Confidence Guardrails**: The extraction agent assigns confidence scores to outputs, flagging low-confidence parsings for mandatory human review.

## 🛠️ Feature Overview

| Module | Technical Solution |
| :--- | :--- |
| **Identity Gateway** | Streamlit Auth Wrapper forcing credential validation before app render. |
| **Event-Driven Ingestion** | Simulates a Webhook inbox. Operators can cherry-pick individual messages or run Batch-Jobs to extract structured entities (Agent Name, Route, Urgency) from natural language. |
| **Reconciliation Agent** | Auto-detects "Short Payment" discrepancies and drafts explanatory emails justifying cancellation fees before dispatch via HITL. |
| **SSOT Database Explorer** | Unified search interface allowing cross-department querying with a single Global Ticket ID, eliminating manual sheet-to-sheet handoffs. |

## 💻 Local Installation & Testing

**1. Clone & Install**
```bash
# Clone the repository
cd SSOT_Parser
pip install -r requirements.txt
```

**2. Configure Environment**
Set your API key as an environment variable (or input it directly in the app UI if prompted):
```bash
export GEMINI_API_KEY="your_api_key"
```

**3. Run the App**
```bash
streamlit run app.py
```

**4. Test Credentials (Important for QA)**
To evaluate the Role-Based Access Control (RBAC) and Data Masking, use the following mock credentials at the login screen:
* **Manager Role** (Full Access): Username: `manager` | Password: `admin123`
* **Operator Role** (Masked Data & Restricted Exports): Username: `operator` | Password: `agent123`

## 📊 Data Verification
The business metrics (100 drops, 149 mismatches) were derived via strict programmatic database joins (Anti-Joins & Inner Joins). For a complete breakdown of the business logic and ROI analysis, please review the submitted PDF Write-Up.
