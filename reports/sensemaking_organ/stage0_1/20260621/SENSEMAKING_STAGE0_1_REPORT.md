# Sensemaking Organ — Stage 0/1 Report

**Track:** seeing-organ-2026-06 · **Status:** Stage 0 PASS, Stage 1 PASS, Stage 2 DESIGN-ONLY · No external action enabled.

## What was wired
- **Stage 0 — safety substrate** (`dharma_swarm/world_radar/safety.py`): untrusted-by-default envelope verification
  (`verify_provenance_envelope`), instruction/data separation **by construction** (`render_untrusted_for_context`
  fences untrusted text so a payload cannot forge the boundary), `classify_instruction_risk`, `fence_intact`,
  advisory `scan_injection_markers`.
- **Stage 1 — Frontier Council verifier** (`dharma_swarm/world_radar/frontier_council.py`): consumes a boundary
  signal, cross-falsifies across 3 decorrelated fixture evaluator families (skeptic/builder/domain_reader), and
  emits a `WorldSensemakingReceipt`. Corroboration requires ≥2 decorrelated evaluator families AND ≥2 decorrelated
  source families; poisoned/high-risk signals are quarantined; every receipt stamps
  `no_action_authority=True, dispatch_authority=False`. Hermetic — live LLM evaluators env-gated
  (`DHARMA_FRONTIER_COUNCIL_LLM`) and OFF by default.

## What remains severed (next PRs)
- Stage 2: Shakti reads corroborated receipts → advisory warrant-pressure (read-only; DISPATCH_AUTHORITY stays
  False). Design seam in `docs/architecture/SENSEMAKING_ORGAN.md`; not yet implemented.
- Stage 3: `WorldProposal` → existing Memory-Kernel/telos gates (first *gated* motor neuron).
- Receipt durable integration onto spine.EvidenceReceipt (currently JSON receipts + replay report).

## Owner files
- intake: `dharma_swarm/world_radar/bronze.py` (extended read-only)
- safety: `dharma_swarm/world_radar/safety.py` (new, this track)
- verifier: `dharma_swarm/world_radar/frontier_council.py` (new, this track)
- closure checks: `scripts/governance/check_world_quarantine.py`, `scripts/governance/check_frontier_council_replay.py`

## Commands run / results
- `python3 -m compileall -q dharma_swarm/world_radar scripts/governance` → OK
- `python3 -m pytest tests/test_world_radar_safety.py tests/test_frontier_council.py` → **13 passed**
- `python3 scripts/governance/check_world_quarantine.py` → **QUARANTINE_HOLDS=yes**
- `python3 scripts/governance/check_frontier_council_replay.py` → **FRONTIER_COUNCIL_REPLAY=pass** (4 cases)
- `ruff check dharma_swarm/world_radar/ scripts/governance/check_*` → clean

## Stage pass/fail
- Stage 0: **PASS** (poisoned signal ingested as inert data; instruction-like content flagged; quarantine contract holds).
- Stage 1: **PASS** (corroborated/refuted/insufficient/quarantined deterministic; ≥2 decorrelated families required;
  confident prose cannot upgrade; receipts serialize+replay; verifier is pure/mutates no owner).
- Stage 2: **DESIGN-ONLY** (read-only handoff seam documented).

## Risks discovered
- No second receipt store yet — `WorldSensemakingReceipt` lives as JSON; durable spine integration is a future seam.
- Fixture evaluators are deterministic stand-ins; live decorrelated model-family evaluation is designed but
  env-gated off (operator decision to enable).

## Next PR recommendation
Stage 2 (Shakti read-only handoff) + the receipt→spine integration seam. Do NOT enable DISPATCH_AUTHORITY or live
ingestion beyond fixtures without explicit operator approval.

## Operator decisions needed
1. Proceed to Stage 2 full Shakti read-only integration.
2. Permit live decorrelated model-family evaluation for the Frontier Council (currently env-gated off).
3. Permit live source ingestion beyond fixtures.
