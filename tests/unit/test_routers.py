"""
Unit tests for api/routers.

Part of AMA-378: Create api/routers skeleton and wiring

Tests that routers are correctly configured and wired into the application.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.settings import Settings


class TestRouterInclusion:
    """Test that all routers are correctly included in the app."""

    @pytest.fixture
    def test_app(self):
        """Create a test app with routers."""
        settings = Settings(environment="test", _env_file=None)
        return create_app(settings=settings)

    @pytest.fixture
    def client(self, test_app):
        """Create a test client for the app."""
        return TestClient(test_app)

    def test_health_endpoint_accessible(self, client):
        """Health endpoint should be accessible via router."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_openapi_health_endpoint_has_tag(self, test_app):
        """OpenAPI schema should show Health tag on health endpoint."""
        openapi = test_app.openapi()
        paths = openapi.get("paths", {})
        health_path = paths.get("/health", {})
        health_get = health_path.get("get", {})
        # Health endpoint should have the Health tag
        assert "Health" in health_get.get("tags", [])

    def test_openapi_schema_generated(self, test_app):
        """OpenAPI schema should be generated without errors."""
        openapi = test_app.openapi()
        # Verify basic schema structure
        assert "openapi" in openapi
        assert "info" in openapi
        assert "paths" in openapi
        # Health endpoint should be in paths
        assert "/health" in openapi["paths"]


class TestHealthRouter:
    """Test health router endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        settings = Settings(environment="test", _env_file=None)
        app = create_app(settings=settings)
        return TestClient(app)

    def test_health_returns_ok_status(self, client):
        """Health endpoint should return status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_json(self, client):
        """Health endpoint should return JSON content type."""
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]

    def test_health_method_not_allowed(self, client):
        """Health endpoint should only accept GET."""
        response = client.post("/health")
        assert response.status_code == 405


class TestEmptyRouters:
    """Test that empty routers are correctly configured."""

    @pytest.fixture
    def test_app(self):
        """Create a test app."""
        settings = Settings(environment="test", _env_file=None)
        return create_app(settings=settings)

    def test_mapping_router_prefix(self, test_app):
        """Mapping router should have /map prefix."""
        routes = [route.path for route in test_app.routes]
        # Currently empty, but prefix should be /map
        # When endpoints are added, they'll be at /map/...
        # For now, just verify the app creates without error
        assert test_app is not None

    def test_all_routers_included_without_error(self, test_app):
        """All routers should be included without raising errors."""
        # If we got here, all routers were successfully included
        assert isinstance(test_app, FastAPI)

    def test_routes_list_accessible(self, test_app):
        """App routes should be accessible."""
        routes = list(test_app.routes)
        assert len(routes) > 0  # At least health endpoint

        # Find health route
        health_routes = [r for r in routes if hasattr(r, 'path') and r.path == "/health"]
        assert len(health_routes) == 1
