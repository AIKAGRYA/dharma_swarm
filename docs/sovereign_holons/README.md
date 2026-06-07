# Sovereign Agent Holons — the single home

**Created:** 2026-06-08 · **Status:** brainstorm → design (no implementation yet) · **Owner:** Dhyana + opus_composer

This directory is the one home for the **sovereign holon** initiative: making dharma_swarm's
registered persistent agents into *holons* — each one simultaneously

- a **sovereign agent** you can sit with and talk to on its own terms (its own identity, memory,
  voice, will, executable agency), and
- a **cell** in the dharma_swarm organism (a governed worker, plugged into shared telos,
  coordination, learning, and receipts).

The core decision, already made: **sovereign within the banks.** Autonomy and constraint are not
opposed. The agent is fully itself *and* the telos holds, in both modes. "A river's power comes
from its banks."

> Source proposal: `~/.dharma/proposals/sovereign_agent_holons.md` (2026-06-06).
> This repo home supersedes the loose proposal as the working location.

## What's in here

| File | What it is |
|---|---|
| `README.md` | This index. |
| `00_RESEARCH_DOSSIER.md` | The profound research dossier — frontier landscape (what world-class super-autonomous agents are in 2026), the verified internal-wiring reality of our own substrate, and the gap analysis. Includes both research passes. |
| `01_BUILD_GUIDE.md` | The guiding build doc — the organ model, the verified gaps, the **first brick** (the record→runtime bridge), the build sequence, and open design questions. |

## The verified current state (don't trust the optimistic version)

A dharma_swarm persistent agent is designed to have **five organs**, all of which exist as code:

1. **Evolving registry self** — `dharma_swarm/agent_registry.py` (`AgentRegistry`, identity.json +
   task_log.jsonl + fitness_history.jsonl + prompt_variants/ with generations). ✅ 46 selves on disk.
2. **Autonomous wake-loop body** — `dharma_swarm/persistent_agent.py` (`PersistentAgent`). ✅ real,
   but only ever constructed from hardcoded config in `orchestrate_live.py`, never from the registry.
3. **Reasoning brain** — `dharma_swarm/autonomous_agent.py` (`AutonomousAgent`, ReAct). ✅
4. **Registration manifest (banks + summon)** — `examples/agents/*.registration.json`
   (`dharma_external_agent_registration_manifest.v1`): declares `authority` / `autonomy_policy`
   (sovereign-within-banks, literally) + `summon_phrase` / `summon_contract`. ⚠️ only 2 agents
   (merge_master_mike, qwen_code).
5. **NATS mailbox** — `~/.dharma/a2a_bus/inboxes/<name>/`. ✅

**The decisive gap (verified 2026-06-08):** there is **no record→runtime bridge**. The chat endpoint
`api/routers/agents.py:404-496` runs the *operator's global model* with a *cosmetic persona string*;
it never loads the agent's own model/prompt/banks. `AgentRegistry.load_agent` returns a dict (a filing
cabinet), with no function anywhere that turns a registered record into a runnable `PersistentAgent`.
So "talk to a registered agent on its own terms" **does not exist yet** — and it is the single
highest-leverage thing on the entire 2026 frontier (see dossier). It is a real build, not glue.

**Two ironies the dossier documents honestly:**
- The agents with the most *soul* (the Inner Circle — KARYA/VIVEKA/DRISHTI/SMRITI) have the least
  *body*: they are `~/.claude/agents/*.md` personas with only a mailbox, not registered selves.
- We over-invested in *governance* (telos gates, 25-axiom kernel, DarwinEngine) — which (a) the
  frontier evidence says is *secondary* to harness quality and can even hurt reliability, and (b) per
  our own audits is largely **unwired** (DarwinEngine self-improvement: 0% lineage; telos gate:
  paraphrase-evadable, REVIEW→applied). Meanwhile the "commodity shell" we under-built **is** the
  differentiator.

## Relationship to existing substrate (this is an EXTENSION, not a parallel build)

This initiative wires together code that already exists. It must NOT create a new agent system, a new
registry, a new daemon, or a new memory store. It composes: `AgentRegistry` (self) + `PersistentAgent`
(body) + `AutonomousAgent` (brain) + the registration manifest (banks/summon) + `runtime_provider`
(the one canonical model door) + a small new **record→runtime bridge** + a human **talk** surface with
a **verification loop** baked in.

## Governance note (honest)

The repo's declared active track is "Runtime Truth Reconciliation," whose non-goals forbid new
daemons/stores. A `talk` surface is read-and-interact over existing owners (likely fine), but it is
**off the declared active track** — opening this lane is an explicit operator choice, recorded here.
