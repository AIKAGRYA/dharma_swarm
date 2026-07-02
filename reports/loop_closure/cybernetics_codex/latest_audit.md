# cybernetics_codex Audit

- observed_at: `2026-06-29T14:21:57.012433Z`
- mode: `read_only_verifier`
- manifest_registered: `True`
- loop_track_found: `True`
- seed_registered: `True`
- live_registration: `True`
- nats_runtime_status: `declared_not_started`

## Runtime

- runtime_db: `/Users/dhyana/.dharma/state/runtime.db`
- read_ok: `True`
- delegation_runs: `7401` total, `3552` completed, `3775` failed
- receipt_json: `2047` rows

## Loop Statuses

| # | Loop | Verdict | Blocker |
|---|---|---|---|
| 1 | Swarm Task Loop | PARTIAL | activity exists (3552/7401 completed), but receipt_json coverage is 2047/7401 and dispatch_dropoff=1612 |
| 2 | Organism Heartbeat | PARTIAL | runtime substrate is active, but this loop lacks a dedicated closure receipt |
| 3 | Evolution Loop / DarwinEngine | PARTIAL | activity exists, but adaptation/fitness authority is not closure-proven |
| 4 | Consolidation Loop / Memory | PARTIAL | runtime substrate is active, but this loop lacks a dedicated closure receipt |
| 5 | Zeitgeist Scanner | PARTIAL | runtime substrate is active, but this loop lacks a dedicated closure receipt |
| 6 | Witness Auditor | PARTIAL | audit/receipt activity exists, but current Loop 1 production tie-in not proven |
| 7 | Training Flywheel | PARTIAL | activity exists, but adaptation/fitness authority is not closure-proven |
| 8 | Recognition Loop / eigenform | PARTIAL | activity exists, but adaptation/fitness authority is not closure-proven |
| 9 | Conductors | PARTIAL | runtime substrate is active, but this loop lacks a dedicated closure receipt |
| 10 | Context Agent | PARTIAL | runtime substrate is active, but this loop lacks a dedicated closure receipt |
| 11 | Replication Monitor | PARTIAL | runtime substrate is active, but this loop lacks a dedicated closure receipt |
| 12 | Self-Improvement | BLOCKED | guardian quorum below threshold: N=3/5, M=1/3 |
| 13 | Free Evolution Grind | BLOCKED | guardian quorum below threshold: N=3/5, M=1/3 |

## Verifier Commands

- `make onboard`
- `make orient`
- `.venv/bin/dgc status`
- `.venv/bin/dgc loop-status`
- `bash scripts/runtime/codex_toolbelt_status.sh`
- `python3 scripts/governance/cybernetics_codex_audit.py --json`
- `python3 scripts/governance/register_cybernetics_codex.py --dry-run`
- `pytest -q tests/test_cybernetics_codex.py tests/test_manifest_health.py`

