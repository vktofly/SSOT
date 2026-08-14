"""
Data Manager Module for BharatTrip Operations.
Handles SQLite data hydration, CSV ingestion/seeding, discrepancy analysis, and orphan matching.
"""
import os
import difflib
import sqlite3
import logging
from collections import Counter
from typing import Dict, Any, List, Tuple
import pandas as pd
import streamlit as st
from src.db import DB_PATH, get_connection

logger = logging.getLogger(__name__)

# Standardized Constants
DEFAULT_DIFFLIB_CUTOFF: float = 0.7
HIGH_RISK_DIFF_RATIO: float = 0.20
HIGH_RISK_UNLOGGED_AGENT_THRESHOLD: int = 2

def clean_money_string(value: Any) -> str:
    """Sanitizes monetary string representations removing currency symbols, commas, and whitespace."""
    if pd.isna(value):
        return ""
    return str(value).replace(',', '').replace('₹', '').replace('INR', '').strip()

@st.cache_data(show_spinner=False)
def load_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads all 3 operational datasets from SQLite, automatically seeding from CSVs on first run."""
    try:
        needs_init = not os.path.exists(DB_PATH)
        if needs_init:
            seed_from_csv()
            
        with get_connection() as conn:
            support = pd.read_sql("SELECT * FROM support_tracker", conn)
            finance = pd.read_sql("SELECT * FROM finance_tracker", conn)
            escalations = pd.read_sql("SELECT * FROM escalations", conn)
            
        return support, finance, escalations
    except Exception as err:
        logger.error("Failed to load datasets: %s", err)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def seed_from_csv() -> None:
    """Seeds the SQLite database from raw baseline CSV files."""
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
            
        if 'Related Ticket / Ref' in escalations.columns:
            escalations = escalations.rename(columns={
                'Related Ticket / Ref': 'Ticket ID',
                'Agent / Team': 'Agent',
                'Complaint': 'Message'
            })
        
        # Clean currency columns
        if 'Refund Amount (INR)' in support.columns:
            support['Refund Amount (INR)'] = support['Refund Amount (INR)'].apply(clean_money_string)
        if 'Amount Paid (INR)' in finance.columns:
            finance['Amount Paid (INR)'] = finance['Amount Paid (INR)'].apply(clean_money_string)
        if 'Deduction (INR)' in finance.columns:
            finance['Deduction (INR)'] = finance['Deduction (INR)'].apply(clean_money_string)
            
        support['Ticket ID'] = support['Ticket ID'].astype(str).str.strip().str.upper()
        finance['Ref No'] = finance['Ref No'].astype(str).str.strip().str.upper()
        
        with sqlite3.connect(DB_PATH) as conn:
            support.to_sql("support_tracker", conn, if_exists="replace", index=False)
            finance.to_sql("finance_tracker", conn, if_exists="replace", index=False)
            escalations.to_sql("escalations", conn, if_exists="replace", index=False)
            
        logger.info("Successfully seeded database from baseline CSVs.")
    except Exception as err:
        logger.error("Error seeding DB: %s", err)

def find_mismatches(support: pd.DataFrame, finance: pd.DataFrame) -> List[Dict[str, Any]]:
    """Analyzes datasets to identify financial discrepancies between Support and Finance amounts."""
    if support.empty or finance.empty:
        return []
        
    mismatches: List[Dict[str, Any]] = []
    support_ids = support['Ticket ID'].dropna().astype(str).tolist()
    
    for _, f_row in finance.iterrows():
        ref = str(f_row['Ref No'])
        s_row = None
        
        # 1. Exact Match
        exact_matches = support[support['Ticket ID'] == ref]
        if not exact_matches.empty:
            s_row = exact_matches.iloc[0]
        else:
            # 2. Fuzzy Match on Ticket ID (Lexical matching for typos)
            close_matches = difflib.get_close_matches(ref, support_ids, n=1, cutoff=DEFAULT_DIFFLIB_CUTOFF)
            if close_matches:
                s_row = support[support['Ticket ID'] == close_matches[0]].iloc[0]
                
        if s_row is not None:
            try:
                s_amt_str = clean_money_string(s_row.get('Refund Amount (INR)', '0'))
                f_amt_str = clean_money_string(f_row.get('Amount Paid (INR)', '0'))
                deduction_str = clean_money_string(f_row.get('Deduction (INR)', '0'))
                
                s_amt = float(s_amt_str) if s_amt_str and s_amt_str.lower() != 'nan' else 0.0
                f_amt = float(f_amt_str) if f_amt_str and f_amt_str.lower() != 'nan' else 0.0
                deduction = float(deduction_str) if deduction_str and deduction_str.lower() != 'nan' else 0.0
                
                if s_amt != f_amt:
                    risk_level = "Normal"
                    if s_amt > 0:
                        pct_diff = abs(s_amt - f_amt) / s_amt
                        if pct_diff > HIGH_RISK_DIFF_RATIO:
                            risk_level = "High"
                    elif f_amt > 0:
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
            except (ValueError, TypeError):
                continue
                
    return mismatches

def find_orphans(support: pd.DataFrame, finance: pd.DataFrame) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Identifies orphaned records missing in Support or missing in Finance."""
    if support.empty or finance.empty:
        return [], []
        
    support_ids = support['Ticket ID'].dropna().astype(str).tolist()
    finance_ids = finance['Ref No'].dropna().astype(str).tolist()
    
    missing_in_finance: List[Dict[str, Any]] = []
    missing_in_support: List[Dict[str, Any]] = []
    
    # Check Support tickets missing in Finance
    for _, s_row in support.iterrows():
        sid = str(s_row['Ticket ID'])
        if sid not in finance_ids:
            close = difflib.get_close_matches(sid, finance_ids, n=1, cutoff=DEFAULT_DIFFLIB_CUTOFF)
            if not close:
                missing_in_finance.append(s_row.to_dict())
                
    # Check Finance tickets missing in Support
    for _, f_row in finance.iterrows():
        ref = str(f_row['Ref No'])
        if ref not in support_ids:
            close_matches = difflib.get_close_matches(ref, support_ids, n=1, cutoff=DEFAULT_DIFFLIB_CUTOFF)
            if not close_matches:
                missing_in_support.append({
                    "Ref No": ref,
                    "Finance Amount": f_row.get('Amount Paid (INR)', 0),
                    "Remarks": f_row.get('Remarks', 'No info'),
                    "Agent Name": f_row.get('Agent Name', 'Unknown'),
                    "Route": f_row.get('Route', 'Unknown')
                })
                
    # Evaluate Agent Risk for unlogged payouts
    agent_counts = Counter([str(m.get('Agent', 'Unknown')) for m in missing_in_finance])
    for m in missing_in_finance:
        agent = str(m.get('Agent', 'Unknown'))
        if agent_counts[agent] > HIGH_RISK_UNLOGGED_AGENT_THRESHOLD:
            m['Risk Level'] = 'High'
            m['Risk Note'] = f"Agent '{agent}' has {agent_counts[agent]} unlogged payouts."
        else:
            m['Risk Level'] = 'Normal'
            m['Risk Note'] = ''

    return missing_in_finance, missing_in_support
