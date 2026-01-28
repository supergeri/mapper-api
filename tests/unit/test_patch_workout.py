"""
Unit tests for PatchWorkoutUseCase and patch operations.

Part of AMA-433: PATCH /workouts/{id} endpoint implementation

Tests for:
- PatchOperation model validation
- Path parsing and validation
- Apply operations to workout data
- PatchWorkoutUseCase with mocked Supabase
- Error handling and validation
"""

import copy
import pytest
from unittest.mock import MagicMock, patch

from domain.models.patch_operation import (
    PatchOperation,
    PatchOperationList,
    parse_path,
    validate_path_structure,
    VALID_ROOT_PATHS,
    VALID_EXERCISE_FIELDS,
)
from application.use_cases.patch_workout import (
    PatchWorkoutUseCase,
    PatchWorkoutResult,
    PatchValidationError,
)


# =============================================================================
# PatchOperation Model Tests
# =============================================================================


class TestPatchOperationModel:
    """Tests for PatchOperation Pydantic model."""

    @pytest.mark.unit
    def test_valid_replace_operation(self):
        """Valid replace operation is accepted."""
        op = PatchOperation(op="replace", path="/title", value="New Title")
        assert op.op == "replace"
        assert op.path == "/title"
        assert op.value == "New Title"

    @pytest.mark.unit
    def test_valid_add_operation(self):
        """Valid add operation is accepted."""
        op = PatchOperation(op="add", path="/tags/-", value="strength")
        assert op.op == "add"
        assert op.path == "/tags/-"
        assert op.value == "strength"

    @pytest.mark.unit
    def test_valid_remove_operation(self):
        """Valid remove operation is accepted."""
        op = PatchOperation(op="remove", path="/exercises/2")
        assert op.op == "remove"
        assert op.path == "/exercises/2"
        assert op.value is None

    @pytest.mark.unit
    def test_invalid_op_rejected(self):
        """Invalid operation type is rejected."""
        with pytest.raises(Exception):
            PatchOperation(op="invalid", path="/title", value="test")

    @pytest.mark.unit
    def test_path_must_start_with_slash(self):
        """Path must start with /."""
        with pytest.raises(Exception):
            PatchOperation(op="replace", path="title", value="test")

    @pytest.mark.unit
    def test_empty_path_rejected(self):
        """Empty path is rejected."""
        with pytest.raises(Exception):
            PatchOperation(op="replace", path="", value="test")


class TestPatchOperationList:
    """Tests for PatchOperationList model."""

    @pytest.mark.unit
    def test_valid_operation_list(self):
        """Valid operation list is accepted."""
        ops = PatchOperationList(
            operations=[
                PatchOperation(op="replace", path="/title", value="New"),
                PatchOperation(op="add", path="/tags/-", value="hiit"),
            ]
        )
        assert len(ops.operations) == 2

    @pytest.mark.unit
    def test_empty_operations_rejected(self):
        """Empty operations list is rejected."""
        with pytest.raises(Exception):
            PatchOperationList(operations=[])


# =============================================================================
# Path Parsing Tests
# =============================================================================


class TestParsePath:
    """Tests for parse_path function."""

    @pytest.mark.unit
    def test_simple_path(self):
        """Parse simple path."""
        assert parse_path("/title") == ["title"]

    @pytest.mark.unit
    def test_nested_path(self):
        """Parse nested path."""
        assert parse_path("/exercises/0/sets") == ["exercises", "0", "sets"]

    @pytest.mark.unit
    def test_array_append_path(self):
        """Parse array append path."""
        assert parse_path("/tags/-") == ["tags", "-"]

    @pytest.mark.unit
    def test_deep_block_path(self):
        """Parse deep block path."""
        assert parse_path("/blocks/1/exercises/2/name") == [
            "blocks", "1", "exercises", "2", "name"
        ]

    @pytest.mark.unit
    def test_invalid_path_no_slash(self):
        """Path without leading slash raises error."""
        with pytest.raises(ValueError):
            parse_path("title")


# =============================================================================
# Path Validation Tests
# =============================================================================


