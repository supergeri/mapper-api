# Mapper API Tests

## Structure

```
tests/
├── unit/                   # Unit tests for individual components
│   ├── test_canonicalize.py
│   ├── test_catalog.py
│   ├── test_cir_to_garmin.py
│   ├── test_ingest_to_cir.py
│   ├── test_match.py
│   └── test_normalize.py
├── integration/            # Integration and API tests
├── golden/                # Golden/snapshot tests
├── contract/               # Contract tests
└── e2e/                   # End-to-end tests
```

## Running Tests

### Using Markers (Recommended)

Pytest markers allow selective test execution:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only golden tests
pytest -m golden

# Run only contract tests
pytest -m contract

# Run only e2e tests
pytest -m e2e
```

### Combining Markers

```bash
# Run unit OR golden tests (fast PR subset)
pytest -m "unit or golden or contract"

# Run all except e2e (skip slow tests)
pytest -m "not e2e"

# Run unit AND integration
pytest -m "unit and integration"
```

### Running Specific Test Directories

```bash
# Run all tests
pytest tests/

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run API tests
bash tests/integration/test_api_blocks.sh
python3 tests/integration/test_api_full.py

# Run with coverage
pytest tests/ --cov=backend --cov-report=html
```

## Marker Descriptions

| Marker | Description |
|--------|-------------|
| `unit` | Pure logic tests with no external dependencies (fast, isolated) |
| `golden` | Snapshot tests for export output validation (deterministic output comparison) |
| `integration` | Tests using FastAPI TestClient with fake repositories |
| `contract` | API response shape and OpenAPI schema validation tests |
| `e2e` | End-to-end tests hitting real services (optional, nightly runs only) |

## CI Configuration

For PRs, run the fast subset:
```bash
pytest -m "unit or golden or contract" --tb=short
```

For nightly/full runs:
```bash
pytest -m "not e2e" --tb=short
```

For complete CI:
```bash
pytest --tb=short
```

## Test Data

Test JSON and YAML files in `tests/integration/` are used as:
- Input payloads for API tests
- Expected output comparisons
- Workflow test data
