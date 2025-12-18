"""
CSV Parser

Parses CSV files with support for:
- Strong App exports
- Hevy exports
- FitNotes exports
- Generic auto-detection

Features:
- Delimiter detection (comma, semicolon, tab)
- Known schema templates
- Auto-detect columns by header names
"""

import io
import csv
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from .base import BaseParser
from .models import (
    ParseResult,
    ParsedWorkout,
    ParsedExercise,
    ColumnInfo,
    FileInfo,
    ExerciseFlag,
)

logger = logging.getLogger(__name__)


# Known CSV schemas
STRONG_APP_COLUMNS = {
    'date': 'Date',
    'workout_name': 'Workout Name',
    'exercise': 'Exercise Name',
    'set_order': 'Set Order',
    'weight': 'Weight',
    'weight_unit': 'Weight Unit',
    'reps': 'Reps',
    'rpe': 'RPE',
    'distance': 'Distance',
    'distance_unit': 'Distance Unit',
    'seconds': 'Seconds',
    'notes': 'Notes',
    'workout_notes': 'Workout Notes',
}

HEVY_COLUMNS = {
    'date': 'Date',
    'workout_name': 'Workout Name',
    'exercise': 'Exercise Name',
    'set_order': 'Set Order',
    'weight': 'Weight (kg)',
    'reps': 'Reps',
    'rpe': 'RPE',
    'notes': 'Notes',
}

FITNOTES_COLUMNS = {
    'date': 'Date',
    'exercise': 'Exercise',
    'category': 'Category',
    'weight': 'Weight',
    'weight_unit': 'Weight Unit',
    'reps': 'Reps',
    'notes': 'Comment',
}