class TestValidatePathStructure:
    """Tests for validate_path_structure function."""

    @pytest.mark.unit
    @pytest.mark.parametrize("path", [
        "/title",
        "/name",
        "/description",
        "/notes",
        "/tags",
        "/tags/-",
        "/tags/0",
        "/exercises/-",
        "/exercises/0",
        "/exercises/0/name",
        "/exercises/0/sets",
        "/exercises/0/reps",
        "/blocks/0",
        "/blocks/0/exercises/-",
        "/blocks/0/exercises/0",
        "/blocks/0/exercises/0/name",
        "/blocks/0/label",
    ])
    def test_valid_paths(self, path):
        """Valid paths return None."""
        assert validate_path_structure(path) is None

    @pytest.mark.unit
    @pytest.mark.parametrize("path,expected_error", [
        ("/invalid_root", "Invalid root path"),
        ("/title/nested", "does not support nested"),
        ("/exercises", "Cannot replace entire exercises array"),
        ("/tags/0/nested", "too deep"),
        ("/exercises/abc", "Invalid exercise index"),
        ("/blocks", "requires index"),
        ("/blocks/abc", "Invalid block index"),
        ("/exercises/0/invalid_field", "Invalid exercise field"),
    ])
    def test_invalid_paths(self, path, expected_error):
        """Invalid paths return error message."""
        error = validate_path_structure(path)
        assert error is not None
        assert expected_error in error


# =============================================================================
# Mock Workout Repository
# =============================================================================


class MockWorkoutRepository:
    """Mock implementation of WorkoutRepository for testing."""

    def __init__(self):
        self._workouts = {}
        self._audit_logs = []

    def setup_workout(self, workout_id: str, user_id: str, workout_data: dict):
        """Setup a workout in the mock repository."""
        self._workouts[(workout_id, user_id)] = {
            "id": workout_id,
            "profile_id": user_id,
            "title": workout_data.get("title", "Test Workout"),
            "description": workout_data.get("description"),
            "tags": workout_data.get("tags", []),
            "workout_data": workout_data,
            "embedding_content_hash": "hash123",
        }

    def get_workout_by_id(self, workout_id: str, profile_id: str):
        """Get workout by ID."""
        return self._workouts.get((workout_id, profile_id))

    def update_workout_data(
        self,
        workout_id: str,
        profile_id: str,
        workout_data: dict,
        *,
        title=None,
        description=None,
        tags=None,
        clear_embedding=False,
    ):
        """Update workout data."""
        key = (workout_id, profile_id)
        if key not in self._workouts:
            return None

        workout = self._workouts[key]
        workout["workout_data"] = workout_data
        if title is not None:
            workout["title"] = title
        if description is not None:
            workout["description"] = description
        if tags is not None:
            workout["tags"] = tags
        if clear_embedding:
            workout["embedding_content_hash"] = None

        return workout

    def log_patch_audit(
        self,
        workout_id: str,
        user_id: str,
        operations: list,
        changes_applied: int,
    ):
        """Log patch audit (mock implementation)."""
        self._audit_logs.append({
            "workout_id": workout_id,
            "user_id": user_id,
            "operations": operations,
            "changes_applied": changes_applied,
        })


def setup_mock_workout(mock_repo: MockWorkoutRepository, workout_id: str, user_id: str, workout_data: dict):
    """Setup a workout in the mock repository."""
    mock_repo.setup_workout(workout_id, user_id, workout_data)


# =============================================================================
# PatchWorkoutUseCase Tests
# =============================================================================


