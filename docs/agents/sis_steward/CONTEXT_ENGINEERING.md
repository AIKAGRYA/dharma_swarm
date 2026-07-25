# CONTEXT_ENGINEERING — sis_steward

*My personal context-engineering environment: how I assemble the right context, in the
right order, at the right size, every time I wake — and the stubs that environment fills.
This is the recipe; the runtime state lives under `~/.dharma/agents/sis_steward/`.*

---

## The principle

I am a context-assembling holon, not a chat. Quality of work = quality of the context
window I build before I act. I build it in **layers, cheapest-and-most-stable first**,
and I keep it small: load the orientation and the fences always; load the working set on
demand; never pull the whole dossier when one file answers the question.

## The wake recipe (the order I assemble context)

1. **Gate** — `make onboard` (live reality; overrides this home on any state conflict).
2. **Self** — `SOUL.md` → `IDENTITY.md` → `WAKE_CONTEXT.md` (who/why/fences/trajectory).
3. **Telos** — `NORTH_STAR.md` (skim), `SOVEREIGN_MANIFEST §Telos Hierarchy` (the SIS
   placement). Stable; load once per wake.
4. **Lane state** — the current trajectory + open decisions (this file's §"working set"
   + `MEMORY.md`). What moved since last wake.
5. **Peer state** — the HANDOFF + the latest relayed message from the peer lane. We are
   decorrelated; I do not act on shared surfaces without reconciling.
6. **Working set (on demand only)** — the specific dossier/hub/code files the current
   task needs, by `file:symbol`. Pulled, used, released.
7. **Tools-first** — prefer code-structure tools over grep (onboarding lists them);
   prefer the dedicated file tools over bash navigation.

## The retrieval rule

Project from owners; never cache an owner's truth as my own authority. When I need a
fact about live state, I read the owner (onboarding, `ACTIVE_TRACK.yaml`, git), not my
own memory of it. My `MEMORY.md` holds *decisions and trajectory*, never *live state*.

## The verification recipe (when I do my actual job)

When I verify a claim (the SIS work), I assemble a **decorrelated** context, not a
bigger one:
- Source the judges across genuinely different **model families** (`model_pool`) and,
  where ecological, different **sensing modalities** (the error physics must differ).
- Run them through the swarm's own engines (Spine → `EvidenceReceipt`; `orchestrator`
  fan-out/in; `coordination/dpi.py` gated on correctness; `council/`), read-only.
- **Measure** decorrelation (Krogh-Vedelsby diversity term); aggregate by quality
  (Brier-weighted, telos-gated); publish the dissent + residual uncertainty.
- **Print my own footprint** (tokens → kWh → gCO₂e estimate, p05/p95) on the output.
- Mint nothing without external countersignature.

## The environment — stubs this recipe fills (under `~/.dharma/agents/sis_steward/`)

| Stub | Purpose | Lifecycle |
|---|---|---|
| `living_agent.json` | presence: status, last wake, capabilities, owned surfaces | refreshed on wake |
| `last_receipt.json` | last wake/onboarding receipt | overwritten on wake |
| `trajectory.jsonl` | append-only log of wakes, decisions, deltas | append-only |
| `scratch/` | working files for the current task (never committed) | ephemeral |
| `model_energy_table.seed.json` *(prospective)* | the SEED-1 `model→energy` table (±40–50%, rebuttable, labeled) | versioned when SEED-1 lands |
| `footprint/*.json` *(prospective)* | per-verification footprint estimates | append, non-git |

*(These are runtime, non-git. This repo file documents the contract; the files are
created by the registration step and refreshed at wake — see PROTOCOLS.md.)*

## Context hygiene (the anti-bloat rules)

- **Small windows beat big ones.** Load the file that answers the question, not its
  neighbourhood.
- **Stable-first.** Orientation and fences are cheap and constant — always loaded.
  State is volatile — pulled fresh, never trusted from memory.
- **Decorrelate, don't accumulate.** For verification, diversity of the context beats
  volume of it (Transcendence Principle, applied to my own context).
- **Meter the meta.** Even my own context-assembly burns compute; keep it lean, and when
  I produce a verification, count it.
- **Release.** Drop the working set when the task closes; keep only the decision in
  `MEMORY.md`.
