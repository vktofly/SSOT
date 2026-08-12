import json
import re
import requests
import pandas as pd
from typing import Dict, Any
from google.genai import types
from src.config import HAS_API_KEY, API_KEY, CLIENT

def redact_pii(text: str) -> str:
    """Masks phone numbers, emails, and credit cards to ensure Data Privacy."""
    # Mask 10+ digit phone numbers
    text = re.sub(r'\b\d{10,12}\b', '[REDACTED_PHONE]', text)
    # Mask email addresses
    text = re.sub(r'\S+@\S+\.\S+', '[REDACTED_EMAIL]', text)
    # Mask 16-digit credit cards (with or without spaces/dashes)
    text = re.sub(r'\b(?:\d[ -]*?){13,16}\b', '[REDACTED_CARD]', text)
    return text

def parse_informal_message(text: str) -> Dict[str, Any]:
    """
    Ingestion Agent: Extracts structured entities from informal complaints.
    """
    # Security: Redact PII before processing
    safe_text = redact_pii(text)
    
    if not HAS_API_KEY:
        return {
            "agent_name": "Peak Journeys",
            "route": "DEL-DXB",
            "reference_id": None,
            "expected_refund_amount": None,
            "elapsed_wait_time": "last week",
            "source_channel": "WhatsApp",
            "missing_reference": True,
            "urgency": "High",
            "intent": "status_update",
            "confidence_score": 70,
            "_mocked": True
        }

    prompt = f"""
    You are the Ingestion Agent for a travel company. 
    Analyze the following informal message and return a valid JSON object.
    
    Extract these keys:
    - "agent_name": The name of the agency if identifiable, else null.
    - "route": The flight/travel route (e.g., BLR-MAA, DEL-DXB), else null.
    - "reference_id": The booking reference or PNR mentioned (e.g., RF-1099, XYZ123), else null.
    - "expected_refund_amount": Any monetary amount mentioned, as a number, else null.
    - "elapsed_wait_time": The wait time mentioned (e.g., "last week", "2 weeks", "14 days"), else null.
    - "source_channel": The channel of the message (e.g., "WhatsApp", "Email"). Infer if not explicitly stated, else "Unknown".
    - "missing_reference": Boolean, true if they mention missing a ref number or PNR.
    - "urgency": "High", "Medium", or "Low" based on the tone and wait time.
    - "intent": "status_update" or "new_refund"
    - "confidence_score": Integer (0-100) representing how confident you are in the extracted details.
    
    Message: "{safe_text}"
    """
    
    try:
        if API_KEY.startswith("sk-"):
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            raw_output = resp.json()["choices"][0]["message"]["content"]
        else:
            response = CLIENT.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            raw_output = response.text
            
        # Robustly extract JSON block to prevent "extra data" errors from markdown or trailing text
        cleaned = raw_output.strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]
            
        parsed = json.loads(cleaned)
        
        # --- UNHAPPY PATH HANDLING ---
        valid_sectors = ["DEL-SIN", "DEL-KUL", "HYD-BKK", "DEL-CCU", "DEL-BOM", "COK-DXB", "GOI-BOM", "MAA-CMB", "BOM-BKK", "BLR-DXB", "PNQ-DEL", "DEL-KTM", "BLR-MAA"]
        if parsed.get("route") and parsed.get("route") not in valid_sectors:
            parsed["route"] = None
            parsed["route_flagged"] = True
            
        if not parsed.get("agent_name") or not parsed.get("route"):
            parsed["needs_human_review"] = True
            
        return parsed
        
    except Exception as e:
        return {"error": str(e), "needs_human_review": True}

