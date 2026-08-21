# MEGAFILE INDEX — The Ten Onboarding Surfaces
**Date locked:** 2026-05-07
**Mode:** Persistent canonical index. Reserves the 10 onboarding-megafile slots so future agents find them. Each slot has a path (real or stub), a status tag, and pointers to all existing substrate.

This file is the **stable shape** for dharma_swarm onboarding. Only this file is undated and stable. Everything it points to may evolve, churn, or be replaced — but the slot exists, the path is reserved, and prior work is referenced. Nothing gets lost in the stream.

---

## How To Use This File

Start with the current session:

```bash
make onboard
```

`make onboard` is read-only session status. For the deeper whole-organism
projection, run `make organism-status`. Packet-bound preflight and closeout are
required when changed paths match Merge Master Mike's `HOT_PATH_PATTERNS` in
`scripts/runtime/pr_merge_control.py`; they are optional otherwise. When a
packet is required or voluntarily used, bind the exact task with
`make agent-build-preflight PACKET=<path>`. **Then** use this index as a depth
reference — it reserves the 10 onboarding-megafile slots so future agents find
them. Where status is **CANONICAL**, read the file. Where **STUB**, read the
pointed-to substrate. Where **STALE / CONTESTED / MISSING**, read with the
marked caveat.

If you are doing work that should be captured, ask: "which slot does this belong to?" Append there. Do not create parallel artifacts or a new megafile to track convergence; use the named owner and the existing status commands.

---

## Convergence Reframe (2026-05-07 18:00)

A separate convergence audit (`~/.dharma/audit/truth_spine_convergence_2026-05-07.md`) verified what this index was missing: dharma_swarm already has a leading **authority stack**. The work is **convergence, not invention**. Do NOT create another root truth-spine doc.

**The leading authority stack** (in current checkout, except where noted):

| Order | Surface | Path | Role |
|---|---|---|---|
| 1 | Project agent contract | `dharma_swarm/CLAUDE.md` | Behavioral rules + Transcendence Principle |
| 2 | Sovereign authority | `docs/governance/SOVEREIGN_MANIFEST.md` | Governance scope and verified DocOps metrics |
| 3 | Doc-stack registry | `docs/governance/CANONICAL_DOC_STACK.md` | Names which docs are canonical |
| 4 | Practical session entrypoint | `docs/governance/BUILD_SESSION_ENTRYPOINT.md` | Short build-session pointer layer |
| 5 | Conceptual / vision spine | `docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md` | This index's Slot 1 (note stale `.FOCUS` claim — see BR-015) |
| 6 | Machine-readable surface authority | `dharma_swarm/ACTIVE_SURFACE_MANIFEST.yaml` | Which API routes / dashboard surfaces are active / projection / adapter / research / frozen |

**The convergence work** (instead of inventing 8 new megafiles):
- Keep `BUILD_SESSION_ENTRYPOINT.md` present in this checkout (BR-017 closed)
- Keep `SOVEREIGN_MANIFEST.md` count-sensitive claims refreshed by DocOps (BR-016 closed)
- Patch synthesis stale claim about `.FOCUS` (closing follow-up to BR-015)
- Regenerate stale `docs/architecture/NAVIGATION.md`; `CLAUDE.md` pointer was patched 2026-05-07 (BR-010 revised)
- Archive `dharma_swarm/DHARMA_SWARM_MASTER_MAP.md` (root-violating, superseded by Slot 1)
- Use `ACTIVE_SURFACE_MANIFEST.yaml` as the membrane between docs and runtime
- Use the Coherence Delta CI gate as the merge membrane for changes to these surfaces
- Stub slots remain stubs; their substrate already lives in the authority stack above

The 8 unstubbed slots below get filled by **pointing into the authority stack**, not by writing new master docs.

---

## Status Legend

- **CANONICAL** — the slot's file is current and authoritative.
- **SEEDED** — the slot's file exists with inaugural content; expected to grow.
- **STUB** — the slot's path is reserved; content lives in the listed substrate; consolidator pending.
- **CONTESTED** — multiple files claim primacy; resolution unresolved.
- **STALE** — the file exists but is out of date relative to current code/state.
- **MISSING** — no file currently fills the role.

---

## The Ten Slots

