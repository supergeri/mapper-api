"""
Health endpoint tests.

Part of AMA-461: Create program-api service scaffold
"""

import pytest


@pytest.mark.unit
def test_health_returns_ok(client):
    """Health endpoint should return ok status."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.unit
def test_health_returns_service_name(client):
    """Health endpoint should return service name."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "program-api"
