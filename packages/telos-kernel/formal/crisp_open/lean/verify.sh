#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

count_token() {
  local token="$1"
  { grep -R -I -h -o -w --include='*.lean' "$token" . 2>/dev/null || true; } | wc -l | tr -d ' '
}

sorry_count="$(count_token sorry)"
admit_count="$(count_token admit)"
native_decide_count="$(count_token native_decide)"
declared_axiom_count="$(count_token axiom)"

echo "VERIFIER_COUNTS sorry=${sorry_count} admit=${admit_count} native_decide=${native_decide_count} declared_axiom=${declared_axiom_count}"

if [[ "$sorry_count" != "0" || "$admit_count" != "0" || "$native_decide_count" != "0" || "$declared_axiom_count" != "0" ]]; then
  echo "Forbidden proof escape or declared axiom found" >&2
  exit 1
fi

lake build

# The pinned Lean toolchain bundles an independent comparator that re-checks
# the built environment without running elaborator or tactic code again.
lake env leanchecker

audit_log="$(mktemp)"
trap 'rm -f "$audit_log"' EXIT
lake env lean AxiomAudit.lean 2>&1 | tee "$audit_log"

python3 - "$audit_log" <<'PY'
from pathlib import Path
import re
import sys

allowed = {"propext", "Classical.choice", "Quot.sound"}
text = Path(sys.argv[1]).read_text(encoding="utf-8")
observed: set[str] = set()
for line in text.splitlines():
    if "depends on axioms:" not in line:
        continue
    payload = line.split("depends on axioms:", 1)[1]
    observed.update(re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", payload))

unexpected = sorted(observed - allowed)
print("VERIFIER_AXIOMS observed=" + (",".join(sorted(observed)) if observed else "none"))
if unexpected:
    print("Unexpected axioms: " + ", ".join(unexpected), file=sys.stderr)
    raise SystemExit(1)
PY
