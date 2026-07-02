# cybernetics_codex Audit

- observed_at: `2026-07-01T15:27:50.197412Z`
- mode: `read_only_verifier`
- manifest_registered: `True`
- loop_track_found: `True`
- seed_registered: `True`
- live_registration: `True`
- nats_runtime_status: `declared_not_started`

## Runtime

- runtime_db: `/Users/dhyana/.dharma/state/runtime.db`
- read_ok: `True`
- scope_since: `None`
- delegation_runs: `8669` total, `4158` completed, `4403` failed
- receipt_json: `2574` rows `(orchestrator surface; A2A empty is success)`
- served_provider_truth: delegation completed `1917/4158`, runtime_receipts `20607` rows

## Bounded Replays

- loop1_report: `/Users/dhyana/dw-worktrees/g/reports/loop_closure/cybernetics_codex/2026-06-23_loop1_ollama_fresh_spine_dispatch.json`
- loop1_closed: `True`
- loop1_tasks: `3/3`
- loop1_dispatch_dropoffs: `0`
- loop1_evidence_receipts_ok: `3`

## Loop Statuses

| # | Loop | Verdict | Blocker |
|---|---|---|---|
| 1 | Swarm Task Loop | CLOSED_BOUNDED_REPLAY | bounded replay closes current Loop 1 lane (3/3 completed, dispatch_dropoff=0, evidence_receipts_ok=3, served_provider_truth=999); standing all-history audit still includes historical dispatch_dropoff=2135 |
| 2 | Organism Heartbeat | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 2 (cycles=3, all transitions receipted, adapt change fed the next cycle) |
| 3 | Evolution Loop / DarwinEngine | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 3 (cycles=2, all transitions receipted, adapt change fed the next cycle) |
| 4 | Consolidation Loop / Memory | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 4 (cycles=2, all transitions receipted, adapt change fed the next cycle) |
| 5 | Zeitgeist Scanner | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 5 (cycles=2, all transitions receipted, adapt change fed the next cycle) |
| 6 | Witness Auditor | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 6 (cycles=4, all transitions receipted, adapt change fed the next cycle) |
| 7 | Training Flywheel | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 7 (cycles=1, all transitions receipted, adapt change fed the next cycle) |
| 8 | Recognition Loop / eigenform | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 8 (cycles=2, all transitions receipted, adapt change fed the next cycle) |
| 9 | Conductors | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 9 (cycles=2, all transitions receipted, adapt change fed the next cycle) |
| 10 | Context Agent | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 10 (cycles=2, all transitions receipted, adapt change fed the next cycle) |
| 11 | Replication Monitor | CLOSED_BOUNDED_REPLAY | bounded closure replay closes loop 11 (cycles=2, all transitions receipted, adapt change fed the next cycle) |
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
