"""
Meta-tests for the golden test harness.

Part of AMA-395: Create golden test harness for exporters
Phase 4 - Testing Overhaul

Tests the golden test infrastructure itself to ensure:
- assert_golden() works correctly
- update_golden() creates/updates fixtures
- Diff generation is useful
- Binary and text modes work
"""

import json
import tempfile
from pathlib import Path

import pytest

from tests.golden.conftest import (
    assert_golden,
    update_golden,
    GoldenTestError,
    FIXTURES_DIR,
    _normalize_content,
    _generate_diff,
)


# =============================================================================
# Normalization Tests
# =============================================================================


class TestNormalization:
    """Tests for content normalization."""

    @pytest.mark.unit
    def test_normalizes_line_endings(self):
        """Windows and Unix line endings are normalized."""
        content_crlf = "line1\r\nline2\r\n"
        content_lf = "line1\nline2\n"
        content_cr = "line1\rline2\r"

        normalized_crlf = _normalize_content(content_crlf)
        normalized_lf = _normalize_content(content_lf)
        normalized_cr = _normalize_content(content_cr)

        assert normalized_crlf == normalized_lf == normalized_cr

    @pytest.mark.unit
    def test_strips_trailing_whitespace(self):
        """Trailing whitespace per line is stripped."""
        content = "line1   \nline2\t\nline3\n"
        normalized = _normalize_content(content)

        assert "   " not in normalized
        assert "\t" not in normalized

    @pytest.mark.unit
    def test_ensures_trailing_newline(self):
        """Output ends with exactly one newline."""
        content_no_newline = "line1\nline2"
        content_many_newlines = "line1\nline2\n\n\n"

        assert _normalize_content(content_no_newline).endswith("\n")
        assert _normalize_content(content_many_newlines).endswith("\n")
        assert not _normalize_content(content_many_newlines).endswith("\n\n")

    @pytest.mark.unit
    def test_binary_not_normalized(self):
        """Binary content is not modified."""
        binary_data = b"\x00\x01\x02\r\n\xff"
        result = _normalize_content(binary_data, is_binary=True)
        assert result == binary_data


# =============================================================================
# Diff Generation Tests
# =============================================================================


class TestDiffGeneration:
    """Tests for diff generation."""

    @pytest.mark.unit
    def test_generates_unified_diff(self):
        """Generates readable unified diff."""
        expected = "line1\nline2\nline3\n"
        actual = "line1\nchanged\nline3\n"

        diff = _generate_diff(expected, actual, Path("test.txt"))

        assert "line2" in diff
        assert "changed" in diff
        assert "-line2" in diff or "- line2" in diff
        assert "+changed" in diff or "+ changed" in diff

    @pytest.mark.unit
    def test_diff_includes_fixture_name(self):
        """Diff header includes fixture name."""
        diff = _generate_diff("a\n", "b\n", Path("my_fixture.yaml"))
        assert "my_fixture.yaml" in diff


# =============================================================================
# Update Golden Tests
# =============================================================================


