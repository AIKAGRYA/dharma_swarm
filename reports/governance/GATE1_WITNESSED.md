# GATE 1 — operator-witnessed EvidenceReceipt

- witnessed_at: 2026-06-11T21:16:12Z
- watch_started: 2026-06-11T20:52:19Z  (the count moved AFTER this — freshness-guarded)
- receipt_count: 0 -> 1
- latest_receipt_json_sha256_16: 82c65502d79eecc9
- db: /Users/dhyana/.dharma/state/runtime.db

Written by gate1_witness.sh --watch the moment the count moved past a
freshness-guarded baseline (stale baselines are reset at watch start, and
the baseline advances on success so a re-run cannot re-trigger).
Verify anytime: sqlite3 '/Users/dhyana/.dharma/state/runtime.db' "SELECT COUNT(*) FROM delegation_runs WHERE receipt_json IS NOT NULL"

LIMITATION (by design, documented): file_exists is the criterion, so this
file CAN be hand-written — but the sha16 is checkable against the DB row,
so fabrication is an auditable lie, not a satisfied proxy.
