# CANONICAL DOC STACK

**Purpose:** Define which doc owns which kind of truth, and which surfaces an
agent reads first. This is the doc-ownership map. The single *door* into the
current operating state is the onboarding command, not this file:

```bash
make onboard
# or: python3 scripts/governance/agent_onboard.py
```

That command reads the owners below and renders the live truth in one screen.

---

## The Three-Layer SSoT Model

Every governance fact lives in exactly one of three layers:

| Layer | What it answers | Owner file | Decay protection |
|---|---|---|---|
| **Intent** | What are we working on right now? | [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) | CI gate + TTL + managed-block render |
| **Surface** | What exists in the codebase (routers, state dirs, nav)? | [`ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml) | Manifest Health API |
| **State** | What is live right now (HEAD, recent merges, runtime)? | [`docs/state/LIVE_OPS_DASHBOARD.md`](../state/LIVE_OPS_DASHBOARD.md) | Onboarding surfaces staleness as soft warning |

Everything else is **doctrine** (stable, prose-friendly: axioms, anti-slop
rules, AGENTOPS loops, architecture). Doctrine never claims live state;
live state never claims doctrine.

---

## First-Read Surfaces (max 5)

Earlier versions of this doc said "max 5 governance docs". That was wrong;
governance/ has more than 5 files and that is fine — most are doctrine.
The honest constraint is **max 5 first-read surfaces**: docs an agent must
ingest before any action. They are:

1. The onboarding command output (`make onboard`)
2. [`CLAUDE.md`](../../CLAUDE.md) — behavioural contract for coding agents
3. [`docs/governance/SWARM_GENOME.md`](SWARM_GENOME.md) — compact first-token map and claim-language guard
4. [`docs/governance/ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) — active build track
5. [`docs/governance/ANTI_SLOP_RULES.md`](ANTI_SLOP_RULES.md) — what not to do

Everything else in `docs/governance/`, `docs/doctrine/`, and `docs/architecture/`
is **depth-on-demand**. Read it when you need it. Do not memorise a read order.
`SOVEREIGN_MANIFEST.md` remains the deeper architecture/doctrine authority; it
is no longer a forced first-read surface.

---

## Ownership Map (what owns what)

