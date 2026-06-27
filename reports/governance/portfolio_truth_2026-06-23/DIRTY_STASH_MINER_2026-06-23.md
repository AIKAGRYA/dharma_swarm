# Dirty + Stash Miner — DGM Reconciliation (2026-06-23)

> Mode: READ-ONLY classification. No stash operation was performed.
> No dirty file was reset, cleaned, or committed. This artifact fills the gap
> left by the unreturned Dirty+Stash Miner scout in the original 6-agent fan-out.
>
> Baseline: `origin/main = 4137e83c3d0e6fb18a9182d3842c6a34b77a585c`
> Canonicality labels: on-main | open-pr | local-only | dirty | stash | off-repo | uncertain
> Every retirement statement uses: **archive-after-preserve after off-machine preservation + operator approval**.

## 1. Dirty working tree (211 porcelain entries on `telos-ai-seed-v0-from-sandbox`)

Status kinds: 113 modified (` M`), 97 untracked (`??`), 1 staged removal-status entry (`D `).
Canonicality of the entire overlay: **dirty** (candidate, not canonical).

### Theme clusters (by top-level path)

| Cluster | Top-level prefixes | Approx entries | Theme | Disposition |
|---|---|---:|---|---|
| Tests overlay | `tests/` | 55 | spans Holon L4, runtime-truth, A2A, cockpit, refinery | Preserve; extract per-track with the code they cover. |
| Core engine overlay | `dharma_swarm/` | 48 | Holon L4, A2A cloud/contact/verifier, GAIA, Palantir, runtime_context, insight bridge | Preserve; split by theme (Holon vs A2A vs research vs runtime). |
| Docs overlay | `docs/` | 31 | architecture (A2A cloud bridge, orchestrator spec), research/telos personas, governance schemas, missions | Preserve; fold design docs with their lanes. |
| Scripts overlay | `scripts/` | 28 | Holon L4 service/supervisor, runtime-truth burn-in/closeout/audit, A2A inbox-bridge launchd, research ingest | Preserve; extract with owning lane. |
| Reports overlay | `reports/` | 18 | cockpit v2 receipt, lane_admission, A2A specs, governance reconciliation, sovereign holons | Preserve; these are evidence — keep with cockpit/governance extraction. |
| Dashboard overlay | `dashboard/` | 10 | operator-coherence components/hooks/lib (cockpit V2) | Preserve; this is the cockpit UI lane — primary extraction target. |
| API overlay | `api/` | 4 | `routers/operator_coherence.py` + main wiring | Preserve; extract with cockpit backplane. |
| Root markdown / config | `Makefile`, `CLAUDE.md`, `*.md`, `.gitignore`, `com.dharma.swarm.plist`, `synthesizer_memory.json` | ~12 | mixed holon/substrate proofs + launchd plist | Review individually; root proofs are likely fold-into-holon-track. |

### Highest-priority dirty extraction targets (engineering, not operator-only)

1. **Cockpit / backplane** — `api/routers/operator_coherence.py`, `dashboard/src/components/operator-coherence/`, `dashboard/src/hooks/useOperatorCoherence.ts`, `dashboard/src/lib/operatorCoherence.ts`, `dharma_swarm/operator_core/operator_coherence_cockpit.py`, `scripts/runtime/operator_coherence_cockpit.py`, `tests/test_operator_coherence_cockpit.py`, plus cockpit V2 reports. → extract to `governance/operator-coherence-cockpit-20260623`.
2. **Holon L4** — `dharma_swarm/holon_l4_*.py`, `dharma_swarm/holon_*.py`, `scripts/holon_l4_*.py`, `tests/test_holon_*.py`. → feeds `holon-l4-production-proof-2026-06`.
3. **A2A / NATS** — `dharma_swarm/a2a/a2a_cloud_contact.py`, `contact_registry.py`, `verifier.py`, `scripts/*_a2a_inbox_bridge_fleet_launchd.sh`, `reports/a2a/*`, `tests/test_a2a_cloud_contact.py`. → feeds `a2a-nats-live-readiness-2026-06`.
4. **Runtime truth** — `dharma_swarm/runtime_context.py`, `scripts/runtime/runtime_truth_{burn_in,closeout,100_audit}.py`, `mark_runtime_truth_clean_epoch.py`, `runtime_task_backlog_firebreak.py`, `daemon_operator_status.py` + tests. → fold into `runtime-truth-reconciliation-2026-06` after fresh DB receipt.
5. **Research-depth** — `dharma_swarm/palantir_pilot_*.py`, `scripts/research/palantir_*.py`, `docs/research/telos_ai/persona_agents/*`. → feeds `research-depth-verified-sensemaking-2026-06`.
6. **GAIA / revenue-adjacent** — `dharma_swarm/gaia_initiative.py`, `docs/missions/2026-06-20_jagat_kalyan_gaia_execution_spine.md`. → incubate under revenue/external-value.

