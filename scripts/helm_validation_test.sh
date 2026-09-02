#!/usr/bin/env bash
# Helm-scope validation contract for the no-mistakes Test step (and humans).
# Intent-targeted: bun workspace + the helm bridge/lifecycle/tmux python suites
# this branch touches, including its major new regression suites.
# Broad regression stays with CI (CI_TRUTH_CONTRACT.json owns required checks).
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
(cd terminal && bun install --frozen-lockfile --silent && bun test)
PY="${DHARMA_PYTHON:-${HOME}/dharma_swarm/.venv/bin/python}"
PYTHONPATH="$PWD" "$PY" -m pytest \
  tests/test_terminal_bridge_helm_context.py \
  tests/test_session_lifecycle.py \
  tests/test_operator_core_session_views.py \
  tests/test_claude_preview_protocol.py \
  tests/test_terminal_bridge.py \
  tests/test_terminal_tmux_isolation.py \
  tests/test_key_oracle_live_filter.py \
  tests/test_terminal_bridge_external_preview.py \
  tests/test_route_verification.py \
  tests/test_helm_seat_matrix.py \
  tests/test_model_pool.py \
  tests/test_model_status_projection.py \
  tests/test_model_key_routing_guard.py \
  tests/tui/test_model_routing.py \
  tests/tui/test_claude_adapter_v11.py -q
