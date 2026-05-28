# Minimal Metabolic Loop v1 — The First Loop That Can Sustain Itself

**Purpose.** Specify, fully, the FIRST autonomous loop that could sustain itself. Not a fantasy loop. One that demonstrably produces value, generates receipts, generates learning, reinforces the organism. Anchored to existing owner surfaces — no new substrate.

**Companion to** `autonomous_activation_map_v1.md`. Companion PR sequence in `autonomous_activation_pr_sequence_v1.md`.

**Active-track defense.** This loop does NOT displace `runtime-truth-spine-2026-06`. It runs entirely in shadow / feature-flagged mode until the truth-spine track closes its blockers.

---

## Why this loop (and not the others)

| Candidate wedge | Verdict | Why |
|---|---|---|
| **Operator Brief Publication** (chosen) | ✅ Selected | (a) Output already exists internally as `daily_operating_brief` markdown; (b) value-out is editorial — a real artifact a real reader can read; (c) no payment infrastructure required for v0 (free issues build credibility ledger first); (d) every claim carries existing `EvidenceReceipt` references; (e) no new compute (text rendering); (f) human-approval gate already in place. |
| Trading Lab (`ginko_*`) | ❌ Deferred | 18 modules, real-money risk, regulatory surface, requires `economic_engine` reinvestment policy *first*. Gated. Empirical floor — keep for the second wedge. |
| Revenue Scout outreach | ❌ Deferred | `scout_daemon` already says "outreach drafts require human approval" — the wedge would be human-authored sales, not autonomous. Sales is downstream; first prove the artifact has readers. |
| Benchmark publication (e.g., SWE-bench style) | ❌ Deferred | High craft cost, needs differentiated benchmark methodology, multi-week setup. Worth doing later; not the first loop. |
| API services / freelance coding | ❌ Deferred | Requires platform integration (Upwork, etc.), customer comms, payment rails. Multi-month setup. |
| Grants / bounties | ❌ Deferred | External approval cycle (weeks–months); not a tight loop. |

**Operator Brief Publication is the only candidate that closes the full loop in ≤ 6 weeks without changing the substrate.**

---

## The Loop, Explicitly

