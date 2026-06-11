# Swarm Genome / Command Map Convergence Spec

Date: 2026-06-11
Status: draft mission spec
Primary mode: read-only reconnaissance, then synthesis
Intended runner: `/goal`, `ds-goal`, or a bounded six-agent parallel scan

## 1. Mission

Build the missing fast-path cognitive map for the whole Dharma Swarm organism.

The repo currently has strong operating canon: onboarding, governance, active tracks, anti-slop rules, runtime truth, verification gates, and safety rails. That makes agents safer around code, but it does not yet put the full organism vision into the first-token path.

The mission is to let a powerful new agent understand the whole system in:

- 10 seconds: identity, grand vision, live organs, active work, weak spots.
- 10 minutes: source families, health of each organ, revenue/research/media/runtime map.
- 1 hour: what is working, semi-working, aspirational, stale, duplicated, or bloated.
- 1 day: where to safely improve the organism without losing complexity, sophistication, or vision.

The desired end state is a proposed canonical front door, tentatively named `SWARM_GENOME.md` or `COMMAND_MAP.md`, plus receipts proving which files support each claim.

## 2. Non-Goals

- Do not clean, delete, rewrite, or consolidate canon during the first pass.
- Do not let six agents produce six overlapping essays with no integration.
- Do not collapse the vision into engineering governance only.
- Do not collapse the repo into mystical language without runtime, revenue, research, and verification grounding.
- Do not claim a source family is working unless code, tests, receipts, runtime logs, or governance evidence support that claim.
- Do not silently edit high-authority files such as `CLAUDE.md`, `AGENTS.md`, `SOVEREIGN_MANIFEST.md`, `ACTIVE_TRACK.yaml`, or onboarding docs during reconnaissance.

## 3. Expert Lenses

Each lane should explicitly borrow from these expert frames:

- Complex systems architect: organism health, feedback loops, metabolism, viability, emergence.
- Founding CEO / capital allocator: what funds the system, what can sell, what has near-term leverage.
- Palantir-style ontology architect: source of truth, operational graph, decision intelligence, human-in-the-loop workflows.
- SRE / platform reliability engineer: what is live, testable, maintainable, observable, and brittle.
- Research lab PI: mech-interpretability, consciousness research, R_V, knowledge programs, real research agenda.
- Media / memetics strategist: Loomwork, public narrative, noosphere, trust, cultural propagation.
- Adversarial editor: stale canon, overclaims, duplicate maps, vibe-only language, missing operational closure.

## 4. Required Source Families

Agents should discover more sources, but the first sweep must include these families when present:

- `WHAT_IT_WANTS_TO_BECOME.md`
- `foundations/`
- `docs/MEGAFILE_INDEX.md`
- `docs/vision_maps/`
- `docs/architecture/GENOME_WIRING.md`
- `docs/telos-engine/`
- `docs/loomwork/`
- `docs/doctrine/`
- `docs/governance/ACTIVE_TRACK.yaml`
- `docs/governance/SOVEREIGN_MANIFEST.md`
- `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`
- `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md`
- `docs/state/BROKEN_REGISTER.md`
- `reports/governance/active_track_evidence.md`
- `reports/anatomy_altitude_2026-06-10/`
- `reports/capital_lab/`
- `dharma_swarm/capital_lab/`
- `dharma_swarm/revenue/`
- `scripts/revenue/`
- `dharma_swarm/ginko_*.py`
- `docs/GINKO_ENHANCEMENT_WAVE.md`
- `requirements-ginko.txt`
- `dharma_swarm/chetana/`
- `dharma_swarm/memory_kernel/`
- `dharma_swarm/knowledge_ops/`
- `~/.dharma/knowledge/wiki/` when locally readable
- `reports/agentops/work_packets/`
- `reports/sovereign_holons/`
- `docs/sovereign_holons/`

## 5. Six-Agent Lane Design

All six agents operate read-only unless explicitly promoted by the synthesizer after the scan.

### Agent 1: Telos / Vision Cartographer

Question: What is this organism trying to become?

Scan for:

- grand vision;
- organism identity;
- Krishna/Arjuna, Sakshi/Drishti, witness/seer, consciousness, noosphere, good-works arc;
- media and memetics;
- "Palantir of good works" or operating-company organism language;
- contradictions between old and recent vision docs.

Output:

- top 20 vision source files with one-line purpose;
- 10-second vision summary;
- missing first-read material;
- stale or fragmented vision documents;
- quotes or short paraphrases with line references.

### Agent 2: Revenue / Capital / Self-Funding Strategist

Question: How does the organism fund itself and become economically alive?

Scan for:

- Shakti Ginko;
- Capital Lab;
- stock trading, paper/live broker paths, risk membranes;
- scrappy cash-claw systems;
- venture cells and revenue wedges;
- market-facing organs;
- current blockers to revenue-external-humans-served.

Output:

- revenue organ map;
- capital/trading readiness map;
- what is live, semi-live, aspirational, stale;
- strongest near-term self-funding paths;
- missing active tracks and governance gaps.

### Agent 3: Research / Mech-Interp / Chetana Scientist

Question: What is the research engine, and how does it feed organism intelligence?

Scan for:

- R_V and mech-interpretability;
- Chetana;
- memory kernel;
- knowledge ops;
- semantic search and wiki;
- consciousness research;
- research-depth objective gaps;
- how research outputs become operational knowledge.

Output:

- research program map;
- knowledge graph / wiki / memory-kernel health map;
- top missing feedback loops;
- what would make 10-second understanding possible from memory alone;
- stale, duplicate, or disconnected research surfaces.

### Agent 4: Operating System / Governance Architect

Question: What rules tell agents how to work safely, and what do those rules hide?

