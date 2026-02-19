from shared.schemas.cir import CIR

from .match import classify

from .normalize import normalize



def canonicalize(cir: CIR, resolver=lambda _norm: None):

    for block in cir.workout.blocks:

        for ex in block.items:

            raw_norm = normalize(ex.name)

            cached = resolver(raw_norm)

            if cached:

                ex.canonical_name = cached

                continue

            result = classify(ex.name)

            ex.canonical_name = result["canonical"] if result["status"] != "unknown" else None

    return cir
