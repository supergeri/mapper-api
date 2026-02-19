"""
Tags router for user tag management.

Part of AMA-594: Create tags router

This router contains endpoints for:
- GET /tags - Get all tags for a user
- POST /tags - Create a new user tag
- DELETE /tags/{tag_id} - Delete a user tag
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from api.deps import (
    get_current_user,
    get_user_tags,
    create_user_tag,
    delete_user_tag,
)

router = APIRouter(
    tags=["Tags"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateTagRequest(BaseModel):
    """Request model for creating a user tag."""
    profile_id: str
    name: str
    color: Optional[str] = None


# =============================================================================
# User Tags Endpoints (AMA-122, extracted in AMA-594)
# =============================================================================


@router.get("/tags")
def get_tags_endpoint(
    user_id: str = Depends(get_current_user),
    profile_id: str = Query(..., description="User profile ID")
):
    """
    Get all tags for a user.

    Args:
        profile_id: User profile ID

    Returns:
        List of tags with count
    """
    # Authorization: ensure user_id matches profile_id
    if user_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this profile's tags")
    tags = get_user_tags(profile_id)

    return {
        "success": True,
        "tags": tags,
        "count": len(tags)
    }


@router.post("/tags")
def create_tag_endpoint(
    request: CreateTagRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Create a new user tag.

    Args:
        request: Tag creation request with profile_id, name, and optional color

    Returns:
        Created tag or error message
    """
    # Authorization: ensure user_id matches profile_id
    if user_id != request.profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to create tags for this profile")

    result = create_user_tag(
        profile_id=request.profile_id,
        name=request.name,
        color=request.color
    )

    if result:
        return {
            "success": True,
            "tag": result,
            "message": "Tag created"
        }
    else:
        return {
            "success": False,
            "message": "Failed to create tag (may already exist)"
        }


@router.delete("/tags/{tag_id}")
def delete_tag_endpoint(
    tag_id: str,
    user_id: str = Depends(get_current_user),
    profile_id: str = Query(..., description="User profile ID")
):
    """
    Delete a user tag.

    Args:
        tag_id: The ID of the tag to delete
        profile_id: User profile ID

    Returns:
        Success status message
    """
    # Authorization: ensure user_id matches profile_id
    if user_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete tags for this profile")

    success = delete_user_tag(tag_id, profile_id)

    if success:
        return {
            "success": True,
            "message": "Tag deleted"
        }
    else:
        return {
            "success": False,
            "message": "Failed to delete tag"
        }
