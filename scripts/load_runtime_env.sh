#!/usr/bin/env bash
# Runtime env loader — THIN WRAPPER over the one canonical loader:
#   dharma_swarm.api_keys.bootstrap_runtime_env()
#   (via dharma_swarm/runtime_env_loader.py emit-exports)
#
# History: this script used to be a second, parallel loader with its own
# `set -a` last-wins precedence, its own keychain step, and its own
# (narrower) alias table — diverging from the Python loader's
# never-overwrite semantics and full ENV_ALIASES table. Four loaders and
# two precedence semantics was the root cause of cross-seat key confusion
# (audit 2026-07-03). Now there is ONE loader with ONE semantic
# (never-overwrite, first writer wins); this wrapper just projects its
# result into the calling shell. Keychain lookup and alias normalization
# live in the Python loader.

if [[ -n "${DHARMA_RUNTIME_ENV_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi

_DHARMA_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"

_dharma_exports="$(
    cd "$_DHARMA_REPO_ROOT" 2>/dev/null && \
    PYTHONPATH="$_DHARMA_REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -m dharma_swarm.runtime_env_loader emit-exports 2>/dev/null
)" || _dharma_exports=""

if [[ -n "$_dharma_exports" ]]; then
    eval "$_dharma_exports"
    export DHARMA_RUNTIME_ENV_LOADED=1
else
    # Fallback (python unavailable/broken): source the same files the
    # canonical loader reads, in the same order. No keychain, no aliases —
    # any dharma python process will still run the full bootstrap lazily
    # in-process, so semantics converge once the app starts.
    for _dharma_envfile in "$HOME/.zshrc" "$HOME/.env" "$HOME/.dharma/.env" \
        "$HOME/.dharma/daemon.env" "$HOME/.dharma/agent_keys.env"; do
        if [[ "$_dharma_envfile" == "$HOME/.zshrc" ]]; then
            # only key-ish `export NAME=value` lines; never execute zshrc code
            if [[ -f "$_dharma_envfile" ]]; then
                eval "$(
                    grep -E '^export [A-Za-z_][A-Za-z0-9_]*=' "$_dharma_envfile" 2>/dev/null \
                        | grep -E '(API_KEY|BASE_URL|AUTH_TOKEN)' \
                        || true
                )"
            fi
        elif [[ -f "$_dharma_envfile" ]]; then
            set -a
            # shellcheck disable=SC1090
            source "$_dharma_envfile"
            set +a
        fi
    done
    unset _dharma_envfile
    export DHARMA_RUNTIME_ENV_LOADED=1
fi

unset _dharma_exports _DHARMA_REPO_ROOT
