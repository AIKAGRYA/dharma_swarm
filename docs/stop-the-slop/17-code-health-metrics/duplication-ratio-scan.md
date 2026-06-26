---
id: duplication-ratio-scan
version: 0.0.1
theme: 17-code-health-metrics
status: tested
invariant: >
  Duplication is the highest-frequency code smell (Fowler) and a top AI-slop signal:
  a bug fixed in one copy survives in the others, and intent fractures across clones.
  Detect STRUCTURAL duplicates (same logic, renamed vars) — not just identical text —
  and extract only when the copies truly share one reason to change. Not all
  duplication is bad: coincidental similarity that will diverge should be left alone.
lineage:
  - "Fowler (Refactoring) — duplication is the #1 smell; DRY"
  - "Baker/Kamiya (CCFinder, clone detection) — structural (Type-2/3) clones, not text"
  - "arXiv 2508.14727 — duplication a core AI-generated smell"
ground_truth_tools: ["jscpd / pmd-cpd / pylint R0801 / CCFinder", "AST-normalized body hashing", "git blame (did they diverge?)"]
returns_clean: true
---

## Prompt

> Find **duplication**. The invariant (Fowler): a bug fixed in one clone lives on in
> the others. Detect **structural** clones (same logic, renamed locals — Type-2/3),
> not just identical text — **route to a clone detector** (`jscpd`, `pmd-cpd`,
> pylint `R0801`) or AST-normalized hashing.
>
> **Output:** clone clusters (`file:line` of each copy), the shared logic, and the
> extraction (shared helper / base method / util). **Discipline:** only recommend
> extraction where the copies share **one reason to change** — coincidental
> similarity that will diverge should be left duplicated (premature DRY couples
> unrelated code). Rank by cluster size × how-load-bearing. **Return clean** if the
> ratio is low.

## Why it's built this way

Text-diff duplication misses the renamed-variable clone (the common case); structural
detection is the real instrument (CCFinder lineage). And the discipline cuts the
other way too — Fowler's DRY is about *knowledge*, not *text*, so the prompt must
resist extracting accidental twins, which is how over-abstraction starts.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Tool: AST-normalized body hashing (no
`jscpd` installed).

- **5,446 functions; 32 exact-duplicate-body clusters; 86 functions are clones.**
  Worst:
  - `_build_messages` **×11** in `providers.py` (`:331` == `:1275` == …) — each
    provider class re-implements the same message-builder. **Real DRY target:** lift
    to a shared base/mixin.
  - `complete` **×9** in `providers.py` — same story.
  - `_jsonl_rows` **×5** / `_append_hashed` **×3** across
    `operator_core/living_agent_kernel_*` — copy-pasted JSONL helpers → one util.
- **Confirm + nuance:** route to `jscpd` for Type-3 (near-miss) clones the exact-hash
  proxy misses; before extracting `complete`, check `git blame` that the copies
  haven't already diverged per-provider (if they have, they have different reasons to
  change — leave them).

## Changelog

- **v0.0.1** (2026-06-25) — duplication scan (Fowler/CCFinder): structural not text,
  extract-only-on-shared-reason-to-change, return-clean. Tested on `dharma_swarm`: 32
  clone clusters; `providers._build_messages` ×11 the standout DRY target.
