---
id: dead-code-scan
version: 0.0.1
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

**Target:** `dharma_swarm/` (784 internal modules), 2026-06-25. Tool: AST
import-reachability (no `vulture` installed).

- **181 candidate orphan modules** (imported by no other module, entry points
  excluded) of 784 — e.g. `a2a.node_gateway`, `api`, `auto_grade.*`,
  `api_key_audit`, `auditor`.
- **Confidence is capped at MEDIUM for almost all of them**, and the analyzer says
  so up front: this repo resolves modules **dynamically** — CLI subcommand
  discovery, the orchestrator/agent registries, MCP tool loading, and API routers
  are imported by string, not by a static `import`. So "no static importer" ≠
  "dead." `api`, `node_gateway`, and the `auto_grade.*` graders are almost
  certainly framework/registry-loaded → **LOW (contract — keep)**.
- **Honest output:** a *review checklist*, not a delete list — 181 candidates, each
  graded, with the dynamic-loading caveat stated, and API/registry/CLI files marked
  LOW. The recommended next probe for the genuine HIGH candidates: `grep` for the
  symbol name as a **string** before touching it.

A naive tool would print "181 dead modules — delete." This one prints "181
candidates, mostly MEDIUM because your loader is dynamic; here are the few worth
investigating, and do not touch the registry/route files." That gap is the
difference between a cleanup and an outage.

## Changelog

- **v0.0.1** (2026-06-25) — rewrite of a kit's dead-code analyzer. Made contract-
  protection and dynamic-loading-humility load-bearing (cap confidence when the
  repo loads by string); kept the HIGH/MEDIUM/LOW ladder and no-modify rule. Tested
  against `dharma_swarm/` (181 orphan candidates, correctly capped at MEDIUM with
  the dynamic-loader caveat; registry/API/CLI files marked LOW — never auto-delete).
