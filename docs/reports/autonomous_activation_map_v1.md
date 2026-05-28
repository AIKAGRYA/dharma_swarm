# Autonomous Activation Map v1

**Purpose.** Map the eleven-stage autonomous-activation chain from intent to recursive improvement onto **existing owner surfaces** in `dharma_swarm`. Identify, per stage, the missing adapter (if any), and four classes of risk: activation, telos, economic, ecological. Surface operational leverage so the operator can sequence work by yield-per-PR.

**Doctrinal frame (verbatim from operator).** Growth is allowed; unwitnessed growth is not. Autonomy is allowed; unreceipted autonomy is not. Revenue is allowed; revenue that corrupts telos is not. Expansion is allowed; ecologically blind expansion is not.

**Active track defended.** This map does not displace `runtime-truth-spine-2026-06`. It describes the *next* track to consider once truth-spine blockers close. Every stage names a code surface; no stage requires a new substrate.

**Anti-slop posture.** Every "missing adapter" is ≤ 1 thin module, additive, behind a feature flag, with kill conditions and rollback. If a stage has no missing adapter, it is already wired and the proposal does not touch it.

**Cross-PR audit reference.** The 597-line `autonomous_expansion_seed_audit_2026-05-28.md` (PR #369) classified seeds LIVE / SCAFFOLDED / SPEC-ONLY / DORMANT / STALE. This map composes those seeds into a chain.

---

## The Chain

```
Stage 1  intent
       ↓
Stage 2  venture cell instantiation
       ↓
Stage 3  noticer perceives signal
       ↓
Stage 4  task generation (WorkPacket)
       ↓
Stage 5  agent execution (AgentOps worktree run)
       ↓
Stage 6  receipt chain (EvidenceReceipt + Go SDK)
       ↓
Stage 7  benchmark / KPI evaluation (KaizenReview, kill-condition eval)
       ↓
Stage 8  value generation (revenue / capability output)
       ↓
Stage 9  compute reinvestment (EconomicEngine budget allocation)
       ↓
Stage 10 world-model update (subconscious dream cycle, zeitgeist)
       ↓
Stage 11 recursive improvement (NextDecision + Darwin candidate)
```

Each row below names the existing owner surface, the missing adapter (if any), and the four risk classes plus operational leverage. Leverage is yield-per-PR ordinal, 1 highest, 11 lowest.

---

## Stage 1 — Intent

| Field | Value |
|---|---|
| **Existing owner surface** | `docs/governance/ACTIVE_TRACK.yaml` (machine-readable intent); `dharma_swarm/operator_brief/types.py` (`_BriefInput`, `_DraftedBrief`) for operator-side intent capture; `closure_v0.TelosObjective` (`jagat_kalyan`, `purpose`) for telos-level intent. `auto_proposer.py:136+` for autonomous proposal cards (still operator-approved). |
| **Missing adapter** | None. Active track is a YAML; operator brief is a code surface; `closure_v0.TelosObjective` is a dataclass. The chain reads `ACTIVE_TRACK.yaml` already (via `scripts/governance/check_track_status.py`). |
| **Activation risk** | Low. Intent is read-only; cannot diverge from declared track without CI failure. |
| **Telos risk** | Low. `TelosObjective.objective_id = "jagat_kalyan"` is the constitutional anchor. **Mitigation:** every `WorkPacket` carries `objective_id`; downstream stages refuse packets where `objective_id != "jagat_kalyan"`. |
| **Economic risk** | Negligible — file reads. |
| **Ecological risk** | Negligible. |
| **Operational leverage** | **11** (lowest). Already wired; PR yield is zero. |

---

## Stage 2 — Venture Cell Instantiation

| Field | Value |
|---|---|
| **Existing owner surface** | `dharma_swarm/fractal/fractal_room.py` — `FractalRoom`, `VentureCellV1`, `autonomy_stage 1..5`. Kill-condition evaluators l.248–303; spinout evaluators l.305+. `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` declares the first cell (`revenue-wedge`, status `proposed`). `closure_v0.VentureCellRef` for downstream binding. |
| **Missing adapter** | One thin FSM driver: `dharma_swarm/fractal/venture_cell_fsm.py` (~150 LOC) — drives `autonomy_stage` 1→2→3→4→5 transitions against `evaluate_kill_conditions` / `evaluate_spinout_conditions`. Reads cell config from YAML, writes stage transitions to `runtime_state.SessionEventRecord`. No new persistence. |
| **Activation risk** | **Medium.** FSM that mutates `autonomy_stage` is load-bearing. **Mitigation:** behind `DHARMA_VENTURE_CELL_FSM_ENABLED` env flag; default off. All transitions require human approval per `VENTURE_CELL_REVENUE_WEDGE.md §"Human Approval Required For"`. |
| **Telos risk** | **Medium.** A misfiring spinout evaluator could declare a cell graduated when it hasn't met `revenue-wedge.spinout_conditions` (3 paying customers, 3 months revenue>burn). **Mitigation:** spinout decisions require human approval; FSM only proposes, never executes. Use `closure_v0.NextDecision.confidence` floor of 0.7 for any auto-recommended transition. |
| **Economic risk** | Medium. A cell whose kill-condition `no_revenue_after_60_days` doesn't trigger drains budget. **Mitigation:** Kill condition is already implemented as a pure function; FSM runs evaluator daily via `cron_runner` and surfaces results in `daily_operating_brief`. Budget cap enforced by `economic_engine.allocate_budget`. |
| **Ecological risk** | Low. FSM is one cron-driven evaluation; cost ≈ 0. |
| **Operational leverage** | **3.** Without an FSM driver, the kill-condition logic is unreachable in the live loop and the `revenue-wedge` cell stays `proposed` forever. This unlocks Stage 8 and Stage 11. |

---

## Stage 3 — Noticer Perceives Signal

| Field | Value |
|---|---|
| **Existing owner surface** | `dharma_swarm/auto_proposer.py:136+` — the canonical notice-only template. `dharma_swarm/revenue/scout_daemon.py` (443 LOC) — 80% of `MarketScanNoticer`. `dharma_swarm/subconscious_v2.py` (724 LOC, `SubconsciousAgent`, `run_dream_cycle`) — passive resonance / dream-channel noticing. `dharma_swarm/shakti_zeitgeist_executive.py` (353 LOC, `ExecutiveSignal`, `ScoredOpportunity`) — external opportunity scoring. `docs/architecture/BUSINESS_INTELLIGENCE_NOTICERS.md` — spec for five BI noticers. `tools/world_scout_go/`, `tools/world_signal_ingestor_go/` — Go ingestion. |
| **Missing adapter** | Thin RBAC wrapper enforcing notice-only contract (`docs/architecture/BUSINESS_INTELLIGENCE_NOTICERS.md §0`): noticers run under role `noticer`; BoardStore facade refuses executor verbs. Estimate ~100 LOC under `dharma_swarm/noticers/base.py`. **`scout_daemon` already enforces "no autonomous spam".** The other four BI noticers are spec-only. |
| **Activation risk** | Low — notice-only contract is structurally safe. **Mitigation:** RBAC check refuses every executor verb; CI test asserts each noticer's exported tool surface ⊆ `{read, write_proposal_card, write_witness}`. |
| **Telos risk** | **Medium.** A miscalibrated `RankingSignals` vector (per BI Noticers spec §1.3) could surface anti-telos opportunities. **Mitigation:** v1 explicitly forbids learned ranking (per BI Noticers §1.3, "v1 forbids learned ranking"); all signals are fixed weights from operator priors (`arjuna_weight`, `vision_file_proximity`, `recency`, `blocker_proximity`). |
| **Economic risk** | **Medium-high.** External HTTP fetches in `scout_daemon` and `world_scout_go` cost rate-limit quota and time. **Mitigation:** cron cadence (6 h for MarketScan, 24 h for Ideation, per BI Noticers spec); rate-limit witnessing under `~/.dharma/revenue_scout/` already exists; `economic_engine.record_expense(category=ExpenseCategory.API_CALLS)`. |
| **Ecological risk** | Low–medium. Background daemons hum continuously. **Mitigation:** cron-driven only (per `cron_runner.py`); `subconscious_v2` runs dream cycles on schedule, not in a loop. Total noticer wall-clock should be capped (target: <60 min/day of compute). |
| **Operational leverage** | **5.** Scout daemon is already 80% there; the four missing BI noticers are not blocking Stage 8 (the first wedge does not need them). Leverage matters once the second cell spins out. |

---

## Stage 4 — Task Generation (WorkPacket)

| Field | Value |
|---|---|
| **Existing owner surface** | `dharma_swarm/operator_core/closure_v0.WorkPacket` (dataclass, frozen, with `__post_init__` validation: correlation_id, allowed_paths, acceptance_test, rollback_plan all required; allowed/forbidden path overlap rejected; `review_tier ∈ {auto, review, human}`). AgentOps JSON packet schema (`docs/governance/AGENTOPS.md`). `closure_v0.TelosObjective` and `VentureCellRef` bound on every packet. |
| **Missing adapter** | One thin generator: `dharma_swarm/operator_core/work_packet_proposer.py` (~120 LOC) — takes a noticer's `CardProposal` (Stage 3 output), enriches with `correlation_id`, `cell_id`, `objective_id`, declares `allowed_paths`/`forbidden_paths`/`acceptance_test`/`rollback_plan`, writes JSON to `agentops_packets/`. **Operator approval still required before packet runs.** |
| **Activation risk** | Low — `WorkPacket.__post_init__` rejects malformed packets at construction. |
| **Telos risk** | Low. Every packet carries `objective_id="jagat_kalyan"`; downstream gates reject mismatch. **Mitigation:** `closure_v0.WorkPacket` is frozen; cannot mutate post-construction. |
| **Economic risk** | Low. Packet generation is cheap. |
| **Ecological risk** | Negligible. |
| **Operational leverage** | **4.** Without a packet proposer, noticer output stays as cards and never reaches AgentOps. This is the critical glue between Stage 3 and Stage 5. |

---

## Stage 5 — Agent Execution

| Field | Value |
|---|---|
| **Existing owner surface** | AgentOps v0 runner (per `docs/governance/AGENTOPS.md`) — bounded worktree, scope gate, declared gates, structured `reports/agentops/<job>/<ts>/report.json`, optional local commit candidate. Never merges or pushes. `dharma_swarm/agent_runner.py` (grandfathered, 3691→4060 LOC ceiling) — the production execution surface. External worker `AGT-DEVIN_ROAMING_2987D222` operates under `external_worker_evidence_only` authority. Approval flags `approval.before_commit` / `approval.before_merge` always respected. |
| **Missing adapter** | None for v0. **AgentOps already runs work packets and produces evidence.** A future thin bridge could route `WorkPacket` (Stage 4) → AgentOps JSON packet automatically, but for v0 the operator copies / renders manually. |
| **Activation risk** | Low. AgentOps refuses dirty worktrees, refuses scope-violating diffs, refuses merge/push commands. **Already production-tested.** |
| **Telos risk** | Low. Scope gate is structural — `forbidden_files` includes `api/**`, `dashboard/**`, `dharma_swarm/telos_gates.py`. Telos surfaces cannot be modified by an AgentOps run. |
| **Economic risk** | **Medium.** Long agent runs (Devin sessions, Codex runs) consume LLM tokens and human review time. **Mitigation:** `daily_operating_brief` already ingests `llm_burn_state_dir` and surfaces token usage with span/cost normalization. Per-cell budget cap in `revenue-wedge` (50,000 tokens). |
| **Ecological risk** | **Medium.** Token spend is the dominant cost. **Mitigation:** packet `acceptance_test` must be cheap (≤ 1 min CI); `monthly_burn_target = 2000` USD for revenue-wedge. |
| **Operational leverage** | **8.** Already operational; further leverage gains require Stage 4 (packet proposer) and Stage 7 (KaizenReview link) — those PRs unlock this stage's continuous use. |

---

## Stage 6 — Receipt Chain

| Field | Value |
|---|---|
| **Existing owner surface** | `tools/go_sdk/receipt/receipt.go` — canonical Go SDK for evidence receipts. Boundary explicit: "this SDK emits receipts only. It does not decide, dispatch, write runtime DB, write ontology DB, or call Python policy." Hashing canon: `content_hash = sha256(payload)`, `event_uid = hex12(sha256(source\0source_url\0content_hash))`, `receipt_id = hex12(sha256(correlation_id\0event_uid))`. `dharma_swarm/operator_core/closure_v0.EvidenceReceipt` — Python dataclass (`__post_init__` enforces `success == (test_exit_code == 0)`; raises `EvidenceInconsistentError` on mismatch). `dharma_swarm/operator_core/go_evidence_bridge.py` — Python ↔ Go boundary. `dharma_swarm/spine/**` — dispatch receipts (per active-track surfaces). |
| **Missing adapter** | None. Receipt chain is **the most complete part of the system** — Go SDK + Python bridge + `closure_v0` together enforce: receipt before decision, hash determinism, success/failure invariant, replay command. |
| **Activation risk** | Low — receipt schema versioned (`go_evidence_receipt.v0`); deterministic hashes verified by tests. |
| **Telos risk** | Low. `EvidenceReceipt` is purely descriptive; cannot itself violate telos. |
| **Economic risk** | Negligible — JSON writes. |
| **Ecological risk** | Negligible — receipts are tiny. |
| **Operational leverage** | **10.** Already done. Don't touch. |

---

## Stage 7 — Benchmark / KPI Evaluation

| Field | Value |
|---|---|
| **Existing owner surface** | `dharma_swarm/daily_operating_brief.py` — daily aggregator over `reports/agentops/**/report.json`, `reports/kaizen/**/kaizen_review.json`, YDS ratings, cost report, LLM burn state dir, DocOps inventory. `scripts/governance/kaizen_review_from_agentops.py` — KaizenReview bridge (one input dir → one JSON+MD review with gate classification, scope classification, commit classification, waste patterns, stop-doing items, one next-packet recommendation). `closure_v0.KaizenReviewLink` — typed link object. `fractal_room.evaluate_kill_conditions` / `evaluate_spinout_conditions` — pure-function KPI predicates. `docs/governance/HUMAN_YDS_LEDGER.md` — human-authored YDS rating ledger. |
| **Missing adapter** | One thin orchestrator: `dharma_swarm/operator_core/kaizen_publisher.py` (~80 LOC) — after each AgentOps run, automatically invokes `kaizen_review_from_agentops` and writes `KaizenReviewLink` to a discoverable index (existing `reports/kaizen/index.json` pattern). Optional: a `closure_v0`-typed KPI emitter that pushes `cell_kpis` dict into `fractal_room` for kill-condition evaluation. |
| **Activation risk** | Low — KaizenReview is already strictly advisory (`human_yds_rating` always `null`). |
| **Telos risk** | **Medium.** Auto-classifying gate health and recommending next packet without human oversight can drift telos. **Mitigation:** every KaizenReview is read by the human operator via `daily_operating_brief`; YDS rating remains human-only; auto-recommendation goes to a queue, not to direct execution. |
| **Economic risk** | Low — review is local file processing. |
| **Ecological risk** | Negligible. |
| **Operational leverage** | **2.** Once auto-publishing KaizenReview is wired, every AgentOps run produces a review automatically, which feeds `daily_operating_brief` and `kill_conditions`. High yield. |

---

## Stage 8 — Value Generation

| Field | Value |
|---|---|
| **Existing owner surface** | `dharma_swarm/revenue/spine.py` — `RevenueSpine`, `RevenueTarget`, `TargetStatus`, `OutreachChannel`. `dharma_swarm/revenue/intelligence.py` — `RevenueIntelligenceIngestor`. `economic_engine.record_revenue(amount_usd, source, ...)` — file-native ledger at `~/.dharma/economics/transactions.jsonl`. `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` — first cell, target `10,000 USD`, monthly burn `2,000`. Trading Lab (18 `ginko_*.py` modules per prior audit) — empirical floor / alternative wedge candidate. |
| **Missing adapter** | The actual **publication / sales surface**. The proposal in Deliverable 2 picks **Operator Brief Publication** as the concrete wedge: render `daily_operating_brief` outputs as a paid newsletter / report PDF. Adapter: `dharma_swarm/revenue/operator_brief_publisher.py` (~150 LOC) — converts internal `daily_operating_brief` to a public-safe artifact, redacts internal paths, attaches `closure_v0.EvidenceReceipt` references for credibility, writes to `revenue/publications/<date>/`. Human approval required before send. |
| **Activation risk** | **Medium-high.** Publishing anything is the first time the swarm produces an artifact for an external audience. **Mitigation:** explicit allowlist of fields safe to publish; redaction test in CI; human approval gate (`approval.before_publish = true`); kill condition `welfare_tons_negative` already exists in `fractal_room`. |
| **Telos risk** | **High.** "Revenue that corrupts telos" is the explicit failure mode. **Mitigation:** Jagat Kalyan constraint in `VENTURE_CELL_REVENUE_WEDGE.md §"Jagat Kalyan Constraint"`: "Revenue without welfare is extraction." Every published brief must include a welfare assessment per `KaizenReview`. Topics restricted to: agentic-AI operations transparency, anti-slop case studies, governance receipts. **Forbidden topics:** competitive intel that names harmed parties, anything resembling adtech / clickbait / dark patterns. |
| **Economic risk** | **Medium.** Publication infrastructure (substack, ghost, self-hosted) costs $0–20/mo. **Mitigation:** start with free tier; first 3 issues free; price only after 3 paying readers via `revenue-wedge.spinout_conditions`. |
| **Ecological risk** | Low — text artifacts. |
| **Operational leverage** | **1** (highest). Without a value-generation surface that produces a real external artifact, every stage upstream is a closed loop. This is what makes the metabolic loop *metabolic* rather than ornamental. |

---

## Stage 9 — Compute Reinvestment

| Field | Value |
|---|---|
| **Existing owner surface** | `dharma_swarm/economic_engine.py` — `EconomicEngine`, `BudgetState` (`training`, `inference`, `operations`, `reserve`, `reinvestment`), `allocate_budget`, `can_afford_training`, `record_revenue`, `record_expense`. File-native at `~/.dharma/economics/transactions.jsonl` and `budget.json`. Idempotency key support. Correlation ID enrichment from `dharma_swarm.correlation_context`. |
| **Missing adapter** | One reinvestment policy: `dharma_swarm/economic_engine_policy.py` (~80 LOC) — on every `record_revenue`, applies a fixed split (e.g., 40% operations / 30% reinvestment / 20% reserve / 10% training) via `allocate_budget`. Policy is data-driven (`~/.dharma/economics/policy.json`), with explicit gates: never auto-spend on training above an operator-approved cap. |
| **Activation risk** | **Medium.** Auto-allocation could lock budget into wrong category. **Mitigation:** allocation is bookkeeping only; *spending* requires `economic_engine.can_afford_training()` + explicit human approval for training jobs per `VENTURE_CELL_REVENUE_WEDGE.md §"Human Approval Required For"`. |
| **Telos risk** | Low. Allocation is internal; cannot violate telos. |
| **Economic risk** | **Medium-high.** Wrong split starves the wedge or over-reserves. **Mitigation:** policy file is operator-edited; default split is conservative; daily brief surfaces `BudgetState`. |
| **Ecological risk** | Low — only matters when reinvestment triggers training (gated). |
| **Operational leverage** | **7.** Without revenue (Stage 8) this is unreachable. Once revenue >0, this becomes mechanical. |

---

## Stage 10 — World-Model Update

| Field | Value |
|---|---|
| **Existing owner surface** | `dharma_swarm/subconscious_v2.py` (724 LOC) — `SubconsciousAgent`, `DreamAssociation`, `ResonanceType`, `WakeTrigger`, `run_dream_cycle`, `select_dense_files`. `dharma_swarm/shakti_zeitgeist_executive.py` (353 LOC) — `ScoredOpportunity`, `ExecutiveSignal`, `WarrantPressure`. `closure_v0.VSMProjection` — 5-system viable-systems-model projection (S1 open packets, S2 collisions, S3 blocked, S4 recognition seed age, S5 kernel signature match). `WORLD_MODEL.md`. Memory kernel landing gate: `make memory-kernel-readiness` (81 adapters, 7 ready surfaces, shadow-mode + read-only only). |
| **Missing adapter** | One thin adapter: `dharma_swarm/operator_core/world_model_witness.py` (~60 LOC) — after each `closure_v0.NextDecision`, emit a `WitnessEvent` capturing the (VSMProjection, KaizenReviewLink, NextDecision) triple, queryable by `subconscious_v2.run_dream_cycle` next cycle. No new persistence — uses existing `runtime_state.SessionEventRecord`. |
| **Activation risk** | Low — witness emission is one append to an existing table. |
| **Telos risk** | Low. World-model is descriptive. |
| **Economic risk** | Low. |
| **Ecological risk** | **Medium.** Dream cycles read 15 dense files per `select_dense_files` default. **Mitigation:** dream cadence is operator-configured (default off?); memory kernel landing gate enforces shadow-mode + read-only; existing rule "Rule on no second event log" — proposal uses existing event log only. |
| **Operational leverage** | **6.** Important for long-term recursive improvement (Stage 11) but not blocking the first wedge. |

---

## Stage 11 — Recursive Improvement

| Field | Value |
|---|---|
| **Existing owner surface** | `closure_v0.decide_next(projection, candidates, review, ...)` — already returns different `NextDecision` for success vs failure (the entire purpose of `closure_v0`, proven by `tests/fixtures/organism_closure_v0/`). `closure_v0.DarwinProposalCandidate` (data only; `validate_darwin_candidate` requires `evidence_refs`, `kaizen_review_refs`, `correlation_id`). `dharma_swarm/evolution.py` (grandfathered, real apply path l.2193–2310 via `DiffApplier`; `dgm_loop.py:89` defaults `shadow_mode=True`). |
| **Missing adapter** | One thin proposer: `dharma_swarm/operator_core/darwin_proposer.py` (~80 LOC) — after N consecutive successful packets (e.g., N=5) on the same `cell_id`, propose a `DarwinProposalCandidate` to `evolution.py`. **Stays `shadow_mode=True`** for v0 — proposal generates, but `DiffApplier` only writes to a shadow worktree. Operator promotes manually. |
| **Activation risk** | **High.** This is the only stage that touches `evolution.py`. **Mitigation:** Hard-coded `shadow_mode=True` in adapter; CI test asserts the adapter never sets `shadow_mode=False`; `validate_darwin_candidate` enforces evidence + kaizen refs + correlation_id. No PR in the activation sequence (Deliverable 3) flips this default. |
| **Telos risk** | **High.** Self-modification is the forbidden zone. **Mitigation:** Shadow-mode is mandatory; every proposed candidate requires (i) evidence refs (`EvidenceReceipt.receipt_id`), (ii) kaizen refs (`KaizenReviewLink.review_id`), (iii) human review. Per Master Prompt forbidden list: "uncontrolled self-modification" — not proposed. |
| **Economic risk** | Low (shadow mode). |
| **Ecological risk** | **Medium** if shadow-mode were lifted. **Mitigation:** stay in shadow-mode for the entire activation sequence; lifting it is an entirely separate decision outside this map. |
| **Operational leverage** | **9.** Important but late. Don't touch until the wedge is producing revenue and Stages 7–9 are running clean for ≥ 30 days. |

---

## Operational Leverage Ranking (highest yield-per-PR first)

1. **Stage 8 — Value Generation** (Operator Brief Publication wedge). Without this, every other stage is closed-loop.
2. **Stage 7 — Auto KaizenReview publisher.** One thin orchestrator makes every AgentOps run feed `daily_operating_brief` and `kill_conditions` automatically.
3. **Stage 2 — VentureCell FSM driver.** Unlocks live kill-condition evaluation; otherwise `revenue-wedge` stays `proposed`.
4. **Stage 4 — WorkPacket proposer.** The critical glue between noticer cards and AgentOps runs.
5. **Stage 3 — BI Noticer base class** (`Noticer` protocol + RBAC). Scout daemon already covers 80%; the four spec-only noticers (Viability, Opportunity, Ideation, Quality) are deferred.
6. **Stage 10 — World-model witness adapter.** Feeds Stage 11.
7. **Stage 9 — Reinvestment policy.** Unblocked once revenue arrives.
8. **Stage 5 — Agent execution.** Already production-tested; gains come from Stages 4 + 7.
9. **Stage 11 — Darwin proposer.** Shadow-mode only; not in the first wedge.
10. **Stage 6 — Receipt chain.** Already done.
11. **Stage 1 — Intent.** Already done.

---

## What this map does *not* propose

- ❌ New persistence surfaces. Every stage uses `runtime_state.py` event log, `reports/agentops/`, `~/.dharma/economics/`, or `agentops_packets/` — all already declared owners.
- ❌ New governance documents (besides this report, Deliverable 2, and Deliverable 3 — all under `docs/reports/`, none claim authority over an owned fact).
- ❌ Changes to grandfathered modules. Every proposed thin module is a new file ≤ 150 LOC.
- ❌ Changes to active-track surfaces (`dharma_swarm/spine/**`, `orchestrator.py`, `agent_runner.py`, `runtime_state.py`, etc.).
- ❌ Changes to `~/.dharma` writer set (Rule 1).
- ❌ Changes to the receipt chain (Stage 6 is done; don't touch).
- ❌ Lifting `evolution.py` `shadow_mode=True`.
- ❌ Autonomous outreach or payment. Human-approval gates from `VENTURE_CELL_REVENUE_WEDGE.md` remain enforced.

---

## Final test (per Master Prompt)

> Does this make Dharma Swarm more coherent, more metabolically alive, more reality-grounded, more replayable, more witness-capable, and more able to survive contact with the world WITHOUT losing its telos?

| Criterion | How this map satisfies it |
|---|---|
| **More coherent** | One named owner per stage; no parallel substrate; no new governance docs that compete with existing owners. |
| **More metabolically alive** | The chain *closes*: Stage 8 produces a real artifact a real customer can read; Stage 9 routes revenue back to budget; Stage 11 (shadow only) proposes improvements based on evidence. |
| **More reality-grounded** | Every stage has a line-numbered code surface or YAML file; no recursive-architecture prose; no new ontologies. |
| **More replayable** | Every receipt carries `replay_command`; every `WorkPacket` carries `acceptance_test`; `closure_v0` fixtures already replay the decision loop deterministically. |
| **More witness-capable** | Every stage emits to an existing witness sink: `runtime_state.SessionEventRecord`, `reports/agentops/`, `reports/kaizen/`, `closure_v0.EvidenceReceipt`. |
| **More able to survive contact with the world** | Kill conditions live in `fractal_room.evaluate_kill_conditions`; budget cap in `revenue-wedge`; human-approval gates on outreach, spending, publication, spinout. |
| **WITHOUT losing telos** | `closure_v0.TelosObjective.objective_id = "jagat_kalyan"` flows through every `WorkPacket`; Jagat Kalyan constraint enforced on every published artifact; `evolution.py` stays shadow-mode. |

If any future stage cannot answer **yes** to all seven criteria: do not build it.

— Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`, authority `external_worker_evidence_only`, 2026-05-28
