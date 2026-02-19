import yaml, pathlib

from shared.schemas.cir import CIR



ROOT = pathlib.Path(__file__).resolve().parents[2]

GARMIN = yaml.safe_load((ROOT / "shared/dictionaries/garmin_map.yaml").read_text())



def step_from_ex(ex):

    can = ex.canonical_name

    m = GARMIN.get(can, None)

    if not m:

        return {"type":"exercise","exerciseName":f"Custom: {can or ex.name}",

                "sets":ex.sets,"repetitionValue":ex.reps,"rest":ex.rest_seconds}

    step = {"type":"exercise","exerciseName":m["name"],

            "sets":ex.sets,"repetitionValue":ex.reps,"rest":ex.rest_seconds}

    if "Incline" in (m.get("modifiers") or []) or "incline" in (ex.modifiers or []):

        step["position"] = "Incline"

    return step



def to_garmin_yaml(cir: CIR) -> str:

    steps = []

    for block in cir.workout.blocks:

        if block.type == "straight" and block.rounds == 1:

            for ex in block.items:

                steps.append(step_from_ex(ex))

        else:

            steps.append({

              "type": "circuit" if block.type in ("superset","circuit") else "repeat",

              "rounds": block.rounds,

              "steps": [step_from_ex(e) for e in block.items]

            })

    doc = {"workout": {"name": cir.workout.title, "sport": "strength",

                       "notes": cir.workout.notes, "steps": steps}}

    return yaml.safe_dump(doc, sort_keys=False)
