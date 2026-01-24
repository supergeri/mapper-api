"""
E2E tests for AmakaFlow Mapper API.

These tests run against real services (Supabase database, API endpoints)
and should only be executed in CI nightly runs or explicitly by developers.

Usage:
    pytest -m e2e tests/e2e/       # Run all E2E tests
    pytest tests/e2e/ --live       # Run with live API flag
"""
