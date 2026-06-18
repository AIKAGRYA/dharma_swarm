#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[terminal-guardian] architecture spec"
test -f specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md

echo "[terminal-guardian] bridge syntax"
python3 -m py_compile dharma_swarm/terminal_bridge.py

echo "[terminal-guardian] Bun dependency presence"
if [ ! -d terminal/node_modules ]; then
  echo "terminal/node_modules missing; run: cd terminal && bun install" >&2
  exit 2
fi

echo "[terminal-guardian] typecheck"
(cd terminal && bun run typecheck)

echo "[terminal-guardian] protocol/route-policy tests"
(cd terminal && bun test tests/routePolicy.test.ts tests/protocol.test.ts)

echo "[terminal-guardian] compact terminal smoke"
if command -v timeout >/dev/null 2>&1; then
  (cd terminal && COLUMNS=80 LINES=24 timeout 5 bun run start >/tmp/dharma-terminal-guardian-smoke.log 2>&1) || true
else
  (cd terminal && COLUMNS=80 LINES=24 bun run start >/tmp/dharma-terminal-guardian-smoke.log 2>&1 & pid=$!; sleep 5; kill "$pid" >/dev/null 2>&1 || true; wait "$pid" >/dev/null 2>&1 || true)
fi

if grep -qiE "Cannot find module|SyntaxError|ReferenceError|TypeError" /tmp/dharma-terminal-guardian-smoke.log; then
  cat /tmp/dharma-terminal-guardian-smoke.log >&2
  exit 1
fi

echo "terminal-guardian preflight: OK"
