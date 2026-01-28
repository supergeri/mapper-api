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
# Mock Supabase Client
# =============================================================================


def create_mock_supabase():
    """Create a mock Supabase client for testing."""
    mock_client = MagicMock()

    # Store for workouts and edit history
    mock_client._workouts = {}
    mock_client._edit_history = []

    def table(name):
        if name == "workouts":
            return mock_client._workouts_table
        elif name == "workout_edit_history":
            return mock_client._edit_history_table
        return MagicMock()

    mock_client.table = table

    # Setup workouts table mock
    mock_client._workouts_table = MagicMock()

    return mock_client


def setup_mock_workout(mock_client, workout_id, user_id, workout_data):
    """Setup a workout in the mock client."""
    workout_row = {
        "id": workout_id,
        "profile_id": user_id,
        "title": workout_data.get("title", "Test Workout"),
        "description": workout_data.get("description"),
        "tags": workout_data.get("tags", []),
        "workout_data": workout_data,
        "embedding_content_hash": "hash123",
    }
    mock_client._workouts[workout_id] = workout_row

    # Configure select chain
    select_mock = MagicMock()
    eq_mock = MagicMock()
    single_mock = MagicMock()

    def execute_select():
        result = MagicMock()
        result.data = workout_row
        return result

    single_mock.execute = execute_select
    eq_mock.single.return_value = single_mock
    eq_mock.eq.return_value = eq_mock
    select_mock.eq.return_value = eq_mock
    mock_client._workouts_table.select.return_value = select_mock

    # Configure update chain
    update_mock = MagicMock()
    update_eq_mock = MagicMock()

    def execute_update():
        result = MagicMock()
        result.data = [workout_row]
        return result

    update_eq_mock.execute = execute_update
    update_eq_mock.eq.return_value = update_eq_mock
    update_mock.eq.return_value = update_eq_mock
    mock_client._workouts_table.update.return_value = update_mock

    # Configure edit history insert
    insert_mock = MagicMock()

    def execute_insert():
        result = MagicMock()
        result.data = [{}]
        return result

    insert_mock.execute = execute_insert
    mock_client._edit_history_table = MagicMock()
    mock_client._edit_history_table.insert.return_value = insert_mock


# =============================================================================
# PatchWorkoutUseCase Tests
# =============================================================================


