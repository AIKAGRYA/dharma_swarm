#!/usr/bin/env bash
# Helm-scope validation contract for the no-mistakes Test step (and humans).
# Intent-targeted: bun workspace + the helm bridge/lifecycle python suites.
# Broad regression stays with CI (CI_TRUTH_CONTRACT.json owns required checks).
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
(cd terminal && bun install --frozen-lockfile --silent && bun test)
PY="${DHARMA_PYTHON:-${HOME}/dharma_swarm/.venv/bin/python}"
PYTHONPATH="$PWD" "$PY" -m pytest \
  tests/test_terminal_bridge_helm_context.py \
  tests/test_session_lifecycle.py \
  tests/test_operator_core_session_views.py \
  tests/test_claude_preview_protocol.py -q
