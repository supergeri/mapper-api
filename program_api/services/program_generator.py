"""
AI-powered program generator service.

Part of AMA-462: Implement ProgramGenerator Service

This service orchestrates the hybrid template-guided LLM approach:
1. Template Selection - Match goal + experience + sessions
2. Periodization Calculation - Calculate intensity/volume per week
3. LLM Exercise Selection - Select personalized exercises
4. Validation - Ensure safety constraints are met
5. Persistence - Save to database
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from typing import Dict, List, Optional
from uuid import uuid4

from application.ports import ExerciseRepository, ProgramRepository, TemplateRepository
from models.generation import GenerateProgramRequest, GenerateProgramResponse
from models.program import (
    ExperienceLevel,
    ProgramGoal,
    ProgramStatus,
    ProgramWeek,
    ProgramWorkout,
    TrainingProgram,
)
from services.exercise_selector import ExerciseSelector, SlotRequirements
from services.llm import OpenAIExerciseSelector, ExerciseSelectionRequest
from services.periodization import PeriodizationModel, PeriodizationService, WeekParameters
from services.program_validator import ProgramValidator, ValidationSeverity
from services.template_selector import TemplateSelector

logger = logging.getLogger(__name__)


class ProgramGenerationError(Exception):
    """Error during program generation."""

    pass


class ProgramGenerator:
    """
    Service for generating training programs using AI.

    This service orchestrates:
    - Template selection for workout structure
    - Periodization planning for progression
    - LLM-powered exercise selection
    - Validation for safety and quality
    - Persistence to database
    """

    def __init__(
        self,
        program_repo: ProgramRepository,
        template_repo: TemplateRepository,
        exercise_repo: ExerciseRepository,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        """
        Initialize the program generator.

        Args:
            program_repo: Repository for program persistence
            template_repo: Repository for template access
            exercise_repo: Repository for exercise data
            openai_api_key: OpenAI API key for GPT models
            anthropic_api_key: Anthropic API key for Claude models (future use)
        """
        self._program_repo = program_repo
        self._template_repo = template_repo
        self._exercise_repo = exercise_repo
        self._openai_key = openai_api_key
        self._anthropic_key = anthropic_api_key

        # Initialize sub-services
        self._periodization = PeriodizationService()
        self._template_selector = TemplateSelector(template_repo)
        self._validator = ProgramValidator()

        # Initialize exercise selector for intelligent fallback
        self._db_exercise_selector = ExerciseSelector(exercise_repo)

        # Initialize LLM selector if API key provided
        self._exercise_selector: Optional[OpenAIExerciseSelector] = None
        if openai_api_key:
            self._exercise_selector = OpenAIExerciseSelector(api_key=openai_api_key)

        # Thread pool for running sync DB operations from async context
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="program_gen_")

    async def generate(
        self,
        request: GenerateProgramRequest,
        user_id: str,
    ) -> GenerateProgramResponse:
        """
        Generate a training program based on user preferences.

        Flow:
        1. Select best matching template (or use default structure)
        2. Plan periodization for each week
        3. For each workout, select exercises via LLM
        4. Validate complete program
        5. Persist to database
        6. Return response with metadata

        Args:
            request: Generation parameters
            user_id: The user's ID

        Returns:
            Generated program with metadata

        Raises:
            ProgramGenerationError: If generation fails
        """
        logger.info(
            f"Generating program for user {user_id}: "
            f"goal={request.goal}, duration={request.duration_weeks}w, "
            f"sessions={request.sessions_per_week}/w"
        )

        start_time = datetime.utcnow()
        suggestions: List[str] = []

        try:
            # Step 1: Select template
            template_match = await self._template_selector.select_best_template(
                goal=request.goal,
                experience_level=request.experience_level,
                sessions_per_week=request.sessions_per_week,
                duration_weeks=request.duration_weeks,
            )

            if template_match:
                structure = template_match.template.get("structure", {})
                template_id = template_match.template.get("id")
                suggestions.append(
                    f"Using template: {template_match.template.get('name')}"
                )
                # Increment usage count (run in thread pool to avoid blocking)
                await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    self._template_repo.increment_usage_count,
                    template_id
                )
            else:
                # Use default structure
                structure = await self._template_selector.get_default_structure(
                    goal=request.goal,
                    experience_level=request.experience_level,
                    sessions_per_week=request.sessions_per_week,
                    duration_weeks=request.duration_weeks,
                )
                template_id = None
                suggestions.append("Using default workout structure")

            # Step 2: Select periodization model and plan progression
            periodization_model = self._periodization.select_periodization_model(
                goal=request.goal,
                experience_level=request.experience_level,
                duration_weeks=request.duration_weeks,
            )

            week_params = self._periodization.plan_progression(
                duration_weeks=request.duration_weeks,
                goal=request.goal,
                experience_level=request.experience_level,
                model=periodization_model,
            )

            suggestions.append(f"Using {periodization_model.value} periodization")

            # Step 3: Generate weeks with workouts
            weeks_data = await self._generate_weeks(
                request=request,
                structure=structure,
                week_params=week_params,
            )

            # Step 4: Validate program
            validation = self._validator.validate_program(
                program_data={"weeks": weeks_data},
                available_equipment=request.equipment_available,
                experience_level=request.experience_level,
                limitations=request.limitations,
            )

            if not validation.is_valid:
                error_messages = [i.message for i in validation.errors]
                raise ProgramGenerationError(
                    f"Generated program failed validation: {'; '.join(error_messages)}"
                )

            # Add validation warnings as suggestions
            for issue in validation.warnings:
                suggestions.append(f"Note: {issue.message}")

            # Step 5: Create and persist program
            program_id = str(uuid4())
            now = datetime.utcnow()

            program_create_data = {
                "id": program_id,
                "user_id": user_id,
                "name": self._generate_program_name(request),
                "description": self._generate_program_description(request),
                "goal": request.goal.value if hasattr(request.goal, "value") else str(request.goal),
                "periodization_model": periodization_model.value,
                "duration_weeks": request.duration_weeks,
                "sessions_per_week": request.sessions_per_week,
                "experience_level": request.experience_level.value if hasattr(request.experience_level, "value") else str(request.experience_level),
                "equipment_available": request.equipment_available,
                "status": ProgramStatus.DRAFT.value,
                "generation_metadata": {
                    "template_id": template_id,
                    "periodization_model": periodization_model.value,
                    "generated_at": now.isoformat(),
                    "llm_used": self._exercise_selector is not None,
                },
            }

            # Persist program (run in thread pool to avoid blocking)
            created_program = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._program_repo.create,
                program_create_data
            )
            logger.info(f"Created program {program_id}")

            # Persist weeks and workouts
            program_weeks = []
            for week_data in weeks_data:
                week_create_data = {
                    "week_number": week_data["week_number"],
                    "focus": week_data.get("focus"),
                    "intensity_percentage": int(week_data.get("intensity_percent", 0.7) * 100),
                    "volume_modifier": week_data.get("volume_modifier", 1.0),
                    "is_deload": week_data.get("is_deload", False),
                    "notes": week_data.get("notes"),
                }

                created_week = await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    partial(self._program_repo.create_week, program_id, week_create_data)
                )
                week_id = created_week["id"]

                # Persist workouts
                workouts = []
                for idx, workout_data in enumerate(week_data.get("workouts", [])):
                    workout_create_data = {
                        "day_of_week": workout_data.get("day_of_week", idx + 1),
                        "name": workout_data.get("name", f"Workout {idx + 1}"),
                        "workout_type": workout_data.get("workout_type", "full_body"),
                        "target_duration_minutes": workout_data.get("target_duration_minutes", 60),
                        "exercises": workout_data.get("exercises", []),
                        "notes": workout_data.get("notes"),
                        "sort_order": idx,
                    }

                    created_workout = await asyncio.get_event_loop().run_in_executor(
                        self._executor,
                        partial(self._program_repo.create_workout, week_id, workout_create_data)
                    )
                    workouts.append(
                        ProgramWorkout(
                            id=created_workout["id"],
                            program_week_id=week_id,
                            day_of_week=workout_create_data["day_of_week"],
                            name=workout_create_data["name"],
                            description=workout_create_data.get("notes"),
                            workout_id=None,
                            order_index=idx,
                            created_at=now,
                            updated_at=now,
                        )
                    )

                program_weeks.append(
                    ProgramWeek(
                        id=week_id,
                        program_id=program_id,
                        week_number=week_create_data["week_number"],
                        name=f"Week {week_create_data['week_number']}",
                        description=week_create_data.get("notes"),
                        deload=week_create_data["is_deload"],
                        workouts=workouts,
                        created_at=now,
                        updated_at=now,
                    )
                )

            # Build response
            training_program = TrainingProgram(
                id=program_id,
                user_id=user_id,
                name=program_create_data["name"],
                description=program_create_data["description"],
                goal=request.goal,
                experience_level=request.experience_level,
                duration_weeks=request.duration_weeks,
                sessions_per_week=request.sessions_per_week,
                status=ProgramStatus.DRAFT,
                equipment_available=request.equipment_available,
                weeks=program_weeks,
                created_at=now,
                updated_at=now,
            )

            generation_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Program generation completed in {generation_time:.2f}s")

            return GenerateProgramResponse(
                program=training_program,
                generation_metadata={
                    "template_id": template_id,
                    "periodization_model": periodization_model.value,
                    "generation_time_seconds": round(generation_time, 2),
                    "llm_used": self._exercise_selector is not None,
                    "validation_passed": validation.is_valid,
                    "warning_count": len(validation.warnings),
                },
                suggestions=suggestions,
            )

        except Exception as e:
            logger.error(f"Program generation failed: {e}")
            raise ProgramGenerationError(str(e)) from e

    async def _generate_weeks(
        self,
        request: GenerateProgramRequest,
        structure: Dict,
        week_params: List[WeekParameters],
    ) -> List[Dict]:
        """
        Generate all weeks with workouts and exercises.

        Args:
            request: Generation request
            structure: Template structure
            week_params: Periodization parameters per week

        Returns:
            List of week dictionaries with workouts
        """
        weeks = []
        workout_templates = structure.get("weeks", [{}])[0].get("workouts", [])

        for params in week_params:
            week_data = {
                "week_number": params.week_number,
                "focus": self._get_week_focus(params, request.goal),
                "intensity_percent": params.intensity_percent,
                "volume_modifier": params.volume_modifier,
                "is_deload": params.is_deload,
                "notes": "Deload week - reduced volume and intensity" if params.is_deload else None,
                "workouts": [],
            }

            for workout_template in workout_templates:
                workout = await self._generate_workout(
                    template=workout_template,
                    request=request,
                    params=params,
                )
                week_data["workouts"].append(workout)

            weeks.append(week_data)

        return weeks

    async def _generate_workout(
        self,
        template: Dict,
        request: GenerateProgramRequest,
        params: WeekParameters,
    ) -> Dict:
        """
        Generate a single workout with exercises.

        Args:
            template: Workout template from structure
            request: Generation request
            params: Week periodization parameters

        Returns:
            Workout dictionary with exercises
        """
        workout_type = template.get("workout_type", "full_body")
        muscle_groups = template.get("muscle_groups", [])
        exercise_slots = template.get("exercise_slots", 5)
        target_duration = template.get("target_duration_minutes", 60)

        # Adjust for deload
        if params.is_deload:
            exercise_slots = max(3, exercise_slots - 2)

        # Get available exercises from database (run in thread pool)
        available_exercises = await asyncio.get_event_loop().run_in_executor(
            self._executor,
            partial(
                self._exercise_repo.get_for_workout_type,
                workout_type=workout_type,
                equipment=request.equipment_available,
                limit=50,
            )
        )

        # Select exercises
        exercises = await self._select_exercises(
            workout_type=workout_type,
            muscle_groups=muscle_groups,
            equipment=request.equipment_available,
            exercise_count=exercise_slots,
            available_exercises=available_exercises,
            request=request,
            params=params,
        )

        return {
            "day_of_week": template.get("day_of_week", 1),
            "name": template.get("name", f"{workout_type.title()} Workout"),
            "workout_type": workout_type,
            "target_duration_minutes": target_duration,
            "exercises": exercises,
            "notes": None,
        }

    async def _select_exercises(
        self,
        workout_type: str,
        muscle_groups: List[str],
        equipment: List[str],
        exercise_count: int,
        available_exercises: List[Dict],
        request: GenerateProgramRequest,
        params: WeekParameters,
    ) -> List[Dict]:
        """
        Select exercises for a workout using LLM or fallback.

        Args:
            workout_type: Type of workout
            muscle_groups: Target muscle groups
            equipment: Available equipment
            exercise_count: Number of exercises to select
            available_exercises: Exercises from database
            request: Generation request
            params: Week periodization parameters

        Returns:
            List of exercise dictionaries
        """
        goal_str = request.goal.value if hasattr(request.goal, "value") else str(request.goal)
        exp_str = request.experience_level.value if hasattr(request.experience_level, "value") else str(request.experience_level)

        if self._exercise_selector and available_exercises:
            # Use LLM for exercise selection
            selection_request = ExerciseSelectionRequest(
                workout_type=workout_type,
                muscle_groups=muscle_groups,
                equipment=equipment,
                exercise_count=exercise_count,
                intensity_percent=params.intensity_percent,
                volume_modifier=params.volume_modifier,
                available_exercises=available_exercises,
                user_limitations=request.limitations if request.limitations else None,
                experience_level=exp_str,
                goal=goal_str,
                is_deload=params.is_deload,
            )

            try:
                response = await self._exercise_selector.select_exercises(selection_request)
                return [
                    {
                        "exercise_id": ex.exercise_id,
                        "exercise_name": ex.exercise_name,
                        "sets": ex.sets,
                        "reps": ex.reps,
                        "rest_seconds": ex.rest_seconds,
                        "notes": ex.notes,
                        "order": ex.order,
                        "primary_muscles": self._get_exercise_muscles(ex.exercise_id, available_exercises),
                        "equipment": self._get_exercise_equipment(ex.exercise_id, available_exercises),
                    }
                    for ex in response.exercises
                ]
            except Exception as e:
                logger.warning(f"LLM exercise selection failed, using fallback: {e}")

        # Fallback: deterministic selection with intelligent exercise selector
        return self._fallback_exercise_selection(
            available_exercises=available_exercises,
            exercise_count=exercise_count,
            goal=goal_str,
            is_deload=params.is_deload,
            equipment=equipment,
            workout_type=workout_type,
            muscle_groups=muscle_groups,
        )

    def _fallback_exercise_selection(
        self,
        available_exercises: List[Dict],
        exercise_count: int,
        goal: str,
        is_deload: bool,
        equipment: Optional[List[str]] = None,
        workout_type: Optional[str] = None,
        muscle_groups: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Fallback exercise selection when LLM is unavailable.

        Uses the ExerciseSelector for intelligent selection based on
        equipment availability and workout requirements.

        Args:
            available_exercises: Available exercises
            exercise_count: Target count
            goal: Training goal
            is_deload: Deload flag
            equipment: Available equipment (for intelligent selection)
            workout_type: Type of workout (push, pull, legs, etc.)
            muscle_groups: Target muscle groups

        Returns:
            List of exercise dictionaries
        """
        selected = []
        exclude_ids: List[str] = []
        equipment_list = equipment or []

        # Determine category preference based on goal
        prefer_compound = goal in ("strength", "hypertrophy", "general_fitness")

        # Try to use ExerciseSelector for intelligent selection
        if self._db_exercise_selector and equipment_list:
            # Determine movement patterns based on workout type
            workout_patterns = {
                "push": ["push"],
                "pull": ["pull"],
                "legs": ["squat", "hinge"],
                "upper": ["push", "pull"],
                "lower": ["squat", "hinge"],
                "full_body": ["push", "pull", "squat", "hinge"],
            }
            patterns = workout_patterns.get(workout_type or "", [])

            # Select compound exercises first
            compound_count = max(2, exercise_count // 2) if prefer_compound else 1

            for pattern in patterns[:compound_count]:
                requirements = SlotRequirements(
                    movement_pattern=pattern,
                    target_muscles=muscle_groups,
                    category="compound" if prefer_compound else None,
                    supports_1rm=goal == "strength",
                )
                ex = self._db_exercise_selector.fill_exercise_slot(
                    requirements=requirements,
                    available_equipment=equipment_list,
                    exclude_exercises=exclude_ids,
                )
                if ex:
                    selected.append(ex)
                    exclude_ids.append(ex["id"])

            # Fill remaining slots with isolation exercises
            while len(selected) < exercise_count:
                requirements = SlotRequirements(
                    target_muscles=muscle_groups,
                    category="isolation" if prefer_compound else None,
                )
                ex = self._db_exercise_selector.fill_exercise_slot(
                    requirements=requirements,
                    available_equipment=equipment_list,
                    exclude_exercises=exclude_ids,
                )
                if ex:
                    selected.append(ex)
                    exclude_ids.append(ex["id"])
                else:
                    break

        # Fallback to simple sorting if ExerciseSelector didn't fill all slots
        if len(selected) < exercise_count and available_exercises:
            selected_ids = set(ex.get("id") for ex in selected)
            remaining = [
                ex for ex in available_exercises
                if ex.get("id") not in selected_ids
            ]
            # Sort by category (compounds first)
            sorted_remaining = sorted(
                remaining,
                key=lambda x: (0 if x.get("category") == "compound" else 1, x.get("name", "")),
            )
            selected.extend(sorted_remaining[:exercise_count - len(selected)])

        # Determine rep scheme based on goal
        rep_schemes = {
            "strength": ("3-5", 4, 150),
            "hypertrophy": ("8-12", 4, 90),
            "endurance": ("15-20", 3, 60),
            "weight_loss": ("12-15", 3, 45),
            "general_fitness": ("10-15", 3, 60),
        }

        reps, sets, rest = rep_schemes.get(goal, ("8-12", 3, 90))
        if is_deload:
            sets = max(2, sets - 1)

        return [
            {
                "exercise_id": ex["id"],
                "exercise_name": ex.get("name", ex["id"]),
                "sets": sets,
                "reps": reps,
                "rest_seconds": rest,
                "notes": None,
                "order": i + 1,
                "primary_muscles": ex.get("primary_muscles", []),
                "equipment": ex.get("equipment", []),
            }
            for i, ex in enumerate(selected[:exercise_count])
        ]

    def _get_exercise_muscles(self, exercise_id: str, exercises: List[Dict]) -> List[str]:
        """Get primary muscles for an exercise."""
        for ex in exercises:
            if ex.get("id") == exercise_id:
                return ex.get("primary_muscles", [])
        return []

    def _get_exercise_equipment(self, exercise_id: str, exercises: List[Dict]) -> List[str]:
        """Get equipment for an exercise."""
        for ex in exercises:
            if ex.get("id") == exercise_id:
                return ex.get("equipment", [])
        return []

    def _get_week_focus(self, params: WeekParameters, goal: ProgramGoal | str) -> str:
        """Generate focus text for a week."""
        if params.is_deload:
            return "Recovery & Deload"

        if params.phase:
            phase_names = {
                "accumulation": "Volume Accumulation",
                "transmutation": "Intensity Transmutation",
                "realization": "Peak Realization",
            }
            return phase_names.get(params.phase.value, "Training")

        goal_str = goal.value if hasattr(goal, "value") else str(goal)
        goal_focus = {
            "strength": "Strength Development",
            "hypertrophy": "Muscle Building",
            "endurance": "Endurance Training",
            "weight_loss": "Fat Loss",
            "general_fitness": "General Fitness",
        }
        return goal_focus.get(goal_str, "Training")

    def _generate_program_name(self, request: GenerateProgramRequest) -> str:
        """Generate a name for the program."""
        goal_str = request.goal.value if hasattr(request.goal, "value") else str(request.goal)
        goal_names = {
            "strength": "Strength",
            "hypertrophy": "Hypertrophy",
            "endurance": "Endurance",
            "weight_loss": "Fat Loss",
            "general_fitness": "Fitness",
        }
        goal_name = goal_names.get(goal_str, goal_str.title())
        return f"{request.duration_weeks}-Week {goal_name} Program"

    def _generate_program_description(self, request: GenerateProgramRequest) -> str:
        """Generate a description for the program."""
        goal_str = request.goal.value if hasattr(request.goal, "value") else str(request.goal)
        exp_str = request.experience_level.value if hasattr(request.experience_level, "value") else str(request.experience_level)
        return (
            f"A {request.duration_weeks}-week {goal_str.replace('_', ' ')} program "
            f"designed for {exp_str} lifters, "
            f"with {request.sessions_per_week} sessions per week."
        )
