"""
Integration tests for generation API.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-462: Tests for implemented generation endpoint

Tests program generation endpoint with mocked AI.
"""

import pytest


# ---------------------------------------------------------------------------
# Generation Endpoint Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGenerateProgram:
    """Integration tests for POST /generate."""

    def test_generate_program_success(self, client_with_all_fakes, sample_generation_request):
        """Generate returns success with program."""
        response = client_with_all_fakes.post("/generate", json=sample_generation_request)

        # Endpoint is now implemented
        assert response.status_code in [200, 201]
        data = response.json()
        assert "program" in data
        assert "weeks" in data["program"]

    def test_generate_program_validation_error(self, client_with_all_fakes):
        """Invalid payload returns 422."""
        response = client_with_all_fakes.post(
            "/generate",
            json={"goal": "strength"},  # Missing required fields
        )

        assert response.status_code == 422

    def test_generate_program_all_goals(self, client_with_all_fakes):
        """All goal types are accepted by validation."""
        goals = ["strength", "hypertrophy", "endurance", "weight_loss", "general_fitness"]

        for goal in goals:
            response = client_with_all_fakes.post(
                "/generate",
                json={
                    "goal": goal,
                    "duration_weeks": 4,
                    "sessions_per_week": 3,
                    "experience_level": "intermediate",
                    "equipment_available": ["barbell", "dumbbells", "bench", "squat_rack"],
                },
            )

            # Now returns success
            assert response.status_code in [200, 201], f"Failed for goal: {goal}"

    def test_generate_program_all_experience_levels(self, client_with_all_fakes):
        """All experience levels are accepted by validation."""
        levels = ["beginner", "intermediate", "advanced"]

        for level in levels:
            response = client_with_all_fakes.post(
                "/generate",
                json={
                    "goal": "strength",
                    "duration_weeks": 4,
                    "sessions_per_week": 3,
                    "experience_level": level,
                    "equipment_available": ["barbell", "dumbbells", "bench", "squat_rack"],
                },
            )

            # Now returns success
            assert response.status_code in [200, 201], f"Failed for level: {level}"

    def test_generate_program_with_optional_fields(self, client_with_all_fakes):
        """Optional fields are accepted."""
        response = client_with_all_fakes.post(
            "/generate",
            json={
                "goal": "hypertrophy",
                "duration_weeks": 4,
                "sessions_per_week": 4,
                "experience_level": "advanced",
                "equipment_available": ["barbell", "dumbbells", "cables", "bench", "squat_rack"],
                "focus_areas": ["chest", "shoulders"],
                "limitations": ["lower back pain"],
                "preferences": "Prefer high volume training",
            },
        )

        # Now returns success
        assert response.status_code in [200, 201]


# ---------------------------------------------------------------------------
# Boundary Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGenerateProgramBoundaries:
    """Boundary tests for generation parameters."""

    def test_minimum_duration(self, client_with_all_fakes):
        """Minimum duration (1 week) is accepted."""
        response = client_with_all_fakes.post(
            "/generate",
            json={
                "goal": "strength",
                "duration_weeks": 1,
                "sessions_per_week": 3,
                "experience_level": "beginner",
                "equipment_available": ["barbell", "dumbbells", "bench", "squat_rack"],
            },
        )

        assert response.status_code in [200, 201]

    def test_maximum_duration(self, client_with_all_fakes):
        """Maximum duration (52 weeks) is accepted."""
        response = client_with_all_fakes.post(
            "/generate",
            json={
                "goal": "strength",
                "duration_weeks": 52,
                "sessions_per_week": 3,
                "experience_level": "beginner",
                "equipment_available": ["barbell", "dumbbells", "bench", "squat_rack"],
            },
        )

        assert response.status_code in [200, 201]

    def test_minimum_sessions(self, client_with_all_fakes):
        """Minimum sessions (1/week) is accepted."""
        response = client_with_all_fakes.post(
            "/generate",
            json={
                "goal": "strength",
                "duration_weeks": 4,
                "sessions_per_week": 1,
                "experience_level": "beginner",
                "equipment_available": ["barbell", "dumbbells", "bench", "squat_rack"],
            },
        )

        assert response.status_code in [200, 201]

    def test_maximum_sessions(self, client_with_all_fakes):
        """Maximum sessions (7/week) is accepted."""
        response = client_with_all_fakes.post(
            "/generate",
            json={
                "goal": "strength",
                "duration_weeks": 4,
                "sessions_per_week": 7,
                "experience_level": "advanced",
                "equipment_available": ["barbell", "dumbbells", "bench", "squat_rack"],
            },
        )

        assert response.status_code in [200, 201]
