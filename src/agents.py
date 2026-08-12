import json
import re
import requests
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
