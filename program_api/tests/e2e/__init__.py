"""
E2E tests for program-api.

Part of AMA-460: Training Programs Schema

These tests verify program-api endpoints against real Supabase database.
They are designed for nightly runs only, not PR checks.

Run with:
    pytest -m e2e tests/e2e/ -v              # Direct database tests only
    pytest tests/e2e/ --live -v              # Include live API tests
    pytest tests/e2e/ --live --api-url http://localhost:8005 -v

Test Structure:
- conftest.py: Fixtures for Supabase client, test users, cleanup
- test_program_lifecycle.py: Full CRUD lifecycle tests

Test Categories (by class):
- TestDatabaseSmoke: Critical connectivity and schema tests
- TestProgramCrudDirect: Direct database CRUD operations
- TestProgramWithWeeksAndWorkouts: Nested structure tests
- TestCascadeDelete: Foreign key cascade behavior
- TestUserIsolation: RLS and multi-tenant isolation
- TestProgramAPIEndpoints: Live API endpoint tests
- TestGenerationAPIEndpoints: AI generation endpoint tests
- TestProgressionAPIEndpoints: Exercise progression tests
- TestDataIntegrity: Schema constraint validation

Environment Requirements:
- SUPABASE_URL: Supabase project URL
- SUPABASE_SERVICE_ROLE_KEY: Service role key for bypassing RLS
"""