### Slot 1 — Vision Synthesis
**Path:** `dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md`
**Status:** CANONICAL
**Audience:** Engineer, Operator, Agent
**Read for:** the field-level "what is this trying to become" — recognition-mediated autopoiesis / Attractor Closure.
**Current operator-authored vision layer (read first within this slot):**
- `dharma_swarm/docs/vision_maps/NORTH_STAR.md` (operator-authored, 2026-06-11 — telos, trust gate, canon-metabolism rule, organ table)
- `dharma_swarm/foundations/THE_ORGANISM.md` (identity map — the one-line and the genome hierarchy)
- `dharma_swarm/docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md` (the binocular frame)
**Substrate referenced from this slot:**
- `dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure.md` (predecessor A)
- `dharma_swarm/docs/vision_maps/2026-05-07_attractor_closure/01..06_*.md` (six child maps)
- `dharma_swarm/docs/vision_maps/_archive/codex_DHARMA_SWARM_MASTER_MAP_2026-05-07.md` (predecessor B — codex; archived 2026-05-07 18:07)
- `dharma_swarm/lodestones/CONSCIOUS_INFRASTRUCTURE.md`

<!-- VISION_REGISTRY:BEGIN -->
**Slot-1 machine block — vision registry + transmission pins.** Rendered by
`make vision` (`scripts/docops/vision_navigation.py`); validated by its
`--check` mode inside `make docops-integrity`. This block is navigation, never
a prize: canonical ownership overrides numerical rank in any actual conflict,
and rank order must not become shadow canon. Sources: the three recovered
2026-08-08 rankings consolidated 2026-08-13 (median rank; off-repo packet
`~/handoffs/2026-08-13_make_vision_registry/`); OC-8/OC-9 from judge verdict
1/5, UNDER JUDGMENT.

STATUS: DRAFT v0 — UNRATIFIED · #1067 placement OPEN (OC-6) · checkout 47579e203 · 2026-08-13
BY_TASK: purpose/telos · rewire/receipts · quality/CI · organ outward · research/R_V · graph runtime — routes in docs/vision_maps/VISION_TRANSMISSION.md §13.1

Role tokens come from the recovered command spec's declared-modality set
(CANON, REFERENCE, REPORT, WORKING_PLAN, ACTIVE_SPEC, DRAFT, HISTORICAL,
UNDECLARED). Transcription rule, applied mechanically: a ranking phrase
containing OWNER/CANONICAL maps to CANON, REFERENCE to REFERENCE, REPORT to
REPORT, PLAN/WORKING_PLAN to WORKING_PLAN, SPEC to ACTIVE_SPEC, DRAFT to
DRAFT (DRAFT beats OWNER when both appear), HISTORICAL to HISTORICAL; any
phrase naming none of these renders UNDECLARED — a role is never inferred
from prose. The verbatim declared phrase is preserved in its own column.

