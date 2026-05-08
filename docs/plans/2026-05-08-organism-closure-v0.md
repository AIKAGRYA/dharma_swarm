# Organism Closure v0

**Date locked:** 2026-05-08
**Status:** SHIPPED — closure proof green
**Owner:** Track 4
**Subordinate to:** [`docs/governance/CANONICAL_DOC_STACK.md`](../governance/CANONICAL_DOC_STACK.md), [`docs/governance/SOVEREIGN_MANIFEST.md`](../governance/SOVEREIGN_MANIFEST.md)

This plan documents a self-contained, file-native proof that the organism's
evidence changes its next decision. It is implemented as a single module
(`dharma_swarm/operator_core/closure_v0.py`, ≤300 LOC) plus deterministic
fixtures, and proves closure with one diff: `expected_next_decision_success.json`
≠ `expected_next_decision_failure.json`.

The plan deliberately introduces no new substrate. Ontology promotion,
telic_seam recorder wiring, evolution.py evidence gate, and
ACTIVE_SURFACE_MANIFEST registration are deferred to v1+.

---

## North Star

`Jagat Kalyan → TelosObjective → VentureCell → WorkPacket → AgentOps →
EvidenceReceipt → VSMProjection → KaizenReviewLink → DarwinProposalCandidate →
NextDecision`

The loop is closed when, at any tick, replaying with success-evidence yields a
different `NextDecision.chosen_packet_id` than replaying with failure-evidence.
Tested by `tests/test_organism_closure_v0.py::test_t8_closure_proof_success_differs_from_failure`.

---

## Scope (locked)

- File-native dataclasses; no ontology ObjectType registration.
- JSON read/write helpers only; no SQLite, no new database.
- Imports: stdlib + `dharma_swarm.operator_core.operating_facts` only.
- `correlation_id` MANDATORY on every closure record.
- `DarwinProposalCandidate` is a data shape; never submitted to `evolution.py`.
- Module-private: nothing re-exported through `operator_core/__init__.py`.

## Forbidden in v0

```
dharma_swarm/ontology.py
dharma_swarm/telic_seam.py
dharma_swarm/evolution.py
dharma_swarm/dharma_kernel.py
dharma_swarm/telos_gates.py
dharma_swarm/agent_runner.py
dharma_swarm/swarm.py
dharma_swarm/orchestrator.py
dharma_swarm/operator_core/contracts.py
dharma_swarm/operator_core/__init__.py
dharma_swarm/shakti_executive/feedback_writer.py
dharma_swarm/ACTIVE_SURFACE_MANIFEST.yaml
docs/governance/*
docs/MEGAFILE_INDEX.md
docs/doctrine/*
docs/loomwork/*
~/.dharma/kernel.json
```

Audit: `git diff --stat` against `origin/main` confirms zero hot-file edits.

---

## Footprint

| File | LOC | Status |
|---|---|---|
| `dharma_swarm/operator_core/closure_v0.py` | 294 | new |
| `tests/test_organism_closure_v0.py` | ~280 | new |
| `tests/fixtures/organism_closure_v0/*` | 14 JSON + README + replay.sh | new |
| `docs/plans/2026-05-08-organism-closure-v0.md` | this file | new |

Hot files touched: 0. Ontology types added: 0. Databases: 0.

---

## Schemas (file-native, in `closure_v0.py`)

`TelosObjective`, `VentureCellRef`, `WorkPacket`, `EvidenceReceipt`,
`VSMProjection`, `KaizenReviewLink`, `DarwinProposalCandidate`, `NextDecision`.

All frozen `@dataclass`es. `correlation_id: str` required on the closure five.
`__post_init__` validates: WorkPacket review_tier ∈ {auto, review, human},
allowed/forbidden path overlap, EvidenceReceipt success ↔ test_exit_code
consistency.

## Pure functions

```
record_evidence_receipt(packet, agentops_fact, *, correlation_id, created_at, duration_ms=0.0) -> EvidenceReceipt
project_vsm(bundle, receipt, *, correlation_id, captured_at, recognition_seed_age_hours, ...) -> VSMProjection
kaizen_link(receipt, *, human_yds=None, waste_patterns=()) -> KaizenReviewLink
decide_next(projection, candidates, review, *, decided_at, expires_at, decided_by="policy") -> NextDecision
validate_darwin_candidate(c) -> tuple[bool, list[str]]
```

