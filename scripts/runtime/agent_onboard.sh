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

section "Governance Snapshot"
if [ -f scripts/governance/agent_onboard.py ]; then
  "${PYTHON:-python3}" scripts/governance/agent_onboard.py || printf 'WARN governance onboarding renderer exited non-zero\n'
else
  printf 'MISS scripts/governance/agent_onboard.py\n'
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
exists_line "docs/ops/CODEX_TOOLBELT_ONBOARDING.md" "Codex/MCP/key-helper gates"

section "Current Build Track"
exists_line "docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md" "active seam master spec"
exists_line "docs/plans/NEXT_10_SUBSTRATE_TODO.md" "next substrate tasks"
exists_line "docs/plans/HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md" "handoff for code agents"

section "Next Commands"
cat <<'EOF'
sed -n '1,220p' docs/ops/AGENT_ONBOARDING.md
sed -n '1,220p' CLAUDE.md
sed -n '1,220p' docs/governance/BUILD_SESSION_ENTRYPOINT.md
sed -n '1,220p' docs/ops/CODEX_TOOLBELT_ONBOARDING.md
EOF
