# Loop 1 Closure Receipt — Phase 1b

**Track:** `loop-closure-2026-06` (Cybernetic Loop Closure)
**Phase:** 1b — Loop 1 closure under spine dispatch (`DHARMA_SPINE_DISPATCH=1`), real provider/model receipts, persistence, and a closure check in `make orient`.
**Lane:** `/Users/dhyana/ds_loop_closure` (branch `loop-closure/phase1b-2026-06`)
**Author:** opus_composer (Opus 4.8) — build lease 2026-06-13; independent verification by codex_composer per OPUS_CODEX_LOOP_CLOSURE_COMPACT_2026-06-13
**Date:** 2026-06-13

---

## VERDICT: NOT CLOSED

Loop 1 is **NOT closed through the spine on the surface the operator actually orients on.**

The dispatch-layer patch is real and the isolated proof is real, but the
operator-facing closure check (`make orient`) reads the **canonical**
`~/.dharma/state/runtime.db` — whose latest receipt is still the stale
`provider='orchestrator', model=''` row from 2026-06-12 — and prints
**"Loop 1 (provider chain + dispatch): NOT LIVE"**. The fresh real-provider
receipt was written ONLY to the lane-local sandbox DB that orient never consults.

I am recording this as a **partial**, not a pass. The adversarial panel was
unanimous: **0 of 4 lenses failed to refute closure** — every lens refuted it,
all on the same load-bearing hole.

---

## What IS proven (verified firsthand this session)

### 1. The dispatch-path patch is real and correct

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

### 2. The test is green

