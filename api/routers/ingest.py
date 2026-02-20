"""
Ingest router for Instagram and workout text parsing.

Endpoints:
- POST /api/ingest/instagram/preview — Get Instagram oEmbed preview
- POST /api/ingest/workout/parse — Parse workout text into structured data

Part of AMA-532: Instagram Link Ingestion POC (oEmbed Preview + Workout Text Parsing)
"""

import hashlib
import logging
import re
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ingest",
    tags=["ingest"],
)


# =============================================================================
# Settings for Instagram oEmbed
# =============================================================================

def get_instagram_settings() -> Dict[str, Any]:
    """Get Instagram/Meta API settings."""
    settings = get_settings()
    return {
        "meta_access_token": getattr(settings, 'meta_access_token', None),
        "meta_app_id": getattr(settings, 'meta_app_id', None),
        "meta_app_secret": getattr(settings, 'meta_app_secret', None),
    }


# =============================================================================
# In-Memory Cache for oEmbed Results
# =============================================================================

MAX_CACHE_SIZE = 500
_oembed_cache: Dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 3600  # 1 hour


def _get_cache_key(url: str) -> str:
    """Generate cache key from URL."""
    return hashlib.md5(url.encode()).hexdigest()


def _get_cached_oembed(url: str) -> Optional[Dict[str, Any]]:
    """Get cached oEmbed result if available and not expired."""
    key = _get_cache_key(url)
    if key in _oembed_cache:
        result, cached_at = _oembed_cache[key]
        if time.time() - cached_at < _CACHE_TTL:
            logger.debug(f"Cache hit for URL: {url[:50]}...")
            return result
        else:
            del _oembed_cache[key]
    return None


def _set_cached_oembed(url: str, result: Dict[str, Any]) -> None:
    """Cache oEmbed result with LRU eviction."""
    key = _get_cache_key(url)
    
    # Evict oldest entries if cache is full
    if len(_oembed_cache) >= MAX_CACHE_SIZE:
        oldest_key = min(_oembed_cache, key=lambda k: _oembed_cache[k][1])
        del _oembed_cache[oldest_key]
    
    _oembed_cache[key] = (result, time.time())


# =============================================================================
# Simple Rate Limiter
# =============================================================================

_rate_limit_store: Dict[str, list] = {}
RATE_LIMIT = 10  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds


def _check_rate_limit(identifier: str) -> bool:
    """Check if identifier has exceeded rate limit. Returns True if allowed."""
    now = time.time()
    
    if identifier not in _rate_limit_store:
        _rate_limit_store[identifier] = []
    
    # Clean old entries
    _rate_limit_store[identifier] = [
        ts for ts in _rate_limit_store[identifier]
        if now - ts < RATE_LIMIT_WINDOW
    ]
    
    if len(_rate_limit_store[identifier]) >= RATE_LIMIT:
        return False
    
    _rate_limit_store[identifier].append(now)
    return True


# =============================================================================
# Request/Response Models
# =============================================================================


class InstagramPreviewRequest(BaseModel):
    """Request model for Instagram preview."""
    url: str = Field(..., description="Instagram post or reel URL")


class InstagramPreviewResponse(BaseModel):
    """Response model for Instagram oEmbed preview."""
    success: bool = Field(..., description="Whether preview was successful")
    html: Optional[str] = Field(None, description="oEmbed HTML embed code")
    author_name: Optional[str] = Field(None, description="Author username")
    author_url: Optional[str] = Field(None, description="Author profile URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail image URL")
    title: Optional[str] = Field(None, description="Post title or caption preview")
    provider_name: str = Field(default="Instagram", description="Provider name")
    cached: bool = Field(default=False, description="Whether result was cached")
    error: Optional[str] = Field(None, description="Error message if failed")


class WorkoutParseRequest(BaseModel):
    """Request model for workout text parsing."""
    text: str = Field(..., description="Workout text to parse", min_length=1, max_length=10000)


