import streamlit as st
import json
import os
from src.config import HAS_API_KEY
from src.data_manager import load_data
# BharatTrip Operations Suite v2.1 (Hot Reload Trigger)
from src.views import (
    render_dashboard, render_ingestion, render_reconciliation,
    render_database_explorer, render_escalation_triage, render_partner_matrix
)

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BharatTrip AI Operations",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# Security & DLP
# -----------------------------------------------------------------------------
# Inject CSS to prevent text selection (Data Loss Prevention)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    code, pre, .stCodeBlock {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* DLP text selection lock */
    body {
        user-select: none;
        -webkit-user-select: none;
        -ms-user-select: none;
    }

    /* Enterprise Glassmorphism KPI cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 2px solid rgba(14, 165, 233, 0.6);
        border-radius: 10px;
        padding: 14px 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: rgba(14, 165, 233, 0.8);
        box-shadow: 0 8px 24px rgba(14, 165, 233, 0.15);
    }

    /* Polished Interactive Buttons */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 500;
        letter-spacing: 0.01em;
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    /* Modern Tabs Navigation */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding-bottom: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px 6px 0 0;
        padding: 8px 16px;
        font-weight: 500;
    }

    /* Subtle Glassmorphism for Containers & Expanders */
    div[data-testid="stExpander"], div[data-testid="stContainer"] {
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Mock Authentication (Identity Provider)
# -----------------------------------------------------------------------------
MOCK_USERS = {
    "manager": {"password": "admin123", "role": "Manager"},
    "operator": {"password": "agent123", "role": "Junior"}
}

def check_password():
    """Returns `True` if the user had a correct password."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = None
        
        # Check for remember me file
        if os.path.exists(".remember.json"):
            try:
                with open(".remember.json", "r") as f:
                    saved_creds = json.load(f)
                    if saved_creds.get("username") in MOCK_USERS and MOCK_USERS[saved_creds["username"]]["password"] == saved_creds.get("password"):
                        st.session_state.logged_in = True
                        st.session_state.role = MOCK_USERS[saved_creds["username"]]["role"]
                        st.session_state.username = saved_creds["username"]
                        return True
            except:
                pass

    if st.session_state.logged_in:
        return True

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Identity Gateway")
        st.markdown("This application is restricted. Please authenticate via your Identity Provider.")
        
        with st.form("login_form"):
            username = st.text_input("Username").strip()
            password = st.text_input("Password", type="password").strip()
            remember_me = st.checkbox("Remember Me")
            submit = st.form_submit_button("Log In", type="primary", use_container_width=True)
            
            if submit:
                if username in MOCK_USERS and MOCK_USERS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.role = MOCK_USERS[username]["role"]
                    st.session_state.username = username
                    
                    if remember_me:
                        with open(".remember.json", "w") as f:
                            json.dump({"username": username, "password": password}, f)
                            
                    st.rerun()
                else:
                    st.error("😕 Invalid username or password")
    return False

def main():
    if not check_password():
        return
        
    st.sidebar.title("✈️ BharatTrip Operations")
    
    st.sidebar.markdown(f"**Logged in as:** {st.session_state.username} ({st.session_state.role})")
    if st.sidebar.button("Log Out", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = None
        if os.path.exists(".remember.json"):
            os.remove(".remember.json")
        st.rerun()
        
    st.sidebar.markdown("---")
    
    if not HAS_API_KEY:
        st.sidebar.warning("⚠️ `GEMINI_API_KEY` not found. Using mocked AI responses for demonstration.")
    
    # Load data into session state for mutability
    if 'support_df' not in st.session_state:
        sup, fin, esc = load_data()
        st.session_state.support_df = sup.copy()
        st.session_state.finance_df = fin.copy()
        st.session_state.escalations_df = esc.copy()

    # Page wrappers ensuring dynamic session state passing
    def page_dashboard():
        render_dashboard()

    def page_ingestion():
        render_ingestion()

    def page_reconciliation():
        render_reconciliation(st.session_state.support_df, st.session_state.finance_df)

    def page_triage():
        render_escalation_triage(st.session_state.escalations_df, st.session_state.support_df)

    def page_database():
        render_database_explorer(st.session_state.support_df, st.session_state.finance_df, st.session_state.escalations_df)

    def page_partners():
        render_partner_matrix(st.session_state.escalations_df, st.session_state.support_df)

    # Declarative Multi-Page Declarations with clean URL paths
    dashboard_p = st.Page(page_dashboard, title="Metrics Dashboard", icon="📊", url_path="dashboard", default=True)
    partners_p = st.Page(page_partners, title="Partner Health Matrix", icon="📈", url_path="partners")
    database_p = st.Page(page_database, title="Database Explorer", icon="🗄️", url_path="database")
    ingestion_p = st.Page(page_ingestion, title="Ingestion Agent", icon="📥", url_path="ingestion")
    reconciliation_p = st.Page(page_reconciliation, title="Reconciliation (HITL)", icon="⚖️", url_path="reconciliation")
    triage_p = st.Page(page_triage, title="Escalation Triage", icon="🚨", url_path="triage", default=(st.session_state.role != "Manager"))

    # Role-Based Sectioned Navigation
    if st.session_state.role == "Manager":
        nav_dict = {
            "Operations Cockpit": [dashboard_p, partners_p, database_p],
            "AI Workflows & HITL": [ingestion_p, reconciliation_p, triage_p]
        }
    else:
        nav_dict = {
            "Operator Workspace": [ingestion_p, triage_p]
        }

    pg = st.navigation(nav_dict)
    pg.run()

if __name__ == "__main__":
    main()

