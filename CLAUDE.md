# dharma_swarm — Claude Code Configuration

## Before Anything Else — the single remembered gate

If you have not run `make onboard` this session, do it now — before any non-trivial Read, Grep, or Edit. It renders the current operating reality and the code-structure tools you should reach for before grep.

`make onboard` is the only command you need to remember. Everything else
(active track, live ops, broken register, axioms, tooling hints, depth
pointers) is rendered from the existing owners by that command:

```bash
make onboard
# or: python3 scripts/governance/agent_onboard.py
```

If this file disagrees with that output on anything live (track id, prereqs, recent commits), trust the onboarding output. This file owns behaviour; the onboarding command surfaces state.

<!-- ACTIVE_TRACK:START -->

<!-- This block is generated from docs/governance/ACTIVE_TRACK.yaml.
     Do not hand-edit. Run scripts/governance/render_active_track_includes.py
     after updating the YAML. -->

**Active portfolio:** 11 co-equal track(s) (WIP warn 11, max 11). A new project is a new track here, not a violation — model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned.

**Spine objectives (each track serves one):**

- `substrate-nativeness` — Substrate nativeness — runtime flows through the ontology/spine, not around it (covered)
- `revenue-external-humans-served` — Revenue & external humans served — value leaves the house and someone acts on it (covered)
- `research-depth` — Research depth — the contemplative-mechanistic bridge (R_V, geometric lens) deepens (covered)

### Runtime Truth Reconciliation — operator-visible truth packets

