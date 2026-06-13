# Active 10 Cleanup Portfolio Proposal

Status: proposal only. Do not treat this as a live track declaration.
Authority remains `docs/governance/ACTIVE_TRACK.yaml`.

## Intent

The operator wants the system capable of holding up to 10 active tracks with
clear, clickable internal structure. The cleanup-first interpretation is:

- Keep 10 as the ceiling and eventual operating capacity, not today's standing
  WIP target.
- Reconcile dirty lanes and stale shippable tracks before renaming canon.
- Give each active track a generated history/index page that links existing
  receipts where they already live.
- Use flat phases instead of recursive subtracks: max 5 phases per active
  track, max 3 named seams per phase.

## Promotion Gates

Do not promote this portfolio shape until these gates are true:

1. `runtime-truth-reconciliation-2026-06` has either been closed as shipped or
   explicitly renewed with non-proxy criteria.
2. `orientation-graph-2026-06` has its liveness ID and census-staleness defects
   fixed, then is closed as a projection track.
3. A2A/NATS remains open until production quorum is `READY`; it must not be
   closed merely because the old NATS criteria were weak.
4. The untracked quality seed in `/Users/dhyana/dharma_swarm/docs/quality/` is
   either committed, superseded, or explicitly withdrawn.
5. TAM's worktree is rebased and promoted by operator keystroke, not by a
   self-declared lane note.
6. The holon package-consolidation drift is assigned an owner and either lands,
   gets shelved, or is explicitly decoupled from active-track restructuring.
7. Generated track-history pages are implemented as projections over existing
   receipt homes; no new receipt authority subtree is introduced.

## Proposed Active Shape

1. `runtime-truth-spine-prod-cutover-2026-06`
   - Rename/supersede `runtime-truth-spine-adoption-2026-06`.
   - Purpose: production dispatch saturation through the runtime truth spine.
   - Candidate phases: bypass-drain, default-on flag, 24h dispatch coverage.

2. `a2a-runtime-spine-2026-06` or `a2a-consumption-closure-2026-06`
   - Keep open until target-owned Fable/Hermes quorum records exist.
   - Purpose: hot-contact transport, consumption closure, route health, quorum.
   - Candidate phases: broker truth, consumer registry, route health, quorum.

3. `loop-closure-2026-06`
   - Keep one top-level track for all 13 cybernetic loops.
   - Purpose: loop-by-loop closure receipts without spawning 13 tracks.
   - Candidate phases: loop-1 closure, phase-1 campaign, retrospective.

4. `composer-holon-spine-longrun-2026-06`
   - Keep visible because HOLON is a real contender.
   - Purpose: persistent-agent harness, orchestration, wake proof.
   - Candidate phases: package decision, orchestrator heart, provider proof.

5. `tam-venture-operator-2026-06`
   - Promote only after operator approval and rebase/PR.
   - Purpose: revenue-external-humans-served coverage.
   - Candidate phases: operator seed, cloud/CLI proof, first venture cell.

6. `quality-harmony-2026-06`
   - Promote from the existing quality cartography seed, not a parallel build.
   - Purpose: repo quality, coherence, invariants, cross-track hygiene.
   - Candidate phases: seed commit, membrane scheduling, ratchets, exemplars.

7. `whole-system-truth-federation-2026-06`
   - Proposed only until it has a named consumer.
   - Purpose: read-only federation over GitNexus, memory, runtime.db, A2A,
     wiki, receipts, and worktrees. No new truth store.
   - Candidate phases: consumer definition, source registry, query API.

8. `research-depth-2026-06`
   - Operator must choose the actual research wedge.
   - Purpose: close the standing research-depth coverage gap without inventing
     filler work.
   - Candidate phases: scope selection, evidence protocol, publication packet.

9. `operator-helm-cockpit-2026-06`
   - Promote only if the operator wants Helm governed by this repo portfolio.
   - Purpose: terminal/operator UI integration when it stops being a manual
     external lane.
   - Candidate phases: ownership decision, receipt bridge, golden gate.

10. Surge slot
    - Do not predeclare in `ACTIVE_TRACK.yaml`.
    - Purpose: keep one empty capacity slot for urgent, non-overlapping work.

## Cleanup Queue

Immediate cleanup should happen before portfolio promotion:

- Fix Orientation Graph projection defects and add tests.
- Create generated per-track index pages as read models.
- Close or renew shippable tracks with honest closure notes.
- Rebase and decide TAM.
- Decide the untracked quality seed.
- Decide the dirty holon package-consolidation lane.
- Keep A2A focused on quorum and consumption closure, not more producers.

## Subtree Model

The operator's desired subtree shape is valid as a navigation model, not as a
second authority model:

```text
track
  phase 1..5
    seam 1..3
      links to existing receipts, code, tests, docs
```

The generated page may live under a future `docs/governance/active_track_views/`
directory, but its content must be regenerated from `ACTIVE_TRACK.yaml`, git,
and receipt locations. Receipt files stay where their owners already write them.