`decide_next` branches:

1. `truth_stale` (S4 freshness / algedonic / S5 integrity flagged) → `chosen_packet_id=None`, confidence 0.0.
2. `accepted ∧ candidates` → first candidate, confidence 0.7.
3. `not accepted` → None, "evidence_failed", confidence 0.2.
4. accepted but no candidates → None, "no_candidates", confidence 0.0.

---

## Determinism

- `correlation_id = "corr_v0_test_001"` is hard-coded in the test.
- `created_at`, `captured_at`, `decided_at`, `expires_at` are fixed strings.
- Object IDs use `blake2s(prefix, *parts)` — no `time.time()`, no `uuid4`, no random.
- Replay determinism is asserted by `test_t9_replay_determinism`.

## Closure proof

```bash
diff tests/fixtures/organism_closure_v0/expected_next_decision_success.json \
     tests/fixtures/organism_closure_v0/expected_next_decision_failure.json
# Exit 1. The diff:
#   chosen_packet_id: "wp_v0_test_001"  →  null
#   confidence:       0.7               →  0.2
#   reason:           evidence_accepted →  evidence_failed
#   input_refs:       (kaizen+evidence IDs propagate)
```

That non-zero exit IS the closure proof.

---

## Acceptance gate (run before each PR)

```bash
python3 -m pytest tests/test_organism_closure_v0.py -q             # 18 tests, all green
diff tests/fixtures/organism_closure_v0/expected_next_decision_success.json \
     tests/fixtures/organism_closure_v0/expected_next_decision_failure.json   # non-zero exit
grep -nE "from dharma_swarm\.(ontology|telic_seam|evolution|dharma_kernel|telos_gates|agent_runner|swarm|orchestrator)" \
     dharma_swarm/operator_core/closure_v0.py                       # zero matches
git diff --stat dharma_swarm/operator_core/__init__.py dharma_swarm/operator_core/contracts.py   # empty
wc -l dharma_swarm/operator_core/closure_v0.py                      # ≤ 300
bash tests/fixtures/organism_closure_v0/replay.sh                   # CLOSURE OK
```

## Cross-track status

```
Track-1-status: open@PR#166/excluded — closure_v0 is fully decoupled from
                feedback_writer; runs against in-memory facts only
PR-104-correlation: deferred — closure_v0 carries correlation_id: str directly
PR-150-namespace: VSMProjection scoped to closure_v0 module; not exported via
                  operator_core/__init__.py
PR-131-rebase-check: green — closure_v0 does not edit operator_core/contracts.py
                     or operator_core/__init__.py
```

## Out of scope (deferred to v1+)

- Ontology ObjectType promotion of `WorkPacket`, `EvidenceReceipt`, `VSMProjection`, `NextDecision`.
- `telic_seam.record_evidence_receipt` / `record_vsm_projection` / `record_next_decision` recorders.
- `evolution.Proposal.evidence_refs` invariant in `apply_diff_and_test`.
- `operator_core/__init__.py` public re-export of v0 types.
- `ACTIVE_SURFACE_MANIFEST.yaml` registration of vsm_projector / packet recorder.
- BR-002 full closure (board-side feedback resolver wiring).
- BR-007 runtime↔ontology sync.
- BR-008 VentureCell polymorphism (ontology vs Ginko).
- BR-014 BHED_GNAN hard-pass fix.
- Substrate graduation (Rust verifier, Datalog, Rego).

Each becomes its own bounded WorkPacket post-v0, using closure_v0 as the
contract baseline.

---

## Coherence Delta (BR-019 honor-system)

```
Stack-touched: dharma_swarm/operator_core/closure_v0.py (NEW), tests
Ledgers-affected: none (no DB / ledger writes)
Drift-introduced: file-native closure layer (ontology promotion deferred to v1)
Drift-resolved: closure-discipline contract proven; correlation_id discipline
                established; Darwin evidence-gate as data contract; partial
                schematic for BR-002 follow-up (closure object now exists
                independent of opportunity_board.json)
```
