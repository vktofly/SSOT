# BharatTrip SSOT Parser & Multi-Agent Orchestrator

![System Architecture Flowchart](deliverables/architecture.png)

## 📌 Executive Summary
Customer and agent escalations regarding refunds are rising at BharatTrip. Our deep data reconciliation revealed **100 dropped tickets** and **149 deduction mismatches** caused by a severe operational disconnect between the Support and Finance trackers. 

This repository contains the prototype for a unified **Single Source of Truth (SSOT)** driven by a **Multi-Agent AI Architecture**. It leverages `gemini-3.5-flash` to ingest messy WhatsApp/Email messages, extract structured data, and orchestrate automated communications with external agents via a secure Human-In-The-Loop (HITL) approval process.

## 🚀 Live Demo
**[Play with the Live Web App Here] https://vktoflyss.streamlit.app/**

## 🛠️ Features
- **Operations Telemetry Dashboard**: Live KPI tracking for Escalations and Discrepancies to prove ROI.
- **AI Ingestion Agent**: Extracts structured entities (Agent Name, Route, Urgency) from unstructured text.
- **Unhappy Path Mitigation**: Built-in hallucination checks against valid travel sectors and automated flagging for missing required information.
- **Reconciliation Agent (HITL)**: A built-in approval UI to review AI-generated explanatory emails before dispatch, mitigating financial compliance risks.
- **MCP Ready**: Designed to integrate with enterprise databases securely using the Model Context Protocol.

## 💻 Local Installation (Docker)
To run this application locally via Docker:
```bash
docker build -t bharattrip-ssot .
docker run -p 8501:8501 -e GEMINI_API_KEY="your_api_key" bharattrip-ssot
```
The app will be available at `http://localhost:8501`.

## 📦 Local Installation (Python)
```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your_api_key"
streamlit run app.py
```

## 📊 Data Verification
The analysis calculations provided in the `deliverables/write_up.pdf` business case have been strictly verified against the raw internal CSV trackers via Pandas database joins. All numbers are mathematically certified.
