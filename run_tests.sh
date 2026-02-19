#!/bin/bash
# Helper script to run tests with pytest-watch

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run pytest-watch with default options
echo "Starting pytest-watch... Tests will run automatically on file changes."
echo "Press Ctrl+C to stop."
echo ""
ptw -- -v --tb=short