class WorkoutExercise(BaseModel):
    """Parsed exercise from workout text."""
    name: str = Field(..., description="Exercise name")
    sets: Optional[int] = Field(None, description="Number of sets")
    reps: Optional[int] = Field(None, description="Number of reps")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    weight: Optional[str] = Field(None, description="Weight/load description")
    notes: Optional[str] = Field(None, description="Additional notes")


class WorkoutRound(BaseModel):
    """Parsed round from workout text."""
    round_number: int = Field(..., description="Round number")
    exercises: List[WorkoutExercise] = Field(default_factory=list, description="Exercises in round")
    rest_seconds: Optional[int] = Field(None, description="Rest between rounds")


class WorkoutParseResponse(BaseModel):
    """Response model for workout text parsing."""
    success: bool = Field(..., description="Whether parsing was successful")
    title: Optional[str] = Field(None, description="Workout title if detected")
    rounds: List[WorkoutRound] = Field(default_factory=list, description="Parsed rounds")
    exercises: List[WorkoutExercise] = Field(default_factory=list, description="Flat list of exercises")
    total_duration_minutes: Optional[int] = Field(None, description="Estimated total duration")
    equipment: List[str] = Field(default_factory=list, description="Detected equipment")
    raw_text: str = Field(..., description="Original text for reference")
    error: Optional[str] = Field(None, description="Error message if failed")


# =============================================================================
# URL Validation
# =============================================================================

INSTAGRAM_HOSTS = [
    "instagram.com",
    "www.instagram.com",
    "ddinstagram.com",
    "www.ddinstagram.com",
]


