"""
Tests for Finance Records REST API endpoints.
"""
from fastapi import status


def test_list_finance_records_empty(client, manager_auth_headers):
    """Verify listing finance records returns empty list when DB has no records."""
    response = client.get("/api/v1/finance-records", headers=manager_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_create_finance_record(client, manager_auth_headers):
    """Verify creating a new finance record."""
    payload = {
        "Ref No": "RF-2001",
        "Agent Name": "Coral Voyages",
        "Sector": "DEL-KUL",
        "Amount Paid (INR)": 22300.0,
        "Deduction (INR)": 0.0,
        "Received On": "04-03-2026",
        "Processed On": "07-03-2026",
        "Payout Status": "Refund Done",
        "Approved By": "N. Iyer",
        "Remarks": "payout complete",
    }
    response = client.post("/api/v1/finance-records", json=payload, headers=manager_auth_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["Ref No"] == "RF-2001"
    assert data["Agent Name"] == "Coral Voyages"
    assert data["Amount Paid (INR)"] == 22300.0


def test_create_duplicate_finance_record_fails(client, sample_finance_record, manager_auth_headers):
    """Verify creating a record with existing Ref No returns 409 Conflict."""
    payload = {
        "Ref No": sample_finance_record.ref_no,
        "Agent Name": "Another Agent",
        "Sector": "BOM-BLR",
    }
    response = client.post("/api/v1/finance-records", json=payload, headers=manager_auth_headers)
    assert response.status_code == status.HTTP_409_CONFLICT


def test_get_finance_record_by_ref_no(client, sample_finance_record, manager_auth_headers):
    """Verify retrieving a single finance record by Ref No."""
    response = client.get(f"/api/v1/finance-records/{sample_finance_record.ref_no}", headers=manager_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["Ref No"] == sample_finance_record.ref_no
    assert data["Agent Name"] == sample_finance_record.agent_name


def test_get_nonexistent_finance_record_returns_404(client, manager_auth_headers):
    """Verify 404 is returned when finance record does not exist."""
    response = client.get("/api/v1/finance-records/RF-NONEXISTENT", headers=manager_auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_finance_record(client, sample_finance_record, manager_auth_headers):
    """Verify updating fields on an existing finance record."""
    update_payload = {
        "Payout Status": "Declined",
        "Remarks": "Rejected by airline policy",
        "Deduction (INR)": 2000.0,
    }
    response = client.patch(
        f"/api/v1/finance-records/{sample_finance_record.ref_no}",
        json=update_payload,
        headers=manager_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["Payout Status"] == "Declined"
    assert data["Remarks"] == "Rejected by airline policy"
    assert data["Deduction (INR)"] == 2000.0


def test_delete_finance_record(client, sample_finance_record, manager_auth_headers):
    """Verify deleting a finance record."""
    response = client.delete(f"/api/v1/finance-records/{sample_finance_record.ref_no}", headers=manager_auth_headers)
    assert response.status_code == status.HTTP_200_OK

    # Confirm it is gone
    get_resp = client.get(f"/api/v1/finance-records/{sample_finance_record.ref_no}", headers=manager_auth_headers)
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


def test_filter_and_search_finance_records(client, sample_finance_record, manager_auth_headers):
    """Verify filtering and search parameters on list endpoint."""
    # Filter by agent name
    resp = client.get("/api/v1/finance-records", params={"agent_name": "Alpha"}, headers=manager_auth_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # Filter by payout status
    resp = client.get("/api/v1/finance-records", params={"payout_status": "Refund Done"}, headers=manager_auth_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # Search keyword
    resp = client.get("/api/v1/finance-records", params={"search": "DEL-BOM"}, headers=manager_auth_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

