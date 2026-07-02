#!/usr/bin/env bash
# Terminal active-track ratchet: current compact shell, app routing tests,
# typecheck, and hermetic golden-frame drift.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERMINAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

cd "${TERMINAL_DIR}"

bun run typecheck
bun test tests/app.test.ts tests/compactShell.test.tsx

GOLDEN_OUT_DIR="${TMP_DIR}" "${SCRIPT_DIR}/golden_capture.sh"
diff -u "${TERMINAL_DIR}/tests/golden/120x40/chat.txt" "${TMP_DIR}/120x40/chat.txt"

echo "ratchet: OK"