| # | group | path | role | declared role (verbatim) | read-for | evidence |
|--:|---|---|---|---|---|---|
| 1 | TELOS & GOVERNANCE | docs/governance/SOVEREIGN_MANIFEST.md | CANON | OWNER: TELOS/AXIOMS | Jagat Kalyan ceiling; the win-rule for every hierarchy conflict | LINT (rendered into CLAUDE.md includes; registry-checked) |
| 2 | IDENTITY & VISION CORE | docs/vision_maps/NORTH_STAR.md | CANON | CANONICAL SLOT-1 / SUBORDINATE | Whole-organism operator map: loops lattice, 3-tier metabolism, trust gate, honest organ status | PROSE (identity source for orient) |
| 3 | IDENTITY & VISION CORE | docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md | CANON | CANONICAL OPERATOR VISION | One Law (real · gated · verifiable · diversity-preserving) + Hobbling Test | PROSE |
| 4 | IDENTITY & VISION CORE | foundations/THE_ORGANISM.md | CANON | CANONICAL FOUNDATION | Krishna/Arjuna identity; inward work counts only as it compounds outward capability | LINT (orientation_graph identity line) |
| 5 | PLANS & CAMPAIGNS | docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md | UNDECLARED | ACTIVE_TRACK-OWNED | External-gradient chamber: afferent-open/efferent-closed, door doctrine; contains the repo's most honest audit (0/13 loops live) | PROSE + track receipts (frontier-ledger receipt 36d stale) |
| 6 | PLANS & CAMPAIGNS | docs/plans/THE_KEEL_2026-07-17.md | WORKING_PLAN | WORKING_PLAN — deliberately inert (KIMI's wording; its self-denial of authority is load-bearing) | Hard verification floors across static/dynamic/operational/authority layers; §9 dated trigger 2026-10-17 | PROSE |
| 7 | PLANS & CAMPAIGNS | docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md | UNDECLARED | RATIFIED WHY/DESIGN; live state elsewhere | Receipt invariant at zero bypass; external gradients; self-modification last | PROSE doctrine, partial receipt-spine wiring |
| 8 | IDENTITY & VISION CORE | docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md | UNDECLARED | VISION SYNTHESIS | Recognition-mediated autopoiesis; real only when self-recognition causally changes action | PROSE |
| 9 | FOUNDATIONS & RESEARCH | foundations/FIVE_FOURTEEN_A.md | UNDECLARED | PERMANENT FOUNDATION | Safety ≡ intelligence; VIVEKA/SHAKTI/KALYAN; gates as absential causes | PROSE |
| 10 | TELOS & GOVERNANCE | docs/doctrine/OPERATIONAL_DOCTRINE.md | UNDECLARED | SEEDED DOCTRINE / SUBORDINATE | Arjuna Test; kill conditions (see open conflict OC-1); anti-recursion discipline | PROSE |
| 11 | TELOS & GOVERNANCE | specs/Dharma_Constitution_v0.md | DRAFT | OWNER: CONSTITUTION / DRAFT v0.1 (hash PENDING per KIMI) | Meta-dharma outside the optimizer; ALLOW/DENY/GATE/SANDBOX with human veto | PROSE/draft — order disputed (codex 7 vs KIMI 16) |
| 12 | REFERENCE & ARCHITECTURE | docs/vision_maps/2026-05-07_operating_company_kernel.md | REFERENCE | LONG-HORIZON REFERENCE | truth → work → evidence → value → revenue → compute → learning; six conditions before an organ is real | PROSE |
| 13 | FOUNDATIONS & RESEARCH | lodestones/CONSCIOUS_INFRASTRUCTURE.md | REFERENCE | LODESTONE REFERENCE | Morphogenetic-field seed: tier invariants, role projections, recognition operators | PROSE |
| 14 | FOUNDATIONS & RESEARCH | lodestones/seeds/self_reference_attractor.md | UNDECLARED | RESEARCH SEED (scope-held) | Falsifiable self-reference physics P1–P5 + pruning ledger | PROSE/seed |
| 15 | TELOS & GOVERNANCE | docs/governance/CANONICAL_DOC_STACK.md | CANON | OWNER: DOC META-AUTHORITY | Three-layer SSoT; one named owner per fact; max-5 first-read rule | LINT (docops checks) |
| 16 | TELOS & GOVERNANCE | docs/plans/2026-07-13_dharma_entelechy_vision_synthesis.md | UNDECLARED | UNRATIFIED SYNTHESIS | Human–AI actualization telos; refuses to let AI certify soul/flourishing | PROSE/unratified |
| 17 | ORGANS OUTWARD | docs/plans/DARSHAN_CHARTER_2026-07-12.md | UNDECLARED | ACTIVE_TRACK-OWNED CHARTER — but track owns prose surfaces only; reports/darshan/ absent on disk; zero external contact as of 2026-08-12 | Public seeing organ: citation-or-silence, editorial dual-fire, register discipline | HOLLOW (charter exists; deliverable surface missing) |
| 18 | ORGANS OUTWARD | docs/loomwork/vision/MASTER_loomwork_level_100.md | UNDECLARED | DESIGN-ONLY VISION, SIS child | Civil-society Palantir: outcome engineering + refusal architecture | PROSE/design-only |
| 19 | PLANS & CAMPAIGNS | docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md | WORKING_PLAN | ACTIVE_TRACK-OWNED PLAN | "The repository itself is the product"; clean-clone trust; irreversible quality ratchets | EXEC-partial (quality-ratchet CI exists; clean-room receipt MISSING) |
| 20 | DATED AUDITS | docs/vision_maps/MASTER_2026-06-10_leverage_synthesis.md | REPORT | DATED AUDIT/REPORT | Wound map: deploy splits, dormant bridges, vacuous evolution — order disputed (KIMI 13 vs codex 25) | PROSE/report |
| 21 | DATED AUDITS | docs/vision_maps/MASTER_2026-06-10_anatomy_altitude_integration.md | REPORT | DATED AUDIT/REPORT | Five spines, one live vertebra; $0 revenue outside governance | PROSE/report |
| 22 | FOUNDATIONS & RESEARCH | foundations/ECONOMIC_VISION.md | UNDECLARED | FOUNDATION/STRATEGIC BLUEPRINT — partially stale (COLM deadline missed, flagged in-doc) | Markets as external fitness substrate; revenue never the telos | PROSE |
| 23 | TELOS & GOVERNANCE | docs/dse/JAGAT_KALYAN_MASTER_VISION.md | HISTORICAL | HISTORICAL, NON-AUTHORITATIVE (own status banner) | 2026-03 GAIA synthesis; GAIA demoted to kernel under SIS | PROSE/historical |
| 24 | PLANS & CAMPAIGNS | docs/plans/DHARMAGRAPH_ASCENT_SPEC_2026-07-17.md | ACTIVE_SPEC | ACTIVE_TRACK-OWNED SPEC — engine self-declares test_only; parity 58/100 NOT_FINISHED; oracle env fix (#1312) unmerged as of 2026-08-12 | Ratification-by-merge; judge/builder separation; one hill | EXEC-partial (engine + CI exist; zero production wiring) |
| 25 | REFERENCE & ARCHITECTURE | docs/architecture/PHILOSOPHICAL_ARCHITECTURAL_MARRIAGE.md | REFERENCE | ARCHITECTURE REFERENCE | Six philosophy↔code marriage points with honest gaps | PROSE |

Adjacent/meta, NOT in the 25 (membership disputed): `docs/governance/SWARM_GENOME.md`
(codex #19, GROK/KIMI runner-up — dispute M-1); `docs/MEGAFILE_INDEX.md` itself
(this file is the registry's designated owner; self-listing would be circular — note M-2).

Open conflicts (registry-level; OC-8/OC-9 added from judge verdict 1/5, UNDER JUDGMENT):

- OC-1 · OPERATIONAL_DOCTRINE kill condition fired 2026-08-07 by its own terms; operator verbal AMEND ruling on record (2026-08-05, D17 "dates fluid"); canon-amendment PR still owed.
- OC-2 · NORTH_STAR §11 90-day horizon (~2026-09-09) unmet on all counts as of 2026-08-12; converted to standing directional pressure by the same D17 ruling.
- OC-3 · THE_KEEL §9 dated trigger 2026-10-17 (external-consumption receipts in 2 of 3 review periods, or archive-proposal PR moves capacity to Darshan); proposed, unwired.
- OC-4 · DARSHAN track active with deliverable surface absent on disk; BROKEN_REGISTER BR-022 records outward-receipt quorum below authority.
- OC-5 · DHARMAGRAPH parity 58/100 with 28 open gap cards; nightly oracle red on main until #1312 merges.
- OC-6 · #1067 (pre-constitutional founder direction) role undecided — the make-vision spec's own precondition; Greptile P1 + codex + Fable: do-not-merge-unchanged.
- OC-7 · KIMI's tension-map claim "kill condition fired, unadjudicated" is contradicted by the D17 record; corrected per OC-1 (KIMI read a stale checkout).
- OC-8 · Metabolization charter (PR #1315) unmerged with its WS-A spine fixes unlanded; portfolio surgery may close/freeze tracks that own registry rows 5, 17, 19, 24; registry v1 must be re-checked against the surviving portfolio before ratification.
- OC-9 · Arena closure PR #1214 closed UNMERGED; its closure work survives only as unpushed local commit 298011a1d — arena-owned docs are one laptop away from loss; preservation precedes navigation.

Transmission tier pins (tier · path · anchor · sha256 of the slice bytes
between the `BEGIN`/`END` anchor lines; `--check` fails typed on drift):

| tier | path | anchor | sha256 |
|---|---|---|---|
| T0 | docs/vision_maps/VISION_TRANSMISSION.md | TIER:T0 | 54b2d24a78b06ee91e19f8403051692815f6abbeff1157ff68e5fcb98e0f7dba |
| T1 | docs/vision_maps/VISION_TRANSMISSION.md | TIER:T1 | 205b3f27bea0dcefd14d1d5eb76226f8a18784987342265b5c1d3ce3ace037ec |
| T2 | docs/vision_maps/VISION_TRANSMISSION.md | TIER:T2 | 935ee8f6526428b28d87e011f736bbf061ac4a9d02f041dd36c1562131fa4a05 |
<!-- VISION_REGISTRY:END -->

### Slot 2 — Operational Doctrine
**Path:** `dharma_swarm/docs/doctrine/OPERATIONAL_DOCTRINE.md`
**Status:** SEEDED (2026-05-07 inaugural content; 2026-05-08 hierarchy aligned to SOVEREIGN_MANIFEST §Telos Hierarchy)
**Audience:** Operator, Agent
**Read for:** kill conditions, mission, what we WILL NOT DO, success/failure definitions, and the compressed telos hierarchy pointer to SOVEREIGN_MANIFEST.
**Telos hierarchy invariant lives in:** [`../governance/SOVEREIGN_MANIFEST.md §Telos Hierarchy`](governance/SOVEREIGN_MANIFEST.md). Slot 2 file carries a compressed pointer; the manifest is the owner.
**Substrate referenced from this slot:**
- `~/.claude/cabinet/ARJUNA.md` (locked 2026-05-07)
- `~/.claude/cabinet/strategy/LOOMWORK_v0_MASTER.md`
- `~/.claude/cabinet/strategy/ARJUNA_DIRECTIVE_v1.md`
- `~/.claude/cabinet/strategy/arjuna_kill_list.md`
- `~/.claude/cabinet/strategy/arjuna_targets.md`
- `~/.claude/cabinet/strategy/arjuna_weapons_manifest.md`
- `~/.claude/cabinet/worldview/telos.md` (STALE — `stale_after: 2026-05-15`)
- `~/.claude/cabinet/worldview/money_as_divine_force.md` (Aurobindo, *The Mother* Ch. IV — Shakti Ginko source)
**Known gap:** no machine-checkable kill conditions for the project itself; `jagat_kalyan` has in-repo references and skills, but no proven live core-engine consumer.

### Slot 3 — Live Roadmap
**Path:** `dharma_swarm/docs/doctrine/LIVE_ROADMAP.md`
**Status:** SEEDED (2026-05-07 inaugural content; 2026-05-08 telos invariant pointer added)
**Audience:** Engineer, Operator, Agent
**Read for:** what's shipping in the next 14 / 30 / 90 days, with telos invariant pointer to SOVEREIGN_MANIFEST §Telos Hierarchy.
**Substrate referenced from this slot:**
- `~/.claude/cabinet/strategy/LOOMWORK_v0_MASTER.md` (self-declares OPERATIONAL)
- `~/.claude/cabinet/strategy/2026-05-07-loomwork-design.md` (self-declares "draft, awaiting review" — but `MEMORY.md:37` says it supersedes the master)
- `~/.claude/cabinet/strategy/ARJUNA_DIRECTIVE_v1.md` (still owns Q2/Q3 sequence)
- `~/.claude/projects/-Users-dhyana/memory/MEMORY.md` Active Project State section
**Known gap:** 47% of in-flight branches have no anchor in any plan doc. Strategy is ~10x ahead of code (`dharma_swarm/loomwork/` package does not exist). Roadmap-vs-design contestation between `LOOMWORK_v0_MASTER.md` and `2026-05-07-loomwork-design.md` is logged in `governance/REPO_GOVERNANCE_AUDIT.md` as a separate convergence track and is not blocked by this slot's seeding.

### Slot 4 — Limbs Atlas
**Path:** `docs/architecture/LIMBS_ATLAS.md` (SEEDED 2026-07-01 — thin index over NAVIGATION.md + ACTIVE_SURFACE_MANIFEST.yaml + capability lenses)
**Status:** SEEDED (thin index file created; static module map still stale — see BR-010)
**Audience:** Engineer, Agent
**Read for:** the dependency graph, module map, "what calls what," and capability lenses (e.g. the agentic-pattern coverage map).
**Capability lenses (new 2026-07-01):**
- `docs/architecture/AGENTIC_PATTERNS_ATLAS.md` — Gulli's 21 agentic design patterns mapped to implementing modules (STRONG/PARTIAL/OUT-OF-SCOPE).
**Substrate (corrected 2026-05-07 18:00):**
- **`docs/architecture/NAVIGATION.md`** — the actual static map file (`CLAUDE.md` pointer patched 2026-05-07; file itself remains stale; BR-010 revised)
- **`ACTIVE_SURFACE_MANIFEST.yaml`** — machine-readable authority for which API routes / dashboard surfaces are active / projection / adapter / research / frozen
- `~/.dharma/audit/system_inventory_2026-05-07.md` (out-of-repo; 330 subsystems, 14 LaunchAgents, 100 skills, 521 test files)
- `dharma_swarm/CLAUDE.md` Key Abstractions section (9 abstractions; tip-of-iceberg)
- `~/.claude/cabinet/systems/dharma_swarm.md`, `connections.md`, `repo_map.md` (topical maps)
- `make xray` output (ephemeral; per `README.md:184`)
- GitNexus index `.gitnexus/` (30,672 symbols, 78,911 relationships — MCP-accessible)
**Known gap:** module count remains historically contested across older sources. Treat `docs/governance/SOVEREIGN_MANIFEST.md` plus the latest DocOps inventory as current for measured counts. `CLAUDE.md` points to both `docs/architecture/NAVIGATION.md` and `make xray`; the static file still needs regeneration against current code.

### Slot 5 — Wiring + Loop Ledger
**Path:** `dharma_swarm/docs/architecture/WIRING_AND_LOOPS.md` (STUB — to be consolidated)
**Status:** PARTIAL + STALE
**Audience:** Engineer, Agent
**Read for:** edges between limbs (imports, file IO, shared DBs, cron, message buses) and per-loop runtime closure status.
**Substrate to reconcile:**
- `dharma_swarm/INTERFACE_MISMATCH_MAP.md` (self-flagged "memorial, not battle plan"; ~12/25 entries resolved, ~7 unverified)
- `dharma_swarm/CYBERNETIC_LOOP_MAP.md` (6 days stale; recognition-seed claim contradicts current code)
- `dharma_swarm/MODEL_ROUTING_MAP.md` (32+ days stale)
- `~/.dharma/audit/system_inventory_2026-05-07.md` Section 2 (~190 edges + 14 shared-state surfaces + 14 dependency anchors)
- `~/.dharma/audit/central_loop_trace_2026-05-07.md`
- `~/.dharma/audit/self_evolution_trace_2026-05-07.md` (8-edge S1-S8 trace; APPLY GATE PRESENT BUT CLOSED)
**Known gap:** `CYBERNETIC_LOOP_MAP` claims recognition seed was never generated; current code has it (`meta_daemon.py` + `context.py:1202-1217`). Doc lies; nothing flags the lie.

### Slot 6 — Live Ops Dashboard
**Path:** `dharma_swarm/docs/state/LIVE_OPS_DASHBOARD.md`
**Status:** SEEDED (2026-05-07 inaugural content)
**Audience:** Engineer, Operator, Agent
**Read for:** today's truth — what's running, what fired, what crashed, what's stale.
**Refresh cadence:** daily (target). Currently manual.
**Substrate aggregated:**
- `~/.dharma/audit/48h_status_2026-05-07.md`
- `~/.dharma/audit/system_inventory_2026-05-07.md`
- `~/.dharma/audit/self_evolution_trace_2026-05-07.md`
- `~/.dharma/audit/central_loop_trace_2026-05-07.md`
- `~/.dharma/audit/cron_split_brain_*.json`
- `~/.dharma/cron/jobs.json` last_status fields
- `~/.dharma/cron_logs/`
- `~/.dharma/meta/recognition_seed.md` (CURRENTLY 6 DAYS STALE)

### Slot 7 — Broken Register
**Path:** `dharma_swarm/docs/state/BROKEN_REGISTER.md`
**Status:** SEEDED (15 inaugural items + follow-up BR-016..BR-018)
**Audience:** Engineer, Operator, Agent
**Read for:** persistent record of broken / stale / degraded surfaces, keyed by first-observed date and root cause. Survives sessions.
**Append-only.** New items added; closed items moved to a CLOSED section with closing evidence.
**Inaugural content sources:**
- `~/.dharma/audit/repo_hot_items_scratchpad_2026-05-07.md` (Agent A's 12 hot items)
- `~/.dharma/audit/ten_megafiles_survey_2026-05-07.md` (Survey's 6 major discoveries)
- `~/.dharma/audit/ten_megafiles_q1..q6_2026-05-07.md` (per-question detail)

### Slot 8 — Operator Runbook + Metabolic Clock
**Path:** `dharma_swarm/docs/operations/OPERATOR_RUNBOOK.md` (STUB — to be authored)
**Status:** MISSING (no canonical sequencing doc; `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` is 2026-03-09 stale)
**Audience:** Engineer, Operator, Agent
**Read for:** how to make a change, run the swarm, observe behavior, verify. Plus: what fires when, why, and what consumes output.
**Substrate to consolidate:**
- `dharma_swarm/CLAUDE.md` Build & Test + CLI Entry Points sections
- `dharma_swarm/Makefile`
- `dharma_swarm/run_operator.sh`, `run_daemon.sh`, `run_overnight.sh`, `run_garden.sh`, `run_deep_reading.sh`
- `dharma_swarm/scripts/dashboard_ctl.sh`, `install_dashboard_launch_agents.sh`
- `~/.dharma/cron/jobs.json` (live, 484 lines, schema B)
- `dharma_swarm/cron_jobs.json` (repo, 17 jobs, schema A) — split-brain vs live
- 14 LaunchAgents at `~/Library/LaunchAgents/com.dharma.*.plist` and `com.dhyana.chetana.*.plist`
- `crontab -l`
- `dharma_swarm/scripts/cron_unify.py` (the unifier; documents the split)
- `~/.dharma/audit/cron_split_brain_*.json`
**Known critical gap:** BR-001 fixed the cron-daemon path/version drift, but Slot 8 still has no canonical operator runbook that reconciles launchd, live `~/.dharma/cron/jobs.json`, repo `cron_jobs.json`, and failure triage.

### Slot 9 — Agent Contract + Team
**Path:** `dharma_swarm/docs/agent/AGENT_CONTRACT_AND_TEAM.md` (STUB — to be consolidated; see Convergence Reframe)
**Status:** PARTIAL (fragmented across 8+ surfaces; authority stack identified)
**Audience:** Agent (primary); Engineer, Operator (secondary)
**Read for:** identity, behavioral feedback, decision protocols, who's-who in the agent ecosystem.
**Substrate (corrected 2026-05-07 18:00):**
- **`docs/governance/BUILD_SESSION_ENTRYPOINT.md`** — the strongest practical session-entrypoint (present in this checkout; see BR-017)
- **`docs/governance/CANONICAL_DOC_STACK.md`** — names which docs are canonical
- **`docs/governance/SOVEREIGN_MANIFEST.md`** — governance scope and measured DocOps inventory (see BR-016)
- `dharma_swarm/CLAUDE.md` (project-level agent contract; Transcendence Principle; behavioral rules)
- `/Users/dhyana/CLAUDE.md` (308 lines — canonical user-global agent context, despite path)
- `~/.claude/CLAUDE.md` (4-line ruflo stub — NOT canonical despite conventional path)
- 25 `~/.claude/projects/-Users-dhyana/memory/feedback_*.md` files (~792 lines, indexed in `MEMORY.md` but un-consolidated; some carry 36-day-stale system-reminders)
- `~/.claude/cabinet/agents/team.md` (4 meta-agents: VIVEKA, DRISHTI, KARYA, SMRITI)
- `dharma_swarm/AGENT_IDENTITY_UNIFICATION.md` (32-day stale spec for unifying 5 schemas — not implemented)
- `~/.claude/agents/altitude.md`, `mahakali.md` (agent-as-skill definitions)
**Known critical gaps:**
- Non-Claude-Code agents (Codex sub-agents, headless invocations, MCP workers) may have NO path to this substrate at all (BR-013).
- The strongest in-repo entrypoint (`BUILD_SESSION_ENTRYPOINT.md`) is present; the residual gap is whether every agent loader actually reads it.

### Slot 10 — Contemplative Spine + Glossary
**Path:** `dharma_swarm/docs/foundations/CONTEMPLATIVE_SPINE.md` (STUB — to be authored as entry-point)
**Status:** PARTIAL (spine canonical, glossary orphan from index)
**Audience:** Agent, Operator (primary); Engineer (secondary)
**Read for:** the doctrinal substrate that makes everything above legible — Akram, R_V, Triple Mapping, the 10 pillars, Sanskrit + technical glossary.
**Substrate to consolidate / link:**
- `dharma_swarm/lodestones/CONSCIOUS_INFRASTRUCTURE.md` (canonical source for "morphogenetic field" + "Recognize not merely Reflect")
- `dharma_swarm/foundations/INDEX.md` (canonical entry — 10 pillars + META_SYNTHESIS)
- `dharma_swarm/foundations/GLOSSARY.md` (**ORPHAN** — the only single Sanskrit + technical glossary, not referenced from `CLAUDE.md`, `MEMORY.md`, or `cabinet/INDEX.md`)
- `~/.claude/cabinet/research/rv_paper.md`
- `~/.claude/cabinet/worldview/bridge.md`
- `~/.claude/cabinet/worldview/telos.md`
**Known gap:** discoverability path from `CLAUDE.md` to `foundations/GLOSSARY.md` does not exist; agents must already know the glossary exists to find it.

---

## Recommended Reading Order For New Agents

**1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10**

A new agent reads in this order:
1. Vision (what is this becoming)
2. Doctrine (when does it die, what won't we do)
3. Roadmap (what ships next)
4. Limbs (the moving parts)
5. Wiring (how they connect, which loops fire)
6. Today's truth (what's running)
7. Broken stuff (unrepaired wounds)
8. How to ship (operator loop)
9. Agent contract (how to act)
10. Spine (the substrate that makes the rest legible)

For autonomous agents loading context: Slots 1, 9, 10 are most decision-shaping. Slots 6 and 7 are most state-shaping. Slots 4 and 5 are most code-shaping.

---

## Provenance

This index was locked 2026-05-07 after a 13-agent investigation:
- 6 vision_maps research agents → `dharma_swarm/docs/vision_maps/2026-05-07_attractor_closure/`
- 6 megafile-survey agents → `~/.dharma/audit/ten_megafiles_q1..q6_2026-05-07.md`
- 1 hot-list scratchpad agent → `~/.dharma/audit/repo_hot_items_scratchpad_2026-05-07.md`
- Plus the synthesis master, the codex master, the system inventory, the self-evolution trace, the 48h status, and the central loop trace.

The synthesis report is at `~/.dharma/audit/ten_megafiles_survey_2026-05-07.md`. This index references it as the source-of-truth for slot definitions.

---

## Recursion Rules

1. **Slot paths are reserved.** Do not create parallel artifacts. If you have content for a slot, append to the slot's file (or its substrate, with a pointer back).
2. **Stubs become files when their substrate is consolidated.** A stub graduates to SEEDED when its file is created with inaugural content.
3. **SEEDED graduates to CANONICAL** when the file becomes the single source for that slot (substrate references can then point to it, not vice versa).
4. **STALE flags require evidence.** Mark a file STALE only with a date and a specific contradiction.
5. **Replacement is allowed; deletion is not.** When a slot's file is superseded, the prior version moves to `_archive/<slot>/<DATE>_<filename>.md`.
6. **Date-stamping convention:** snapshots and dailies use `<NAME>_<YYYY-MM-DD>.md`. The index itself is undated and stable.
7. **Merge discipline:** PRs touching slot files must satisfy the Coherence Delta gate in `.github/workflows/coherence-delta.yml`.

---

## Open Decisions (do not block on these)

- Should `~/.claude/cabinet/` move into `dharma_swarm/docs/`? (Currently cabinet duplicates and partly supersedes in-repo docs.)
- Should `~/.dharma/audit/` content be regenerated into `dharma_swarm/docs/audits/`? (Currently audits live outside the repo, breaking discoverability.)
- Should the daily dashboard (Slot 6) be auto-generated by a cron job? (Cron daemon may itself be broken — chicken/egg.)
- Should `dharma_swarm/DHARMA_SWARM_MASTER_MAP.md` (codex's, root-violating) move to `_archive/`?

---

*This index is the locked shape of dharma_swarm onboarding as of 2026-05-07. The shape persists. The contents may change.*
