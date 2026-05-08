# Loomwork — Design Spec

**Created:** 2026-05-07
**Status:** Design draft, awaiting Dhyana review before plan
**Build base:** `dharma_swarm_truth_spine` worktree, new branch `feat/loomwork-venture-cell`
**External name:** Loomwork. Internal engine name `dharma_swarm` stays private.

---

## 1. What Loomwork IS (corrected, after adversarial verification)

Loomwork is an **outward-facing arm** of dharma_swarm — a sense organ that reaches into the world's data flows, atomizes records, cross-pollinates them across sources, and surfaces patterns no single human, journalist, or AI could see alone. It publishes those patterns as cited revelations on a public website.

It is **not** the spine. It is **not** the substrate. It is **not** the nervous system. It is an arm — peer to Shakti Ginko (financial arm), but pointed at world-pattern surfacing rather than wealth.

`ontology.py` already declares the frame: *"Palantir built this pattern for supply chains and kill chains. We take the engineering and reforge it for Jagat Kalyan."* Loomwork is the explicit operationalization of that line — Palantir-pattern engineering reforged to find what's broken in the world and put it where journalists, NGOs, regulators, and citizens can act.

## 2. Corrected architecture metaphor

Vertebrate-spine metaphor breaks at high resolution. The accurate topology is:

```
LAYER                      WHAT LIVES HERE
──────────────────────────────────────────────────────────────────────
1. CONSTRAINT KERNEL   →   DharmaKernel (25 SHA-256 axioms)
                           TelosGatekeeper (11 gates)
                           PolicyCompiler
                           Foundations Corpus (11 pillars)
                           WitnessLog
                           IdentityMonitor (TCS)
──────────────────────────────────────────────────────────────────────
2. TYPED SUBSTRATE     →   Ontology (object/link/action/security)
                           "not a feature, IS the platform" — ontology.py
──────────────────────────────────────────────────────────────────────
3. COORDINATION        →   SignalBus (loops feel each other)
                           Stigmergy (pheromone marks)
                           VSM Channels (Beer S1-S5)
──────────────────────────────────────────────────────────────────────
4. ORGANS              →   FractalRoom (composition primitive)
                           VentureCell (autonomy-laddered work-pursuit pattern)
                           AgentOps (safe execution gate)
                           Kaizen (continuous improvement)
──────────────────────────────────────────────────────────────────────
5. ARMS                →   Shakti Ginko VC (wealth — exists)
                           Loomwork VC  ← THIS BUILD (world-pattern)
                           JagatKalyanEngine (welfare reach)
──────────────────────────────────────────────────────────────────────
6. OUTPUTS             →   Operator Brief, daily_operating_brief
                           Public Astro site (NEW for Loomwork)
```

Loomwork lives at Layer 5. It depends on Layers 1-4 and emits to Layer 6.

## 3. Loomwork's Internal Composition

`LoomworkVentureCell` (registered in `telos_substrate.py` peer to Shakti Ginko) hosts five `FractalRoom`s of `RoomKind.OPERATIONS` (with one of `RoomKind.GOVERNANCE`):

| Room | Kind | Function |
|---|---|---|
| `CompassRoom` | GOVERNANCE | Telos-driven filter. Scores any candidate atom/feed against Jagat Kalyan fitness. |
| `ScoutRoom` | OPERATIONS | Autonomous feed-discovery from journalism citations, NGO supplements, court gaps, academic supplementary data. |
| `DemandRoom` | OPERATIONS | Periodic listening to NGO/journalist/defender output — surfaces "what they need that nobody shows them." |
| `GapRoom` | OPERATIONS | Finds high-suffering-signal × low-watcher-density domains. |
| `EvolutionRoom` | OPERATIONS | Singularity-claude pattern. Weekly. Scores other rooms' output against Jagat Kalyan fitness, evolves their adapters/heuristics. AgentOps-gated. |

Each room has Beer S1-S5 (per FractalRoom convention). Rooms communicate via SignalBus events (`SIGNAL_WORK_PACKET_*`, `SIGNAL_YDS_RATING_ADDED`, custom `SIGNAL_LOOM_REVELATION_PROPOSED`).

## 4. Atom and Connection Lifecycle (typed through Ontology)

Loomwork atoms are NOT just markdown files. They are **OntologyObj instances** with first-class types:

