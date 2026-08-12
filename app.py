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

def main():
    st.sidebar.title("✈️ BharatTrip Operations")
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
