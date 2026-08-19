import streamlit as st
import json
import os
from src.config import HAS_API_KEY
from src.data_manager import load_data
import importlib
import src.views
import src.views.dashboard
import src.views.ingestion
import src.views.reconciliation
import src.views.database_explorer
import src.views.escalation_triage
import src.views.partner_matrix
importlib.reload(src.views)
importlib.reload(src.views.dashboard)
importlib.reload(src.views.ingestion)
importlib.reload(src.views.reconciliation)
importlib.reload(src.views.database_explorer)
importlib.reload(src.views.escalation_triage)
importlib.reload(src.views.partner_matrix)
from src.views import (
    render_dashboard, render_ingestion, render_reconciliation,
    render_database_explorer, render_escalation_triage, render_partner_matrix
)

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BharatTrip Operations",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# Security & DLP + Global Standardized Typography
# -----------------------------------------------------------------------------
# Inject global CSS for typography standardization & DLP text protection
try:
    with open("src/assets/style.css", "r") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
except Exception as e:
    st.warning(f"Failed to load CSS: {e}")

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
        st.title("Identity Gateway")
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
                    st.error("Invalid username or password")
    return False

def main():
    if not check_password():
        return
        
    st.sidebar.title("BharatTrip Operations")
    
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
        st.sidebar.warning("`GEMINI_API_KEY` not found. Using mocked AI responses for demonstration.")
    
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
    dashboard_p = st.Page(page_dashboard, title="Metrics Dashboard", url_path="dashboard", default=True)
    partners_p = st.Page(page_partners, title="Partner Health Matrix", url_path="partners")
    database_p = st.Page(page_database, title="Database Explorer", url_path="database")
    ingestion_p = st.Page(page_ingestion, title="Ingestion Agent", url_path="ingestion")
    reconciliation_p = st.Page(page_reconciliation, title="Reconciliation (HITL)", url_path="reconciliation")
    triage_p = st.Page(page_triage, title="Escalation Triage", url_path="triage", default=(st.session_state.role != "Manager"))

    # Store pages in session_state for programmatic navigation in other modules
    st.session_state.pages = {
        "dashboard": dashboard_p,
        "partners": partners_p,
        "database": database_p,
        "ingestion": ingestion_p,
        "reconciliation": reconciliation_p,
        "triage": triage_p
    }

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

