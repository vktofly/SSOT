"""
Tests for Support Tickets REST API endpoints.
"""
import pytest
from fastapi import status


def test_list_support_tickets_empty(client):
    """Verify listing support tickets returns empty list when DB has no records."""
    response = client.get("/api/v1/support-tickets")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_create_support_ticket(client):
    """Verify creating a new support ticket."""
    payload = {
        "Ticket ID": "RF-1001",
        "Agent": "Sunrise Trips",
        "Route": "DEL-KTM",
        "Refund Amount (INR)": 10200.0,
        "Request Date": "25-05-2026",
        "Last Updated": "31-05-2026",
        "Status": "Pending",
        "Handled By": "Aditi M.",
        "Channel": "WhatsApp",
        "Notes": "refund processed, informed agent",
    }
    response = client.post("/api/v1/support-tickets", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["Ticket ID"] == "RF-1001"
    assert data["Agent"] == "Sunrise Trips"
    assert data["Refund Amount (INR)"] == 10200.0


def test_create_duplicate_support_ticket_fails(client, sample_support_ticket):
    """Verify creating a ticket with existing Ticket ID returns 409 Conflict."""
    payload = {
        "Ticket ID": sample_support_ticket.ticket_id,
        "Agent": "Another Agent",
        "Route": "BOM-BLR",
    }
    response = client.post("/api/v1/support-tickets", json=payload)
    assert response.status_code == status.HTTP_409_CONFLICT


def test_get_support_ticket_by_id(client, sample_support_ticket):
    """Verify retrieving a single ticket by ID."""
    response = client.get(f"/api/v1/support-tickets/{sample_support_ticket.ticket_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["Ticket ID"] == sample_support_ticket.ticket_id
    assert data["Agent"] == sample_support_ticket.agent


def test_get_nonexistent_support_ticket_returns_404(client):
    """Verify 404 is returned when ticket does not exist."""
    response = client.get("/api/v1/support-tickets/RF-NONEXISTENT")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_support_ticket(client, sample_support_ticket):
    """Verify updating fields on an existing support ticket."""
    update_payload = {
        "Status": "Closed",
        "Notes": "Refund processed and closed",
        "Refund Amount (INR)": 15000.0,
    }
    response = client.patch(
        f"/api/v1/support-tickets/{sample_support_ticket.ticket_id}",
        json=update_payload
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["Status"] == "Closed"
    assert data["Notes"] == "Refund processed and closed"
    assert data["Refund Amount (INR)"] == 15000.0


def test_delete_support_ticket(client, sample_support_ticket):
    """Verify deleting a support ticket."""
    response = client.delete(f"/api/v1/support-tickets/{sample_support_ticket.ticket_id}")
    assert response.status_code == status.HTTP_200_OK

    # Confirm it is gone
    get_resp = client.get(f"/api/v1/support-tickets/{sample_support_ticket.ticket_id}")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


def test_filter_and_search_support_tickets(client, sample_support_ticket):
    """Verify filtering and search parameters on list endpoint."""
    # Filter by agent
    resp = client.get("/api/v1/support-tickets", params={"agent": "Alpha"})
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # Filter by status
    resp = client.get("/api/v1/support-tickets", params={"status": "Pending"})
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # Search keyword
    resp = client.get("/api/v1/support-tickets", params={"search": "DEL-BOM"})
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # Non-matching search
    resp = client.get("/api/v1/support-tickets", params={"search": "NON_MATCHING_KEYWORD"})
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 0
