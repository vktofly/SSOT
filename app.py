import streamlit as st
from src.config import HAS_API_KEY
from src.data_manager import load_data
from src.ui_components import render_dashboard, render_ingestion, render_reconciliation, render_database_explorer

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

    if st.session_state.logged_in:
        return True

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Identity Gateway")
        st.markdown("This application is restricted. Please authenticate via your Identity Provider.")
        
        with st.form("login_form"):
            username = st.text_input("Username").strip()
            password = st.text_input("Password", type="password").strip()
            submit = st.form_submit_button("Log In", type="primary", width="stretch")
            
            if submit:
                if username in MOCK_USERS and MOCK_USERS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.role = MOCK_USERS[username]["role"]
                    st.session_state.username = username
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
        st.rerun()
        
    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigate", ["📊 Metrics Dashboard", "📥 Ingestion Agent", "⚖️ Reconciliation (HITL)", "🗄️ Database Explorer"])
    
    if not HAS_API_KEY:
        st.sidebar.warning("⚠️ `GEMINI_API_KEY` not found. Using mocked AI responses for demonstration.")
    
    # Load data once at the entrypoint level
    support_df, finance_df, escalations_df = load_data()

    # Route to the appropriate modular UI component
    if page == "📊 Metrics Dashboard":
        render_dashboard()
    elif page == "📥 Ingestion Agent":
        render_ingestion()
    elif page == "⚖️ Reconciliation (HITL)":
        render_reconciliation(support_df, finance_df)
    elif page == "🗄️ Database Explorer":
        render_database_explorer(support_df, finance_df, escalations_df)

if __name__ == "__main__":
    main()
