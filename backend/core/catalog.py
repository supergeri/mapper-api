import yaml, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

CAT = yaml.safe_load((ROOT / "shared/dictionaries/canonical_exercises.yaml").read_text())



def all_synonyms():

    for item in CAT:

        yield item["canonical"], item.get("synonyms", []) + [item["canonical"]]



def lookup(canonical):

    return next((c for c in CAT if c["canonical"] == canonical), None)
