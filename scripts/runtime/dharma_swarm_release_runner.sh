#!/usr/bin/env bash
#
# Stable launchd boundary for an immutable dharma_swarm release worktree.
# Install this file outside every checkout, then pin both release root and
# exact commit in the launchd environment.

set -euo pipefail

release_root="${DHARMA_RELEASE_ROOT:?DHARMA_RELEASE_ROOT is required}"
expected_commit="${DHARMA_RUNTIME_EXPECTED_COMMIT:?DHARMA_RUNTIME_EXPECTED_COMMIT is required}"

release_root="$(cd "${release_root}" 2>/dev/null && pwd -P)" || {
    echo "release runner: DHARMA_RELEASE_ROOT is unavailable" >&2
    exit 78
}

runtime_python="${DHARMA_PYTHON:-${release_root}/.venv/bin/python}"
case "${runtime_python}" in
    "${release_root}"/*) ;;
    *)
        echo "release runner: DHARMA_PYTHON must live inside DHARMA_RELEASE_ROOT" >&2
        exit 78
        ;;
esac

if [[ ! -x "${runtime_python}" ]]; then
    echo "release runner: dedicated release interpreter is not executable" >&2
    exit 78
fi

runtime_env_helper="${release_root}/scripts/load_runtime_env.sh"
if [[ ! -f "${runtime_env_helper}" ]]; then
    echo "release runner: versioned runtime environment loader is missing" >&2
    exit 78
fi

export PATH="${runtime_python%/*}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${release_root}"

"${runtime_python}" -m dharma_swarm.runtime_admission \
    --repo "${release_root}" \
    --expected-commit "${expected_commit}"

cd "${release_root}"
# shellcheck disable=SC1090
source "${runtime_env_helper}"

exec env \
    DHARMA_RUNTIME_EXPECTED_COMMIT="${expected_commit}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="${release_root}" \
    "${runtime_python}" -m dharma_swarm.dgc_cli orchestrate-live
