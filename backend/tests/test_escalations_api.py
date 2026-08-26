"""
Tests for Escalations REST API endpoints.
"""
from fastapi import status


def test_list_escalations_empty(client):
    """Verify listing escalations returns empty list when DB has no records."""
    response = client.get("/api/v1/escalations")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_create_escalation(client):
    """Verify creating a new escalation."""
    payload = {
        "Escalation ID": "ESC-801",
        "Raised On": "01-03-2026",
        "Ticket ID": "RF-1325",
        "Raised By": "Agent",
        "Agent": "GoFly Holidays",
        "Channel": "Email",
        "Message": "Agent chasing for a status update, no response",
        "Status": "Open",
        "Resolved On": None,
        "Days Open": 5.0,
    }
    response = client.post("/api/v1/escalations", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["Escalation ID"] == "ESC-801"
    assert data["Agent"] == "GoFly Holidays"
    assert data["Ticket ID"] == "RF-1325"


def test_create_duplicate_escalation_fails(client, sample_escalation):
    """Verify creating an escalation with existing Escalation ID returns 409 Conflict."""
    payload = {
        "Escalation ID": sample_escalation.escalation_id,
        "Agent": "Another Agent",
        "Message": "Duplicate test",
    }
    response = client.post("/api/v1/escalations", json=payload)
    assert response.status_code == status.HTTP_409_CONFLICT


def test_get_escalation_by_id(client, sample_escalation):
    """Verify retrieving a single escalation by ID."""
    response = client.get(f"/api/v1/escalations/{sample_escalation.escalation_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["Escalation ID"] == sample_escalation.escalation_id
    assert data["Agent"] == sample_escalation.agent


def test_get_nonexistent_escalation_returns_404(client):
    """Verify 404 is returned when escalation does not exist."""
    response = client.get("/api/v1/escalations/ESC-NONEXISTENT")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_escalation(client, sample_escalation):
    """Verify updating fields on an existing escalation."""
    update_payload = {
        "Status": "Resolved",
        "Resolved On": "10-06-2026",
        "Message": "Issue resolved with airline refund waiver.",
    }
    response = client.patch(
        f"/api/v1/escalations/{sample_escalation.escalation_id}",
        json=update_payload
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["Status"] == "Resolved"
    assert data["Resolved On"] == "10-06-2026"
    assert data["Message"] == "Issue resolved with airline refund waiver."


def test_delete_escalation(client, sample_escalation):
    """Verify deleting an escalation."""
    response = client.delete(f"/api/v1/escalations/{sample_escalation.escalation_id}")
    assert response.status_code == status.HTTP_200_OK

    # Confirm it is gone
    get_resp = client.get(f"/api/v1/escalations/{sample_escalation.escalation_id}")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


def test_filter_and_search_escalations(client, sample_escalation):
    """Verify filtering and search parameters on list endpoint."""
    # Filter by agent
    resp = client.get("/api/v1/escalations", params={"agent": "Alpha"})
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # Filter by status
    resp = client.get("/api/v1/escalations", params={"status": "Open"})
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # Search keyword
    resp = client.get("/api/v1/escalations", params={"search": "disputed"})
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1