class TestPatchWorkoutUseCase:
    """Tests for PatchWorkoutUseCase."""

    @pytest.fixture
    def mock_repo(self):
        """Create mock workout repository."""
        return MockWorkoutRepository()

    @pytest.fixture
    def use_case(self, mock_repo):
        """Create use case with mock repository."""
        return PatchWorkoutUseCase(workout_repo=mock_repo)

    @pytest.fixture
    def sample_workout_data(self):
        """Sample workout data for testing."""
        return {
            "title": "Original Title",
            "description": "Original description",
            "tags": ["cardio"],
            "blocks": [
                {
                    "label": "Main",
                    "exercises": [
                        {"name": "Squat", "sets": 3, "reps": 10},
                        {"name": "Bench Press", "sets": 3, "reps": 8},
                    ],
                }
            ],
        }

    @pytest.mark.unit
    def test_replace_title(self, mock_repo, use_case, sample_workout_data):
        """Replace title operation works."""
        setup_mock_workout(mock_repo, "w-123", "user-123", sample_workout_data)

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/title", value="Updated Title"),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_replace_name_alias(self, mock_repo, use_case, sample_workout_data):
        """/name is alias for /title."""
        setup_mock_workout(mock_repo, "w-123", "user-123", sample_workout_data)

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/name", value="New Name"),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_add_tag(self, mock_repo, use_case, sample_workout_data):
        """Add tag operation works."""
        setup_mock_workout(mock_repo, "w-123", "user-123", sample_workout_data)

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="add", path="/tags/-", value="strength"),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_replace_tags(self, mock_repo, use_case, sample_workout_data):
        """Replace entire tags array works."""
        setup_mock_workout(mock_repo, "w-123", "user-123", sample_workout_data)

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/tags", value=["new", "tags"]),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_replace_exercise_field(self, mock_repo, use_case, sample_workout_data):
        """Replace exercise field works."""
        setup_mock_workout(mock_repo, "w-123", "user-123", sample_workout_data)

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/exercises/0/sets", value=5),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_add_exercise(self, mock_repo, use_case, sample_workout_data):
        """Add exercise operation works."""
        setup_mock_workout(mock_repo, "w-123", "user-123", sample_workout_data)

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(
                    op="add",
                    path="/exercises/-",
                    value={"name": "Deadlift", "sets": 3, "reps": 5},
                ),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_remove_exercise(self, mock_repo, use_case, sample_workout_data):
        """Remove exercise operation works."""
        setup_mock_workout(mock_repo, "w-123", "user-123", sample_workout_data)

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="remove", path="/exercises/1"),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_multiple_operations(self, mock_repo, use_case, sample_workout_data):
        """Multiple operations are applied in sequence."""
        setup_mock_workout(mock_repo, "w-123", "user-123", sample_workout_data)

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/title", value="New Title"),
                PatchOperation(op="add", path="/tags/-", value="hiit"),
                PatchOperation(op="replace", path="/exercises/0/sets", value=4),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 3

    @pytest.mark.unit
    def test_workout_not_found(self, mock_repo, use_case):
        """Returns error when workout not found."""
        # Don't set up any workout in the mock repo - it should return None

        result = use_case.execute(
            workout_id="nonexistent",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/title", value="New"),
            ],
        )

        assert result.success is False
        assert "not found" in result.error.lower()


# =============================================================================
# PatchWorkoutResult Tests
# =============================================================================


