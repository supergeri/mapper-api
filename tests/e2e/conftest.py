"""
E2E test fixtures and configuration.

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service E2E Testing

These fixtures provide:
- Real Supabase client for database verification
- HTTP client for API endpoint testing
- Test data validation utilities
"""
import os
import pytest
from typing import Generator, Optional

import httpx
from dotenv import load_dotenv
from supabase import Client, create_client


# Load environment variables from .env file
load_dotenv()


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run tests against live API (requires mapper-api running on port 8001)",
    )
    parser.addoption(
        "--api-url",
        action="store",
        default="http://localhost:8001",
        help="Base URL for the mapper-api service",
    )


@pytest.fixture(scope="session")
def live_mode(request) -> bool:
    """Check if tests should run against live API."""
    return request.config.getoption("--live")


@pytest.fixture(scope="session")
def api_base_url(request) -> str:
    """Get the API base URL from command line or default."""
    return request.config.getoption("--api-url")


@pytest.fixture(scope="session")
def supabase_url() -> str:
    """Get Supabase URL from environment."""
    url = os.getenv("SUPABASE_URL")
    if not url:
        pytest.skip("SUPABASE_URL environment variable not set")
    return url


@pytest.fixture(scope="session")
def supabase_key() -> str:
    """Get Supabase service role key from environment."""
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_ROLE_KEY environment variable not set")
    return key


@pytest.fixture(scope="session")
def supabase_client(supabase_url: str, supabase_key: str) -> Client:
    """Create a Supabase client for direct database access."""
    return create_client(supabase_url, supabase_key)


@pytest.fixture(scope="session")
def http_client(api_base_url: str) -> Generator[httpx.Client, None, None]:
    """Create an HTTP client for API requests."""
    with httpx.Client(base_url=api_base_url, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def all_exercises(supabase_client: Client) -> list:
    """Fetch all exercises from the database for test validation."""
    result = supabase_client.table("exercises").select("*").execute()
    return result.data or []


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def known_exercise_names() -> list:
    """
    Common exercise names that should exist in the database.
    These are names that should have exact matches or known aliases.
    """
    return [
        "Barbell Bench Press",
        "Barbell Back Squat",
        "Conventional Deadlift",
        "Romanian Deadlift",
        "Pull-Up",
        "Push-Up",
        "Dumbbell Curl",
        "Lat Pulldown",
        "Leg Press",
        "Overhead Press",
    ]


@pytest.fixture
def exercise_aliases() -> dict:
    """
    Common aliases and their expected canonical exercise names.
    Used to test alias matching functionality.
    """
    return {
        "RDL": "Romanian Deadlift",
        "Bench Press": "Barbell Bench Press",
        "Back Squat": "Barbell Back Squat",
        "Squat": "Barbell Back Squat",
        "Deadlift": "Conventional Deadlift",
        "Pull Up": "Pull-Up",
        "Pullup": "Pull-Up",
        "Push Up": "Push-Up",
        "Pushup": "Push-Up",
        "DB Curl": "Dumbbell Curl",
        "Bicep Curl": "Dumbbell Curl",
    }


@pytest.fixture
def muscle_groups() -> list:
    """Valid muscle group values for filtering."""
    return [
        "chest",
        "lats",
        "quadriceps",
        "hamstrings",
        "glutes",
        "biceps",
        "triceps",
        "anterior_deltoid",
        "posterior_deltoid",
        "core",
        "lower_back",
        "traps",
        "forearms",
        "calves",
    ]


@pytest.fixture
def equipment_types() -> list:
    """Valid equipment type values for filtering."""
    return [
        "barbell",
        "dumbbell",
        "cable",
        "machine",
        "bodyweight",
        "kettlebell",
        "pull_up_bar",
        "bench",
    ]


@pytest.fixture
def edge_case_inputs() -> list:
    """
    Edge case inputs for testing robustness.
    These should not crash the system.
    """
    return [
        "",                          # Empty string
        "   ",                       # Whitespace only
        "x" * 500,                   # Very long name
        "!@#$%^&*()",               # Special characters only
        "123456789",                 # Numbers only
        "Bench Press!!!",            # Trailing special chars
        "  Bench Press  ",           # Leading/trailing whitespace
        "BenchPress",                # No spaces
        "BARBELL BENCH PRESS",       # All caps
        "barbell bench press",       # All lowercase
        "Barbell  Bench   Press",    # Extra whitespace
        "Bench\nPress",              # Newline character
        "Bench\tPress",              # Tab character
    ]
