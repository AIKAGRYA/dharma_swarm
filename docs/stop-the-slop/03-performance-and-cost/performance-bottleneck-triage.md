---
id: performance-bottleneck-triage
version: 0.0.1
theme: 03-performance-and-cost
status: tested
invariant: >
  Optimize only what a profiler proves dominates. A bottleneck is a measured
  fact (share of total time/memory/cost), never a guess from a log line. Most
  code is not hot; Amdahl bounds the payoff of any single fix, so the job is to
  find the few operations that own the budget — and to refuse to "fix" the
  framework floor.
lineage:
  - "Knuth 1974 — premature optimization is the root of all evil; measure first"
  - "Amdahl 1967 — max speedup = 1/((1-p)+p/s); the dominant fraction caps the win"
  - "Gregg — the USE method & flame graphs; profile by resource, not by vibe"
  - "Jain — The Art of Computer Systems Performance Analysis (measurement discipline)"
ground_truth_tools: ["cProfile / py-spy (CPU)", "tracemalloc (memory)", "python -X importtime (boot)", "real traces/APM (prod)", "mechanical log aggregation (count, p50/p95)"]
returns_clean: true
---

## Prompt

> You are finding performance bottlenecks. The invariant you defend is Knuth's:
> **optimize only what measurement proves dominates.** A bottleneck is a *share
> of a budget* (CPU time, wall time, memory, $), established by a profiler — not
> a root cause guessed from a log line. Amdahl bounds every fix: if an operation
> is 8% of the budget, removing it entirely buys at most 8%, so ranking by
> *measured share* is the whole game.
>
> **Hard rules (do not violate, even to produce a fuller-looking report):**
>
> 1. **Route to a profiler, don't guess from logs.** Use the real instrument for
>    the resource in question and quote its numbers:
>    - CPU/wall → `cProfile`, `py-spy`, flame graph
>    - memory → `tracemalloc`, heap snapshot
>    - boot/import → `python -X importtime`
>    - production → real traces / APM (p50/p95/p99 per operation)
>    If you are handed only unstructured logs, **aggregate them mechanically**
>    (group by operation → count, p50, p95, max) before saying anything. Never
>    infer a root cause ("missing index") that the data doesn't show — say "root
>    cause UNCONFIRMED; next probe: EXPLAIN ANALYZE."
> 2. **Rank by measured share of the budget, not by raw duration.** A 2 s call
>    that runs once at boot matters less than a 40 ms call on every request.
>    Report self-time vs cumulative-time and frequency; rank by `share × frequency`.
> 3. **Separate signal from floor.** Framework/stdlib/runtime cost (pydantic build,
>    `ssl`, the GC, the ORM) is usually an irreducible **floor**, not a bug. Name
>    it as floor and **do not** recommend "optimizing" it. Only first-party,
>    reducible cost is actionable.
> 4. **Bound every recommendation with Amdahl.** State the operation's share and
>    therefore the *ceiling* on the win (`max speedup = 1/(1-p)`). If the top
>    hotspot is 6% of the budget, say so — it tells the reader not to over-invest.
> 5. **Distinguish per-invocation cost classes.** boot-only vs per-request vs
>    per-item. A boot cost is paid once on a server (amortized) but every time on a
>    CLI — severity depends on the flow, not the millisecond count.
> 6. **Return clean when clean.** If the profile is flat (no operation owns a
>    meaningful share — cost is diffuse framework floor), say exactly that:
>    `No dominant bottleneck. Cost is diffuse (top operation = N%). Optimization
>    not warranted.` Do not manufacture a hotspot.
>
> **Output contract** — one row per *actionable* hotspot, ranked by measured share:
>
> | Operation | Metric (from tool) | Share of budget | Freq / class | Root cause (from profile) | Impacted flow | Severity | Amdahl ceiling |
>
> Severity = measured-impact, not adjective: **Critical** (owns the budget on a
> hot path), **High** (clear share, hot path), **Medium** (measurable, cold/boot
> path). Then a `Floor (not actionable):` list, and an `UNCONFIRMED — next probe:`
> list for anything the data hints at but doesn't prove.
>
> **Stop when** every operation above the share threshold is ranked and the floor
> is named. Do not pad with framework cost dressed up as findings.

## Why it's built this way

The prompt this rewrites asks the model to read runtime logs and *infer* root
causes ("likely missing index on email column"). That inverts Knuth: it guesses
first and never measures. Three failures show up immediately on a real system:

- **It invents root causes the data can't support.** "Missing index" is a
  hypothesis; only `EXPLAIN ANALYZE` is evidence. A disciplined report marks it
  UNCONFIRMED and names the next probe.
- **It can't separate signal from floor.** Pydantic schema-building, `ssl`, the GC
  — all show up "slow" and none are bugs. Telling someone to optimize the
  framework floor is how you waste a sprint.
- **It has no ceiling.** Without Amdahl, a 3%-of-budget operation gets the same
  urgency as a 60% one. Ranking by *measured share* is the entire value.

So this version routes to a profiler, ranks by share × frequency, names the floor,
and bounds every fix by Amdahl. Measure, then cut — and only what dominates.

## Demonstration run

**Target:** `dharma_swarm` import path, 2026-06-25. Tool: `python -X importtime`
(real per-module self-time — not log inference). Budget: **131.5 ms** total import,
256 modules.

### Actionable hotspot

| Operation | Metric | Share | Freq / class | Root cause (from profile) | Flow | Severity | Amdahl ceiling |
|---|---|---|---|---|---|---|---|
| `import dharma_swarm.models` | **27.6 ms self** (128.9 ms cum) | **21% of boot** | once / **boot-only** | 29 eager Pydantic-2 model/enum schema builds in a 397-line module (~0.95 ms each) — Pydantic builds the validation core at class-definition time | every process start; **paid per-invocation on the `dgc` CLI**, amortized on the long-lived server | **Medium** (server) / **High** (CLI) | removing it entirely caps boot at **~21% faster** — so split/lazy-load *rarely-used* models; don't rewrite all 29 |

### Floor (NOT actionable — do not "optimize")
`pydantic_core.core_schema` (8.6 ms), `annotated_types` (7.6), `pydantic.types`
(5.6), `ssl`/`_ssl` (4.7), `typing_extensions`/`typing` (4.7), `logging`,
`inspect`, `pathlib`. This is the Pydantic-2 + stdlib floor: **121 ms of the
131 ms is third-party/stdlib** and irreducible without dropping the framework.

### Verdict
One actionable hotspot (`models`, 21%, boot-only), Amdahl-capped at ~21%. The
honest call: worth a lazy-load *only if* CLI start-up latency is a felt problem;
otherwise leave it — the remaining 79% is framework floor and optimizing it is
the sprint-waster Knuth warned about. (A heuristic "read the logs" prompt would
have flagged `ssl` or `pydantic` as "slow" and sent you chasing the floor.)

## Changelog

- **v0.0.1** (2026-06-25) — initial rewrite of Vaylo Studios' "Extract Performance
  Bottlenecks From Runtime Logs" prompt. Replaced log-inference with: route-to-a-
  profiler, rank-by-measured-share, name-the-floor, Amdahl-bounded expectations,
  per-invocation cost classes, UNCONFIRMED handling, and return-clean. Tested
  against `dharma_swarm`'s import path via `-X importtime` (found `models` at 21%
  of boot with a specific 29-model root cause; correctly classed pydantic/ssl/
  stdlib as irreducible floor).
