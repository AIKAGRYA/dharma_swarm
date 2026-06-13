# Loop 1 Closure Receipt — Phase 1b

**Track:** `loop-closure-2026-06` (Cybernetic Loop Closure)
**Phase:** 1b — Loop 1 closure under spine dispatch (`DHARMA_SPINE_DISPATCH=1`), real provider/model receipts, persistence, and a closure check in `make orient`.
**Lane:** `/Users/dhyana/ds_loop_closure` (branch `loop-closure/phase1b-2026-06`)
**Author:** opus_composer (Opus 4.8) — build lease 2026-06-13; independent verification by codex_composer per OPUS_CODEX_LOOP_CLOSURE_COMPACT_2026-06-13
**Date:** 2026-06-13

---

## VERDICT: CLOSED (E2E in-lane)

Loop 1 (provider chain + dispatch) is **closed end-to-end on the canonical
surface the operator actually orients on.** A bounded, zero-cost real dispatch
ran through the patched spine path against the canonical
`~/.dharma/state/runtime.db`, its `delegation_runs.receipt_json` now carries a
non-empty `provider` AND `model`, and the operator's own `make orient` (no args)
reads that canonical receipt and prints **LIVE**.

The adversarial panel was unanimous in the other direction this round:
**4 of 4 lenses did NOT refute closure.** No lens found a hole that falsifies
the closure claim. The single unrefuted observation across all four is a
labeling-provenance nit (below), not a refutation.

---

## Closure evidence (verified firsthand this session)

### 1. `make orient` (canonical, no args) reports LIVE

Running the closure check exactly as the operator would — no db override, so
`build_loop1_closure()` resolves to `~/.dharma/state/runtime.db` via
`runtime_state.DEFAULT_RUNTIME_DB`:

```
LOOP 1 CLOSURE — owner: delegation_runs.receipt_json (read-only)
  Loop 1 (provider chain + dispatch): LIVE
    latest receipt: provider='ollama' model='mistral:latest'
    latest dispatch receipt carries provider+model
```

This is the canonical surface, not the lane sandbox. The fresh
`provider='ollama' model='mistral:latest'` receipt is the latest row in the
canonical store, and the closure check is satisfied there.

### 2. The dispatch-path patch is real and correct

`dharma_swarm/orchestrator.py` `_run_task_via_spine` previously hardcoded the
EvidenceReceipt as `provider="orchestrator"` with no `model`. The patch sources
both from the runner's static config (`AgentRunner._config`):

```python
_cfg = getattr(runner, "_config", None)
_prov = getattr(_cfg, "provider", None)
provider = getattr(_prov, "value", _prov) if _prov is not None else "orchestrator"
provider = str(provider) if provider else "orchestrator"
model = str(getattr(_cfg, "model", "") or "")
...
-   provider="orchestrator",
+   provider=provider,
+   model=model,
```

It is tolerant of a missing/partial config (falls back to the empty-string
defaults) and fabricates nothing — token usage stays `None` when the runner
does not expose it.

### 3. The test is green

`tests/test_loop1_spine_provider_model.py` — **green=true** (`2 passed in 0.18s`,
verified this session):

- `test_spine_receipt_carries_real_provider_and_model_and_persists` — drives a
  no-network `_FakeRunner(provider=OPENROUTER, model="z-ai/glm-4.6")` through
  `Orchestrator._run_task_via_spine`, asserts the in-flight `EvidenceReceipt`
  carries the real provider/model (non-empty), then **re-reads
  `delegation_runs.receipt_json` from the db** and asserts the persisted blob
  carries `provider="openrouter"`, `model="z-ai/glm-4.6"`. Persistence proven by
  round-trip, not by the in-memory object.
- `test_orient_marks_loop1_live_only_with_provider_and_model` — exercises
  `orientation_graph.build_loop1_closure(db_path=...)` against a temp db: no
  receipt → NOT live; receipt with empty provider/model → NOT live; latest
  receipt with both → LIVE. The closure check's logic is correct and now
  satisfied on the canonical db.

