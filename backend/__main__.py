"""
Entry point for running the application with `python -m backend.main`.

AMA-355: Introduce app factory pattern
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)
