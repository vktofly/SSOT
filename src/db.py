"""
Database persistence layer for BharatTrip SSOT.
Encapsulates SQLite connection management, parameterized queries, and transactional updates.
"""
import sqlite3
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

DB_PATH: str = "data/ssot.db"

def get_connection() -> sqlite3.Connection:
    """Returns a new SQLite database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def insert_support_record(record: Dict[str, Any]) -> bool:
    """Inserts a single new record into the support_tracker table using parameterized SQL."""
    if not record:
        return False
        
    columns = ', '.join(f'"{k}"' for k in record.keys())
    placeholders = ', '.join('?' for _ in record.values())
    values = tuple(record.values())
    query = f"INSERT INTO support_tracker ({columns}) VALUES ({placeholders})"
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
        return True
    except sqlite3.Error as err:
        logger.error("Failed to insert support record: %s", err)
        return False

def update_support_status(ticket_id: str, new_status: str, appended_notes: str) -> bool:
    """Updates the status and notes of a specific support ticket."""
    if not ticket_id:
        return False
        
    query = 'UPDATE support_tracker SET "Status" = ?, "Notes" = ? WHERE "Ticket ID" = ?'
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (new_status, appended_notes, ticket_id))
            conn.commit()
        return True
    except sqlite3.Error as err:
        logger.error("Failed to update support status for ticket %s: %s", ticket_id, err)
        return False

def delete_escalation(ticket_id: str, message: str) -> bool:
    """Deletes an escalation from the active queue using parameterized Ticket ID and Message."""
    query = 'DELETE FROM escalations WHERE "Ticket ID" = ? AND "Message" = ?'
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (ticket_id, message))
            conn.commit()
        return True
    except sqlite3.Error as err:
        logger.error("Failed to delete escalation: %s", err)
        return False

def update_ticket_id(old_id: str, new_id: str) -> bool:
    """Updates the Ticket ID across the support_tracker to match Finance."""
    if not old_id or not new_id:
        return False
        
    query = 'UPDATE support_tracker SET "Ticket ID" = ? WHERE "Ticket ID" = ?'
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (new_id, old_id))
            conn.commit()
        return True
    except sqlite3.Error as err:
        logger.error("Failed to update ticket ID from %s to %s: %s", old_id, new_id, err)
        return False
