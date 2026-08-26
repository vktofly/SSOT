# ✈️ BharatTrip AI Escalation Resolver & SSOT Prototype

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange.svg)](https://python.langchain.com/docs/langgraph)

## 📌 Executive Summary
Customer and agent escalations regarding refunds are rising at BharatTrip. Our deep data reconciliation revealed **100 dropped tickets** and **149 deduction mismatches** caused by a severe operational disconnect between the Support and Finance trackers. 

This repository contains the prototype for a unified **Single Source of Truth (SSOT)** driven by a **Multi-Agent AI Architecture (LangGraph)**. It leverages Large Language Models to ingest messy WhatsApp/Email messages, extract structured data, and orchestrate automated communications with external agents via a secure Human-In-The-Loop (HITL) approval process.

## 🏗️ Decoupled Architecture
The system has been upgraded to a modern, decoupled architecture:
*   **Backend:** A highly scalable **FastAPI** application (`backend/app/main.py`) powered by a real **SQLite** relational database (`bharattrip.db`).
*   **Frontend:** A sleek, interactive **Streamlit** dashboard (`app.py`) that communicates with the backend exclusively via REST APIs (`src/api_client.py`).
*   **AI Orchestration:** A **LangGraph** `StateGraph` pipeline (`backend/app/services/ai_agent.py`) that separates concerns: Entity Extraction, Priority Routing, Policy RAG, and Safety Guardrails.

## 🔐 Enterprise-Grade Security Architecture
This prototype goes beyond functional LLM wrappers to demonstrate true enterprise readiness:
*   **JWT OAuth 2.0 Identity Gateway:** Dual-role authorization (`Manager` vs `Operator`) secured via signed JSON Web Tokens.
*   **Data Privacy (PII Masking):** Sensitive identifiers (Phones, Emails, Credit Cards) are automatically redacted via RegEx prior to LLM ingestion.
*   **Auditability & HITL:** Complete audit traces are generated for every LangGraph node execution. VIP escalations dynamically trigger mandatory Human-In-The-Loop interrupts.
*   **AI Confidence Guardrails:** The LangGraph extraction node assigns confidence scores, flagging low-confidence parsings for human review.

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

**3. Start the FastAPI Backend Server**
Open a terminal and start the API backend:
```bash
uvicorn backend.app.main:app --reload --port 8000
```

**4. Run the Streamlit Frontend App**
Open a *second* terminal and launch the UI:
```bash
streamlit run app.py
```

**5. Test Credentials (Important for QA)**
To evaluate the JWT Role-Based Access Control (RBAC) and Data Masking, use the following mock credentials at the login screen:
*   **Manager Role** (Full Access): Username: `manager` | Password: `admin123`
*   **Operator Role** (Masked Data & Restricted Exports): Username: `operator` | Password: `agent123`

## 📊 Data Verification
The business metrics (100 drops, 149 mismatches) were derived via strict programmatic database joins (Anti-Joins & Inner Joins). The prototype handles these seamlessly through the robust FastAPI + SQLite backend.
