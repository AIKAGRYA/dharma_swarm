#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

required_files=(
  "terminal/package.json"
  "terminal/src/app.tsx"
  "terminal/scripts/golden_capture.sh"
  "terminal/scripts/ratchet.sh"
  "terminal/tests/compactShell.test.tsx"
  "terminal/tests/golden/120x40/chat.txt"
  "dharma_swarm/terminal_bridge.py"
)

for path in "${required_files[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "terminal_guardian_preflight: missing $path" >&2
    exit 1
  fi
done

if command -v rg >/dev/null 2>&1; then
  if rg -n "from textual|import textual" terminal/src >/dev/null; then
    echo "terminal_guardian_preflight: Bun terminal path imports textual" >&2
    rg -n "from textual|import textual" terminal/src >&2
    exit 1
  fi
fi

(
  cd terminal
  bun run typecheck
  bun test tests/compactShell.test.tsx
)

python3 -m py_compile dharma_swarm/terminal_bridge.py

echo "terminal_guardian_preflight: pass"