| Atom Kind | OntologyObj subtype | Wiki render |
|---|---|---|
| `event` | `WorldEvent` | `concepts/world/events/<slug>.md` |
| `entity` | `Entity` (extends existing ontology Entity) | `concepts/world/entities/<slug>.md` |
| `pattern` | `Pattern` | `concepts/world/patterns/<slug>.md` |
| `dot` | `Hypothesis` | `_staging/dots/<slug>.md` |
| `revelation` | `Revelation` | `concepts/world/revelations/<slug>.md` |
| `actor` | `Actor` | `concepts/world/actors/<slug>.md` |
| `dataset` | `DataSource` | `concepts/world/sources/<slug>.md` |
| `claim` | `Claim` | embedded in revelations |

Connections are **Link** instances (typed, bidirectional, auditable). Self-modification (Scout adding a feed, Evolution promoting a heuristic) goes through **ActionExec** records — auditable, reversible, telos-gated.

This is the Palantir pattern reforged. **Loomwork doesn't store data — it stores typed objects that the Ontology indexes and the Public Render reads.**

## 5. The Seven Spine Contracts (verifier-required)

Loomwork is an arm, but it must satisfy seven spine contracts. These add ~4-6h to the build but are non-negotiable:

1. **Boot-time kernel signature verify** — Loomwork imports `DharmaKernel.verify()` at module load; refuses to start if any axiom signature is invalid.
2. **Register publication gates as GateProposals** — the 7 Loomwork-specific gates (vulnerable-person / libel / citation-retrievability / disinformation / pramana / confidence-floor / staleness) register with `TelosGatekeeper` as `GateProposal` instances for S5 approval before going live.
3. **Witness every decision** to `~/.dharma/witness/loomwork/<YYYY-MM-DD>.jsonl` — every promote, every retract, every self-modification, every revelation publication.
4. **Inject Foundations Corpus** into every agent via `context.read_foundations()` before LLM calls. Loomwork agents reason inside the 11-pillar frame, not raw.
5. **Surface TCS to IdentityMonitor** — Loomwork's Telos Coherence Score gets reported alongside Shakti Ginko's, visible in the daily_operating_brief.
6. **VSM S1-S5 per room** — each FractalRoom honors the Beer convention (operations, coordination, control, intelligence, identity).
7. **Multi-evaluator promotion** per the Transcendence Principle — promoting a `dot` to `revelation` requires ≥3 decorrelated evaluators (different model families, different prompts) with quality-weighted aggregation. Otherwise the Krogh-Vedelsby diversity term drops to zero and revelations become Brier-bad.

## 6. Local Render (v0 — local-only, public deferred)

**SCOPE NOTE 2026-05-07:** v0 is **local-only**. No domain registration, no Cloudflare deploy, no DNS. Astro `dev` and `build` run on `localhost:4321` (or chosen port). Public deployment is deferred to v1 (post-launch decision after local proves itself).

- **Stack:** Astro static site, Obsidian-compatible markdown, served locally via `astro dev` (live reload) or `astro build` + `python -m http.server` for static preview
- **Render input:** `~/.dharma/knowledge/wiki_public/` — populated by `Publisher` agent reading the Ontology
- **Filters:** only atoms with `register: world` AND `public_y_n: true` AND telos-gate-passed render
- **Surfaces:** front page (mission + counts + latest 5), feed (chronological), atlas (topic-clustered), atoms graph (Obsidian-style cross-links), sources (transparency), methodology, submit (journalist threads), about
- **Deferred to v1:** RSS / JSON-feed / email digest / subscribe form / public domain / Cloudflare deploy / share-able URL — all wait until local proves the loom works
- **Demo path:** for partner briefings, screen-share or `ngrok http 4321` ad-hoc tunnel (no permanent public surface)
- **Updated by:** `Publisher` agent emits to wiki_public after Witness Gate clears; local Astro picks up via file watcher

## 7. Build Location & Sequencing

**Branch:** `feat/loomwork-venture-cell` off `dharma_swarm_truth_spine` HEAD.

Reasons:
- Truth_spine has the canonical spine docs (`LIVING_LAYERS.md`, `MASTER_BUILD_SPEC.md`, `FOUNDATIONS_TO_CODE_MAP.md`, `SOVEREIGN_MANIFEST`)
- Truth_spine has the full ontology family (decision_ontology, action_gateway, adapters, agents, hub, query, runtime)
- Truth_spine has `jagat_kalyan.py` AND `jk_stigmergy_seeds.py` already
- Truth_spine has `fractal/` package with `fractal_room.py`
- Truth_spine has `policy_compiler.py`, `identity.py`, `telos_substrate.py`

Building anywhere else means re-mounting these. **No port work. Compose with what's there.**

The merge of `truth_spine` + `feat/loomwork-venture-cell` to main becomes one unified narrative: *"the spine assembled itself, then the spine extended its first outward arm to serve the world."*

## 8. New Files & Edits