**Track id:** `runtime-truth-reconciliation-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-04 (TTL 14 days)
**Relations:** complements: runtime-truth-nats-2026-06
**Owns surfaces:** dharma_swarm/operator_core/**, scripts/governance/agent_onboard.py, dharma_swarm/runtime_state.py
**Moves vital signs:** quality_gates, memory_persistence

The Runtime Truth Spine substrate is merged and shippable. This track moves
from substrate existence to read-only reconciliation: operator-visible
runtime truth packets that separate heartbeat, readiness, artifact progress,
completion, authority, projection/cache, mutation, and external-gated proof.

The track must not create a new truth store, daemon, receipt system, or
authority surface. It projects from existing owners only:
spine.EvidenceReceipt for in-flight dispatch proof, runtime_state.RuntimeReceipt
for persisted runtime receipts, IdempotencyRecord for exactly-once substrate,
and existing operator/onboard/control-surface rows for read-only rendering.

Doctrine line that must hold:
  Read models project truth from owners; they do not become authority.

**Next items:**

- [code] (blocker) Define the smallest read-only RuntimeTruthPacket contract in the existing operator_core owner.
- [code] (blocker) Render compact runtime truth in make onboard without making onboard an authority surface.
- [test] Protect A2A single-persistence invariant while adding runtime truth projections.

**Non-goals:**

- Do not create a new daemon, database, event log, truth store, or receipt system.
- Do not mint a second RuntimeReceipt for A2A or paths with an inner runtime owner.
- Do not mutate external systems, live processes, archive fitness, payments, or gateways.
- Do not broadly refactor orchestrator.py, agent_runner.py, swarm.py, providers.py, or SwarmManager.
- Do not build Verified Experiment Loop runtime in this track.
- Do not create standalone BetCard, Experiment, SwarmRun, DecisionRecord, LineageRecord, WikiUpdate, or cost-tracker classes.

### Runtime Truth NATS — internal live transport for A2A dispatch

**Track id:** `runtime-truth-nats-2026-06` · **Status:** ACTIVE · **Owner:** @codex
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-07 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06
**Owns surfaces:** docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md, dharma_swarm/a2a/a2a_nats_contact.py, dharma_swarm/a2a/a2a_core_contact.py
**Moves vital signs:** tool_coverage

The concurrent Codex transport lane. NATS was scoped out of the global
prohibition by the 2026-05-31 doctrine amendment and runs as a concurrent
scoped track with non-overlapping surfaces (transport layer only). This
track wires the internal live transport so A2A dispatch can travel at
broker speed, distinct from the reconciliation lane's read-model surfaces.

Surface separation is the safety boundary: this track owns the NATS
transport contact modules and the master spec; it does not touch the
operator_core read models the reconciliation lane owns.

**Next items:**

- [code] Confirm NATS transport contact modules are wired and receipted end-to-end.

**Non-goals:**

- Do not introduce Redis or gRPC as part of this track.
- Do not touch the operator_core read-model surfaces owned by the reconciliation lane.
- Do not add a parallel spine-check CI workflow.

### Runtime Truth Spine — Adoption (god objects flow through invoke_agent)

**Track id:** `runtime-truth-spine-adoption-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-10 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06, runtime-truth-nats-2026-06
**Owns surfaces:** dharma_swarm/spine/**, dharma_swarm/a2a/a2a_bridge.py, dharma_swarm/orchestrator.py, dharma_swarm/agent_runner.py, docs/agent_tasks/2026-06-14_runtime_spine_hardening_goal.md, scripts/uplift_guards/check_spine_ownership.py
**Moves vital signs:** quality_gates, tool_coverage

spine-adoption ships end-to-end: every production dispatch flows through
invoke_agent() and emits exactly one EvidenceReceipt. This track migrates
the god objects (agent_runner.py, orchestrator.py, a2a_bridge.py) onto
the shipped spine substrate. Target: 3 production callers outside the
spine package, zero bypass paths. Substrate-nativeness moves toward 30%+.

Ported 2026-06-10 from the v1 declaration (opened 2026-06-06 on the
qwen/spine-adoption lane, commit c28951d5b, which closed reconciliation
in v1) into the v2 portfolio while merging origin/main. In the v2
multi-track model it runs as a co-equal peer of the reconciliation and
NATS lanes rather than requiring their closure; reconciliation's open
status is main's standing declaration and is left to the operator.

Runtime-only audit baseline, 2026-06-14 JST:
  Baseline production-readiness score: 54/100; current hardening score
  is tracked in hardening_status above.
  Rejected claim: 88/100 production-ready.
  The spine has useful live pieces, but it is not yet the coherent,
  default, governed runtime substrate for the whole repo. Score movement
  now requires hardening evidence: bypass drainage, default dispatch
  adoption, receipt saturation, live bridge/process agreement, and
  operator-surface honesty.

**Next items:**

- [runtime] (blocker) Prove one daemon/default dispatch run with DHARMA_SPINE_DISPATCH=1 lands a fresh EvidenceReceipt and scoped runtime receipt coverage.
- [code] (blocker) orchestrator.py dispatch through invoke_agent behind DHARMA_SPINE_DISPATCH (landed via #557; operator confirms one live EvidenceReceipt on a real dispatch = GATE 1).
- [code] (blocker) Migrate agent_runner.py run_task through invoke_agent(). Largest surface, last.
- [governance] (blocker) Promote the zero-bypass allowlist state into uplift guard enforcement without weakening NATS/runtime ownership checks.
- [docs] Author docs/architecture/SPINE_ADOPTION_NARRATIVE.md
- [runtime] (blocker) Run the 54/100 Runtime Spine Hardening long goal and raise the score only through executable gates.

**Non-goals:**

- Do not create new spine sub-modules. Adopt invoke/receipt/routing/persistence.
- Do not decompose agent_runner.run_task beyond invoke_agent() routing.
- Do not change EvidenceReceipt schema; adopt shipped types unchanged.
- Do not introduce NATS, Redis, or gRPC in this track (transport belongs to the NATS lane).
- Do not broadly refactor swarm.py, providers.py, or SwarmManager.

### Cybernetic Loop Closure — wire all 13 loops with receipted closure checks

**Track id:** `loop-closure-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-11 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06
**Owns surfaces:** reports/loop_closure/**, CYBERNETIC_LOOP_MAP.md
**Moves vital signs:** quality_gates, eval_coverage

Operator-instructed campaign (2026-06-11 master prompt): wire all 13
cybernetic loops in CYBERNETIC_LOOP_MAP.md until each runs
sense->interpret->constrain->act->adapt on real data with receipts to
its declared owner surface and an automated closure check.

Phase 0 (research dossier, no build code) ships first. Phases proceed
in dependency-lattice order: Loop 1 trunk (provider chain + dispatch),
then the fed cascade (6,2,5,9 -> 3,4,7 -> 8,10,11), then Loops 12/13
gated behind the One Wire external-receipt quorum (N>=5, M>=3).

Invariant that must hold throughout:
  Internal artifacts never touch archive fitness; only countersigned
  external acted receipts above quorum do.

**Next items:**

- [code] (blocker) Phase 1a: provider chain hardening — separate failure state classes, fallback ordering, honest smoke receipts (no real key required).
- [ops] (blocker) Operator escalation: one real provider key (OPENROUTER recommended) to close Loop 1.
- [code] Phase 1b: Loop 1 closure under orchestrate_live with DHARMA_SPINE_DISPATCH=1, dispatch_dropoff receipted, closure check in make orient.

**Non-goals:**

- Do not weaken, bypass, or hard-code any telos gate to close a loop.
- Do not let internal artifacts touch archive fitness (One Wire quorum stands).
- Do not touch the operator_core read-model surfaces owned by the reconciliation lane.
- Do not commit provider API keys or any credentials.
- Do not create a new truth store, receipt system, or state owner; extend loop_supervisor and existing owners.

### Orientation Graph — whole-system view served on token one

**Track id:** `orientation-graph-2026-06` · **Status:** ACTIVE · **Owner:** @devin
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-11 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06
**Owns surfaces:** scripts/governance/orientation_graph.py, tests/test_orientation_graph.py
**Moves vital signs:** quality_gates

Operator directive 2026-06-11: any agent must see the whole system at
once — identity (why), organs, active tracks, canon custody, liveness,
and the broken register — in ~10 seconds, not by grepping prose. This
track delivers that as a single read-only orientation view.

The track creates NO new truth store and NO authority surface. It
projects from the existing owners only: foundations/THE_ORGANISM.md
and docs/vision_maps/NORTH_STAR.md (identity),
docs/governance/VENTURE_CELL_PORTFOLIO.yaml (organs),
docs/governance/ACTIVE_TRACK.yaml (tracks),
docs/docops/assertions.yaml canonical_guard.registered + the worktree
(custody), the live ops census receipt (liveness), and
docs/state/BROKEN_REGISTER.md (broken).

Doctrine line that must hold (same as the reconciliation lane's):
  Read models project truth from owners; they do not become authority.

The one-section identity hook added to agent_onboard.py (a surface the
reconciliation lane owns) was done under explicit operator instruction
2026-06-11, is read-only pointers, and does not touch that lane's
runtime-truth rendering or non-goals.

**Next items:**

- [code] Graph-shaped queries (organ -> tracks -> surfaces -> liveness edges) over the same owners, still read-only.
- [test] Measure time-to-orientation for a fresh agent (target <10s) and record the receipt.

**Non-goals:**

- Do not create a new daemon, database, vector store, event log, or truth store.
- Do not mutate owner files; the view writes nothing.
- Do not duplicate make onboard's state rendering; this is the why/shape layer, onboard remains the state layer.
- Do not touch operator_core/** or runtime_state.py.

### Composer Holon Spine Longrun — fable/codex pair over verified command receipts

**Track id:** `composer-holon-spine-longrun-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-11 (TTL 14 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06, runtime-truth-nats-2026-06 · depends_on: runtime-truth-spine-adoption-2026-06
**Owns surfaces:** docs/sovereign_holons/**, reports/sovereign_holons/**, dharma_swarm/holon_*.py, scripts/holon_*.py, tests/test_holon_*.py
**Moves vital signs:** quality_gates, tool_coverage, memory_persistence

Build A from the composer convergence: merge Verified Composer Command
Spine v1 with the Sovereign Holon Orchestrator target, bringing
fable_composer and codex_composer up as the first read-only composer
holon pair. The track is active as a scoped longrun lane, not as a new
receipt owner. Command receipts are projections of spine.EvidenceReceipt.

The clean GitHub-main mirror remains the merge target; the active build
lane currently lives on qwen/spine-adoption because that lane contains
the holon docs, modules, and verifier tests. The lane must reconcile back
to main through the normal review path before it is called shipped.

**Next items:**

- [test] (blocker) Run the frozen Build A verifier set and publish the exact output in convergence.
- [runtime] (blocker) Prove one unattended fable_composer wake and one unattended codex_composer wake with fresh state files and EvidenceReceipt-profile command receipts.
- [code] (blocker) Merge living_agent_kernel source choice and prove import green.
- [governance] (blocker) Reconcile the holon substrate lane back to GitHub main after verifier green.

**Non-goals:**

- Do not create a new durable receipt store; project over spine.EvidenceReceipt.
- Do not send outreach, deploy, push, or open PRs in this track without a later explicit lease.
- Do not claim unattended 90% confidence until fable and codex both leave fresh wake receipts.
- Do not merge holon substrate to main without the frozen verifier runbook passing.

### AgentAdmission + Semantic Commons — one door for agent identity and naming

**Track id:** `agent-admission-semantic-commons-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-14 (TTL 14 days)
**Relations:** complements: cybernetics-codex-stewardship-2026-06
**Owns surfaces:** docs/ontology/**, docs/ops/AGENT_ADMISSION.md, dharma_swarm/semantic_commons.py, dharma_swarm/engine/hybrid_retriever.py, dharma_swarm/context.py, scripts/governance/agent_admission*.py, scripts/governance/name_drift*.py, tests/test_agent_admission*.py, tests/test_semantic_commons*.py, tests/test_hybrid_retriever.py
**Moves vital signs:** quality_gates, memory_persistence

Operator directive 2026-06-14: promote AgentAdmission and the Semantic
Commons from discussion into an official track. The track creates the
single admission path for any new persistent agent and the living semantic
object/alias index used to prevent name drift.

Canonical intent:
  AgentAdmission is the full lifecycle for a new swarm/fleet identity.
  Semantic Commons is the typed, versioned naming surface agents update
  as they build, without pretending the ontology is final.
  SessionOrientation is the layered L0-L4 loading contract that keeps
  agents from paying broad-search context costs before route selection.

**Next items:**

- [docs] (blocker) Create docs/ontology/SEMANTIC_COMMONS.md with lifecycle states: seed, working, preferred, canonical, deprecated, forbidden.
- [docs] (blocker) Create semantic_objects.yaml and semantic_aliases.yaml with AgentAdmission, RegistrationDesk, AgentSeed, LivingDock, A2ACard, NameDriftPreflight, and SessionOrientation.
- [code] (blocker) Add one `dgc agent admit`/`make agent-admit` path or a documented shim that does not collide with make onboard semantics.
- [test] (blocker) Add tests proving aliases catch hyphen/underscore/name-drift collisions.
- [docs] (blocker) Generate read-only Obsidian/PKM Semantic Commons projections with Bases dashboard views.
- [docs] (blocker) Add retrieval scoping contract proving structure-first recall before lexical/vector/graph search.
- [code] (blocker) Wire Semantic Commons scope metadata into HybridRetriever runtime evidence.

**Non-goals:**

- Do not overload `make onboard`; it remains session/governance orientation.
- Do not hard-freeze the ontology; use lifecycle states for terms.
- Do not admit agents without a name-drift preflight and a receipt.
- Do not bypass existing registration desk or living-agent owner surfaces.

### Cybernetics Codex Stewardship — permanent owner for loop ecology

**Track id:** `cybernetics-codex-stewardship-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `research-depth` · **Verified at:** 2026-06-14 (TTL 14 days)
**Relations:** complements: agent-admission-semantic-commons-2026-06 · depends_on: loop-closure-2026-06
**Owns surfaces:** docs/ops/CYBERNETICS_CODEX.md, docs/agents/cybernetics_codex/**, dharma_swarm/cybernetics_codex.py, scripts/governance/cybernetics_codex_audit.py, scripts/governance/register_cybernetics_codex.py, tests/test_cybernetics_codex.py, reports/loop_closure/cybernetics_codex/**
**Moves vital signs:** quality_gates, eval_coverage, memory_persistence

Promotes cybernetics_codex from a local loop-closure helper into an
official stewardship track. The steward owns the operational cybernetics
layer: loop closure claims, VSM/cybernetic mapping, receipt freshness,
multi-loop interference review, and closure-verifier discipline.

This track does not close the 13 loops itself. It creates the persistent
technician/holon seat that keeps cybernetics from decaying back into a
metaphor.

**Next items:**

- [docs] (blocker) Write the admission receipt packet under reports/loop_closure/cybernetics_codex/.
- [runtime] (blocker) Prove one fresh cybernetics_codex audit from a clean context and record the runtime heartbeat receipt.
- [governance] Add the steward to the future AgentAdmission path once that track lands.

**Non-goals:**

- Do not grant write authority over loop hot paths without a later build track.
- Do not weaken telos gates to make a loop look closed.
- Do not treat a declared NATS card as a running subscriber.
- Do not duplicate runtime_state, witness, or active-track authority.

### TELOS AI Morning Refinery — user-facing semantic refinery seed

**Track id:** `telos-ai-morning-refinery-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `revenue-external-humans-served` · **Verified at:** 2026-06-14 (TTL 14 days)
**Owns surfaces:** docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md, docs/vision_maps/TELOS_MORNING_REFINERY_V0.md, docs/research/telos_ai/**, PRODUCT_SURFACE.md, dashboard/src/app/dashboard/telos*/**, dashboard/src/components/telos*/**, tests/test_telos*.py
**Moves vital signs:** eval_coverage, cost_efficiency

Promotes the TELOS AI seed and Morning Refinery lane into the portfolio
as the user-facing product/revenue bridge. The track is still design and
evidence work: no live external account action, no raw private material
promotion, and no product claims before receipts.

The product hypothesis: a morning-page-to-semantic-refinery loop that
helps one human turn private dharma signals into corrected vectors,
bridge candidates, venture seeds, and consent-gated public artifacts.

**Next items:**

- [test] (blocker) Write the consent/privacy boundary test before any product implementation.
- [code] (blocker) Create a narrow dashboard or CLI prototype that reads only sanitized example packets.
- [docs] (blocker) Define the first external acted receipt format for TELOS without spend or account action.

**Non-goals:**

- Do not process private user material into repo artifacts without explicit consent.
- Do not send outreach, charge money, or touch live external accounts in this track.
- Do not build a generic journaling app.
- Do not claim product-market or revenue proof without acted external receipts.

### Helm Worldclass Terminal — operator TUI integration and verification lane

**Track id:** `helm-worldclass-terminal-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-14 (TTL 14 days)
**Owns surfaces:** terminal/**, docs/TERMINAL_TUI_TMUX_HARNESS_2026-04-02.md, docs/plans/2026-04-02-terminal-*.md, reports/terminal/**
**Moves vital signs:** quality_gates, tool_coverage

Promotes the high-activity Helm terminal work into an official track so
terminal UI changes stop living as a large invisible branch. The track
owns operator-facing TUI polish only when backed by golden frames, compact
viewport checks, and live tmux receipts.

**Next items:**

- [docs] (blocker) Collect the current Helm branch diff into a closeout packet with exact tests and screenshots/terminal captures.
- [governance] (blocker) Either split the branch into reviewable PRs or state the large-diff exception with receipts.

**Non-goals:**

- Do not change runtime providers, agent dispatch, or receipt semantics.
- Do not ship cosmetic changes without golden-frame and compact-terminal checks.
- Do not leave terminal branch work outside the active-track surface.

### A2A Cloud-Agent Bridge — cloud reasoners onto the NATS substrate

**Track id:** `a2a-cloud-agent-bridge-2026-06` · **Status:** ACTIVE · **Owner:** @codex_composer
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-14 (TTL 14 days)
**Relations:** complements: agent-admission-semantic-commons-2026-06
**Owns surfaces:** docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml, docs/architecture/A2A_CLOUD_BRIDGE.md, dharma_swarm/a2a/a2a_cloud_contact.py, dharma_swarm/a2a/contact_registry.py, dharma_swarm/a2a/verifier.py, reports/state/a2a_score_denominator.md, tests/test_a2a_cloud_contact.py
**Moves vital signs:** tool_coverage, memory_persistence

Promotes the proposed cloud-agent bridge into the active portfolio. The
track extends the local A2A/NATS contact pattern so cloud-resident agents
like perplexity-computer and Devin can enter the same message contract
without manual operator copy/paste transport.

This is transport-only. It must not create a second task format, a second
receipt owner, or a live public ingress without explicit operator approval.

**Next items:**

- [docs] (blocker) Write the architecture ADR and threat model before implementation.
- [test] (blocker) Implement a local-only round-trip test with no public ingress or external accounts.

**Non-goals:**

- Do not expose public ingress, spend, or live external accounts in this track.
- Do not change invoke_agent or the spine receipt contract.
- Do not create a perplexity-specific message format.
- Do not mark cloud agents live until liveness is receipted by the same verifier class as local agents.

**Recently closed tracks:**

- `runtime-truth-spine-2026-06` — Runtime Truth Spine — one invariant, one invocation path, one receipt (SHIPPED, closed 2026-06-04)
- `trace-identity-coverage-2026-05` — Trace Identity Coverage — native propagation and soft coverage findings (SUPERSEDED, closed 2026-05-28)
- `trace-attractor-causal-spine-2026-05` — Trace Attractor Causal Spine — operator-visible trace packets (SHIPPED, closed 2026-05-21)

For machine-readable status, see [`reports/governance/active_track_evidence.md`](reports/governance/active_track_evidence.md) (generated by `scripts/governance/check_track_status.py`).

<!-- ACTIVE_TRACK:END -->

## Behavioral Rules (Always Enforced)

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested
- NEVER save working files, text/mds, or tests to the root folder
- Never continuously check status after spawning a swarm — wait for results
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- BEFORE opening any PR that closes / demotes / adds a BR-id, ALWAYS run `gh pr list --state open --search "BR-NNN"` for each cited BR-id. If another open PR cites the same id, coordinate (rebase / split / close-as-redundant) before pushing. The `pr-collision-detect` workflow is an after-the-fact safety net, not a substitute for this check. See `docs/governance/COHERENCE_DELTA.md` § Pre-flight check.
- **Worktree budget (enforced 2026-06-18):** open git worktrees must be ≤ active-track count (`docs/governance/ACTIVE_TRACK.yaml`) + 1 canonical tree + ≤2 TTL-tagged scratch. Every non-canonical worktree maps to an active track; excess/unmapped worktrees are a governance violation — compost the branch list to `~/.claude/cabinet/_compost/` first, then `git worktree remove`. Replaces the fixed 24-lane law.
- **Naming / identity SSOT = Semantic Commons (`docs/ontology/`).** Resolve any concept / agent / object name against `docs/ontology/semantic_objects.yaml` (26 objects) + `docs/ontology/semantic_aliases.yaml` (143 aliases, 9 forbidden) BEFORE inventing a name. `docs/ontology/SEMANTIC_COMMONS.md` is the contract; `scripts/governance/name_drift_preflight.py` is the checker; the `api_name` grammar is ADR-008 (PROPOSED — needs ratification). Do NOT create parallel naming schemes — that drift is what Semantic Commons exists to kill.
- **Runtime receipts never enter git.** `reports/a2a/*_receipts/`, `reports/model_*/e2e/` are loop-generated artifacts → `.gitignore`, write under `~/.dharma/` ideally. (2026-06-18: 20,898 stray receipts were blocking deploy.)

## File Organization

- NEVER save to root folder — use the directories below
- Use `dharma_swarm/` for Python source code
- Use `tests/` for test files (one test file per module: `test_foo.py` tests `foo.py`)
- Use `docs/` for documentation and markdown files
- Use `scripts/` for operator utilities and shell scripts
- Use `api/` for FastAPI routers and backend code
- Use `dashboard/` for Next.js frontend code

## Project Architecture

- Python 3.11+, Pydantic 2, async-first (aiosqlite, aiofiles)
- Follow Domain-Driven Design with bounded contexts
- Keep files under 500 lines
- Use typed interfaces for all public APIs
- Use `pytest-asyncio` with `asyncio_mode = "auto"` for testing
- Ensure input validation at system boundaries

### Key Abstractions

- **Organism** (`dharma_swarm/organism.py`): The living system. VSM, identity, memory, router, strange loop, attractor.
- **SwarmManager** (`dharma_swarm/swarm.py`): Top-level coordinator. Agent pool, task board, orchestrator.
- **DarwinEngine** (`dharma_swarm/evolution.py`): Self-improvement via gated evolution.
- **LoopEngine** (`dharma_swarm/cascade.py`): F(S)=S universal convergence loop across 5 domains.
- **DharmaKernel** (`dharma_swarm/dharma_kernel.py`): 25 immutable axioms (SHA-256 signed).
- **MemoryKernel** (`dharma_swarm/memory_kernel/`): Canonical front door for agent memory context; legacy MemoryPlane, RuntimeState facts, MemoryPalace, MemoryLattice, vector, graph, log, and wiki stores are subordinate sources, adapters, projections, or promotion feeds.
- **TelosGatekeeper** (`dharma_swarm/telos_gates.py`): 11 dharmic safety gates.
- **StigmergyStore** (`dharma_swarm/stigmergy.py`): Pheromone-trail coordination.
- **CatalyticGraph** (`dharma_swarm/catalytic_graph.py`): Autocatalytic set detection (Tarjan SCC).
- **StrangeLoop** (`dharma_swarm/strange_loop.py`): Organism self-modification engine.

## The Transcendence Principle (Engineering Axiom)

**The claim**: Diverse competent agents, with decorrelated errors and quality aggregation, provably outperform any individual agent. This is not aspirational — it is proven mathematics (Zhang et al., NeurIPS 2024; Condorcet 1785; Krogh-Vedelsby 1995; Breiman 2001).

**The mechanism**: When multiple experts each make correct decisions on their specialties but make different errors elsewhere, a system that learns the mixture distribution and concentrates toward high-confidence outputs (low-temperature sampling, majority voting, quality-weighted aggregation) will exceed every individual expert. The errors cancel. The knowledge compounds.

**Three modes of transcendence** (Abreu et al. 2025):
1. **Skill denoising** — filtering idiosyncratic errors across agents
2. **Skill selection** — routing to the best agent per sub-problem
3. **Skill generalization** — recombining capabilities beyond any single agent

**Three necessary conditions** (all must hold, or transcendence fails):
1. **Diversity of competence** — agents must have genuinely different capabilities, trained on different data, using different approaches. Same model prompted differently may NOT suffice. Different model families, different specializations, different error profiles. Measured via MAP-Elites behavioral diversity (`diversity_archive.py`).
2. **Error decorrelation** — agent errors must be independent. If agents fail on the same inputs in the same way, aggregation provides no benefit. Correlated errors compound; decorrelated errors cancel. This is arithmetic: `E_ensemble = E_mean - E_diversity` (Krogh-Vedelsby). The diversity term directly subtracts from ensemble error.
3. **Quality aggregation** — the mechanism that combines agent outputs must amplify agreement and suppress noise. Temperature concentration, weighted voting, Brier-scored selection, telos-gated filtering. Bad aggregation (simple averaging, loudest-voice-wins) kills the signal.

**The critical tradeoff**: Governance (Beer's VSM: coordination, control, identity) is necessary for sustained operation. But governance can reduce diversity through standardization, shared protocols, convergence pressure. **Every governance mechanism must be evaluated against its diversity cost.** Light coordination (System 2 damping) preserves diversity. Heavy control (System 3 mandates) may destroy it.

**What this means for every session**:
- When adding agents: maximize behavioral diversity, not count. The 5th agent from a different model family adds more than the 50th agent from the same family.
- When designing orchestration: route by specialty (skill selection), aggregate by quality weighting (skill denoising), recombine in cascade loops (skill generalization).
- When evolving agents: DarwinEngine MUST preserve diversity. Pure fitness pressure → convergence → transcendence death. Use diversity-preserving selection (MAP-Elites in `diversity_archive.py`).
- When measuring success: track the Krogh-Vedelsby diversity term, not just individual agent fitness. If diversity is falling, transcendence is dying regardless of individual performance.
- When governing: telos gates and VSM channels are necessary but must be LIGHT. System 2 (damping) > System 3 (mandates). The governance cost of a gate is measured in diversity loss.

**Where this lives in the codebase**:
- `diversity_archive.py` — MAP-Elites quality-diversity optimization
- `orchestrator.py` — topology-based routing (fan-out/fan-in/pipeline/broadcast)
- `evolution.py` — DarwinEngine with diversity-preserving selection
- `vsm_channels.py` — Beer's S1-S5 nervous system (light governance)
- `ginko_brier.py` — Brier scoring as aggregation quality measurement
- `signal_bus.py` — decorrelated loop-to-loop signaling (not opinion sharing)
- `handoff.py` — typed artifact handoff preserving agent independence

**Research reference**: Full 9-phase literature review at `spec-forge/transcendence-multi-agent-coordination/research/`

## Build & Test

```bash
# Run all tests
python3 -m pytest tests/ -q

