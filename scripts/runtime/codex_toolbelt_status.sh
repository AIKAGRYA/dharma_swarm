#!/usr/bin/env bash
set -u

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CODEX_CONFIG="${HOME}/.codex/config.toml"

ok() {
  printf 'OK   %s\n' "$1"
}

warn() {
  printf 'WARN %s\n' "$1"
}

info() {
  printf 'INFO %s\n' "$1"
}

present_env() {
  local name="$1"
  if [ -n "${!name:-}" ]; then
    ok "env ${name} is present"
  else
    warn "env ${name} is missing"
  fi
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

server_configured() {
  local name="$1"
  if [ -f "${CODEX_CONFIG}" ] && grep -q "^\[mcp_servers\.${name}\]" "${CODEX_CONFIG}"; then
    return 0
  fi
  return 1
}

printf 'Codex toolbelt status\n'
printf 'repo=%s\n' "${ROOT}"
printf 'config=%s\n\n' "${CODEX_CONFIG}"

printf 'Core local stack\n'
if has_cmd gitnexus; then
  gitnexus_ver="$(gitnexus --version 2>/dev/null | head -1 | tr -d '[:space:]')"
  if [ "${gitnexus_ver}" = "1.6.9" ]; then
    ok "gitnexus CLI ${gitnexus_ver} (pinned)"
  else
    warn "gitnexus CLI ${gitnexus_ver:-unknown}; pin with make gitnexus-ensure (want 1.6.9)"
  fi
else
  warn "gitnexus CLI missing; pin with make gitnexus-ensure"
fi
if server_configured gitnexus; then
  ok "gitnexus MCP configured in Codex"
else
  warn "gitnexus MCP missing from Codex config; Grok/Claude pins live in ~/.grok/config.toml and ~/.claude.json"
fi
if [ -f "${ROOT}/.gitnexus/meta.json" ]; then
  ok "gitnexus index meta present at ${ROOT}/.gitnexus/meta.json"
else
  warn "gitnexus index missing; from repo root run: gitnexus analyze --skip-agents-md"
fi

if server_configured contextplus; then
  ok "contextplus MCP configured"
else
  warn "contextplus MCP missing from Codex config"
fi

if has_cmd rg; then
  ok "rg available"
else
  warn "rg missing"
fi

if [ -x "${HOME}/.local/bin/src" ] || has_cmd src; then
  ok "Sourcegraph src CLI available"
else
  warn "Sourcegraph src CLI missing; public-code search fallback unavailable"
fi
if [ -n "${SRC_ENDPOINT:-}" ]; then
  info "SRC_ENDPOINT is set (host only; value not printed)"
else
  info "SRC_ENDPOINT unset; src defaults to public sourcegraph.com search"
fi
if [ -n "${SRC_ACCESS_TOKEN:-}" ]; then
  info "SRC_ACCESS_TOKEN is present"
else
  info "SRC_ACCESS_TOKEN absent; workspace/private search needs src login"
fi

printf '\nLocal provider key helper, values not printed\n'
if has_cmd dkeys; then
  ok "dkeys CLI available"
else
  info "dkeys CLI not found in PATH; it is a local operator helper, not a repo dependency"
fi

if [ -s "${HOME}/.dharma/agent_keys.env" ]; then
  ok "local dkeys key store exists"
else
  info "local dkeys key store missing"
fi

if [ -s "${HOME}/.dharma/keys_status.json" ]; then
  ok "local dkeys status cache exists"
else
  info "local dkeys status cache missing"
fi

present_env OPENAI_API_KEY
present_env OPENROUTER_API_KEY
present_env OLLAMA_API_KEY
present_env NVIDIA_NIM_API_KEY
present_env GOOGLE_AI_API_KEY
present_env GEMINI_API_KEY

printf '\nRemoved/optional MCPs\n'
if server_configured sourcegraph; then
  warn "sourcegraph MCP still configured; remove unless Enterprise/OAuth access exists"
else
  ok "sourcegraph MCP not configured globally"
fi

if server_configured gdrive; then
  warn "gdrive MCP configured; verify credentials before spawning agents"
else
  ok "gdrive MCP not configured globally"
fi

if server_configured postgres; then
  warn "postgres MCP configured; verify DSN before spawning agents"
else
  ok "postgres MCP not configured globally"
fi

printf '\nCredential gates, values not printed\n'
present_env SRC_ACCESS_TOKEN
present_env SOURCEBOT_API_KEY
present_env MCP_POSTGRES_URL
present_env GDRIVE_OAUTH_PATH
present_env GDRIVE_CREDENTIALS_PATH

if [ -s "${HOME}/.codex/memories/postgres-url.txt" ]; then
  ok "postgres DSN file exists"
else
  warn "postgres DSN file missing"
fi

if [ -s "${HOME}/.codex/memories/gcp-oauth.keys.json" ]; then
  ok "GDrive OAuth client JSON exists"
else
  warn "GDrive OAuth client JSON missing"
fi

if [ -s "${HOME}/.codex/memories/gdrive-credentials.json" ]; then
  ok "GDrive saved credentials exist"
else
  warn "GDrive saved credentials missing"
fi

printf '\nSourcebot lane\n'
if curl --max-time 0.3 -fsS http://localhost:3000/api/mcp >/dev/null 2>&1; then
  ok "Sourcebot MCP endpoint responds on localhost:3000"
else
  info "Sourcebot MCP endpoint not reachable on localhost:3000"
fi

if has_cmd docker; then
  info "docker CLI present: $(docker --version 2>/dev/null | head -1)"
else
  warn "docker CLI missing"
fi

if has_cmd colima; then
  info "colima present; run 'colima list' if Sourcebot/Docker is needed"
else
  info "colima not found"
fi

printf '\nRead next: docs/ops/AGENT_ONBOARDING.md and docs/ops/CODEX_TOOLBELT_ONBOARDING.md\n'
