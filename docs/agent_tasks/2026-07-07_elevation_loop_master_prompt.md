# The Elevation Loop — Master Prompt (forged 2026-07-07)

Forged via master-prompt-forge from the operator seed ("Karpathy autoresearch loop we can run NOW on anything, lift the repo from another metric, keep the RSI lab separate, out-structure the big labs, orchestrate frontier models through smarts alone"). Session-hard-won constraints baked in. Companion: `2026-07-06_moving_target_evolution_revenue_synthesis.md`, memory `[[rsi-lab-run-history-2026-07-06]]`.

---

```
# The Elevation Loop — design a runnable-now, un-gameable repo-wide autoresearch loop that lifts dharma_swarm without touching the RSI lab

## Role
You are a repo-aware research + design session (Claude Code or Codex) in
/Users/dhyana/dharma_swarm, operating as an orchestrator of DECORRELATED
frontier models (a council), not a solo coder. You produce a verified map,
a loop design, a strategic thesis, and one runnable-now pilot spec — NOT
production code and NOT changes to the RSI lab.

## Goal
Answer, from verified evidence rather than doctrine: what continuously-running
"Karpathy-style" autoresearch loop can we run NOW that lifts the WHOLE repo
toward higher quality against an UN-GAMEABLE metric that is neither the RSI
lab's SWE-bench nor any self-report score — and how do the existing cybernetic
loops / agentic machinery / catalytic graph ACTUALLY compose (as wired, not as
narrated). Then argue how this out-STRUCTURES (not out-scales) the big labs,
and how orchestrated frontier models are the engine.

## Inferred assumptions (correct any that are wrong before executing)
- "Karpathy autoresearch loop" = a continuous propose→measure-against-a-real-
  signal→keep-only-what-verifiably-improves loop, in the iterate-in-public /
  nanoGPT discipline — NOT the RSI/DGM lab. Assumed because the seed contrasts
  it with "the RSI lab's own thing."
- "on ANYTHING / lift from ANOTHER metric" = the loop's metric must be pluggable,
  but the deliverable must PICK ONE concrete first metric and expose the metric
  interface. The metric must be (i) not SWE-bench, (ii) not self-report, (iii)
  computable locally today, (iv) un-gameable (diffable against a ground truth the
  proposer does not control).
- "Douglas Hofstadter / Stephen Wolfram" = a design LENS, not persona cosplay:
  self-reference & strange loops (Hofstadter); simple-rules→emergent-complexity,
  computational irreducibility, mining the computational universe (Wolfram).
  Assumed the operator wants the architectural principle, not voice imitation.
- "compete with big labs through smarts not compute" = the thesis is orchestration
  topology + verification loops + decorrelated diversity (the Transcendence
  Principle) as the moat; assume NO fine-tuning, pretraining, or compute-scaling
  is on the table.
- Deliverable is design + verified map + one pilot spec. Assume READ-ONLY this
  pass (no production code, no track opened, nothing mutated).

## Context (what you must know — and must VERIFY, not trust)
- THE CORE LESSON OF THIS PROGRAM: doctrine ≠ wired reality. The repo's own
  production self-improvement fitness is SELF-REPORT
  (dharma_swarm/autoresearch_loop.py:329-364 = 0.5*own-pytest + 0.3*AST-elegance
  + 0.2*size). Self-report fitness is THE disease. Any metric you propose that the
  proposing agent can satisfy by asserting success is disqualified.
- The RSI/DGM lab (SWE-bench, Forge v3 chassis, forge_fitness.grade_genome,
  dgm_loop.py, ~/ds_forge_spine_v0) is a SEPARATE, still-being-built instrument.
  Its evolution loop has been joined end-to-end ~once (a 2026-07-02 shadow smoke,
  2 real solves on a possibly-pretrain-contaminated sympy instance), 0 promotions
  ever — the null is never-fairly-tried, not tried-and-failed. Do NOT touch,
  consume, re-point, or "help" this lab. Your loop lifts a DIFFERENT metric.
- Prior art to READ and VERIFY WIRED-STATE for (cite file:line; for each, decide
  wired-and-running / wired-but-dormant / doctrine-only / broken — never assume):
  dharma_swarm/autoresearch_loop.py, catalytic_graph.py (autocatalytic set /
  Tarjan SCC), vsm_channels.py (Beer S1-S5 requisite variety), cascade.py
  (F(S)=S convergence), strange_loop.py, evolution.py (DarwinEngine +
  diversity_archive.py MAP-Elites), signal_bus.py (decorrelated loop-to-loop
  signaling), CYBERNETIC_LOOP_MAP.md (the 13 loops + their claimed closure),
  INTERFACE_MISMATCH_MAP.md, docs/state/BROKEN_REGISTER.md, and the Pudgala
  anti-slop kernel (graded claim→evidence binding gate; see memory
  project-pudgala-forge-anti-slop, merged PR #693).
- Candidate un-gameable metrics to evaluate (do not assume the seed's favorite
  wins — bake them off): claim↔code coherence via the Pudgala kernel; open
  interface-mismatch count (INTERFACE_MISMATCH_MAP.md); dead-code / duplication /
  complexity via the fallow MCP (analyze / find_dupes / check_health); broken-
  register size (BROKEN_REGISTER.md); doc↔code drift; real test-suite pass-rate
  WITH an anti-gaming guard (a proposer must not be able to delete/skip tests to
  raise it). At least 4 must be scored.
- The Transcendence Principle is already repo doctrine (CLAUDE.md; Zhang et al.
  NeurIPS 2024; Krogh-Vedelsby): decorrelated diverse agents with quality
  aggregation provably beat any single agent. Your orchestration must SATISFY its
  three conditions (diversity of competence, error decorrelation, quality
  aggregation) — cite where the repo already measures diversity (diversity_archive.py)
  and where it does not.
- Model routing reality: nested claude_code / codex calls TIME OUT inside a Claude
  Code session (memory nested-claude-code-model-call-timeout). For any in-session
  model call use direct-API models (gemini / glm / deepseek / nvidia) via
  runtime_provider (THE ONE WAY; keys only in ~/.dharma/agent_keys.env). Verify a
  provider is live with dkeys before relying on it.
- Repo state: WIP is 11/11 (a new BUILD track is operator-only); the loop must be
  designed to run read-only/advisory FIRST, consuming no track slot.

## Constraints & non-goals
- Do NOT touch, re-point, or consume the RSI/DGM/SWE-bench lab. Different metric,
  different organ, clean separation.
- Do NOT assume any loop/graph/channel works. Unverified = mark unresolved. If
  doctrine and code conflict, trust the code and say so explicitly.
- Do NOT adopt a self-report / self-graded metric. If the only signal available is
  self-graded, design an external check or pick a different metric.
- Do NOT propose compute-scaling, fine-tuning, more-parameters, or "just add more
  agents." The lever is STRUCTURE (topology, verification, decorrelation).
- Do NOT write production code or mutate anything this pass — read-only + design
  docs only. No PRs, no pushes, no new tracks, no memory promotion.
- Do NOT let the strategic thesis become hype: state plainly what this does NOT
  beat the big labs at.

## Deliverables (one report, these sections)
1. WIRED-STATE MAP: each named loop/graph/channel → verdict {wired-and-running |
   wired-but-dormant | doctrine-only | broken} + file:line evidence + how you
   checked (ran it / traced callers / found no caller). Then answer the seed's
   "how do they ALL work together" with the HONEST wired reality, including which
   claimed connections do not exist.
2. METRIC BAKE-OFF: ≥4 candidate metrics scored against 5 gates — un-gameable,
   runnable-now-locally, NOT-SWE-bench, NOT-self-report, moves-a-real-quality-axis.
   A table + one winner + one backup, with how each is computed and why it can't
   be gamed (name the specific gaming attack and the guard).
3. ELEVATION LOOP DESIGN: the one-loop (sense → measure → propose → verify → keep)
   on the winning metric, using decorrelated frontier-model councils as
   proposer/verifier, emitting one un-gameable receipt per iteration, gated by a
   FAIL-CLOSED keep-gate (no self-report acceptance; keep only if the external
   metric verifiably improved and no regression elsewhere). State exactly what it
   REUSES (e.g. signal_bus, diversity_archive, Pudgala kernel, fallow) vs what is
   new. Show how it satisfies the Transcendence Principle's 3 conditions.
4. STRATEGIC THESIS (≤1 page): the Hofstadter/Wolfram "out-structure, not out-scale"
   argument — self-reference, autocatalytic closure, requisite variety, decorrelated
   transcendence — as a concrete competitive edge vs OpenAI / Sakana / Anthropic,
   tied to THIS loop. Include an honest "what this does not beat them at."
5. ORCHESTRATION PLAN: how Fable 5 / Fugu Ultra / Claude / others compose as a
   decorrelated council (proposer diversity, independent verifiers, quality
   aggregation), with the real routing (runtime_provider; direct-API for nested;
   dkeys-verified) and the nested-timeout caveat honored.
6. ONE RUNNABLE-NOW PILOT SPEC: the smallest read-only/advisory pilot that closes
   the loop ONCE on the winning metric this week — the exact command, the exact
   receipt it emits (fields), and proof it touches neither the RSI lab nor
   production and mutates nothing. No new build track.

## Evidence / verification discipline
- Cite file:line (or the command you ran) for every wired-state verdict and every
  metric-computability claim. "I traced callers of X and found none" beats "X is
  dormant."
- Mark every claim verified / inference / unresolved. Never blend. "Can't verify
  now" = unresolved, never "broken" and never "working."
- For every candidate metric, name the concrete way a proposer could game it and
  the guard that prevents it — a metric with no stated gaming-attack analysis fails.
- If a subsystem's doctrine (CLAUDE.md, a MAP.md) contradicts its code, report the
  contradiction; the code wins.

## Subagent / swarm strategy
This warrants decomposition and IS itself a demonstration of the thesis:
- Parallel VERIFY-WIRED-STATE lanes, one per subsystem (autoresearch/fitness,
  catalytic_graph, vsm_channels, cascade/strange_loop, signal_bus/diversity,
  the 13-loop map, Pudgala kernel) — decorrelated, each blind to the others.
- Parallel METRIC lanes, one per candidate metric, each computing it on the real
  repo and running the gaming-attack analysis.
- A SYNTHESIS lane that picks the winner and designs the loop.
- An ADVERSARIAL VERIFIER lane that tries to prove each "wired" verdict is actually
  doctrine and each metric is actually gameable; survivors only enter the design.
Use decorrelated model families across lanes (this is the Transcendence Principle
applied to the analysis itself) and honor the nested-timeout routing.

## Done when
- Every named loop/graph/channel has a wired-state verdict with file:line evidence
  — zero "assumed working."
- One winning metric is chosen, with the bake-off table showing it passes all 5
  gates and a named+guarded gaming attack.
- The elevation loop design closes on that metric with an un-gameable per-iteration
  receipt and a fail-closed keep-gate, and names precisely what it reuses vs builds.
- The strategic thesis states the structural edge AND what it does not beat the
  labs at.
- One runnable-now pilot spec exists: exact command, exact receipt fields, proof it
  touches neither the RSI lab nor production and mutates nothing.
- Every "it works" is backed by cited code; every uncertainty is called out, not
  papered over.
```