# Run a single test file
python3 -m pytest tests/test_cascade.py -q

# Smoke test (fast subset)
make test-smoke

# Full test suite
make test-all

# Static analysis / repo inventory
make xray

# Dashboard lint
make dashboard-lint
```

- ALWAYS run tests after making code changes
- ALWAYS verify tests pass before committing

## CLI Entry Points

```bash
# Primary CLI
dgc status          # System status
dgc health          # Health diagnostics
dgc stigmergy       # Read stigmergy marks
dgc hum             # Subconscious dreams
dgc evolve trend    # Evolution fitness trend
dgc dharma status   # Kernel integrity check

# API server
uvicorn api.main:app --host 127.0.0.1 --port 8420 --reload

# Dashboard
npm --prefix dashboard run dev

# Operator launcher
bash run_operator.sh
```

## Security Rules

- NEVER hardcode API keys, secrets, or credentials in source files
- NEVER commit .env files or any file containing secrets
- Always validate user input at system boundaries
- Always sanitize file paths to prevent directory traversal

## State Directory (~/.dharma/)

- `~/.dharma/witness/` — Gate check witness logs (JSONL)
- `~/.dharma/stigmergy/marks.jsonl` — Stigmergic marks (append-only)
- `~/.dharma/evolution/archive.jsonl` — Evolution archive
- `~/.dharma/meta/recognition_seed.md` — System self-model
- `~/.dharma/meta/catalytic_graph.json` — Autocatalytic graph
- `~/.dharma/organism_memory/mutations.jsonl` — Strange loop mutations
- `~/.dharma/traces/` — Trace entries

## Navigation

See [`docs/architecture/NAVIGATION.md`](docs/architecture/NAVIGATION.md) for the full module map (500+ modules, 12 architectural layers).
See [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) for the ten highest-system onboarding maps and their current status.
See `README.md` for repo map and common commands.
See `foundations/` for the 10-pillar intellectual genome.

## CRITICAL: Read Before Any Code Changes

**Build-session entrypoint:** Before any build work, read [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](docs/governance/BUILD_SESSION_ENTRYPOINT.md) and run `make onboard`. The current build **portfolio** (1–N co-equal active tracks) is declared in [`docs/governance/ACTIVE_TRACK.yaml`](docs/governance/ACTIVE_TRACK.yaml) and rendered by `make onboard` — do not name a track here in prose. Substrate-nativeness is a measured number, not a prose constant — run `python3 scripts/governance/spine_bypass_report.py` for the live dispatch-site measure instead of citing any doc's frozen percentage. When the operator proposes a new project, **open a new track** in the portfolio (`serves:` a spine objective, `owned_surfaces:`, acceptance criteria) up to the WIP limit — a new project is a new track, not a violation of an existing one. Never close an active track from gate output, WIP pressure, or a SHIPPABLE label; closure requires explicit operator lifecycle authorization and should be treated with the same seriousness as merging a PR.

**Highest-system map:** Read [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) before treating any large map as canonical. It points to the Attractor Closure synthesis, live ops dashboard, broken register, and missing slots.

See [`INTERFACE_MISMATCH_MAP.md`](INTERFACE_MISMATCH_MAP.md) for the complete map of every interface mismatch between modules. **This is the #1 source of runtime failures.** The map documents:
- 0 BLOCKER mismatches (all 3 original BLOCKERs resolved)
- 4 DEGRADED mismatches remaining (MM-05 private coupling, NEW-05 guarded, NEW-07/08 partial)
- 55 module pairs verified, 11 resolved, 6 new entries added and fixed
- A prioritized **Bootstrap Sequence** of fixes (most now resolved)

**Rule for all sessions:** Before fixing a bug or adding a feature, check the mismatch map first. If the module pair you're touching has a known mismatch, fix the mismatch as part of your change. Do not add new callers to broken interfaces.

**Rule for all sessions:** After fixing a mismatch, update the map. Remove the entry or mark it RESOLVED with the commit hash.

Historical model-routing notes now live at [`docs/_archive/2026-04/MODEL_ROUTING_MAP.md`](docs/_archive/2026-04/MODEL_ROUTING_MAP.md). Treat that file as stale context only; verify current provider and routing behavior directly against code before changing model calls.

See [`CYBERNETIC_LOOP_MAP.md`](CYBERNETIC_LOOP_MAP.md) for every feedback loop's sense→act→evaluate→adapt path, current closure status, and verification commands.

Historical agent identity notes now live at [`docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md`](docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md). Treat that file as stale context only; verify current agent creation and identity behavior directly against code before changing that surface.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **dharma_swarm** (122773 symbols, 206424 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/dharma_swarm/context` | Codebase overview, check index freshness |
| `gitnexus://repo/dharma_swarm/clusters` | All functional areas |
| `gitnexus://repo/dharma_swarm/processes` | All execution flows |
| `gitnexus://repo/dharma_swarm/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
