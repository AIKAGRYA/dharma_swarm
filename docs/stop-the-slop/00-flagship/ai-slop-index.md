---
id: ai-slop-index
version: 0.0.1
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

**Target:** `dharma_swarm/`, 2026-06-25. Instruments: AST scans + the repo's own
`ratchet_counters.py`.

| Signal | Measured | Grade | Confidence | Confirm with |
|---|---|---|---|---|
| God objects | **8** modules >3000 ln (max 5,255) | 🔴 RED | HIGH | `ratchet largest_module_lines` |
| Complexity inflation | **161** fns cc>20; worst **cc~88** (`swarm.py:2093 tick`) | 🔴 RED | HIGH | `radon cc -n D` |
| Dead code | **181** orphan-module candidates | 🟡 AMBER | MEDIUM (dynamic loader) | `vulture` + string-ref grep |
| Silent swallows | **244** (`except…: pass`, witness-less) | 🟡 AMBER↓ | HIGH | `ratchet silent_exception_swallows` |
| Broad catches | **2,275** `except Exception` | 🟡 AMBER | HIGH | review for log+re-raise |
| Wildcard imports | **0** | 🟢 GREEN | HIGH | `grep 'import \*'` |
| Test theater | 0 in `tests/`; 15 out-of-suite scripts | 🟢 GREEN | MEDIUM | assertion audit |
| Coupling | `models` **156** fan-in; `swarm` **57** fan-out | 🟡 AMBER | HIGH | fan-in/out map |
| Churn/revert | UNASSESSED (history not analyzed here) | — | — | `git log` revert rate |

**Composite: ELEVATED but improving.** Driven by **complexity inflation**
(`swarm.tick` cc~88) and **god objects** (8 files >3000) — not by imports or test
theater, which are clean. **Single highest-leverage fix:** decompose the two
worst-complexity functions (`swarm.tick`, `agent_runner.run_task`) — they're both
god-object *and* complexity hotspots, so one refactor moves two RED signals.
**Trend lever:** 4 of these 8 signals already sit on the repo's quality ratchet
(now CI-gated, per PR #713), so the index is wired to ratchet **down**, not just be
scored once.

This is the whole library in one number — decomposable, instrument-backed, honest
about the clean axes, and trend-aware.

## Changelog

- **v0.0.1** (2026-06-25) — flagship composite. 8 orthogonal slop signals, each
  routed to a real instrument and graded with confidence; composite + driving
  signals + highest-leverage fix; ratchet-wired for trend. Tested on `dharma_swarm`:
  ELEVATED-but-improving, driven by complexity (`swarm.tick` cc~88) and god objects;
  clean on wildcards/tests; churn axis honestly marked UNASSESSED.
