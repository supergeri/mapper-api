"""
Golden test utilities and pytest configuration.

Part of AMA-395: Create golden test harness for exporters
Phase 4 - Testing Overhaul
Extended in AMA-371: Additional helpers for workout fixture loading

Provides:
- assert_golden(): Compare output against saved fixture
- update_golden(): Regenerate fixture file
- load_fixture(): Load canonical workout fixtures
- compare_output(): Compare actual vs expected output with optional regeneration
- --update-golden / --regenerate-golden pytest flags for batch fixture updates
"""

import difflib
import json
from pathlib import Path
from typing import Union

import pytest

# Directory containing golden fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class GoldenTestError(AssertionError):
    """Raised when golden test output doesn't match fixture."""

    def __init__(self, message: str, diff: str, fixture_path: Path):
        self.diff = diff
        self.fixture_path = fixture_path
        super().__init__(message)


def _normalize_content(content: Union[str, bytes], is_binary: bool = False) -> Union[str, bytes]:
    """Normalize content for comparison (handle line endings, trailing whitespace)."""
    if is_binary:
        return content
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    # Normalize line endings and strip trailing whitespace per line
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized = "\n".join(line.rstrip() for line in lines)
    # Ensure single trailing newline
    return normalized.rstrip() + "\n"


def _get_fixture_path(fixture_name: str) -> Path:
    """Get full path to fixture file."""
    return FIXTURES_DIR / fixture_name


def _generate_diff(expected: str, actual: str, fixture_path: Path) -> str:
    """Generate a unified diff between expected and actual content."""
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)

    diff = difflib.unified_diff(
        expected_lines,
        actual_lines,
        fromfile=f"fixture: {fixture_path.name}",
        tofile="actual output",
        lineterm="",
    )
    return "".join(diff)


def update_golden(
    output: Union[str, bytes, dict],
    fixture_name: str,
    *,
    is_binary: bool = False,
) -> Path:
    """
    Update (regenerate) a golden fixture file.

    Use this when output has intentionally changed and the fixture
    needs to be updated.

    Args:
        output: The new output to save as the fixture
        fixture_name: Relative path within fixtures/ directory
        is_binary: If True, treat as binary content (no normalization)

    Returns:
        Path to the updated fixture file
    """
    fixture_path = _get_fixture_path(fixture_name)
    fixture_path.parent.mkdir(parents=True, exist_ok=True)

    # Handle dict/JSON output
    if isinstance(output, dict):
        output = json.dumps(output, indent=2, sort_keys=True)
        is_binary = False

    # Normalize text content
    if not is_binary:
        output = _normalize_content(output, is_binary=False)

    # Write fixture
    mode = "wb" if is_binary else "w"
    encoding = None if is_binary else "utf-8"
    with open(fixture_path, mode, encoding=encoding) as f:
        f.write(output)

    return fixture_path


def assert_golden(
    output: Union[str, bytes, dict],
    fixture_name: str,
    *,
    is_binary: bool = False,
    update: bool = False,
) -> None:
    """
    Assert that output matches the golden fixture.

    Args:
        output: The actual output to compare
        fixture_name: Relative path within fixtures/ directory
        is_binary: If True, compare as binary (no normalization)
        update: If True, update fixture instead of asserting

    Raises:
        GoldenTestError: If output doesn't match fixture (with diff)
        FileNotFoundError: If fixture doesn't exist (unless update=True)
    """
    fixture_path = _get_fixture_path(fixture_name)

    # Handle dict/JSON output
    if isinstance(output, dict):
        output = json.dumps(output, indent=2, sort_keys=True)
        is_binary = False

    # Check for update mode (from pytest flag or explicit)
    if update or _should_update_golden():
        update_golden(output, fixture_name, is_binary=is_binary)
        return

    # Normalize output for comparison
    if not is_binary:
        output = _normalize_content(output, is_binary=False)

    # Load and normalize fixture
    if not fixture_path.exists():
        raise FileNotFoundError(
            f"Golden fixture not found: {fixture_path}\n"
            f"Run with --update-golden to create it, or call update_golden() directly."
        )

    mode = "rb" if is_binary else "r"
    encoding = None if is_binary else "utf-8"
    with open(fixture_path, mode, encoding=encoding) as f:
        expected = f.read()

    if not is_binary:
        expected = _normalize_content(expected, is_binary=False)

    # Compare
    if output != expected:
        if is_binary:
            diff = f"Binary content differs (expected {len(expected)} bytes, got {len(output)} bytes)"
        else:
            diff = _generate_diff(expected, output, fixture_path)

        raise GoldenTestError(
            f"Output doesn't match golden fixture: {fixture_path}\n\n"
            f"Diff:\n{diff}\n\n"
            f"To update the fixture, run: pytest --update-golden {fixture_path.parent}",
            diff=diff,
            fixture_path=fixture_path,
        )


