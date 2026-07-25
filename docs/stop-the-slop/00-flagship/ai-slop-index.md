---
id: ai-slop-index
version: 0.1.1
theme: 00-flagship
status: tested
flagship: true
invariant: >
  "AI slop" — code that works today and rots tomorrow — is MEASURABLE, not a vibe.
  The index is a composite of orthogonal, individually-grounded signals, each routed
  to a real instrument and graded with confidence; the score is honest per-axis
  (clean where clean) and never collapses to a single adjective. A slop score you
  cannot decompose into measured signals is itself slop.
lineage:
  - "Larridin — AI Slop Index (duplication, revert rate, complexity, architectural coherence, test-behavior coverage)"
  - "arXiv 2508.14727 — AI code introduces measurable smells (Wildcard #1; dead code 34–42%)"
  - "Lehman — software evolution/rot; + the per-signal canon (Tarjan, McCabe, Parnas…)"
ground_truth_tools: ["probe/ runner (radon, git, AST, PyPI)", "the repo's own quality ratchet counters", "radon/jscpd/vulture where available", "git revert/churn history"]
returns_clean: true
reproduce: "python docs/stop-the-slop/probe/probe.py index <pkg> --online"
---

## Prompt

> Compute an **AI-Slop Index** for this codebase. The invariant (Larridin, the
> arXiv evidence): slop is *measurable*. Score these orthogonal signals, **each
> routed to a real instrument**, each graded GREEN / AMBER / RED with a confidence,
> and compose them into one index — **never** a single vibe-grade. Return clean on
> any axis that's genuinely clean.
>
> **Signals (route each to ground truth):**
> 1. **God objects** — modules over a size budget (AST line count).
> 2. **Complexity inflation** — functions over a cyclomatic/cognitive threshold
>    (radon / AST branch count). AI loves the 200-line function.
> 3. **Dead / unreachable code** — orphan modules & unused exports (reachability;
>    cap confidence if the repo loads dynamically).
> 4. **Silent error swallows & broad catches** — `except: pass` / `catch {}` count.
> 5. **Wildcard / re-export sprawl** — `import *` (the #1 measured AI smell).
> 6. **Test theater** — tests with no/structural-only assertions (assert *behavior*,
>    not shape).
> 7. **Coupling hotspots** — fan-in/fan-out extremes (change blast radius).
> 8. **Import cycles** — load-time cyclic SCCs (AST + Tarjan; exclude
>    `TYPE_CHECKING`-only and function-local edges — they don't run at import).
> 9. **Duplication** — copy-paste convergence (structural AST clone clusters;
>    a top AI-slop signal and Fowler's #1 smell).
> 10. *(if history available)* **Churn/revert rate** — files reverted within 30/90
>    days = code that didn't survive contact.
>
> **Output:** a per-signal table (`signal → measured value → grade → confidence →
> the one instrument to confirm`), then a composite index with the **2–3 signals
> driving it** and the **single highest-leverage fix**. **Wire each signal to a
> ratchet** so the index can only improve. Do **not** invent a signal you didn't
> measure; mark unmeasured axes UNASSESSED.

## Why it's the flagship

Every other prompt in this library measures one axis; this one **composes them into
the number a buyer actually wants** — "how much slop is in here, and is it getting
better or worse?" It's defensible precisely because it decomposes: no hand-waving
"this feels sloppy," just N grounded signals and a trend. And it closes the loop —
each signal wires to a ratchet, turning a one-time score into a monotonic gate.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-27. **This table is emitted verbatim by the
runner** — not hand-written prose:

```
python docs/stop-the-slop/probe/probe.py index dharma_swarm --online
```

Every row's scope is `dharma_swarm/` (deps excluded) unless noted, so the composite
sums signals over **one** denominator — no per-package/whole-repo mixing.

| Signal | Measured | Grade | Confidence | Confirm with |
|---|---|---|---|---|
| God objects | **8** files ≥3000 ln (max **5,255** `thinkodynamic_director.py`) | 🔴 RED | HIGH | `wc -l` on the listed files |
| Complexity inflation | **227** fns cc>20; worst **cc=231** (`main` @ `dgc_cli.py:1303`) | 🔴 RED | HIGH | `radon cc -n D` |
| Import cycles | **1** load-time cyclic SCC; **11** total; largest load-time = 3 modules | 🔴 RED | HIGH | `grimp` / `import-linter` contract |
| Wildcard imports | **0** | 🟢 GREEN | HIGH | `grep -rn 'import \*'` |
| Silent swallows | **337** (`except…: pass`) | 🔴 RED | HIGH | `ratchet silent_exception_swallows` |
| Broad catches | **1,865** (`except Exception`/bare) | 🟡 AMBER | HIGH | review each for log + re-raise vs swallow |
| Coupling | max fan-in **188** (`models`); max fan-out **56** (`swarm`) | 🟡 AMBER | MEDIUM | `grimp` / `pydeps` import graph |
| Dead code | **36** items (`vulture` ≥80%) | 🟡 AMBER | MEDIUM | `vulture` + string-ref grep before delete |
| Duplication | **65** clone clusters; **102** cloned fns (1.0% of 10,431) | 🟡 AMBER | MEDIUM | `jscpd` / `pmd-cpd` for Type-2/3 (near-miss) clones |
| Churn/revert | **5/1063** commits are reverts (0.5%) in 90d | 🟢 GREEN | HIGH | `git log --grep=revert --since` |
| Phantom deps | **1** hallucinated/phantom of 24 unresolved (23 real-but-uninstalled) | 🔴 RED | MEDIUM | verify it exists AND predates the project on PyPI |
| Change coupling | **1** file-pair co-changes ≥8× at ≥60% conf | 🟡 AMBER | HIGH | `git log --name-only`; inspect for a hidden contract |
| Narrative comments | **~86** restate-the-code comments (0.9% of 9,718) | 🟡 AMBER | LOW | human read of the flagged lines |

**Composite: ELEVATED.** RED 5 / AMBER 6 / GREEN 2 / UNASSESSED 0.
**Drivers (HIGH/MEDIUM-confidence RED): God objects, Complexity inflation, Import
cycles, Silent swallows, Phantom deps.** LOW-confidence rows (Narrative comments)
and UNASSESSED rows never drive the headline; the composite is a vector, not a sum.
**Single highest-leverage fix:** decompose `thinkodynamic_director.py` (5,255 ln) —
the worst god-object; then `dgc_cli.main` (cc=231) and the load-time cycle.

**Three honesty notes the runner forces (and a hand-written demo got wrong):**
- **Complexity driver.** The real worst function is `dgc_cli.main` at **cc=231**
  (radon), not `swarm.tick` (cc=96). An earlier draft used a homemade AST
  branch-count and crowned the wrong function; routing to radon fixed it.
- **Phantom deps is a driver — and the confirm step dissolves it.** The runner
  lists `Phantom deps` as a 5th driver (RED, MEDIUM): MEDIUM-confidence RED *does*
  drive the headline (only LOW and UNASSESSED are barred). But the single candidate
  is `run_agent` @ `build_engine.py:100`, imported only inside
  `if HERMES_DIR.is_dir()` after `sys.path.insert(HERMES_DIR)` — a vendored external
  module (`external/hermes-agent/`, not checked out here), **not** a hallucinated
  PyPI package. True phantom count: **0**. That is the entire point of grading a RED
  as MEDIUM and shipping a `confirm with` step: a MEDIUM driver is a *lead*, not a
  verdict — you confirm before you act, and here it evaporates.
- **Dead code is now routed, not skipped.** The prior demo returned UNASSESSED
  ("vulture absent"); `vulture` is now installed, so the row is real (36 items, AMBER)
  — and half of `vulture`'s "100% confident" hits are `__aexit__` protocol params
  that must be kept, which is why the signal is MEDIUM, not HIGH.

**Trend lever:** **2** of these signals sit on the repo's quality ratchet today
(`largest_module_lines` → god objects, `silent_exception_swallows` → silent
swallows). The other axes are *ratchetable* but not yet gated — claiming otherwise
would be the exact overclaim this library exists to kill.

This is the whole library in one number — decomposable, instrument-backed, honest
about the clean axes, honest about what is *not* yet ratcheted, and reproducible by
re-running the one command above.

## Changelog

- **v0.1.1** (2026-06-27) — composite now spans **13** routed signals: added
  **Import cycles** (AST + Tarjan, load-time vs `TYPE_CHECKING`/lazy) and
  **Duplication** (structural AST clone clusters) as first-class rows, and **Dead
  code** now routes to the real `vulture` (was UNASSESSED). Fixed a
  doc/runner contradiction: MEDIUM-confidence RED *does* drive the headline (per the
  runner's own logic), so `Phantom deps` is correctly listed as a 5th driver — and
  the `confirm with` step is shown dissolving it to a true phantom count of 0. Also
  fixed the runner so the driver list is never silently truncated below the RED
  count. RED 4→5, AMBER 4→6, UNASSESSED 1→0.
- **v0.1.0** (2026-06-27) — regenerated entirely from the `probe/` runner (no
  hand-written numbers). Fixes three defects from independent review: complexity
  driver now radon-routed (`dgc_cli.main` cc=231, was the wrong function at a proxy
  cc~88); ratchet claim corrected to **2 of 8** (was 4); all rows scope-normalized
  to `dharma_swarm/` (was silently mixing per-package and whole-repo denominators).
  Adds three new dimensions to the composite: phantom/hallucinated deps, change
  (logical) coupling, narrative-comment density.
- **v0.0.1** (2026-06-25) — flagship composite. 8 orthogonal slop signals, each
  routed to a real instrument and graded with confidence; composite + driving
  signals + highest-leverage fix; ratchet-wired for trend.
