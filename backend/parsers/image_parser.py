"""
Image Parser

Part of AMA-423: Add AIRequestContext to All AI Call Sites for Full Observability

Parses workout images using OCR and Vision AI:
- Workout screenshots (gym whiteboards, program PDFs)
- Infographics from Instagram/Pinterest
- App screenshots from other fitness apps
- Handwritten workout programs

Routes to workout-ingestor-api for processing.
"""

import base64
import asyncio
import logging
import tempfile
import os
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
import httpx

# Import AIRequestContext for observability (AMA-423)
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.ai_context import AIRequestContext

logger = logging.getLogger(__name__)

# Workout ingestor API URL
INGESTOR_API_URL = os.getenv("INGESTOR_API_URL", "http://workout-ingestor:8004")

# Supported image formats
SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.webp', '.heic', '.gif'}


@dataclass
class ImageMetadata:
    """Metadata extracted from an image"""
    image_id: str
    filename: str
    size_bytes: int
    format: str
    width: Optional[int] = None
    height: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "format": self.format,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class ImageParseResult:
    """Result of parsing a single image"""
    image_id: str
    success: bool
    confidence: int  # 0-100

    # Parsed workout data
    title: Optional[str] = None
    exercises: List[Dict[str, Any]] = field(default_factory=list)
    blocks: List[Dict[str, Any]] = field(default_factory=list)

    # Raw data
    raw_workout: Optional[Dict[str, Any]] = None
    ocr_text: Optional[str] = None

    # Extraction metadata
    extraction_method: str = "vision"  # "vision" | "ocr"
    model_used: Optional[str] = None

    # Flagged items for review
    flagged_items: List[Dict[str, Any]] = field(default_factory=list)

    # Error info
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "success": self.success,
            "confidence": self.confidence,
            "title": self.title,
            "exercises": self.exercises,
            "blocks": self.blocks,
            "raw_workout": self.raw_workout,
            "ocr_text": self.ocr_text,
            "extraction_method": self.extraction_method,
            "model_used": self.model_used,
            "flagged_items": self.flagged_items,
            "error": self.error,
        }


