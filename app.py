import streamlit as st
import json
import os
from src.config import HAS_API_KEY
from src.data_manager import load_data
from src.ui_components import render_dashboard, render_ingestion, render_reconciliation, render_database_explorer, render_escalation_triage

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
    body {
        user-select: none;
        -webkit-user-select: none;
        -ms-user-select: none;
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
    if st.sidebar.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = None
        if os.path.exists(".remember.json"):
            os.remove(".remember.json")
        st.rerun()
        
    st.sidebar.markdown("---")
    
    # Role-Based Access Control (RBAC) Navigation
    if st.session_state.role == "Manager":
        pages = ["📊 Metrics Dashboard", "📥 Ingestion Agent", "⚖️ Reconciliation (HITL)", "🚨 Escalation Triage", "🗄️ Database Explorer"]
    else:
        # Junior Role restrictions
        pages = ["🚨 Escalation Triage"]
        
    # Track navigation via our own session state (never a widget key)
    if "_current_page" not in st.session_state:
        st.session_state._current_page = pages[0]
    
    # Ensure current page is valid for the user's role
    if st.session_state._current_page not in pages:
        st.session_state._current_page = pages[0]
    
    default_idx = pages.index(st.session_state._current_page)
    nav_version = st.session_state.get("_nav_version", 0)
    page = st.sidebar.radio("Navigate", pages, index=default_idx, key=f"nav_v{nav_version}")
    st.session_state._current_page = page
    
    if not HAS_API_KEY:
        st.sidebar.warning("⚠️ `GEMINI_API_KEY` not found. Using mocked AI responses for demonstration.")
    
    # Load data into session state for mutability
    if 'support_df' not in st.session_state:
        sup, fin, esc = load_data()
        st.session_state.support_df = sup.copy()
        st.session_state.finance_df = fin.copy()
        st.session_state.escalations_df = esc.copy()
        
    support_df = st.session_state.support_df
    finance_df = st.session_state.finance_df
    escalations_df = st.session_state.escalations_df

    # Route to the appropriate modular UI component
    if page == "📊 Metrics Dashboard":
        render_dashboard()
    elif page == "📥 Ingestion Agent":
        render_ingestion()
    elif page == "⚖️ Reconciliation (HITL)":
        render_reconciliation(support_df, finance_df)
    elif page == "🚨 Escalation Triage":
        render_escalation_triage(escalations_df, support_df)
    elif page == "🗄️ Database Explorer":
        render_database_explorer(support_df, finance_df, escalations_df)

if __name__ == "__main__":
    main()
