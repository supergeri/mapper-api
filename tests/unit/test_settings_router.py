"""
Unit tests for api/routers/settings.py

Part of AMA-586: Write unit tests for settings router.

Tests cover:
- GET /settings/defaults endpoint
- PUT /settings/defaults endpoint
- Pydantic validation for request payloads
- save_user_defaults() helper (atomic write, directory creation, error handling)
"""

import os
import pathlib

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.routers.settings import (
    router,
    save_user_defaults,
    get_settings_file_path,
    UserSettingsRequest,
    UserSettingsResponse,
    SettingsUpdateResponse,
)
from backend.auth import get_current_user


# ---------------------------------------------------------------------------
# Test-local app & client (uses the new router, not the legacy app.py)
# ---------------------------------------------------------------------------


TEST_USER_ID = "test-user-123"


def _mock_get_current_user() -> str:
    return TEST_USER_ID


@pytest.fixture
def settings_client():
    """
    TestClient wired to a minimal FastAPI app that only includes the
    settings router.  This avoids interference from the legacy endpoints
    in backend/app.py which are not yet removed.
    """
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_current_user] = _mock_get_current_user
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# GET /settings/defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetDefaults:
    """Tests for GET /settings/defaults."""

    def test_get_defaults_returns_settings(self, settings_client):
        """Should return current settings from YAML file."""
        stored = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "dark",
        }
        with patch("api.routers.settings.load_user_defaults", return_value=stored):
            resp = settings_client.get("/settings/defaults")
            assert resp.status_code == 200
            data = resp.json()
            assert data["distance_handling"] == "percentage"
            assert data["default_exercise_value"] == "rep_range"
            assert data["ignore_distance"] is False
            assert data["theme"] == "dark"

    def test_get_defaults_with_distance_unit(self, settings_client):
        """Should return distance_unit setting correctly."""
        stored = {
            "distance_handling": "distance_unit",
            "default_exercise_value": "time",
            "ignore_distance": True,
            "theme": "light",
        }
        with patch("api.routers.settings.load_user_defaults", return_value=stored):
            resp = settings_client.get("/settings/defaults")
            assert resp.status_code == 200
            data = resp.json()
            assert data["distance_handling"] == "distance_unit"
            assert data["default_exercise_value"] == "time"
            assert data["ignore_distance"] is True
            assert data["theme"] == "light"

    def test_get_defaults_returns_500_on_file_not_found(self, settings_client):
        """Should return 500 when settings file is missing."""
        with patch(
            "api.routers.settings.load_user_defaults",
            side_effect=FileNotFoundError("no file"),
        ):
            resp = settings_client.get("/settings/defaults")
            assert resp.status_code == 500
            assert "Failed to load user settings" in resp.json()["detail"]

    def test_get_defaults_returns_500_on_yaml_error(self, settings_client):
        """Should return 500 when YAML is malformed."""
        with patch(
            "api.routers.settings.load_user_defaults",
            side_effect=yaml.YAMLError("bad yaml"),
        ):
            resp = settings_client.get("/settings/defaults")
            assert resp.status_code == 500

    def test_get_defaults_returns_500_on_key_error(self, settings_client):
        """Should return 500 when settings keys are missing."""
        with patch(
            "api.routers.settings.load_user_defaults",
            side_effect=KeyError("distance_handling"),
        ):
            resp = settings_client.get("/settings/defaults")
            assert resp.status_code == 500

    def test_get_defaults_returns_500_on_value_error(self, settings_client):
        """Should return 500 when settings values are invalid."""
        with patch(
            "api.routers.settings.load_user_defaults",
            side_effect=ValueError("invalid value"),
        ):
            resp = settings_client.get("/settings/defaults")
            assert resp.status_code == 500

    def test_get_defaults_backward_compatible_no_theme(self, settings_client):
        """Should default to 'system' theme when theme is missing from stored settings."""
        stored = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
        }
        with patch("api.routers.settings.load_user_defaults", return_value=stored):
            resp = settings_client.get("/settings/defaults")
            assert resp.status_code == 200
            data = resp.json()
            assert data["theme"] == "system"


