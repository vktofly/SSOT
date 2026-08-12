import os
import streamlit as st
from google import genai

def get_api_key():
    """Securely handles local env vars & Streamlit Cloud Secrets."""
    api_key = os.environ.get("GEMINI_API_KEY", "")

    # Fallback 1: Local .env file
    if not api_key and os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.strip().split("=", 1)[1].strip('"').strip("'")
                    break

    # Fallback 2: Streamlit Cloud Secrets
    try:
        if not api_key and hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    return api_key

API_KEY = get_api_key()
HAS_API_KEY = bool(API_KEY and API_KEY != "YOUR_GEMINI_API_KEY")

def get_gemini_client():
    if HAS_API_KEY:
        return genai.Client(api_key=API_KEY)
    return None

CLIENT = get_gemini_client()