```
NEW (in feat/loomwork-venture-cell off truth_spine):
  dharma_swarm/loomwork/
    __init__.py
    venture_cell.py        ← LoomworkVentureCell (registers in telos_substrate)
    rooms/
      __init__.py
      compass.py           ← CompassRoom (Jagat Kalyan fitness scorer)
      scout.py             ← ScoutRoom + ScoutAdapter base + 5 source adapters
      demand.py            ← DemandRoom (NGO/journalist listener)
      gap.py               ← GapRoom (under-watched domain detector)
      evolution.py         ← EvolutionRoom (singularity-claude pattern)
    atoms/
      types.py             ← OntologyObj subtypes for each atom kind
      schema.py            ← YAML frontmatter spec
      lifecycle.py         ← dot → revelation promotion engine
    publisher/
      __init__.py
      render.py            ← Astro markdown emitter
      digest.py            ← RSS / email digest
      feeds.py             ← JSON-feed
    gates/
      __init__.py
      vulnerable_person.py
      libel.py
      citation.py
      disinformation.py
      pramana.py
      confidence.py
      staleness.py
    sources/                ← scrape / API adapters per source class
      __init__.py
      gfw.py
      carbon_mapper.py
      methanesat.py
      occrp_aleph.py
      opensanctions.py
      courtlistener.py
      climate_trace.py
      gfw_vessels.py
      acled.py
      ai_incident_db.py
      reliefweb.py
      base.py              ← ScoutAdapter base
    tests/
      ... mirror structure ...

  ~/.dharma/knowledge/wiki_public/   ← public render target (separate tree)
  ~/.dharma/witness/loomwork/        ← witness logs
  loomwork-site/                     ← Astro project (root of repo)

EDIT:
  dharma_swarm/orchestrate_live.py   ← add run_loomwork_loop (9th concurrent loop)
  dharma_swarm/telos_substrate.py    ← register LoomworkVentureCell
  dharma_swarm/insight_brief.py      ← consume Loomwork revelations
  dharma_swarm/agent_runner.py       ← add ProviderType.GLM5_FREE_TIER if not present
  ~/bin/wiki                         ← add `wiki publish` subcommand
  ~/.claude/cabinet/ARJUNA.md        ← reference this design doc
  CLAUDE.md (truth_spine)            ← document Loomwork as next user-visible seam
```

Estimate: ~3,500 LOC across 30+ modules. Most reuse existing primitives (FractalRoom, VentureCell, Ontology, SignalBus, TelosGatekeeper). Only ~600 LOC is genuinely new logic; rest is composition + adapters + tests.

## 9. Data Flow

```
SCOUT polls source → raw record fetched
   ↓
ATOMIZER converts record → OntologyObj instance (typed)
   ↓
ONTOLOGY.register(obj) → typed object stored, indexed
   ↓
LINKER.scan(new_obj) → candidate Links proposed (cites/contradicts/same-actor/etc)
   ↓
SignalBus emits SIGNAL_ATOM_CREATED
   ↓
PATTERN agent (cron, 6h) → reads recent atoms, finds dots (≥3 corroborating, ≥2 sources)
   ↓
SignalBus emits SIGNAL_DOT_PROPOSED
   ↓
COMPASS scores dot against Jagat Kalyan fitness
   ↓
If score > threshold: REVELATION agent (multi-evaluator) drafts narrative
   ↓
WITNESS GATE (7 telos gates) reviews
   ↓
If all pass: PUBLISHER renders to wiki_public/, Astro rebuilds
   ↓
ALGEDONIC FEEDBACK: external readers flag inaccuracies → retraction queue
   ↓
EVOLUTION ROOM (weekly cron): scores, evolves Scout adapters, retires stale feeds
```

## 10. Error Handling & Safety

- **Spine contract violation** → Loomwork refuses to boot
- **Telos gate fail** → revelation goes to retraction queue, witnessed
- **Multi-evaluator disagreement** → dot remains a dot, doesn't promote
- **Algedonic signal from external reader** → revelation auto-retracted pending review
- **Self-modification proposal from EvolutionRoom** → AgentOps gates it before any code change
- **Vulnerable-person gate** → hard stop, never publishes; logs the close-call
- **Cost overrun** → CostTracker triggers GuardianCrew alert, Loomwork loop pauses
- **Stigmergy poisoning** (upstream source manipulated) → confidence-floor gate catches it

## 11. Testing

- Unit: each gate, each adapter, each atom-kind serialization
- Integration: SCOUT → ATOMIZE → LINK round-trip with mock source
- End-to-end: 3 hand-crafted revelations rendered through full pipeline
- Adversarial: synthetic disinformation injection — does the disinformation gate catch it?
- Multi-evaluator: same dot scored by GLM-5 + Haiku + Sonnet — Brier consistency check
- Witness-log integrity: every promote/retract appears in `~/.dharma/witness/loomwork/`
- Spine-contract compliance: pytest checks all 7 contracts at module load

