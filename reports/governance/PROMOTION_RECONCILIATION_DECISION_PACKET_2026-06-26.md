# Promotion Reconciliation Decision Packet - 2026-06-26

Role: report
Subordinates to: `docs/governance/ACTIVE_TRACK.yaml`, `docs/governance/CANONICAL_DOC_STACK.md`
Replaces: no canonical doc; this is a scoped promotion decision packet and evidence index.

Status: operator-approved planning packet for scoped promotion lanes.

This packet distills the June 22 reconciliation findings, June 24 preservation pass, and June 26 operator approvals into one promotion plan. It intentionally excludes raw dumps, generated receipt floods, and dirty-worktree state as canonical code.

## Operator decisions captured

The operator approved:

1. Preserve the old-clone ignored `spec-forge/runtime-pipeline-hardening/` package before any old-clone cleanup.
2. Use this reconciliation packet as the first clean PR lane.
3. Exclude generated A2A and Cashclaw report floods from canonical PRs.
4. Treat the Operator Coherence Cockpit as a read-only projection and control tower only.
5. Perform no cleanup until every archive or discard item has its own receipt.

## Current authority baseline

- Code authority: `origin/main`.
- Baseline commit: `c53721d5f8aa713db88b5647b06682fa8ea50e98`.
- Baseline subject: `fix(governance): rigor-aware track readiness + enforced gate + onboard trust verdict (#695)`.
- This packet was authored from a fresh worktree:
  - path: `/Users/dhyana/worktrees/ds_reconciliation_promotion_20260626`
  - branch: `codex/reconciliation-promotion-20260626`
  - base: `origin/main`

Dirty worktrees remain evidence only. They are not promotion targets.

## Preservation baseline

Current preservation root:

`/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST`

Evidence:

- `receipts/BACKUP_RECEIPT.md` - local and off-machine backup recorded.
- `receipts/TRIANGULATION_SUMMARY.md` - current clean picture and at-risk surfaces.
- `trees/tree_preservation_summary.tsv` - per-tree dirty/untracked classification.
- `receipts/IGNORED_SPEC_FORGE_RUNTIME_PIPELINE_HARDENING_RECEIPT.md` - ignored old-clone spec-forge gap closed after operator approval.

Preservation is now sufficient to begin scoped PR extraction. It is not a cleanup authorization.

## Executive verdict

Promotion may proceed only as scoped PR lanes from clean `origin/main`.

Do not:

- bulk merge any dirty branch;
- merge the A2A/NATS stale worktree directly;
- treat generated reports as canonical artifacts;
- turn cockpit projections into a new truth store;
- delete or clean worktrees without an item-specific archive/discard receipt.

Ready for scoped extraction:

- reconciliation decision packet;
- A2A/NATS offline substrate slices;
- A2A operator runtime tools in prevalidate mode;
- A2A governance/readiness criteria hardening;
- cockpit canonicalization and proof-model hardening;
- ADR-010 scheduler federation;
- Helm closeout normalization;
- old-clone runtime-pipeline-hardening salvage;
- Cashclaw summary-first triage.

## Keeper inventory

### P0 current authority

- `origin/main`.
- `docs/governance/ACTIVE_TRACK.yaml` from `origin/main`.
- `reports/governance/active_track_evidence.*` from `origin/main`.
- June 24 preservation root and preserve refs.

### P1 near-term canonicalization

- A2A/NATS locked spec and verifier from `/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618`; before extraction, update `runtime-truth-nats-2026-06` owned surfaces if the lane will touch NATS transport implementation or `tests/test_nats_transport.py`.
- DGM/reconciliation decision material from `/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622`.
- Operator Coherence Cockpit PR #677 lineage already merged to `origin/main`.
- ADR-010 scheduler federation draft from dirty recovery evidence.
- Helm closeout packet from `/Users/dhyana/dharma_helm_build/reports/terminal/HELM_CLOSEOUT_2026-06-16.md`.
- Old-clone `spec-forge/runtime-pipeline-hardening/` package; because `spec-forge/` is ignored, any salvage PR must either land the packet under a tracked destination or explicitly unignore/force-add the intended files.

### P2 salvage or mining

