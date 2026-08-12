import streamlit as st
import pandas as pd
import difflib
from typing import Dict, Any, List
from src.agents import fuzzy_match_metadata

import sqlite3
from src.db import DB_PATH, get_connection

@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads data from SQLite, seeding it from CSVs on first run."""
    try:
        # Check if DB exists
        import os
        needs_init = not os.path.exists(DB_PATH)
        
        if needs_init:
            seed_from_csv()
            
        conn = get_connection()
        support = pd.read_sql("SELECT * FROM support_tracker", conn)
        finance = pd.read_sql("SELECT * FROM finance_tracker", conn)
        escalations = pd.read_sql("SELECT * FROM escalations", conn)
        conn.close()
        
        return support, finance, escalations
    except Exception as e:
        st.error(f"Failed to load datasets: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def seed_from_csv():
    """Seeds the SQLite database from the raw CSV files."""
    try:
        support = pd.read_csv("data/Support_Tracker.csv", skiprows=1)
        if 'Ticket ID' not in support.columns:
            support.columns = support.iloc[0]
            support = support.drop(0)
            
        finance = pd.read_csv("data/Finance_Tracker.csv", skiprows=1)
        if 'Ref No' not in finance.columns:
            finance.columns = finance.iloc[0]
            finance = finance.drop(0)
            
        escalations = pd.read_csv("data/Escalations.csv", skiprows=1)
        if 'Escalation ID' not in escalations.columns and len(escalations.columns) > 1:
            escalations.columns = escalations.iloc[0]
            escalations = escalations.drop(0)
            
        # Standardize escalation column names for UI
        if 'Related Ticket / Ref' in escalations.columns:
            escalations = escalations.rename(columns={
                'Related Ticket / Ref': 'Ticket ID',
                'Agent / Team': 'Agent',
                'Complaint': 'Message'
            })
        
        # Clean Data
        def clean_money(val):
            if pd.isna(val): return val
            return str(val).replace(',', '').replace('₹', '').replace('INR', '').strip()
            
        if 'Refund Amount (INR)' in support.columns:
            support['Refund Amount (INR)'] = support['Refund Amount (INR)'].apply(clean_money)
        if 'Amount Paid (INR)' in finance.columns:
            finance['Amount Paid (INR)'] = finance['Amount Paid (INR)'].apply(clean_money)
        if 'Deduction (INR)' in finance.columns:
            finance['Deduction (INR)'] = finance['Deduction (INR)'].apply(clean_money)
            
        support['Ticket ID'] = support['Ticket ID'].astype(str).str.strip().str.upper()
        finance['Ref No'] = finance['Ref No'].astype(str).str.strip().str.upper()
        
        conn = sqlite3.connect(DB_PATH)
        support.to_sql("support_tracker", conn, if_exists="replace", index=False)
        finance.to_sql("finance_tracker", conn, if_exists="replace", index=False)
        escalations.to_sql("escalations", conn, if_exists="replace", index=False)
        conn.close()
        
    except Exception as e:
        print(f"Error seeding DB: {e}")

def find_mismatches(support: pd.DataFrame, finance: pd.DataFrame) -> List[Dict[str, Any]]:
    """Analyzes datasets to find discrepancies between Support and Finance amounts, using difflib for ID matching."""
    mismatches = []
    support_ids = support['Ticket ID'].dropna().astype(str).tolist()
    
    for _, f_row in finance.iterrows():
        ref = str(f_row['Ref No'])
        s_row = None
        
        # 1. Exact Match
        exact_matches = support[support['Ticket ID'] == ref]
        if not exact_matches.empty:
            s_row = exact_matches.iloc[0]
        else:
            # 2. Difflib Fuzzy Match on ID (Lexical matching for typos like RF-1099 vs 1099)
            close_matches = difflib.get_close_matches(ref, support_ids, n=1, cutoff=0.7)
            if close_matches:
                s_row = support[support['Ticket ID'] == close_matches[0]].iloc[0]
                
        if s_row is not None:
            try:
                # Clean strings before casting to float
                s_amt_str = str(s_row['Refund Amount (INR)']).replace(',', '').strip()
                f_amt_str = str(f_row['Amount Paid (INR)']).replace(',', '').strip()
                deduction_str = str(f_row.get('Deduction (INR)', '0')).replace(',', '').strip()
                
                s_amt = float(s_amt_str) if s_amt_str and s_amt_str.lower() != 'nan' else 0.0
                f_amt = float(f_amt_str) if f_amt_str and f_amt_str.lower() != 'nan' else 0.0
                deduction = float(deduction_str) if deduction_str and deduction_str.lower() != 'nan' else 0.0
                
                if s_amt != f_amt:
                    # Calculate percentage difference based on Support Amount
                    risk_level = "Normal"
                    if s_amt > 0:
                        pct_diff = abs(s_amt - f_amt) / s_amt
                        if pct_diff > 0.2:
                            risk_level = "High"
                    elif f_amt > 0:
                        # If Support amount is 0 but finance amount is > 0, that's infinite difference
                        risk_level = "High"
                        
                    mismatches.append({
                        "Ticket ID": str(s_row['Ticket ID']),
                        "Finance Ref No": ref,
                        "Agent": s_row.get('Agent', 'Unknown'),
                        "Route": s_row.get('Route', 'Unknown'),
                        "Support Amount": s_amt,
                        "Finance Amount": f_amt,
                        "Deduction": deduction,
                        "Reason": f_row.get('Remarks', 'No reason given'),
                        "Risk Level": risk_level
                    })
            except ValueError:
                continue
    return mismatches

def find_orphans(support: pd.DataFrame, finance: pd.DataFrame) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Finds tickets that exist in Support but not Finance, and vice-versa.
    Also returns them as lists of dicts for the UI.
    """
    support_ids = support['Ticket ID'].dropna().astype(str).tolist()
    finance_ids = finance['Ref No'].dropna().astype(str).tolist()
    
    # We use exact match + difflib here to consider a ticket "found"
    # To be fast, we'll build sets
    
    missing_in_finance = []
    missing_in_support = []
    
    # Check Support tickets missing in Finance
    for _, s_row in support.iterrows():
        sid = str(s_row['Ticket ID'])
        if sid not in finance_ids:
            # Try fuzzy
            close = difflib.get_close_matches(sid, finance_ids, n=1, cutoff=0.7)
            if not close:
                missing_in_finance.append(s_row.to_dict())
                
    # Check Finance tickets missing in Support
    for _, f_row in finance.iterrows():
        ref = str(f_row['Ref No'])
        if ref not in support_ids:
            # Let's see if difflib finds it
            close_matches = difflib.get_close_matches(ref, support_ids, n=1, cutoff=0.7)
            if not close_matches:
                missing_in_support.append({
                    "Ref No": ref,
                    "Finance Amount": f_row.get('Amount Paid (INR)', 0),
                    "Remarks": f_row.get('Remarks', 'No info')
                })
                
    # Evaluate Agent Risk for unlogged payouts
    from collections import Counter
    agent_counts = Counter([m['Agent'] for m in missing_in_finance])
    
    for m in missing_in_finance:
        agent = m['Agent']
        if agent_counts[agent] > 2:
            m['Risk Level'] = 'High'
            m['Risk Note'] = f"Agent '{agent}' has {agent_counts[agent]} unlogged payouts."
        else:
            m['Risk Level'] = 'Normal'
            m['Risk Note'] = ''

    return missing_in_finance, missing_in_support