## 12. The 14-Day Ship Plan (adjusted, +4-6h for spine contracts)

| Day | Action | Output |
|---|---|---|
| 1 | Branch `feat/loomwork-venture-cell` off truth_spine · scaffold `dharma_swarm/loomwork/` package · register LoomworkVentureCell in telos_substrate · register 7 GateProposals · register witness path | Boot test passes |
| 2 | First 3 Scout adapters (GFW DIST-ALERT, Carbon Mapper, Climate TRACE) · OntologyObj subtypes for event/entity/pattern | Atoms ingest |
| 3 | Linker prototype · 50 atoms ingested · pattern detector v0 | Atom corpus growing |
| 4 | Add OCCRP Aleph + OpenSanctions adapters · CompassRoom Jagat Kalyan fitness scorer (v0 simple heuristic) | 5 sources, 200+ atoms |
| 5 | Hand-craft Revelation 1 (Methane-Award Paradox) · Astro project scaffold · render home page LOCALLY | Local site has 1 revelation, viewable at localhost:4321 |
| 6 | GFW vessels + AI Incident Database adapters · hand-craft Revelation 2 · multi-evaluator wired | 7 sources, 2 revelations, decorrelated eval working |
| 7 | Mid-week status check · all 7 spine contracts test-passing · TCS reporting to IdentityMonitor | Go/no-go on Day-14 timeline |
| 8 | Hand-craft Revelations 3-5 · all 7 telos gates wired and tested | All 5 revelations rendered |
| 9 | CourtListener + ACLED + ReliefWeb adapters · cross-pollination quality pass | 10 sources |
| 10 | Submit form (local) · transparency page · methodology page | Local surface complete |
| 11 | First end-to-end demo to Dhyana — full local walkthrough — gather feedback | Local demo passes |
| 12 | EvolutionRoom v0 · first AUTONOMOUS revelation candidate proposed by engine · Witness gate review | Engine-generated revelation queued |
| 13 | Final spine-contract audit · final telos-gate audit · last bug fixes | Site locally complete |
| 14 | **LOCAL LAUNCH** — Loomwork v0 running on localhost, fully functional, first autonomous engine-generated revelation rendered. **No public deployment yet.** Decision gate for v1 (public domain + Cloudflare): does the local prove the loom works? | Loomwork v0 local-live |

## 13. Decision gates

**Day-14 (local v0):** if the engine has not autonomously generated a revelation that passed all 7 telos gates by 2026-05-21, extend by 7 days but do NOT add features. Hard stop on scope creep.

**v0 → v1 gate (post Day-14):** after local proves out, decide whether to (a) register domain + Cloudflare-deploy public, (b) keep local-only and expand sources/quality first, (c) reframe scope. Decision criteria: does the local engine's revelation queue pass adversarial review by ≥1 external trusted reader (Bellingcat / OCCRP / a friendly investigative journalist)? If yes → public. If no → improve locally.

## 14. Open questions deferred to writing-plans

- Concrete `JagatKalyanFitness` formula (V0 = simple heuristic; v1 needs the canonical spec)
- Astro vs Quartz final pick (Astro recommended for control, Quartz already Obsidian-native)
- ~~Domain registration~~ → **DEFERRED to v1** per Dhyana directive 2026-05-07; v0 is local-only
- ~~Fiscal sponsor / 501(c)(3) wrap~~ → DEFERRED to v1
- Multi-evaluator provider mix — V0 uses GLM-5 + Haiku; production needs cross-family

---

## Spec self-review

- ✅ No TBD or TODO placeholders in load-bearing sections
- ✅ Internal consistency: architecture metaphor matches feature descriptions
- ✅ Scope: focused enough for one implementation plan; the 14-day ship is one cohesive arc
- ✅ Ambiguity: where ambiguous (Astro vs Quartz, fitness formula v0), explicitly deferred to plan or noted as v1 work
- ✅ All 7 spine contracts named with implementation paths
- ✅ Build location verified by reading truth_spine contents
- ✅ Path-precise file plan with LOC estimate

---

*This design is the corrected version after two adversarial verifiers found that the parent agent's earlier "spine" claim conflated layers. Loomwork is an arm — outward-reaching, world-pattern-surfacing, peer to Shakti Ginko. The spine is the kernel + gates + policy + foundations + witness + identity. The substrate is the Ontology. The composition is FractalRoom. The arm reaches outward and brings back atoms. The world reads what the witness gates approve.*