class TestPatchWorkoutResult:
    """Tests for PatchWorkoutResult dataclass."""

    @pytest.mark.unit
    def test_success_result(self):
        """Success result has expected fields."""
        result = PatchWorkoutResult(
            success=True,
            workout={"id": "w-123", "title": "Test"},
            changes_applied=3,
            embedding_regeneration="queued",
        )

        assert result.success is True
        assert result.changes_applied == 3
        assert result.embedding_regeneration == "queued"
        assert result.error is None

    @pytest.mark.unit
    def test_failure_result(self):
        """Failure result has error field."""
        result = PatchWorkoutResult(
            success=False,
            error="Something went wrong",
            validation_errors=["Invalid path"],
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert len(result.validation_errors) == 1

    @pytest.mark.unit
    def test_default_values(self):
        """Default values are set correctly."""
        result = PatchWorkoutResult(success=True)

        assert result.workout is None
        assert result.changes_applied == 0
        assert result.embedding_regeneration == "none"
        assert result.validation_errors == []


# =============================================================================
# Apply Operation Tests (Internal Logic)
# =============================================================================


class TestApplyOperationLogic:
    """Tests for the internal _apply_operation logic."""

    @pytest.fixture
    def use_case(self):
        """Create use case with mock repository."""
        return PatchWorkoutUseCase(workout_repo=MockWorkoutRepository())

    @pytest.mark.unit
    def test_apply_title_replace(self, use_case):
        """Apply title replace operation."""
        workout_data = {"title": "Old", "blocks": []}
        op = PatchOperation(op="replace", path="/title", value="New")

        new_data, title, desc, tags, changed = use_case._apply_operation(
            op, workout_data, "Old", None, []
        )

        assert title == "New"
        assert new_data["title"] == "New"
        assert changed is True

    @pytest.mark.unit
    def test_apply_tag_add(self, use_case):
        """Apply tag add operation."""
        workout_data = {"title": "Test", "tags": ["existing"], "blocks": []}
        op = PatchOperation(op="add", path="/tags/-", value="new")

        new_data, title, desc, tags, changed = use_case._apply_operation(
            op, workout_data, "Test", None, ["existing"]
        )

        assert "new" in tags
        assert len(tags) == 2
        assert changed is True

    @pytest.mark.unit
    def test_apply_exercise_field_replace(self, use_case):
        """Apply exercise field replace operation."""
        workout_data = {
            "title": "Test",
            "blocks": [
                {"exercises": [{"name": "Squat", "sets": 3}]}
            ],
        }
        op = PatchOperation(op="replace", path="/exercises/0/sets", value=5)

        new_data, title, desc, tags, changed = use_case._apply_operation(
            op, workout_data, "Test", None, []
        )

        assert new_data["blocks"][0]["exercises"][0]["sets"] == 5
        assert changed is True

    @pytest.mark.unit
    def test_apply_exercise_add(self, use_case):
        """Apply exercise add operation."""
        workout_data = {
            "title": "Test",
            "blocks": [
                {"exercises": [{"name": "Squat", "sets": 3}]}
            ],
        }
        op = PatchOperation(
            op="add",
            path="/exercises/-",
            value={"name": "Bench", "sets": 3},
        )

        new_data, title, desc, tags, changed = use_case._apply_operation(
            op, workout_data, "Test", None, []
        )

        assert len(new_data["blocks"][0]["exercises"]) == 2
        assert new_data["blocks"][0]["exercises"][1]["name"] == "Bench"
        assert changed is True

    @pytest.mark.unit
    def test_apply_exercise_remove(self, use_case):
        """Apply exercise remove operation."""
        workout_data = {
            "title": "Test",
            "blocks": [
                {"exercises": [
                    {"name": "Squat", "sets": 3},
                    {"name": "Bench", "sets": 3},
                ]}
            ],
        }
        op = PatchOperation(op="remove", path="/exercises/0")

        new_data, title, desc, tags, changed = use_case._apply_operation(
            op, workout_data, "Test", None, []
        )

        assert len(new_data["blocks"][0]["exercises"]) == 1
        assert new_data["blocks"][0]["exercises"][0]["name"] == "Bench"
        assert changed is True

    @pytest.mark.unit
    def test_apply_block_exercise_path(self, use_case):
        """Apply operation using full blocks path."""
        workout_data = {
            "title": "Test",
            "blocks": [
                {"label": "Block 1", "exercises": [{"name": "Squat", "sets": 3}]},
                {"label": "Block 2", "exercises": [{"name": "Bench", "sets": 3}]},
            ],
        }
        op = PatchOperation(op="replace", path="/blocks/1/exercises/0/sets", value=5)

        new_data, title, desc, tags, changed = use_case._apply_operation(
            op, workout_data, "Test", None, []
        )

        # Second block's exercise should be updated
        assert new_data["blocks"][1]["exercises"][0]["sets"] == 5
        assert changed is True


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidationErrors:
    """Tests for validation error cases."""

    @pytest.fixture
    def mock_repo(self):
        """Create mock workout repository."""
        return MockWorkoutRepository()

    @pytest.fixture
    def use_case(self, mock_repo):
        """Create use case with mock repository."""
        return PatchWorkoutUseCase(workout_repo=mock_repo)

    @pytest.mark.unit
    def test_invalid_path_validation(self, mock_repo, use_case):
        """Invalid paths are rejected during validation."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/invalid_path", value="test"),
            ],
        )

        assert result.success is False
        assert len(result.validation_errors) > 0

    @pytest.mark.unit
    def test_empty_title_validation(self, mock_repo, use_case):
        """Empty title is rejected."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/title", value=""),
            ],
        )

        assert result.success is False

    @pytest.mark.unit
    def test_tags_must_be_array(self, mock_repo, use_case):
        """Tags must be an array when replacing entire tags."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "tags": ["existing"],
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/tags", value="not-an-array"),
            ],
        )

        assert result.success is False


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def mock_repo(self):
        """Create mock workout repository."""
        return MockWorkoutRepository()

    @pytest.fixture
    def use_case(self, mock_repo):
        """Create use case with mock repository."""
        return PatchWorkoutUseCase(workout_repo=mock_repo)

    @pytest.mark.unit
    def test_remove_nonexistent_index_no_change(self, mock_repo, use_case):
        """Remove on non-existent index succeeds with 0 changes applied.

        The implementation is lenient - operations on non-existent indices
        simply don't apply any changes rather than failing validation.
        This allows batch operations to be more flexible.
        """
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })

        # Try to remove non-existent index - succeeds but applies 0 changes
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="remove", path="/exercises/99"),
            ],
        )

        # Succeeds but with 0 changes since index doesn't exist
        assert result.success is True
        assert result.changes_applied == 0

    @pytest.mark.unit
    def test_add_exercise_creates_default_block(self, mock_repo, use_case):
        """Adding exercise when no blocks exist creates default block."""
        # Setup workout with empty blocks
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [],
        })

        # Adding to exercises with empty blocks - the implementation
        # creates a default block automatically
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(
                    op="add",
                    path="/exercises/-",
                    value={"name": "Squat", "sets": 3, "reps": 10},
                ),
            ],
        )

        # Succeeds because implementation auto-creates default block
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_remove_valid_exercise(self, mock_repo, use_case):
        """Remove existing exercise by valid index."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [
                {"name": "Squat", "sets": 3},
                {"name": "Bench", "sets": 3},
            ]}],
        })

        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="remove", path="/exercises/0"),
            ],
        )

        assert result.success is True
        assert result.changes_applied == 1


