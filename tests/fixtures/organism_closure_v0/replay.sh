#!/usr/bin/env bash
# Replay the Organism Closure v0 proof.
# Exits 0 if pytest passes AND success/failure NextDecision JSON differ.
#
# Interpreter resolution:
#   1. $PYTEST_PYTHON
#   2. /Users/dhyana/dharma_swarm_lf5/.venv/bin/python
#   3. ./.venv/bin/python
#   4. python3
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

resolve_python() {
    local candidates=(
        "${PYTEST_PYTHON:-}"
        "/Users/dhyana/dharma_swarm_lf5/.venv/bin/python"
        "$REPO/.venv/bin/python"
        "$(command -v python3 || true)"
    )
    for candidate in "${candidates[@]}"; do
        [ -n "$candidate" ] || continue
        [ -x "$candidate" ] || continue
        if "$candidate" -c "import pytest" >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

PY="$(resolve_python)" || {
    echo "ERROR: no Python interpreter with pytest available." >&2
    echo "Set PYTEST_PYTHON=/path/to/python and retry." >&2
    exit 2
}

cd "$REPO"
"$PY" -m pytest tests/test_organism_closure_v0.py -q

# Closure proof: success and failure NextDecision rows must differ.
if diff -q \
    "$HERE/expected_next_decision_success.json" \
    "$HERE/expected_next_decision_failure.json" >/dev/null; then
    echo "CLOSURE FAIL: NextDecision rows are byte-identical." >&2
    exit 1
fi
echo "CLOSURE OK: success/failure NextDecision rows differ."