| Kind of truth | Single owner | Who defers to it |
|---|---|---|
| Active build track (intent) | `ACTIVE_TRACK.yaml` | CLAUDE.md, SOVEREIGN_MANIFEST.md, BUILD_SESSION_ENTRYPOINT.md (rendered via managed blocks) |
| Declared surfaces (routers, state dirs, nav) | `ACTIVE_SURFACE_MANIFEST.yaml` | Manifest Health API, anti-slop allowlists |
| Live runtime / merge state | `docs/state/LIVE_OPS_DASHBOARD.md` | Daily Operating Brief, situational prose |
| Known breakage | `docs/state/BROKEN_REGISTER.md` | INTERFACE_MISMATCH_MAP.md (parallel substrate) |
| Behavioural contract (coding agents) | `CLAUDE.md` | — |
| Operational manual (Devin sessions) | `DEVIN.md` | Defers to `CLAUDE.md` on repo governance |
| Behavioural contract (cross-agent) | `AGENTS.md` (root), `docs/AGENTS.md` | — |
| First-token organism map / claim-language guard | `docs/governance/SWARM_GENOME.md` | Defers to owners for live state and doctrine |
| Reality debt / guarded overclaim language | `docs/governance/REALITY_DEBT_LEDGER.md` | Defers to source owners for claim upgrades |
| Runtime truth command cutover matrix | `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md` | Defers to RuntimeStateStore, spine modules, and tests for proof |
| Architecture / invariants / axioms | `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/doctrine/` | — |
| Doc ownership | `docs/governance/CANONICAL_DOC_STACK.md` (this file) | — |
| Anti-slop / repo-rule discipline | `docs/governance/ANTI_SLOP_RULES.md` + `.semgrep/dharma-anti-slop.yml` | — |
| Forge / Pudgala naming rule | `docs/governance/SOVEREIGN_MANIFEST.md` | `docs/governance/FORGE_NAMING_BOUNDARY.md` is reference-only and defers to the manifest |
| Vibe-code and AI-agent hygiene lifecycle | `docs/governance/hygiene/README.md` + `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md` + `docs/governance/hygiene/patterns/*.yaml` | `ANTI_SLOP_RULES.md` and `docs/ops/PR_REVIEW_CONTROL.md` when a pattern is promoted to a hard gate |
| Vibe-code antipattern catalogue (54 patterns × 12 clusters, scan-backed) | `docs/governance/VIBE_CODE_HYGIENE.md` + `scripts/governance/vibe_code_scan.sh` + `reports/governance/vibe_code_baseline_2026-06-07.txt` | `ANTI_SLOP_RULES.md` (companion); signals promote into enforced rules via PR |
| Semantic Commons agent identity and naming ontology | `docs/ontology/SEMANTIC_COMMONS.md` | A2A cards, contact registries, `docs/ontology/semantic_objects.yaml`, `docs/ontology/semantic_aliases.yaml`, runtime resolver names |
| Internal live transport decision | `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` | A2A docs, runtime plans, onboarding output, Live Ops Cockpit |
| LangGraph parity local acceptance contract | `docs/langgraph_parity/LANGGRAPH_PARITY_CONTRACT.md` | parity benchmark, readiness report, future adapter work |
| LangGraph parity operator runbook | `docs/langgraph_parity/OPERATOR_RUNBOOK.md` | benchmark/readiness commands and human verification flow |
| LangGraph parity task graph | `docs/langgraph_parity/TASK_GRAPH.md` | future parity adapter sequencing; defers to the acceptance contract |
| Living Agent Kernel build spec (holon lane) | `spec-forge/living-agent-kernel/MASTER_SPEC.md` | Defers to `dharma_swarm/operator_core/living_agent_kernel.py` + its tests for runtime truth |
| Terminal persistence substrate | `docs/ops/TMUX_AGENT_SUBSTRATE.md` | tmux launchers, VPS recovery plans, onboarding output, Live Ops Cockpit |
| Live ops cockpit workflow | `docs/ops/LIVE_OPS_COCKPIT.md` | dashboard cockpit route, operator-coherence report, operator travel/restart triage |
| PR coherence gate | `docs/governance/COHERENCE_DELTA.md` | PR template |
| PR review / merge-control operations | `docs/ops/PR_REVIEW_CONTROL.md` | Merge Master Mike workflows, PR janitor playbook |
| Merge authority charter (Merge Master Mike) | `docs/governance/MMM_CHARTER.md` | Defers to `docs/ops/PR_REVIEW_CONTROL.md` for operations and to `examples/agents/merge_master_mike.registration.json` for capabilities |
| Action warrant | `docs/governance/FOURFOLD_ACTION_WARRANT.md` | — |
| Cybernetic loop closure state | `CYBERNETIC_LOOP_MAP.md` | Generated from `scripts/governance/cybernetics_codex_audit.py --json`; per-loop packets defer to it for current closure verdicts |
| Cybernetics Codex operating protocol | `docs/agents/cybernetics_codex/PROTOCOLS.md` | Defers to Cybernetics Codex audit, `CYBERNETIC_LOOP_MAP.md`, and `reports/loop_closure/cybernetics_codex/` for live loop truth |
| Agent onboarding (ops) | `docs/ops/AGENT_ONBOARDING.md`, `docs/ops/CODEX_TOOLBELT_ONBOARDING.md` | — |
| Module-level what-does-what | `docs/architecture/NAVIGATION.md` | — |
| Router/TaskBoard domain pinning | `docs/architecture/ROUTERS_AND_TASKBOARD.md` | — |
| VentureCell portfolio (which cells exist, status, instrument, separation) | `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` | per-cell `VENTURE_CELL_*.md` declarations defer to it |
| Model / provider routing | `docs/architecture/MODEL_ROUTING_CANON.md` | root `MODEL_ROUTING_MAP.md` (archive pointer) |
| Memory Kernel production bar | `docs/architecture/MEMORY_KERNEL_PROD_BAR.md` | MemoryLattice, MemoryPalace, projection stores, canon/promotion claims |
| Perplexity Computer autonomous loop mode | `docs/agents/perplexity-computer/AUTONOMOUS_LOOP.md` | Perplexity Computer agent card loop-mode metadata and deployment notes |
| BoardStore facade / agent participation | `docs/architecture/SWARM_BOARDSTORE_SPEC.md` | — |
| Terminal protocol | `specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md` | v1.0 is archived |
| Constitutional rules | `specs/Dharma_Constitution_v0.md` | — |
| Kernel immutability | `specs/KERNEL_CORE_SPEC.md` | — |
| Foundations index | `foundations/INDEX.md` | Empirical-claims research and lodestone references |
| Lodestone index | `lodestones/README.md` | Lodestone seed discoverability |
| Onboarding megafile slots | `docs/MEGAFILE_INDEX.md` | individual slot files |
| Audit trail | `docs/governance/REPO_GOVERNANCE_AUDIT.md` | — |
| Work loops | `docs/governance/AGENTOPS.md`, `KAIZENOPS.md`, `DAILY_OPERATING_BRIEF.md`, `METABOLIC_CLOCK.md`, `HUMAN_YDS_LEDGER.md` | — |
| Cross-agent coordination | `docs/state/CROSS_AGENT_INVENTORY.md` | — |