# =============================================================================
# Length Validation Tests (Code Review Fix Verification)
# =============================================================================


class TestLengthValidation:
    """Tests for input length validation constants.

    Verifies the code review fix that added:
    - MAX_TITLE_LENGTH = 200
    - MAX_DESCRIPTION_LENGTH = 2000 (matches domain model)
    - MAX_NOTES_LENGTH = 2000 (matches domain model)
    - MAX_TAG_LENGTH = 100
    - MAX_TAGS_COUNT = 50
    - MAX_EXERCISE_NAME_LENGTH = 200
    - MAX_EXERCISE_NOTES_LENGTH = 1000
    """

    @pytest.fixture
    def mock_repo(self):
        """Create mock workout repository."""
        return MockWorkoutRepository()

    @pytest.fixture
    def use_case(self, mock_repo):
        """Create use case with mock repository."""
        return PatchWorkoutUseCase(workout_repo=mock_repo)

    @pytest.fixture
    def basic_workout(self, mock_repo):
        """Setup a basic workout for testing."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test Workout",
            "description": "Test description",
            "tags": ["cardio"],
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3, "reps": 10}]}],
        })
        return mock_repo

    # -------------------------------------------------------------------------
    # Title Length Tests (MAX_TITLE_LENGTH = 200)
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_title_at_max_length_accepted(self, use_case, basic_workout):
        """Title exactly at 200 chars is accepted."""
        title = "x" * 200
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/title", value=title)],
        )
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_title_exceeds_max_length_rejected(self, use_case, basic_workout):
        """Title exceeding 200 chars is rejected."""
        title = "x" * 201
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/title", value=title)],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0
        assert any("200" in err or "Title" in err for err in result.validation_errors)

    # -------------------------------------------------------------------------
    # Description Length Tests (MAX_DESCRIPTION_LENGTH = 2000)
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_description_at_max_length_accepted(self, use_case, basic_workout):
        """Description exactly at 2000 chars is accepted."""
        desc = "x" * 2000
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/description", value=desc)],
        )
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_description_exceeds_max_length_rejected(self, use_case, basic_workout):
        """Description exceeding 2000 chars is rejected."""
        desc = "x" * 2001
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/description", value=desc)],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0
        assert any("2000" in err or "Description" in err for err in result.validation_errors)

    # -------------------------------------------------------------------------
    # Notes Length Tests (MAX_NOTES_LENGTH = 2000)
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_notes_at_max_length_accepted(self, use_case, basic_workout):
        """Notes exactly at 2000 chars is accepted."""
        notes = "x" * 2000
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/notes", value=notes)],
        )
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_notes_exceeds_max_length_rejected(self, use_case, basic_workout):
        """Notes exceeding 2000 chars is rejected."""
        notes = "x" * 2001
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/notes", value=notes)],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0
        assert any("2000" in err or "Notes" in err for err in result.validation_errors)

    # -------------------------------------------------------------------------
    # Tags Count Tests (MAX_TAGS_COUNT = 50)
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_tags_at_max_count_accepted(self, use_case, basic_workout):
        """Exactly 50 tags is accepted."""
        tags = [f"tag{i}" for i in range(50)]
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/tags", value=tags)],
        )
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_tags_exceeds_max_count_rejected(self, use_case, basic_workout):
        """More than 50 tags is rejected."""
        tags = [f"tag{i}" for i in range(51)]
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/tags", value=tags)],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0
        assert any("50" in err for err in result.validation_errors)

    # -------------------------------------------------------------------------
    # Single Tag Length Tests (MAX_TAG_LENGTH = 100)
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_single_tag_at_max_length_accepted(self, use_case, basic_workout):
        """Single tag exactly at 100 chars is accepted."""
        tag = "x" * 100
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="add", path="/tags/-", value=tag)],
        )
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_single_tag_exceeds_max_length_rejected(self, use_case, basic_workout):
        """Single tag exceeding 100 chars is rejected."""
        tag = "x" * 101
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="add", path="/tags/-", value=tag)],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0
        assert any("100" in err or "Tag" in err for err in result.validation_errors)

    @pytest.mark.unit
    def test_tag_in_array_exceeds_max_length_rejected(self, use_case, basic_workout):
        """Tag within array exceeding 100 chars is rejected."""
        tags = ["valid", "x" * 101, "also-valid"]
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/tags", value=tags)],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0

    # -------------------------------------------------------------------------
    # Exercise Name Length Tests (MAX_EXERCISE_NAME_LENGTH = 200)
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_exercise_name_at_max_length_accepted(self, use_case, basic_workout):
        """Exercise name exactly at 200 chars is accepted."""
        name = "x" * 200
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/exercises/0/name", value=name)],
        )
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_exercise_name_exceeds_max_length_rejected(self, use_case, basic_workout):
        """Exercise name exceeding 200 chars is rejected."""
        name = "x" * 201
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/exercises/0/name", value=name)],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0
        assert any("200" in err or "name" in err.lower() for err in result.validation_errors)

    @pytest.mark.unit
    def test_new_exercise_name_exceeds_max_length_rejected(self, use_case, basic_workout):
        """Adding exercise with name exceeding 200 chars is rejected."""
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(
                op="add",
                path="/exercises/-",
                value={"name": "x" * 201, "sets": 3, "reps": 10},
            )],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0

    # -------------------------------------------------------------------------
    # Exercise Notes Length Tests (MAX_EXERCISE_NOTES_LENGTH = 1000)
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_exercise_notes_at_max_length_accepted(self, use_case, basic_workout):
        """Exercise notes exactly at 1000 chars is accepted."""
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(
                op="add",
                path="/exercises/-",
                value={"name": "New Exercise", "sets": 3, "notes": "x" * 1000},
            )],
        )
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_exercise_notes_exceeds_max_length_rejected(self, use_case, basic_workout):
        """Exercise notes exceeding 1000 chars is rejected."""
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(
                op="add",
                path="/exercises/-",
                value={"name": "New Exercise", "sets": 3, "notes": "x" * 1001},
            )],
        )
        assert result.success is False
        assert len(result.validation_errors) > 0
        assert any("1000" in err or "notes" in err.lower() for err in result.validation_errors)


# =============================================================================
# Business Rule Edge Cases
# =============================================================================


class TestBusinessRuleEdgeCases:
    """Tests for business rule validation edge cases."""

    @pytest.fixture
    def mock_repo(self):
        """Create mock workout repository."""
        return MockWorkoutRepository()

    @pytest.fixture
    def use_case(self, mock_repo):
        """Create use case with mock repository."""
        return PatchWorkoutUseCase(workout_repo=mock_repo)

    @pytest.mark.unit
    def test_remove_last_exercise_rejected(self, mock_repo, use_case):
        """Removing the only exercise results in business rule failure."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="remove", path="/exercises/0")],
        )
        assert result.success is False
        assert any(
            "at least one" in err.lower() or "no exercises" in err.lower()
            for err in result.validation_errors
        )

    @pytest.mark.unit
    def test_remove_last_block_rejected(self, mock_repo, use_case):
        """Removing the only block is rejected."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="remove", path="/blocks/0")],
        )
        assert result.success is False
        assert any(
            "at least one" in err.lower() or "block" in err.lower()
            for err in result.validation_errors
        )

    @pytest.mark.unit
    def test_add_exercise_with_empty_name_rejected(self, mock_repo, use_case):
        """Adding exercise with empty name is rejected."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(
                op="add",
                path="/exercises/-",
                value={"name": "", "sets": 3},
            )],
        )
        assert result.success is False

    @pytest.mark.unit
    def test_add_exercise_without_name_rejected(self, mock_repo, use_case):
        """Adding exercise without name field is rejected."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(
                op="add",
                path="/exercises/-",
                value={"sets": 3, "reps": 10},
            )],
        )
        assert result.success is False

    @pytest.mark.unit
    def test_replace_exercise_name_with_empty_rejected(self, mock_repo, use_case):
        """Replacing exercise name with empty string is rejected."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/exercises/0/name", value="")],
        )
        assert result.success is False

    @pytest.mark.unit
    def test_replace_title_with_empty_rejected(self, mock_repo, use_case):
        """Replacing title with empty string is rejected."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/title", value="")],
        )
        assert result.success is False

    @pytest.mark.unit
    def test_replace_title_with_whitespace_only_rejected(self, mock_repo, use_case):
        """Replacing title with whitespace-only string is rejected."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/title", value="   ")],
        )
        assert result.success is False


