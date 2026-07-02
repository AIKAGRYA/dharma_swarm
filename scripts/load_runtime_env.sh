#!/usr/bin/env bash
# Shared runtime env loader for launchd/daemon entrypoints.

if [[ -n "${DHARMA_RUNTIME_ENV_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi
export DHARMA_RUNTIME_ENV_LOADED=1

_load_env_file() {
    local envfile="$1"
    if [[ -f "$envfile" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$envfile"
        set +a
    fi
}

if [[ -f "$HOME/.zshrc" ]]; then
    eval "$(
        grep -E '^export ' "$HOME/.zshrc" 2>/dev/null \
            | grep -E '(API_KEY|BASE_URL|OPENROUTER|OLLAMA|GROQ|CEREBRAS|SILICONFLOW|KIMI|MOONSHOT|NIM_API_KEY|NVIDIA_NIM_API_KEY)' \
            || true
    )"
fi

for envfile in "$HOME/.env" "$HOME/.dharma/.env" "$HOME/.dharma/daemon.env" "$HOME/.dharma/agent_keys.env"; do
    _load_env_file "$envfile"
done

_load_keychain_var() {
    local var_name="$1"
    local account="$2"
    local service="$3"
    local current="${!var_name:-}"
    local value=""

    if [[ -n "$current" ]]; then
        return 0
    fi

    value="$(security find-generic-password -a "$account" -s "$service" -w 2>/dev/null || true)"
    if [[ -n "$value" ]]; then
        export "${var_name}=${value}"
    fi
}

_load_keychain_var "ANTHROPIC_API_KEY" "$USER" "anthropic-api-key"
_load_keychain_var "OPENAI_API_KEY" "$USER" "openai-api-key"
_load_keychain_var "OPENROUTER_API_KEY" "$USER" "openrouter-api-key"
_load_keychain_var "OLLAMA_API_KEY" "$USER" "ollama-api-key"
_load_keychain_var "KIMI_API_KEY" "$USER" "kimi-api-key"
_load_keychain_var "GROQ_API_KEY" "$USER" "groq-api-key"
_load_keychain_var "NIM_API_KEY" "$USER" "nim-api-key"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    _load_keychain_var "OPENROUTER_API_KEY" "openrouter" "openrouter-api-key"
fi

# ── dkeys ↔ dharma_swarm alias normalization ──────────────────────────────
# External tools (dkeys, keychain helpers) may export keys under names that
# differ from what dharma_swarm expects.  Bridge the gap here so runtime
# providers find credentials regardless of origin.

# NIM_API_KEY ↔ NVIDIA_NIM_API_KEY (bidirectional)
if [[ -n "${NIM_API_KEY:-}" && -z "${NVIDIA_NIM_API_KEY:-}" ]]; then
    export NVIDIA_NIM_API_KEY="$NIM_API_KEY"
fi
if [[ -n "${NVIDIA_NIM_API_KEY:-}" && -z "${NIM_API_KEY:-}" ]]; then
    export NIM_API_KEY="$NVIDIA_NIM_API_KEY"
fi

# NVIDIA_API_KEY → NVIDIA_NIM_API_KEY (dkeys uses the former)
if [[ -n "${NVIDIA_API_KEY:-}" && -z "${NVIDIA_NIM_API_KEY:-}" ]]; then
    export NVIDIA_NIM_API_KEY="$NVIDIA_API_KEY"
fi

# GEMINI_API_KEY → GOOGLE_AI_API_KEY (dkeys uses the former)
if [[ -n "${GEMINI_API_KEY:-}" && -z "${GOOGLE_AI_API_KEY:-}" ]]; then
    export GOOGLE_AI_API_KEY="$GEMINI_API_KEY"
fi

# PERPLEXITY_API_KEY → PPLX_API_KEY
if [[ -n "${PERPLEXITY_API_KEY:-}" && -z "${PPLX_API_KEY:-}" ]]; then
    export PPLX_API_KEY="$PERPLEXITY_API_KEY"
fi
