import streamlit as st
import pandas as pd
from typing import Dict, Any, List

@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads and preprocesses the CSV data representing our SSOT."""
    try:
        support = pd.read_csv("data/Support_Tracker.csv", skiprows=1)
        if 'Ticket ID' not in support.columns:
            support.columns = support.iloc[0]
            support = support.drop(0)
            
        finance = pd.read_csv("data/Finance_Tracker.csv", skiprows=1)
        if 'Ref No' not in finance.columns:
            finance.columns = finance.iloc[0]
            finance = finance.drop(0)
            
        escalations = pd.read_csv("data/Escalations.csv")
        
        support['Ticket ID'] = support['Ticket ID'].astype(str).str.strip().str.upper()
        finance['Ref No'] = finance['Ref No'].astype(str).str.strip().str.upper()
        
        return support, finance, escalations
    except Exception as e:
        st.error(f"Failed to load datasets: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def find_mismatches(support: pd.DataFrame, finance: pd.DataFrame) -> List[Dict[str, Any]]:
    """Analyzes datasets to find discrepancies between Support and Finance amounts."""
    mismatches = []
    for _, f_row in finance.iterrows():
        ref = f_row['Ref No']
        s_row = support[support['Ticket ID'] == ref]
        if not s_row.empty:
            s_row = s_row.iloc[0]
            try:
                s_amt = float(s_row['Refund Amount (INR)'])
                f_amt = float(f_row['Amount Paid (INR)'])
                deduction = float(f_row['Deduction (INR)'])
                
                if s_amt != f_amt:
                    mismatches.append({
                        "Ticket ID": ref,
                        "Agent": s_row.get('Agent', 'Unknown'),
                        "Route": s_row.get('Route', 'Unknown'),
                        "Support Amount": s_amt,
                        "Finance Amount": f_amt,
                        "Deduction": deduction,
                        "Reason": f_row.get('Remarks', 'No reason given')
                    })
            except ValueError:
                continue
    return mismatches
