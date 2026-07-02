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
  if [[ ! -x "${DHARMA_PYTHON}" ]]; then
    echo "error: DHARMA_PYTHON is not executable: ${DHARMA_PYTHON}" >&2
    exit 1
  fi
  PY="${DHARMA_PYTHON}"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY="${REPO_ROOT}/.venv/bin/python"
else
  PY=""
  while IFS= read -r line; do
    case "${line}" in
      worktree\ *)
        candidate="${line#worktree }/.venv/bin/python"
        if [[ -x "${candidate}" ]]; then
          PY="${candidate}"
          break
        fi
        ;;
    esac
  done < <(git worktree list --porcelain 2>/dev/null || true)
  if [[ -z "${PY}" ]]; then
    PY="$(command -v python3 || true)"
  fi
fi

if [[ -z "${PY}" ]]; then
  echo "error: no Python interpreter found; set DHARMA_PYTHON=/path/to/python" >&2
  exit 1
fi

cd "${REPO_ROOT}"
exec "${PY}" "${TARGET_SCRIPT}" "$@"