# =============================================================================
# Audit Log Resilience Tests
# =============================================================================


class TestAuditLogResilience:
    """Tests verifying main operation succeeds even if audit logging fails."""

    @pytest.mark.unit
    def test_patch_succeeds_when_audit_log_fails(self):
        """Patch operation should succeed even if audit logging throws."""

        class FailingAuditRepository(MockWorkoutRepository):
            """Repository that fails on audit log."""

            def log_patch_audit(self, workout_id, user_id, operations, changes_applied):
                raise Exception("Database connection lost")

        mock_repo = FailingAuditRepository()
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })

        use_case = PatchWorkoutUseCase(workout_repo=mock_repo)
        result = use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[PatchOperation(op="replace", path="/title", value="New Title")],
        )

        # Main operation should still succeed
        assert result.success is True
        assert result.changes_applied == 1

    @pytest.mark.unit
    def test_audit_log_receives_correct_data(self):
        """Verify audit log receives the correct operation data."""

        class AuditCapturingRepository(MockWorkoutRepository):
            """Repository that captures audit log calls."""

            def __init__(self):
                super().__init__()
                self.audit_calls = []

            def log_patch_audit(self, workout_id, user_id, operations, changes_applied):
                self.audit_calls.append({
                    "workout_id": workout_id,
                    "user_id": user_id,
                    "operations": operations,
                    "changes_applied": changes_applied,
                })

        mock_repo = AuditCapturingRepository()
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [{"exercises": [{"name": "Squat", "sets": 3}]}],
        })

        use_case = PatchWorkoutUseCase(workout_repo=mock_repo)
        use_case.execute(
            workout_id="w-123",
            user_id="user-123",
            operations=[
                PatchOperation(op="replace", path="/title", value="New Title"),
                PatchOperation(op="add", path="/tags/-", value="strength"),
            ],
        )

        assert len(mock_repo.audit_calls) == 1
        audit = mock_repo.audit_calls[0]
        assert audit["workout_id"] == "w-123"
        assert audit["user_id"] == "user-123"
        assert audit["changes_applied"] == 2
        assert len(audit["operations"]) == 2
        assert audit["operations"][0]["op"] == "replace"
        assert audit["operations"][0]["path"] == "/title"


