---
id: onboarding-brief
version: 0.0.1
theme: 11-onboarding-and-comprehension
status: tested
invariant: >
  An onboarding brief transfers the THEORY of the system (Naur), not a tour. It
  must be FAITHFUL (real file paths and function names, never plausible-sounding
  fabrications), PRIORITIZED to the reader's time budget, and HONEST about
  landmines and the things the code itself can't answer. Padding and invented
  structure are the failure mode — a newcomer who trusts a wrong path loses an
  hour.
lineage:
  - "Naur 1985 — Programming as Theory Building: onboarding = transferring the theory"
  - "Parnas — the module guide: each module's responsibility and secret, stated once"
  - "Brooks — conceptual integrity; name the few ideas that organize the whole"
ground_truth_tools: ["real folder/file listing", "real entry points (grep main/cli/app)", "the repo's own onboarding/navigation docs if any"]
returns_clean: true
---

## Prompt

> Generate a focused onboarding brief for a developer joining tomorrow with **30
> minutes** to skim. The invariant (Naur): transfer the *theory* of the system,
> not a tour — and be **faithful** (real paths/function names you verified, never
> plausible-sounding guesses). Sections, in order:
>
> 1. **What this project does** — 3 sentences max, for someone who's never seen it.
> 2. **Stack & key dependencies** — language, framework, datastore, notable libs,
>    deploy target.
> 3. **Entry points** — 1–3 real files where execution starts, one line each.
> 4. **Core domain concepts** — the 3–7 nouns that show up everywhere, defined by
>    **how the code actually uses them** (cite where).
> 5. **Module map** — top-level folders, one line of responsibility each.
> 6. **Where to make common changes** — "to add an X: edit A, then B, then C".
> 7. **Landmines** — the weird/hacky/fragile things a newcomer trips over (be
>    specific: the 5000-line file, the dynamic loader, the flaky test).
> 8. **Open questions** — what the code does *not* make clear that you'd ask the team.
>
> Reference **real file paths and function names**. If you can't verify a path,
> say so rather than invent one. Do not pad — a thin honest brief beats a thick
> fabricated one. If the repo has its own onboarding/navigation doc, build on it
> instead of duplicating.

## Why it's built this way

The kit's version is already well-structured. The discipline we add is **fidelity
over fluency**: an onboarding brief that *sounds* right but cites a path that
doesn't exist is worse than no brief — the reader burns their 30 minutes on a
fiction. Naur's "theory building" is the frame (sections 4 & 7 carry the theory;
the rest is navigation); Parnas's module guide is section 5; Brooks's conceptual
integrity is why section 4 is capped at 7 nouns.

## Demonstration run (real, abbreviated)

**Target:** `dharma_swarm/`, 2026-06-25.

1. **What it does:** A self-modifying multi-agent "organism" — a Python swarm that
   routes tasks across LLM providers, evolves its own agents under safety gates,
   and governs itself via receipts and ratchets.
2. **Stack:** Python 3.11+, Pydantic 2, async (`aiosqlite`/`aiofiles`); FastAPI
   (`api/`), Next.js dashboard (`dashboard/`); some Go sense-organs (`tools/*_go`).
3. **Entry points (verified):** `dharma_swarm/cli.py` (629 ln, the `dgc` CLI) ·
   `api/main.py` (324 ln, FastAPI app) · `dharma_swarm/swarm.py` (3227 ln,
   `SwarmManager` top-level coordinator).
4. **Core concepts (as used):** `Organism` (`organism.py`) — the living system;
   `SwarmManager` (`swarm.py`) — agent pool + task board; `EvidenceReceipt`
   (`spine/`) — the one proof every dispatch emits; `TelosGatekeeper`
   (`telos_gates.py`) — 11 safety gates; `MemoryKernel` (`memory_kernel/`) — the
   memory front door.
5. **Module map:** `dharma_swarm/` (runtime core, ~784 modules) · `api/` (FastAPI)
   · `dashboard/` (Next.js) · `scripts/governance/` (the ratchets/onboarding) ·
   `docs/` · `foundations/` (the genome) · `tools/*_go` (Go ingestors).
6. **Common changes:** *new dispatch path* → flow through `spine.invoke_agent()`
   (emits the receipt), not around it. *governance counter* → `ratchet_counters.py`
   + baseline. *onboarding state* → it's generated; run `make onboard`.
7. **Landmines (specific):** `thinkodynamic_director.py` is **5,255 lines** (8 files
   >3000); the module loader is **dynamic** (CLI/registry/MCP import by string — a
   "no static importer" ≠ dead); **244 witness-less `except` swallows**; see
   `INTERFACE_MISMATCH_MAP.md` for live BLOCKER/DEGRADED pairs.
8. **Open questions:** which of the 784 modules are actually live vs archival? what
   is the real provider-key posture in prod? (the code can't tell you — ask the team).

**Honesty note:** this repo *has* its own onboarding (`make onboard`,
`scripts/governance/agent_onboard.py`) — a faithful brief points there rather than
fabricating a parallel map. Saying that is the discipline.

## Changelog

- **v0.0.1** (2026-06-25) — rewrite of a kit's onboarding-brief prompt. Added
  fidelity-over-fluency (verify paths or say you can't), Naur/Parnas/Brooks lineage,
  and build-on-the-repo's-own-onboarding. Demoed against `dharma_swarm` with real
  verified paths, real landmines (the 5,255-line file, dynamic loader, 244 swallows),
  and a pointer to `make onboard`.
