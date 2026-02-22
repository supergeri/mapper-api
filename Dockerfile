FROM python:3.11-slim

WORKDIR /app

# Copy requirements if it exists, otherwise we'll install common dependencies
# git required by pip packages (e.g. fit-tool from VCS)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; else pip install --no-cache-dir fastapi uvicorn pydantic pyyaml rapidfuzz; fi

# Copy application code
COPY . .

# Expose port 8001
EXPOSE 8001

# Install shared fitfiletool package if mounted (done at runtime via entrypoint)
# The package is mounted at /amakaflow-fitfiletool via docker-compose

# Run the FastAPI application (AMA-355: use main module entry point)
CMD ["sh", "-c", "pip install -e /amakaflow-fitfiletool 2>/dev/null || true; uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload"]
