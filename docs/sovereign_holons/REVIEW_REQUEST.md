# Independent Mission-Drift Review — Sovereign Holon

**You are an independent reviewer. Be brutally honest — the operator (Dhyana) suspects the mission has
drifted and the building agent (opus_composer/Claude) cannot see it. Do not flatter. Tell the operator
whether what's being built is what he actually needs.**

## The mission (operator's original intent)
Build a *sovereign holon* — a bleeding-edge agentic harness, researched for weeks. Each major dharma_swarm
agent should be simultaneously (a) a *being* you can sit and talk with on its own terms — own identity,
memory, voice, continuity — and (b) a governed *worker cell* in the larger organism. "Sovereign within the
banks." The flagship, opus_composer, should have **Opus 4.8 at the helm orchestrating cheaper models as
subagents within the holon's ecosystem** (model choice otherwise flexible — models don't matter much).
Reference: `~/dharma_swarm/docs/sovereign_holons/` (esp. `01_BUILD_GUIDE.md` 12-organ model, the 52-source
dossiers `00_/04_`) and `~/.dharma/proposals/sovereign_agent_holons.md`.

## What was actually built in one long session (the code)
~7 new modules in `dharma_swarm/`: `holon_bridge` (load agent + talk), `holon_runtime` (governed wake loop:
kill→budget→work→compass→persist), `holon_killswitch`, `holon_budget_guard`, `holon_compass` (non-binding
telos signal), `holon_health`, `holon_persistence`; a `/holon/{name}/chat` route; `scripts/holon_talk.py`
+ `holon_run.py`; ~74 passing tests. A live run worked — but on a *free* model (glm-5), not Opus, so it
was arguably a costume, not opus_composer.

## The process the operator is frustrated by (be skeptical of all of it)
The building agent oscillated badly — declared "done," then "10%," then "80%," then "100%"; spent hours
theorizing (frontier-surpassing, Constitutional AI) instead of building; hit self-inflicted "walls"
(treated an expired token / unfunded API as architectural impossibility); built units that passed in
isolation but didn't compose (wake loop ≠ persistence until a detonation caught it); swapped the agent's
actual model (Opus→glm-5) and declared victory.

## Review questions (answer each directly)
1. **Is this what the operator needs?** Or did "sovereign holon agentic harness" quietly become "a pile of
   governance/persistence plumbing modules in dharma_swarm"?
2. **The biggest possible drift:** the operator wants a holon that *orchestrates subagents* (Opus helm +
   model fleet). What got built is a *single-model wake loop*. Is that the wrong architecture? Should the
   holon be an orchestrator (à la Claude Code / a maestro pattern) rather than a single-model cron loop?
3. **Is the harness the bleeding-edge thing the research pointed at** (record→runtime bridge, verification
   loop, reliability `pass^k`, sleep-time compute, pilot→prod), or did it stall at the two easiest organs?
4. **Is there a simpler or truer path** to what the operator actually wants than continuing these modules?
5. **What is the single most important thing the building agent is NOT seeing?**

Read the artifacts, then give a blunt verdict: *on track / drifted / wrong thing entirely* — and the one
correction that matters most.
