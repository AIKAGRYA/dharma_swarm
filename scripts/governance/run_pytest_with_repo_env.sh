#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

if [[ -n "${DHARMA_PYTHON:-}" && -x "${DHARMA_PYTHON}" ]]; then
  PY="${DHARMA_PYTHON}"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY="${REPO_ROOT}/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

if ! "${PY}" -c "import pytest" >/dev/null 2>&1; then
  echo "error: pytest is not importable with interpreter: ${PY}" >&2
  echo "set DHARMA_PYTHON=/path/to/python or create ${REPO_ROOT}/.venv" >&2
  exit 1
fi

exec "${PY}" -m pytest "$@"
