#!/bin/bash
# Live window into the Helm overnight run. Run in a second terminal:
#   bash /Users/dhyana/dharma_helm_build/spec-forge/watch.sh
# Refreshes every 15s. Ctrl+C to stop watching (does NOT affect the run).
ROOT=/Users/dhyana/dharma_helm_build
while true; do
  clear
  echo "═══════════════ THE HELM — live run status ═══════════════"
  date
  echo
  echo "── Is the loop running? ──"
  if pgrep -f "spec-forge/loop.sh" > /dev/null; then echo "YES — loop is alive"; else echo "NO — loop is not running"; fi
  echo
  echo "── Features done (verified by the independent evaluator) ──"
  python3 - <<'EOF'
import json
raw = json.load(open('/Users/dhyana/dharma_helm_build/spec-forge/features.json'))
feats = raw['features'] if isinstance(raw, dict) and 'features' in raw else raw
v = [f['id'] for f in feats if f.get('verified')]
ip = [f['id'] for f in feats if f.get('status') == 'in_progress']
ns = sum(1 for f in feats if f.get('priority') == 'P0' and f.get('status') == 'not_started')
print(f"  verified: {len(v)}/156  {' '.join(v[-8:])}")
print(f"  being worked on right now: {' '.join(ip) if ip else '(between sessions)'}")
print(f"  P0 remaining: {ns}")
EOF
  echo
  echo "── Last 8 receipt lines (the truth log) ──"
  tail -8 "$ROOT/spec-forge/RUN_RECEIPT.md" 2>/dev/null | sed 's/^/  /'
  echo
  echo "── Last 5 commits ──"
  git -C "$ROOT" log --oneline -5 | sed 's/^/  /'
  echo
  echo "(refreshes every 15s · Ctrl+C stops watching, never the run)"
  sleep 15
done
