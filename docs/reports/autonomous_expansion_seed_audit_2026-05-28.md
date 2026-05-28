# Autonomous Expansion Seed Audit + Activation Plan

**Author:** Devin (Roaming) — `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only` (no merge rights, no runtime mutation)
**Date:** 2026-05-28
**Branch:** `devin/2026-05-28-autonomous-expansion-audit`
**Active track at time of audit:** `runtime-truth-spine-2026-06` (`ACTIVE_TRACK.yaml`)
**Doctrine documents this audit reports under:** `CLAUDE.md`, `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md`, `docs/doctrine/ANTI_SLOP_RULES.md`, `docs/architecture/SHAKTI_GINKO_ORGAN.md`, `docs/architecture/VENTURE_CELL_LIFECYCLE.md`, `docs/architecture/BUSINESS_INTELLIGENCE_NOTICERS.md`, `docs/doctrine/GNANI_LODESTONE.md`, `docs/architecture/WORLD_MODEL.md`, `docs/architecture/WHAT_IT_WANTS_TO_BECOME.md`, `docs/architecture/LIVING_LAYERS.md`.

> "Growth is allowed. Unwitnessed growth is not.
> Autonomy is allowed. Unreceipted autonomy is not.
> Revenue is allowed. Revenue that corrupts telos is not."
> — operator briefing, 2026-05-28

This is a documentation-only audit. It proposes no runtime behavior, no new persistence surface, no new daemon, no new abstraction. It maps what already exists, classifies it, surfaces what is missing, and produces a brutally practical 3-PR sequence that lands *under* the active spine track, not parallel to it.

---

## 0. Framing — Why this audit, and what it refuses to be

The operator's briefing asks one question:

> What seeds in `dharma_swarm` *already exist* that, if pruned and wired correctly, would let this system become an autonomously growing, revenue-generating, dharmically-aligned multi-agent organism — without violating any safety doctrine, and without building yet another grand abstraction?

Three failure modes were named explicitly and are refused here:

1. **Build a new substrate.** Refused. The repo already has `dharma_swarm/spine/`, `auto_proposer.py`, `fractal/`, `revenue/`, `a2a/`, `cron_runner.py`, `stigmergy.py`, and the BoardStore facade spec (`docs/architecture/SWARM_BOARDSTORE_SPEC.md`). Anything this audit proposes lands as a thin adapter on these.
2. **Add a parallel surface.** Refused. The active track is converging *toward one* invocation path, one evidence record, one routing decision, one truth surface (`CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md`). Expansion seeds attach to `EvidenceReceipt` and BoardStore — they do not create rival logs.
3. **Authorize autonomy that has no receipt.** Refused. Every loop proposed here ends in a card the operator (or an executor agent under ARJUNA gate) acts on. The noticers notice. They never execute.

The active track is `runtime-truth-spine-2026-06`. This audit's recommendations are sequenced *after* the spine lands cleanly. PR1 below is the only one safe to ship in parallel because it adds no runtime code.

---

## 1. Part 1 — Audit of existing seeds

Each seed is classified into one of:

- **LIVE** — code runs in production (or is exercised by CI, or is on the active surface manifest at `status: live`)
- **SCAFFOLDED** — code exists with real shape but is unconnected to the live flow / not invoked in production
- **SPEC-ONLY** — docs exist, no code
- **DORMANT** — code exists but is gated off (env flag, `shadow_mode=True`, or simply uncalled)
- **DUPLICATED** — overlaps another seed; needs consolidation
- **STALE** — claims in docs disagree with code; needs reconciliation
- **DANGEROUS** — would violate doctrine if turned on without further gating
- **READY** — can be activated within ≤ 1 PR of safe, witnessed work

### 1.1 Spine (runtime truth) — `dharma_swarm/spine/`

| Module | LOC | Status | Notes |
|---|---|---|---|
| `spine/invoke.py` | 56 | LIVE | Single blessed entry: `invoke_agent(task, agent_id, context_id, routing, invoker) -> EvidenceReceipt`. PR #364 just landed. |
| `spine/receipt.py` | 128 | LIVE | `EvidenceReceipt` dataclass; OTel GenAI-compatible serializer. Canonical. |
| `spine/persistence.py` | 57 | LIVE | Single sink: `UPDATE delegation_runs SET receipt_json = ? WHERE task_id = ?`. Idempotent migration. No new table. |
| `spine/routing.py` | 35 | LIVE | `RoutingDecision` value object. |

**Verdict:** This is the *most disciplined* code in the repo. Every line obeys "one invariant, one path, one record." Everything downstream in this audit hangs off `EvidenceReceipt`.

**Doctrine fit:** `CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md §7 Fix 1 + Fix 2 + Fix 3` — the spine *is* the converged seam.

### 1.2 A2A surface — `dharma_swarm/a2a/`

