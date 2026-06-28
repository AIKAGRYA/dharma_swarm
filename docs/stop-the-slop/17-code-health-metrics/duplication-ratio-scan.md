---
id: duplication-ratio-scan
version: 0.1.0
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

**Target:** `dharma_swarm/`, 2026-06-27. **Runner-generated** (not hand-transcribed)
— `python docs/stop-the-slop/probe/probe.py duplication dharma_swarm`. Instrument:
AST function-body hashing (docstring-stripped, signature-/decorator-independent) — a
real Type-1 clone detector; `jscpd` (the named tool for Type-2/3 near-miss clones)
was not installed, so confidence is MEDIUM, not HIGH.

```
| Duplication | 65 clone clusters; 102 cloned fns (1.0% of 10,431) | AMBER | MEDIUM | jscpd / pmd-cpd for Type-2/3 (renamed/near-miss) clones |
  11x  _build_messages  (providers.py:331 == providers.py:1275)
   9x  complete         (providers.py:1283 == providers.py:1357)
   9x  stream           (providers.py:1308 == providers.py:1382)
   5x  _jsonl_rows      (operator_core/living_agent_kernel_workers.py:395 == .../living_agent_kernel_activation.py:595)
   4x  _identifier      (board/adapters/semantic_receipt_adapter.py:30 == board/adapters/agentops_adapter.py:37)
   3x  _string_list     (zeitgeist.py:318 == world_radar/bronze.py:626)
```

- **The standout DRY target:** `_build_messages` **×11** and `complete`/`stream`
  **×9** in `providers.py` — every provider class re-implements the same
  message-builder / completion / streaming bodies. Lift to a shared base/mixin. The
  same `providers.py` clone surfaced independently in the `duplication` and
  `cycles`/`god_objects` runs, which is why it's the repo's clearest single fix.
- **Confirm + nuance:** the Type-1 body hash sees *identical* bodies only; route to
  `jscpd`/`pmd-cpd` for the Type-2/3 (renamed-variable, near-miss) clones it
  structurally cannot see. Before extracting `complete`/`stream`, check `git blame`
  that the copies haven't already diverged per-provider — if they have, they now have
  *different reasons to change*, and premature DRY would wrongly couple them.

## Changelog

- **v0.1.0** (2026-06-27) — demo is now **runner-generated** (`probe.py duplication`)
  via AST function-body hashing wired into the runner, with self-tests pinning both
  return-clean (unique bodies → GREEN) and detection (a planted identical body →
  flagged). Reproduces the earlier hand-run's standout findings
  (`_build_messages ×11` at `providers.py:331==1275`, `complete ×9`, `_jsonl_rows ×5`)
  and surfaces new clusters (`stream ×9`, `_identifier ×4`). Counts differ from v0.0.1
  (65 clusters / 102 cloned fns vs 32 / 86) because the runner uses a fixed,
  reproducible filter (docstring-stripped body, ≥3 statements, ≥160-char dump) instead
  of the ad-hoc first-pass script. Confidence set to MEDIUM (Type-1 only; jscpd is the
  Type-2/3 confirm).
- **v0.0.1** (2026-06-25) — duplication scan (Fowler/CCFinder): structural not text,
  extract-only-on-shared-reason-to-change, return-clean. Tested on `dharma_swarm`: 32
  clone clusters; `providers._build_messages` ×11 the standout DRY target.