def draft_reconciliation_message(agent_name: str, route: str, ticket_id: str, 
                                 support_amount: float, finance_amount: float, 
                                 deduction: float, reason: str) -> str:
    """
    Execution Agent: Drafts a polite message explaining a discrepancy to an agent.
    """
    if not HAS_API_KEY:
        return (f"Dear {agent_name},\n\nRegarding your refund for {route} (Ticket {ticket_id}): "
                f"Support originally quoted {support_amount} INR. However, Finance processed "
                f"{finance_amount} INR due to a deduction of {deduction} INR for the following "
                f"reason: {reason}.\n\nBest regards,\nBharatTrip Operations\n\n*(Mocked response)*")

    prompt = f"""
    Write a polite, professional, and concise message (max 3 sentences) to {agent_name} explaining a refund payout.
    They requested a refund for route {route} (Ticket: {ticket_id}).
    Support originally quoted them {support_amount} INR.
    Finance actually paid {finance_amount} INR because of a deduction of {deduction} INR.
    The reason for the deduction/rejection is: {reason}.
    
    Make it sound like it's coming from BharatTrip Operations. Do not include subject lines, just the message body.
    """
    try:
        if API_KEY.startswith("sk-"):
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            response = CLIENT.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
            )
            return response.text.strip()
    except Exception as e:
        return str(e)

def analyze_escalations(escalations_df) -> str:
    """
    Analyzes the escalations dataset and returns an executive summary.
    """
    if escalations_df is None or escalations_df.empty:
        return "No escalations data available to analyze."
        
    if not HAS_API_KEY:
        return "*(Mocked Summary)*: Analysis indicates that 80% of escalations are due to missing reference numbers and delayed finance responses, predominantly affecting 'GoFly Holidays'."
        
    # Calculate aggregated statistics using Pandas to avoid sending raw data to the LLM
    total_escalations = len(escalations_df)
    
    # Check for 'Agent' column to aggregate
    if 'Agent' in escalations_df.columns:
        top_agencies = escalations_df['Agent'].value_counts().head(3).to_dict()
    else:
        top_agencies = "Data unavailable"
        
    if 'Status' in escalations_df.columns:
        status_counts = escalations_df['Status'].value_counts().to_dict()
    else:
        status_counts = "Data unavailable"
        
    if 'Days Open' in escalations_df.columns:
        # Try to convert to numeric, dropping NaNs
        days_open = pd.to_numeric(escalations_df['Days Open'], errors='coerce').dropna()
        avg_days_open = round(days_open.mean(), 1) if not days_open.empty else "N/A"
    else:
        avg_days_open = "Data unavailable"
        
    agg_stats = f"""
    - Total Escalations: {total_escalations}
    - Top Agencies Involved: {top_agencies}
    - Status Breakdown: {status_counts}
    - Average Days Open: {avg_days_open}
    """
    
    prompt = f"""
    You are an Operations Analyst for a travel company.
    
    I have aggregated our recent Escalations data to ensure data privacy (no raw customer data is included).
    Please provide a concise, bulleted Executive Summary (max 4-5 bullet points) highlighting the key insights from these statistics:
    
    Aggregated Statistics:
    {agg_stats}
    
    Focus on:
    1. The volume and general status of complaints.
    2. Which agencies or teams are most frequently involved.
    3. Any other notable patterns (e.g., average resolution delays).
    """
    
    try:
        if API_KEY.startswith("sk-"):
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            response = CLIENT.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
            )
            return response.text.strip()
    except Exception as e:
        return f"Failed to generate summary: {str(e)}"