- Cashclaw branch code deltas after excluding `reports/revenue_wedge/evolution/**`.
- Old-clone local-only commits as historical source material.
- A2A timestamped readiness reports for distilled evidence only.

### P3 evidence only

- Timestamped A2A run reports.
- Reconciliation raw inventories and command dumps.
- Throwaway mandala cockpit topology.
- Dirty recovery-branch active-track projections.

## Archive and discard inventory

| Surface | Current handling | Later action |
|---|---|---|
| `reports/a2a/**` timestamped floods | Archive-only | Discard only after distilled evidence PR and receipt |
| Reconciliation raw dumps | Archive-only | Keep out of canonical docs unless summarized |
| `reports/revenue_wedge/evolution/**` | Archive-only noise | Discard only after operator receipt |
| Old clone wholesale history | Archive-only | No bulk import |
| Throwaway cockpit topology | Archive-only | Do not promote as canonical cockpit |
| Dirty recovery checkout | Evidence only | Never use as merge source |

## Promotion lanes

| Lane | First PR scope | Exclusions | Verification gate | Approval state |
|---|---|---|---|---|
| Reconciliation decision packet | This distilled packet | Raw dumps and generated inventories | `git diff --check`; governance/doc checks | Approved |
| A2A offline substrate | Locked spec pointer, topology contract, fixture verifier, NATS substrate tests after owned-surface alignment | Live publish, credentials, timestamped reports | `pytest tests/test_nats_transport.py tests/test_a2a_spec_conformance.py`; contract checker | Approved for clean extraction |
| A2A operator runtime tools | Prevalidate scripts, explicit blockers, domain-receipt checks | Live mode, model calls, quorum claims | Existing Make/Python targets only: `make onboard`, `python3 scripts/governance/check_nats_substrate_contract.py`, and targeted pytest wrappers added by that lane | Approved for prevalidate-only extraction |
| A2A governance/readiness | Replace existence-only NATS readiness with rigorous evidence requirements | Production-ready claims | `make onboard`; track checker | Approved |
| Cockpit canonicalization | Normalize existing read-only cockpit lineage | New truth store, mutating command system | Dashboard lint/build and API smoke | Approved as read-only projection |
| Cockpit proof hardening | Canonicality badges, production readiness cards, evidence links | Broad redesign | Focused model tests; dashboard build | Approved |
| ADR-010 scheduler federation | Doc-only ADR ratification | Reconciler daemon or cron mutation | Doc check; name drift if objects added | Approved |
| Helm closeout normalization | Promote closeout packet and merge recipe | Large terminal code merge | Terminal PR gates later | Approved |
| Old-clone runtime hardening | Preserve and optionally salvage spec packet | Old-clone wholesale import | Spec self-check | Approved |
| Cashclaw triage | Summarize real code delta and revenue truth | Generated evolution reports | Focused tests if code survives | Approved |

## Recommended order

1. Preserve ignored old-clone `spec-forge/runtime-pipeline-hardening/`. Done; see receipt in the June 24 preservation root.
2. Land this reconciliation decision packet.
3. Land A2A governance/readiness criteria hardening.
4. Align `runtime-truth-nats-2026-06` owned surfaces for any NATS transport/test extraction.
5. Extract A2A offline substrate.
6. Extract A2A prevalidate operator tools using existing verifier commands or adding the verifier target in that same lane.
7. Canonicalize cockpit as read-only projection.
8. Harden cockpit proof model.
9. Ratify ADR-010.
10. Normalize Helm closeout.
11. Triage Cashclaw.

## Hard blockers

- A2A/NATS worktree is stale relative to `origin/main`; extract patches only.
- A2A extraction must not edit outside declared ACTIVE_TRACK owned surfaces; update ownership first if the lane needs NATS transport implementation or test surfaces.
- A2A still lacks live `DOMAIN_RECEIPTED`, live ACL, semantic liveness, and five-agent quorum proof.
- Dirty active-track projections conflict with origin evidence.
- Cockpit must not become an authority surface.
- Cleanup/discard still requires item-specific receipts.
- Old-clone `spec-forge/` salvage must account for `.gitignore`; use a tracked destination or explicit unignore/force-add with provenance.

## Next approved action

After this packet is verified, the next lane is A2A governance/readiness hardening: make the NATS active-track evidence require rigorous proof instead of passing on existence-only checks.
