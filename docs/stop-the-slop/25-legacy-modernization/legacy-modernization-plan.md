---
id: legacy-modernization-plan
version: 0.0.1
theme: 25-legacy-modernization
status: tested
invariant: >
  You modernize legacy code by getting it under test FIRST (characterization tests that
  pin current behavior, bugs included), then changing it behind that safety net — never a
  big-bang rewrite. Find the seams (Feathers) where you can insert a test without changing
  behavior. Risk-order the work: highest-churn × highest-value first; leave dormant legacy
  alone. A rewrite without characterization tests is how you re-introduce every bug you
  forgot about.
lineage:
  - "Feathers — Working Effectively with Legacy Code: characterization tests + seams"
  - "branch by abstraction / strangler fig (Fowler) — replace incrementally, never big-bang"
  - "Lehman — the system must keep working throughout the change"
ground_truth_tools: ["identify legacy modules (size, churn, no tests, _legacy markers)", "find seams for characterization tests", "the strangler boundary"]
returns_clean: true
---

## Prompt

> Produce a **legacy-modernization plan** — not a rewrite. The invariant (Feathers): get
> it under **characterization tests** (pin *current* behavior, bugs and all) at a **seam**,
> then change behind the net; replace incrementally (strangler fig), never big-bang.
>
> **Do this:**
> 1. Identify the legacy targets (large, high-churn, untested, `_legacy`-marked) and
>    **risk-order** them (churn × value); leave dormant legacy alone.
> 2. For the top target, find the **seam** — where can you insert a characterization test
>    without changing behavior? (inject a dependency, extract an interface).
> 3. Sketch the **strangler boundary**: route new behavior to a new implementation while
>    the old one still serves, shrinking it over releases.
> 4. Output the plan + the *first* safe step (a characterization test), not a rewrite.
>
> **Return clean** for legacy that's stable, tested, and not on a change path — don't
> modernize what isn't hurting.

## Why it's built this way

The big-bang rewrite is the classic failure (re-introduces forgotten bugs, no safety net).
Feathers' method — characterization tests at a seam, then incremental change — is the
discipline, and risk-ordering keeps effort where churn/value is, not on dormant code.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Legacy targets (real):** `tui_legacy.py` (**1,795 lines**), `scripts/legacy/*`,
  `import_legacy_archive.py`. The `_legacy` naming is an explicit "old path" marker.
- **Risk-order:** `tui_legacy.py` is large but — is the TUI on a **change path**? If the
  active TUI is `dharma_swarm/tui/**` (the newer package) and `tui_legacy` is dormant,
  then **leave it** (don't modernize what isn't hurting) or delete-after-confirming-orphan
  (cross-refs dead-code-scan — but it's MEDIUM confidence under the dynamic loader, so
  characterize-then-decide). The `scripts/legacy/*.sh` are likely replaced — confirm via
  the strangler boundary (does anything still call them?).
- **First safe step:** before touching `tui_legacy`, write a characterization test of its
  one public entry (snapshot current output) — *then* it's safe to extract or delete.
  Output: risk-ordered list + "characterize `tui_legacy` entry first; verify the
  `scripts/legacy` strangler is complete; don't rewrite."

## Changelog

- **v0.0.1** (2026-06-25) — legacy-modernization plan (Feathers/strangler/Lehman):
  characterization-tests-at-a-seam, risk-order, incremental, leave-dormant-alone. Tested
  on `dharma_swarm`: `tui_legacy.py` (1,795 ln) + `scripts/legacy/*` risk-ordered;
  first step = characterize before touch, not rewrite.
