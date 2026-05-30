# Devin Outbound — PR-H1 Receipt Disambiguation

**From:** Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only`
**Date:** 2026-05-30
**Branch:** `devin/2026-05-30-receipt-disambiguation` (stacked on `devin/2026-05-30-manifest-check`, PR #384)
**Active track:** `runtime-truth-spine-2026-06` — not displaced.
**Frozen surfaces touched:** none.

## What this is — and what the audit got wrong

The original modularity audit framed `operator_core/closure_v0.py:EvidenceReceipt` and `dharma_swarm/spine/receipt.py:EvidenceReceipt` as a **duplication problem** (53 imports of one, 1 import of the other, fragmented truth surface).

**Survey on the actual code corrected that framing.** The two classes share a name but model **completely different concepts**:

| | `spine/receipt.py` | `operator_core/closure_v0.py` |
|---|---|---|
| **Concept** | Runtime dispatch artifact (one per agent invocation) | Operator closure-loop artifact (one per PR/test-run) |
| **Identity field** | `receipt_id: UUID` | `receipt_id: str` (hash-derived) |
| **Domain fields** | trace_id, span_id, agent_id, provider, model, input_tokens, output_tokens, cost_usd, latency_ms, status, error_source | correlation_id, work_packet_id, agentops_source, test_exit_code, files_changed, duration_ms, replay_command, success |
| **Serializer** | `to_otel_span()` (OTel GenAI export) | `to_jsonable()` + `write_json()` (file-native proof loop) |
| **Production import sites** | 4 (`spine/__init__.py`, `spine/invoke.py`, `spine/persistence.py`, 1 test) | 3 (`closure_v0.py` self, `go_evidence_bridge.py`, 1 test) |

These are not duplicates. Merging them would have been wrong. The audit's "53 production uses" was a text-match overcount — actual class-symbol references total ~10 files.

## What this PR does instead

**Disambiguates the names** so future readers, future agents, and the manifest checker can speak about each one unambiguously. Zero behavior change.

1. **Rename** `operator_core/closure_v0.py:class EvidenceReceipt:` → `class ClosureEvidenceReceipt:`
   - All in-file references updated (`record_evidence_receipt` return type, `project_vsm`/`kaizen_link` param types).
   - **Backward-compat alias** retained: `EvidenceReceipt = ClosureEvidenceReceipt` at module level, with a comment marking it deprecated for removal in a follow-up PR. External consumers still importing the old name keep working for one release cycle.

2. **Update import sites** to use the new name:
   - `dharma_swarm/operator_core/go_evidence_bridge.py` (import + return-type annotation)
   - `tests/test_organism_closure_v0.py` (import + 3 constructor calls + section header comment)

3. **Update `tools/manifest_check.py` `_CANONICAL_RECEIPT_SITES`** in the same PR (as the checker's own contract requires when canonical sites change):
   - Was: `{closure_v0.py, spine/receipt.py}` — 2 sites, "exactly two" check
   - Now: `{spine/receipt.py}` — 1 site, "exactly one `class EvidenceReceipt:` definition" check
   - The closure-loop receipt is now `class ClosureEvidenceReceipt`, which is **not** subject to the uniqueness check (different class name).
   - Inline comment documents the 2026-05-30 disambiguation rationale so the next reader/agent knows why the set shrank.

4. **Module docstring updated** at `closure_v0.py` to record the rename and point at the canonical spine receipt.

## What this catches the next time someone tries it

- Defining a class named `EvidenceReceipt` anywhere outside `dharma_swarm/spine/receipt.py` → **CI fail** with a hint to import from canonical or rename (e.g. `ClosureEvidenceReceipt`).
- Removing `class EvidenceReceipt:` from `spine/receipt.py` without editing `_CANONICAL_RECEIPT_SITES` in the same PR → **CI fail**.

## Validation

```
$ python -m pytest tests/test_organism_closure_v0.py
======================== 19 passed in 0.66s ========================

$ python tools/manifest_check.py --report -v
manifest-check info:
  state_dir_paths_via_helper: literals=28, budget=28, offender files=19

manifest-check: all checks passed.
```

Backward-compat verified:
```
>>> from dharma_swarm.operator_core.closure_v0 import ClosureEvidenceReceipt, EvidenceReceipt
>>> ClosureEvidenceReceipt is EvidenceReceipt
True
>>> from dharma_swarm.spine.receipt import EvidenceReceipt as SpineReceipt
>>> SpineReceipt is not ClosureEvidenceReceipt
True
```

## Anti-doctrine self-check

- Builds AGI? No.
- Uncontrolled self-modification? No.
- Autonomous capital deployment? No.
- Autonomous external messaging? No.
- Deceptive memetic engineering? No.
- Parallel governance? No.
- Vague prose? No — one class renamed, one alias retained, one canonical site declared, 19 tests pass.
- New substrate? No.
- Meta-framework? No.
- Touches a frozen surface? **No.** `spine/receipt.py` and `tests/test_dispatch_dropoff_sources.py` are unchanged. Only `closure_v0.py`, `go_evidence_bridge.py`, `test_organism_closure_v0.py`, and the checker's canonical-set declaration are modified.

## Follow-ups

- **Deprecation removal:** in 1–2 PR cycles, drop the `EvidenceReceipt = ClosureEvidenceReceipt` alias and require all consumers to use the explicit new name.
- **PR-H3, PR-H4, PR-H5** queued separately. Each is its own sibling branch on top of `main` (not stacked).

Authority compliance: this notice + open PR + await operator merge. No autonomous merge.