# ---------------------------------------------------------------------------
# PUT /settings/defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUpdateDefaults:
    """Tests for PUT /settings/defaults."""

    def test_put_defaults_saves_and_returns(self, settings_client):
        """Should save settings and return success response."""
        payload = {
            "distance_handling": "distance_unit",
            "default_exercise_value": "time",
            "ignore_distance": True,
            "theme": "dark",
        }
        with patch("api.routers.settings.save_user_defaults") as mock_save:
            resp = settings_client.put("/settings/defaults", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["message"] == "Settings updated successfully"
            assert data["settings"]["distance_handling"] == "distance_unit"
            assert data["settings"]["default_exercise_value"] == "time"
            assert data["settings"]["ignore_distance"] is True
            assert data["settings"]["theme"] == "dark"
            mock_save.assert_called_once_with(
                {
                    "distance_handling": "distance_unit",
                    "default_exercise_value": "time",
                    "ignore_distance": True,
                    "theme": "dark",
                }
            )

    def test_put_defaults_percentage_rep_range(self, settings_client):
        """Should accept percentage + rep_range combination."""
        payload = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        with patch("api.routers.settings.save_user_defaults"):
            resp = settings_client.put("/settings/defaults", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["settings"]["distance_handling"] == "percentage"
            assert data["settings"]["default_exercise_value"] == "rep_range"
            assert data["settings"]["theme"] == "system"

    def test_put_defaults_percentage_as_exercise_value(self, settings_client):
        """Should accept percentage as default_exercise_value."""
        payload = {
            "distance_handling": "percentage",
            "default_exercise_value": "percentage",
            "ignore_distance": False,
            "theme": "light",
        }
        with patch("api.routers.settings.save_user_defaults"):
            resp = settings_client.put("/settings/defaults", json=payload)
            assert resp.status_code == 200
            assert resp.json()["settings"]["default_exercise_value"] == "percentage"

    def test_put_defaults_ignore_distance_defaults_false(self, settings_client):
        """ignore_distance should default to False when omitted."""
        payload = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "theme": "dark",
        }
        with patch("api.routers.settings.save_user_defaults"):
            resp = settings_client.put("/settings/defaults", json=payload)
            assert resp.status_code == 200
            assert resp.json()["settings"]["ignore_distance"] is False
            assert resp.json()["settings"]["theme"] == "dark"

    def test_put_defaults_validates_invalid_distance_handling(self, settings_client):
        """Should reject invalid distance_handling value with 422."""
        payload = {
            "distance_handling": "invalid_option",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        resp = settings_client.put("/settings/defaults", json=payload)
        assert resp.status_code == 422

    def test_put_defaults_validates_invalid_exercise_value(self, settings_client):
        """Should reject invalid default_exercise_value with 422."""
        payload = {
            "distance_handling": "percentage",
            "default_exercise_value": "invalid",
            "ignore_distance": False,
            "theme": "system",
        }
        resp = settings_client.put("/settings/defaults", json=payload)
        assert resp.status_code == 422

    def test_put_defaults_missing_required_field(self, settings_client):
        """Should reject payload missing required fields with 422."""
        payload = {"distance_handling": "percentage"}
        resp = settings_client.put("/settings/defaults", json=payload)
        assert resp.status_code == 422

    def test_put_defaults_empty_body(self, settings_client):
        """Should reject empty body with 422."""
        resp = settings_client.put("/settings/defaults", json={})
        assert resp.status_code == 422

    def test_put_defaults_returns_500_on_save_oserror(self, settings_client):
        """Should return 500 when save_user_defaults raises OSError."""
        payload = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        with patch(
            "api.routers.settings.save_user_defaults",
            side_effect=OSError("disk full"),
        ):
            resp = settings_client.put("/settings/defaults", json=payload)
            assert resp.status_code == 500
            assert "Failed to save user settings" in resp.json()["detail"]

    def test_put_defaults_returns_500_on_file_not_found(self, settings_client):
        """Should return 500 when settings directory cannot be created."""
        payload = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        with patch(
            "api.routers.settings.save_user_defaults",
            side_effect=FileNotFoundError("Cannot create settings directory"),
        ):
            resp = settings_client.put("/settings/defaults", json=payload)
            assert resp.status_code == 500
            assert "Settings directory error" in resp.json()["detail"]

    def test_put_defaults_returns_500_on_value_error(self, settings_client):
        """Should return 500 when YAML serialization fails."""
        payload = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        with patch(
            "api.routers.settings.save_user_defaults",
            side_effect=ValueError("Failed to serialize settings as YAML"),
        ):
            resp = settings_client.put("/settings/defaults", json=payload)
            assert resp.status_code == 500
            assert "Failed to save user settings" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPydanticModels:
    """Tests for settings Pydantic models."""

    def test_user_settings_request_valid(self):
        """Should accept valid settings combinations."""
        req = UserSettingsRequest(
            distance_handling="percentage",
            default_exercise_value="rep_range",
            ignore_distance=False,
            theme="dark",
        )
        assert req.distance_handling == "percentage"
        assert req.default_exercise_value == "rep_range"
        assert req.ignore_distance is False
        assert req.theme == "dark"

    def test_user_settings_request_all_exercise_values(self):
        """Should accept all valid default_exercise_value options."""
        for val in ("rep_range", "percentage", "time"):
            req = UserSettingsRequest(
                distance_handling="percentage",
                default_exercise_value=val,
                ignore_distance=False,
                theme="system",
            )
            assert req.default_exercise_value == val

    def test_user_settings_request_all_distance_handling(self):
        """Should accept all valid distance_handling options."""
        for val in ("percentage", "distance_unit"):
            req = UserSettingsRequest(
                distance_handling=val,
                default_exercise_value="rep_range",
                ignore_distance=False,
                theme="light",
            )
            assert req.distance_handling == val

    def test_user_settings_request_ignore_distance_default(self):
        """ignore_distance should default to False."""
        req = UserSettingsRequest(
            distance_handling="percentage",
            default_exercise_value="rep_range",
            theme="dark",
        )
        assert req.ignore_distance is False

    def test_user_settings_request_theme_default(self):
        """theme should default to 'system'."""
        req = UserSettingsRequest(
            distance_handling="percentage",
            default_exercise_value="rep_range",
        )
        assert req.theme == "system"

    def test_user_settings_request_all_theme_options(self):
        """Should accept all valid theme options."""
        for theme in ("light", "dark", "system"):
            req = UserSettingsRequest(
                distance_handling="percentage",
                default_exercise_value="rep_range",
                theme=theme,
            )
            assert req.theme == theme

    def test_user_settings_request_invalid_distance_handling(self):
        """Should raise ValidationError for invalid distance_handling."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserSettingsRequest(
                distance_handling="bad_value",
                default_exercise_value="rep_range",
                theme="system",
            )

    def test_user_settings_request_invalid_exercise_value(self):
        """Should raise ValidationError for invalid default_exercise_value."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserSettingsRequest(
                distance_handling="percentage",
                default_exercise_value="bad_value",
                theme="system",
            )

    def test_user_settings_request_invalid_theme(self):
        """Should raise ValidationError for invalid theme."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserSettingsRequest(
                distance_handling="percentage",
                default_exercise_value="rep_range",
                theme="invalid_theme",
            )

    def test_user_settings_response_model(self):
        """UserSettingsResponse should serialize correctly."""
        resp = UserSettingsResponse(
            distance_handling="percentage",
            default_exercise_value="rep_range",
            ignore_distance=True,
            theme="dark",
        )
        data = resp.model_dump()
        assert data == {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": True,
            "theme": "dark",
        }

    def test_settings_update_response_model(self):
        """SettingsUpdateResponse should contain message and settings."""
        inner = UserSettingsResponse(
            distance_handling="distance_unit",
            default_exercise_value="time",
            ignore_distance=False,
            theme="light",
        )
        resp = SettingsUpdateResponse(message="ok", settings=inner)
        data = resp.model_dump()
        assert data["message"] == "ok"
        assert data["settings"]["distance_handling"] == "distance_unit"
        assert data["settings"]["theme"] == "light"


# ---------------------------------------------------------------------------
# save_user_defaults() helper tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSaveUserDefaults:
    """Tests for save_user_defaults() atomic write helper."""

    def test_save_creates_yaml_file(self, tmp_path):
        """Should write settings as YAML with 'defaults' wrapper."""
        settings_file = tmp_path / "settings" / "user_defaults.yaml"
        settings_dict = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "dark",
        }
        with patch(
            "api.routers.settings.get_settings_file_path",
            return_value=settings_file,
        ):
            save_user_defaults(settings_dict)

        assert settings_file.exists()
        data = yaml.safe_load(settings_file.read_text())
        assert data["defaults"]["distance_handling"] == "percentage"
        assert data["defaults"]["default_exercise_value"] == "rep_range"
        assert data["defaults"]["ignore_distance"] is False
        assert data["defaults"]["theme"] == "dark"

    def test_save_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        settings_file = tmp_path / "deep" / "nested" / "user_defaults.yaml"
        settings_dict = {
            "distance_handling": "distance_unit",
            "default_exercise_value": "time",
            "ignore_distance": True,
            "theme": "system",
        }
        with patch(
            "api.routers.settings.get_settings_file_path",
            return_value=settings_file,
        ):
            save_user_defaults(settings_dict)

        assert settings_file.exists()
        assert settings_file.parent.exists()

    def test_save_overwrites_existing_file(self, tmp_path):
        """Should overwrite existing settings file atomically."""
        settings_file = tmp_path / "user_defaults.yaml"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("defaults:\n  distance_handling: percentage\n")

        new_settings = {
            "distance_handling": "distance_unit",
            "default_exercise_value": "time",
            "ignore_distance": True,
            "theme": "light",
        }
        with patch(
            "api.routers.settings.get_settings_file_path",
            return_value=settings_file,
        ):
            save_user_defaults(new_settings)

        data = yaml.safe_load(settings_file.read_text())
        assert data["defaults"]["distance_handling"] == "distance_unit"

    def test_save_atomic_write_uses_tempfile(self, tmp_path):
        """Should use tempfile + os.replace for atomic writes."""
        settings_file = tmp_path / "user_defaults.yaml"
        settings_dict = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "dark",
        }
        with (
            patch(
                "api.routers.settings.get_settings_file_path",
                return_value=settings_file,
            ),
            patch("api.routers.settings.os.replace", wraps=os.replace) as mock_replace,
        ):
            save_user_defaults(settings_dict)
            mock_replace.assert_called_once()
            call_args = mock_replace.call_args
            assert str(call_args[0][1]) == str(settings_file)

    def test_save_raises_file_not_found_on_mkdir_failure(self, tmp_path):
        """Should raise FileNotFoundError when directory creation fails."""
        settings_file = tmp_path / "settings" / "user_defaults.yaml"
        settings_dict = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        with (
            patch(
                "api.routers.settings.get_settings_file_path",
                return_value=settings_file,
            ),
            patch.object(
                pathlib.Path,
                "mkdir",
                side_effect=OSError("Permission denied"),
            ),
        ):
            with pytest.raises(FileNotFoundError, match="Cannot create settings directory"):
                save_user_defaults(settings_dict)

    def test_save_raises_oserror_on_write_failure(self, tmp_path):
        """Should raise OSError when file write fails."""
        settings_file = tmp_path / "user_defaults.yaml"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_dict = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        with (
            patch(
                "api.routers.settings.get_settings_file_path",
                return_value=settings_file,
            ),
            patch(
                "api.routers.settings.tempfile.NamedTemporaryFile",
                side_effect=OSError("disk full"),
            ),
        ):
            with pytest.raises(OSError, match="Failed to write settings file"):
                save_user_defaults(settings_dict)

    def test_save_wraps_data_in_defaults_key(self, tmp_path):
        """Should wrap settings dict under 'defaults' key in YAML."""
        settings_file = tmp_path / "user_defaults.yaml"
        settings_dict = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "dark",
        }
        with patch(
            "api.routers.settings.get_settings_file_path",
            return_value=settings_file,
        ):
            save_user_defaults(settings_dict)

        data = yaml.safe_load(settings_file.read_text())
        assert "defaults" in data
        assert set(data["defaults"].keys()) == {
            "distance_handling",
            "default_exercise_value",
            "ignore_distance",
            "theme",
        }

    def test_save_no_temp_file_leak_on_replace_failure(self, tmp_path):
        """Should clean up temp file if os.replace fails."""
        settings_file = tmp_path / "user_defaults.yaml"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_dict = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        with (
            patch(
                "api.routers.settings.get_settings_file_path",
                return_value=settings_file,
            ),
            patch(
                "api.routers.settings.os.replace",
                side_effect=OSError("replace failed"),
            ),
        ):
            with pytest.raises(OSError, match="Failed to write settings file"):
                save_user_defaults(settings_dict)

        # No stale temp files should remain (only directory, no .yaml files)
        yaml_files = list(tmp_path.glob("*.yaml"))
        assert len(yaml_files) == 0, f"Temp file leaked: {yaml_files}"


# ---------------------------------------------------------------------------
# get_settings_file_path() helper tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetSettingsFilePath:
    """Tests for get_settings_file_path() helper."""

    def test_returns_pathlib_path(self):
        """Should return a pathlib.Path instance."""
        result = get_settings_file_path()
        assert isinstance(result, pathlib.Path)

    def test_ends_with_expected_suffix(self):
        """Path should end with shared/settings/user_defaults.yaml."""
        result = get_settings_file_path()
        assert result.name == "user_defaults.yaml"
        assert result.parent.name == "settings"
        assert result.parent.parent.name == "shared"


# ---------------------------------------------------------------------------
# Theme endpoints tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetTheme:
    """Tests for GET /settings/theme endpoint."""

    def test_get_theme_returns_current_theme(self, settings_client):
        """Should return current theme setting."""
        stored = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "dark",
        }
        with patch("api.routers.settings.load_user_defaults", return_value=stored):
            resp = settings_client.get("/settings/theme")
            assert resp.status_code == 200
            data = resp.json()
            assert data["theme"] == "dark"

    def test_get_theme_defaults_to_system(self, settings_client):
        """Should default to 'system' when theme not in stored settings."""
        stored = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
        }
        with patch("api.routers.settings.load_user_defaults", return_value=stored):
            resp = settings_client.get("/settings/theme")
            assert resp.status_code == 200
            data = resp.json()
            assert data["theme"] == "system"

    def test_get_theme_returns_500_on_error(self, settings_client):
        """Should return 500 when settings cannot be loaded."""
        with patch(
            "api.routers.settings.load_user_defaults",
            side_effect=FileNotFoundError("no file"),
        ):
            resp = settings_client.get("/settings/theme")
            assert resp.status_code == 500
            assert "Failed to load theme setting" in resp.json()["detail"]


@pytest.mark.unit
class TestUpdateTheme:
    """Tests for PUT /settings/theme endpoint."""

    def test_update_theme_saves_and_returns(self, settings_client):
        """Should save theme and return success response."""
        stored = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "light",
        }
        with patch("api.routers.settings.load_user_defaults", return_value=stored):
            with patch("api.routers.settings.save_user_defaults") as mock_save:
                resp = settings_client.put("/settings/theme", json={"theme": "dark"})
                assert resp.status_code == 200
                data = resp.json()
                assert data["theme"] == "dark"
                # Verify save was called with updated theme
                mock_save.assert_called_once()
                saved_settings = mock_save.call_args[0][0]
                assert saved_settings["theme"] == "dark"

    def test_update_theme_all_valid_options(self, settings_client):
        """Should accept all valid theme options."""
        stored = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "system",
        }
        for theme in ("light", "dark", "system"):
            with patch("api.routers.settings.load_user_defaults", return_value=stored.copy()):
                with patch("api.routers.settings.save_user_defaults"):
                    resp = settings_client.put("/settings/theme", json={"theme": theme})
                    assert resp.status_code == 200
                    assert resp.json()["theme"] == theme

    def test_update_theme_rejects_invalid_theme(self, settings_client):
        """Should reject invalid theme value with 422."""
        resp = settings_client.put("/settings/theme", json={"theme": "invalid_theme"})
        assert resp.status_code == 422

    def test_update_theme_returns_500_on_save_error(self, settings_client):
        """Should return 500 when save fails."""
        stored = {
            "distance_handling": "percentage",
            "default_exercise_value": "rep_range",
            "ignore_distance": False,
            "theme": "light",
        }
        with patch("api.routers.settings.load_user_defaults", return_value=stored):
            with patch(
                "api.routers.settings.save_user_defaults",
                side_effect=OSError("disk full"),
            ):
                resp = settings_client.put("/settings/theme", json={"theme": "dark"})
                assert resp.status_code == 500
                assert "Failed to save theme setting" in resp.json()["detail"]