```
┌──────────────────────────────────────────────────────────────────────────┐
│  T+0d  Operator publishes Issue #1 (free)                                │
│         └─ generated from real internal daily_operating_brief            │
│         └─ redacted via operator_brief_publisher allowlist               │
│         └─ human approval before send                                    │
│                                                                          │
│  T+0d  Telemetry receipts                                                │
│         └─ closure_v0.EvidenceReceipt for the publication packet         │
│         └─ economic_engine.record_revenue(0, source=API_SAVINGS) initial │
│                                                                          │
│  T+7d  Reader feedback (or zero) recorded                                │
│         └─ revenue_notes_path picks up reader replies / signups          │
│         └─ daily_operating_brief includes reader_count in next brief     │
│                                                                          │
│  T+7d  KaizenReview                                                      │
│         └─ kaizen_review_from_agentops processes the publication packet │
│         └─ classifies: gate_state (green/red), scope (clean), waste     │
│         └─ produces ONE next-packet recommendation                       │
│                                                                          │
│  T+7d  closure_v0.NextDecision                                           │
│         └─ if accepted: queue Issue #2 packet (same allowed_paths)       │
│         └─ if not accepted: narrow topic; rerun acceptance_test          │
│                                                                          │
│  T+14d Issue #2 published (incorporates learning from #1)                │
│                                                                          │
│  T+30d 3 issues published; if ≥ 3 paying readers or 50 free subs:       │
│         └─ spinout candidate per revenue-wedge.spinout_conditions       │
│         └─ if not: cell stays autonomy_stage 2; continue                 │
│                                                                          │
│  T+60d HARD KILL: if revenue_usd == 0 → fractal_room.evaluate_kill      │
│         └─ no_revenue_after_60_days triggers; cell dissolved             │
│         └─ unspent budget returns to core-ops; memory archived           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Stage-by-Stage Specification (every step has a code owner)

### 1. Trigger (cron, weekly)

| Field | Value |
|---|---|
| Owner surface | `dharma_swarm/cron_runner.py` |
| Schedule | Sunday 09:00 local → emit signal `OPERATOR_BRIEF_PUBLISH_TRIGGER` |
| Pre-condition | `runtime-truth-spine-2026-06` track confirmed open or closed (don't fight active track) |
| Kill condition | `revenue-wedge.autonomy_stage < 2` blocks trigger |

### 2. Input gather (inherit existing aggregator)

| Field | Value |
|---|---|
| Owner surface | `dharma_swarm.daily_operating_brief.DailyOperatingBriefInputs` |
| Inputs | `agentops_reports_dir`, `kaizen_reports_dir`, `yds_ratings_path`, `cost_report_path`, `llm_burn_state_dir`, `docops_check_report_path`, `hot_items_path`, `revenue_notes_path` |
| Output | Internal markdown brief (the existing `render_markdown()` 6-section output) |
| Telos check | Inputs are paths only; cannot inject runtime authority |

### 3. Render publication candidate

| Field | Value |
|---|---|
| Owner surface | **New thin adapter:** `dharma_swarm/revenue/operator_brief_publisher.py` (~150 LOC) |
| Behavior | Reads internal brief markdown; applies `_PUBLIC_SAFE_FIELDS` allowlist (sections: "What happened", "Value produced", "Burn / cost signals" with absolute numbers redacted); strips file paths; redacts customer names; attaches `closure_v0.EvidenceReceipt` references as footnotes (just `receipt_id`, not payload) |
| Output | `revenue/publications/<YYYY-MM-DD>/draft.md` + `manifest.json` (cited receipt IDs, cited fact IDs from `_BriefInput.cited_fact_ids`) |
| Acceptance test | `tests/test_operator_brief_publisher.py` — asserts redaction allowlist enforced; asserts no `~/.dharma` paths leak; asserts manifest contains ≥ 1 receipt reference |
| Rollback | Single new file; `git revert` cleanly. Feature flag `DHARMA_OPERATOR_BRIEF_PUBLISHER_ENABLED` default off |

### 4. Telos / safety review (gates inherited from operator_brief seam)

| Field | Value |
|---|---|
| Owner surface | `dharma_swarm/operator_brief/types.REQUIRED_GATES` = `(CONSENT, BHED_GNAN, STEELMAN, DOGMA_DRIFT)` |
| Behavior | Re-use the existing operator-brief gate pipeline against the **publication candidate** (not the internal brief). If `STEELMAN` fails (no counterargument present), publication blocked. |
| Acceptance test | Publication candidate must pass all 4 gates before progressing |
| Rollback | Gates already enforced; no new code |

### 5. Human approval (mandatory)

| Field | Value |
|---|---|
| Owner surface | `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md §"Human Approval Required For"` — item 2 (external outreach) |
| Behavior | Operator reads `revenue/publications/<date>/draft.md`; either approves (writes `approved.json` with timestamp + signature) or rejects (writes `rejected.json` with reason) |
| Cycle time | ≤ 24h target; if no decision in 48h, auto-rejected (no silent autonomy) |
| Telos check | Human is in the loop for every external artifact; system cannot publish without operator |

### 6. Publish (the actual external action)

| Field | Value |
|---|---|
| Owner surface | The operator (initially manual copy-paste to substack/ghost/email). Automated push deferred until 5 issues published successfully. |
| Persistence | `revenue/publications/<date>/published.json` (URL, platform, timestamp, hash of published text) |
| Telos check | Published text hash must match approved draft hash (no last-minute mutation) |

### 7. Record economic event

| Field | Value |
|---|---|
| Owner surface | `economic_engine.record_revenue` / `record_expense` |
| Behavior | T+0 expense: cost of operator review time (estimated, e.g. 30 min @ rate). T+0 revenue: 0 (free issue). T+7 revenue: any paid subs recorded. |
| Idempotency | Use publication `manifest.json` hash as `idempotency_key` |
| Telos check | `Transaction.telos_approved = True` only if STEELMAN gate passed |

### 8. Generate WorkPacket evidence receipt

| Field | Value |
|---|---|
| Owner surface | `closure_v0.record_evidence_receipt(packet, agentops_fact, ...)` |
| Behavior | The publication itself runs as an AgentOps job: `allowed_files=["revenue/publications/<date>/**"]`, `forbidden_files=["api/**","dashboard/**","dharma_swarm/telos_gates.py","dharma_swarm/spine/**","~/.dharma/**"]`, gate `git diff --check`, `approval.before_commit=true` |
| Output | `reports/agentops/operator-brief-publish-<date>/<ts>/report.json` |
| Receipt | `EvidenceReceipt(success=approval_received)` |

### 9. KaizenReview on the publication packet

| Field | Value |
|---|---|
| Owner surface | `scripts/governance/kaizen_review_from_agentops.py` |
| Behavior | After publication AgentOps run completes, KaizenReview emits gate/scope/commit classifications, waste patterns, ONE next-work-packet recommendation |
| Output | `reports/kaizen/operator-brief-publish-<date>/kaizen_review.json` + `.md` |
| Human YDS | Operator manually rates the published issue's craft/truth/usefulness/beauty/coherence (per `fractal_room.VALID_DIMENSIONS`); writes to `~/.dharma/yds/<date>.json` |

### 10. VSM projection + NextDecision

| Field | Value |
|---|---|
| Owner surface | `closure_v0.project_vsm`, `closure_v0.decide_next` |
| Behavior | Project current state across S1–S5; `decide_next` returns either: `chosen_packet_id = <next publication packet>` (if review accepted) or `chosen_packet_id = None, reason = "evidence_failed"` (if rejected/STEELMAN failed) |
| Confidence floor | Auto-queue only if `confidence ≥ 0.7` |
| Telos check | If `truth_stale` (S4/algedonic/S5 integrity flagged), abort — no auto-queue regardless of review |

### 11. Reader-feedback ingest (closes outer loop)

| Field | Value |
|---|---|
| Owner surface | `daily_operating_brief.DailyOperatingBriefInputs.revenue_notes_path` (already exists as plain text/markdown reader) |
| Behavior | Operator writes reader replies / subscription counts / cancellation notes into `revenue/publications/feedback/<date>.md`; next week's brief ingests it |
| Telos check | Negative reader feedback (`welfare_tons_negative`) → kill condition evaluator triggers; FSM stops the cell |

### 12. KPI update + cell evaluation

| Field | Value |
|---|---|
| Owner surface | `dharma_swarm/fractal/fractal_room.evaluate_kill_conditions`, `evaluate_spinout_conditions` |
| KPIs tracked per loop | `revenue_usd`, `burn_usd`, `days_active`, `days_since_last_packet`, `paying_customers`, `welfare_tons`, `autonomy_stage`, `budget_ratio` |
| Spinout target | `paying_customers ≥ 3` AND `revenue_usd ≥ burn_usd` for 3 consecutive months |
| Kill target | `no_revenue_after_60_days` OR `budget_exceeded` (>1.2× cap) OR `welfare_tons_negative` |

---

## What is value produced

The artifact: **a weekly operator brief**, witness-grade, citing real receipts.

- **For agentic-AI builders:** transparency case studies — how a real solo-operator agentic system reports its own gate state, scope state, waste patterns, anti-slop receipts. The kind of artifact that does not exist in public yet.
- **For researchers:** primary-source evidence of how `closure_v0` / `KaizenReview` / `daily_operating_brief` actually behave under live operation (with hashed identifiers; no internal paths).
- **For operators of similar systems:** a credible benchmark of "did this run produce something a human would pay $X to read."

**Differentiator:** every published claim carries a `receipt_id` footnote. No competitor newsletter does this.

**Concrete pricing path (deferred to T+30d):** free issues 1–3; paid tier $5/mo at issue 4 only if ≥ 50 free subscribers. No paid tier until reader demand is demonstrated.

---

## What receipts are produced

Per loop iteration:

1. `reports/agentops/operator-brief-publish-<date>/<ts>/report.json` — AgentOps run report
2. `reports/agentops/operator-brief-publish-<date>/<ts>/report.md` — human-readable
3. `reports/kaizen/operator-brief-publish-<date>/kaizen_review.json` + `.md` — KaizenReview
4. `closure_v0.EvidenceReceipt` (via `record_evidence_receipt`) — `receipt_id`, `correlation_id`, replay command
5. `revenue/publications/<date>/manifest.json` — cited receipt IDs, redaction allowlist hash
6. `revenue/publications/<date>/published.json` — published URL, platform, timestamp, hash
7. `~/.dharma/economics/transactions.jsonl` — `record_revenue` / `record_expense` entries
8. `~/.dharma/yds/<date>.json` — human YDS rating
9. `runtime_state.SessionEventRecord` — VentureCellFSM state-transition event (if FSM PR landed)

**Every receipt is replayable.** `EvidenceReceipt.replay_command` is the canonical pytest invocation against the AgentOps acceptance test.

---

## What learning is produced

1. **Per-week KaizenReview** — explicit waste patterns and one next-packet recommendation.
2. **VSM projection delta** (`closure_v0.project_vsm`) week-over-week — surfaces S1 success-rate trends, S4 recognition-seed age, truth-stale flags.
3. **Reader feedback signal** — direct ground-truth from outside the swarm. The first signal that does not originate inside the closed loop.
4. **YDS time series** — operator's own quality ratings per dimension, week-over-week. Reveals dimensions that decay.
5. **DocOps drift** — if `docops_check_report_path` shows new corpus issues, surfaces in brief.
6. **Cost-per-issue trend** — `daily_operating_brief` already surfaces LLM burn normalization; per-issue cost should trend down if process improves.

**Recursive-improvement gate (Stage 11 in the map).** Only after **5 consecutive issues** with KaizenReview `gate_state == "all_green"` does `darwin_proposer.py` (proposed module in PR sequence) generate a `DarwinProposalCandidate`. Even then: `shadow_mode=True`. Operator manually decides whether to promote.

---

## What reinforces the organism

The metabolic loop reinforces the organism IFF:

| Reinforcement signal | How it lands |
|---|---|
| **Receipt density grows** | Every issue adds ≥ 9 new receipts (per list above) to the corpus; `daily_operating_brief` increasingly grounded in real, dated evidence rather than internal claims. |
| **Reader signal increases** | `welfare_tons` proxy: reader replies, subscribes, cites the brief. Negative signal (unsubscribes, harm reports) triggers kill condition. |
| **Cost-per-issue decreases** | Process improvements (better redaction allowlist, faster operator review) feed `Transaction.record_expense` reductions; tracked in `economic_engine.snapshot()`. |
| **YDS dimension scores stabilize or rise** | Human rating per dimension is the only authoritative quality signal; system is fitter when scores hold or improve. |
| **VSM projection becomes less stale** | `truth_stale` flag (S4 + algedonic + S5) trends to `False` as recognition seed refreshes weekly. |
| **Kill conditions don't trip** | Survival itself is reinforcement. If the cell survives 60 days with revenue (even $5/mo), the loop has proven self-sustainability at minimum viable scale. |
| **Spinout becomes plausible** | `revenue_exceeds_burn` for 3 consecutive months is the explicit graduation criterion. The first metabolically alive sub-organism. |

If none of these signals appear: kill condition trips and the organism does NOT reinforce. That is the correct outcome. Doctrine: "Expansion that doesn't reinforce: kill."

---

## Existing owner surfaces touched by this loop (full inventory)

- `dharma_swarm/cron_runner.py` — read-only (register one handler)
- `dharma_swarm/daily_operating_brief.py` — read-only (consumer)
- `dharma_swarm/operator_brief/types.py` — read-only (gate constants)
- `dharma_swarm/operator_brief/persistence.py` — read-only
- `dharma_swarm/operator_core/closure_v0.py` — read-only (consumer)
- `dharma_swarm/fractal/fractal_room.py` — read-only (kill/spinout evaluators)
- `dharma_swarm/economic_engine.py` — write via existing API (`record_revenue`, `record_expense`)
- `scripts/governance/kaizen_review_from_agentops.py` — read-only (consumer; runs via subprocess)
- `tools/go_sdk/receipt/` — not touched (decision boundary excludes this loop)
- `dharma_swarm/spine/**` — **NOT TOUCHED** (active-track surface)
- `runtime_state.py` — **NOT TOUCHED** (active-track surface)

**New files added by this loop (across all PRs in the sequence):**

- `dharma_swarm/revenue/operator_brief_publisher.py` — ~150 LOC, the publication renderer
- `dharma_swarm/fractal/venture_cell_fsm.py` — ~150 LOC, FSM driver
- `dharma_swarm/operator_core/kaizen_publisher.py` — ~80 LOC, auto-Kaizen orchestrator
- `dharma_swarm/operator_core/work_packet_proposer.py` — ~120 LOC, packet generator
- `dharma_swarm/economic_engine_policy.py` — ~80 LOC, reinvestment policy (deferred PR)
- `dharma_swarm/operator_core/world_model_witness.py` — ~60 LOC, witness emitter (deferred PR)

**Total new code:** ~640 LOC across 6 thin modules, all behind feature flags. Compare to current repo ~280k LOC. Substrate impact: <0.25%.

---

## The Loop Survives Contact With The World

The Master Prompt's final test, applied to **just this loop**:

| Criterion | Verdict |
|---|---|
| More coherent | ✅ Every step has named owner; no parallel substrate. |
| More metabolically alive | ✅ Produces a real artifact for a real reader; takes external feedback. |
| More reality-grounded | ✅ Every claim carries a receipt; no recursive prose. |
| More replayable | ✅ Every AgentOps run replay-able via `pytest <acceptance_test>`. |
| More witness-capable | ✅ 9 receipts per loop iteration. |
| Survives contact with the world | ✅ Kill condition `no_revenue_after_60_days` ensures organism cannot persist in delusion. |
| Without losing telos | ✅ STEELMAN gate + Jagat Kalyan constraint + human approval before publish. |

If any answer were "no" — this loop would not have been chosen.

— Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`, 2026-05-28