def load_fixture(fixture_name: str) -> Union[str, dict]:
    """
    Load a canonical workout fixture file.

    Args:
        fixture_name: Relative path within fixtures/ directory

    Returns:
        The fixture content as string, or parsed JSON dict if .json file

    Raises:
        FileNotFoundError: If fixture doesn't exist
    """
    fixture_path = _get_fixture_path(fixture_name)

    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    # Load and parse based on file extension
    if fixture_path.suffix == ".json":
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        with open(fixture_path, "r", encoding="utf-8") as f:
            return f.read()


def compare_output(
    actual: Union[str, bytes, dict],
    expected_fixture: str,
    *,
    is_binary: bool = False,
    regenerate: bool = False,
) -> bool:
    """
    Compare actual output against expected fixture, with optional regeneration.

    Args:
        actual: The actual output to compare
        expected_fixture: Relative path to expected fixture in fixtures/ directory
        is_binary: If True, compare as binary (no normalization)
        regenerate: If True, update the fixture with actual output

    Returns:
        True if output matches (or was regenerated), False if mismatch

    Raises:
        GoldenTestError: If output doesn't match fixture (with diff)
        FileNotfoundError: If fixture doesn't exist (unless regenerate=True)
    """
    # Use assert_golden for the comparison (it handles regeneration)
    try:
        assert_golden(actual, expected_fixture, is_binary=is_binary, update=regenerate)
        return True
    except GoldenTestError:
        return False


# ---------------------------------------------------------------------------
# Pytest Plugin for --update-golden flag
# ---------------------------------------------------------------------------

_UPDATE_GOLDEN = False


def _should_update_golden() -> bool:
    """Check if --update-golden flag is set."""
    return _UPDATE_GOLDEN


def pytest_addoption(parser):
    """Add --update-golden and --regenerate-golden command line options."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Update golden test fixtures instead of asserting (alias: --regenerate-golden)",
    )
    parser.addoption(
        "--regenerate-golden",
        action="store_true",
        default=False,
        help="Regenerate golden test fixtures (alias: --update-golden)",
    )


def pytest_configure(config):
    """Configure golden update mode from command line."""
    global _UPDATE_GOLDEN
    # Support both --update-golden and --regenerate-golden flags
    _UPDATE_GOLDEN = config.getoption("--update-golden", default=False) or config.getoption(
        "--regenerate-golden", default=False
    )


# ---------------------------------------------------------------------------
# Fixtures for golden tests
# ---------------------------------------------------------------------------


@pytest.fixture
def golden_update_mode(request) -> bool:
    """Fixture to check if we're in golden update mode."""
    return request.config.getoption("--update-golden", default=False) or request.config.getoption(
        "--regenerate-golden", default=False
    )


@pytest.fixture
def regenerate_golden(request) -> bool:
    """Fixture to check if we're in golden regeneration mode (--regenerate-golden)."""
    return request.config.getoption("--regenerate-golden", default=False)


@pytest.fixture
def fixtures_dir() -> Path:
    """Fixture providing path to golden fixtures directory."""
    return FIXTURES_DIR
