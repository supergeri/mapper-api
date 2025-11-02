from fastapi import FastAPI

from pydantic import BaseModel

from backend.adapters.ingest_to_cir import to_cir

from backend.core.canonicalize import canonicalize

from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml



app = FastAPI()



class IngestPayload(BaseModel):

    ingest_json: dict



@app.post("/map/final")

def map_final(p: IngestPayload):

    cir = canonicalize(to_cir(p.ingest_json))

    return {"yaml": to_garmin_yaml(cir)}

