import re, yaml, pathlib



ROOT = pathlib.Path(__file__).resolve().parents[2]

DICT = yaml.safe_load((ROOT / "shared/dictionaries/normalization.yaml").read_text())



def normalize(text: str) -> str:

    t = text.lower()

    for k,v in DICT["expand"].items():

        t = re.sub(rf"\b{k}\b", v, t)

    t = re.sub(r"[-_/]", " ", t)

    t = re.sub(r"[^\w\s]", "", t)

    words = [w for w in t.split() if w not in set(DICT["stopwords"])]

    for i,w in enumerate(words):

        if w in DICT["plural_to_singular"]:

            words[i] = DICT["plural_to_singular"][w]

    return " ".join(words).strip()
