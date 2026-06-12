#!/bin/bash
# Helm overnight loop — RUN FROM A PLAIN TERMINAL (never inside a Claude Code session).
# Launch:  caffeinate -dimsu bash /Users/dhyana/dharma_helm_build/spec-forge/loop.sh
set -u
unset CLAUDECODE CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS 2>/dev/null || true
# CRITICAL: scrub metered-API keys so headless claude uses the Max-plan Keychain OAuth.
# Without this every session dies in 10s with "Credit balance is too low" (2026-06-12 incident).
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN 2>/dev/null || true

ROOT=/Users/dhyana/dharma_helm_build
SPEC=$ROOT/spec-forge
RECEIPT=$SPEC/RUN_RECEIPT.md
PROGRESS=$ROOT/claude-progress.txt
LOG_DIR=$SPEC/logs
MAX_SESSIONS=40
MAX_HOURS=10
MIN_SESSION_SECS=90   # a real coder session takes minutes; faster = provider/auth failure
FAILSTREAK=0

mkdir -p "$LOG_DIR"
cd "$ROOT" || exit 1

# Preflight: one tiny headless call must succeed before we burn any sessions.
echo "[loop] preflight: verifying headless claude works..."
PREFLIGHT=$(claude -p "Reply with exactly: OK" 2>&1 | tail -1)
case "$PREFLIGHT" in
  *OK*) echo "[loop] preflight green" ;;
  *)
    echo "RUN_ABORT preflight-failed $(date -u +%FT%TZ) reason=\"$PREFLIGHT\"" >> "$RECEIPT"
    echo "[loop] PREFLIGHT FAILED: $PREFLIGHT"
    echo "[loop] Nothing was started. Fix the provider/auth issue and relaunch."
    exit 1 ;;
esac

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
  S_START=$(date +%s)
  claude -p "$(cat "$SPEC/prompts/CODER.md")" --permission-mode acceptEdits --add-dir "$ROOT" \
    > "$LOG_DIR/session_$(printf %03d "$i")_coder.log" 2>&1
  S_SECS=$(( $(date +%s) - S_START ))

  # Liveness circuit-breaker: instant returns = provider/auth failure, not work.
  if [ "$S_SECS" -lt "$MIN_SESSION_SECS" ]; then
    FAILSTREAK=$((FAILSTREAK + 1))
    REASON=$(tail -1 "$LOG_DIR/session_$(printf %03d "$i")_coder.log" | cut -c1-120)
    echo "SESSION $i instant-fail ${S_SECS}s streak=$FAILSTREAK reason=\"$REASON\"" >> "$RECEIPT"
    if [ "$FAILSTREAK" -ge 3 ]; then
      echo "RUN_HALT provider-dead $(date -u +%FT%TZ) (3 consecutive instant failures)" >> "$RECEIPT"
      echo "[loop] HALT: 3 consecutive instant failures — provider/auth is down, not burning sessions."
      break
    fi
    sleep 120   # back off before retrying
    continue    # do not run the evaluator on a session that did nothing
  fi
  FAILSTREAK=0

  echo "[loop] evaluator session $i"
  claude -p "$(cat "$SPEC/prompts/EVALUATOR.md")" --permission-mode acceptEdits --add-dir "$ROOT" \
    > "$LOG_DIR/session_$(printf %03d "$i")_eval.log" 2>&1
done

echo "RUN_END $(date -u +%FT%TZ) head=$(git rev-parse --short HEAD)" >> "$RECEIPT"
echo "==================== MORNING RECEIPT (tail) ===================="
tail -60 "$RECEIPT"