Scan for:

- onboarding;
- operating canon;
- active tracks;
- manifests;
- broken registers;
- anti-slop doctrine;
- verification gates;
- agent rules;
- how current entrypoints bias agents toward substrate repair over full organism telos.

Output:

- current first-read stack;
- governance source-of-truth map;
- strongest weak spots in current kanban/todo surfaces;
- exact places where revenue, research, media, and self-evolution are absent or underweighted;
- proposal for where `SWARM_GENOME.md` should sit in the canon.

### Agent 5: Organs / Runtime / DevOps Systems Engineer

Question: Which organs actually exist in code, and how healthy are they?

Scan for:

- runtime organs;
- APIs, daemons, CLIs, schedulers, tmux loops;
- tests and receipts;
- capital, revenue, chetana, memory, holon, loomwork, a2a, control surface, swarm runtime;
- bloat, duplicate organs, broken imports, stale scripts, fake-live surfaces.

Output:

- organ inventory with status: working, semi-working, aspirational, stale, bloated, dangerous;
- verifier commands per live organ;
- top runtime risks;
- top cleanup candidates;
- top "do not touch until understood" surfaces.

### Agent 6: Synthesis / Adversarial Editor

Question: What is the smallest true map that makes the next agent vastly stronger?

This agent waits for the other five outputs, then attacks them.

Responsibilities:

- identify contradictions;
- reject unsupported claims;
- rank weak spots by leverage;
- merge overlapping source families;
- detect missing organs;
- produce the proposed `SWARM_GENOME.md` / `COMMAND_MAP.md` draft;
- produce a minimal onboarding patch plan, but do not apply it unless explicitly authorized.

Output:

- `reports/swarm_genome/<date>/SYNTHESIS.md`;
- proposed `docs/governance/SWARM_GENOME.md` or `docs/ops/COMMAND_MAP.md`;
- proposed first-read stack update;
- ranked weak spots;
- "10 seconds / 10 minutes / 1 hour / 1 day" comprehension ladder;
- exact source index.

## 6. Output Contract

Each lane writes one receipt:

`reports/swarm_genome/2026-06-11/agent_<lane>_<slug>.md`

Each receipt must contain:

1. Role and question.
2. Files read, grouped by source family.
3. Claims with source paths and line references when possible.
4. Organ health labels: working, semi-working, aspirational, stale, duplicate, bloated, dangerous, unknown.
5. Top 10 findings.
6. Top 10 weak spots.
7. What the final command map must include.
8. What the agent is unsure about.
9. Suggested verifier commands or follow-up scans.

The synthesis receipt must additionally contain:

1. One-page 10-second map.
2. One-page 10-minute map.
3. One-hour reading order.
4. One-day deep-dive order.
5. Ranked source-of-truth hierarchy.
6. Ranked organism weak spots.
7. Candidate canonical artifact draft.
8. Candidate onboarding patch plan.
9. Open questions for the operator.

## 7. Health Labels

Use these labels consistently:

- Working: code, docs, tests, receipts, or runtime evidence agree.
- Semi-working: visible implementation exists, but proof is incomplete, brittle, or stale.
- Aspirational: vision exists, but there is little or no implementation.
- Stale: source appears superseded, contradictory, or no longer in the active path.
- Duplicate: multiple surfaces claim the same authority without a clear hierarchy.
- Bloated: volume or indirection harms comprehension or operation.
- Dangerous: likely to mislead agents or cause unsafe work if treated as canonical.
- Unknown: not enough evidence yet.

## 8. Success Criteria

The mission succeeds when a new agent can read one final synthesis artifact and answer:

- What is Dharma Swarm becoming?
- How does it intend to fund itself?
- Which organs exist, and how healthy are they?
- Where are revenue, research, media, memetics, consciousness, and runtime truth located?
- What is live versus aspirational?
- What should an agent read first?
- What are the top weak spots by leverage?
- What should be done next by role?
- Which files support those answers?

## 9. Verification

Minimum verification before declaring done:

- All six lane receipts exist.
- Synthesis cites all lane receipts.
- Synthesis cites source files, not only agent opinions.
- No high-authority files were edited unless explicitly authorized after the read-only phase.
- `rg -n "SWARM_GENOME|COMMAND_MAP|Swarm Genome|Command Map" docs reports foundations` confirms discoverability of the new report/spec surfaces.
- If candidate canonical docs are created, run the narrowest relevant DocOps or markdown integrity check available in the repo.

## 10. Suggested Handoff `/goal` Prompt

Use this compact prompt to launch the next pass:

```text
/goal Read /Users/dhyana/dharma_swarm/docs/agent_tasks/2026-06-11_swarm_genome_convergence_spec.md first. Execute the Swarm Genome / Command Map Convergence mission in read-only mode unless the spec explicitly permits report artifacts. Coordinate six lanes: telos/vision, revenue/capital, research/mech-interp/chetana, governance/operating canon, runtime/organs/devops, and adversarial synthesis. Produce lane receipts under reports/swarm_genome/2026-06-11/ and a final SYNTHESIS.md that gives a 10-second, 10-minute, 1-hour, and 1-day understanding path for the whole Dharma Swarm organism. Do not edit high-authority canon during reconnaissance. Rank working, semi-working, aspirational, stale, duplicate, bloated, and dangerous surfaces. The final output should make a powerful new agent understand the full organism vision, not only the substrate repair story.
```

## 11. Operator Notes

This mission is not a doc cleanup. It is the missing shared cognitive operating system.

The important failure mode is producing another long report that agents do not read. The synthesis must become a front-door map with exact links, ranked weak spots, and a role-aware next-action matrix. The map should preserve the system's complexity while making the first ten seconds dramatically better.
