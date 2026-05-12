#!/usr/bin/env bash
set -euo pipefail

SESSION="dharma-interop-workers"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "$SESSION already running"
  tmux list-windows -t "$SESSION"
  exit 0
fi

worker_cmd() {
  local adapter_id="$1"
  local worker_id="$2"
  local command_template="${3:-}"
  if [[ -n "$command_template" ]]; then
    printf '%q -m dharma_swarm.operator_core.interop_worker --adapter-id %q --worker-id %q --repo-root %q --command-template %q' \
      "$PYTHON" "$adapter_id" "$worker_id" "$ROOT" "$command_template"
  else
    printf '%q -m dharma_swarm.operator_core.interop_worker --adapter-id %q --worker-id %q --repo-root %q' \
      "$PYTHON" "$adapter_id" "$worker_id" "$ROOT"
  fi
}

codex_template="./scripts/run_interop_codex_task.sh {prompt_file}"
claude_template="./scripts/run_interop_claude_task.sh {prompt_file}"

if command -v codex >/dev/null 2>&1; then
  tmux new-session -d -s "$SESSION" -n codex "$(worker_cmd codex-cli codex-cli-worker "$codex_template")"
else
  tmux new-session -d -s "$SESSION" -n codex "$(worker_cmd codex-cli codex-cli-handoff)"
fi

if command -v claude >/dev/null 2>&1; then
  tmux new-window -t "$SESSION" -n claude "$(worker_cmd claude-code claude-code-worker "$claude_template")"
else
  tmux new-window -t "$SESSION" -n claude "$(worker_cmd claude-code claude-code-handoff)"
fi

tmux new-window -t "$SESSION" -n cursor "$(worker_cmd cursor cursor-handoff)"
tmux new-window -t "$SESSION" -n warp "$(worker_cmd warp-oz warp-oz-handoff)"
tmux new-window -t "$SESSION" -n perplexity "$(worker_cmd perplexity-computer perplexity-computer-handoff)"
tmux new-window -t "$SESSION" -n kimi "$(worker_cmd kimi-claw-phone kimi-claw-phone-handoff)"
tmux new-window -t "$SESSION" -n hermes "$(worker_cmd hermes hermes-handoff)"
tmux new-window -t "$SESSION" -n openclaw "$(worker_cmd openclaw openclaw-handoff)"
tmux new-window -t "$SESSION" -n opencalw "$(worker_cmd opencalw opencalw-handoff)"
tmux new-window -t "$SESSION" -n claude-flow "$(worker_cmd claude-flow claude-flow-handoff)"

echo "started $SESSION"
tmux list-windows -t "$SESSION"
