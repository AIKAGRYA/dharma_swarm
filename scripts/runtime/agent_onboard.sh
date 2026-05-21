#!/usr/bin/env bash
set -u

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

cd "${ROOT}" || exit 2

section() {
  printf '\n== %s ==\n' "$1"
}

exists_line() {
  local path="$1"
  local note="$2"
  if [ -e "${path}" ]; then
    printf 'OK   %-72s %s\n' "${path}" "${note}"
  else
    printf 'MISS %-72s %s\n' "${path}" "${note}"
  fi
}

printf 'dharma_swarm new-agent onboarding\n'
printf 'repo=%s\n' "${ROOT}"
printf 'command=make onboard\n'

section "Live Toolbelt"
if [ -f scripts/runtime/codex_toolbelt_status.sh ]; then
  bash scripts/runtime/codex_toolbelt_status.sh "${ROOT}"
else
  printf 'MISS scripts/runtime/codex_toolbelt_status.sh\n'
fi

section "Working Tree"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git branch --show-current 2>/dev/null || true)"
  dirty_count="$(git status --short | wc -l | tr -d ' ')"
  printf 'branch=%s\n' "${branch:-unknown}"
  printf 'dirty_entries=%s\n' "${dirty_count}"
  if [ "${dirty_count}" != "0" ]; then
    printf 'WARN worktree is dirty; do not revert user or other-agent changes.\n'
  fi
else
  printf 'WARN not inside a git worktree\n'
fi

section "First Read Order"
exists_line "docs/ops/AGENT_ONBOARDING.md" "this map"
exists_line "CLAUDE.md" "repo behavior and engineering rules"
exists_line "docs/ops/CODEX_TOOLBELT_ONBOARDING.md" "MCP/tool routing and Sourcegraph replacement"
exists_line "docs/governance/BUILD_SESSION_ENTRYPOINT.md" "mandatory build-session pointer"
exists_line "docs/MEGAFILE_INDEX.md" "ten durable onboarding surfaces"

section "Task-Specific Maps"
exists_line "docs/governance/SOVEREIGN_MANIFEST.md" "governance and substrate boundaries"
exists_line "docs/governance/CANONICAL_DOC_STACK.md" "doc ownership rules"
exists_line "reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md" "canonical substrate table and gaps"
exists_line "docs/architecture/NAVIGATION.md" "large static architecture map"
exists_line "INTERFACE_MISMATCH_MAP.md" "known interface mismatches before code edits"
exists_line "CYBERNETIC_LOOP_MAP.md" "feedback-loop map"
exists_line "docs/state/LIVE_OPS_DASHBOARD.md" "current live state"
exists_line "docs/state/BROKEN_REGISTER.md" "known broken surfaces"
exists_line "docs/agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md" "persistent/external agent identity gates"
exists_line "docs/research/persistent_agents_census_2026-05/l4_readiness_report.md" "current L4 readiness truth"

section "Current Build Track"
exists_line "docs/governance/ACTIVE_TRACK.yaml" "single source of active build-track intent"
exists_line "docs/plans/COMMAND_PLANE_MULTIAGENT_PROTOCOL.md" "command-plane pickup protocol"
exists_line "docs/plans/COMMAND_PLANE_CHECKLIST.md" "command-plane living checklist"
exists_line "docs/plans/2026-05-21-command-plane-design-lock.md" "locked command-plane decisions"
exists_line "docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md" "PGE autonomous-build repo bridge"
exists_line "docs/ops/LONG_RUNNING_HARNESS.md" "planner/generator/evaluator harness scaffold"
exists_line "docs/plans/COMMAND_PLANE_LONG_RUNNING_HARNESS_APPLICATION.md" "future command-plane harness application"

section "Strategy Brain"
exists_line "docs/strategy/agentic_harness_2026-05/00_index.md" "agentic harness strategy index"
exists_line "examples/agents/strategy_librarian.registration.json" "strategy-librarian registration manifest"
exists_line "${HOME}/.dharma/external_agents/strategy_librarian/CALL_CARD.md" "manual call card for strategy-librarian"

section "Next Commands"
cat <<'EOF'
sed -n '1,220p' docs/ops/AGENT_ONBOARDING.md
sed -n '1,220p' CLAUDE.md
sed -n '1,220p' docs/governance/BUILD_SESSION_ENTRYPOINT.md
EOF
