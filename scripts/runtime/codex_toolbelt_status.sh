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
if server_configured gitnexus; then
  ok "gitnexus MCP configured"
else
  warn "gitnexus MCP missing from Codex config"
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

if [ -x "${HOME}/.local/bin/src" ]; then
  ok "Sourcegraph src CLI available for public-code search"
else
  warn "Sourcegraph src CLI missing; public-code search fallback unavailable"
fi

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
