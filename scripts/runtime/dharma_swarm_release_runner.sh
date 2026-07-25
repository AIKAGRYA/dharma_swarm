#!/usr/bin/env bash
#
# Stable launchd boundary for an immutable dharma_swarm release worktree.
# Install this file outside every checkout, then pin both release root and
# exact commit in the launchd environment.

set -euo pipefail

fail() {
    echo "release runner: $1" >&2
    exit 78
}

verify_only=false
if [[ "${1-}" == "--verify-only" ]]; then
    verify_only=true
elif [[ "$#" -ne 0 ]]; then
    fail "unsupported argument"
fi

release_root="${DHARMA_RELEASE_ROOT:?DHARMA_RELEASE_ROOT is required}"
expected_commit="${DHARMA_RUNTIME_EXPECTED_COMMIT-}"
if [[ ! "${expected_commit}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    fail "DHARMA_RUNTIME_EXPECTED_COMMIT must be a full 40-character commit SHA"
fi

release_root="$(cd "${release_root}" 2>/dev/null && pwd -P)" || {
    fail "DHARMA_RELEASE_ROOT is unavailable"
}

runtime_python_input="${DHARMA_PYTHON:-${release_root}/.venv/bin/python}"
runtime_python_dir="$(
    cd "$(dirname "${runtime_python_input}")" 2>/dev/null && pwd -P
)" || fail "dedicated release interpreter directory is unavailable"
runtime_python="${runtime_python_dir}/$(basename "${runtime_python_input}")"

if [[ "${runtime_python_dir}" != "${release_root}/.venv/bin" ]] \
    || [[ "$(basename "${runtime_python}")" != "python" ]]; then
    fail "DHARMA_PYTHON must be the release-local .venv/bin/python"
fi
if [[ ! -x "${runtime_python}" ]]; then
    fail "dedicated release interpreter is not executable"
fi

runtime_env_helper="${release_root}/scripts/load_runtime_env.sh"
if [[ ! -f "${runtime_env_helper}" ]]; then
    fail "versioned runtime environment loader is missing"
fi

safe_path="${runtime_python%/*}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
git_bin="/usr/bin/git"
if [[ ! -x "${git_bin}" ]]; then
    fail "trusted Git executable is unavailable"
fi
git_env=(
    env -i
    "PATH=${safe_path}"
    "GIT_CONFIG_GLOBAL=/dev/null"
    "GIT_CONFIG_NOSYSTEM=1"
    "GIT_OPTIONAL_LOCKS=0"
)
observed_root="$(
    "${git_env[@]}" "${git_bin}" -c core.fsmonitor=false \
        -C "${release_root}" rev-parse --show-toplevel 2>/dev/null
)" || fail "Git provenance root is unavailable"
observed_root="$(cd "${observed_root}" 2>/dev/null && pwd -P)" \
    || fail "Git provenance root cannot be canonicalized"
if [[ "${observed_root}" != "${release_root}" ]]; then
    fail "DHARMA_RELEASE_ROOT must be the Git toplevel"
fi
tracked_status="$(
    "${git_env[@]}" "${git_bin}" -c core.fsmonitor=false \
        -C "${release_root}" status --porcelain=v1 \
        --untracked-files=all --ignore-submodules=none
)" || fail "Git cleanliness probe failed"
if [[ -n "${tracked_status}" ]]; then
    fail "release checkout has uncommitted paths"
fi
ignored_imports="$(
    "${git_env[@]}" "${git_bin}" -c core.fsmonitor=false \
        -C "${release_root}" ls-files --others --ignored --exclude-standard -- \
        ":(top,glob)sitecustomize.py[co]" \
        ":(top,glob)usercustomize.py[co]" \
        ":(top,glob)dharma_swarm/**/*.py[co]"
)" || fail "ignored import-artifact probe failed"
if [[ -n "${ignored_imports}" ]]; then
    fail "release checkout has ignored import bytecode"
fi

export PATH="${safe_path}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

"${runtime_python}" -B -I -S "${release_root}/dharma_swarm/runtime_admission.py" \
    --repo "${release_root}" \
    --expected-commit "${expected_commit}"

if [[ "${verify_only}" == "true" ]]; then
    exit 0
fi

cd "${release_root}"
# shellcheck disable=SC1090
source "${runtime_env_helper}"

exec env \
    DHARMA_RUNTIME_EXPECTED_COMMIT="${expected_commit}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    "${runtime_python}" -B -I -m dharma_swarm.dgc_cli orchestrate-live
