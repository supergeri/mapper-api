# Figma Workflow Examples - Complete JSON Examples

This document contains comprehensive, complex JSON examples for all API endpoints. Use these in Figma for prototyping and testing.

---

## Table of Contents

1. [Complex Workout Request Examples](#complex-workout-request-examples)
2. [API Request/Response Examples](#api-requestresponse-examples)
3. [Apple WorkoutKit Examples](#apple-workoutkit-examples)
4. [Workflow Validation Examples](#workflow-validation-examples)
5. [Exercise Suggestion Examples](#exercise-suggestion-examples)
6. [Mapping Examples](#mapping-examples)

---

## Complex Workout Request Examples

### Example 1: Complex Strength Workout with Multiple Blocks and Supersets

**Request Body for `/map/auto-map`, `/workflow/validate`, `/workflow/process`:**

```json
{
  "blocks_json": {
    "title": "Updated Strength Workout",
    "source": "ai_generated",
    "blocks": [
      {
        "label": "Big Lifts (Single Sets)",
        "structure": null,
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [
          {
            "name": "Marrs Bar Squat (SquatMax-MD + Voltras)",
            "sets": 1,
            "reps": null,
            "reps_range": "6-8",
            "duration_sec": null,
            "rest_sec": null,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          },
          {
            "name": "Flat Bench Press (dumbbells or bar)",
            "sets": 1,
            "reps": null,
            "reps_range": "6-8",
            "duration_sec": null,
            "rest_sec": null,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          }
        ],
        "supersets": []
      },
      {
        "label": "Superset Cluster 1 – Rack Work",
        "structure": "3 sets",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "Landmine Press (using Jammer Arms or barbell in landmine slot) (per side)",
                "sets": 3,
                "reps": null,
                "reps_range": "8-10",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "Seal Row / Chest-Supported Dumbbell Row",
                "sets": 3,
                "reps": null,
                "reps_range": "10-12",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": 90
          }
        ]
      },
      {
        "label": "Superset Cluster 2 – Dumbbells & Bands",
        "structure": "3 sets",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "Dumbbell RDLs",
                "sets": 3,
                "reps": null,
                "reps_range": "8-10",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "Band-Resisted Push-Ups",
                "sets": 3,
                "reps": null,
                "reps_range": "8-12",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": 75
          }
        ]
      },
      {
        "label": "Superset Cluster 3 – Core & Torque Zone",
        "structure": "3 sets",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "Pure Torque Device Twists or Holds",
                "sets": 3,
                "reps": null,
                "reps_range": null,
                "duration_sec": 30,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "interval"
              },
              {
                "name": "Freak Athlete Hyper (Back Extensions)",
                "sets": 3,
                "reps": null,
                "reps_range": "10-12",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": 60
          }
        ]
      }
    ]
  }
}
```

### Example 2: Complex Multi-Block Workout with Rounds, Supersets, and Intervals

```json
{
  "blocks_json": {
    "title": "Imported Workout",
    "source": "image:week7.png",
    "blocks": [
      {
        "label": "Primer",
        "structure": "3 rounds",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "A1: GOODMORNINGS X10",
                "sets": 3,
                "reps": 10,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "A2: KB ALTERNATING PLANK DRAG X12",
                "sets": 3,
                "reps": 12,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "A3: BACKWARD SLED DRAG X20M",
                "sets": 3,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 20,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": null
          }
        ]
      },
      {
        "label": "Strength / Power",
        "structure": "4 rounds",
        "rest_between_sec": 15,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 4,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "B1: DUAL KB FRONT SQUAT X5",
                "sets": 4,
                "reps": 5,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "B2: BURPEE MAX BROAD JUMPS X4 wb",
                "sets": 4,
                "reps": 4,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "B3: KB SINGLE ARM SWING X § EACH SIDE",
                "sets": 4,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "interval"
              }
            ],
            "rest_between_sec": null
          }
        ]
      },
      {
        "label": "Muscular Endurance",
        "structure": "3 rounds",
        "rest_between_sec": 45,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "C1: FARMER CARRY X 60M",
                "sets": 3,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 60,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "C2: DB PUSH PRESS X 25 S",
                "sets": 3,
                "reps": 25,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": null
          },
          {
            "exercises": [
              {
                "name": "D1: SLED PUSH X25-30M",
                "sets": 3,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": "25-30m",
                "type": "strength"
              },
              {
                "name": "D2: HAND RELEASE PUSH UPS X6-10 0",
                "sets": 3,
                "reps": null,
                "reps_range": "6-10",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": null
          }
        ]
      },
      {
        "label": "Metabolic Conditioning",
        "structure": null,
        "rest_between_sec": 90,
        "time_work_sec": 60,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [
          {
            "name": "E: SKIER 60S ON 90S OFF X3",
            "sets": 3,
            "reps": null,
            "reps_range": null,
            "duration_sec": 60,
            "rest_sec": 90,
            "distance_m": null,
            "distance_range": null,
            "type": "interval"
          }
        ],
        "supersets": []
      }
    ]
  }
}
```

### Example 3: HIIT Workout with For Time Structure

```json
{
  "blocks_json": {
    "title": "Jour 193",
    "source": "image:Screenshot 2025-11-05 at 9.15.56 PM.png",
    "blocks": [
      {
        "label": "Hyrox",
        "structure": "for time (cap: 35 min)",
        "rest_between_sec": null,
        "time_work_sec": 2100,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "1200 m Run",
                "sets": null,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 1200,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "100 m KB Farmers (32/24kg)",
                "sets": null,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 100,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "1000 m Run",
                "sets": null,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 1000,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "80 Walking Lunges (30/20kg)",
                "sets": null,
                "reps": 80,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "800 m Run",
                "sets": null,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 800,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "60 cals Row / Skireg",
                "sets": null,
                "reps": 60,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "600 m Run '",
                "sets": null,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 600,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "40 Wall Balls (9/6kg)",
                "sets": null,
                "reps": 40,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "400 m Run \"",
                "sets": null,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 400,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "20 Burpees",
                "sets": null,
                "reps": 20,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "HIIT"
              }
            ],
            "rest_between_sec": null
          }
        ]
      }
    ]
  }
}
```

---

## API Request/Response Examples

### Endpoint: `POST /map/auto-map`

**Request:**
```json
{
  "blocks_json": {
    "title": "Updated Strength Workout",
    "source": "ai_generated",
    "blocks": [
      {
        "label": "Big Lifts",
        "structure": null,
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [
          {
            "name": "Marrs Bar Squat (SquatMax-MD + Voltras)",
            "sets": 1,
            "reps": null,
            "reps_range": "6-8",
            "duration_sec": null,
            "rest_sec": null,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          }
        ],
        "supersets": []
      }
    ]
  }
}
```

**Response:**
```json
{
  "yaml": "settings:\n  deleteSameNameWorkout: true\nworkouts:\n  Updated Strength Workout:\n    sport: strength\n    steps:\n    - type: exercise\n      exerciseName: Squat\n      sets: 1\n      repetitionValue: 6-8\n      rest: null\nschedulePlan:\n  start_from: '2025-11-21'\n  workouts:\n  - Updated Strength Workout\n"
}
```

### Endpoint: `POST /map/to-workoutkit`

**Request:**
```json
{
  "blocks_json": {
    "title": "Updated Strength Workout",
    "source": "ai_generated",
    "blocks": [
      {
        "label": "Big Lifts (Single Sets)",
        "structure": null,
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [
          {
            "name": "Marrs Bar Squat (SquatMax-MD + Voltras)",
            "sets": 1,
            "reps": null,
            "reps_range": "6-8",
            "duration_sec": null,
            "rest_sec": null,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          },
          {
            "name": "Flat Bench Press (dumbbells or bar)",
            "sets": 1,
            "reps": null,
            "reps_range": "6-8",
            "duration_sec": null,
            "rest_sec": null,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          }
        ],
        "supersets": []
      },
      {
        "label": "Superset Cluster 1 – Rack Work",
        "structure": "3 sets",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "Landmine Press (using Jammer Arms or barbell in landmine slot) (per side)",
                "sets": 3,
                "reps": null,
                "reps_range": "8-10",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "Seal Row / Chest-Supported Dumbbell Row",
                "sets": 3,
                "reps": null,
                "reps_range": "10-12",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": 90
          }
        ]
      },
      {
        "label": "Superset Cluster 2 – Dumbbells & Bands",
        "structure": "3 sets",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "Dumbbell RDLs",
                "sets": 3,
                "reps": null,
                "reps_range": "8-10",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "Band-Resisted Push-Ups",
                "sets": 3,
                "reps": null,
                "reps_range": "8-12",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": 75
          }
        ]
      },
      {
        "label": "Superset Cluster 3 – Core & Torque Zone",
        "structure": "3 sets",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "Pure Torque Device Twists or Holds",
                "sets": 3,
                "reps": null,
                "reps_range": null,
                "duration_sec": 30,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "interval"
              },
              {
                "name": "Freak Athlete Hyper (Back Extensions)",
                "sets": 3,
                "reps": null,
                "reps_range": "10-12",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": 60
          }
        ]
      }
    ]
  }
}
```

**Response:**
```json
{
  "title": "Updated Strength Workout",
  "sportType": "strengthTraining",
  "intervals": [
    {
      "kind": "reps",
      "reps": 7,
      "name": "Squat",
      "load": null,
      "restSec": null
    },
    {
      "kind": "reps",
      "reps": 7,
      "name": "Bench Press",
      "load": null,
      "restSec": null
    },
    {
      "kind": "repeat",
      "reps": 3,
      "intervals": [
        {
          "kind": "reps",
          "reps": 9,
          "name": "Clean And Press",
          "load": null,
          "restSec": null
        },
        {
          "kind": "time",
          "seconds": 90,
          "target": null
        },
        {
          "kind": "reps",
          "reps": 11,
          "name": "Chest-Supported Dumbbell Row",
          "load": null,
          "restSec": null
        }
      ]
    },
    {
      "kind": "repeat",
      "reps": 3,
      "intervals": [
        {
          "kind": "reps",
          "reps": 9,
          "name": "Romanian Deadlift",
          "load": null,
          "restSec": null
        },
        {
          "kind": "time",
          "seconds": 75,
          "target": null
        },
        {
          "kind": "reps",
          "reps": 10,
          "name": "Push Up",
          "load": null,
          "restSec": null
        }
      ]
    },
    {
      "kind": "repeat",
      "reps": 3,
      "intervals": [
        {
          "kind": "time",
          "seconds": 30,
          "target": null
        },
        {
          "kind": "time",
          "seconds": 60,
          "target": null
        },
        {
          "kind": "reps",
          "reps": 11,
          "name": "Ghd Back Extensions",
          "load": null,
          "restSec": null
        }
      ]
    }
  ],
  "schedule": null
}
```

### Endpoint: `POST /map/to-zwo`

**Request:** (Same as above)

**Response:** (XML file download)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase>
  <Workouts>
    <Workout>
      <Name>Updated Strength Workout</Name>
      <SportType>Running</SportType>
      <Workout>
        <Step>
          <Type>Exercise</Type>
          <ExerciseName>Squat</ExerciseName>
        </Step>
      </Workout>
    </Workout>
  </Workouts>
</TrainingCenterDatabase>
```

---

## Apple WorkoutKit Examples

### Endpoint: `POST /map/to-workoutkit`

Converts blocks JSON to Apple WorkoutKit DTO format for creating workouts on Apple Watch.

#### Example 1: Complex Strength Workout with Multiple Block Types

**Request:**
```json
{
  "blocks_json": {
    "title": "Full Body Strength Workout",
    "source": "manual",
    "blocks": [
      {
        "label": "Warm-up",
        "structure": null,
        "rest_between_sec": null,
        "time_work_sec": 300,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [],
        "supersets": []
      },
      {
        "label": "Main Workout",
        "structure": "4 sets",
        "rest_between_sec": 90,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 4,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "DB Bench Press",
                "sets": 4,
                "reps": 8,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": 60,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "Seal Row",
                "sets": 4,
                "reps": null,
                "reps_range": "10-12",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": 90
          }
        ]
      },
      {
        "label": "Accessory Work",
        "structure": "3 sets",
        "rest_between_sec": 60,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [
          {
            "name": "Farmers Walk",
            "sets": 3,
            "reps": null,
            "reps_range": null,
            "duration_sec": null,
            "rest_sec": null,
            "distance_m": 50,
            "distance_range": null,
            "type": "strength"
          }
        ],
        "supersets": []
      },
      {
        "label": "Metabolic Finisher",
        "structure": null,
        "rest_between_sec": 90,
        "time_work_sec": 60,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [
          {
            "name": "Burpees",
            "sets": 3,
            "reps": null,
            "reps_range": null,
            "duration_sec": 60,
            "rest_sec": 90,
            "distance_m": null,
            "distance_range": null,
            "type": "interval"
          }
        ],
        "supersets": []
      },
      {
        "label": "Cooldown",
        "structure": null,
        "rest_between_sec": null,
        "time_work_sec": 300,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [],
        "supersets": []
      }
    ]
  }
}
```

**Response:**
```json
{
  "title": "Full Body Strength Workout",
  "sportType": "strengthTraining",
  "intervals": [
    {
      "kind": "warmup",
      "seconds": 300,
      "target": null
    },
    {
      "kind": "repeat",
      "reps": 4,
      "intervals": [
        {
          "kind": "reps",
          "reps": 8,
          "name": "Dumbbell Bench Press",
          "load": null,
          "restSec": 60
        },
        {
          "kind": "time",
          "seconds": 90,
          "target": null
        },
        {
          "kind": "reps",
          "reps": 11,
          "name": "Chest-Supported Dumbbell Row",
          "load": null,
          "restSec": null
        }
      ]
    },
    {
      "kind": "distance",
      "meters": 50,
      "target": null
    },
    {
      "kind": "time",
      "seconds": 60,
      "target": null
    },
    {
      "kind": "repeat",
      "reps": 3,
      "intervals": [
        {
          "kind": "time",
          "seconds": 60,
          "target": null
        },
        {
          "kind": "time",
          "seconds": 90,
          "target": null
        }
      ]
    },
    {
      "kind": "cooldown",
      "seconds": 300,
      "target": null
    }
  ],
  "schedule": null
}
```

#### Example 2: Workout with Distance-Based Exercises

**Request:**
```json
{
  "blocks_json": {
    "title": "Hyrox Training Session",
    "source": "manual",
    "blocks": [
      {
        "label": "Main Workout",
        "structure": "for time",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "1000 m Run",
                "sets": null,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 1000,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "100 m KB Farmers (32/24kg)",
                "sets": null,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 100,
                "distance_range": null,
                "type": "HIIT"
              },
              {
                "name": "80 Walking Lunges (30/20kg)",
                "sets": null,
                "reps": 80,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "HIIT"
              }
            ],
            "rest_between_sec": null
          }
        ]
      }
    ]
  }
}
```

**Response:**
```json
{
  "title": "Hyrox Training Session",
  "sportType": "strengthTraining",
  "intervals": [
    {
      "kind": "distance",
      "meters": 1000,
      "target": null
    },
    {
      "kind": "distance",
      "meters": 100,
      "target": null
    },
    {
      "kind": "reps",
      "reps": 80,
      "name": "Walking Lunge",
      "load": null,
      "restSec": null
    }
  ],
  "schedule": null
}
```

#### Example 3: Workout with Time-Based Intervals

**Request:**
```json
{
  "blocks_json": {
    "title": "Interval Training",
    "source": "manual",
    "blocks": [
      {
        "label": "Metabolic Conditioning",
        "structure": null,
        "rest_between_sec": 90,
        "time_work_sec": 60,
        "default_reps_range": null,
        "default_sets": null,
        "exercises": [
          {
            "name": "SKIER 60S ON 90S OFF X3",
            "sets": 3,
            "reps": null,
            "reps_range": null,
            "duration_sec": 60,
            "rest_sec": 90,
            "distance_m": null,
            "distance_range": null,
            "type": "interval"
          }
        ],
        "supersets": []
      }
    ]
  }
}
```

**Response:**
```json
{
  "title": "Interval Training",
  "sportType": "strengthTraining",
  "intervals": [
    {
      "kind": "repeat",
      "reps": 3,
      "intervals": [
        {
          "kind": "time",
          "seconds": 60,
          "target": null
        },
        {
          "kind": "time",
          "seconds": 90,
          "target": null
        }
      ]
    }
  ],
  "schedule": null
}
```

#### Example 4: Complex Multi-Block Workout (Complete Example)

**Request:**
```json
{
  "blocks_json": {
    "title": "Complete Training Session",
    "source": "ai_generated",
    "blocks": [
      {
        "label": "Primer",
        "structure": "3 rounds",
        "rest_between_sec": null,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "A1: GOODMORNINGS X10",
                "sets": 3,
                "reps": 10,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "A2: KB ALTERNATING PLANK DRAG X12",
                "sets": 3,
                "reps": 12,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "A3: BACKWARD SLED DRAG X20M",
                "sets": 3,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 20,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": null
          }
        ]
      },
      {
        "label": "Strength / Power",
        "structure": "4 rounds",
        "rest_between_sec": 15,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 4,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "B1: DUAL KB FRONT SQUAT X5",
                "sets": 4,
                "reps": 5,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "B2: BURPEE MAX BROAD JUMPS X4 wb",
                "sets": 4,
                "reps": 4,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "B3: KB SINGLE ARM SWING X § EACH SIDE",
                "sets": 4,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "interval"
              }
            ],
            "rest_between_sec": null
          }
        ]
      },
      {
        "label": "Muscular Endurance",
        "structure": "3 rounds",
        "rest_between_sec": 45,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "C1: FARMER CARRY X 60M",
                "sets": 3,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": 60,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "C2: DB PUSH PRESS X 25 S",
                "sets": 3,
                "reps": 25,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": null
          },
          {
            "exercises": [
              {
                "name": "D1: SLED PUSH X25-30M",
                "sets": 3,
                "reps": null,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": "25-30m",
                "type": "strength"
              },
              {
                "name": "D2: HAND RELEASE PUSH UPS X6-10 0",
                "sets": 3,
                "reps": null,
                "reps_range": "6-10",
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": null
          }
        ]
      }
    ]
  }
}
```

**Response:**
```json
{
  "title": "Complete Training Session",
  "sportType": "strengthTraining",
  "intervals": [
    {
      "kind": "repeat",
      "reps": 3,
      "intervals": [
        {
          "kind": "reps",
          "reps": 10,
          "name": "Good Morning",
          "load": null,
          "restSec": null
        },
        {
          "kind": "reps",
          "reps": 12,
          "name": "Plank",
          "load": null,
          "restSec": null
        },
        {
          "kind": "distance",
          "meters": 20,
          "target": null
        }
      ]
    },
    {
      "kind": "repeat",
      "reps": 4,
      "intervals": [
        {
          "kind": "reps",
          "reps": 5,
          "name": "Front Squat",
          "load": null,
          "restSec": null
        },
        {
          "kind": "reps",
          "reps": 4,
          "name": "Burpee",
          "load": null,
          "restSec": null
        },
        {
          "kind": "reps",
          "reps": 10,
          "name": "Kettlebell Swing",
          "load": null,
          "restSec": null
        },
        {
          "kind": "time",
          "seconds": 15,
          "target": null
        }
      ]
    },
    {
      "kind": "repeat",
      "reps": 3,
      "intervals": [
        {
          "kind": "distance",
          "meters": 60,
          "target": null
        },
        {
          "kind": "reps",
          "reps": 25,
          "name": "Push Press",
          "load": null,
          "restSec": null
        },
        {
          "kind": "time",
          "seconds": 45,
          "target": null
        },
        {
          "kind": "distance",
          "meters": 27,
          "target": null
        },
        {
          "kind": "reps",
          "reps": 8,
          "name": "Push Up",
          "load": null,
          "restSec": null
        }
      ]
    }
  ],
  "schedule": null
}
```

### WorkoutKit Response Format Reference

**Step Types:**
- `TimeStep`: `{"kind": "time", "seconds": 60, "target": null}`
- `DistanceStep`: `{"kind": "distance", "meters": 100, "target": null}`
- `RepsStep`: `{"kind": "reps", "reps": 10, "name": "Exercise Name", "load": null, "restSec": 60}`

**Interval Types:**
- `WarmupInterval`: `{"kind": "warmup", "seconds": 300, "target": null}`
- `CooldownInterval`: `{"kind": "cooldown", "seconds": 300, "target": null}`
- `RepeatInterval`: `{"kind": "repeat", "reps": 3, "intervals": [...]}`

**Complete Plan Structure:**
```json
{
  "title": "Workout Name",
  "sportType": "strengthTraining" | "running" | "cycling",
  "intervals": [
    // Array of intervals (warmup, cooldown, repeat, or steps)
  ],
  "schedule": {
    "startLocal": "2025-11-14T10:00:00Z"  // Optional
  }
}
```

### Notes for Apple App Importer

1. **Sport Types**: `strengthTraining`, `running`, or `cycling`
2. **Step Priority**: Time > Distance > Reps (first available is used)
3. **Rounds**: Converted to `RepeatInterval` with `reps` field
4. **Rest Periods**: Included as `TimeStep` between exercises
5. **Load Information**: Currently `null`, but structure supports `{"value": 20, "unit": "kg"}`
6. **Warmup/Cooldown**: Automatically detected from block labels containing "warmup", "primer", or "cooldown"

---

## Workflow Validation Examples

### Endpoint: `POST /workflow/validate`

**Request:**
```json
{
  "blocks_json": {
    "title": "Complex Workout with Unknown Exercises",
    "source": "manual",
    "blocks": [
      {
        "label": "Main Workout",
        "structure": "3 sets",
        "rest_between_sec": 60,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 3,
        "exercises": [
          {
            "name": "DB Bench Press",
            "sets": 3,
            "reps": 8,
            "reps_range": null,
            "duration_sec": null,
            "rest_sec": 60,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          },
          {
            "name": "UNKNOWN EXERCISE XYZ",
            "sets": 3,
            "reps": 10,
            "reps_range": null,
            "duration_sec": null,
            "rest_sec": null,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          },
          {
            "name": "SOME TYPE OF SQUAT",
            "sets": 3,
            "reps": 12,
            "reps_range": null,
            "duration_sec": null,
            "rest_sec": null,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          }
        ],
        "supersets": []
      }
    ]
  }
}
```

**Response:**
```json
{
  "total_exercises": 3,
  "validated_exercises": [
    {
      "original_name": "DB Bench Press",
      "mapped_to": "Dumbbell Bench Press",
      "confidence": 1.0,
      "description": "lap | DB Bench Press x8",
      "block": "Main Workout",
      "location": "exercises[0]",
      "status": "valid",
      "suggestions": {
        "similar": [
          {
            "name": "Dumbbell Bench Press",
            "score": 1.0,
            "normalized": "dumbbell bench press"
          },
          {
            "name": "Bench Press",
            "score": 0.95,
            "normalized": "bench press"
          }
        ],
        "by_type": [],
        "category": null,
        "needs_user_search": false
      }
    }
  ],
  "needs_review": [
    {
      "original_name": "SOME TYPE OF SQUAT",
      "mapped_to": "Squat",
      "confidence": 0.75,
      "description": "lap | SOME TYPE OF SQUAT x12",
      "block": "Main Workout",
      "location": "exercises[1]",
      "status": "needs_review",
      "suggestions": {
        "similar": [
          {
            "name": "Squat",
            "score": 0.85,
            "normalized": "squat"
          },
          {
            "name": "Air Squat",
            "score": 0.75,
            "normalized": "air squat"
          }
        ],
        "by_type": [
          {
            "name": "Air Squat",
            "score": 0.75,
            "normalized": "air squat",
            "keyword": "squat"
          },
          {
            "name": "Back Squat",
            "score": 0.70,
            "normalized": "back squat",
            "keyword": "squat"
          }
        ],
        "category": "squat",
        "needs_user_search": false
      }
    }
  ],
  "unmapped_exercises": [
    {
      "original_name": "UNKNOWN EXERCISE XYZ",
      "mapped_to": null,
      "confidence": 0.0,
      "description": "lap | UNKNOWN EXERCISE XYZ x10",
      "block": "Main Workout",
      "location": "exercises[2]",
      "status": "needs_review",
      "suggestions": {
        "similar": [],
        "by_type": [],
        "category": null,
        "needs_user_search": true
      }
    }
  ],
  "can_proceed": false
}
```

### Endpoint: `POST /workflow/process`

**Request:** (Same as validate)

**Response:**
```json
{
  "validation": {
    "total_exercises": 3,
    "validated_exercises": [
      {
        "original_name": "DB Bench Press",
        "mapped_to": "Dumbbell Bench Press",
        "confidence": 1.0,
        "status": "valid"
      }
    ],
    "needs_review": [
      {
        "original_name": "SOME TYPE OF SQUAT",
        "mapped_to": "Squat",
        "confidence": 0.75,
        "status": "needs_review"
      }
    ],
    "unmapped_exercises": [
      {
        "original_name": "UNKNOWN EXERCISE XYZ",
        "mapped_to": null,
        "confidence": 0.0,
        "status": "needs_review"
      }
    ],
    "can_proceed": false
  },
  "yaml": "settings:\n  deleteSameNameWorkout: true\nworkouts:\n  Complex Workout with Unknown Exercises:\n    sport: strength\n    steps:\n    - type: exercise\n      exerciseName: Dumbbell Bench Press\n      sets: 3\n      repetitionValue: 8\n      rest: 60\n    - type: exercise\n      exerciseName: Custom: UNKNOWN EXERCISE XYZ\n      sets: 3\n      repetitionValue: 10\n    - type: exercise\n      exerciseName: Squat\n      sets: 3\n      repetitionValue: 12\n",
  "message": "Workout converted successfully"
}
```

### Endpoint: `POST /workflow/process-with-review`

**Request:** (Same as above)

**Response:** (Similar to process, but will block if unmapped exercises exist)
```json
{
  "validation": {
    "total_exercises": 3,
    "validated_exercises": [
      {
        "original_name": "DB Bench Press",
        "mapped_to": "Dumbbell Bench Press",
        "confidence": 1.0,
        "status": "valid"
      }
    ],
    "needs_review": [
      {
        "original_name": "SOME TYPE OF SQUAT",
        "mapped_to": "Squat",
        "confidence": 0.75,
        "status": "needs_review"
      }
    ],
    "unmapped_exercises": [
      {
        "original_name": "UNKNOWN EXERCISE XYZ",
        "mapped_to": null,
        "confidence": 0.0,
        "status": "needs_review"
      }
    ],
    "can_proceed": false
  },
  "yaml": null,
  "message": "Please review 1 unmapped exercises before proceeding"
}
```

---

## Exercise Suggestion Examples

### Endpoint: `POST /exercise/suggest`

**Request:**
```json
{
  "exercise_name": "SOME TYPE OF SQUAT",
  "include_similar_types": true
}
```

**Response:**
```json
{
  "input": "SOME TYPE OF SQUAT",
  "best_match": {
    "name": "Squat",
    "score": 0.85,
    "is_exact": false
  },
  "similar_exercises": [
    {
      "name": "Squat",
      "score": 0.85,
      "normalized": "squat"
    },
    {
      "name": "Air Squat",
      "score": 0.75,
      "normalized": "air squat"
    },
    {
      "name": "Back Squat",
      "score": 0.70,
      "normalized": "back squat"
    },
    {
      "name": "Front Squat",
      "score": 0.68,
      "normalized": "front squat"
    },
    {
      "name": "Overhead Squat",
      "score": 0.65,
      "normalized": "overhead squat"
    }
  ],
  "exercises_by_type": [
    {
      "name": "Air Squat",
      "score": 0.75,
      "normalized": "air squat",
      "keyword": "squat"
    },
    {
      "name": "Back Squat",
      "score": 0.70,
      "normalized": "back squat",
      "keyword": "squat"
    },
    {
      "name": "Front Squat",
      "score": 0.68,
      "normalized": "front squat",
      "keyword": "squat"
    },
    {
      "name": "Overhead Squat",
      "score": 0.65,
      "normalized": "overhead squat",
      "keyword": "squat"
    },
    {
      "name": "Goblet Squat",
      "score": 0.63,
      "normalized": "goblet squat",
      "keyword": "squat"
    },
    {
      "name": "Bulgarian Split Squat",
      "score": 0.60,
      "normalized": "bulgarian split squat",
      "keyword": "squat"
    }
  ],
  "category": "squat",
  "needs_user_search": false
}
```

**Request for Unknown Exercise:**
```json
{
  "exercise_name": "UNKNOWN EXERCISE XYZ",
  "include_similar_types": true
}
```

**Response:**
```json
{
  "input": "UNKNOWN EXERCISE XYZ",
  "best_match": null,
  "similar_exercises": [],
  "exercises_by_type": [],
  "category": null,
  "needs_user_search": true
}
```

### Endpoint: `GET /exercise/similar/{exercise_name}`

**Request:** `GET /exercise/similar/DB%20Bench%20Press?limit=10`

**Response:**
```json
{
  "exercise_name": "DB Bench Press",
  "similar": [
    {
      "name": "Dumbbell Bench Press",
      "score": 0.95,
      "normalized": "dumbbell bench press"
    },
    {
      "name": "Bench Press",
      "score": 0.85,
      "normalized": "bench press"
    },
    {
      "name": "Incline Dumbbell Bench Press",
      "score": 0.80,
      "normalized": "incline dumbbell bench press"
    },
    {
      "name": "Decline Dumbbell Bench Press",
      "score": 0.75,
      "normalized": "decline dumbbell bench press"
    }
  ]
}
```

### Endpoint: `GET /exercise/by-type/{exercise_name}`

**Request:** `GET /exercise/by-type/Squat?limit=20`

**Response:**
```json
{
  "exercise_name": "Squat",
  "category": "squat",
  "exercises": [
    {
      "name": "Squat",
      "score": 1.0,
      "normalized": "squat",
      "keyword": "squat"
    },
    {
      "name": "Air Squat",
      "score": 0.85,
      "normalized": "air squat",
      "keyword": "squat"
    },
    {
      "name": "Back Squat",
      "score": 0.80,
      "normalized": "back squat",
      "keyword": "squat"
    },
    {
      "name": "Front Squat",
      "score": 0.78,
      "normalized": "front squat",
      "keyword": "squat"
    },
    {
      "name": "Overhead Squat",
      "score": 0.75,
      "normalized": "overhead squat",
      "keyword": "squat"
    },
    {
      "name": "Goblet Squat",
      "score": 0.73,
      "normalized": "goblet squat",
      "keyword": "squat"
    },
    {
      "name": "Bulgarian Split Squat",
      "score": 0.70,
      "normalized": "bulgarian split squat",
      "keyword": "squat"
    },
    {
      "name": "Jump Squat",
      "score": 0.68,
      "normalized": "jump squat",
      "keyword": "squat"
    }
  ]
}
```

---

## Mapping Examples

### Endpoint: `POST /mappings/add`

**Request:**
```json
{
  "exercise_name": "DB Bench",
  "garmin_name": "Dumbbell Bench Press"
}
```

**Response:**
```json
{
  "message": "Mapping saved successfully (also recorded for global popularity)",
  "mapping": {
    "exercise_name": "DB Bench",
    "garmin_name": "Dumbbell Bench Press",
    "created_at": "2025-11-14T15:30:00Z"
  }
}
```

### Endpoint: `GET /mappings`

**Response:**
```json
{
  "total": 5,
  "mappings": [
    {
      "exercise_name": "DB Bench",
      "garmin_name": "Dumbbell Bench Press"
    },
    {
      "exercise_name": "KB Swing",
      "garmin_name": "Kettlebell Swing"
    },
    {
      "exercise_name": "BB Squat",
      "garmin_name": "Back Squat"
    },
    {
      "exercise_name": "Pull Ups",
      "garmin_name": "Pull-Up"
    },
    {
      "exercise_name": "Push Ups",
      "garmin_name": "Push-Up"
    }
  ]
}
```

### Endpoint: `GET /mappings/lookup/{exercise_name}`

**Request:** `GET /mappings/lookup/DB%20Bench`

**Response:**
```json
{
  "exercise_name": "DB Bench",
  "mapped_to": "Dumbbell Bench Press",
  "exists": true
}
```

**Request:** `GET /mappings/lookup/Unknown%20Exercise`

**Response:**
```json
{
  "exercise_name": "Unknown Exercise",
  "mapped_to": null,
  "exists": false
}
```

### Endpoint: `GET /mappings/popularity/stats`

**Response:**
```json
{
  "total_mappings": 1250,
  "unique_exercises": 342,
  "most_popular_exercises": [
    {
      "exercise_name": "DB Bench",
      "mapping_count": 45,
      "top_mapping": "Dumbbell Bench Press"
    },
    {
      "exercise_name": "Squat",
      "mapping_count": 38,
      "top_mapping": "Squat"
    },
    {
      "exercise_name": "KB Swing",
      "mapping_count": 32,
      "top_mapping": "Kettlebell Swing"
    }
  ],
  "stats_by_category": {
    "strength": 850,
    "cardio": 250,
    "hiit": 150
  }
}
```

### Endpoint: `GET /mappings/popularity/{exercise_name}`

**Request:** `GET /mappings/popularity/DB%20Bench`

**Response:**
```json
{
  "exercise_name": "DB Bench",
  "popular_mappings": [
    {
      "garmin_name": "Dumbbell Bench Press",
      "count": 45,
      "percentage": 90.0
    },
    {
      "garmin_name": "Bench Press",
      "count": 3,
      "percentage": 6.0
    },
    {
      "garmin_name": "Incline Dumbbell Bench Press",
      "count": 2,
      "percentage": 4.0
    }
  ]
}
```

---

## Settings Examples

### Endpoint: `GET /settings/defaults`

**Response:**
```json
{
  "distance_handling": "lap",
  "default_exercise_value": "lap",
  "ignore_distance": true
}
```

### Endpoint: `PUT /settings/defaults`

**Request:**
```json
{
  "distance_handling": "distance",
  "default_exercise_value": "button",
  "ignore_distance": false
}
```

**Response:**
```json
{
  "message": "Settings updated successfully",
  "settings": {
    "distance_handling": "distance",
    "default_exercise_value": "button",
    "ignore_distance": false
  }
}
```

---

## Complete Workflow Example

### Scenario: User imports a complex workout and needs to review exercises

**Step 1: Validate the workout**
```bash
POST /workflow/validate
```

**Request:**
```json
{
  "blocks_json": {
    "title": "Complex Multi-Block Workout",
    "source": "image:workout.png",
    "blocks": [
      {
        "label": "Warm-up",
        "structure": "2 rounds",
        "rest_between_sec": 30,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 2,
        "exercises": [
          {
            "name": "DB Bench Press",
            "sets": 2,
            "reps": 10,
            "reps_range": null,
            "duration_sec": null,
            "rest_sec": 30,
            "distance_m": null,
            "distance_range": null,
            "type": "strength"
          }
        ],
        "supersets": []
      },
      {
        "label": "Main Workout",
        "structure": "4 sets",
        "rest_between_sec": 90,
        "time_work_sec": null,
        "default_reps_range": null,
        "default_sets": 4,
        "exercises": [],
        "supersets": [
          {
            "exercises": [
              {
                "name": "UNKNOWN EXERCISE",
                "sets": 4,
                "reps": 8,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              },
              {
                "name": "SOME TYPE OF SQUAT",
                "sets": 4,
                "reps": 12,
                "reps_range": null,
                "duration_sec": null,
                "rest_sec": null,
                "distance_m": null,
                "distance_range": null,
                "type": "strength"
              }
            ],
            "rest_between_sec": 60
          }
        ]
      }
    ]
  }
}
```

**Response:**
```json
{
  "total_exercises": 3,
  "validated_exercises": [
    {
      "original_name": "DB Bench Press",
      "mapped_to": "Dumbbell Bench Press",
      "confidence": 1.0,
      "description": "lap | DB Bench Press x8",
      "block": "Main Workout",
      "location": "exercises[0]",
      "status": "valid",
      "suggestions": {
        "similar": [
          {
            "name": "Dumbbell Bench Press",
            "score": 1.0,
            "normalized": "dumbbell bench press"
          }
        ],
        "by_type": [],
        "category": null,
        "needs_user_search": false
      }
    }
  ],
  "needs_review": [
    {
      "original_name": "SOME TYPE OF SQUAT",
      "mapped_to": "Squat",
      "confidence": 0.75,
      "description": "lap | SOME TYPE OF SQUAT x12",
      "block": "Main Workout",
      "location": "exercises[1]",
      "status": "needs_review",
      "suggestions": {
        "similar": [
          {
            "name": "Squat",
            "score": 0.85,
            "normalized": "squat"
          },
          {
            "name": "Air Squat",
            "score": 0.75,
            "normalized": "air squat"
          }
        ],
        "by_type": [
          {
            "name": "Air Squat",
            "score": 0.75,
            "normalized": "air squat",
            "keyword": "squat"
          }
        ],
        "category": "squat",
        "needs_user_search": false
      }
    }
  ],
  "unmapped_exercises": [
    {
      "original_name": "UNKNOWN EXERCISE",
      "mapped_to": null,
      "confidence": 0.0,
      "description": "lap | UNKNOWN EXERCISE x10",
      "block": "Main Workout",
      "location": "exercises[2]",
      "status": "needs_review",
      "suggestions": {
        "similar": [],
        "by_type": [],
        "category": null,
        "needs_user_search": true
      }
    }
  ],
  "can_proceed": false
}
```

**Step 2: Get suggestions for problematic exercises**

For "UNKNOWN EXERCISE":
```bash
POST /exercise/suggest
```
```json
{
  "exercise_name": "UNKNOWN EXERCISE",
  "include_similar_types": true
}
```
→ Returns `needs_user_search: true`

For "SOME TYPE OF SQUAT":
```bash
POST /exercise/suggest
```
```json
{
  "exercise_name": "SOME TYPE OF SQUAT",
  "include_similar_types": true
}
```
→ Returns list of squat variations

**Step 3: User adds mapping for unknown exercise**
```bash
POST /mappings/add
```
```json
{
  "exercise_name": "UNKNOWN EXERCISE",
  "garmin_name": "Custom Exercise Name"
}
```

**Step 4: Process the workout**
```bash
POST /workflow/process?auto_proceed=true
```
→ Returns YAML with all exercises mapped

---

## Notes for Figma

1. **Copy JSON blocks** - Each example is a complete, valid JSON that can be copied directly
2. **Test endpoints** - Use these examples with your running API server at `http://localhost:8000`
3. **Response formats** - All responses match the actual API structure
4. **Edge cases** - Examples include null values, ranges, and complex nested structures
5. **Real-world data** - Based on actual workout data from your test files

---

## Quick Reference

**Base URL:** `http://localhost:8000`

**Key Endpoints:**
- `POST /map/auto-map` - Quick conversion (recommended)
- `POST /workflow/validate` - Check before converting
- `POST /workflow/process` - Validate + convert
- `POST /exercise/suggest` - Get alternatives
- `POST /mappings/add` - Save custom mappings

**Test with curl:**
```bash
curl -X POST http://localhost:8000/map/auto-map \
  -H "Content-Type: application/json" \
  -d @test_hiit_workout.json
```
