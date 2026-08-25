#!/bin/sh
set -eu

FOUNDRY_REPO_ROOT="${FOUNDRY_REPO_ROOT:-/opt/dharma-foundry/current}"
FOUNDRY_STATE_ROOT="${FOUNDRY_STATE_ROOT:-/var/lib/sublimation-foundry}"
FOUNDRY_PYTHON="${FOUNDRY_PYTHON:-${FOUNDRY_REPO_ROOT}/.venv/bin/python}"
FOUNDRY_EXPECTED_SHA="${FOUNDRY_EXPECTED_SHA:-}"

exec "${FOUNDRY_PYTHON}" \
  "${FOUNDRY_REPO_ROOT}/scripts/foundry/foundry_status.py" \
  --repo-root "${FOUNDRY_REPO_ROOT}" \
  --state-root "${FOUNDRY_STATE_ROOT}" \
  --expected-sha "${FOUNDRY_EXPECTED_SHA}" \
  "$@"