## 2. Stash census (70 stashes, all label `stash`, locally preserved as `refs/preserve/dgm-20260622/stashes/stash-000..069`)

### Theme buckets

| Bucket | Stash indices | Count | Value | Disposition |
|---|---|---:|---|---|
| Worktree-cull holds (2026-06-18) | 1–7 | 7 | low/medium; snapshots taken during a worktree cull | archive-after-preserve after off-machine preservation + operator approval. |
| Telos/cockpit design WIP | 8, 9 | 2 | medium (design background) | Mine concepts only; cockpit V2 remains authoritative. Do not revive as implementation. |
| Spine-adoption WIP | 10, 11, 12 | 3 | medium | Compare against on-main spine adoption; mine non-duplicate only. |
| Trust-build-compass / provider gate WIP | 13–17 | 5 | medium (provider tool-call gate) | Compare to PR #675 / provider-honesty; fold unique gate logic. |
| Runtime-truth spine e2e WIP | 18, 19, 21 | 3 | medium/high (execution identity spine v2) | High-signal; preserve and diff against landed runtime-truth. |
| C2 approval enforcement WIP | 20 | 1 | medium | Governance gate; review with closure-gate PR #674. |
| Command-plane nav / UI experiments | 22–30 | 9 | low for impl; history only | Old UI rounds; do not create competing front doors. Keep as preserved history. |
| Persistent-agents research | 31, 32 | 2 | high (research-depth) | Feeds `research-depth-verified-sensemaking-2026-06`. Mine as source cards. |
| Memory-kernel lane holds (2026-05) | 33–41 | 9 | low/medium | Mostly superseded; archive-after-preserve after off-machine preservation + operator approval. |
| Phase2 governance isolation / interop | 42–44 | 3 | low/medium | Quarantine snapshots; review then archive-after-preserve. |
| Holistic-sweep cleanup-holds (2026-05-03) | 45–64 | 20 | mixed; some large (entries=50, 54, 34, 16) | Index by source worktree; high-entry ones (57=54, 62=50, 60=34) deserve inspection before any archive-after-preserve. |
| Chetana grand-memory | 61 | 1 | medium/high (research-depth) | Feeds Chetana/research lane. |
| Tier-1 governance pre-merge | 65 | 1 | medium | Historical canonical-governance snapshot; preserve. |
| `main`-based WIP | 66–69 | 4 | medium (integration fixes, dashboard, Bun TUI) | Diff against current main; fold any unique fix. 66/67 are duplicates. |

### Stashes worth promoting/mining (not archive)

- `stash@{21}` execution identity spine v2 WIP — runtime-truth high signal.
- `stash@{18}`/`stash@{19}` runtime-truth spine e2e reconciliation slices.
- `stash@{31}`/`stash@{32}` persistent-agents research — research-depth gap.
- `stash@{61}` Chetana grand-memory — research-depth/ingest.
- `stash@{13}`–`stash@{16}` provider tool-call gate — compare to PR #675.
- `stash@{52}` (entries=16), `stash@{57}` (entries=54), `stash@{60}` (entries=34), `stash@{62}` (entries=50) — large holistic-sweep snapshots; inspect before any retirement.

### Stashes that are pure history (archive-after-preserve candidates only)

- Worktree-cull holds (1–7), command-plane UI rounds (22–30), most memory-kernel holds (33–41), low-entry holistic-sweep holds.

All of the above require **off-machine preservation + operator approval** before any retirement.

## 3. Preservation cross-check

- All 70 stashes are mirrored at `refs/preserve/dgm-20260622/stashes/stash-000..069` and in `all_local_branches_and_stash_refs.bundle`.
- Local preservation **exists**; off-machine preservation is **uncertain** — confirm before any archive-after-preserve action.
- The dirty overlay on `telos-ai-seed-v0-from-sandbox` is captured in the preservation packet's `dirty_checkout` / `dirty_checkout_followup_20260622T1400Z` snapshots.

## 4. Uncertainty notes

- Stash *contents* were not expanded (no `git stash show -p`); classification is by stash subject line + branch context. Treat per-stash value as a strong hint, not a verified diff.
- Duplicate stashes exist (e.g. 66/67); dedupe at review time.
- Some "cleanup-hold" stashes reference worktrees that may no longer exist; resolve at preservation-confirmation time.