class ImageParser:
    """Parser for workout images using OCR and Vision AI"""

    @classmethod
    def is_supported_format(cls, filename: str) -> bool:
        """Check if the file format is supported"""
        if not filename:
            return False
        ext = os.path.splitext(filename.lower())[1]
        return ext in SUPPORTED_FORMATS

    @classmethod
    async def parse_image(
        cls,
        image_data: bytes,
        filename: str,
        mode: Literal["vision", "ocr", "auto"] = "vision",
        vision_provider: str = "openai",
        vision_model: Optional[str] = "gpt-4o-mini",
        context: Optional[AIRequestContext] = None,
    ) -> ImageParseResult:
        """
        Parse a single image to extract workout data.

        Args:
            image_data: Raw image bytes
            filename: Original filename
            mode: Extraction mode
                - "vision": Use Vision AI (more accurate, costs more)
                - "ocr": Use OCR only (faster, free)
                - "auto": Try vision, fall back to OCR
            vision_provider: Vision provider ("openai" or "anthropic")
            vision_model: Model to use (e.g., "gpt-4o-mini", "gpt-4o")
            context: AI request context for observability (AMA-423)

        Returns:
            ImageParseResult with extracted workout data
        """
        image_id = f"img_{hash(image_data) % 10**8:08d}"

        # Validate format
        if not cls.is_supported_format(filename):
            ext = os.path.splitext(filename.lower())[1] if filename else "unknown"
            return ImageParseResult(
                image_id=image_id,
                success=False,
                confidence=0,
                error=f"Unsupported image format: {ext}. Supported: {', '.join(SUPPORTED_FORMATS)}"
            )

        try:
            if mode == "vision" or mode == "auto":
                result = await cls._parse_with_vision(
                    image_data, filename, image_id,
                    vision_provider, vision_model, context
                )
                if result.success or mode == "vision":
                    return result
                # Fall through to OCR if auto mode and vision failed

            if mode == "ocr" or mode == "auto":
                return await cls._parse_with_ocr(image_data, filename, image_id, context)

            return ImageParseResult(
                image_id=image_id,
                success=False,
                confidence=0,
                error=f"Unknown parsing mode: {mode}"
            )

        except Exception as e:
            logger.exception(f"Error parsing image {filename}: {e}")
            return ImageParseResult(
                image_id=image_id,
                success=False,
                confidence=0,
                error=str(e)
            )

    @classmethod
    async def _parse_with_vision(
        cls,
        image_data: bytes,
        filename: str,
        image_id: str,
        vision_provider: str,
        vision_model: Optional[str],
        context: Optional[AIRequestContext] = None,
    ) -> ImageParseResult:
        """Parse image using Vision AI via workout-ingestor-api"""

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                # Create multipart form data
                files = {
                    "file": (filename, image_data, cls._get_content_type(filename))
                }
                data = {
                    "vision_provider": vision_provider,
                }
                if vision_model:
                    data["vision_model"] = vision_model
                
                # Pass AI context metadata for observability (AMA-423)
                if context:
                    context_data = context.to_dict()
                    if context_data:
                        data["ai_context"] = context_data

                response = await client.post(
                    f"{INGESTOR_API_URL}/ingest/image_vision",
                    files=files,
                    data=data,
                )

                if response.status_code == 200:
                    result = response.json()
                    workout = result.get("workout", {})
                    metadata = result.get("metadata", {})

                    # Calculate confidence based on exercise count and completeness
                    confidence = cls._calculate_confidence(workout)

                    # Count exercises
                    exercise_count = 0
                    exercises = []
                    for block in workout.get("blocks", []):
                        block_exercises = block.get("exercises", [])
                        exercise_count += len(block_exercises)
                        exercises.extend(block_exercises)
                        for superset in block.get("supersets", []):
                            superset_exercises = superset.get("exercises", [])
                            exercise_count += len(superset_exercises)
                            exercises.extend(superset_exercises)

                    # Flag low-confidence items
                    flagged = cls._flag_low_confidence_items(workout)

                    return ImageParseResult(
                        image_id=image_id,
                        success=True,
                        confidence=confidence,
                        title=workout.get("title"),
                        exercises=exercises,
                        blocks=workout.get("blocks", []),
                        raw_workout=workout,
                        extraction_method="vision",
                        model_used=metadata.get("model", vision_model),
                        flagged_items=flagged,
                    )
                else:
                    error_text = response.text
                    return ImageParseResult(
                        image_id=image_id,
                        success=False,
                        confidence=0,
                        extraction_method="vision",
                        error=f"Vision API error ({response.status_code}): {error_text[:200]}"
                    )

            except httpx.ConnectError:
                return ImageParseResult(
                    image_id=image_id,
                    success=False,
                    confidence=0,
                    extraction_method="vision",
                    error="Could not connect to workout-ingestor service"
                )

    @classmethod
    async def _parse_with_ocr(
        cls,
        image_data: bytes,
        filename: str,
        image_id: str,
        context: Optional[AIRequestContext] = None,
    ) -> ImageParseResult:
        """Parse image using OCR via workout-ingestor-api"""

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                files = {
                    "file": (filename, image_data, cls._get_content_type(filename))
                }
                
                data = {}
                # Pass AI context metadata for observability (AMA-423)
                if context:
                    context_data = context.to_dict()
                    if context_data:
                        data["ai_context"] = context_data

                response = await client.post(
                    f"{INGESTOR_API_URL}/ingest/image",
                    files=files,
                    data=data if data else None,
                )

                if response.status_code == 200:
                    result = response.json()
                    workout = result.get("workout", {})

                    # OCR is generally less accurate
                    confidence = cls._calculate_confidence(workout)
                    # Reduce confidence for OCR (generally less reliable)
                    confidence = int(confidence * 0.8)

                    # Count exercises
                    exercises = []
                    for block in workout.get("blocks", []):
                        exercises.extend(block.get("exercises", []))
                        for superset in block.get("supersets", []):
                            exercises.extend(superset.get("exercises", []))

                    flagged = cls._flag_low_confidence_items(workout)

                    return ImageParseResult(
                        image_id=image_id,
                        success=True,
                        confidence=confidence,
                        title=workout.get("title"),
                        exercises=exercises,
                        blocks=workout.get("blocks", []),
                        raw_workout=workout,
                        extraction_method="ocr",
                        flagged_items=flagged,
                    )
                else:
                    return ImageParseResult(
                        image_id=image_id,
                        success=False,
                        confidence=0,
                        extraction_method="ocr",
                        error=f"OCR API error ({response.status_code}): {response.text[:200]}"
                    )

            except httpx.ConnectError:
                return ImageParseResult(
                    image_id=image_id,
                    success=False,
                    confidence=0,
                    extraction_method="ocr",
                    error="Could not connect to workout-ingestor service"
                )

    @classmethod
    def _calculate_confidence(cls, workout: Dict[str, Any]) -> int:
        """
        Calculate confidence score (0-100) based on workout completeness.

        Scoring:
        - Has exercises: +40
        - Has title: +10
        - Exercises have reps/sets: +30 (proportional)
        - Exercises have names > 3 chars: +20 (proportional)
        """
        if not workout:
            return 0

        score = 0

        # Collect all exercises
        exercises = []
        for block in workout.get("blocks", []):
            exercises.extend(block.get("exercises", []))
            for superset in block.get("supersets", []):
                exercises.extend(superset.get("exercises", []))

        if not exercises:
            return 10  # Has structure but no exercises

        # Has exercises
        score += 40

        # Has title
        if workout.get("title"):
            score += 10

        # Exercise completeness
        exercises_with_details = 0
        exercises_with_valid_names = 0

        for ex in exercises:
            # Check for reps/sets/duration
            has_details = any([
                ex.get("reps"),
                ex.get("reps_range"),
                ex.get("sets"),
                ex.get("duration_sec"),
                ex.get("distance_m"),
            ])
            if has_details:
                exercises_with_details += 1

            # Check for valid name (not garbled)
            name = ex.get("name", "")
            if name and len(name) > 3 and not cls._is_garbled_text(name):
                exercises_with_valid_names += 1

        # Proportional scoring
        if exercises:
            score += int(30 * exercises_with_details / len(exercises))
            score += int(20 * exercises_with_valid_names / len(exercises))

        return min(100, score)

    @classmethod
    def _flag_low_confidence_items(cls, workout: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flag exercises that need manual review"""
        flagged = []

        for block_idx, block in enumerate(workout.get("blocks", [])):
            for ex_idx, ex in enumerate(block.get("exercises", [])):
                issues = []

                name = ex.get("name", "")
                if not name:
                    issues.append("missing_name")
                elif len(name) <= 2:
                    issues.append("name_too_short")
                elif cls._is_garbled_text(name):
                    issues.append("garbled_name")

                # No reps/sets/duration
                if not any([
                    ex.get("reps"),
                    ex.get("reps_range"),
                    ex.get("sets"),
                    ex.get("duration_sec"),
                    ex.get("distance_m"),
                ]):
                    issues.append("missing_details")

                if issues:
                    flagged.append({
                        "block_index": block_idx,
                        "exercise_index": ex_idx,
                        "exercise_name": name,
                        "issues": issues,
                    })

        return flagged

    @classmethod
    def _is_garbled_text(cls, text: str) -> bool:
        """Check if text appears garbled (OCR errors)"""
        if not text:
            return False

        text = text.strip()

        # Too short with no letters
        if len(text) <= 2:
            letters = sum(1 for c in text if c.isalpha())
            return letters == 0

        # Count character types
        letters = sum(1 for c in text if c.isalpha())
        digits = sum(1 for c in text if c.isdigit())
        spaces = sum(1 for c in text if c.isspace())
        symbols = len(text) - letters - digits - spaces

        # If mostly symbols, likely garbled
        if len(text) >= 3:
            meaningful = letters + digits
            if meaningful == 0:
                return True
            if symbols > meaningful * 2:
                return True

        return False

    @classmethod
    def _get_content_type(cls, filename: str) -> str:
        """Get content type for file"""
        ext = os.path.splitext(filename.lower())[1]
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.heic': 'image/heic',
            '.gif': 'image/gif',
        }
        return content_types.get(ext, 'application/octet-stream')

    @classmethod
    async def parse_images_batch(
        cls,
        images: List[tuple],  # List of (image_data, filename)
        mode: Literal["vision", "ocr", "auto"] = "vision",
        vision_provider: str = "openai",
        vision_model: Optional[str] = "gpt-4o-mini",
        max_concurrent: int = 3,
        context: Optional[AIRequestContext] = None,
    ) -> List[ImageParseResult]:
        """
        Parse multiple images with concurrency limit.

        Args:
            images: List of (image_data, filename) tuples
            mode: Extraction mode
            vision_provider: Vision provider
            vision_model: Model to use
            max_concurrent: Maximum concurrent requests
            context: AI request context for observability (AMA-423)

        Returns:
            List of ImageParseResult in same order as input
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def parse_with_limit(image_data: bytes, filename: str) -> ImageParseResult:
            async with semaphore:
                return await cls.parse_image(
                    image_data, filename,
                    mode=mode,
                    vision_provider=vision_provider,
                    vision_model=vision_model,
                    context=context,
                )

        tasks = [parse_with_limit(data, name) for data, name in images]
        return await asyncio.gather(*tasks)


# Convenience functions
async def parse_image(
    image_data: bytes,
    filename: str,
    mode: Literal["vision", "ocr", "auto"] = "vision",
) -> ImageParseResult:
    """Parse a single workout image"""
    return await ImageParser.parse_image(image_data, filename, mode=mode)


async def parse_images_batch(
    images: List[tuple],
    mode: Literal["vision", "ocr", "auto"] = "vision",
    max_concurrent: int = 3,
) -> List[ImageParseResult]:
    """Parse multiple workout images"""
    return await ImageParser.parse_images_batch(images, mode=mode, max_concurrent=max_concurrent)


def is_supported_image(filename: str) -> bool:
    """Check if file is a supported image format"""
    return ImageParser.is_supported_format(filename)
