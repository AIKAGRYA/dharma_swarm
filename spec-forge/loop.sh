#!/bin/bash
# Helm overnight loop — RUN FROM A PLAIN TERMINAL (never inside a Claude Code session).
# Launch:  caffeinate -dimsu bash /Users/dhyana/dharma_helm_build/spec-forge/loop.sh
set -u
unset CLAUDECODE CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS 2>/dev/null || true

ROOT=/Users/dhyana/dharma_helm_build
SPEC=$ROOT/spec-forge
RECEIPT=$SPEC/RUN_RECEIPT.md
PROGRESS=$ROOT/claude-progress.txt
LOG_DIR=$SPEC/logs
MAX_SESSIONS=40
MAX_HOURS=10

mkdir -p "$LOG_DIR"
cd "$ROOT" || exit 1
START_TS=$(date +%s)
echo "RUN_START $(date -u +%FT%TZ) caps=${MAX_SESSIONS}sessions/${MAX_HOURS}h head=$(git rev-parse --short HEAD)" >> "$RECEIPT"

p0_remaining() {
  python3 - <<'EOF'
import json
raw = json.load(open('/Users/dhyana/dharma_helm_build/spec-forge/features.json'))
feats = raw['features'] if isinstance(raw, dict) and 'features' in raw else raw
print(sum(1 for f in feats if f.get('priority') == 'P0' and f.get('status') == 'not_started'))
EOF
}

if ! grep -q "^INITIALIZED" "$RECEIPT" 2>/dev/null; then
  echo "[loop] session 0: initializer"
  claude -p "$(cat "$SPEC/prompts/INITIALIZER.md")" --permission-mode acceptEdits --add-dir "$ROOT" \
    > "$LOG_DIR/session_000_init.log" 2>&1
  echo "INITIALIZED $(date -u +%FT%TZ) head=$(git rev-parse --short HEAD)" >> "$RECEIPT"
fi

for i in $(seq 1 $MAX_SESSIONS); do
  NOW=$(date +%s)
  if [ $(( (NOW - START_TS) / 3600 )) -ge $MAX_HOURS ]; then
    echo "RUN_HALT wall-clock-cap $(date -u +%FT%TZ)" >> "$RECEIPT"; break
  fi
  if grep -q "VERDICT: HALT" "$PROGRESS" 2>/dev/null; then
    echo "RUN_HALT systemic $(date -u +%FT%TZ)" >> "$RECEIPT"; break
  fi
  REMAINING=$(p0_remaining)
  if [ "$REMAINING" = "0" ]; then
    echo "RUN_COMPLETE p0-exhausted $(date -u +%FT%TZ)" >> "$RECEIPT"; break
  fi

  echo "SESSION $i coder-start $(date -u +%FT%TZ) p0_remaining=$REMAINING" >> "$RECEIPT"
  echo "[loop] coder session $i/${MAX_SESSIONS} (P0 remaining: $REMAINING)"
  claude -p "$(cat "$SPEC/prompts/CODER.md")" --permission-mode acceptEdits --add-dir "$ROOT" \
    > "$LOG_DIR/session_$(printf %03d "$i")_coder.log" 2>&1

  echo "[loop] evaluator session $i"
  claude -p "$(cat "$SPEC/prompts/EVALUATOR.md")" --permission-mode acceptEdits --add-dir "$ROOT" \
    > "$LOG_DIR/session_$(printf %03d "$i")_eval.log" 2>&1
done

echo "RUN_END $(date -u +%FT%TZ) head=$(git rev-parse --short HEAD)" >> "$RECEIPT"
echo "==================== MORNING RECEIPT (tail) ===================="
tail -60 "$RECEIPT"