class TestUpdateGolden:
    """Tests for update_golden() function."""

    @pytest.mark.unit
    def test_creates_fixture_file(self, tmp_path, monkeypatch):
        """Creates fixture file with correct content."""
        # Temporarily override FIXTURES_DIR
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        content = "test content\n"
        fixture_path = update_golden(content, "test/output.txt")

        assert fixture_path.exists()
        assert fixture_path.read_text() == content

    @pytest.mark.unit
    def test_creates_nested_directories(self, tmp_path, monkeypatch):
        """Creates nested directories if needed."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        update_golden("content\n", "deeply/nested/path/file.txt")

        assert (tmp_path / "deeply/nested/path/file.txt").exists()

    @pytest.mark.unit
    def test_handles_dict_as_json(self, tmp_path, monkeypatch):
        """Dict input is serialized as pretty JSON."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        data = {"key": "value", "number": 42}
        update_golden(data, "data.json")

        content = (tmp_path / "data.json").read_text()
        assert json.loads(content) == data
        assert "\n" in content  # Pretty printed

    @pytest.mark.unit
    def test_handles_binary_content(self, tmp_path, monkeypatch):
        """Binary content is written correctly."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        binary_data = b"\x00\x01\x02\xff"
        update_golden(binary_data, "binary.bin", is_binary=True)

        assert (tmp_path / "binary.bin").read_bytes() == binary_data


# =============================================================================
# Assert Golden Tests
# =============================================================================


class TestAssertGolden:
    """Tests for assert_golden() function."""

    @pytest.mark.unit
    def test_passes_when_matches(self, tmp_path, monkeypatch):
        """Passes when output matches fixture."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        # Create fixture
        fixture_content = "expected content\n"
        (tmp_path / "test.txt").write_text(fixture_content)

        # Should not raise
        assert_golden("expected content\n", "test.txt")

    @pytest.mark.unit
    def test_passes_with_normalized_content(self, tmp_path, monkeypatch):
        """Passes when content matches after normalization."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        # Create fixture with Unix line endings
        (tmp_path / "test.txt").write_text("line1\nline2\n")

        # Windows line endings should still match
        assert_golden("line1\r\nline2\r\n", "test.txt")

    @pytest.mark.unit
    def test_fails_when_differs(self, tmp_path, monkeypatch):
        """Raises GoldenTestError when output differs."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        (tmp_path / "test.txt").write_text("expected\n")

        with pytest.raises(GoldenTestError) as exc_info:
            assert_golden("actual\n", "test.txt")

        assert "expected" in exc_info.value.diff
        assert "actual" in exc_info.value.diff

    @pytest.mark.unit
    def test_fails_when_fixture_missing(self, tmp_path, monkeypatch):
        """Raises FileNotFoundError when fixture doesn't exist."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        with pytest.raises(FileNotFoundError) as exc_info:
            assert_golden("content\n", "nonexistent.txt")

        assert "--update-golden" in str(exc_info.value)

    @pytest.mark.unit
    def test_update_mode_creates_fixture(self, tmp_path, monkeypatch):
        """In update mode, creates missing fixture."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        assert_golden("new content\n", "new_fixture.txt", update=True)

        assert (tmp_path / "new_fixture.txt").exists()
        assert (tmp_path / "new_fixture.txt").read_text() == "new content\n"

    @pytest.mark.unit
    def test_handles_json_dict(self, tmp_path, monkeypatch):
        """Dict is compared as sorted JSON."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        # Create fixture with JSON
        data = {"b": 2, "a": 1}
        (tmp_path / "data.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

        # Same data in different order should match
        assert_golden({"a": 1, "b": 2}, "data.json")

    @pytest.mark.unit
    def test_binary_comparison(self, tmp_path, monkeypatch):
        """Binary content is compared byte-for-byte."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        binary_data = b"\x00\x01\x02"
        (tmp_path / "binary.bin").write_bytes(binary_data)

        # Should pass
        assert_golden(binary_data, "binary.bin", is_binary=True)

        # Different binary should fail
        with pytest.raises(GoldenTestError):
            assert_golden(b"\x00\x01\x03", "binary.bin", is_binary=True)


# =============================================================================
# Error Message Tests
# =============================================================================


class TestErrorMessages:
    """Tests for helpful error messages."""

    @pytest.mark.unit
    def test_error_includes_fixture_path(self, tmp_path, monkeypatch):
        """Error message includes fixture path."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        (tmp_path / "my_fixture.yaml").write_text("expected\n")

        with pytest.raises(GoldenTestError) as exc_info:
            assert_golden("actual\n", "my_fixture.yaml")

        assert "my_fixture.yaml" in str(exc_info.value)
        assert exc_info.value.fixture_path.name == "my_fixture.yaml"

    @pytest.mark.unit
    def test_error_includes_update_hint(self, tmp_path, monkeypatch):
        """Error message includes hint to use --update-golden."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        (tmp_path / "test.txt").write_text("expected\n")

        with pytest.raises(GoldenTestError) as exc_info:
            assert_golden("actual\n", "test.txt")

        assert "--update-golden" in str(exc_info.value)


# =============================================================================
# Integration Test
# =============================================================================


class TestGoldenHarnessIntegration:
    """Integration tests for the complete golden test workflow."""

    @pytest.mark.unit
    def test_full_workflow(self, tmp_path, monkeypatch):
        """Test create -> assert -> update -> assert workflow."""
        import tests.golden.conftest as conftest
        monkeypatch.setattr(conftest, "FIXTURES_DIR", tmp_path)

        # 1. Create initial fixture
        update_golden("version 1\n", "workflow.txt")
        assert (tmp_path / "workflow.txt").read_text() == "version 1\n"

        # 2. Assert matches
        assert_golden("version 1\n", "workflow.txt")

        # 3. Assert fails with different content
        with pytest.raises(GoldenTestError):
            assert_golden("version 2\n", "workflow.txt")

        # 4. Update fixture
        update_golden("version 2\n", "workflow.txt")

        # 5. Now assertion passes
        assert_golden("version 2\n", "workflow.txt")
