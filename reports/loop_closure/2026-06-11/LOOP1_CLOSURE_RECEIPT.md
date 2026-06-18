# Loop 1 Closure Receipt — operator-surface closure on the canonical DB

**Role:** report (dated descriptive output, per `docs/AGENTS.md` doc types)
**Track:** `loop-closure-2026-06` (declared in `docs/governance/ACTIVE_TRACK.yaml`)
**Date:** 2026-06-11
**Author:** Devin session 863663ec (campaign: "wire all 13 loops together")
**Subordinate to:** `reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md` (#590,
opus_composer). That receipt proved the dispatch-path patch but recorded verdict
**NOT CLOSED**, because `make orient` reads the canonical
`~/.dharma/state/runtime.db` and its latest `delegation_runs` receipt was still
the stale `provider='orchestrator', model=''` row — the real receipt landed only
in a throwaway sandbox DB. This report records the run that **completes** that
open item: a real dispatch that writes a genuine `provider+model` receipt to the
canonical DB the operator actually orients on.
**Authority:** none. This report projects truth from a committed run report
(`reports/loop_closure/2026-06-11/loop1_closure_run.json`) and the live
canonical receipt; it does not become authority. `make orient` renders the
verdict directly from `delegation_runs.receipt_json` — this prose never overrides it.

---

## 1. Verdict

**Loop 1 (Swarm Task: sense → interpret → constrain → act → adapt) is closed on
the operator surface, zero provider keys.** The orient closure axis #590 added
(`scripts/governance/orientation_graph.py::build_loop1_closure`) now reads a real
receipt from the canonical DB and prints **LIVE**:

```
LOOP 1 CLOSURE — owner: delegation_runs.receipt_json (read-only)
  Loop 1 (provider chain + dispatch): LIVE
    latest receipt: provider='ollama' model='llama3.2'
    latest dispatch receipt carries provider+model
```

The repeatable harness run behind that receipt:

| Field | Value |
| --- | --- |
| Provider lane | `ollama` (local, CPU-only) |
| Model | `llama3.2` |
| Spine dispatch | `DHARMA_SPINE_DISPATCH=1` (one `EvidenceReceipt` per dispatch) |
| Boot | `DHARMA_READ_ONLY_BOOT=1` (no seed crews — only closure tasks dispatch) |
| State dir | `/home/ubuntu/.dharma` → writes `~/.dharma/state/runtime.db` (= `DEFAULT_RUNTIME_DB`, the DB orient reads) |
| Agents | 1 (serialized — avoids CPU-contention timeouts on this box) |
| Tasks requested | 5 |
| Tasks completed | 5 |
| Tasks failed | 0 |
| Dispatch dropoffs | 0 |
| Evidence receipts | 5 (all `ok`) |
| Ticks | 539 |

Harness closure criterion (`scripts/loop1_closure_run.py::main`):
`tasks_completed == tasks_requested` **and** `dispatch_dropoffs == 0` **and**
`evidence_receipts` non-empty → **`LOOP1_CLOSED=yes`**.

## 2. What actually ran

Five controlled tasks driven end-to-end through the real orchestrator —
route → dispatch → `invoke_agent` (spine) → `OllamaProvider` LLM call →
`EvidenceReceipt` → `persist_receipt` into `delegation_runs.receipt_json` →
task completion — not a mock:

1. `loop1-closure-0001` — "Summarize in two sentences why feedback loops need both sensing and acting."
2. `loop1-closure-0002` — "Name three failure modes of a distributed task queue and one mitigation each."
3. `loop1-closure-0003` — "Write a one-line docstring for a function that retries with exponential backoff."
4. `loop1-closure-0004` — "Explain the difference between a rate limit and a quota in one paragraph."
5. `loop1-closure-0005` — "List four properties a good evidence receipt should record."

Each task carried `metadata={"provider_allowlist": ["ollama"], "timeout_seconds": 300}`
so the run is pinned to the keyless local lane and each task gets a real per-task
budget. Booting with `DHARMA_READ_ONLY_BOOT=1` suppresses `startup_crew` seed
tasks, so the canonical DB's latest receipt is unambiguously a closure dispatch.

## 3. Trunk bugs fixed to get here

Loop 1 was `PARTIAL` because the dispatch path starved or crashed on real data.
Each was found by *running* the harness, reproduced, and fixed in production code.
After merging `origin/main`, the split is:

**Landed independently on main (deduped in the merge, not re-claimed here):**

- **SQLite write contention** — dispatch DB connections had no `busy_timeout`,
  so concurrent ticks raised "database is locked". Main carries the named
  `_BUSY_TIMEOUT_MS` PRAGMA; this branch's duplicate was dropped on merge.

**Still unique to this branch:**

- **Keyless `:cloud` / `-cloud` degrade** — Ollama Cloud frontier ids
  (`glm-5:cloud`, `qwen3-coder:480b-cloud`, …) 401 without an `OLLAMA_API_KEY`.
  `is_ollama_cloud_model()` now degrades them to the local default when no key is
  present (checks both `:cloud` and `-cloud` suffixes) instead of failing dispatch.
- **Ollama native tool-args 400** — Ollama's native `/api/chat` requires
  tool-call `arguments` as a JSON *object*; the swarm sent JSON *strings* (the
  OpenAI convention), yielding `400 "Value looks like object, but can't find
  closing '}' symbol"`. `OllamaProvider._native_messages()` now coerces string
  arguments to objects.
- **Priority starvation** — `HIGH` seed tasks could sit ahead of closure tasks;
  the harness creates closure tasks at `URGENT`.
- **Per-task timeout** — `--timeout-per-task` flows into task metadata
  (`timeout_seconds`) so a CPU-slow tool-loop task gets its full budget.

## 4. Honest notes

- **CPU contention is real on this box.** A parallel 2-agent run of the same 5
  tasks returned 4/5 (one task timed out under simultaneous llama3.2 inference;
  `dispatch_dropoffs=0` — the Loop-1 mechanism held, the model server just
  starved). The clean 5/5 above used **1 agent** so inference serializes. This is
  a hardware property of a keyless CPU box, not a Loop-1 defect.
- **The "everything collapses to openrouter" symptom is still visible.** With the
  default (non-read-only) boot, `startup_crew` seed tasks carry no
  `provider_allowlist`, so the intelligence router resolves them to `openrouter`,
  which has no key here → `All providers failed in chain ['openrouter']`. Pinned
  closure tasks are unaffected. Ensuring a keyless lane always survives in the
  chain when no provider key is configured is a candidate follow-up.
- **Scope of this proof.** Repeatable 5-task harness closure on this VM, on a
  small local model, demonstrating the *path* is sound end-to-end and the
  operator orient surface reads LIVE. The honest 100-task run and the
  multi-family diversity run still want a real provider key (or an Ollama Cloud
  key for the frontier models the doctrine prefers); those are downstream of this
  receipt, not blockers to it.

## 5. Reproduce

```
OLLAMA_LOCAL_MODEL=llama3.2 DHARMA_SPINE_DISPATCH=1 DHARMA_READ_ONLY_BOOT=1 \
  .venv/bin/python scripts/loop1_closure_run.py \
  --tasks 5 --agents 1 --timeout-per-task 300 \
  --state-dir /home/ubuntu/.dharma \
  --report reports/loop_closure/2026-06-11/loop1_closure_run.json
# tail: LOOP1_CLOSED=yes
make orient   # LOOP 1 CLOSURE axis reads delegation_runs → LIVE via ollama
```
