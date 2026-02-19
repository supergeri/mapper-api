FROM python:3.11-slim

WORKDIR /app

# Copy requirements if it exists, otherwise we'll install common dependencies
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; else pip install --no-cache-dir fastapi uvicorn pydantic pyyaml rapidfuzz; fi

# Copy application code
COPY . .

# Expose port 8001
EXPOSE 8001

# Install shared fitfiletool package if mounted (done at runtime via entrypoint)
# The package is mounted at /amakaflow-fitfiletool via docker-compose

# Run the FastAPI application (AMA-377: use main module entry point)
CMD ["sh", "-c", "pip install -e /amakaflow-fitfiletool 2>/dev/null || true; uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload"]
