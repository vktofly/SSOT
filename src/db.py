import sqlite3
import pandas as pd
import os
import streamlit as st

DB_PATH = "data/ssot.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def insert_support_record(record: dict):
    """Inserts a single new record into the support_tracker table."""
    conn = get_connection()
    cursor = conn.cursor()
    
    columns = ', '.join(f'"{k}"' for k in record.keys())
    placeholders = ', '.join('?' for _ in record.values())
    values = tuple(record.values())
    
    query = f"INSERT INTO support_tracker ({columns}) VALUES ({placeholders})"
    try:
        cursor.execute(query, values)
        conn.commit()
    except Exception as e:
        print(f"Error inserting record: {e}")
    finally:
        conn.close()

def update_support_status(ticket_id: str, new_status: str, appended_notes: str):
    """Updates the status and notes of a specific support ticket."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # We update the fields where `Ticket ID` matches
    query = 'UPDATE support_tracker SET "Status" = ?, "Notes" = ? WHERE "Ticket ID" = ?'
    try:
        cursor.execute(query, (new_status, appended_notes, ticket_id))
        conn.commit()
    except Exception as e:
        print(f"Error updating record: {e}")
    finally:
        conn.close()

def delete_escalation(ticket_id: str, message: str):
    """Deletes an escalation from the active queue using Ticket ID and Message."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Use exact match or coalesce for nulls depending on data
    query = 'DELETE FROM escalations WHERE "Ticket ID" = ? AND "Message" = ?'
    try:
        cursor.execute(query, (ticket_id, message))
        conn.commit()
    except Exception as e:
        print(f"Error deleting record: {e}")
    finally:
        conn.close()

def update_ticket_id(old_id: str, new_id: str):
    """Updates the Ticket ID across the support_tracker to match Finance."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'UPDATE support_tracker SET "Ticket ID" = ? WHERE "Ticket ID" = ?'
    try:
        cursor.execute(query, (new_id, old_id))
        conn.commit()
    except Exception as e:
        print(f"Error updating ticket ID: {e}")
    finally:
        conn.close()