`tests/test_loop1_spine_provider_model.py` — **green=true** (`2 passed in 0.26s`,
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
  receipt with both → LIVE. The closure check's logic is correct **when pointed
  at the right db.**

### 3. The live, zero-cost proof ran (in the lane sandbox)

`prove_loop1_spine_ollama.py` drove ONE real Loop-1 dispatch through the
blessed spine path (`Orchestrator._run_task_via_spine`, `DHARMA_SPINE_DISPATCH=1`)
using a real local `OllamaProvider` bound to `mistral:latest` (localhost, no
cloud token, $0). The lane DB row confirms it:

```
LANE DB (_proof_state/runtime.db) latest receipt:
  task_id=078f7b95464d45d1  status=completed  started_at=2026-06-13T04:13:15Z
  provider=ollama  model=mistral:latest
```

A real provider, a real model, a completed status, persisted to
`delegation_runs.receipt_json` — in the **isolated** lane DB.

---

## Why it is NOT closed — the live receipt rows

The closure check the operator runs reads the canonical store, where nothing changed:

```
CANONICAL DB (~/.dharma/state/runtime.db) latest receipts:
  08a4acd48ea548f7  completed  2026-06-12T13:52:08Z  provider=orchestrator  model=''
  3ab8248ea464473d  completed  2026-06-12T13:52:02Z  provider=orchestrator  model=''
  e420592414304bcf  failed     2026-06-12T13:51:57Z  provider=orchestrator  model=''
  ...
  (4436 rows total; ALL carry the OLD hardcoded provider='orchestrator', model='')
```

Running `make orient` exactly as the operator would (no args, canonical db):

```
LOOP 1 CLOSURE — owner: delegation_runs.receipt_json (read-only)
  Loop 1 (provider chain + dispatch): NOT LIVE
    latest receipt: provider='orchestrator' model=''
    latest receipt missing provider and/or model
```

Root cause: `Makefile` `orient:` runs `python3 scripts/governance/orientation_graph.py`
with no db arg → `build_loop1_closure()` (db_path=None) → `_runtime_db_path()`
→ `dharma_swarm.runtime_state.DEFAULT_RUNTIME_DB` = `~/.dharma/state/runtime.db`.
The fresh ollama/mistral receipt is in `_proof_state/runtime.db`, which orient
never opens. The patched dispatch path has therefore **never run against the db
the operator actually orients on.**

---

## Adversarial tally — 0/4 lenses did NOT refute (all four refuted)

Every unrefuted hole, verbatim from the verdicts:

- **receipt-reality** (`refuted: true`): The "make orient reflects it" conjunct is
  false: `make orient` runs `orientation_graph.py` with no db arg, so
  `build_loop1_closure()` reads the CANONICAL ~/.dharma/state/runtime.db (whose
  latest receipt is provider='orchestrator', model='' from 2026-06-12) and prints
  "Loop 1: NOT LIVE" — the fresh ollama/mistral receipt was written ONLY to the
  isolated lane DB /Users/dhyana/ds_loop_closure/_proof_state/runtime.db that the
  operator-facing orient view never consults.

- **persistence** (`refuted: true`): The live proof wrote its real ollama/mistral
  receipt only to the lane-local sandbox DB
  (/Users/dhyana/ds_loop_closure/_proof_state/runtime.db), but `make orient` reads
  the canonical ~/.dharma/state/runtime.db (via DEFAULT_RUNTIME_DB, no db_path
  override in the Makefile), whose latest receipts are stale 2026-06-12 rows with
  provider="orchestrator" and empty model — so running orient exactly as the
  operator would reports Loop 1: NOT LIVE, directly falsifying the "make orient
  reflects it" clause.

- **live-not-replay** (`refuted: true`): The third clause "make orient reflects it"
  is false: the real `make orient` reads the canonical ~/.dharma/state/runtime.db
  (via runtime_state.DEFAULT_RUNTIME_DB) where all 464 receipts still carry the OLD
  hardcoded provider='orchestrator', model='' (latest 2026-06-12) and prints
  "Loop 1: NOT LIVE" — the fresh provider=ollama/model=mistral receipt was written
  ONLY to an isolated lane-local _proof_state/runtime.db that orient never consults,
  so the patched dispatch path has never run against the db the operator actually
  orients on.

- **closure-check-honesty** (`refuted: true`): The "make orient reflects it" clause
  is false: make orient reads the canonic[al ~/.dharma/state/runtime.db].

(Verdict text reproduced exactly as received; the `live-not-replay` lens's "464
receipts" is its own count — the live canonical row count this session is 4436;
the substance — all rows carry the old defaults, latest 2026-06-12 — is confirmed.)

---

## What remains to actually CLOSE Loop 1 through the spine

1. Run one real spine dispatch against the **canonical** `~/.dharma/state/runtime.db`
   (not the lane sandbox) so its latest `delegation_runs.receipt_json` carries a
   non-empty `provider` AND `model`. The patched orchestrator path must touch the
   canonical store at least once.
2. THEN `make orient` (no args) will read that fresh canonical receipt and print
   Loop 1: LIVE. Closure = the operator's own `make orient` saying LIVE, not a
   sandbox-scoped proof.
3. The Phase-1b ACTIVE_TRACK item ("closure check in make orient") is only half
   done: the check exists and is correct, but it has never been satisfied on the
   canonical surface.

Until step 1 lands on the canonical db, Loop 1 is **NOT closed**.

---

## PR draft

**Title:** loop-closure Phase 1b: close Loop 1 through spine (real provider receipts + persistence + orient check)

**Coherence Delta:** Net-positive on substrate-nativeness intent, but **does NOT
yet close Loop 1**. It (a) removes the hardcoded `provider="orchestrator", model=""`
from the spine dispatch receipt and sources both from the runner's real config,
(b) adds a Loop-1 closure check to `orientation_graph.py` (read-only projection
over `delegation_runs.receipt_json`, no new truth store — honors the track's
non-goals), and (c) adds a green test proving the in-flight receipt AND the
persisted round-trip carry the real provider/model. It changes `orchestrator.py`
(a hot-path god object owned by the spine-adoption track) by ~24 lines, confined
to the receipt-construction block; it does not decompose `run_task` or alter the
`EvidenceReceipt` schema beyond populating already-existing fields. The honest gap:
the live proof and the closure check operate on two different databases (lane
sandbox vs canonical), so `make orient` still reports NOT LIVE. This PR is a
correct, tested **building block** for closure — not the closure itself.

**Summary:**
- `dharma_swarm/orchestrator.py`: spine receipt now carries real provider/model from `AgentRunner._config`; surfaces token usage only when present (no fabrication).
- `scripts/governance/orientation_graph.py`: read-only `build_loop1_closure()` + Loop-1 section in the orientation render (LIVE only when latest receipt has non-empty provider AND model).
- `tests/test_loop1_spine_provider_model.py`: 2 tests, green — persistence proven by db round-trip; orient closure gated on provider+model.
- `tests/test_orientation_graph.py`: 1-line adjustment for the new section.
- `prove_loop1_spine_ollama.py` + `_proof_state/`: zero-cost local-ollama live proof (lane sandbox only).

**Do NOT push / do NOT open a PR — operator reviews first.**
