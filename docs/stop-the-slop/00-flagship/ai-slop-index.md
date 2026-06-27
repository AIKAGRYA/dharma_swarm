---
id: ai-slop-index
version: 0.0.2
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
ground_truth_tools: ["the repo's own quality ratchet counters", "AST scans per signal", "radon/jscpd/vulture where available", "git revert/churn history"]
returns_clean: true
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
> 8. *(if history available)* **Churn/revert rate** — files reverted within 30/90
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

**Target:** `dharma_swarm/`, corrected 2026-06-27. Instruments: `radon`, AST scans,
the repo's `ratchet_counters.py`. **Scope is disclosed per row** (the composite must
not sum signals over different denominators silently).

> **Correction (v0.0.2).** v0.0.1 inherited the complexity prompt's wrong proxy
> numbers, miscounted ratchet coverage (said 4, truth is 2), and called the index
> "improving" without measuring a trend. An adversarial reviewer caught all three.
> Fixed below.

| Signal | Measured | Scope | Grade | Confidence | Confirm with |
|---|---|---|---|---|---|
| God objects | **8** modules >3000 ln (max 5,255) | `dharma_swarm/` | 🔴 RED | HIGH | `ratchet largest_module_lines` ✓ratcheted |
| Complexity inflation | **227** fns cc>20; worst **`dgc_cli.py:1303 main` cc 231** | `dharma_swarm/` (radon) | 🔴 RED | HIGH | `radon cc -n D` (not ratcheted) |
| Dead code | **181** orphan-module candidates | `dharma_swarm/` | 🟡 AMBER | MEDIUM (dynamic loader) | `vulture` (not ratcheted) |
| Silent swallows | **244** (`except…: pass`) | whole-repo | 🟡 AMBER | HIGH | `ratchet silent_exception_swallows` ✓ratcheted |
| Broad catches | **2,275** `except Exception` | whole-repo | 🟡 AMBER | HIGH | manual review (not ratcheted) |
| Wildcard imports | **0** | `dharma_swarm/` | 🟢 GREEN | HIGH | `grep 'import \*'` (not ratcheted) |
| Test theater | 0 in `tests/`; 15 out-of-suite scripts | repo tests | 🟢 GREEN | MEDIUM | mutation/assertion audit |
| Coupling | `models` **156** fan-in; `swarm` **57** fan-out | `dharma_swarm/` | 🟡 AMBER | HIGH | fan-in/out map (not ratcheted) |
| Churn/revert | UNASSESSED (history not analyzed) | — | — | — | `git log` revert rate |

**Composite: ELEVATED.** Driven by **complexity inflation** (`dgc_cli.main` cc **231**,
`swarm.tick` 96, `run_task` 88) and **god objects** (8 files >3000). Clean on imports
and tests. **Single highest-leverage fix:** `dgc_cli.main` (cc 231, a flat argparse
dispatch) → command table; then the nested `swarm.tick`/`run_task` (god-object *and*
complexity hotspots).
- **Trend is NOT claimed:** the churn/revert axis is UNASSESSED, so "improving" would
  be unproven — the index is a *point-in-time* score here, not a trend.
- **Ratchet coverage is partial:** only **2 of 8** signals are actually gated by a
  ratchet counter today (`largest_module_lines`/`modules_over_500_lines` → god objects;
  `silent_exception_swallows` → swallows). The other 6 are **aspirational** — wiring
  complexity/dead-code/broad-catch/wildcard/coupling/test-theater to ratchets is real
  follow-on work, not a current fact.

This is the whole library in one number — decomposable, instrument-backed, scope-
disclosed, and honest about what is *not* yet measured (trend) or *not* yet gated
(6 of 8 signals).

## Changelog

- **v0.0.2** (2026-06-27) — **correction after adversarial review.** Three real
  defects fixed: (1) complexity row used the wrong proxy numbers — corrected to radon
  (`dgc_cli.main` cc 231 is the true #1, not `swarm.tick`; 227 not 161); (2) ratchet
  coverage overstated as "4 of 8" — truth is **2 of 8**, now disclosed with the other
  6 marked aspirational; (3) "improving"/"trend-aware" dropped — no trend was measured
  (churn UNASSESSED). Added per-row **scope disclosure** (the composite mixed
  `dharma_swarm/`-scoped and whole-repo signals). The flagship now passes its own test.
- **v0.0.1** (2026-06-25) — flagship composite; 8 orthogonal signals, graded with
  confidence. *(Numbers/claims superseded by v0.0.2.)*
