# Workout Canonical Mapper

[![Coverage](https://img.shields.io/badge/coverage-48%25-green)](https://github.com/supergeri/mapper-api/actions)

A Python application that converts workout data from OCR/ingest format to canonical exercise names and exports to Garmin YAML format.

## Features

- **Exercise Normalization**: Normalizes exercise names by expanding abbreviations, removing stopwords, and converting plural forms
- **Canonical Matching**: Uses fuzzy matching to map raw exercise names to canonical names from a dictionary
- **Garmin Export**: Converts workouts to Garmin-compatible YAML format
- **FastAPI REST API**: Web API endpoint for workout conversion
- **CLI Tool**: Command-line interface for batch processing

## Prerequisites

- Python 3.8+
- pip (Python package manager)

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/supergeri/workoutcanonicalmapper.git
   cd workoutcanonicalmapper
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install fastapi uvicorn pydantic pyyaml rapidfuzz python-slugify orjson pytest pytest-cov
   ```

## Garmin Export Debug Mode

When `GARMIN_EXPORT_DEBUG=true` is set for **mapper-api**, the backend will log detailed information about Garmin mapping:

- Exercise mapping pipeline logs (`=== GARMIN_EXPORT_STEP ===`)
- Category assignments (`=== GARMIN_CATEGORY_ASSIGN ===`)
- YAML export output (`=== GARMIN_EXPORT_YAML ===`)
- Sync payloads (`=== GARMIN_SYNC_PAYLOAD ===`)
- Follow-along vs YAML comparison logs

### How to enable

The Docker service for `mapper-api` is already configured to set:

```yaml
services:
  mapper-api:
    environment:
      GARMIN_EXPORT_DEBUG: "true"
```

### Viewing debug logs

To follow the mapper-api logs in real-time, use the helper script:

```bash
# From the mapper-api directory
./scripts/garmin-mapper-logs.sh

# Or using npm/yarn
npm run logs:garmin
```

This will tail the Docker logs for the mapper-api service. Press `Ctrl+C` to stop.

## Usage

### CLI Tool

Convert a workout JSON file to Garmin YAML:

```bash
python -m backend.cli sample/ocr.json -o output.yaml
```

Or output to stdout:

```bash
python -m backend.cli sample/ocr.json
```

### Start the API server

```bash
uvicorn backend.app:app --reload
```

The server will start on `http://localhost:8000`

## Database Migrations

This project uses Supabase for the database. Migrations can be run against both development and staging environments using the GitHub Actions workflow.

### Running Migrations via GitHub Actions

1. Go to the **Actions** tab in the repository
2. Select the **Database Migrations** workflow
3. Click **Run workflow**
4. Choose the target environment (`development` or `staging`)
5. Click **Run workflow** to execute

For detailed documentation, see [DATABASE.md](./DATABASE.md).
