# Promotion Proposals — DGM Clean Truth Surface (2026-06-23)

## Principle

Parallel work is allowed. The promotion gate is not a clean single-threaded workspace; it is **no invisible, unclassified, unpreserved, unowned, or unreceipted work**.

Promotion path:

```text
parallel lane
→ cockpit-visible card
→ preserved/off-machine if valuable
→ lane admission packet
→ production-readiness/admission review
→ ACTIVE_TRACK admission, fold into an existing active track, or archive-after-preserve after off-machine preservation + operator approval
```

## Wave 0 — unblock truth visibility

1. **Preservation confirmation**  
   Confirm that `/Users/dhyana/.dharma/preservation/dgm_reconciliation_20260622` and high-value overlays have an off-machine copy. Local preservation exists; off-machine safety remains uncertain.

2. **STOP_BUILD surfaced in cockpit**  
   Treat `/Users/dhyana/.dharma/STOP_BUILD` as an unresolved Arena/Cockpit admission blocker until a test-regression verification explicitly clears it.

3. **PR queue triage**  
   GitHub auth is currently available. Open PR queue observed: #676, #675, #674, #669, #668, #661, #660, #643, #642.

## Wave 1 — highest ROI promotions

### 1. Operator Coherence Cockpit Control Tower

- Proposed track: `operator-coherence-cockpit-control-tower-2026-06`
- Source canonicality: `dirty`
- Source branch: `telos-ai-seed-v0-from-sandbox`
- Extraction branch: `governance/operator-coherence-cockpit-20260623`
- Why first: DGM should consume a clean control-tower read model, not raw local state.
- Gate:
  - JSON projection validates.
  - Markdown receipt generated.
  - Dashboard build/lint passes.
  - Every card has evidence and canonicality labels.
  - Dirty checkout truth is explicitly labeled candidate/noncanonical.

### 2. Orchestration Arena v1

- Proposed track: `orchestration-arena-v1-2026-06`
- Source canonicality: `on-main`
- Evidence: #670 landed at `4137e83c3d0e6fb18a9182d3842c6a34b77a585c`.
- Why: substrate exists but active-track governance does not reflect it.
- Gate:
  - Frozen task battery.
  - Orchestration genome schema.
  - Council/verifier hook.
  - Score: VerifiedCapabilityDelta × Trust / (cost × latency × fragility).
  - Best-single-model baseline and decorrelated verifier controls.

### 3. Revenue External-Human Receipt

- Proposed track: `revenue-external-human-receipt-2026-06`
- Source canonicality: `candidate` + `dirty` inputs.
- Inputs: on-main revenue spine, `cashclaw/revenue-hydra-v1`, revenue wedge branch.
- Why: fixes revenue objective gap.
- Gate: at least one external human reads/replies/acts or a cash receipt exists.
- Non-goal: broad revenue automation without a real receipt.

### 4. Research-Depth Verified Sensemaking

- Proposed track: `research-depth-verified-sensemaking-2026-06`
- Source canonicality: mixed `on-main`, `local-only`, and `stash`.
- Inputs: #663 Chetana MarkItDown, Palantir pilot, persistent-agent research, Moltbook investigation, ontology ADR.
- Why: fixes research-depth objective gap.
- Gate: source cards + claim extraction + decorrelated verification + paper-grade claim packet.

## Wave 2 — fold into active themes

| Candidate | Fold target | Condition |
|---|---|---|
| #675 provider discoverability | `loop-closure-2026-06` / `provider-routing-consolidation-2026-06` | Review clean PR head separately from dirty overlay; live provider canary for closure. |
| #674 closure gate | Runtime truth / cockpit governance | Reconcile with tracks-consolidation grading branch before landing overlapping closure logic. |
| `ds_supplychain_slice` local tip | `bronze-boundary-ledger-throat-consumer-2026-06` | Port only unique post-#648 residue. |
| `ds_a2a_nats_rebuild_preflight_20260618` | `a2a-nats-live-readiness-2026-06` | Fresh live ack proof required. |
| Holon L4 dirty files / `organ/03-seat` | `holon-l4-production-proof-2026-06` | Split Build A readiness from standing composer proof. |

## Wave 3 — archive-after-preserve candidates

- Stale duplicate branch refs.
- Restack/backlog/salvage refs represented elsewhere.
- Superseded draft ops-report PR family after a policy decision.
- Empty sibling dirs whose value exists only in stashes or PR history.
- Old UI experiments if they do not serve the current cockpit V2 direction.

Only after off-machine preservation + operator approval.

## Promotion order recommendation

1. Cockpit extraction branch.
2. Arena v1 governance admission.
3. PR #675 provider discoverability triage.
4. PR #674 closure gate triage.
5. `ds_supplychain_slice` unique residue review.
6. Forge V1 scoreboard port as Arena experiment.
7. Revenue receipt pilot.
8. Research-depth verified sensemaking pilot.
