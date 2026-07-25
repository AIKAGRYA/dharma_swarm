# Vision + Engine Grill — Decision Seed (2026-07-12)

**Doc role:** `report` (vision-seed / decision record) — **NOT ratified canon.**
This is a durable, dated, custody-labeled capture of decisions the operator confirmed
in a live grill session, preserved per the NORTH_STAR canon-metabolism rule
(`docs/vision_maps/NORTH_STAR.md:175`, §9) so they survive beyond ephemeral session
state. It becomes canon only through the explicit operator-ratified edits named in
"Canon edits pending ratification" below. (`report` per the closed role vocabulary
in `docs/AGENTS.md:30-40`.)

**Subordinate to:** `CLAUDE.md`, `docs/vision_maps/NORTH_STAR.md`, and the canonical
document stack (`docs/governance/CANONICAL_DOC_STACK.md`). **Supersedes/replaces:**
nothing — a new record with no repo-level authority (per `docs/AGENTS.md:18-24`, only
the named owner files make authority claims).

**Location:** this `report` lives under `docs/plans/` (working-doc space, exempt from
the canonical-authority guard). It is deliberately NOT in `docs/vision_maps/` (the
authority/vision space): a non-authority record does not belong there. The distinct
**honeycomb CANON seed** named in "Canon edits pending ratification" below is what
targets `docs/vision_maps/` — and only upon operator ratification, as a separate
future doc, not this record.

**Provenance:** grill run via `.claude/skills/grill-me/SKILL.md` (adapted from Matt
Pocock's grill-me, MIT). Original ephemeral log:
`~/.dharma/grill/2026-07-12-vision-and-engine-grill.md` (home dir, not git — the
reason this seed exists). Session: `claude/onboarding-langraph-parity-viapg7`.
Subject: operator's present vision vs canon (`docs/vision_maps/NORTH_STAR.md`,
locked 2026-06-11) and DharmaGraph next-phase requirements.
Status at capture: grill **CLOSED** 2026-07-12 by the operator's engine-requirements
statement.

---

## Decisions confirmed (operator-affirmed in-session)

1. **TELOS — dual, not single.** A truly autonomous organism **and** a
   user-directed, co-creative instrument. "Trust before scale" is the live
   operational *why*; Jagat Kalyan rides on it. (Operator: the single-telos framing
   "narrows things.")

2. **SOVEREIGN UNIT — the dyad** (one human + their swarm). Lattice-level autonomy
   emerges from a *federation of dyads*; no layer overrides a cell-operator's veto
   over their own cell. Only the axiom layer (ahimsa / satya / consent) propagates
   non-negotiably.

3. **RATIFICATION vs VERIFICATION — the load-bearing distinction.**
   - *Ratification* (human-in-loop permission) is **stage-bound and dissolves** as
     trust is earned. Hybrid model: cross-model peer consensus (decorrelated second
     signatures, e.g. Claude + Codex) + **receipts as the recovery substrate**.
     Autonomy prices against **reversibility**: fully reversible → peer consensus
     proceeds; irreversible → human key, held longest.
   - *Verification* (gates, receipts, self-checks) is **permanent** — proprioception,
     not a leash.
   - Operator's phrasing: co-creative union; at sufficient understanding + traction
     the only limit is funds (compute / money / energy).

4. **HONEYCOMB — seeded, not tracked.** Per-user cell / "palantir for peace from an
   iPhone" is **SEEDED**, no product push until the swarm has made **~$1M in full
   display**. Overmind places user visions into the holarchy **only** with opt-in,
   legible, exit-preserving placement (consent runs both directions).

5. **ENGINE REQUIREMENTS — no first-passenger specialization.** ("It shouldn't
   matter — that is TAM.") Requirements, verbatim: **durable complexity, multi-day
   campaign bearing, provider/model/agent-agnostic organizing intelligence.** These
   map to the workload-agnostic top of the parity rubric — **LG18 (w10), LG15 (w9),
   LG17 (w8)**, plus LG24 / LG25 / LG30 / APP01 (weights per
   `reports/governance/dharmagraph_parity/PARITY_MATRIX.md`). **Next build phase:
   DharmaGraph spec Phase 0b (`docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md:77`;
   crash-resume + exactly-once dispatch), then the durability cluster.**

6. **REAL PROBLEM NAMED.** "The wiring is not working and the agents aren't
   working" — agents keep asking *narrowing* questions that shortsell the substrate.
   Matches `docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md:18` (§1) **as diagnosed
   2026-07-05**: crash-resumable dispatch FALSE (`orchestrator.py:2403-2407`; dispatch
   is a detached `asyncio.create_task`, no boot reconciler for `delegation_runs`),
   5+ fragmented executors, heartbeat then-unwired (`heartbeat_claim_sync`,
   `runtime_state.py:2074`).
   > Re-derived on current main 2026-07-13 (citation-or-silence, not copied polish):
   > the heartbeat has SINCE been wired — `dharma_swarm/graph/reconciler.py:480` now
   > calls `heartbeat_claim_sync` ("wires the previously-orphaned" one, `:450`). Treat
   > these spec-§1 lines as the DATED grill diagnosis; re-derive current engine status
   > against main before acting. (The `:2062` in the first draft of this seed was a
   > stale line copied from the spec without re-derivation — the exact mistake the
   > rule forbids; `heartbeat_claim_sync` is at `:2074`.)

---

## The two 2026-07-12 drills agree on the target

This grill (Decision 5) and the independent **DharmaGraph × LangGraph parity
gauntlet** (`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:1-3` — **31.00/100,
NOT_FINISHED**, judge-signed, committed `6965d38` / resealed `6644d57`) point at the
same rows. The highest-weight open parity gaps are exactly the durability cluster:

| Card | Gap | Weight |
|---|---|---:|
| LG18 | Durability ordering + process-restart recovery | 10 |
| LG15 | Thread-scoped continuity + resume | 9 |
| LG17 | Manual/bulk state update, fork, time travel | 8 |
| LG14 | Checkpoint schema, saver protocol, pending writes, lineage | 4 |

**Coherent conclusion:** the next DharmaGraph build target is a single
**persistence / resume kernel** (Phase 0b crash-resume + exactly-once dispatch →
LG14–LG18), *not* a scatter across the 39 gap cards.

---

## Canon edits pending operator ratification (owner files)

These were named in-grill as the metabolization edits; **none have landed** as of
this seed. They touch canon owner files and must be operator-ratified (draft-only
until then):

- **Honeycomb / holarchy seed** → `docs/vision_maps/` (dated seed, custody-labeled).
  Draft essence: a replicable personal swarm cell in co-creative union with its
  operator; cells honeycomb into the lattice; overmind placement is
  opt-in / legible / exit-preserving; gated behind the $1M full-display proof.
- **Ratification-vs-verification doctrine line** → `SOVEREIGN_MANIFEST` or
  `NORTH_STAR` §8 vicinity: *"ratification dissolves by earned, reversibility-priced
  delegation; verification never dissolves."*
- **NORTH_STAR §11 90-day horizon** (dated ~2026-06-11, lands ~mid-September):
  re-stamp or annotate so the date cannot rot in canon.

## Open items NOT resolved by this grill

- D2 ratification record (operator-only, onboarding spec §9.2); C1 merge-blocking
  context promotion; D3 fleet reader sweep.
- Parity non-goal ratification: decide **after** the checkpoint/durability cluster
  lands.