def _validate_instagram_url(url: str) -> str:
    """Validate that URL is a valid Instagram URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use HTTP or HTTPS")
        
        if parsed.netloc not in INSTAGRAM_HOSTS:
            raise ValueError(f"URL must be from Instagram ({', '.join(INSTAGRAM_HOSTS)})")
        
        # Must be a post or reel URL
        path = parsed.path.strip("/")
        if not path or "p/" not in path and "reel" not in path:
            raise ValueError("URL must be a post (/p/...) or reel (/reel/...)")
        
        return url
    except Exception as e:
        raise ValueError(f"Invalid Instagram URL: {e}")


# =============================================================================
# Instagram oEmbed API
# =============================================================================

INSTAGRAM_GRAPH_API = "https://graph.facebook.com/v18.0"


async def _fetch_instagram_oembed(url: str) -> Dict[str, Any]:
    """
    Fetch Instagram oEmbed data using Meta Graph API.
    
    Uses the Instagram oEmbed endpoint to get embed HTML and metadata.
    """
    settings = get_settings()
    
    # Check cache first
    cached = _get_cached_oembed(url)
    if cached:
        cached["cached"] = True
        return cached
    
    # Prepare API request
    # Instagram oEmbed endpoint
    oembed_url = f"{INSTAGRAM_GRAPH_API}/instagram_oembed"
    
    params = {
        "input_url": url,
        "access_token": settings.meta_access_token or "",
    }
    
    headers = {
        "Accept": "application/json",
    }
    
    # If no access token, try the public oEmbed endpoint as fallback
    if not settings.meta_access_token:
        # Try public oEmbed endpoint
        public_oembed_url = "https://api.instagram.com/oembed/"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(public_oembed_url, params={"url": url})
                if response.status_code == 200:
                    data = response.json()
                    _set_cached_oembed(url, data)
                    return data
                else:
                    logger.warning(f"Public oEmbed failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"Public oEmbed request failed: {e}")
        
        # Return graceful fallback - user can still manually enter workout
        return {
            "success": False,
            "error": "Instagram preview unavailable. You can still paste workout text manually.",
        }
    
    # Use Meta Graph API with access token
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(oembed_url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                data["success"] = True
                _set_cached_oembed(url, data)
                return data
            elif response.status_code == 401:
                logger.warning("Meta access token invalid")
                return {
                    "success": False,
                    "error": "Instagram preview unavailable. You can still paste workout text manually.",
                }
            else:
                logger.warning(f"Instagram oEmbed API error: {response.status_code} - {response.text[:200]}")
                return {
                    "success": False,
                    "error": "Instagram preview unavailable. You can still paste workout text manually.",
                }
    except httpx.TimeoutException:
        logger.warning("Instagram oEmbed request timed out")
        return {
            "success": False,
            "error": "Instagram preview timed out. You can still paste workout text manually.",
        }
    except Exception as e:
        logger.error(f"Instagram oEmbed request failed: {e}")
        return {
            "success": False,
            "error": "Instagram preview unavailable. You can still paste workout text manually.",
        }


# =============================================================================
# Workout Text Parser
# =============================================================================

# Common exercise patterns
EXERCISE_PATTERNS = [
    r"(\d+)\s*x\s*(\d+)",  # 3x10 format
    r"(\d+)\s+sets?\s*(?:of\s+)?(\d+)\s+reps?",  # 3 sets of 10 reps
    r"(\d+)\s+reps?",  # 10 reps
    r"(\d+)\s+seconds?",  # 30 seconds
    r"(\d+)\s+minutes?",  # 5 minutes
    r"(\d+):(\d+)",  # 1:30 format
]

# Equipment keywords
EQUIPMENT_KEYWORDS = {
    "dumbbell": ["dumbbell", "db", "dumbbells", "db's"],
    "barbell": ["barbell", "bar", "bb"],
    "kettlebell": ["kettlebell", "kb", "kbs"],
    "pull-up bar": ["pull-up", "pullup", "chin-up", "chinup"],
    "resistance band": ["resistance band", "band", "bands"],
    "box": ["box", "plyo box", "jump box"],
    "medicine ball": ["medicine ball", "med ball", "medball"],
    "sandbag": ["sandbag"],
    "rower": ["rower", "rowing"],
    "bike": ["bike", "cycling", "assault bike"],
    "ski": ["ski", "ski erg"],
}


def _extract_equipment(text: str) -> List[str]:
    """Extract equipment from workout text."""
    text_lower = text.lower()
    found = []
    
    for equipment, keywords in EQUIPMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                found.append(equipment)
                break
    
    return list(set(found))


def _extract_exercises(text: str) -> List[WorkoutExercise]:
    """Extract exercises from workout text using simple pattern matching."""
    exercises = []
    lines = text.split("\n")
    
    # Keywords that indicate a line is NOT an exercise
    skip_words = {"rest", "round", "rounds", "warm", "warmup", "cool", "cooldown", 
                  "stretch", "minutes", "seconds", "reps", "sets", "notes", "title",
                  "workout", "hiit", "tabata", "circuit", "amrap", "for time",
                  "of", "between", "each", "every", "today", "the", "and", "with"}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip headers and markers
        if line.startswith("#"):
            continue
        
        # Skip lines that are entirely numbers or special chars
        if re.match(r"^[\d\.\:\-\s]+$", line):
            continue
        
        # Try to extract sets and reps
        sets = None
        reps = None
        duration = None
        weight = None
        
        # Look for patterns like "3x10" at the START of the line
        match = re.search(r"^(\d+)\s*x\s*(\d+)(?:\s+(.+))?$", line, re.IGNORECASE)
        if match:
            sets = int(match.group(1))
            reps = int(match.group(2))
            exercise_name = match.group(3).strip() if match.group(3) else ""
            if exercise_name:
                exercises.append(WorkoutExercise(
                    name=exercise_name,
                    sets=sets,
                    reps=reps,
                    duration_seconds=duration,
                    weight=weight,
                ))
            continue
        
        # Look for duration patterns at the END
        match = re.search(r"(.+?)\s+(\d+)\s*(?:seconds?|secs?)$", line, re.IGNORECASE)
        if match:
            exercise_name = match.group(1).strip()
            duration = int(match.group(2))
        else:
            match = re.search(r"(.+?)\s+(\d+)\s*(?:minutes?|mins?)$", line, re.IGNORECASE)
            if match:
                exercise_name = match.group(1).strip()
                duration = int(match.group(2)) * 60
            else:
                # Look for weight
                match = re.search(r"(.+?)\s+(\d+(?:\.\d+)?)\s*(lbs?|kg|pounds?|kilograms?)$", line, re.IGNORECASE)
                if match:
                    exercise_name = match.group(1).strip()
                    weight = match.group(2) + " " + match.group(3)
                else:
                    # Just a plain line, check if it has a number
                    match = re.search(r"(.+?)\s+(\d+)\s*$", line)
                    if match:
                        exercise_name = match.group(1).strip()
                    else:
                        exercise_name = line
        
        # Skip if the remaining name is too short or in skip words
        if not exercise_name or len(exercise_name) < 3:
            continue
        
        # Skip if the first word is in skip_words
        first_word = exercise_name.split()[0].lower().rstrip(':')
        if first_word in skip_words:
            continue
        
        # Skip lines that look like round markers
        if re.match(r"^\d+\s*(rounds?|reps?|sets?)\s*(for|time|of)?", exercise_name, re.IGNORECASE):
            continue
        
        exercises.append(WorkoutExercise(
            name=exercise_name,
            sets=sets,
            reps=reps,
            duration_seconds=duration,
            weight=weight,
        ))
    
    return exercises


def _extract_rounds(text: str) -> List[WorkoutRound]:
    """Extract rounds from workout text."""
    rounds = []
    lines = text.split("\n")
    
    current_round = None
    round_number = 0
    
    for line in lines:
        line = line.strip()
        
        # Look for round markers
        round_match = re.search(r"(?:round|rd|heat)\s*(\d+)", line, re.IGNORECASE)
        if round_match:
            if current_round:
                rounds.append(current_round)
            round_number = int(round_match.group(1))
            current_round = WorkoutRound(
                round_number=round_number,
                exercises=[],
            )
            continue
        
        # Also look for numbered lists like "1." or "1)"
        list_match = re.search(r"^(\d+)[\.\)]\s*(.+)", line)
        if list_match and current_round:
            # This might be an exercise in the current round
            pass
        
        # If no round in progress and we see exercises, create a default round
        if not current_round and line and not line.startswith("#"):
            # Try to parse as exercise
            exercise_name = re.sub(r"[\d\sx\-:]+.*$", "", line).strip()
            if exercise_name and len(exercise_name) > 2:
                if not rounds:
                    round_number = 1
                    current_round = WorkoutRound(
                        round_number=round_number,
                        exercises=[],
                    )
    
    if current_round:
        rounds.append(current_round)
    
    # If no rounds found, create a single round with all exercises
    if not rounds:
        exercises = _extract_exercises(text)
        if exercises:
            rounds.append(WorkoutRound(
                round_number=1,
                exercises=exercises,
            ))
    
    return rounds


def _extract_title(text: str) -> Optional[str]:
    """Extract workout title from text."""
    lines = text.split("\n")
    
    # First non-empty line might be the title
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and len(line) > 2:
            # Skip lines that look like exercise descriptions
            if not re.search(r"\d+\s*(?:x|sets?|reps?|seconds?|minutes?)", line, re.IGNORECASE):
                return line[:100]  # Limit title length
    
    return None


def _estimate_duration(exercises: List[WorkoutExercise]) -> Optional[int]:
    """Estimate total workout duration in minutes."""
    total_seconds = 0
    
    for exercise in exercises:
        if exercise.duration_seconds:
            total_seconds += exercise.duration_seconds
        elif exercise.sets and exercise.reps:
            # Estimate ~3 seconds per rep
            total_seconds += exercise.sets * exercise.reps * 3
        elif exercise.sets:
            # Estimate ~45 seconds per set
            total_seconds += exercise.sets * 45
    
    if total_seconds > 0:
        return max(1, total_seconds // 60)
    
    return None


def _parse_workout_text(text: str) -> WorkoutParseResponse:
    """Parse workout text into structured workout data."""
    try:
        # Extract components
        title = _extract_title(text)
        equipment = _extract_equipment(text)
        exercises = _extract_exercises(text)
        rounds = _extract_rounds(text)
        
        # If we have exercises but no rounds, create one round
        if exercises and not rounds:
            rounds = [WorkoutRound(round_number=1, exercises=exercises)]
        
        # Estimate duration
        duration = _estimate_duration(exercises)
        
        return WorkoutParseResponse(
            success=True,
            title=title,
            rounds=rounds,
            exercises=exercises,
            total_duration_minutes=duration,
            equipment=equipment,
            raw_text=text[:500],  # Keep first 500 chars for reference
        )
    except Exception as e:
        logger.error(f"Workout parsing failed: {e}")
        return WorkoutParseResponse(
            success=False,
            raw_text=text[:500],
            error=f"Failed to parse workout text: {str(e)}",
        )


# =============================================================================
# API Endpoints
# =============================================================================


@router.post(
    "/instagram/preview",
    response_model=InstagramPreviewResponse,
    summary="Get Instagram oEmbed preview",
    description="Fetch Instagram post preview using oEmbed API. Returns embed HTML and metadata.",
)
async def get_instagram_preview(
    request: InstagramPreviewRequest,
    user_id: Optional[str] = Query(None, description="User identifier for rate limiting"),
) -> InstagramPreviewResponse:
    """
    Get Instagram post preview using oEmbed.
    
    - Validates the Instagram URL
    - Fetches oEmbed data from Meta Graph API
    - Returns embed HTML, author info, and thumbnail
    - Caches results for 1 hour
    - Rate limited to 10 requests per minute per user
    
    Graceful fallback: If oEmbed fails, returns success=False with
    message allowing user to manually enter workout text.
    """
    # Rate limiting - use user_id or IP as identifier
    rate_limit_id = user_id or "anonymous"
    
    if not _check_rate_limit(rate_limit_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
        )
    
    # Validate URL
    try:
        validated_url = _validate_instagram_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Fetch oEmbed data
    result = await _fetch_instagram_oembed(validated_url)
    
    if not result.get("success", True):
        return InstagramPreviewResponse(
            success=False,
            html=None,
            error=result.get("error", "Failed to fetch Instagram preview"),
        )
    
    return InstagramPreviewResponse(
        success=True,
        html=result.get("html"),
        author_name=result.get("author_name"),
        author_url=result.get("author_url"),
        thumbnail_url=result.get("thumbnail_url"),
        title=result.get("title"),
        provider_name=result.get("provider_name", "Instagram"),
        cached=result.get("cached", False),
    )


@router.post(
    "/workout/parse",
    response_model=WorkoutParseResponse,
    summary="Parse workout text",
    description="Parse user-provided workout text into structured workout data.",
)
async def parse_workout_text(
    request: WorkoutParseRequest,
    user_id: Optional[str] = Query(None, description="User identifier for rate limiting"),
) -> WorkoutParseResponse:
    """
    Parse workout text into structured data.
    
    - Extracts exercise names
    - Identifies sets, reps, duration, and weight
    - Detects equipment
    - Groups exercises into rounds
    - Estimates total duration
    
    This endpoint does NOT scrape Instagram - it only parses
    text that the user explicitly pastes into the app.
    """
    # Rate limiting
    rate_limit_id = user_id or "anonymous"
    
    if not _check_rate_limit(f"workout:{rate_limit_id}"):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
        )
    
    # Parse the workout text
    return _parse_workout_text(request.text)