class CSVParser(BaseParser):
    """Parser for CSV files"""

    def can_parse(self, file_info: FileInfo) -> bool:
        """Check if this parser can handle the file"""
        return file_info.extension.lower() == '.csv'

    async def parse(self, content: bytes, file_info: FileInfo) -> ParseResult:
        """Parse CSV file and return normalized workout data"""
        self.errors = []
        self.warnings = []

        try:
            # Decode content
            text = self._decode_content(content)

            # Detect delimiter
            delimiter = self._detect_delimiter(text)

            # Parse CSV
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            headers = reader.fieldnames or []

            if not headers:
                return ParseResult(
                    success=False,
                    errors=["No headers found in CSV file"],
                    confidence=0
                )

            # Detect format
            detected_format, column_mapping = self._detect_format(headers)

            result = ParseResult(
                detected_format=detected_format,
                columns=self._create_column_info(headers, column_mapping),
            )

            # Parse rows
            rows = list(reader)
            result.total_rows = len(rows)

            if detected_format in ['strong_app', 'hevy', 'fitnotes']:
                workouts = self._parse_known_format(rows, column_mapping, detected_format)
            else:
                workouts = self._parse_generic_format(rows, column_mapping, headers)

            result.workouts = workouts

            # Detect patterns
            result.patterns = self.detect_patterns(workouts)

            # Calculate confidence
            result.confidence = self._calculate_confidence(result, detected_format)

            result.errors = self.errors
            result.warnings = self.warnings
            result.success = len(self.errors) == 0

            return result

        except Exception as e:
            logger.exception(f"Failed to parse CSV file: {e}")
            return ParseResult(
                success=False,
                errors=[f"Failed to parse CSV file: {str(e)}"],
                confidence=0
            )

    def _decode_content(self, content: bytes) -> str:
        """Decode bytes to string, trying multiple encodings"""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue

        # Fallback with error replacement
        return content.decode('utf-8', errors='replace')

    def _detect_delimiter(self, text: str) -> str:
        """Detect CSV delimiter"""
        # Get first few lines
        lines = text.split('\n')[:5]
        sample = '\n'.join(lines)

        # Count occurrences of common delimiters
        delimiters = {
            ',': sample.count(','),
            ';': sample.count(';'),
            '\t': sample.count('\t'),
        }

        # Return the most common one
        return max(delimiters, key=delimiters.get)

    def _detect_format(self, headers: List[str]) -> Tuple[str, Dict[str, str]]:
        """Detect CSV format based on headers"""
        headers_lower = [h.lower().strip() for h in headers]
        headers_map = {h.lower().strip(): h for h in headers}

        # Check for Strong App
        strong_score = sum(1 for v in STRONG_APP_COLUMNS.values() if v.lower() in headers_lower)
        if strong_score >= 4:
            mapping = {k: headers_map.get(v.lower(), v) for k, v in STRONG_APP_COLUMNS.items()}
            return 'strong_app', mapping

        # Check for Hevy
        hevy_score = sum(1 for v in HEVY_COLUMNS.values() if v.lower() in headers_lower)
        if hevy_score >= 4:
            mapping = {k: headers_map.get(v.lower(), v) for k, v in HEVY_COLUMNS.items()}
            return 'hevy', mapping

        # Check for FitNotes
        fitnotes_score = sum(1 for v in FITNOTES_COLUMNS.values() if v.lower() in headers_lower)
        if fitnotes_score >= 3:
            mapping = {k: headers_map.get(v.lower(), v) for k, v in FITNOTES_COLUMNS.items()}
            return 'fitnotes', mapping

        # Generic - try to map columns by common names
        mapping = self._auto_map_columns(headers)
        return 'generic', mapping

    def _auto_map_columns(self, headers: List[str]) -> Dict[str, str]:
        """Auto-map columns for generic CSV"""
        mapping = {}
        headers_lower = {h.lower(): h for h in headers}

        # Exercise column
        for name in ['exercise', 'exercise name', 'movement', 'lift', 'name']:
            if name in headers_lower:
                mapping['exercise'] = headers_lower[name]
                break

        # Date column
        for name in ['date', 'datetime', 'workout date']:
            if name in headers_lower:
                mapping['date'] = headers_lower[name]
                break

        # Workout name
        for name in ['workout', 'workout name', 'routine', 'session']:
            if name in headers_lower:
                mapping['workout_name'] = headers_lower[name]
                break

        # Sets
        for name in ['sets', 'set', 'set order', 'set number']:
            if name in headers_lower:
                mapping['sets'] = headers_lower[name]
                break

        # Reps
        for name in ['reps', 'rep', 'repetitions', 'reps performed']:
            if name in headers_lower:
                mapping['reps'] = headers_lower[name]
                break

        # Weight
        for name in ['weight', 'load', 'weight (kg)', 'weight (lbs)', 'kg', 'lbs']:
            if name in headers_lower:
                mapping['weight'] = headers_lower[name]
                break

        # Weight unit
        for name in ['weight unit', 'unit', 'units']:
            if name in headers_lower:
                mapping['weight_unit'] = headers_lower[name]
                break

        # Notes
        for name in ['notes', 'note', 'comments', 'comment']:
            if name in headers_lower:
                mapping['notes'] = headers_lower[name]
                break

        # RPE
        for name in ['rpe', 'rir']:
            if name in headers_lower:
                mapping['rpe'] = headers_lower[name]
                break

        return mapping

    def _create_column_info(self, headers: List[str], mapping: Dict[str, str]) -> List[ColumnInfo]:
        """Create column info objects"""
        reverse_mapping = {v: k for k, v in mapping.items()}

        columns = []
        for idx, header in enumerate(headers):
            col = ColumnInfo(
                index=idx,
                name=header,
                detected_type=reverse_mapping.get(header),
                confidence=80 if header in reverse_mapping else 0,
            )
            columns.append(col)

        return columns

    def _parse_known_format(
        self,
        rows: List[Dict[str, str]],
        mapping: Dict[str, str],
        format_type: str
    ) -> List[ParsedWorkout]:
        """Parse rows using a known format schema"""
        workouts_dict: Dict[str, ParsedWorkout] = {}

        for row in rows:
            # Get workout identifier
            date = row.get(mapping.get('date', ''), '').strip()
            workout_name = row.get(mapping.get('workout_name', ''), '').strip()

            if workout_name and date:
                workout_key = f"{date}_{workout_name}"
            elif workout_name:
                workout_key = workout_name
            elif date:
                workout_key = date
            else:
                # No date or workout_name - use default
                workout_key = "Imported Workout"

            # Get or create workout
            if workout_key not in workouts_dict:
                workouts_dict[workout_key] = ParsedWorkout(
                    name=workout_name or (f"Workout on {date}" if date else "Imported Workout"),
                    date=date if date else None,
                    metadata={'format': format_type}
                )

            workout = workouts_dict[workout_key]

            # Parse exercise
            exercise_name = row.get(mapping.get('exercise', ''), '').strip()
            if not exercise_name:
                continue

            # Get values
            reps_val = row.get(mapping.get('reps', ''), '').strip()
            weight_val = row.get(mapping.get('weight', ''), '').strip()
            weight_unit_val = row.get(mapping.get('weight_unit', ''), '').strip()
            rpe_val = row.get(mapping.get('rpe', ''), '').strip()
            notes_val = row.get(mapping.get('notes', ''), '').strip()
            set_order = row.get(mapping.get('set_order', ''), '').strip()

            # Parse reps and flags
            reps_str, reps_flags = self.parse_reps(reps_val or "1")

            # Parse weight
            weight_str, detected_unit, weight_flags = self.parse_weight(weight_val)

            # Determine unit
            unit = None
            if weight_unit_val:
                unit = 'kg' if 'kg' in weight_unit_val.lower() else 'lbs'
            elif detected_unit:
                unit = detected_unit

            # Parse RPE
            rpe = None
            if rpe_val:
                try:
                    rpe = float(rpe_val)
                except ValueError:
                    pass

            # Combine flags
            flags = list(set(reps_flags + weight_flags))

            # For Strong App format, each row is a set, so we group by exercise
            # Check if exercise already exists in workout
            existing_exercise = next(
                (e for e in workout.exercises if e.raw_name == exercise_name),
                None
            )

            if existing_exercise and format_type == 'strong_app':
                # Increment sets count
                existing_exercise.sets += 1
                # Keep the latest reps (or could average them)
                existing_exercise.reps = reps_str
                if weight_str:
                    existing_exercise.weight = weight_str
                if unit:
                    existing_exercise.weight_unit = unit
            else:
                exercise = ParsedExercise(
                    raw_name=exercise_name,
                    order=str(len(workout.exercises) + 1),
                    sets=1,
                    reps=reps_str,
                    weight=weight_str,
                    weight_unit=unit,
                    rpe=rpe,
                    notes=notes_val if notes_val else None,
                    flags=flags,
                )
                workout.exercises.append(exercise)

        return list(workouts_dict.values())

    def _parse_generic_format(
        self,
        rows: List[Dict[str, str]],
        mapping: Dict[str, str],
        headers: List[str]
    ) -> List[ParsedWorkout]:
        """Parse rows using generic column detection"""
        if 'exercise' not in mapping:
            self.add_warning("Could not detect exercise column")
            return []

        workouts_dict: Dict[str, ParsedWorkout] = {}

        for row in rows:
            # Get workout identifier
            date = row.get(mapping.get('date', ''), '').strip()
            workout_name = row.get(mapping.get('workout_name', ''), 'Workout').strip()

            workout_key = f"{date}_{workout_name}" if date else workout_name

            # Get or create workout
            if workout_key not in workouts_dict:
                workouts_dict[workout_key] = ParsedWorkout(
                    name=workout_name,
                    date=date if date else None,
                    metadata={'format': 'generic'}
                )

            workout = workouts_dict[workout_key]

            # Parse exercise
            exercise_name = row.get(mapping['exercise'], '').strip()
            if not exercise_name:
                continue

            exercise_name = self.normalize_exercise_name(exercise_name)

            # Get values with defaults
            sets_val = row.get(mapping.get('sets', ''), '1').strip() or '1'
            reps_val = row.get(mapping.get('reps', ''), '1').strip() or '1'
            weight_val = row.get(mapping.get('weight', ''), '').strip()
            notes_val = row.get(mapping.get('notes', ''), '').strip()
            rpe_val = row.get(mapping.get('rpe', ''), '').strip()

            # Parse values
            reps_str, reps_flags = self.parse_reps(reps_val)
            weight_str, weight_unit, weight_flags = self.parse_weight(weight_val)

            # Parse RPE
            rpe = None
            if rpe_val:
                try:
                    rpe = float(rpe_val)
                except ValueError:
                    pass

            flags = list(set(reps_flags + weight_flags))

            # Parse sets
            try:
                sets = int(sets_val)
            except ValueError:
                sets = 1

            exercise = ParsedExercise(
                raw_name=exercise_name,
                order=str(len(workout.exercises) + 1),
                sets=sets,
                reps=reps_str,
                weight=weight_str,
                weight_unit=weight_unit,
                rpe=rpe,
                notes=notes_val if notes_val else None,
                flags=flags,
            )
            workout.exercises.append(exercise)

        return list(workouts_dict.values())

    def _calculate_confidence(self, result: ParseResult, detected_format: str) -> float:
        """Calculate parsing confidence"""
        if not result.workouts:
            return 0

        confidence = 40

        # Bonus for known format
        if detected_format in ['strong_app', 'hevy', 'fitnotes']:
            confidence += 30

        # Bonus for finding exercise column
        if any(c.detected_type == 'exercise' for c in result.columns):
            confidence += 15

        # Bonus for other mapped columns
        mapped_types = [c.detected_type for c in result.columns if c.detected_type]
        if 'reps' in mapped_types:
            confidence += 5
        if 'weight' in mapped_types:
            confidence += 5
        if 'date' in mapped_types:
            confidence += 5

        return min(confidence, 100)
