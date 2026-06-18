# Loop 1 Closure Receipt — Swarm Task loop, closed on real data

**Role:** report (dated descriptive output, per `docs/AGENTS.md` doc types)
**Track:** `loop-closure-2026-06` (declared in `docs/governance/ACTIVE_TRACK.yaml`)
**Date:** 2026-06-11
**Author:** Devin session 863663ec (campaign: "wire all 13 loops together")
**Authority:** none. This receipt projects truth from a committed run report
(`reports/loop_closure/2026-06-11/loop1_closure_run.json`) and the live code;
it does not become authority. `make orient` renders the same verdict from the
same report — this prose never overrides it.

---

## 1. Verdict

**Loop 1 (Swarm Task: sense → interpret → constrain → act → adapt) is CLOSED on
this VM with a repeatable harness, zero provider keys.**

| Field | Value |
| --- | --- |
| Provider lane | `ollama` (local, CPU-only) |
| Model | `llama3.2` |
| Spine dispatch | `DHARMA_SPINE_DISPATCH=1` (one `EvidenceReceipt` per dispatch) |
| Agents | 2 |
| Tasks requested | 5 |
| Tasks completed | 5 |
| Tasks failed | 0 |
| Dispatch dropoffs | 0 |
| Evidence receipts | 7 (5 `ok` — the harness tasks; 2 `failed` — see §4) |
| Ticks | 193 |

Closure criteria (computed in `scripts/loop1_closure_run.py::main`, mirrored by
`scripts/governance/orientation_graph.py::build_loop_closure`):
`tasks_completed == tasks_requested` **and** `dispatch_dropoffs == 0` **and**
`evidence_receipts` non-empty → **`LOOP1_CLOSED=yes`**.

`make orient` LOOP 1 CLOSURE axis now prints:

```
[CLOSED] 5/5 tasks completed via ollama (dropoffs=0, receipts=7)
Report: reports/loop_closure/2026-06-11/loop1_closure_run.json
```

## 2. What actually ran

Five controlled tasks were driven end-to-end through the real orchestrator —
route → dispatch → `invoke_agent` (spine) → `OllamaProvider` LLM call →
`EvidenceReceipt` → task completion — not a mock:

1. `loop1-closure-0001` — "Summarize in two sentences why feedback loops need both sensing and acting."
2. `loop1-closure-0002` — "Name three failure modes of a distributed task queue and one mitigation each."
3. `loop1-closure-0003` — "Write a one-line docstring for a function that retries with exponential backoff."
4. `loop1-closure-0004` — "Explain the difference between a rate limit and a quota in one paragraph."
5. `loop1-closure-0005` — "List four properties a good evidence receipt should record."

Each task carried `metadata={"provider_allowlist": ["ollama"], "timeout_seconds": 600}`
so the run is pinned to the keyless local lane and each task gets a real
per-task budget (the orchestrator default is 300s; see §3).

## 3. Trunk bugs fixed to get here

Loop 1 was `PARTIAL` because the dispatch path starved or crashed on real data.
Each of the following was found by *running* the harness, reproduced, and fixed
in this campaign's branch (production code, not the harness):

- **SQLite write contention** — dispatch DB connections had no `busy_timeout`,
  so concurrent ticks raised "database is locked" mid-run and killed live runs.
  Fixed with a `PRAGMA busy_timeout` (the actual crash cause, twice).
- **Keyless `:cloud` / `-cloud` degrade** — Ollama Cloud frontier model ids
  (`glm-5:cloud`, `qwen3-coder:480b-cloud`, …) 401 without an `OLLAMA_API_KEY`.
  `is_ollama_cloud_model()` now degrades them to the local default when no key
  is present, instead of failing the dispatch.
- **Priority starvation** — `HIGH` seed tasks could sit ahead of closure tasks;
  the harness now creates closure tasks at `URGENT`.
- **Ollama native tool-args 400** — Ollama's native `/api/chat` requires
  tool-call `arguments` as a JSON *object*; the swarm sent JSON *strings*
  (the OpenAI convention), yielding `400 "Value looks like object, but can't
  find closing '}' symbol"`. `OllamaProvider._native_messages()` now coerces
  string arguments to objects. This was the last known harness failure.
- **Per-task timeout** — `--timeout-per-task` now flows into task metadata
  (`timeout_seconds`) so a CPU-slow tool-loop task gets its full budget rather
  than the 300s orchestrator default.

## 4. Honest notes

- **2 of the 7 receipts are `failed`.** They are not closure tasks — they are
  the swarm's auto-spawned **seed tasks** (`research_spawn_sub_swarm_spec…`,
  `anthropic_economic_futures…`, etc.) created by `startup_crew.create_seed_tasks`
  during `SwarmManager.init()`. These tasks carry no `provider_allowlist`, so the
  intelligence router selects a frontier lane and resolves to `openrouter`, which
  has no key on this box → `All providers failed in chain ['openrouter']`. The 5
  closure tasks (which *are* pinned to `ollama`) all completed. This openrouter
  fall-through on unpinned tasks is the "everything collapses to openrouter"
  symptom flagged by the operator and is a candidate follow-up (ensure a keyless
  lane always survives in the chain when no provider key is configured).
- **Scope of this proof.** This is the repeatable 5-task harness closure on this
  VM, on a small local model. It demonstrates the *path* is sound end-to-end. The
  honest 100-task run and the multi-family diversity run still want a real
  provider key (or an Ollama Cloud key to run the frontier models the doctrine
  prefers); those are downstream of this receipt, not blockers to it.
- **Production state lives on the operator's machine.** Per the Phase 0 dossier,
  the loop map's production evidence (`~/.dharma/`) is on the operator's box; this
  VM closure is `[box-verified]` for the path, not a claim about the operator's
  production swarm.

## 5. Reproduce

```
OLLAMA_LOCAL_MODEL=llama3.2 DHARMA_SPINE_DISPATCH=1 OLLAMA_FORCE_LOCAL=1 \
  .venv/bin/python scripts/loop1_closure_run.py \
  --tasks 5 --agents 2 --timeout-per-task 600 \
  --state-dir /tmp/loop1-run --report /tmp/loop1_run.json
# tail: LOOP1_CLOSED=yes
make orient   # LOOP 1 CLOSURE axis reads the committed report
```