If any file claims to own a fact already owned above, the rule is: **the file
in this table wins; the other file becomes a pointer.**

---

## Anti-Doc-Maze Rules

1. **Max 5 first-read surfaces.** Listed above. Adding a sixth requires removing one.
2. **One owner per fact.** Use the ownership map above. New facts pick exactly one home.
3. **No "single source of truth" claim** for something the ownership map gives to another file.
4. **Active state lives in YAML or live registers, not in prose.** Prose ages; YAML and registers are inspected by tools.
5. **Depth docs may live in `docs/governance/`, `docs/doctrine/`, `docs/architecture/`** — there is no cap on depth docs, but they are read on demand, never in a forced order.
6. **Stale archive within 2 weeks** of becoming stale (move to `docs/archive/` with a redirect).

---

## DocOps Lifecycle (before moving or deleting a doc)

1. **Inventory** — identify current claims, incoming links, replacement owner.
2. **Demote** — mark stale or historical docs with replacement and reason.
3. **Redirect** — update live links to the replacement owner.
4. **Archive** — move only after links and hardcoded paths are accounted for.
5. **Delete later** — remove only generated or duplicate material with no remaining authority or path dependency.

Documentation PRs should classify changed files as one of: `canon`, `ADR`,
`active_spec`, `working_plan`, `report`, `witness`, `reference`, `archive`,
or `experiment`.

---

## Frontmatter Policy

1. **Root governance docs** (this file, CLAUDE.md, README.md, SOVEREIGN_MANIFEST.md, ANTI_SLOP_RULES.md): NO frontmatter. Plain markdown. Maximum clarity.
2. **Architecture docs**: minimal frontmatter (title, date, status only — 5 lines max).
3. **Archive docs**: leave existing frontmatter in place.
4. **New docs**: no frontmatter unless consumed by a machine-readable pipeline.

If a Codex (GPT-5) or similar agent injects frontmatter into a Tier-1 doc,
strip it and move the metadata into `.codex/` or a sibling YAML file.

---

## Agent-Native Semantic Layer

AI-to-AI compressed language and emergent semantic ontologies are valid
research directions, but they are not canonical documentation or runtime
authority by default.

Allowed now:
- read-only extraction of repeated semantic patterns during doc cleanup;
- reports or plans that include a human-readable legend;
- round-trip experiments where compact agent messages expand back to clear
  English and cite source files.

Not allowed yet:
- opaque compact language controlling runtime behavior;
- new ontology schema created from clustering alone;
- hidden symbolic instructions that replace docs, gates, witnesses, or ADRs.

If a semantic pattern becomes load-bearing, promote it through an ADR or active
spec with tests or witness evidence.
