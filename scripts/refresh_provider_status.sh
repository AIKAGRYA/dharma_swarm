#!/usr/bin/env bash
# Refresh provider liveness and credit-health artifacts through the one loader.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_ENV_HELPER="${REPO_ROOT}/scripts/load_runtime_env.sh"

if [[ -f "$RUNTIME_ENV_HELPER" ]]; then
    # shellcheck disable=SC1090
    source "$RUNTIME_ENV_HELPER"
fi

STATE_DIR="${DHARMA_STATE_DIR:-${HOME}/.dharma}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

case "$STATE_DIR" in
    "~") STATE_DIR="$HOME" ;;
    "~/"*) STATE_DIR="${HOME}/${STATE_DIR#~/}" ;;
esac
LOG_DIR="${STATE_DIR}/logs"

mkdir -p "$LOG_DIR"

DKEYS_BIN="$(command -v dkeys 2>/dev/null || true)"
if [[ -z "$DKEYS_BIN" && -x "${HOME}/.dharma/bin/dkeys" ]]; then
    DKEYS_BIN="${HOME}/.dharma/bin/dkeys"
fi

if [[ -n "$DKEYS_BIN" ]]; then
    "$DKEYS_BIN" test >/dev/null
else
    echo "[refresh_provider_status] dkeys not found; skipping keys_status.json refresh" >&2
fi

cd "$REPO_ROOT"
"$PYTHON_BIN" scripts/check_provider_credits.py \
    --json \
    --output "${LOG_DIR}/provider_credits_latest.json"

echo "provider status refreshed:"
echo "  keys_status: ${STATE_DIR}/keys_status.json"
echo "  credits: ${LOG_DIR}/provider_credits_latest.json"
