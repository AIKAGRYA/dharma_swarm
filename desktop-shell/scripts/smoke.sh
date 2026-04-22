#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_SHELL_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd -- "${DESKTOP_SHELL_DIR}/.." && pwd)"

API_URL="${DHARMA_API_URL:-http://127.0.0.1:8420}"
WEB_URL="${DHARMA_WEB_URL:-http://127.0.0.1:3420}"
ROUTE="${DHARMA_DESKTOP_ROUTE:-/dashboard/command-post}"

if [[ "${ROUTE}" != /dashboard* ]]; then
  echo "DHARMA_DESKTOP_ROUTE must start with /dashboard" >&2
  exit 2
fi

echo "Starting dashboard runtime..."
if [[ "${DHARMA_SMOKE_SKIP_START:-0}" != "1" ]]; then
  if ! bash "${REPO_ROOT}/scripts/dashboard_ctl.sh" start >/dev/null; then
    echo "Dashboard runtime failed to start. Try bash scripts/dashboard_ctl.sh status or logs." >&2
    exit 1
  fi
else
  echo "Skipping runtime startup; probing current services only."
fi

echo "Checking API health at ${API_URL}/api/health ..."
if ! curl -fsS --max-time 5 "${API_URL}/api/health" >/dev/null; then
  echo "API health check failed at ${API_URL}/api/health" >&2
  exit 1
fi

echo "Checking dashboard route at ${WEB_URL}${ROUTE} ..."
if ! curl -fsS --max-time 5 "${WEB_URL}${ROUTE}" >/dev/null; then
  echo "Dashboard route check failed at ${WEB_URL}${ROUTE}" >&2
  exit 1
fi

echo "Desktop shell smoke passed for ${WEB_URL}${ROUTE}"
