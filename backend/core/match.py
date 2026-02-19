from rapidfuzz import fuzz

from .normalize import normalize

from .catalog import all_synonyms, lookup



def suggest(raw_name: str, top_k: int = 5):

    q = normalize(raw_name)

    scores = {}

    for canonical, syns in all_synonyms():

        best = 0.0

        for s in syns:

            sc = fuzz.token_set_ratio(q, normalize(s)) / 100.0

            best = max(best, sc)

        meta = lookup(canonical)

        for equip in (meta.get("equipment") or []):

            if equip in q: best += 0.03

        for mod in (meta.get("modifiers") or []):

            if mod in q: best += 0.03

        scores[canonical] = min(best, 1.0)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return ranked[:top_k]



def classify(raw_name: str, accept=0.85, review=0.60):

    ranked = suggest(raw_name)

    canonical, score = ranked[0]

    if score >= accept: status = "auto"

    elif score >= review: status = "review"

    else: status = "unknown"

    return {"canonical": canonical, "score": score, "status": status, "alternates": ranked}
