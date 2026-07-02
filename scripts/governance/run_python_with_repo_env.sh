#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd -P)"

if [[ "$#" -lt 1 ]]; then
  echo "usage: $0 <script.py> [args...]" >&2
  exit 64
fi

TARGET_SCRIPT="$1"
shift
if [[ "${TARGET_SCRIPT}" != /* && -f "${REPO_ROOT}/${TARGET_SCRIPT}" ]]; then
  TARGET_SCRIPT="${REPO_ROOT}/${TARGET_SCRIPT}"
fi

if [[ -n "${DHARMA_PYTHON:-}" ]]; then
  if [[ "${DHARMA_PYTHON}" == */* ]]; then
    if [[ ! -x "${DHARMA_PYTHON}" ]]; then
      echo "error: DHARMA_PYTHON is not executable: ${DHARMA_PYTHON}" >&2
      exit 1
    fi
    PY="${DHARMA_PYTHON}"
  else
    PY="$(command -v "${DHARMA_PYTHON}" || true)"
  fi
  if [[ -z "${PY}" ]]; then
    echo "error: DHARMA_PYTHON is not executable: ${DHARMA_PYTHON}" >&2
    exit 1
  fi
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY="${REPO_ROOT}/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi

if [[ -z "${PY}" ]]; then
  echo "error: no Python interpreter found; set DHARMA_PYTHON=/path/to/python" >&2
  exit 1
fi

cd "${REPO_ROOT}"
exec "${PY}" "${TARGET_SCRIPT}" "$@"
