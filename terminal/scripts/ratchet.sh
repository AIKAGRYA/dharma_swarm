#!/usr/bin/env bash
# Terminal active-track ratchet: current compact shell, app routing tests,
# typecheck, and hermetic golden-frame drift.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERMINAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TMP_DIR="$(mktemp -d)"

if ! BUN_BIN="$(command -v bun)"; then
  echo "ratchet: bun is required" >&2
  exit 127
fi

# Invoked through the EXIT trap below.
# shellcheck disable=SC2329
cleanup() {
  rm -r -- "${TMP_DIR}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "${TERMINAL_DIR}"

"${BUN_BIN}" run typecheck
DHARMA_PYTHON=/nonexistent/dharma-terminal-ratchet-python \
  "${BUN_BIN}" test tests/app.test.ts tests/compactShell.test.tsx

GOLDEN_OUT_DIR="${TMP_DIR}" "${SCRIPT_DIR}/golden_capture.sh"
diff -u "${TERMINAL_DIR}/tests/golden/120x40/chat.txt" "${TMP_DIR}/120x40/chat.txt"

echo "ratchet: OK"
