#!/usr/bin/env bash
set -euo pipefail

# Simple helper to follow mapper-api logs and highlight Garmin export debug lines.

SERVICE_NAME="mapper-api"

echo "🔍 Tailing Docker logs for ${SERVICE_NAME}…"
echo "   Press Ctrl+C to stop."
echo

# If docker compose v2 is available, prefer it
if command -v docker compose >/dev/null 2>&1; then
  docker compose logs -f "${SERVICE_NAME}"
else
  docker-compose logs -f "${SERVICE_NAME}"
fi
