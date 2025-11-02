from shared.schemas.cir import CIR, Workout, Block, Exercise



def to_cir(ingest_json: dict) -> CIR:

    items = []

    for e in ingest_json["exercises"]:

        items.append(Exercise(

            name=e["name"],

            sets=e.get("sets"),

            reps=e.get("reps"),

            duration_seconds=e.get("duration_seconds"),

            rest_seconds=e.get("rest"),

            equipment=e.get("equipment", []),

            modifiers=e.get("modifiers", []),

            tempo=e.get("tempo")

        ))

    return CIR(workout=Workout(

        title=ingest_json.get("title","Imported Workout"),

        notes=ingest_json.get("notes"),

        tags=ingest_json.get("tags", []),

        blocks=[Block(type="straight", rounds=1, items=items)]

    ))

