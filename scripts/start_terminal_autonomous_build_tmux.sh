#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/dharma_swarm"
SESSION="${SESSION_NAME:-dharma_terminal_autonomous_build}"
STATE_DIR="${DGC_TERMINAL_AUTONOMOUS_BUILD_STATE_DIR:-${HOME}/.dharma/terminal_autonomous_build}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="${STATE_DIR}/${RUN_ID}"
PROMPT_FILE="${RUN_DIR}/terminal_autonomous_build_prompt.md"
MANIFEST_FILE="${RUN_DIR}/manifest.env"
CONTROL_FILE="${ROOT}/docs/plans/2026-04-09-terminal-autonomous-build-control.md"
ISSUE_LOG="${ROOT}/docs/plans/2026-04-09-terminal-autonomous-build-issues.md"
SKILL_FILE="${ROOT}/mode_pack/claude/terminal-autonomous-build/SKILL.md"
MODEL="${CLAUDE_MODEL:-}"
EFFORT="${CLAUDE_EFFORT:-high}"
PERMISSION_MODE="${CLAUDE_PERMISSION_MODE:-default}"
USE_CAFFEINATE="${USE_CAFFEINATE:-1}"
DANGEROUS_SKIP_PERMISSIONS="${CLAUDE_DANGEROUS_SKIP_PERMISSIONS:-0}"
ALLOWED_TOOLS="${CLAUDE_ALLOWED_TOOLS:-Read,Grep,Glob,Bash,Edit,Write}"

if [[ ! -d "${ROOT}" ]]; then
  echo "Missing repo directory: ${ROOT}" >&2
  exit 1
fi

if [[ ! -f "${CONTROL_FILE}" ]]; then
  echo "Missing control file: ${CONTROL_FILE}" >&2
  exit 1
fi

if [[ ! -f "${SKILL_FILE}" ]]; then
  echo "Missing skill file: ${SKILL_FILE}" >&2
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "Missing 'claude' CLI in PATH." >&2
  exit 1
fi

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' already running."
  exit 0
fi

mkdir -p "${RUN_DIR}"

cat > "${PROMPT_FILE}" <<EOF
# Terminal Autonomous Build Prompt

Repo root: ${ROOT}
Run id: ${RUN_ID}

You are running the repo-local \`dharma-terminal-autonomous-build\` lane for bounded terminal cleanup and architecture tightening.

Read and obey these files first:

1. ${CONTROL_FILE}
2. ${ISSUE_LOG}
3. ${SKILL_FILE}
4. ${ROOT}/docs/governance/TERMINAL_OPERATING_MODEL.md

Hard rules:

- treat \`terminal/\` as canonical unless a human explicitly changes that decision
- use \`terminal-v2/\` as a reference surface, not as a peer product to keep in parity
- keep one bounded seam at a time
- do not widen into \`dashboard/\`, \`api/\`, or unrelated orchestration code
- stop if the next move would require inventing a new shell or an unapproved promotion decision
- validate the touched terminal or bridge seam before declaring a tranche done

Required output after each tranche:

1. current lane
2. tranche completed
3. files changed
4. validation performed
5. residual risks
6. next bounded seam

Begin by reading the control file and choosing the strongest bounded terminal seam.
EOF

cat > "${MANIFEST_FILE}" <<EOF
RUN_ID='${RUN_ID}'
RUN_DIR='${RUN_DIR}'
PROMPT_FILE='${PROMPT_FILE}'
CONTROL_FILE='${CONTROL_FILE}'
ISSUE_LOG='${ISSUE_LOG}'
SKILL_FILE='${SKILL_FILE}'
SESSION='${SESSION}'
MODEL='${MODEL}'
EFFORT='${EFFORT}'
PERMISSION_MODE='${PERMISSION_MODE}'
ALLOWED_TOOLS='${ALLOWED_TOOLS}'
EOF

runner="claude -p \"\$(cat '${PROMPT_FILE}')\" --add-dir '${ROOT}' --allowedTools '${ALLOWED_TOOLS}' --permission-mode '${PERMISSION_MODE}' --effort '${EFFORT}'"

if [[ -n "${MODEL}" ]]; then
  runner="${runner} --model '${MODEL}'"
fi

if [[ "${DANGEROUS_SKIP_PERMISSIONS}" == "1" ]]; then
  runner="${runner} --dangerously-skip-permissions"
fi

if [[ "${USE_CAFFEINATE}" == "1" ]] && command -v caffeinate >/dev/null 2>&1; then
  runner="caffeinate -i ${runner}"
fi

tmux_cmd="cd '${ROOT}' && ${runner} | tee '${RUN_DIR}/claude_terminal_autonomous_build.log'"
tmux new-session -d -s "${SESSION}" "${tmux_cmd}"

printf '%s\n' "${RUN_DIR}" > "${STATE_DIR}/latest_run.txt"

echo "Started session '${SESSION}'"
echo "Run dir: ${RUN_DIR}"
echo "Prompt file: ${PROMPT_FILE}"
echo "Permission mode: ${PERMISSION_MODE}"
echo "Effort: ${EFFORT}"
echo "Model: ${MODEL:-default}"
echo "Use: scripts/status_terminal_autonomous_build_tmux.sh"