class TestPatchWorkoutUseCase:
    """Tests for PatchWorkoutUseCase."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Supabase client."""
        return create_mock_supabase()

    @pytest.fixture
    def use_case(self, mock_client):
        """Create use case with mock client."""
        return PatchWorkoutUseCase(supabase_client=mock_client)

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
    def test_replace_title(self, mock_client, use_case, sample_workout_data):
        """Replace title operation works."""
        setup_mock_workout(mock_client, "w-123", "user-123", sample_workout_data)

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
    def test_replace_name_alias(self, mock_client, use_case, sample_workout_data):
        """/name is alias for /title."""
        setup_mock_workout(mock_client, "w-123", "user-123", sample_workout_data)

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
    def test_add_tag(self, mock_client, use_case, sample_workout_data):
        """Add tag operation works."""
        setup_mock_workout(mock_client, "w-123", "user-123", sample_workout_data)

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
    def test_replace_tags(self, mock_client, use_case, sample_workout_data):
        """Replace entire tags array works."""
        setup_mock_workout(mock_client, "w-123", "user-123", sample_workout_data)

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
    def test_replace_exercise_field(self, mock_client, use_case, sample_workout_data):
        """Replace exercise field works."""
        setup_mock_workout(mock_client, "w-123", "user-123", sample_workout_data)

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
    def test_add_exercise(self, mock_client, use_case, sample_workout_data):
        """Add exercise operation works."""
        setup_mock_workout(mock_client, "w-123", "user-123", sample_workout_data)

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
    def test_remove_exercise(self, mock_client, use_case, sample_workout_data):
        """Remove exercise operation works."""
        setup_mock_workout(mock_client, "w-123", "user-123", sample_workout_data)

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
    def test_multiple_operations(self, mock_client, use_case, sample_workout_data):
        """Multiple operations are applied in sequence."""
        setup_mock_workout(mock_client, "w-123", "user-123", sample_workout_data)

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
    def test_workout_not_found(self, mock_client, use_case):
        """Returns error when workout not found."""
        # Setup mock to return None
        select_mock = MagicMock()
        eq_mock = MagicMock()
        single_mock = MagicMock()

        def execute_select():
            result = MagicMock()
            result.data = None
            return result

        single_mock.execute = execute_select
        eq_mock.single.return_value = single_mock
        eq_mock.eq.return_value = eq_mock
        select_mock.eq.return_value = eq_mock
        mock_client._workouts_table.select.return_value = select_mock

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
        """Create use case with mock client."""
        return PatchWorkoutUseCase(supabase_client=MagicMock())

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
    def mock_client(self):
        """Create mock Supabase client."""
        return create_mock_supabase()

    @pytest.fixture
    def use_case(self, mock_client):
        """Create use case with mock client."""
        return PatchWorkoutUseCase(supabase_client=mock_client)

    @pytest.mark.unit
    def test_invalid_path_validation(self, mock_client, use_case):
        """Invalid paths are rejected during validation."""
        setup_mock_workout(mock_client, "w-123", "user-123", {
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
    def test_empty_title_validation(self, mock_client, use_case):
        """Empty title is rejected."""
        setup_mock_workout(mock_client, "w-123", "user-123", {
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
    def test_tags_must_be_array(self, mock_client, use_case):
        """Tags must be an array when replacing entire tags."""
        setup_mock_workout(mock_client, "w-123", "user-123", {
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
    def mock_client(self):
        """Create mock Supabase client."""
        return create_mock_supabase()

    @pytest.fixture
    def use_case(self, mock_client):
        """Create use case with mock client."""
        return PatchWorkoutUseCase(supabase_client=mock_client)

    @pytest.mark.unit
    def test_remove_nonexistent_index_no_change(self, mock_client, use_case):
        """Remove on non-existent index succeeds with 0 changes applied.

        The implementation is lenient - operations on non-existent indices
        simply don't apply any changes rather than failing validation.
        This allows batch operations to be more flexible.
        """
        setup_mock_workout(mock_client, "w-123", "user-123", {
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
    def test_add_exercise_creates_default_block(self, mock_client, use_case):
        """Adding exercise when no blocks exist creates default block."""
        # Configure to return workout with empty blocks
        select_mock = MagicMock()
        eq_mock = MagicMock()
        single_mock = MagicMock()

        workout_row = {
            "id": "w-123",
            "profile_id": "user-123",
            "title": "Test",
            "workout_data": {"title": "Test", "blocks": []},
            "tags": [],
        }

        def execute_select():
            result = MagicMock()
            result.data = workout_row
            return result

        single_mock.execute = execute_select
        eq_mock.single.return_value = single_mock
        eq_mock.eq.return_value = eq_mock
        select_mock.eq.return_value = eq_mock
        mock_client._workouts_table.select.return_value = select_mock

        # Configure update chain
        update_mock = MagicMock()
        update_eq_mock = MagicMock()

        def execute_update():
            result = MagicMock()
            result.data = [workout_row]
            return result

        update_eq_mock.execute = execute_update
        update_eq_mock.eq.return_value = update_eq_mock
        update_mock.eq.return_value = update_eq_mock
        mock_client._workouts_table.update.return_value = update_mock

        # Configure edit history insert
        insert_mock = MagicMock()

        def execute_insert():
            result = MagicMock()
            result.data = [{}]
            return result

        insert_mock.execute = execute_insert
        mock_client._edit_history_table = MagicMock()
        mock_client._edit_history_table.insert.return_value = insert_mock

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
    def test_remove_valid_exercise(self, mock_client, use_case):
        """Remove existing exercise by valid index."""
        setup_mock_workout(mock_client, "w-123", "user-123", {
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