### 4. The live, zero-cost dispatch ran against the canonical store

`prove_loop1_spine_ollama.py` drove ONE real Loop-1 dispatch through the
blessed spine path (`Orchestrator._run_task_via_spine`, `DHARMA_SPINE_DISPATCH=1`)
using a real local `OllamaProvider` bound to `mistral:latest` (localhost, no
cloud token, **$0**). It was an independently-confirmed live `mistral:latest`
backend at `localhost:11434`: `status=ok`, ~52.2s real latency, a 1788-char
result. The canonical `delegation_runs.receipt_json` latest row now reads
`provider='ollama' model='mistral:latest'` — a real provider, a real model, a
completed status, persisted to and read back from the canonical store that
`make orient` consults.

---

## Adversarial tally — 4/4 lenses did NOT refute

`receipt-reality`, `persistence`, `live-not-replay`, `closure-check-honesty`:
**none refuted.** The closure claim survived all four.

The one standing observation, raised by three of the four lenses and not a
refutation: the receipt's `provider`/`model` strings are copied from the static
`AgentConfig` (`runner._config`, `orchestrator.py:2222-2226` — hardcoded
`mistral:latest`/`OLLAMA` in `prove_loop1_spine_ollama.py` lines 43-51), **not
parsed back out of the ollama HTTP response body.** So the receipt strictly
proves "dispatched to ollama/mistral and `run_task` returned without raising,"
rather than "ollama's response metadata named this model." The lenses judged
this a labeling-provenance nit, not a hole: `status=ok`, ~52.2s real latency, a
1788-char result, and an independently-confirmed live `mistral:latest` at
`localhost:11434` make a fabricated or dead-backend receipt implausible — the
labels are accurate, just config-asserted rather than network-echoed.

---

## The ONE standing caveat (plainly)

This is Loop 1 closed via a **bounded real dispatch through the patched code on
the canonical surface** — the patched orchestrator path ran once against
`~/.dharma/state/runtime.db`, and `make orient` reads LIVE there. **The STANDING
daemon is still running pre-merge code** and does not yet emit real
provider/model receipts on its own dispatches; it adopts this closure only
**after PR #590 merges and the daemon is restarted** on the patched code. Until
that merge + restart, the daemon's own future dispatches will continue writing
the old hardcoded receipts; the closure proven here is on the canonical surface
via the patched code in this lane, not yet in the long-running process.

---

## What this PR delivers

- `dharma_swarm/orchestrator.py`: spine receipt now carries real provider/model from `AgentRunner._config`; surfaces token usage only when present (no fabrication).
- `scripts/governance/orientation_graph.py`: read-only `build_loop1_closure()` + Loop-1 section in the orientation render (LIVE only when latest receipt has non-empty provider AND model).
- `tests/test_loop1_spine_provider_model.py`: 2 tests, green — persistence proven by db round-trip; orient closure gated on provider+model.
- `tests/test_orientation_graph.py`: 1-line adjustment for the new section.
- `prove_loop1_spine_ollama.py`: zero-cost local-ollama live proof that wrote the canonical closing receipt ($0, ~52.2s, status=ok).

**Coherence Delta:** Net-positive on substrate-nativeness. It (a) removes the
hardcoded `provider="orchestrator", model=""` from the spine dispatch receipt
and sources both from the runner's real config, (b) adds a Loop-1 closure check
to `orientation_graph.py` (read-only projection over
`delegation_runs.receipt_json`, no new truth store — honors the track's
non-goals), and (c) adds a green test proving the in-flight receipt AND the
persisted round-trip carry the real provider/model. It changes `orchestrator.py`
by ~24 lines, confined to the receipt-construction block; it does not decompose
`run_task` or alter the `EvidenceReceipt` schema beyond populating
already-existing fields.

**Do NOT push / do NOT open a PR from this lane — operator reviews first.**
