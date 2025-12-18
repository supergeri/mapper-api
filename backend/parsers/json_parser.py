"""
JSON Parser

Parses JSON files with support for:
- AmakaFlow native schema (re-imports)
- Flexible mapping for third-party formats
- Nested structure support
"""

import json
import logging
from typing import List, Dict, Any, Optional

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


class JSONParser(BaseParser):
    """Parser for JSON files"""

    def can_parse(self, file_info: FileInfo) -> bool:
        """Check if this parser can handle the file"""
        return file_info.extension.lower() == '.json'

    async def parse(self, content: bytes, file_info: FileInfo) -> ParseResult:
        """Parse JSON file and return normalized workout data"""
        self.errors = []
        self.warnings = []

        try:
            # Decode and parse JSON
            text = content.decode('utf-8')
            data = json.loads(text)

            result = ParseResult()

            # Detect format and parse
            if isinstance(data, list):
                # Array of workouts
                workouts = self._parse_workout_array(data)
                result.detected_format = 'json_array'
            elif isinstance(data, dict):
                # Single workout or structured format
                if self._is_amakaflow_format(data):
                    workouts = self._parse_amakaflow_format(data)
                    result.detected_format = 'amakaflow'
                elif 'workouts' in data:
                    workouts = self._parse_workout_array(data['workouts'])
                    result.detected_format = 'json_workouts_key'
                    if 'metadata' in data:
                        result.metadata = data['metadata']
                else:
                    workouts = [self._parse_single_workout(data)]
                    result.detected_format = 'json_single'
            else:
                return ParseResult(
                    success=False,
                    errors=["Invalid JSON structure - expected object or array"],
                    confidence=0
                )

            result.workouts = [w for w in workouts if w is not None]
            result.total_rows = len(result.workouts)

            # Detect patterns
            result.patterns = self.detect_patterns(result.workouts)

            # Calculate confidence
            result.confidence = self._calculate_confidence(result)

            result.errors = self.errors
            result.warnings = self.warnings
            result.success = len(self.errors) == 0

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return ParseResult(
                success=False,
                errors=[f"Invalid JSON: {str(e)}"],
                confidence=0
            )
        except Exception as e:
            logger.exception(f"Failed to parse JSON file: {e}")
            return ParseResult(
                success=False,
                errors=[f"Failed to parse JSON file: {str(e)}"],
                confidence=0
            )

    def _is_amakaflow_format(self, data: Dict[str, Any]) -> bool:
        """Check if data matches AmakaFlow native format"""
        # AmakaFlow format has 'blocks' with exercises
        if 'blocks' in data:
            blocks = data['blocks']
            if isinstance(blocks, list) and len(blocks) > 0:
                first_block = blocks[0]
                return 'exercises' in first_block or 'name' in first_block
        return False

    def _parse_amakaflow_format(self, data: Dict[str, Any]) -> List[ParsedWorkout]:
        """Parse AmakaFlow native format"""
        title = data.get('title', data.get('name', 'Imported Workout'))
        description = data.get('description', '')
        blocks = data.get('blocks', [])

        exercises = []
        order = 1

        for block in blocks:
            block_name = block.get('name', '')
            block_exercises = block.get('exercises', [])

            for ex in block_exercises:
                exercise = self._parse_amakaflow_exercise(ex, order, block_name)
                if exercise:
                    exercises.append(exercise)
                    order += 1

        workout = ParsedWorkout(
            name=title,
            description=description,
            exercises=exercises,
            metadata=data.get('metadata', {})
        )

        return [workout]

    def _parse_amakaflow_exercise(
        self,
        ex: Dict[str, Any],
        order: int,
        block_name: str = ''
    ) -> Optional[ParsedExercise]:
        """Parse exercise from AmakaFlow format"""
        name = ex.get('name', ex.get('exercise', ''))
        if not name:
            return None

        # Handle sets - could be a list or a number
        sets_data = ex.get('sets', [])
        if isinstance(sets_data, list):
            sets = len(sets_data) if sets_data else 1
            # Get reps and weight from first set
            if sets_data:
                first_set = sets_data[0]
                reps = str(first_set.get('reps', first_set.get('targetReps', '1')))
                weight = first_set.get('weight', first_set.get('targetWeight'))
            else:
                reps = str(ex.get('reps', '1'))
                weight = ex.get('weight')
        else:
            sets = int(sets_data) if sets_data else 1
            reps = str(ex.get('reps', '1'))
            weight = ex.get('weight')

        # Parse reps and weight
        reps_str, reps_flags = self.parse_reps(str(reps))
        weight_str, weight_unit, weight_flags = self.parse_weight(str(weight) if weight else '')

        flags = list(set(reps_flags + weight_flags))

        return ParsedExercise(
            raw_name=name,
            order=str(order),
            sets=sets,
            reps=reps_str,
            weight=weight_str,
            weight_unit=weight_unit or ex.get('weightUnit'),
            rpe=ex.get('rpe'),
            notes=ex.get('notes'),
            rest_seconds=ex.get('rest', ex.get('restSeconds')),
            tempo=ex.get('tempo'),
            flags=flags,
        )

    def _parse_workout_array(self, data: List[Any]) -> List[ParsedWorkout]:
        """Parse array of workouts"""
        workouts = []

        for item in data:
            if isinstance(item, dict):
                workout = self._parse_single_workout(item)
                if workout:
                    workouts.append(workout)

        return workouts

    def _parse_single_workout(self, data: Dict[str, Any]) -> Optional[ParsedWorkout]:
        """Parse a single workout object"""
        # Try to find workout name
        name = (
            data.get('name') or
            data.get('title') or
            data.get('workout_name') or
            data.get('workoutName') or
            'Imported Workout'
        )

        # Try to find exercises
        exercises_data = (
            data.get('exercises') or
            data.get('movements') or
            data.get('lifts') or
            []
        )

        # If no exercises array, check for blocks (AmakaFlow format)
        if not exercises_data and 'blocks' in data:
            return self._parse_amakaflow_format(data)[0] if self._parse_amakaflow_format(data) else None

        exercises = []
        for idx, ex in enumerate(exercises_data):
            exercise = self._parse_generic_exercise(ex, idx + 1)
            if exercise:
                exercises.append(exercise)

        if not exercises:
            self.add_warning(f"No exercises found in workout '{name}'")
            return None

        return ParsedWorkout(
            name=name,
            date=data.get('date'),
            week=data.get('week'),
            day=data.get('day'),
            description=data.get('description', data.get('notes')),
            exercises=exercises,
            metadata={k: v for k, v in data.items() if k not in ['name', 'title', 'exercises', 'movements', 'lifts', 'blocks']}
        )

    def _parse_generic_exercise(self, ex: Any, order: int) -> Optional[ParsedExercise]:
        """Parse exercise from generic JSON format"""
        if isinstance(ex, str):
            # Just an exercise name
            return ParsedExercise(
                raw_name=ex,
                order=str(order),
                sets=1,
                reps="1"
            )

        if not isinstance(ex, dict):
            return None

        # Try various field names
        name = (
            ex.get('name') or
            ex.get('exercise') or
            ex.get('exercise_name') or
            ex.get('exerciseName') or
            ex.get('movement') or
            ''
        )

        if not name:
            return None

        # Get sets
        sets = ex.get('sets', ex.get('setCount', 1))
        if isinstance(sets, list):
            sets = len(sets)

        # Get reps
        reps = ex.get('reps', ex.get('repetitions', ex.get('rep', '1')))

        # Get weight
        weight = ex.get('weight', ex.get('load'))

        # Parse values
        reps_str, reps_flags = self.parse_reps(str(reps))
        weight_str, weight_unit, weight_flags = self.parse_weight(str(weight) if weight else '')

        flags = list(set(reps_flags + weight_flags))

        return ParsedExercise(
            raw_name=str(name),
            order=str(order),
            sets=int(sets) if isinstance(sets, (int, float)) else 1,
            reps=reps_str,
            weight=weight_str,
            weight_unit=weight_unit or ex.get('weightUnit', ex.get('weight_unit')),
            rpe=ex.get('rpe'),
            notes=ex.get('notes', ex.get('note')),
            rest_seconds=ex.get('rest', ex.get('restSeconds', ex.get('rest_seconds'))),
            tempo=ex.get('tempo'),
            flags=flags,
        )

    def _calculate_confidence(self, result: ParseResult) -> float:
        """Calculate parsing confidence"""
        if not result.workouts:
            return 0

        confidence = 50

        # Bonus for AmakaFlow format
        if result.detected_format == 'amakaflow':
            confidence += 30

        # Bonus for having exercises
        total_exercises = sum(len(w.exercises) for w in result.workouts)
        if total_exercises > 0:
            confidence += 10

        # Bonus for having weight data
        has_weight = any(
            e.weight for w in result.workouts for e in w.exercises
        )
        if has_weight:
            confidence += 5

        # Bonus for having reps data
        has_reps = any(
            e.reps != "1" for w in result.workouts for e in w.exercises
        )
        if has_reps:
            confidence += 5

        return min(confidence, 100)