# =============================================================================
# Mock Repository Contract Tests
# =============================================================================


class TestMockRepositoryContract:
    """Verify MockWorkoutRepository matches WorkoutRepository Protocol."""

    @pytest.fixture
    def mock_repo(self):
        """Create mock workout repository."""
        return MockWorkoutRepository()

    @pytest.mark.unit
    def test_mock_has_get_workout_by_id(self, mock_repo):
        """Mock implements get_workout_by_id."""
        assert hasattr(mock_repo, "get_workout_by_id")
        assert callable(mock_repo.get_workout_by_id)

    @pytest.mark.unit
    def test_mock_has_update_workout_data(self, mock_repo):
        """Mock implements update_workout_data."""
        assert hasattr(mock_repo, "update_workout_data")
        assert callable(mock_repo.update_workout_data)

    @pytest.mark.unit
    def test_mock_has_log_patch_audit(self, mock_repo):
        """Mock implements log_patch_audit."""
        assert hasattr(mock_repo, "log_patch_audit")
        assert callable(mock_repo.log_patch_audit)

    @pytest.mark.unit
    def test_get_workout_by_id_returns_none_for_missing(self, mock_repo):
        """get_workout_by_id returns None when workout doesn't exist."""
        result = mock_repo.get_workout_by_id("nonexistent", "user-123")
        assert result is None

    @pytest.mark.unit
    def test_get_workout_by_id_returns_workout_when_exists(self, mock_repo):
        """get_workout_by_id returns workout dict when it exists."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [],
        })
        result = mock_repo.get_workout_by_id("w-123", "user-123")
        assert result is not None
        assert result["id"] == "w-123"
        assert result["profile_id"] == "user-123"

    @pytest.mark.unit
    def test_update_workout_data_returns_none_for_missing(self, mock_repo):
        """update_workout_data returns None when workout doesn't exist."""
        result = mock_repo.update_workout_data(
            "nonexistent", "user-123", {"title": "New", "blocks": []}
        )
        assert result is None

    @pytest.mark.unit
    def test_update_workout_data_updates_and_returns_workout(self, mock_repo):
        """update_workout_data modifies workout and returns updated dict."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Old Title",
            "blocks": [],
        })
        result = mock_repo.update_workout_data(
            "w-123", "user-123",
            {"title": "New Title", "blocks": []},
            title="New Title",
        )
        assert result is not None
        assert result["title"] == "New Title"

    @pytest.mark.unit
    def test_update_clears_embedding_when_requested(self, mock_repo):
        """update_workout_data clears embedding hash when clear_embedding=True."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [],
        })
        # Verify hash exists initially
        workout = mock_repo.get_workout_by_id("w-123", "user-123")
        assert workout["embedding_content_hash"] is not None

        # Update with clear_embedding=True
        mock_repo.update_workout_data(
            "w-123", "user-123",
            {"title": "New", "blocks": []},
            clear_embedding=True,
        )

        # Verify hash is cleared
        workout = mock_repo.get_workout_by_id("w-123", "user-123")
        assert workout["embedding_content_hash"] is None

    @pytest.mark.unit
    def test_update_preserves_embedding_when_not_clearing(self, mock_repo):
        """update_workout_data preserves embedding hash when clear_embedding=False."""
        setup_mock_workout(mock_repo, "w-123", "user-123", {
            "title": "Test",
            "blocks": [],
        })
        original_hash = mock_repo.get_workout_by_id("w-123", "user-123")["embedding_content_hash"]

        mock_repo.update_workout_data(
            "w-123", "user-123",
            {"title": "New", "blocks": []},
            clear_embedding=False,
        )

        workout = mock_repo.get_workout_by_id("w-123", "user-123")
        assert workout["embedding_content_hash"] == original_hash
