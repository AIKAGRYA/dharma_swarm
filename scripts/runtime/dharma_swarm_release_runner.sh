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

# Canonicalize a file path, following file symlinks (macOS bash 3.2 safe;
# `pwd -P` alone canonicalizes only the parent directory, so a symlinked
# interpreter FILE would otherwise escape the containment check below).
resolve_file() {
    local target="$1" link hops=0
    while [[ -L "${target}" ]]; do
        hops=$((hops + 1))
        [[ "${hops}" -gt 40 ]] && return 1
        link="$(readlink "${target}")" || return 1
        case "${link}" in
            /*) target="${link}" ;;
            *) target="$(dirname "${target}")/${link}" ;;
        esac
    done
    local dir
    dir="$(cd "$(dirname "${target}")" 2>/dev/null && pwd -P)" || return 1
    printf '%s/%s' "${dir}" "$(basename "${target}")"
}

verify_only=false
runtime_command="orchestrate-live"
runtime_args=()
case "${1-}" in
    "")
        ;;
    --verify-only)
        [[ "$#" -eq 1 ]] || fail "--verify-only accepts no arguments"
        verify_only=true
        ;;
    orchestrate-live)
        shift
        [[ "$#" -eq 0 ]] || fail "orchestrate-live accepts no arguments"
        ;;
    a2a-inbox-bridge)
        runtime_command="a2a-inbox-bridge"
        shift
        runtime_args=("$@")
        ;;
    codex-composer-semantic-responder)
        runtime_command="codex-composer-semantic-responder"
        shift
        runtime_args=("$@")
        ;;
    governed-patch-responder)
        runtime_command="governed-patch-responder"
        shift
        runtime_args=("$@")
        ;;
    governed-patch-foundry-verifier)
        runtime_command="governed-patch-foundry-verifier"
        shift
        runtime_args=("$@")
        ;;
    governed-patch-vibe-verifier)
        runtime_command="governed-patch-vibe-verifier"
        shift
        runtime_args=("$@")
        ;;
    *)
        fail "unsupported command"
        ;;
esac

# Preserve only the selected verifier key locator as a non-exported shell
# variable. Provider credentials are reloaded from the canonical vault only
# after admission; neither role key nor inherited secret-shaped variables may
# remain in the parent environment while unadmitted release code executes.
foundry_verifier_key_file="${DHARMA_FOUNDRY_VERIFIER_KEY_FILE-}"
vibe_verifier_key_file="${DHARMA_VIBE_VERIFIER_KEY_FILE-}"
while IFS= read -r environment_name; do
    case "${environment_name}" in
        *_API_KEY|*_AUTH_TOKEN|*_TOKEN|*_SECRET_KEY|*_SECRET_ACCESS_KEY|\
        DHARMA_FOUNDRY_VERIFIER_KEY_FILE|DHARMA_VIBE_VERIFIER_KEY_FILE)
            unset "${environment_name}"
            ;;
    esac
done < <(compgen -e)
unset environment_name

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
# The FINAL executable must live inside the release too: a `.venv/bin/python`
# symlink pointing at an outside interpreter would otherwise run before (and
# perform) provenance admission. Immutable releases carry a copied
# interpreter (venv --copies); a symlinked one fails loudly here.
runtime_python="$(resolve_file "${runtime_python}")" \
    || fail "release interpreter target cannot be resolved"
case "${runtime_python}" in
    "${release_root}"/*) ;;
    *) fail "release interpreter resolves outside the release root" ;;
esac
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
    "GIT_NO_REPLACE_OBJECTS=1"
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

# The release-local interpreter and admission module are themselves still
# unadmitted at this point. Give that process no provider credentials, runtime
# configuration, or verifier key paths. The parent shell retains its environment
# so the selected admitted role can receive only its intended capabilities later.
admission_env=(
    env -i
    "HOME=/nonexistent"
    "PATH=/usr/bin:/bin"
    "TMPDIR=/tmp"
    "PYTHONDONTWRITEBYTECODE=1"
    "PYTHONNOUSERSITE=1"
)
"${admission_env[@]}" \
    "${runtime_python}" -B -I -S "${release_root}/dharma_swarm/runtime_admission.py" \
    --repo "${release_root}" \
    --expected-commit "${expected_commit}"

if [[ "${verify_only}" == "true" ]]; then
    exit 0
fi

cd "${release_root}"
case "${runtime_command}" in
    orchestrate-live)
        # The autonomous runtime owns provider routing and therefore loads the
        # versioned environment only after provenance admission.
        # shellcheck disable=SC1090
        source "${runtime_env_helper}"
        exec env \
            DHARMA_RUNTIME_EXPECTED_COMMIT="${expected_commit}" \
            PYTHONDONTWRITEBYTECODE=1 \
            PYTHONNOUSERSITE=1 \
            "${runtime_python}" -B -I -m \
            dharma_swarm.runtime_release_entrypoint orchestrate-live
        ;;
    a2a-inbox-bridge)
        # The transport bridge needs no model/provider credentials. Give it a
        # minimal environment rather than sourcing the runtime key bundle.
        bridge_env=(
            env -i
            "HOME=${HOME:?HOME is required}"
            "PATH=${safe_path}"
            "TMPDIR=${TMPDIR:-/tmp}"
            "DHARMA_RELEASE_ROOT=${release_root}"
            "DHARMA_RUNTIME_EXPECTED_COMMIT=${expected_commit}"
            "DHARMA_PYTHON=${runtime_python}"
            "PYTHONDONTWRITEBYTECODE=1"
            "PYTHONNOUSERSITE=1"
            "PYTHONUNBUFFERED=1"
        )
        if [[ -n "${DHARMA_STATE_DIR-}" ]]; then
            bridge_env+=("DHARMA_STATE_DIR=${DHARMA_STATE_DIR}")
        fi
        if [[ -n "${DHARMA_HOME-}" ]]; then
            bridge_env+=("DHARMA_HOME=${DHARMA_HOME}")
        fi
        exec "${bridge_env[@]}" \
            "${runtime_python}" -B -I -m \
            dharma_swarm.runtime_release_entrypoint \
            a2a-inbox-bridge "${runtime_args[@]}"
        ;;
    codex-composer-semantic-responder)
        # The semantic responder needs provider credentials. Load them only
        # after the immutable release has passed provenance admission, then
        # dispatch the one admitted responder through the release entrypoint.
        # shellcheck disable=SC1090
        source "${runtime_env_helper}"
        exec env \
            DHARMA_RELEASE_ROOT="${release_root}" \
            DHARMA_RUNTIME_EXPECTED_COMMIT="${expected_commit}" \
            PYTHONDONTWRITEBYTECODE=1 \
            PYTHONNOUSERSITE=1 \
            PYTHONUNBUFFERED=1 \
            "${runtime_python}" -B -I -m \
            dharma_swarm.runtime_release_entrypoint \
            codex-composer-semantic-responder "${runtime_args[@]}"
        ;;
    governed-patch-responder)
        # Candidate authorship uses the admitted provider environment. Verifier
        # key locators remain stripped: this responder has no authority to sign
        # either independent verification role.
        # shellcheck disable=SC1090
        source "${runtime_env_helper}"
        exec env \
            DHARMA_RELEASE_ROOT="${release_root}" \
            DHARMA_RUNTIME_EXPECTED_COMMIT="${expected_commit}" \
            PYTHONDONTWRITEBYTECODE=1 \
            PYTHONNOUSERSITE=1 \
            PYTHONUNBUFFERED=1 \
            "${runtime_python}" -B -I -m \
            dharma_swarm.runtime_release_entrypoint \
            governed-patch-responder "${runtime_args[@]}"
        ;;
    governed-patch-foundry-verifier)
        # Foundry runs after release admission without provider credentials and
        # receives only its own key path. The Vibe key is deliberately absent.
        [[ -n "${foundry_verifier_key_file}" ]] \
            || fail "DHARMA_FOUNDRY_VERIFIER_KEY_FILE is required"
        verifier_env=(
            env -i
            "HOME=${HOME:?HOME is required}"
            "PATH=${safe_path}"
            "TMPDIR=${TMPDIR:-/tmp}"
            "DHARMA_RELEASE_ROOT=${release_root}"
            "DHARMA_RUNTIME_EXPECTED_COMMIT=${expected_commit}"
            "DHARMA_FOUNDRY_VERIFIER_KEY_FILE=${foundry_verifier_key_file}"
            "PYTHONDONTWRITEBYTECODE=1"
            "PYTHONNOUSERSITE=1"
            "PYTHONUNBUFFERED=1"
        )
        if [[ -n "${DHARMA_STATE_DIR-}" ]]; then
            verifier_env+=("DHARMA_STATE_DIR=${DHARMA_STATE_DIR}")
        fi
        if [[ -n "${DHARMA_HOME-}" ]]; then
            verifier_env+=("DHARMA_HOME=${DHARMA_HOME}")
        fi
        exec "${verifier_env[@]}" \
            "${runtime_python}" -B -I -m \
            dharma_swarm.runtime_release_entrypoint \
            governed-patch-foundry-verifier "${runtime_args[@]}"
        ;;
    governed-patch-vibe-verifier)
        # Vibe has an independent environment and key path. It cannot inherit
        # the Foundry key or model/provider credentials through this boundary.
        [[ -n "${vibe_verifier_key_file}" ]] \
            || fail "DHARMA_VIBE_VERIFIER_KEY_FILE is required"
        verifier_env=(
            env -i
            "HOME=${HOME:?HOME is required}"
            "PATH=${safe_path}"
            "TMPDIR=${TMPDIR:-/tmp}"
            "DHARMA_RELEASE_ROOT=${release_root}"
            "DHARMA_RUNTIME_EXPECTED_COMMIT=${expected_commit}"
            "DHARMA_VIBE_VERIFIER_KEY_FILE=${vibe_verifier_key_file}"
            "PYTHONDONTWRITEBYTECODE=1"
            "PYTHONNOUSERSITE=1"
            "PYTHONUNBUFFERED=1"
        )
        if [[ -n "${DHARMA_STATE_DIR-}" ]]; then
            verifier_env+=("DHARMA_STATE_DIR=${DHARMA_STATE_DIR}")
        fi
        if [[ -n "${DHARMA_HOME-}" ]]; then
            verifier_env+=("DHARMA_HOME=${DHARMA_HOME}")
        fi
        exec "${verifier_env[@]}" \
            "${runtime_python}" -B -I -m \
            dharma_swarm.runtime_release_entrypoint \
            governed-patch-vibe-verifier "${runtime_args[@]}"
        ;;
    *)
        fail "unsupported command"
        ;;
esac
