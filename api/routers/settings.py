"""
Settings router for user default preferences.

Provides GET/PUT endpoints for managing user-specific settings
like distance units and exercise defaults.

Part of AMA-585: Extract settings router from monolithic app.py
"""
import os
import pathlib
import tempfile
from typing import Literal

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError

from backend.auth import get_current_user
from backend.adapters.blocks_to_hyrox_yaml import load_user_defaults

# Type aliases for valid setting values
DISTANCE_HANDLING_OPTIONS = Literal["percentage", "distance_unit"]
DEFAULT_EXERCISE_VALUE_OPTIONS = Literal["rep_range", "percentage", "time"]

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
)


class UserSettingsRequest(BaseModel):
    """Request model for updating user settings."""
    distance_handling: DISTANCE_HANDLING_OPTIONS = Field(
        description="How to handle distance values in workouts"
    )
    default_exercise_value: DEFAULT_EXERCISE_VALUE_OPTIONS = Field(
        description="Default value type for exercises"
    )
    ignore_distance: bool = Field(
        default=False,
        description="Whether to ignore distance in workout calculations"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "distance_handling": "percentage",
                "default_exercise_value": "rep_range",
                "ignore_distance": False
            }
        }


class UserSettingsResponse(BaseModel):
    """Response model for user settings."""
    distance_handling: DISTANCE_HANDLING_OPTIONS
    default_exercise_value: DEFAULT_EXERCISE_VALUE_OPTIONS
    ignore_distance: bool

    class Config:
        json_schema_extra = {
            "example": {
                "distance_handling": "percentage",
                "default_exercise_value": "rep_range",
                "ignore_distance": False
            }
        }


class SettingsUpdateResponse(BaseModel):
    """Response for successful settings update."""
    message: str
    settings: UserSettingsResponse


def get_settings_file_path() -> pathlib.Path:
    """
    Get the path to the user defaults settings file.
    
    IMPORTANT: This path must match the one used by load_user_defaults()
    in backend.adapters.blocks_to_hyrox_yaml:
        ROOT / "shared/settings/user_defaults.yaml"
    
    Both endpoints (GET/PUT) use this to ensure consistency.

    Returns:
        pathlib.Path: Path to shared/settings/user_defaults.yaml
    """
    root = pathlib.Path(__file__).resolve().parents[2]
    return root / "shared/settings/user_defaults.yaml"


def save_user_defaults(settings_dict: dict) -> None:
    """
    Save user default settings to YAML file with atomic writes.

    Uses tempfile + os.replace() to ensure atomicity and prevent
    race conditions from partial writes during concurrent requests.
    
    Path consistency: Uses get_settings_file_path() to write to the same
    location that load_user_defaults() reads from.

    Args:
        settings_dict: Dictionary containing distance_handling,
                      default_exercise_value, ignore_distance

    Raises:
        FileNotFoundError: If settings directory cannot be created
        yaml.YAMLError: If YAML serialization fails
        OSError: If file write operation fails
    """
    settings_path = get_settings_file_path()

    # Ensure directory exists
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise FileNotFoundError(
            f"Cannot create settings directory {settings_path.parent}: {e}"
        ) from e

    # Prepare data structure
    data = {"defaults": settings_dict}

    # Write to temp file first (atomic operation prevents partial writes)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(settings_path.parent),
            suffix=".yaml",
            delete=False,
            encoding="utf-8"
        ) as tmp_file:
            yaml.safe_dump(data, tmp_file, sort_keys=False, default_flow_style=False)
            tmp_path = tmp_file.name

        # Atomic replace (ensures settings are either fully updated or unchanged)
        os.replace(tmp_path, str(settings_path))

    except yaml.YAMLError as e:
        raise ValueError(f"Failed to serialize settings as YAML: {e}") from e
    except OSError as e:
        # Clean up temp file if replace failed
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except OSError:
            pass
        raise OSError(f"Failed to write settings file: {e}") from e


# NOTE: Settings are currently application-wide (not per-user) but protected by auth.
# Authentication is required to prevent unauthorized access/modification.
# Future: If per-user settings are needed, refactor to read/write user-specific files
# and include user.id in the file path: shared/settings/{user.id}_defaults.yaml


@router.get(
    "/defaults",
    response_model=UserSettingsResponse,
    summary="Get user default settings",
    description="Retrieve the current user's default settings for workouts",
)
def get_defaults(current_user=Depends(get_current_user)) -> UserSettingsResponse:
    """
    Get current user default settings.

    Note: Authentication is required but settings are global (not per-user).
    The current_user parameter gates access to this endpoint; actual settings
    are stored at shared/settings/user_defaults.yaml for simplicity.
    If per-user settings are needed in the future, update implementation.
    
    Path consistency: Uses load_user_defaults() from backend.adapters which
    reads from the same path as get_settings_file_path() used in PUT endpoint.

    Returns:
        UserSettingsResponse: Current user's default settings

    Raises:
        HTTPException: If settings cannot be loaded (500 error)
    """
    try:
        settings = load_user_defaults()
        return UserSettingsResponse(**settings)
    except (FileNotFoundError, yaml.YAMLError, KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load user settings: {str(e)}"
        ) from e


@router.put(
    "/defaults",
    response_model=SettingsUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user default settings",
    description="Update the current user's default settings for workouts",
)
def update_defaults(
    settings: UserSettingsRequest,
    current_user=Depends(get_current_user)
) -> SettingsUpdateResponse:
    """
    Update user default settings.

    Validates input and atomically writes settings to YAML file.

    Note: Authentication is required but settings are global (not per-user).
    The current_user parameter gates access to this endpoint; actual settings
    are stored at shared/settings/user_defaults.yaml for simplicity.
    
    Path consistency: Uses get_settings_file_path() to write to the same
    location that load_user_defaults() (used in GET endpoint) reads from.
    Both resolve to ROOT / "shared/settings/user_defaults.yaml".

    Args:
        settings: New settings values
        current_user: Current authenticated user (from dependency)

    Returns:
        SettingsUpdateResponse: Confirmation message and updated settings

    Raises:
        HTTPException: If settings cannot be saved (500 error)
    """
    try:
        settings_dict = {
            "distance_handling": settings.distance_handling,
            "default_exercise_value": settings.default_exercise_value,
            "ignore_distance": settings.ignore_distance,
        }

        save_user_defaults(settings_dict)

        return SettingsUpdateResponse(
            message="Settings updated successfully",
            settings=UserSettingsResponse(**settings_dict),
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Settings directory error: {str(e)}",
        ) from e
    except (ValueError, OSError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save user settings: {str(e)}",
        ) from e
