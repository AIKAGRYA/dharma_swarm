#!/usr/bin/env bash
# Replay the Organism Closure v0 proof.
# Exits 0 if pytest passes AND success/failure NextDecision JSON differ.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

cd "$REPO"
python3 -m pytest tests/test_organism_closure_v0.py -q

# Closure proof: success and failure NextDecision rows must differ.
if diff -q \
    "$HERE/expected_next_decision_success.json" \
    "$HERE/expected_next_decision_failure.json" >/dev/null; then
    echo "CLOSURE FAIL: NextDecision rows are byte-identical." >&2
    exit 1
fi
echo "CLOSURE OK: success/failure NextDecision rows differ."
