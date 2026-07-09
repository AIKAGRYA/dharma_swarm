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
  # Git worktrees have no REPO_ROOT/.venv (the venv lives in the main checkout).
  # Resolve it via the shared git common dir before falling back to system python3.
  PY=""
  common_dir="$(git -C "${REPO_ROOT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
  if [[ -n "${common_dir}" ]]; then
    main_root="$(cd -- "$(dirname -- "${common_dir}")" && pwd -P)"
    if [[ -x "${main_root}/.venv/bin/python" ]]; then
      PY="${main_root}/.venv/bin/python"
    fi
  fi
  if [[ -z "${PY}" ]]; then
    PY="$(command -v python3 || true)"
  fi
fi

if [[ -z "${PY}" ]]; then
  echo "error: no Python interpreter found; set DHARMA_PYTHON=/path/to/python" >&2
  exit 1
fi

# Fail loud on an interpreter too old to parse this 3.11+ codebase, instead of
# emitting a bogus SyntaxError that masquerades as a gate failure and drives a
# blanket --no-verify (which voids every hook). macOS ships /usr/bin/python3=3.9.
if ! "${PY}" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null; then
  ver="$("${PY}" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo '?')"
  echo "error: ${PY} is Python ${ver}; this repo requires >=3.11." >&2
  echo "       Set DHARMA_PYTHON to a 3.11+ interpreter (e.g. the main checkout's .venv/bin/python)." >&2
  exit 1
fi

cd "${REPO_ROOT}"
exec "${PY}" "${TARGET_SCRIPT}" "$@"
