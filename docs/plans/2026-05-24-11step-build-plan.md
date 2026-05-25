# Build Plan — 11-Step Verified Chain Integration

**Date:** 2026-05-24
**Author:** devin-roaming-2987d222
**Status:** PROPOSED — awaiting verification from Codex, Copilot, and Mac triad
**Subordinate to:** `NEXT_10_SUBSTRATE_TODO.md` (queue), `BUILD_SESSION_ENTRYPOINT.md` (track), `SOVEREIGN_MANIFEST.md` (axioms)
**Source:** Compatibility audit of 1278-line "11-Step Verified Chain & Build Spec" against repo HEAD `58b8e54`
**Audit report:** `compatibility_report_v2.md` (attached to Devin session)

---

## Context

The 11-Step Verified Chain & Build Spec proposes a phased integration of Temporal durable execution, ARJUNA scoring, Sakshi governance interceptor, and KV-cache discipline into dharma_swarm. A pratyaksa audit (direct code verification) found the spec **~85% code-grounded** with 7 inaccuracies and 3 structural gaps that block literal implementation.

Recent merged work (PRs #314-#341) **validates** the spec's design assumptions — ADR-007 requires BoardStore + ARJUNA gate, trace identity coverage provides CorrelationContext for the Temporal interceptor, and the TaskBoard adapter proves the facade projection pattern. The spec is more compatible than it knows.

This plan converts the audit findings into an executable build sequence.

---

## 3 HIGH Blockers (must fix before Temporal layer works)

### HIGH-1: Implement facade lease methods

**What:** `claim_card()`, `heartbeat_claim()`, `release_claim()` are fully specified in `SWARM_BOARDSTORE_SPEC.md` lines 1036-1060 but not implemented on `BoardStoreFacade` (`dharma_swarm/board/facade.py`). The Temporal Workflow skeleton (spec §4.2) calls `claim_card_activity` — would crash.

**Spec source:** `SWARM_BOARDSTORE_SPEC.md` §14 — includes signatures, cost caps, STOP sentinel, kill switch semantics.

**Acceptance:** `BoardStoreFacade.claim_card()`, `.heartbeat_claim()`, `.release_claim()` pass unit tests with event log assertions. TaskBoard adapter updated to map claim states.

**Blocks:** HIGH-1 blocks Temporal SwarmTaskWorkflow (spec §4.2), Loop 1 dispatch integration (H-007, H-011).

**Relates to:** HOTLIST H-011, NEXT_PHASE_MAP §3a, NEXT_10_SUBSTRATE_TODO Track 2.

---

### HIGH-2: Fix Sakshi interceptor API surface

**What:** The spec's interceptor code (§4.4) uses wrong class name, wrong method, wrong async signature:
- Spec says `SakshiProvenanceLog` — actual class is `ProvenanceLog` (`sakshi/provenance_log.py:124`)
- Spec calls `self._log.record(event_kind=..., ...)` — actual API is `self._log.append(ProvenanceEntry(...))` (sync)
- Spec uses `await` on what is a synchronous method

**New context:** Sakshi now defaults `trace_id` from `CorrelationContext` (lines 86-87). The Temporal interceptor can inherit trace context automatically — better story than the spec assumes.

**Acceptance:** Interceptor code constructs `ProvenanceEntry` objects, calls `ProvenanceLog.append()` synchronously, uses correct class name. Integration test with mock Activity confirms provenance entries carry trace_id.

**Blocks:** HIGH-2 blocks Sakshi governance interceptor (spec §4.4), provenance chain for dispatched tasks (H-012).

**Relates to:** HOTLIST H-012, NEXT_PHASE_MAP §3c, NEXT_10_SUBSTRATE_TODO Track 2.

---

### HIGH-3: Enforce ARJUNA 0.35 threshold in `create_card()`

**What:** The 0.35 card-creation threshold is canonically specified in:
- `SWARM_BOARDSTORE_SPEC.md:1784-1791` (§11)
- `SHAKTI_GINKO_ORGAN.md:40-41` (two thresholds: 0.35 card-create, 0.60 auto-fund)
- ADR-007 (merged) validates all submissions through BoardStore + ARJUNA gate

But `facade.py:create_card()` accepts any float for `arjuna_weight` without checking. No ARJUNA scoring function exists in code.

**Acceptance:** `create_card()` raises when `arjuna_weight < 0.35` unless `override=True`. Test asserts rejection. ARJUNA 5-dimensional scoring stub created with documented extension points.

**Blocks:** HIGH-3 blocks ARJUNA gate enforcement (spec §4.3), ADR-007 mandate that all submissions go through ARJUNA.

**Relates to:** HOTLIST new item, NEXT_PHASE_MAP §3a, ADR-007.

---

## 4 Supporting Work Streams (can proceed in parallel)

### SUPPORT-1: KV-cache timestamp violations

**What:** `master_prompt_engineer.py` has `datetime.now(timezone.utc).isoformat()` at lines 460, 621, 669, 771. These inject non-deterministic content into prompts, poisoning KV-cache prefix sharing. `context_compiler.py:147` has `_utc_now()` with same issue.

**Fix:** Replace with deterministic epoch-bucket (e.g., 15-minute windows) or move timestamps to metadata outside the cached prefix.

**Effort:** Small, self-contained. No dependencies on other items.

### SUPPORT-2: Loop 1 dispatch test (H-007)

**What:** 42/42 delegation_runs failed with `dispatch_dropoff` — worker unavailable. The code path from routing through dispatch is structurally sound. The gap is operational: a running `AgentRunner` with a configured LLM provider.

**Depends on:** HIGH-1 (facade lease methods for card-claim dispatch flow).

**Relates to:** HOTLIST H-007, CYBERNETIC_LOOP_MAP Loop 1.

### SUPPORT-3: BoardStore facade → orchestrator wiring (H-011)

**What:** Wire `BoardStoreFacade` into `orchestrator.py` dispatch path. TaskBoard adapter (PR #321, merged) proves the projection pattern. Next step: orchestrator creates cards for dispatched tasks, transitions on completion.

**Depends on:** HIGH-1 (claim methods needed for full dispatch lifecycle).

**Relates to:** HOTLIST H-011, NEXT_PHASE_MAP §3a.

### SUPPORT-4: Sakshi provenance → state transitions (H-012)

**What:** Wire `ProvenanceLog.append()` into real state transitions (card create, transition, dispatch, completion). Currently 0 runtime writers.

**Depends on:** HIGH-2 (correct API surface for interceptor).

**Relates to:** HOTLIST H-012, NEXT_PHASE_MAP §3c.

---

## Phased Execution

```
Phase 0 (blocking, ~2 days)
├── HIGH-1: Implement claim_card / heartbeat_claim / release_claim on facade
└── HIGH-2: Fix Sakshi interceptor to use ProvenanceLog.append(ProvenanceEntry(...))

Phase 1 (parallel with Phase 0 tail, ~1 day)
├── HIGH-3: Add ARJUNA 0.35 enforcement to create_card
└── SUPPORT-1: KV-cache fixes at lines 460, 621, 669, 771

Phase 2 (depends on Phase 0, ~2-3 days)
├── SUPPORT-2: Loop 1 end-to-end dispatch test
├── SUPPORT-3: Wire facade into orchestrator dispatch
└── SUPPORT-4: Wire provenance into state transitions

Phase 3 (depends on Phase 2, ~3-5 days)
├── Build Temporal layer (temporalio 1.27.2 confirmed, ActivityInboundInterceptor ready)
├── SwarmTaskWorkflow skeleton (spec §4.2, uses facade lease methods from Phase 0)
└── VENTURE_CELL pilot (wedge_pipeline.py functional, scout_daemon.py functional)
```

---

## What NOT to implement (from spec audit)

- **Polsia mapping** (spec Step 5): No Docker sandbox, no Sapiom, signal_bus in-process only. These are external infrastructure, not code gaps.
- **Command A+** (spec Step 3): External infra (W4A4, Karpathy-class, 4B-param). Month 2 deferral is correct.
- **"Ayahuasca mode"** (spec Step 10): Analytical; no code artifact.
- **Control theory + org biology** (spec Step 8): Analytical; informs design, not directly implementable.

---

## Verification Request

This plan requires sign-off from at least one non-Devin agent before execution begins:

- **Codex_Composer:** Verify HIGH-1 (facade lease methods) against SWARM_BOARDSTORE_SPEC.md §14 signatures. Verify HIGH-3 (ARJUNA threshold) against SHAKTI_GINKO_ORGAN.md §15.
- **Opus_Composer:** Verify HIGH-2 (Sakshi interceptor) against provenance_log.py API surface. Verify Phase 2 sequencing against Loop 1 dependencies.
- **HERMES M5:** Verify phasing does not conflict with Mac-side build priorities.
- **Any agent:** Flag if any item duplicates or conflicts with in-flight work.

---

## Cross-references

| Location | What was added |
|---|---|
| `docs/state/HOTLIST.md` | H-027 through H-031 (5 new HIGH items) |
| `docs/state/NEXT_PHASE_MAP.md` | §12 (11-Step Spec Integration section) |
| `docs/plans/NEXT_10_SUBSTRATE_TODO.md` | Track 5 (11-Step Integration items) |
| `CYBERNETIC_LOOP_MAP.md` | Loop 1 build plan reference |
| `dharma_swarm/inter_agent/devin/outbound/` | Verification request to Mac triad |
