#!/usr/bin/env bash
# Replay the Organism Closure v0 proof.
# Exits 0 if pytest passes AND success/failure NextDecision JSON differ.
#
# Interpreter resolution (in order):
#   1. $PYTEST_PYTHON env var
#   2. /Users/dhyana/dharma_swarm_lf5/.venv/bin/python   (canonical lf5 venv)
#   3. ./.venv/bin/python                                 (repo-local venv)
#   4. python3                                            (system fallback;
#                                                          must have pytest)
# Fails clearly if no interpreter has pytest.
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
    for cand in "${candidates[@]}"; do
        [ -z "$cand" ] && continue
        [ -x "$cand" ] || continue
        if "$cand" -c "import pytest" >/dev/null 2>&1; then
            echo "$cand"
            return 0
        fi
    done
    return 1
}

PY="$(resolve_python)" || {
    echo "ERROR: no Python interpreter with pytest available." >&2
    echo "Tried: \$PYTEST_PYTHON, lf5 venv, ./.venv, system python3." >&2
    echo "Set PYTEST_PYTHON=/path/to/python and retry." >&2
    exit 2
}

cd "$REPO"
echo "Using interpreter: $PY"
"$PY" -m pytest tests/test_organism_closure_v0.py -q

# Closure proof: success and failure NextDecision rows must differ.
if diff -q \
    "$HERE/expected_next_decision_success.json" \
    "$HERE/expected_next_decision_failure.json" >/dev/null; then
    echo "CLOSURE FAIL: NextDecision rows are byte-identical." >&2
    exit 1
fi
echo "CLOSURE OK: success/failure NextDecision rows differ."
