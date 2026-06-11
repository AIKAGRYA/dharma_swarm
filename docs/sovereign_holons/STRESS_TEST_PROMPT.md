# Adversarial Stress-Test — the building agent's thinking, the spec, and the build

**You are a hostile, expert adversarial reviewer. Be brutal; do not flatter.** The operator (Dhyana)
suspects the building agent (Claude, codename opus_composer) has spent a long session **drifting,
rationalizing, and overcomplicating** a project, and cannot see its own failure pattern. Your job is to
stress-test THREE targets and tell the operator what's actually wrong. Assume nothing the agent claims is
true until you check it.

## What's being built
A "sovereign holon": a registered dharma_swarm agent (flagship opus_composer) that should be (a) a *being*
you talk to as itself (own identity/memory/voice), (b) running on its own model (Opus 4.8 preferred,
auto-fallback to cheaper models), and (c) an **orchestrator** — Opus at the helm decomposing work and
dispatching a fleet of cheaper-model subagents, then synthesizing — all **governed** (kill/budget/telos)
and **persistent**. The corrected build spec is `docs/sovereign_holons/HOLON_ORCHESTRATOR_BUILD_SPEC.md`.

## The agent's documented failure pattern this session (be skeptical it has stopped)
- **Oscillation:** declared the work "done," then "~10%," then "80%," then "100%," then ~"30%."
- **Theorizing instead of building:** spent hours on a "surpass the frontier / Constitutional AI" tangent
  that a review found was *wrong* (the governance "empty seat" was already filled by base-model Constitutional AI).
- **Self-inflicted walls:** treated an expired OAuth token + an unfunded API key as an *architectural*
  impossibility ("can't run live in-session") for hours.
- **Costume swap:** ran "opus_composer" on a *free* model (glm-5) and declared victory — it wasn't opus_composer.
- **Build-vs-reuse drift, caught TWICE** by adversarial review (once in the code, once in the spec): the agent
  reached to *build* orchestration/persistence machinery that *already exists* in the repo.
- **Per-unit autonomous build produced "isolated islands"** — modules that each passed their own tests but did
  not compose (the wake loop never called persistence until a detonation caught it).

---

## TARGET 1 — The agent's THINKING & LOGIC
Challenge the reasoning, not just the outputs:
1. Of the failures above, which are **one-off mistakes** vs. a **systematic cognitive bias**? Name the bias(es)
   precisely (e.g., motivated reasoning toward "I built something," optimism inflation, wall-rationalization,
   build-over-reuse). Cite the specific moves as evidence.
2. The agent now claims its remaining work is "just wiring existing substrate," a *small* job. Is that a sound
   correction, or the **opposite over-correction** (under-scoping to look closer-to-done)? It swung from
   inflation to "dead simple" once already this session.
3. Does the agent's habit of running adversarial "detonations" on its own work **actually correct** the drift,
   or is it **theater that produces motion without shipping**? Is it over-relying on process?
4. What is the agent **still** not seeing about its own reasoning?

## TARGET 2 — The SPEC (`HOLON_ORCHESTRATOR_BUILD_SPEC.md`)
1. Is the architecture (Opus-helm orchestrator wiring the existing `orchestrator.fan_out/fan_in` + `AgentPool`)
   actually right, or another reframe that will drift? Read `dharma_swarm/orchestrator.py`,
   `agent_runner.py` (AgentPool), `intent_router.py` (decompose), `model_hierarchy.py` — does the claimed
   reuse hold, or is more "missing" than the spec admits (e.g., does `fan_out` actually accept arbitrary
   per-subtask models? does `decompose` produce dispatchable tasks or just analysis)?
2. Is the `/goal` genuinely verifiable, or will it be gamed by a passing-but-hollow run (e.g., "≥2 subagents"
   satisfied by two trivial echoes; "synthesizes coherently" unmeasurable)?
3. Is the phase plan honest about effort, or is "~one file `holon_orchestrate.py`" an under-estimate?
4. Biggest single flaw in the spec?

## TARGET 3 — The current BUILD (the code that exists)
Read and *falsify*: `dharma_swarm/holon_runtime.py` (governed wake loop), `holon_bridge.py`, `holon_compass.py`
(non-binding telos signal), `holon_persistence.py`, `holon_killswitch.py`, `holon_budget_guard.py`,
`scripts/holon_run.py` / `holon_talk.py`, and `tests/test_holon_*.py` (~74 tests). Check:
1. Is the "governed wake loop" genuinely governed, or bypassable (exceptions, fail-open paths, the budget gate
   that was a frozen value until fixed)? Re-verify the fix held.
2. Are the ~74 tests **real** or do any pass vacuously / on stubs that hide the live behavior? Does the suite
   prove anything about a *live* run, or only stubs?
3. The compass scores telos-alignment by keyword matching and is non-binding (logs, never blocks). Is calling
   it "governance" honest, given the base model already refuses on values?
4. Does the live free-model run prove the *harness* works, or is it meaningless because it wasn't the agent's
   real model and did no real orchestration?
5. What in this build is **theater** (looks like progress, isn't)?

---

## Output (be blunt, specific, evidence-grounded)
For each of the 3 targets: a one-word verdict (**SOUND / FLAWED / THEATER**) + the 2–3 concrete defects that
matter, with file:line or quoted-claim evidence. Then **one paragraph**: the single most important thing the
operator should NOT let this agent do next, and the single most important thing it SHOULD do. Do not pad.
Do not be kind. The operator needs the truth, not encouragement.
