#!/usr/bin/env bash
# Shared helpers for chetana hooks. Sourced by every hook script.
#
# Responsibilities:
#   - Locate a Python interpreter that has chetana importable.
#   - Compute paths the hooks rely on (state dir, capture dirs, log file).
#   - Provide bounded-time helpers (`chetana_run`) so hooks never block sessions.

set -u  # NOT -e — hooks must NEVER crash the session on transient failures.

CHETANA_LOG="${HOME}/.dharma/sessions/captures/chetana_hook.log"
CHETANA_STATE_DIR="${HOME}/.dharma"
CHETANA_CAPTURES_DIR="${CHETANA_STATE_DIR}/sessions/captures"
CHETANA_DAILY_DIR="${CHETANA_CAPTURES_DIR}/daily"
CHETANA_SUBAGENTS_DIR="${CHETANA_CAPTURES_DIR}/subagents"
CHETANA_IN_FLIGHT_DIR="${CHETANA_CAPTURES_DIR}/in_flight"
CHETANA_MANIFESTS_DIR="${CHETANA_CAPTURES_DIR}/manifests"
CHETANA_PROJECTS_ROOT="${HOME}/.claude/projects"

mkdir -p "${CHETANA_DAILY_DIR}" "${CHETANA_SUBAGENTS_DIR}" "${CHETANA_IN_FLIGHT_DIR}" "${CHETANA_MANIFESTS_DIR}" 2>/dev/null

# Discover the right Python+chetana install. Tries dev worktree first, then
# canonical dharma_swarm, then LF5. Falls through silently if nothing works.
chetana_find_python() {
  local candidates=(
    "${HOME}/dharma_chetana/.venv/bin/python"
    "${HOME}/dharma_swarm/.venv/bin/python"
    "${HOME}/dharma_swarm_lf5/.venv/bin/python"
  )
  for p in "${candidates[@]}"; do
    if [[ -x "${p}" ]]; then
      if "${p}" -c "import dharma_swarm.chetana" >/dev/null 2>&1; then
        echo "${p}"
        return 0
      fi
    fi
  done
  return 1
}

chetana_log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [chetana-hook] $*" >> "${CHETANA_LOG}" 2>/dev/null
}

# Run a chetana CLI command with a timeout, capturing stdout to a temp file.
# Args: $1 = timeout seconds, $2... = chetana subcommand args
# Echoes the temp file path on success, empty on failure.
chetana_run() {
  local timeout_s="${1}"
  shift
  local python
  python="$(chetana_find_python)" || {
    chetana_log "skip: no chetana python install found"
    return 1
  }
  local out
  out="$(mktemp -t chetana.XXXXXX)" || return 1
  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout "${timeout_s}" "${python}" -m dharma_swarm.chetana.cli "$@" \
      >"${out}" 2>>"${CHETANA_LOG}" || {
        chetana_log "chetana cli timeout/error: $*"
        echo "${out}"
        return 0
      }
  else
    # macOS without coreutils — best-effort run, no hard timeout.
    "${python}" -m dharma_swarm.chetana.cli "$@" \
      >"${out}" 2>>"${CHETANA_LOG}" || {
        chetana_log "chetana cli error: $*"
        echo "${out}"
        return 0
      }
  fi
  echo "${out}"
}

# Find the most recent session JSONL for the current cwd.
chetana_current_session_jsonl() {
  local cwd
  cwd="$(pwd)"
  local slug
  # Replicate Claude Code's project-dir slug: replace / with -, no leading -
  slug="$(echo "${cwd}" | sed 's|/|-|g')"
  local proj_dir="${CHETANA_PROJECTS_ROOT}/${slug}"
  if [[ ! -d "${proj_dir}" ]]; then
    return 1
  fi
  local latest
  latest="$(ls -t "${proj_dir}"/*.jsonl 2>/dev/null | head -1)"
  [[ -n "${latest}" ]] || return 1
  echo "${latest}"
}

# Emit a JSON systemMessage to stdout for the SessionStart hook contract.
# Args: $1 = message body (markdown)
chetana_emit_system_message() {
  local body="${1}"
  # Escape: take a markdown body, convert to JSON-safe string.
  python3 -c "
import json,sys
body = sys.stdin.read()
print(json.dumps({'systemMessage': body}))
" <<<"${body}"
}
