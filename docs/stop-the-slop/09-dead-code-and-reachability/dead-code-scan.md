---
id: dead-code-scan
version: 0.1.0
theme: 09-dead-code-and-reachability
status: tested
invariant: >
  Deletion requires PROOF of unreachability, not absence of a grep hit. Dynamic
  imports, string-based lookups, plugin registries, and framework conventions
  (route/page exports, default exports, entry points) defeat static reachability —
  so every finding carries a confidence grade and contracts are protected. A
  static analyzer that deletes on a guess breaks production; one that grades
  confidence and protects API surfaces is safe.
lineage:
  - "Aho–Sethi–Ullman (Dragon Book) — dead-code elimination as reachability over a graph"
  - "tree-shaking — unreachable exports pruned only when the graph is statically known"
  - "Knuth — measure before you cut; here, prove before you delete"
ground_truth_tools: ["AST import/reachability graph", "vulture / ts-prune / knip", "grep for dynamic & string-based references"]
returns_clean: true
---

## Prompt

> Act as a **reachability-based dead-code analyzer**. The invariant (Dragon Book):
> dead code is the *unreachable* set in the symbol/import graph — and deletion
> requires **proof** of unreachability, never just "no grep hit." Dynamic imports,
> `getattr`/string lookups, plugin registries, and framework conventions defeat
> static proof, so **every finding is graded by confidence and API/framework
> contracts are protected.**
>
> **Scan the files in context and find:**
> 1. Exported symbols (functions/classes/types/consts) with **zero** importers.
> 2. Modules imported by **no** other module (excluding entry points: `index`,
>    `main`, `app`, CLI, route/page files).
> 3. File-internal symbols defined but never referenced.
> 4. Stale commented-out blocks / dead branches / aged TODOs.
>
> **For each finding return:**
> - file:line · symbol · **confidence**:
>   - **HIGH** — verified no usages, no dynamic/string indirection in this repo
>   - **MEDIUM** — could be reached via dynamic import / string lookup / plugin scan
>   - **LOW** — public-API surface, framework convention, or registration target
> - suggested action: **delete | investigate | keep**
>
> **Hard rules:**
> - **Do not modify code.** Output a review checklist only.
> - **Flag every contract:** public API exports, plugin/registration hooks,
>   framework conventions (Next.js page/route exports, default exports used by
>   routers, pytest fixtures, entry points). These are **LOW** even with no static
>   importer — they are reached by the framework, not by an import.
> - **If the repo uses heavy dynamic loading, say so and cap confidence.** A repo
>   that resolves modules by string is not safely tree-shakeable; most findings
>   become MEDIUM. State that up front rather than over-promising deletions.
> - **Return clean:** if reachability is clean (no orphans beyond entry points),
>   say so. Don't pad the checklist.

## Why it's built this way

The kit's version has the right confidence ladder already; we make the *contract
protection* and *dynamic-loading humility* load-bearing, because that's where naive
dead-code tools cause outages — they delete a "unused" export that a router or a
string-based registry actually calls. Reachability is the Dragon Book's
dead-code-elimination over a graph; the catch is that a graph with dynamic edges
isn't fully known statically, so confidence must be graded, not asserted.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-27. **Runner-generated** (not hand-transcribed)
— `python docs/stop-the-slop/probe/probe.py dead_code dharma_swarm`. The `dead_code`
signal **routes to the real tool** (`vulture`, now installed) and refuses to proxy:
if `vulture` is absent it returns UNASSESSED rather than guessing.

```
| Dead code | 36 items (vulture ≥80%) | AMBER | MEDIUM | vulture + string-ref grep before delete |
  archaeology_ingestion.py:414: unused variable 'max_hits' (100% confidence)
  chetana/revival.py:451:        unused variable 'own_body'  (100% confidence)
  dynamic_correction.py:262:     unused variable 'current_mission' (100% confidence)
  file_lock.py:164: unused variable 'exc_type' (100% confidence)
  file_lock.py:165: unused variable 'exc_val'  (100% confidence)
  file_lock.py:166: unused variable 'exc_tb'   (100% confidence)
```

**The grade is MEDIUM for a reason this very output demonstrates.** vulture reports
"100% confidence" on all six, yet they split cleanly into two kinds:

- **`file_lock.py:164-166` (`exc_type`/`exc_val`/`exc_tb`) are NOT dead — they are
  the `__aexit__(self, exc_type, exc_val, exc_tb)` async-context-manager protocol
  parameters.** Python *requires* those positional names; deleting them breaks the
  `with` protocol. vulture's "100%" is a false positive — exactly why the signal
  caps at MEDIUM and the confirm step is `vulture + string-ref grep before delete`,
  never auto-delete.
- **`archaeology_ingestion.py:414 max_hits` is a genuine candidate** — an unused
  keyword parameter (`max_hits: int = 20`) that the function body never reads. Still
  *investigate*, not *delete*: a caller may pass it positionally, or it may be part
  of a kept signature contract.

**Complementary reachability pass (module-level, the prompt's other half).** A
separate AST import-reachability scan finds **~181 candidate orphan modules**
(imported by no other module, entry points excluded) — e.g. `a2a.node_gateway`,
`api`, `auto_grade.*`. Confidence is capped at MEDIUM for almost all of them and the
analyzer says so up front: this repo resolves modules **dynamically** (CLI
subcommand discovery, orchestrator/agent registries, MCP tool loading, API routers
imported by string). So "no static importer" ≠ "dead"; `api`, `node_gateway`, and
the `auto_grade.*` graders are framework/registry-loaded → **LOW (contract — keep)**.

A naive tool prints "36 unused names + 181 dead modules — delete." This one routes
to vulture, then shows that half its "100% confident" hits are a protocol contract,
caps module orphans at MEDIUM because the loader is dynamic, and emits a *review
checklist* with a `grep`-for-the-string-name confirm step. That gap is the
difference between a cleanup and an outage.

## Changelog

- **v0.1.0** (2026-06-27) — demo is now **runner-generated** (`probe.py dead_code`),
  routing to the real `vulture` (installed) and returning UNASSESSED when it is
  absent rather than proxying. Output makes the MEDIUM grade self-justifying: the
  `__aexit__` protocol params (`file_lock.py:164-166`) are vulture false positives
  (must keep) while `archaeology_ingestion.py:414 max_hits` is a genuine candidate —
  same "100% confidence", opposite correct action. Module-orphan reachability (~181
  candidates, dynamic-loader caveat) retained as the complementary pass.
- **v0.0.1** (2026-06-25) — rewrite of a kit's dead-code analyzer. Made contract-
  protection and dynamic-loading-humility load-bearing (cap confidence when the
  repo loads by string); kept the HIGH/MEDIUM/LOW ladder and no-modify rule. Tested
  against `dharma_swarm/` (181 orphan candidates, correctly capped at MEDIUM with
  the dynamic-loader caveat; registry/API/CLI files marked LOW — never auto-delete).