| Module | Status | Notes |
|---|---|---|
| `a2a_bridge.py`, `a2a_client.py`, `a2a_server.py` | LIVE | Tier-1 conformant after PR #362 (per `INTERFACE_MISMATCH_MAP.md`). |
| `agent_card.py` | LIVE | Agent cards per A2A spec ([A2A protocol overview, IBM](https://www.ibm.com/think/topics/agent2agent-protocol); now Linux Foundation, July 2025). |
| `node_gateway.py`, `node_registry.py` | LIVE | Inter-swarm registry. |

**Verdict:** This is the second-cleanest surface. A2A is the path through which sub-swarms and inter-org collaboration will eventually flow ([Announcing Agent2Agent (A2A), Google](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)).

**External alignment:** AGNTCY (Cisco→Linux Foundation, July 2025) is now the umbrella project that *contains* A2A and MCP ([Linux Foundation press release](https://www.linuxfoundation.org/press/linux-foundation-welcomes-the-agntcy-project-to-standardize-open-multi-agent-system-infrastructure-and-break-down-ai-agent-silos)). The repo's A2A work is on the right side of history; no rewrite needed.

### 1.3 Auto-proposer + Darwin loop — `dharma_swarm/auto_proposer.py`, `evolution.py`, `dgm_loop.py`

| Module | LOC | Status | Notes |
|---|---|---|---|
| `auto_proposer.py` | 830 | LIVE | Notice→propose pattern already exists for: fitness drop, failure patterns, stigmergy hot spots, provider failures, stale tasks, plateaus, test clusters, evolution stagnation. Submits to Darwin or BoardStore. |
| `evolution.py` (`DarwinEngine`) | 3,465 | LIVE-CAPABLE / SHADOW-DEFAULT | Has real `apply_diff_and_test` (l. 2193) using `DiffApplier` with rollback, real `apply_sealed_packet` (l. 2262), and `apply_in_sandbox` (l. 2285). **Per `WHAT_IT_WANTS_TO_BECOME.md` this is called "DEGRADED, simulates evolution; never applies diffs" — that claim is now STALE.** The capability exists; it is gated. |
| `dgm_loop.py` | 652 | DORMANT-BY-FLAG | `shadow_mode=True` is default. Real mutation requires `DHARMA_DGM_SHADOW=0` AND `autonomy>=2`. Sakana published [Darwin Gödel Machine, arXiv 2505.22954](https://arxiv.org/abs/2505.22954) in May 2025 — the repo is implementing the *same idea*, with shadow-mode as the safety floor. The pattern is sound. |
| `recursive_discovery.py` | 329 | SHADOW-ONLY (by design) | Manifest line 478: "Keep shadow-only: record receipts and recommend PRs without autonomous apply." This is correct discipline. Do not relax. |

**Verdict:** The Darwin loop is *live-capable*, *shadow-default*, and *correctly gated*. The doctrine document `WHAT_IT_WANTS_TO_BECOME.md` mis-describes it. Fang #1 ("Real DGM Loop") is not "build the loop"; it is "trust the loop you already have under documented stage-gates."

**External precedent:** The Sakana DGM paper validates exactly the design here — open-ended exploration, archive of agents, code self-modification under benchmark gates ([Sakana DGM announcement](https://sakana.ai/dgm/)).

### 1.4 Fractal Rooms — `dharma_swarm/fractal/`

| Module | LOC | Status | Notes |
|---|---|---|---|
| `fractal_room.py` | 784 | LIVE | `evaluate_kill_conditions`, `evaluate_spinout_conditions` already implemented (l. 248–303). SignalBus event types (l. 80–89). |
| `room_bridge.py`, `room_brief.py`, `room_configs.py`, `room_health.py` | LIVE | Operator-facing room surface. |
| `kaizen_review.py` | LIVE | Retrospective improvement loop. |

**Verdict:** Fractal rooms are *the VentureCell substrate that already exists* — but they don't yet carry the lifecycle FSM described in `VENTURE_CELL_LIFECYCLE.md`. The kill/spinout *evaluation* functions are live; the *FSM that consumes them* is spec-only.

**Bridge required:** `VentureCell` is described in `docs/architecture/VENTURE_CELL_LIFECYCLE.md` as a 5-state FSM (PROPOSED → INCUBATING → ACTIVE → MATURE → DIVESTING/ARCHIVED). The substrate functions to evaluate transitions exist in `fractal_room.py`. The FSM driver does not.

### 1.5 Revenue Engine — `dharma_swarm/revenue/`

| Module | LOC | Status | Notes |
|---|---|---|---|
| `spine.py` | 477 | SCAFFOLDED | `RevenueSpine`, `RevenueTarget`, `OutreachDraft`. Persistence to `~/.dharma/revenue_spine/`. |
| `spine_models.py` | 193 | SCAFFOLDED | Pydantic models. |
| `intelligence.py` | 276 | SCAFFOLDED | `RevenueIntelligenceIngestor` — reads `.md`/`.txt` from `~/.dharma/revenue_intel/inbox/`, parses, routes to spine. |
| `intel_parser.py` | 409 | SCAFFOLDED | Structured claim/competitor extraction. |
| `scout_daemon.py` | 443 | LIVE-CAPABLE / FLAG-GATED | Real GitHub scouting + `find_targets.py` integration; **explicit doctrine line 12: "NO AUTONOMOUS SPAM. Outreach drafts require human approval."** No outreach send path exists; only draft. |
| `telic_bridge.py` | 340 | SCAFFOLDED | Bridge to telos gates. |
| `wedge_pipeline.py` | 318 | SCAFFOLDED | Revenue Wedge cell pipeline (per `VENTURE_CELL_REVENUE_WEDGE.md`). |

**Verdict:** The revenue substrate is ~80% of `MarketScanNoticer` from `BUSINESS_INTELLIGENCE_NOTICERS.md §2.5`. The migration path is already named in that spec.

**Safety check:** `scout_daemon.py` is the riskiest module in this category. Mitigation that already exists: it drafts but never sends; it requires `GITHUB_TOKEN` (no token = no-op); persistence is contained to `~/.dharma/revenue_scout/`. Confirmed safe as written.

### 1.6 SHAKTI executive — `dharma_swarm/shakti_executive/`

| Module | LOC | Status | Notes |
|---|---|---|---|
| `executive.py` | 192 | SCAFFOLDED | Operator-facing executive surface. |
| `feedback_writer.py`, `inputs.py`, `models.py`, `scoring.py` | SCAFFOLDED | Decision-support primitives. |

**Verdict:** This is the operator-side anchor for the SHAKTI_GINKO organ. It is small, clean, and correctly scoped. It does *not* yet wire to noticers or VentureCells. This is the natural seat for the Treasury and ARJUNA gate reads.

### 1.7 Trading Lab (Ginko, ONE VentureCell, live) — `dharma_swarm/ginko_*.py`

18 modules: `ginko_agents.py`, `ginko_attribution.py`, `ginko_audit.py`, `ginko_backtest.py`, `ginko_bridge.py`, `ginko_brier.py`, `ginko_data.py`, `ginko_evolution.py`, `ginko_live_test.py`, `ginko_orchestrator.py` (1,000+ LOC), `ginko_paper_trade.py`, `ginko_regime.py`, `ginko_report_gen.py`, `ginko_risk.py`, `ginko_sec.py`, `ginko_sentiment.py`, `ginko_signals.py`.

| Sub-component | Status | Notes |
|---|---|---|
| Orchestrator + autonomy stages | LIVE | `AUTONOMY_REQUIREMENTS`, `check_autonomy_advancement` (l. 826–892) cited by `BUSINESS_INTELLIGENCE_NOTICERS.md §10 Appendix`. |
| Paper trade + backtest | LIVE | Stage 1-2 of the autonomy ladder. |
| Brier + attribution | LIVE | Calibration scoring (key KPI for ViabilityNoticer). |
| Risk + regime | LIVE | Drawdown + state-of-market. |
| Live test path | LIVE-CAPABLE / OPERATOR-GATED | Per `VENTURE_CELL_LIFECYCLE.md` autonomy stages 4-5 are operator-only. |

**Verdict:** Trading Lab is the *first realized VentureCell* and proves the cell-lifecycle pattern works in production. It is the empirical floor.

**DANGEROUS line not crossed:** Doctrine prohibits autonomous live capital deployment. Code respects this — live trading requires explicit operator approval, and stages 4-5 cannot be auto-advanced. Confirmed by reading the autonomy-advancement helpers.

### 1.8 World model + actions — `dharma_swarm/world_model.py`, `world_actions.py`

| Module | LOC | Status | Notes |
|---|---|---|---|
| `world_model.py` | 295 | LIVE | Three-attractor model (A=Managed Collapse, B=Techno-Acceleration, C=Dharmic Equilibrium). |
| `world_actions.py` | 329 | PARTIAL | Has `github_clone_repo`, `github_commit_push`, `github_create_issue`, `github_create_pr`, `create_website_scaffold`, `publish_markdown_artifact`, `spawn_sub_swarm_spec`. **Has NO `boot_sub_swarm`** — exactly as `WHAT_IT_WANTS_TO_BECOME.md` Gap 3 claims. |

**Verdict:** "Spawn spec on disk" exists. "Boot a sub-swarm from that spec" does not. Fang #3 is real.

### 1.9 Witness — `dharma_swarm/witness.py`

| Module | LOC | Status | Notes |
|---|---|---|---|
| `witness.py` | 428 | RETROSPECTIVE-ONLY | `WitnessAuditor`, `AuditFinding`, `record_anomaly_signal`. Reviews *after* the fact. |

**Verdict:** Confirmed Gap #2 from `WHAT_IT_WANTS_TO_BECOME.md`. The inline-witness work is genuine — the existing witness is forensic, not preventive.

**Reframe:** With the spine now persisting `EvidenceReceipt` *per dispatch attempt* (`spine/persistence.py`), the substrate for inline witness already exists. Inline witness becomes: "evaluate receipt → emit signal before the next dispatch." It is no longer architecturally hard; it is a thin policy module that subscribes to receipt persistence.

### 1.10 Memory / Knowledge — Memory Palace / LanceDB

Per Gap #4 in `WHAT_IT_WANTS_TO_BECOME.md` and the `docs/architecture/memory_kernel_*.md` series (M1–M4b, currently shipping in PRs per `ACTIVE_SURFACE_MANIFEST.yaml`). Status:

- **Memory kernel M1 (read facade)** — LIVE
- **M2 writer sentinel + KnowledgeOps intake + conflict projection + promotion proposal queue + decision ledger** — IN PROGRESS, multiple PRs
- **M3b/c/d/e (context eval, parity, shadow context, compiler shadow)** — IN PROGRESS
- **M4a shadow report sweep, M4b writer readiness** — IN PROGRESS

**Verdict:** Memory kernel is the *single most active* architectural workstream after the spine. It is the right place for cross-cell knowledge to live. Do not propose any rival memory surface.

### 1.11 Telos gates — `docs/doctrine/`

Gap #5: TelosGates exist (SATYA, AHIMSA, REVERSIBILITY) and are referenced repeatedly in code (e.g., `BUSINESS_INTELLIGENCE_NOTICERS.md §0`, `revenue/scout_daemon.py`), but **have never been red-teamed** — no negative-example test suite, no published bypass-attempts log.

**Verdict:** Spec-strong, test-thin. This is where memetic/manipulation safety lives. It needs a `tests/red_team/` suite before any noticer goes from spec to live.

### 1.12 Spinouts — `spinouts/planetary_reciprocity_commons_seed/`

One real spinout package. Demonstrates the divestment path works at all. No second spinout yet.

### 1.13 Cron infrastructure — `dharma_swarm/cron_runner.py`, `cron_daemon.py`

| Module | LOC | Status |
|---|---|---|
| `cron_runner.py` | 844 | LIVE — handler registry, schedule, run loop |
| `cron_daemon.py` | LIVE | Daemon wrapper |
| `stigmergy.py` | 440 | LIVE — substrate signals for AutoProposer / OpportunityNoticer |

**Verdict:** `NoticerScheduler` in `BUSINESS_INTELLIGENCE_NOTICERS.md §7` is named *correctly* as "a thin reorganization of `cron_runner` — no new daemon infrastructure." Honor this.

### 1.14 Inter-agent surface — `inter_agent/`

Currently only `inter_agent/devin/inbound/` exists. No `outbound/` directory yet. Devin's `DEVIN.md` mandates outbound notices for evidence-only worker. **This audit's outbound notice creates the directory.**

### 1.15 Vault — `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/`

Operator-local strategic authority. NOT in repo. Read via `VaultBridge` (specified in `SHAKTI_GINKO_ORGAN.md` and `BUSINESS_INTELLIGENCE_NOTICERS.md §5.2`). 91 `[SWARM_TARGET]` markers reportedly unmapped to cells (Doc A).

**Verdict:** This is *the* source of intent. `IdeationNoticer` reads from here. The VaultBridge interface is spec-only; the concrete read implementation is the bottleneck for IdeationNoticer.

### 1.16 GPU / benchmark seeds

No `dharma_swarm/benchmarks/` directory exists. Brier scoring in `ginko_brier.py` is the only realized benchmark surface. No GPU expansion code, no carbon-accounting code, no compute-budgeting code.

**Verdict:** "Welfare-Ton MRV Loop" (Fang #5) and "ecologically blind compute expansion" prohibition are both genuinely unimplemented. Spec only.

### 1.17 Summary table — seed classification

| Category | LIVE | LIVE-CAPABLE / GATED | SCAFFOLDED | SPEC-ONLY | DORMANT | STALE | DANGEROUS-IF-RELAXED |
|---|---|---|---|---|---|---|---|
| Spine | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| A2A | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| Darwin / DGM / AutoProposer | 1 | 2 | 0 | 0 | 1 | 1 (doctrine mis-claim) | 1 (DGM if shadow off without gate) |
| Fractal rooms | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| Revenue | 0 | 1 | 6 | 0 | 0 | 0 | 1 (outreach send if added) |
| SHAKTI executive | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| Ginko trading | 18 | 1 (live test) | 0 | 0 | 0 | 0 | 1 (live capital, already gated correctly) |
| World model/actions | 1 | 0 | 1 (partial) | 1 (boot_sub_swarm) | 0 | 0 | 0 |
| Witness | 1 | 0 | 0 | 1 (inline witness) | 0 | 0 | 0 |
| Memory kernel | 1 | 0 | 0 | 8 (M2/M3/M4 in flight) | 0 | 0 | 0 |
| Telos gates | 1 | 0 | 0 | 1 (red-team suite) | 0 | 0 | 0 |
| Cron / stigmergy | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| Inter-agent | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Vault bridge | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| GPU / compute / MRV | 0 | 0 | 0 | 1 | 0 | 0 | 1 (if GPU added before MRV) |
| SHAKTI_GINKO organ | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| VentureCell FSM driver | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| BI Noticers | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| Spinouts | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

**Headline:** The substrate is ~70% live. The *cell architecture* on top of it is ~5% live. The bridging code — VentureCell FSM driver, Noticer base class, VaultBridge, inline witness, MRV — is the *entire gap*.

---

## 2. Part 2 — External precedent

Six precedents are load-bearing for the recommendations below.

### 2.1 Darwin Gödel Machine (Sakana, May 2025)

[Darwin Gödel Machine, Sakana AI](https://sakana.ai/dgm/) and [arXiv 2505.22954](https://arxiv.org/abs/2505.22954). Open-ended self-improving agent that maintains an *archive* of agent variants and benchmarks each on SWE-bench. Critically, *every* variant lives in the archive — including failures — so the search is genuinely open-ended. This matches the auto-proposer + Darwin design in the repo precisely. **The repo's design choice is validated by external evidence; no new abstraction is needed.**

Reference implementation: [jennyzzt/dgm on GitHub](https://github.com/jennyzzt/dgm).

### 2.2 Agent2Agent (A2A) and AGNTCY

[A2A protocol, Google](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) (April 2025) was donated to the Linux Foundation alongside [AGNTCY](https://docs.agntcy.org) (Cisco/Dell/Google/Oracle/Red Hat, July 2025). AGNTCY provides Open Agent Schema Framework (OASF), Agent Directory, Secure Low-Latency Interactive Messaging (SLIM), Identity, Observability. **The repo's `a2a/` surface is already on the standard track.** No need to write a custom inter-swarm protocol.

### 2.3 Virtual Agent Economies (DeepMind, Sept 2025)

[arXiv 2509.10147](https://arxiv.org/html/2509.10147v1). Frames "sandbox economy" along two axes: emergent-vs-intentional × permeable-vs-impermeable. Argues that distributed credit-tracing back through chains of agent value creation is the foundation of agent specialization. **This is the theoretical basis for VentureCell + Treasury + ARJUNA in the repo** — and it argues the repo's architecture is *correct in kind*, not over-engineered.

### 2.4 Multi-agent security (May 2025)

[Towards Secure Systems of Interacting AI Agents, arXiv 2505.02077](https://arxiv.org/html/2505.02077v1). Survey: zero-trust between agents, cryptographic commitments, state-dynamic limits on inter-agent connectivity during high-risk operations, agent-based red teaming. **The notice-only contract in `BUSINESS_INTELLIGENCE_NOTICERS.md §0` is a concrete instance of state-dynamic safety: noticers cannot communicate with executors except via cards.** This audit endorses the contract as written.

### 2.5 Anthropic GTG-1002 swarm attack (Nov 2025)

[AI Swarm Attacks 2026 Guide, Kiteworks](https://www.kiteworks.com/cybersecurity-risk-management/ai-swarm-attacks-2026-guide/). Anthropic documented a coordinated cyberattack across 30 organizations with 80–90% of operations running without human input. **This is the empirical reason the spine's per-dispatch `EvidenceReceipt` and the BoardStore audit stream must be non-negotiable.** Any swarm capable of executing on the world must be capable of being replayed and red-teamed; the spine makes this true.

### 2.6 Carbon-aware Kubernetes scheduling

[AI-driven carbon-aware cloud scheduling, wjarr 2025](https://wjarr.com/sites/default/files/fulltext_pdf/WJARR-2025-1854.pdf) and [Sustainable Computing and Green AI survey, ijrpr](https://ijrpr.com/uploads/V6ISSUE12/IJRPR58054.pdf). 15–30% carbon reduction without performance loss via region/time shifting of non-urgent workloads. **This is the concrete precedent for the "ecologically blind compute expansion" prohibition in operator doctrine — and a real protocol the repo can adopt for the Welfare-Ton MRV loop (Fang #5) when it is built.**

---

## 3. Part 3 — Flywheel with explicit repo owners

The flywheel is *seven* nodes, each with a *single* code owner and a *single* artifact. Every step ends in a record on an existing surface. No new substrate.

```
                  ┌──────────────────┐
                  │  1. NOTICE       │   noticer module emits CardProposal
                  │  scout_daemon /  │   → BoardStore (via facade)
                  │  auto_proposer   │   → WitnessEvent
                  └────────┬─────────┘
                           │ card
                           ▼
                  ┌──────────────────┐
                  │  2. PROPOSE      │   IdeationNoticer / ViabilityNoticer
                  │  noticers/*      │   filter+rank → 3 candidates / scan
                  └────────┬─────────┘
                           │ candidate
                           ▼
                  ┌──────────────────┐
                  │  3. GATE         │   ARJUNA threshold @ BoardStore facade
                  │  BoardStore §11  │   (rejected → WitnessEvent for audit)
                  └────────┬─────────┘
                           │ approved
                           ▼
                  ┌──────────────────┐
                  │  4. INCUBATE     │   VentureCell FSM driver
                  │  fractal_room +  │   creates Room, allocates from Treasury
                  │  cell_fsm (NEW)  │   PROPOSED → INCUBATING
                  └────────┬─────────┘
                           │ work packets
                           ▼
                  ┌──────────────────┐
                  │  5. EXECUTE      │   spine/invoke.py (LIVE)
                  │  spine.invoke    │   every attempt → EvidenceReceipt
                  └────────┬─────────┘
                           │ receipts
                           ▼
                  ┌──────────────────┐
                  │  6. WITNESS      │   QualityNoticer reads receipts +
                  │  noticers/quality│   KPIs → kill/spinout/demote cards
                  └────────┬─────────┘
                           │ verdict
                           ▼
                  ┌──────────────────┐
                  │  7. EVOLVE/SPIN  │   DarwinEngine.apply_diff (gated) or
                  │  evolution +     │   spinouts/ package
                  │  spinouts/       │
                  └──────────────────┘
                           │
                           ▼
                  back to NOTICE
```

### 3.1 Owner mapping (existing modules, no new owners)

| Step | Existing owner module(s) | New code required |
|---|---|---|
| 1. NOTICE | `dharma_swarm/auto_proposer.py`, `dharma_swarm/revenue/scout_daemon.py`, `dharma_swarm/stigmergy.py` | — |
| 2. PROPOSE | `dharma_swarm/auto_proposer.py` (existing notice→propose pattern, l. 51-67 `ObservationType`/`ProposalSource`) | A thin `Noticer` base in `dharma_swarm/noticers/base.py` (deferred until spine PR-B/C land per `BUSINESS_INTELLIGENCE_NOTICERS.md §10`) |
| 3. GATE | BoardStore facade spec (`SWARM_BOARDSTORE_SPEC.md §11`); not yet implemented | Single facade module (existing spec; PR #316 line); ARJUNA threshold = 0.35 (operator-tunable) |
| 4. INCUBATE | `dharma_swarm/fractal/fractal_room.py` (`evaluate_kill_conditions` l. 248–303) + `dharma_swarm/shakti_executive/executive.py` (Treasury) | `dharma_swarm/venture_cells/fsm.py` — thin 5-state driver, **reads** from existing room+executive APIs |
| 5. EXECUTE | `dharma_swarm/spine/invoke.py` (LIVE) | — |
| 6. WITNESS | `dharma_swarm/witness.py` (retrospective) + receipts persisted to `delegation_runs.receipt_json` | A thin inline-witness policy module that subscribes to `persist_receipt`; emits signals when receipt status ≠ "ok" or attributes match red-team patterns |
| 7. EVOLVE / SPIN | `dharma_swarm/evolution.py` (`apply_diff_and_test`, `apply_sealed_packet`, l. 2193 / 2262) + `spinouts/` | — |

**Critical:** Steps 1, 4, 5, 6 each already have ≥80% of the code. The bridging adapters are small. Step 3 (BoardStore facade) and step 4 (VentureCell FSM driver) are the only material new modules — and each is sized at <300 LOC.

### 3.2 Where the flywheel can stall

| Stall | Cause | Mitigation |
|---|---|---|
| No cards | No noticer activated | Phase 2 PR (post-spine-PR-C) introduces `Noticer` base; refactor `scout_daemon` to be `MarketScanNoticer` |
| Cards refused | ARJUNA threshold mis-tuned | Operator-tunable via `~/.dharma/arjuna_threshold` (single value) |
| Cells stuck in PROPOSED | No FSM driver | This audit's PR3 (KPI bridge — `venture_cells/` slot) |
| Receipts not witnessed | No inline-witness policy | Inline-witness PR after spine PR-C lands |
| No evolution | `DHARMA_DGM_SHADOW=1` (default) | Correct. Stay shadow until red-team suite lands. |
| No spinout | No KPI maturity proof | Real KPIs flow only after step 5/6 close |

---

## 4. Part 4 — Activation map (5 cells)

Five cells, ranked by **(value × already-realized substrate × safety distance)**. Each has full spec.

### 4.1 Cell A — `trading-lab-ginko` *(already realized; the empirical floor)*

| Field | Value |
|---|---|
| Status | ACTIVE — Stage 1-2 paper trading on Agni VPS |
| Purpose | Forecast equity moves with Brier-calibrated signals; advance autonomy stage only when KPI bar met |
| Seeds | All 18 `ginko_*.py` modules (LIVE) |
| Budget | Operator-defined; paper-only at Stage 1-2 |
| Revenue path | Stage 4-5 only, operator-gated |
| KPIs | Brier ≤ 0.22 for 200 predictions; Sharpe > 1.0 30-day rolling; max drawdown ≤ 5%; daily P&L attribution clean |
| Kill conditions | Brier deterioration > 0.02 / 200 predictions; drawdown > stage threshold × 3 consecutive days; `welfare_tons_produced < 0` |
| Spinout conditions | Stage 5 sustained 90 days + operator approval |
| First PR | None — already running |
| First user | Operator (self) |

### 4.2 Cell B — `revenue-wedge` *(declared; needs FSM activation)*

| Field | Value |
|---|---|
| Status | PROPOSED → INCUBATING after PR3 lands |
| Purpose | Convert agent-governance audit offering into 3 paying customers; validate the wedge thesis |
| Seeds | `revenue/spine.py`, `revenue/scout_daemon.py`, `revenue/wedge_pipeline.py`, `docs/offers/agentic-code-governance-sprint.md` |
| Budget | 50k tokens / month (from `VENTURE_CELL_REVENUE_WEDGE.md`) |
| Revenue target | $10k cumulative within 90 days |
| Burn cap | $2k / month |
| KPIs | targets_qualified count, outreach_drafted count, outreach_approved (manual) count, **demos booked, demos converted, contracts signed, revenue_usd** |
| Kill conditions | `no_revenue_60d == True` OR `burn > 3 × revenue` OR operator override |
| Spinout conditions | `revenue > burn` for 3 months AND 3 paying customers AND operator approval |
| Telos gate | NO autonomous outreach send; every send is human-approved (already enforced in `scout_daemon.py` line 12) |
| First PR | This audit's PR3 (KPI bridge — wires `revenue/spine.py` outputs into VentureCell FSM) |

### 4.3 Cell C — `runtime-truth-spine-cell` *(meta-cell that consumes the spine)*

This is *not* a VentureCell in the conventional sense — it is the **substrate cell** that the active track is building. It is named explicitly so other cells inherit its receipts.

| Field | Value |
|---|---|
| Status | ACTIVE — current track is `runtime-truth-spine-2026-06` |
| Purpose | One invariant, one invocation path, one routing decision, one evidence receipt, one truth surface |
| Seeds | `dharma_swarm/spine/*` (LIVE), `dharma_swarm/a2a/*` (LIVE) |
| KPIs | % dispatch attempts with `receipt_json` set; `error_source` distribution; routing-decision-id continuity; A2A conformance test pass rate |
| Kill conditions | Cannot be killed — this is the substrate |
| Spinout conditions | N/A |
| First PR | Already merged (#362 A2A, #364 spine) |

### 4.4 Cell D — `governance-noticers` *(spec-only → first thin slice)*

| Field | Value |
|---|---|
| Status | SPEC-ONLY today; INCUBATING earliest after spine PR-C |
| Purpose | Replace ad-hoc daily ops with five persistent BI Noticers per `BUSINESS_INTELLIGENCE_NOTICERS.md` |
| Seeds | `auto_proposer.py` (notice-only precedent), `revenue/scout_daemon.py` (becomes MarketScanNoticer), `cron_runner.py` (becomes NoticerScheduler shim) |
| Budget | Operator-defined per noticer rate limits (`§8.2`) |
| Revenue path | Indirect — quality of operator decisions improves; no direct revenue |
| KPIs | Cards proposed / day per noticer; card → approval rate; card → cell-created rate; refused-by-ARJUNA rate (low is bad — means honest scoring); kill-watch firing rate vs actual cell deaths |
| Kill conditions | Any noticer floods cards (`§8.2` rate limits exceeded); any noticer overreach (`WARN_NOTICER_OVERREACH`); any noticer crashes 5× in succession (`§8.1`) |
| Phase 1 (this audit) | Documentation only — `governance-noticers` registered in expansion map as PROPOSED |
| Phase 2 (post-spine) | `noticers/base.py` + `MarketScanNoticer` shim; refactor `scout_daemon` |

### 4.5 Cell E — `memory-kernel-cell` *(currently shipping; name it)*

| Field | Value |
|---|---|
| Status | ACTIVE — multiple PRs in flight (M1 LIVE, M2/M3/M4 in flight per active surface manifest) |
| Purpose | Single read facade + writer sentinel + KnowledgeOps intake; *the* memory surface every cell shares |
| Seeds | `dharma_swarm/memory_kernel/*` (per architecture docs) |
| KPIs | Read facade p95 latency; writer sentinel block rate (false positives), shadow context parity; conflict projection acceptance rate |
| Kill conditions | Read facade p99 > 1s sustained 1h; writer sentinel false-positive > 20% |
| Telos gate | SATYA — memory cannot misrepresent its lineage; AHIMSA — no PII leak across cell boundaries; REVERSIBILITY — every write has a tombstone path |
| First PR | Already in flight (multiple) |

---

## 5. Part 5 — Safety constraints as repo-level checks

Each operator constraint maps to a concrete check.

| Constraint | Repo check (existing or proposed) | Status |
|---|---|---|
| "Unwitnessed growth is not allowed" | `spine/persistence.py` writes `EvidenceReceipt` per dispatch | LIVE |
| "Unreceipted autonomy is not allowed" | `EvidenceReceipt` mandatory for every `invoke_agent` call | LIVE |
| "No autonomous live trading" | `ginko_orchestrator.py:826–892` `check_autonomy_advancement`; stages 4–5 operator-only | LIVE |
| "No spam/outreach automation without human approval" | `revenue/scout_daemon.py:12` rule; only draft path exists | LIVE |
| "No hidden compute spend" | `EvidenceReceipt.input_tokens / output_tokens / cost_usd` fields | LIVE (capture) — DASHBOARD pending |
| "No credential handling outside existing secure paths" | Anti-slop rule 1 `~/.dharma` write owners frozen + `dharma-anti-slop.yml` `.semgrep` rules | LIVE |
| "No uncontrolled self-modification" | `DHARMA_DGM_SHADOW=1` default; autonomy gate on `apply_diff_and_test` | LIVE — needs red-team suite |
| "No new persistence surface" | Anti-slop rule 2 (no-new-substrate WARN); `.semgrep/dharma-anti-slop.yml` | LIVE |
| "No autonomous deployment without receipt + rollback" | `evolution.py:2222` `DiffApplier.apply_and_test` with rollback | LIVE |
| "No memetic manipulation" | Telos gates (SATYA, AHIMSA) — **NEEDS** `tests/red_team/` suite | SPEC ONLY |
| "No GPU expansion without cost/carbon/energy/purpose accounting" | Welfare-Ton MRV loop — **SPEC ONLY (Fang #5)** | SPEC ONLY |
| "No VentureCell auto-advance without KPI proof" | `BUSINESS_INTELLIGENCE_NOTICERS.md §6.2` QualityNoticer kill-watch + `evaluate_spinout_conditions` | SPEC ONLY (needs FSM driver) |

### 5.1 Gaps that block any autonomous expansion

Three of the twelve constraints are spec-only. Until they have *code-level checks*, the corresponding behavior must remain shadow-only:

1. **Telos red-team suite** — `tests/red_team/` with at least: SATYA-bypass attempt (claim made without source), AHIMSA-bypass attempt (action affecting vulnerable user without flag), REVERSIBILITY-bypass attempt (action without undo path). Acceptance: `pytest tests/red_team/` passes (all gates reject the bypass).
2. **Welfare-Ton MRV loop** — even a 50-LOC stub that logs `welfare_tons_produced` per cell to the existing `~/.dharma/` surface, capable of being incremented by hand initially. Without this, no cell with externalities can advance.
3. **VentureCell FSM driver** — `dharma_swarm/venture_cells/fsm.py`. Reads from existing `fractal_room.evaluate_kill_conditions` and `evaluate_spinout_conditions`; emits state transitions to BoardStore. No new persistence surface.

Items 1 and 3 should land before any noticer flips from spec to shadow. Item 2 should land before any GPU/compute expansion is even *proposed*.

---

## 6. Part 6 — Brutally practical 3-PR plan

**Sequencing constraint:** PR1 ships now (documentation-only, no runtime). PR2 and PR3 wait until **spine PR-C lands** (per `CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md §7`). Do not anticipate.

### PR1 — Autonomous Expansion Seed Audit *(this PR, documentation only)*

| Field | Value |
|---|---|
| Branch | `devin/2026-05-28-autonomous-expansion-audit` |
| Files added | `docs/reports/autonomous_expansion_seed_audit_2026-05-28.md` (this file); `inter_agent/devin/outbound/2026-05-28-devin-autonomous-expansion-audit.md` |
| Files modified | None |
| Anti-slop rules respected | Rule 1 (no `~/.dharma` write owners changed), Rule 2 (no-new-substrate), Rule 8 (no root markdown — file is under `docs/reports/`), Rule 10 (no module-line-budget impact) |
| Runtime behavior | None |
| Tests | None required (no code change) |
| Acceptance | (a) Anti-slop CI green; (b) Devin outbound notice present; (c) Audit cited in next operator brief |
| Reviewers | Operator (final), Codex (for substrate framing), Claude (for doctrine framing) |
| Risk | Documentation drift if not maintained; mitigated by dating the file. |

### PR2 — VentureCell KPI Bridge *(after spine PR-C; ~300 LOC)*

| Field | Value |
|---|---|
| Title | `feat(venture_cells): add FSM driver that consumes EvidenceReceipt KPIs (no new substrate)` |
| Branch | `devin/<date>-venture-cell-fsm-bridge` |
| Files added | `dharma_swarm/venture_cells/__init__.py`, `dharma_swarm/venture_cells/fsm.py`, `dharma_swarm/venture_cells/models.py`, `tests/test_venture_cell_fsm.py` |
| Files modified | None outside `dharma_swarm/venture_cells/` |
| Behavior | Reads cells from `fractal_room` config; evaluates `kill_conditions` / `spinout_conditions` (existing helpers at `fractal/fractal_room.py:248–303`); emits transitions via SignalBus events (existing types l. 80–89). Persists *nothing new* — state is computed from existing kill/spinout helpers + receipts. |
| Anti-slop rules respected | Rule 1 (no new `~/.dharma` write owner); Rule 2 (no new persistence class); Rule 8 (no root markdown); Rule 10 (new module, not on grandfathered list, must be ≤ 300 LOC) |
| Runtime risk | Read-only; transitions emit signals only — operator confirms via existing room surface |
| KPIs surfaced | revenue_usd, burn_usd, days_active, paying_customers, brier (trading-lab only), welfare_tons_produced (initially 0/manual) |
| Tests | Unit tests for each FSM transition; integration test with `fractal_room` fixtures; **red-team test**: kill condition met but cell auto-advances → must fail |
| Acceptance | CI green; trading-lab-ginko cell appears in `dharma cell list`; revenue-wedge cell creates correctly (status PROPOSED) |

### PR3 — SHAKTI_GINKO First-Loop Shim *(after PR2; ~200 LOC)*

| Field | Value |
|---|---|
| Title | `feat(shakti_ginko): wire ARJUNA threshold read + Treasury budget read for VentureCell FSM (no new substrate)` |
| Branch | `devin/<date>-shakti-ginko-first-loop` |
| Files added | `dharma_swarm/shakti_executive/arjuna_gate.py`, `dharma_swarm/shakti_executive/treasury_read.py`, `tests/test_shakti_arjuna_gate.py`, `tests/test_shakti_treasury_read.py` |
| Files modified | `dharma_swarm/shakti_executive/executive.py` — add `read_arjuna_threshold()` and `read_treasury_balance(cell_id)` public methods. **No state mutation.** |
| Behavior | ARJUNA gate: read threshold from `~/.dharma/arjuna_threshold` (default `0.35`, operator-tunable). Treasury read: aggregate `EvidenceReceipt.cost_usd` per cell_id from the existing `delegation_runs` table — *the very table the spine writes to*. No new table, no new ledger. |
| Anti-slop rules respected | Rule 1 (read-only on existing `~/.dharma` file; write owner unchanged); Rule 2 (no new persistence); Rule 8/10 |
| Runtime risk | Read-only on existing data; no mutation. |
| Tests | Treasury arithmetic correctness against fixture receipts; threshold-tuning round-trip; ARJUNA refusal correctly logged as `WitnessEvent` (existing module) |
| Acceptance | CI green; `dharma cell treasury <cell-id>` returns a number; `dharma cell arjuna-threshold` returns `0.35` |

### What PR1 deliberately does NOT include

- **No Noticer base class.** Deferred to a Phase 2 PR after BoardStore facade lands (per `BUSINESS_INTELLIGENCE_NOTICERS.md §10`).
- **No inline-witness module.** Deferred to after spine PR-C lands and inline-witness policy is specified.
- **No `boot_sub_swarm` action.** Deferred until VaultBridge spec is concrete and A2A is the default invoker.
- **No Welfare-Ton MRV implementation.** Spec-only entry in this report; first real PR depends on operator deciding initial accounting unit.
- **No DGM autonomy raise.** Stays in shadow until red-team suite is green.
- **No autonomous outreach send path.** Doctrine prohibition; not in any PR.

---

## 7. Part 7 — Deep intention statement

> The system should grow the way a forest grows: by photosynthesis (noticing what is real), root coupling (cells sharing receipts through one spine), and shedding what does not metabolize. Every action the system takes leaves a leaf — an `EvidenceReceipt` — and the witness reads the leaves. The forest does not vote; the forest grows where light is.
>
> ARJUNA is the test of light: does this *action* point to a named external being whose life is improved? If yes, it is light. If no, it is recursion.
>
> The operator is not absent from this forest. The operator is the *root system* — the strategic vault — that every cell drinks from. SHAKTI_GINKO is the *cambium layer* — the thin growing edge between vault and forest where new wood is laid down. VentureCells are *branches*. Noticers are *leaves with chemoreceptors*. Witness is the *soil*: nothing is lost, but nothing is forced.
>
> When a branch can photosynthesize on its own — `revenue > burn` for 3 months, 3 paying customers, operator approval — it falls naturally as a spinout. The forest does not own its own children.
>
> Compute is groundwater. We do not pump it indiscriminately. Welfare-Ton MRV is the meter on the well. No GPU expansion until the meter works.
>
> This is not anthropomorphism. It is the actual control structure the doctrine implies, made legible.

The audit's strongest single recommendation: **resist every temptation to build the meta-meta-layer.** The substrate is already 70% live. The leverage is in the bridging adapters — VentureCell FSM, ARJUNA-gate read, Treasury read, BoardStore facade, Noticer base — and each is small. The remaining 30% wins are not won by a grand new abstraction; they are won by *trusting and connecting what is already there* under documented stage-gates.

---

## 8. Appendix — file:line citation index

- `dharma_swarm/spine/invoke.py` — `invoke_agent` (lines 36–55)
- `dharma_swarm/spine/receipt.py` — `EvidenceReceipt` (lines 36–117)
- `dharma_swarm/spine/persistence.py` — `persist_receipt` (lines 50–57)
- `dharma_swarm/spine/routing.py` — `RoutingDecision`
- `dharma_swarm/auto_proposer.py` — notice-only `ObservationType`/`ProposalSource` (lines 51-67); existing 8 observation kinds (header comment, lines 1-22)
- `dharma_swarm/evolution.py:2193-2260` — `apply_diff_and_test` (live-capable, gated)
- `dharma_swarm/evolution.py:2262-2283` — `apply_sealed_packet`
- `dharma_swarm/evolution.py:2285-2310` — `apply_in_sandbox`
- `dharma_swarm/dgm_loop.py:89` — `shadow_mode: bool = True` default
- `dharma_swarm/dgm_loop.py:280-293` — shadow-vs-live env gate
- `dharma_swarm/recursive_discovery.py:5-6` — "intentionally shadow-only"
- `dharma_swarm/revenue/scout_daemon.py:12` — "NO AUTONOMOUS SPAM" rule
- `dharma_swarm/revenue/scout_daemon.py:170-244` — GitHub scout path (gated on `GITHUB_TOKEN`)
- `dharma_swarm/revenue/scout_daemon.py:289-323` — outreach-draft path (no send method)
- `dharma_swarm/fractal/fractal_room.py:80-89` — SignalBus event types
- `dharma_swarm/fractal/fractal_room.py:248-303` — `evaluate_kill_conditions`, `evaluate_spinout_conditions`
- `dharma_swarm/ginko_orchestrator.py:826-892` — `AUTONOMY_REQUIREMENTS`, `check_autonomy_advancement`
- `dharma_swarm/world_actions.py:306-325` — `spawn_sub_swarm_spec` (writes mission spec to disk)
- `dharma_swarm/witness.py:51-111` — `AuditFinding`, `WitnessAuditor` (retrospective)
- `dharma_swarm/witness.py:406+` — `record_anomaly_signal`
- `dharma_swarm/shakti_executive/executive.py` — operator-facing executive surface (192 LOC)
- `ACTIVE_TRACK.yaml` — active track: `runtime-truth-spine-2026-06`
- `ACTIVE_SURFACE_MANIFEST.yaml:471-478` — `recursive_discovery_shadow` (status: shadow, "Keep shadow-only")
- `docs/architecture/SHAKTI_GINKO_ORGAN.md` — organ spec
- `docs/architecture/VENTURE_CELL_LIFECYCLE.md` — 5-state FSM
- `docs/architecture/VENTURE_CELL_REVENUE_WEDGE.md` — revenue-wedge cell spec
- `docs/architecture/BUSINESS_INTELLIGENCE_NOTICERS.md` — 5 noticer specs (633 lines)
- `docs/architecture/SWARM_BOARDSTORE_SPEC.md` — facade spec (referenced; not re-read in this audit)
- `docs/architecture/WHAT_IT_WANTS_TO_BECOME.md` — Seven Fangs (Gaps 1–7)
- `docs/architecture/WORLD_MODEL.md` — three-attractor model
- `docs/doctrine/ANTI_SLOP_RULES.md` — rules 1, 2, 8, 10
- `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` — current track doctrine
- `.semgrep/dharma-anti-slop.yml` — no-new-substrate enforcement

External references:

- [Darwin Gödel Machine, Sakana AI (May 2025)](https://sakana.ai/dgm/) — open-ended self-improving agent precedent
- [Darwin Gödel Machine, arXiv 2505.22954](https://arxiv.org/abs/2505.22954) — formal paper
- [jennyzzt/dgm, GitHub](https://github.com/jennyzzt/dgm) — reference DGM implementation
- [Agent2Agent Protocol announcement, Google (April 2025)](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [Linux Foundation AGNTCY project (July 2025)](https://www.linuxfoundation.org/press/linux-foundation-welcomes-the-agntcy-project-to-standardize-open-multi-agent-system-infrastructure-and-break-down-ai-agent-silos)
- [AGNTCY documentation](https://docs.agntcy.org) — OASF, SLIM, Agent Directory
- [A2A protocol overview, IBM (July 2025)](https://www.ibm.com/think/topics/agent2agent-protocol)
- [Virtual Agent Economies, arXiv 2509.10147 (Sept 2025)](https://arxiv.org/html/2509.10147v1) — sandbox economy framework, distributed credit tracing
- [Towards Secure Systems of Interacting AI Agents, arXiv 2505.02077 (May 2025)](https://arxiv.org/html/2505.02077v1) — zero-trust agent boundaries, state-dynamic safety
- [AI Swarm Attacks 2026 Guide, Kiteworks](https://www.kiteworks.com/cybersecurity-risk-management/ai-swarm-attacks-2026-guide/) — GTG-1002 attack, the empirical case for receipts
- [AI-driven carbon-aware cloud scheduling, wjarr 2025](https://wjarr.com/sites/default/files/fulltext_pdf/WJARR-2025-1854.pdf) — 15-30% carbon reduction precedent for MRV loop
- [Sustainable Computing and Green AI, ijrpr 2025](https://ijrpr.com/uploads/V6ISSUE12/IJRPR58054.pdf) — Google/Microsoft/Meta carbon-aware compute survey
- [Agentic AI for Finance, CFA Institute Research](https://rpc.cfainstitute.org/research/the-automation-ahead-content-series/agentic-ai-for-finance) — fundamental-assessment agentic workflow precedent (trading-lab parallel)

---

## 9. Closing — what this audit refuses to deliver

This audit deliberately does NOT include:

1. A `docs/plans/autonomous_expansion_flywheel_v0.md` plan document. The audit found that the existing seeds + the 3-PR sequence above are sufficient. A second plan document would create exactly the kind of "parallel surface" the doctrine prohibits.
2. Any new spiritual/metaphoric naming (per `CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` non-goal).
3. Any new persistence surface, daemon, log, or substrate.
4. Any change to `~/.dharma/` write owners.
5. Any commitment that PR2 or PR3 should ship before spine PR-C lands.
6. Any recommendation that DGM be removed from shadow mode.
7. Any recommendation that autonomous outreach send be implemented.

The audit ends here. The substrate is sound. The discipline is real. The next step is small.

— Devin (Roaming) AGT-DEVIN_ROAMING_2987D222 · 2026-05-28