def fuzzy_match_metadata(support_row: Dict[str, Any], finance_candidates: list[Dict[str, Any]]) -> str | None:
    """
    LLM Fallback for fuzzy matching orphaned tickets based on metadata 
    (Agent, Route, Amount, Date) when Ticket ID fails.
    Returns the matching 'Ref No' from finance_candidates if a high-confidence match is found, else None.
    """
    if not finance_candidates:
        return None
        
    if not HAS_API_KEY:
        # Mock behavior for prototype without API key
        return None
        
    prompt = f"""
    You are an intelligent data reconciliation agent. 
    I have a Support ticket that is missing a matching Finance record based on exact ID match.
    
    Support Ticket Details:
    {json.dumps(support_row, indent=2)}
    
    Here is a list of candidate Finance tickets that were also unmatched:
    {json.dumps(finance_candidates, indent=2)}
    
    Your task is to determine if any of the candidate Finance tickets strongly match the Support ticket based on metadata like Agent Name, Sector/Route, and Amounts (allowing for some deduction).
    Return a JSON object with two keys:
    - "match_found": boolean (true if a strong match is found, else false)
    - "matched_ref_no": string (the 'Ref No' of the matched Finance ticket, or null if no match)
    """
    
    try:
        if API_KEY.startswith("sk-"):
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            raw_output = resp.json()["choices"][0]["message"]["content"]
        else:
            response = CLIENT.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            raw_output = response.text
            
        cleaned = raw_output.strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]
            
        parsed = json.loads(cleaned)
        if parsed.get("match_found"):
            return parsed.get("matched_ref_no")
        return None
    except Exception:
        return None

def batch_fuzzy_match_metadata(support_orphans: list[Dict[str, Any]], finance_candidates: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    LLM Fallback for fuzzy matching a batch of orphaned tickets based on metadata.
    Returns a list of dicts: [{"support_ticket_id": "...", "finance_ref_no": "...", "reasoning": "..."}]
    """
    if not support_orphans or not finance_candidates:
        return []
        
    if not HAS_API_KEY:
        return []
        
    prompt = f"""
    You are an intelligent data reconciliation agent. 
    I have a batch of Support tickets that are missing a matching Finance record.
    
    Support Tickets:
    {json.dumps(support_orphans, indent=2)}
    
    Candidate Finance Tickets:
    {json.dumps(finance_candidates, indent=2)}
    
    Your task is to determine if any of the Support tickets match a Candidate Finance ticket based on metadata like Agent Name, Sector/Route, Dates, and Amounts (allowing for some deduction).
    Only link a ticket if you believe there is a plausible match (e.g. typos in ID, but amounts, dates, and agent match).
    
    Return a JSON object with a single key "matches", which is a list of objects. Each object should have:
    - "support_ticket_id": string
    - "finance_ref_no": string
    - "reasoning": string (a short 1-sentence explanation of why they match)
    - "confidence_score": integer (between 0 and 100 representing how certain you are of this match)
    
    Do NOT include support tickets that have no plausible match (confidence under 50).
    """
    
    try:
        if API_KEY.startswith("sk-"):
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            raw_output = resp.json()["choices"][0]["message"]["content"]
        else:
            response = CLIENT.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            raw_output = response.text
            
        cleaned = raw_output.strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]
            
        parsed = json.loads(cleaned)
        return parsed.get("matches", [])
        
    except Exception as e:
        print(f"Batch Match Error: {e}")
        return []

def draft_escalation_response(escalation_text: str, support_status: dict) -> str:
    """
    Drafts a personalized response to an escalated complaint based on SSOT data.
    """
    if not HAS_API_KEY:
        return f"Dear Agent,\n\nWe apologize for the delay. According to our system, your refund is currently {support_status.get('Status', 'Pending')}. The notes show: {support_status.get('Notes', 'No notes')}.\n\nBest, Operations"
        
    prompt = f"""
    You are a customer service agent handling an escalated refund complaint.
    
    Complaint from Agent: "{escalation_text}"
    
    Our internal SSOT shows the following status for this ticket:
    {json.dumps(support_status, indent=2)}
    
    Draft a polite, empathetic email (max 3 sentences) replying to the agent.
    If the status is 'Refund Done' or 'Closed', reassure them it is processed. 
    If it is 'Pending', apologize and state the reason from the notes if available.
    Do not invent facts not present in the SSOT.
    """
    try:
        if API_KEY.startswith("sk-"):
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            response = CLIENT.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
            )
            return response.text.strip()
    except Exception as e:
        return str(e)

