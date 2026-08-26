import streamlit as st
import json
import os
from src.config import HAS_API_KEY
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
    page_icon="src/assets/logo.jpg",
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

from src.auth import init_auth_state, render_login_gate, logout, require_role

def main():
    init_auth_state()
    if not render_login_gate():
        return
        
    st.logo("src/assets/logo.jpg")
    
    if not HAS_API_KEY:
        st.sidebar.warning("`GEMINI_API_KEY` not found. Using mocked responses.")
    
    # Page wrappers ensuring clean REST API client usage and RBAC defense-in-depth
    def page_dashboard():
        require_role(["Manager"])
        render_dashboard()

    def page_ingestion():
        render_ingestion()

    def page_reconciliation():
        require_role(["Manager"])
        render_reconciliation()

    def page_triage():
        render_escalation_triage()

    def page_database():
        render_database_explorer()

    def page_partners():
        require_role(["Manager"])
        render_partner_matrix()

    # Declarative Multi-Page Declarations with clean URL paths
    dashboard_p = st.Page(page_dashboard, title="Metrics Dashboard", url_path="dashboard", icon=":material/dashboard:", default=True)
    partners_p = st.Page(page_partners, title="Partner Health Matrix", url_path="partners", icon=":material/handshake:")
    database_p = st.Page(page_database, title="Database Explorer", url_path="database", icon=":material/database:")
    ingestion_p = st.Page(page_ingestion, title="Ingestion Agent", url_path="ingestion", icon=":material/smart_toy:")
    reconciliation_p = st.Page(page_reconciliation, title="Reconciliation (HITL)", url_path="reconciliation", icon=":material/receipt_long:")
    triage_p = st.Page(page_triage, title="Escalation Triage", url_path="triage", icon=":material/support_agent:", default=(st.session_state.role != "Manager"))

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
            "Operator Workspace": [triage_p, ingestion_p, database_p]
        }

    pg = st.navigation(nav_dict)
    
    st.sidebar.markdown("---")
    user_display = st.session_state.get("username") or st.session_state.get("role") or "User"
    user_role = st.session_state.get("role") or "Unknown"
    st.sidebar.markdown(f"**Logged in as:** {user_display} (`{user_role}`)")
    if st.sidebar.button("Log Out", use_container_width=True):
        logout()
        
    pg.run()

if __name__ == "__main__":
    main()


