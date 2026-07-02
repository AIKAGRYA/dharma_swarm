# cybernetics_codex Audit

- observed_at: `2026-07-02T04:00:31.987075Z`
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
- delegation_runs: `8834` total, `4182` completed, `4530` failed
- receipt_json: `2680` rows `(orchestrator surface; A2A empty is success)`
- served_provider_truth: delegation completed `1941/4182`, runtime_receipts `24624` rows

## Harness Replays

- loop1_report: `/Users/dhyana/dw-worktrees/g/reports/loop_closure/cybernetics_codex/2026-06-23_loop1_ollama_fresh_spine_dispatch.json`
- loop1_closed: `True`
- loop1_tasks: `3/3`
- loop1_dispatch_dropoffs: `0`
- loop1_evidence_receipts_ok: `3`

## Verdict Tiers

- `HARNESS_PROVEN`: bounded replay/regression evidence passed; not production-live closure.
- `CLOSED_LIVE`: declared live owner-surface evidence passed.

## Loop Statuses

| # | Loop | Verdict | Boundary | Live Owner-Surface Criterion |
|---|---|---|---|---|
| 1 | Swarm Task Loop | HARNESS_PROVEN | bounded replay proves current Loop 1 harness (3/3 completed, dispatch_dropoff=0, evidence_receipts_ok=3, served_provider_truth=999); not CLOSED_LIVE while the audited daemon history still includes dispatch_dropoff=2191 | runtime.delegation_runs/runtime_receipts in the audited daemon scope show real completed provider work, zero dispatch_dropoff, and a later routing/adaptation read caused by that work |
| 2 | Organism Heartbeat | HARNESS_PROVEN | bounded closure replay proves the loop 2 harness (cycles=3, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | standing organism pulse/algedonic owner surface shows a non-scratch daemon cycle whose adaptive state is consumed by a later daemon cycle |
| 3 | Evolution Loop / DarwinEngine | HARNESS_PROVEN | bounded closure replay proves the loop 3 harness (cycles=2, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live DarwinEngine/evolution archive owner surface shows a governed non-scratch proposal outcome consumed by a later predictor/archive selection without internal fitness contamination |
| 4 | Consolidation Loop / Memory | HARNESS_PROVEN | bounded closure replay proves the loop 4 harness (cycles=2, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live memory owner surface shows external/completed work, not the closure script itself, consolidated and consumed by later context |
| 5 | Zeitgeist Scanner | HARNESS_PROVEN | bounded closure replay proves the loop 5 harness (cycles=2, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live zeitgeist/environment owner surface shows non-synthetic external signals changing a later gate/priority decision |
| 6 | Witness Auditor | HARNESS_PROVEN | bounded closure replay proves the loop 6 harness (cycles=4, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live witness/runtime receipt owner surface shows production completions audited and governance marks consumed by downstream routing |
| 7 | Training Flywheel | HARNESS_PROVEN | bounded closure replay proves the loop 7 harness (cycles=1, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live trajectory owner surface contains non-synthetic recent trajectories that the flywheel scores and persists into later strategy selection |
| 8 | Recognition Loop / eigenform | HARNESS_PROVEN | bounded closure replay proves the loop 8 harness (cycles=2, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live recognition/context owner surface shows non-scratch loop-history receipts generating a seed later consumed by an agent context build |
| 9 | Conductors | HARNESS_PROVEN | bounded closure replay proves the loop 9 harness (cycles=2, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live conductor/cron owner surface shows production scheduler state changed by observed signals and suppressing/altering a later tick |
| 10 | Context Agent | HARNESS_PROVEN | bounded closure replay proves the loop 10 harness (cycles=2, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live context-package owner surface shows production memory inputs changing a served context package later read by an agent |
| 11 | Replication Monitor | HARNESS_PROVEN | bounded closure replay proves the loop 11 harness (cycles=2, all transitions receipted, adapt change fed the next cycle); not CLOSED_LIVE until live owner-surface criterion passes | live replication owner surface shows a real proposal materialized into roster/probation state and observed by a later monitor cycle |
| 12 | Self-Improvement | BLOCKED | guardian quorum below threshold: N=3/5, M=1/3 | One Wire quorum N>=5, M>=3, and explicit archive-fitness authority |
| 13 | Free Evolution Grind | BLOCKED | guardian quorum below threshold: N=3/5, M=1/3 | One Wire quorum N>=5, M>=3, and explicit archive-fitness authority |

## Verifier Commands

- `make onboard`
- `make orient`
- `.venv/bin/dgc status`
- `.venv/bin/dgc loop-status`
- `bash scripts/runtime/codex_toolbelt_status.sh`
- `python3 scripts/governance/cybernetics_codex_audit.py --json`
- `python3 scripts/governance/register_cybernetics_codex.py --dry-run`
- `pytest -q tests/test_cybernetics_codex.py tests/test_manifest_health.py`
