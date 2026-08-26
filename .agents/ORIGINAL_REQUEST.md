# Original User Request

## 2026-08-25T13:34:15Z

# Teamwork Project Prompt — Draft

> Status: Step 4-6 — Drafting Requirements & Acceptance Criteria
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full team

Upgrade the BharatTrip AI Escalation Resolver prototype from a monolithic Streamlit app with mock auth to a production-ready architecture. This includes implementing OAuth, decoupling the backend into a FastAPI service with an SQLite database, and upgrading the LLM orchestration to a LangGraph multi-agent framework.

Working directory: c:\Users\vikash\Documents\SSOT_Parser
Integrity mode: demo

## Requirements

### R1. Authentication & RBAC
Implement OAuth-based authentication (e.g., integrating with Auth0 or Google) in the Streamlit frontend. Secure the application routes based on roles (Manager vs. Operator). The current mock login gateway in pp.py must be replaced.

### R2. Backend Decoupling & Database Migration
Extract the core data processing and LLM logic into a separate FastAPI backend service. Migrate the existing CSV-based data to an SQLite database managed via SQLAlchemy. The Streamlit frontend must act purely as a presentation layer, fetching data and triggering actions via REST API calls to the FastAPI backend.

### R3. Multi-Agent Orchestration (LangGraph)
Refactor the current AI logic (currently handled in gents.py) into a LangGraph-based multi-agent workflow. The workflow should separate concerns (e.g., a routing agent, a data extraction agent, and a response generation agent) to handle the incoming escalations.

## Acceptance Criteria

### R1. Authentication Verification
- [ ] A test script or agent-as-judge verifies that the Streamlit app redirects unauthenticated users to an OAuth flow and denies access to restricted pages (like the Dashboard) for non-manager roles. (A mock OAuth provider or placeholder credentials can be used for verification).

### R2. Backend and Database Verification
- [ ] A pytest suite is created that programmatically queries the new FastAPI endpoints.
- [ ] Tests pass verifying that data is successfully read from and written to the SQLite database via the API, rather than from CSVs.

### R3. LangGraph Workflow Verification
- [ ] A test script can send a sample raw customer email to the backend API and receive a correctly structured response.
- [ ] The backend logs demonstrate that the LangGraph workflow successfully routes the request through multiple specialized agent nodes (e.g., extraction, then response generation).

## 2026-08-25T13:48:57Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Multi-agent execution in progress
> Requested team: Full team

Upgrade the BharatTrip AI Escalation Resolver prototype from a monolithic Streamlit app with mock auth to a production-ready architecture. This includes implementing OAuth, decoupling the backend into a FastAPI service with an SQLite database, and upgrading the LLM orchestration to a LangGraph multi-agent framework.

Working directory: c:\Users\vikash\Documents\SSOT_Parser
Integrity mode: demo

## Requirements

### R1. Authentication & RBAC
Implement OAuth-based authentication (e.g., integrating with Auth0 or Google) in the Streamlit frontend. Secure the application routes based on roles (Manager vs. Operator). The current mock login gateway in `app.py` must be replaced.

### R2. Backend Decoupling & Database Migration
Extract the core data processing and LLM logic into a separate FastAPI backend service. Migrate the existing CSV-based data to an SQLite database managed via SQLAlchemy. The Streamlit frontend must act purely as a presentation layer, fetching data and triggering actions via REST API calls to the FastAPI backend.

### R3. Multi-Agent Orchestration (LangGraph)
Refactor the current AI logic (currently handled in `agents.py`) into a LangGraph-based multi-agent workflow. The workflow should separate concerns (e.g., a routing agent, a data extraction agent, and a response generation agent) to handle the incoming escalations.

## Acceptance Criteria

### R1. Authentication Verification
- [ ] A test script or agent-as-judge verifies that the Streamlit app redirects unauthenticated users to an OAuth flow and denies access to restricted pages (like the Dashboard) for non-manager roles. (A mock OAuth provider or placeholder credentials can be used for verification).

### R2. Backend and Database Verification
- [ ] A `pytest` suite is created that programmatically queries the new FastAPI endpoints.
- [ ] Tests pass verifying that data is successfully read from and written to the SQLite database via the API, rather than from CSVs.

### R3. LangGraph Workflow Verification
- [ ] A test script can send a sample raw customer email to the backend API and receive a correctly structured response.
- [ ] The backend logs demonstrate that the LangGraph workflow successfully routes the request through multiple specialized agent nodes (e.g., extraction, then response generation).

