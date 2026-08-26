"""
Tests for main FastAPI application entrypoint, root, and health checks.
"""
from fastapi import status


def test_health_check(client):
    """Verify /health returns healthy status."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "BharatTrip SSOT API"


def test_root_endpoint(client):
    """Verify / root returns welcome metadata and docs URLs."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "docs_url" in data
    assert data["docs_url"] == "/docs"
