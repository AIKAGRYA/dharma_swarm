---
title: Arjuna Customer Discovery Stream — Open Consensus Track
path: docs/plans/ARJUNA_CUSTOMER_DISCOVERY_STREAM_2026-07-18.md
slug: arjuna-customer-discovery-stream-2026-07-18
doc_type: working_plan
status: active
summary: Standing residual-stream discovery track answering WHO IS THE CUSTOMER — seeded by a 16-agent deliberation (6 evidence lenses, 4 decorrelated theses, 5-judge ranked vote, 4/5 consensus round 1) with every dissent preserved, a fleet build order that wires receipts into swarm fitness, and a cycle protocol under which recurring research runs must verifiably compound or report themselves stalled.
source:
  provenance: repo_local
  kind: operator_prompt
  origin_signals:
  - CLAUDE.md
  - docs/offers/agentic-code-governance-sprint.md
  - reports/revenue_wedge/first_cash_receipt_status.md
  - dharma_swarm/revenue/spine.py
  - dharma_swarm/archive.py
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- market_research
- software_engineering
- evolutionary_systems
stigmergy:
  meaning: The customer question stays open as a residual stream — cycles append evidence and votes, counters only move forward, dissents are constraints not noise.
  state: active
  semantic_weight: 0.8
  coordination_comment: Subordinate to repository authority; consensus here is advisory input to the operator, never merge or spend authority.
  trace_role: coordination_trace
---
# Arjuna Customer Discovery Stream — Open Consensus Track

## How this document works (cycle protocol — read before appending)

This is a standing residual-stream discovery track in the
`AGENT_EMERGENT_WORKSPACES/residual_stream` lineage: contributions append,
closed sections never rewrite, dissents persist as constraints. It exists to
keep the question WHO IS THE CUSTOMER under live, multi-agent, evidence-bound
deliberation until external receipts make it moot.

**Verifiable compounding contract.** Every research cycle appended below MUST:

1. Open with a dated `## Cycle NNN` header naming the prior cycle it builds on
   (by header and short content hash: `git log -1 --format=%h -- <this file>`
   at append time) — no orphan cycles.
2. Attack at least one numbered Open Question from the latest round (or add a
   new one with evidence for why it outranks the existing list).
3. Move at least one of the stream counters, stated explicitly in a
   `counters:` line — `evidence_items` (new cited claims), `questions_resolved`
   (with the resolving citation), `questions_opened`, `receipts_recorded`
   (external contact or payment receipts, cited to their ledger path), or
   `wires_landed` (fitness/telemetry wiring merged to main, cited by commit).
   Counters only move forward. A cycle that moves nothing MUST record itself
   as `STALLED` with the blocker named — a stalled cycle with an honest
   blocker is compliant; a cycle with prose and no counter movement is not.
4. Carry citation-or-silence: `file:line`, runnable command, or URL on every
   load-bearing claim (CLAUDE.md, operator-ratified 2026-07-10).
5. Re-vote only when new evidence contradicts the standing consensus; a
   re-vote uses the same shape (decorrelated judge lenses, ranked ballots,
   dissents preserved) and appends — it does not edit Round 1.

A recurring Routine (fresh session per fire) executes cycles automatically;
the operator can pause it at any time. Consensus in this stream is advisory
to the operator; it grants no merge, spend, or outreach authority. Fleet
build items land through the normal PR discipline under whichever track owns
the touched surface.

---

# WHO IS THE CUSTOMER — Deliberation Record (Residual Stream)

*Seed document for a standing discovery track. Append below; do not rewrite closed sections. Every claim carries a `file:line`, runnable command, or URL per citation-or-silence (CLAUDE.md, operator-ratified 2026-07-10). Deliberation run: 2026-07-18, six evidence lenses → four theses → five decorrelated judges → one voting round.*

---

## 1) The Question

WHO IS THE CUSTOMER — what revenue seam should the organism open that produces **real external receipts** AND **compounds the evolution of the swarm itself**?

Constraints in force:
- Spine objective `revenue-external-humans-served` is covered by exactly one track, `darshan-publication-2026-07` (CLAUDE.md active-portfolio digest; `docs/governance/ACTIVE_TRACK.yaml`).
- Solo human operator + AI agent fleet; the repo self-governs (merge agents, ratchets, adversarial review).
- KEEL doctrine names a dated trigger, 2026-10-17, by which external contact must exist — **but the date is currently unciteable in this checkout**: `grep -rn '2026-10-17' /home/user/dharma_swarm` → zero matches; `docs/plans/THE_KEEL_2026-07-17.md` is referenced (`docs/prompts/TOKEN_TREASURY_V0_GOAL_2026-07-18.md:14,68-69`) but absent. Re-derive from the operator's copy before treating as binding.
- Transcendence Principle (CLAUDE.md): decorrelated perspectives, no groupthink; every governance/selection mechanism scored against its diversity cost.

---

## 2) Evidence — Six Lenses

### Lens A — Web market research: AI code review / PR automation / merge governance
- AI code review is a real paid category: CodeRabbit $60M Series B at ~$550M, 8,000+ paying customers, ~$40M ARR est. Apr 2026 (https://techcrunch.com/2025/09/16/coderabbit-raises-60m-valuing-the-2-year-old-ai-code-review-startup-at-550m/ ; https://sacra.com/c/coderabbit/).
- Review layer prices $20–48/user/mo (CodeRabbit $24/$48, Greptile $30, Graphite $40); merge-queue layer commoditized at $12–21/user/mo (Mergify, Aviator) (https://www.coderabbit.ai/ ; https://mergify.com/pricing ; https://www.aviator.co/merge-queue).
- Demand driver = agent-PR flood: GitHub merged PRs 25M/mo (Jan 2023) → 90M/mo (Mar 2026); ~12x longer to review an AI PR than to generate one; GitHub shipped PR caps (https://thenewstack.io/ai-generated-code-crisis/).
- White space: nobody sells receipted, adversarial, fleet-scale MERGE GOVERNANCE — the gap between Aviator Verify (acceptance-criteria verification, just launched: https://www.aviator.co/verify) and org-level agent identity/policy (Microsoft Agent 365; https://fortune.com/2026/06/23/ai-agents-verifiable-execution-enterprise-trust-najwa-aaraj-tii/). Agent vendors (Devin, Factory) are structurally conflicted — they cannot audit their own fleets (https://devin.ai/pricing ; https://factory.ai/pricing).
- The repo already dogfoods this exact layer: `scripts/runtime/pr_merge_control.py`, `scripts/governance/check_claim_evidence_binding.py`, `scripts/runtime/ci_truth.py`, `scripts/governance/arena_truth_report.py` (all verified present).
- **Lens A's customer:** VP Eng / platform lead, 50–500 devs, heterogeneous agent fleet, drowning in agent PRs.

### Lens B — Adjacent solo-operator monetization lanes
- Eval SaaS platform lane: venture-saturated (LangChain $1.25B, 6k+ LangSmith customers); solo entry = 6–18 months to first dollar (https://techcrunch.com/2025/10/21/open-source-agentic-startup-langchain-hits-1-25b-valuation/).
- Evals-as-expertise is where small teams get paid: Hamel Husain/Shreya Shankar Maven course at $5,000/seat, 4,500+ students in 15 months (https://maven.com/parlance-labs/evals) — strongest solo-scale payment proof in the pack.
- Paid publications: 66-day median to first dollar; tech-niche free→paid ~8%; honest year-one base case hundreds of $/mo (https://www.beehiiv.com/blog/the-state-of-paid-newsletters-2026 ; https://bestwriting.com/substack-statistics). Contemplative-niche payers exist but are personality-anchored (https://on.substack.com/p/grow-34-amanda-yates-garcia).
- Fastest lane: productized audit / paid design-partner engagement, $1.5K–$5K, 2–6 weeks to close; costs 150–200 operator outreach conversations for 3–5 partners — the one input only the human can supply (https://www.bvp.com/atlas/design-partners-the-pre-launch-edge-most-ai-founders-ignore ; https://review.firstround.com/sierra-design-partnership/).
- Open-core runtime lane: years to first dollar; avoid (https://sacra.com/c/langchain/).

### Lens C — Codebase sellability audit (entanglement gradient)
- **PORTABLE (days):** hygiene delta-ratchet — stdlib-only, zero dharma imports, generic `--base-ref/--head-ref` CLI (`scripts/governance/hygiene/delta_ratchet.py:44-57,97-166,366-380`; runnable: `python3 scripts/governance/hygiene/delta_ratchet.py --base-ref origin/main --head-ref HEAD`).
- **NEEDS-EXTRACTION (1–4 wks):** DocOps integrity gate (`scripts/docops/check_docops_integrity.py:24,63,734-757`); CI truth contract + parity binding (`scripts/runtime/ci_truth.py:14-18,42-43,53-64`); fail-closed automerge lane with "absence is NOT green," hardened after the 2026-07-04 empty-rollup incident — a citable war story (`.github/workflows/automerge.yml:16-17,99-123,264-273`).
- **OUTER EDGE (4+ wks):** Mike's gate core — packet builder + deterministic gate + receipts extractable; NATS `dharma.a2a.*` fanout and Coherence Delta ritual stay behind (`scripts/runtime/pr_merge_control.py:49-50,54-63,88-103,753-772`; 2785 lines).
- **DHARMA-BOUND, do not sell:** daemon supervision (`scripts/runtime/merge_master_mike_daemon.py:25-33,76-93`), packet-scope checker / tracks-packets ontology (`scripts/governance/check_agentops_packet_scope.py:28-39`).
- Gradient rule: reads only git + GitHub API + own config → portable; reads `~/.dharma`, NATS subjects, agent registries, tracks ontology → bound.

### Lens D — Runtime-as-product audit (DharmaGraph / arena / chamber)
- DharmaGraph is honestly behind free LangGraph: 58.00/100 parity, NOT_FINISHED, closeout blocked (`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:1-4`); the earlier 100/100 was VOIDED as self-graded (`docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json` prior_scores).
- Real differentiators are durability/audit-axis: effectively-once receipted dispatch (`dharma_swarm/graph/durable_invoker.py:46-113`), DST seam (`dharma_swarm/graph/effects.py:69-91`; spec claim "one LangGraph cannot make" at `docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md:89`), hash-chained offline-verifiable receipts (`dharma_swarm/graph/receipt_chain.py:1-6`; Phase 4 at spec:109-113).
- The spec names the buyer: EU AI Act Art. 12, applicable 2026-08-02 — before the KEEL trigger — plus AI-agent insurers pricing off audit evidence (spec:153).
- Arena and chamber are constitutionally internal — zero-weight / efferent-closed (`dharma_swarm/coordination/orchestrator_v1.py:7-12`; `dharma_swarm/chamber/__init__.py:1-16`). Not products.
- Extraction is not free: `graph/` imports `dharma_swarm.spine` in 9 places (`grep -rn 'from dharma_swarm.spine' dharma_swarm/graph/ | wc -l` → 9). Phase 6 self-evolution is doctrinally blocked on an ungameable external gradient (spec:124,152, DGM Appendix F).

### Lens E — Darshan lane
- Closest realizable external receipt is NOT a dollar: Issue One on the Darshan-owned site with digest-sealed receipt at `reports/darshan/issue_one_receipt.json` — deliberately RED today (`docs/governance/ACTIVE_TRACK.yaml:1947-1959`); the owned site is exempt from the per-platform posting gate (`ACTIVE_TRACK.yaml:1914-1922`; `docs/plans/DARSHAN_CHARTER_2026-07-12.md:61-63`).
- One operator phone decision (site deployment, next_item 2) plus editorial-law passes gate it (`ACTIVE_TRACK.yaml:1961-1973`).
- Governance hole: the track that owned revenue measurement (TAM / honest_arr, reading $0 — `scripts/governance/tam_axes.py:137-143`) was retired 2026-07-17 (`ACTIVE_TRACK.yaml:1999-2024`); the first dollar has no active-track home.
- Darshan's compounding loop (editorial law 6: article → typed swarm work; `DARSHAN_CHARTER_2026-07-12.md:17-23,54-55`) is **prose-only** — no enforcement script or test exists (repo grep confirms).
- Flagged: the KEEL date 2026-10-17 is unciteable in-repo (grep → zero matches).

### Lens F — Evolution wiring
- The fitness slot exists: `FitnessScore.economic_value` at 13% canonical weight (`dharma_swarm/archive.py:33,277,282-290`). No schema change needed.
- But external dollars exert **zero selection pressure today**: no production caller of `set_economic_spine` (grep verified; definitions only at `evolution.py:425`, `agent_runner.py:1725`, `organism.py:600`); `RevenueSpine` lacks `get_agent_stats`, so the hook would silently return neutral 0.5 via the bare except (`evolution.py:481,489-490`; alias at `revenue/spine.py:477`). `compute_extended_fitness` runs only in tests (`evolution.py:433-452`).
- A real receipts ledger exists and runs: `RevenueSpine.record_payment` → durable JSONL + telic bridge ValueEvent (`revenue/spine.py:305-338`; `revenue/telic_bridge.py:173-219`).
- Adapter precedent exists: `research_reward_to_fitness` (`archive.py:231-262`); missing twin = `revenue_receipt_to_fitness`.
- Cheapest live ingestion point: `record_fitness_observation`, production-called (`orchestrate_live.py:577`) but correctness-only today (`evolution.py:2682-2705`, esp. :2701).
- One-Wire fitness authority already gates archive writes on ≥5 confirmed receipts across ≥3 domains (`archive.py:40-45,572-591`; `tests/test_one_wire_archive_fitness_guard.py`). MAP-Elites is customer-blind — bins only dharmic_alignment/elegance/complexity (`archive.py:379-390`).
- The wiring points at a buyer: `xray.py:1129` builds "a productized X-Ray packet suitable for a paid service offer"; the coded default Offer is "Agentic Code Governance Sprint," $5,000–$25,000, 5 days (`revenue/spine_models.py:117-128`).

---

## 3) The Four Theses

### T1-fastest-dollar — FASTEST FIRST DOLLAR
**Customer: the CTO or founding engineer of a 10–50 person Python-heavy startup that turned on an AI coding fleet in the last two quarters and is drowning in agent PRs it cannot trust** — the buyer `xray.py:1126` already names verbatim ("CTO or founder under shipping pressure"), chosen because they sign a $1.5K–$3K invoice alone on one call, no procurement.
Offer: free delta-ratchet install as wedge (`delta_ratchet.py:44-57,366-380`), then a fixed-scope 5-day Repo X-Ray audit ($1.5K–$3K, deliberately under the coded $5K floor at `spine_models.py:123`), $5K–$25K sprint as upsell. 30-day path: package ratchet (days), operator runs 50–75 outreach conversations, 3–5 free installs, convert one to a paid audit; payment lands via `RevenueSpine.record_payment` (`spine.py:305-338`).
Compounding: build `revenue_receipt_to_fitness` + register 'paid engagement' as One-Wire domain; every foreign install feeds real repos into the detectors.
Biggest risk (self-declared): 50–75 genuine sales conversations in 30 days by an operator carrying 10 tracks / 26 blockers; incumbents (CodeRabbit ~$40M ARR, Aviator Verify) could bundle the audit as a feature.

### T2-compounding-first — COMPOUNDING FIRST
**Customer: the platform-engineering lead / VP Eng at a 50–200 developer company with a heterogeneous agent fleet (Copilot + Claude Code + Cursor + Devin via Agent HQ) that cannot safely merge unattended**; secondary variant: the durable-runtime builder facing EU AI Act Art. 12 on 2026-08-02 (spec:153). Chosen because their receipts arrive bundled with the richest decorrelated gradient — "a dollar with no gradient attached merely funds."
Offer: paid design-partner "Agentic Code Governance Sprint" (the coded offer, `spine_models.py:117-128`) installing Tiers 1–3 of the portable governance kit (ratchet, ci_truth, fail-closed automerge with the 2026-07-04 war story). Pitch: "the merge gate that makes your other AI agents tell the truth." $2.5K–$5K design-partner first receipt; full band after two receipts; hosted gate later, priced against the $40/seat judgment layer.
Compounding: the fully-cited five-wire plan (adapter, spine-alias fix, `record_fitness_observation` widening, MAP-Elites customer descriptor at `archive.py:379-390`, One-Wire domain + ginko_brier ratchet at `ginko_brier.py:75,92,156`); each foreign repo = the "ungameable external gradient" Phase 6 is blocked on (spec:124,152).
Biggest risk (self-declared): 30–50 operator conversations in 10 days against a demonstrated base rate of zero; Aviator Verify window closing; if the two missing wires aren't built first, the dollar arrives gradient-dead.

### T3-skeptic — RADICALLY SMALLER (the winner)
**Customer: not a market segment — ONE warm contact: a founding engineer or CTO at a 5–50 person AI-heavy startup personally known to the operator**, reachable in one conversation, matching the buyer the repo's own offer doc already names (`docs/offers/agentic-code-governance-sprint.md:4`). A parallel zero-dollar "customer": the serious overloaded reader of Darshan Issue One on the owned site.
Steelman: (1) a revenue push already ran and failed at the operator gate, not on product — `reports/revenue_wedge/first_cash_receipt_status.md` reads "NO CASH RECEIPT. Recorded revenue: $0," step 1 "Operator ratifies the wedge — operator gate, open," since 2026-07-05; (2) compounding is mechanically FALSE today (zero production callers of `set_economic_spine`; missing `get_agent_stats`; silent 0.5 at `evolution.py:489-490`) — selling before wiring buys receipts that train nothing; (3) the KEEL deadline is unciteable (grep → zero); (4) the obvious big candidates fail on their own evidence (Aviator Verify funded, DharmaGraph 58/100, Darshan hundreds of $/mo, arena/chamber constitutionally internal); (5) per Guardian cycle-004, One-Wire domain DIVERSITY (M=1/3), not dollar volume, is the binding constraint — a $500 receipt equals a $25K receipt for the metabolic unlock.
Offer: one deliberately undersized paid Repo X-Ray using the EXISTING fixture-proven kit (`scripts/revenue_wedge/audit_kit.py`; `tests/test_revenue_wedge_audit_kit.py`), $500–$1,500 upfront, delivered in under a week. Operator load: ~2 decisions + 3 emails + ~4 calls. Fitness wires (adapter + observation widening) built by agents in parallel BEFORE the receipt lands. Darshan Issue One deploy decision made in the same phone session.
Biggest risk (self-declared): the operator gate stays closed again — "radically smaller" becomes the next sophisticated deferral, agents wire a perfect pipeline with nothing flowing through it (the AMBER-45% pattern that retired company-builder-parity-2026-07). Warm-network receipt carries weak segment signal; One-Wire independence field needs hard scrutiny.

### T4-contrarian — SELL THE KNOW-HOW, ONE-TO-MANY
**Customer: the staff engineer / EM at a 20–200 person company who has personally become the de-facto AI-fleet operator, plus the funded indie fleet operator** — an L&D-budget buyer ($1–5K expensable, no procurement) who cannot buy operating doctrine anywhere; vendors sell seats and comments, not discipline. Comp: $5,000/seat Maven evals course, 4,500+ students (https://maven.com/parlance-labs/evals).
Offer: 4-week paid cohort "Running a Self-Governing Agent Fleet," taught from dogfooded receipts (ratchet install day 1; the 2026-07-04 empty-rollup war story; ci_truth; claim-evidence discipline), kit green on each student's repo by week 4. $1,000/seat × 15–20 seats = $15–20K/cohort. Day-30 gate: <5 presold seats → fall back to one $1.5–3K install engagement.
Compounding: 15–20 decorrelated student repos per cohort — ~4x the foreign-repo gradient of a design-partner motion per operator-hour; seats scale without body-shop delivery.
Biggest risk (self-declared): distribution from a standing start — no audience, no deployed site, personality-anchored comps; teaching arms future competitors.

---

## 4) The Vote — Round 1

| Judge lens | First place | One-line reasoning |
|---|---|---|
| UNIT ECONOMICS | **T3-skeptic** | Highest believable $/operator-hour (~$100–300/hr vs $40–150 for outreach-heavy theses); deliverable already CI-proven so marginal build cost ≈ 0; T4's cohort margin is destroyed by 4 weeks of non-delegable live teaching. |
| OPERATOR CAPACITY | **T3-skeptic** | The 6-weeks-open ratification gate *(correction, Codex review 2026-07-19: `first_cash_receipt_status.md` was last updated 2026-07-05 — 13 days before this deliberation, not six weeks; the gate-open observation stands, its duration was inflated)* (`first_cash_receipt_status.md`, $0) is the ground-truth measurement of operator spare capacity; only T3's budget (~5–8 hrs/month) is calibrated to demonstrated rather than aspirational capacity — T1/T2 need 10–20+ hrs/wk of the exact resource proven unavailable. |
| EVIDENCE QUALITY | **T3-skeptic** | Every load-bearing T3 claim survived mechanical verification (verbatim $0 status, zero `set_economic_spine` call sites, missing `get_agent_stats`, zero '2026-10-17' matches, 58/100 verbatim); T3 alone is literally prescribed by an existing repo evidence surface; T1/T2/T4 all repeat the `economic_amount_usd` field-name error (code says `economic_value_usd`, `telic_bridge.py:218`), and T2's "a WIP slot exists" claim is uncited and wrong at 10/10. |
| TRANSCENDENCE COST | **T4-contrarian** (dissent) | 15–20 self-selected decorrelated foreign repos per cohort ≈ 4x the gradient of any audit motion per operator-hour, and the only thesis whose revenue scaling law is not agent-hours-per-client — the structural anti-body-shop property; T1 ranked last as "the body shop my lens exists to punish." |
| TIME TO RECEIPT | **T3-skeptic** | One miracle step (the operator decision every thesis shares) shrunk to 2 decisions + 3 emails + ~4 calls on already-shipped kit; a $500 receipt = a $25K receipt for the One-Wire unlock (`first_cash_receipt_status.md:22-24`); T4 stacks three-plus distribution miracles. |

**Tally: T3-skeptic 4, T4-contrarian 1.**

---

## 5) Consensus — and Every Dissent

### Winner: T3-skeptic, 4/5 margin, round 1

**The customer is one warm contact — a founding engineer or CTO at a 5–50 person AI-heavy startup in the operator's personal network, with an agent-PR flood on a Python-centric repo** (the buyer `docs/offers/agentic-code-governance-sprint.md:4` already names). The seam is not a new product, track, or SaaS. It is the smallest transactable slice of what is already built and CI-proven: a $500–$1,500 upfront Repo X-Ray using `scripts/revenue_wedge/audit_kit.py`, delivered in under a week, whose receipt lands via the existing `RevenueSpine.record_payment` wire (`spine.py:305-338`) and registers as One-Wire domain #2 (`paid_governance_engagement`, per `first_cash_receipt_status.md` step 4). The parallel zero-dollar external contact is Darshan Issue One on the owned site, gated only by the site-deployment phone decision (`ACTIVE_TRACK.yaml:1961-1973`). The two missing fitness wires (`revenue_receipt_to_fitness` adapter; `record_fitness_observation` widening beyond correctness-only) are built by agents BEFORE the receipt lands, so the first dollar arrives gradient-live, not gradient-dead. Price rises toward the coded $5K–$25K band (`spine_models.py:123-124`) only after the compounding premise has flipped from mechanically-false to cited-true.

The consensus is explicitly NOT "wait" — it is "radically smaller, inside existing tracks, wire-before-scale," with the operator gate named as the single common-mode point of failure across all four theses.

### Dissents preserved (every one)

**Full dissent — TRANSCENDENCE COST judge (first-place vote for T4-contrarian):** T3 buys wiring truth at the cost of gradient volume. Its external gradient is close to minimal — ONE warm-network repo, and warm-network sampling is *correlated with the operator*, weakening the decorrelation the Transcendence Principle demands (the thesis itself concedes the One-Wire independence field must be scrutinized). T4's cohort yields 15–20 heterogeneous, self-selected foreign repos running the organism's own machinery — decorrelated by construction (different companies, stacks, PR distributions) — at ~4x the gradient per operator-hour of any audit motion, and it is the only thesis whose revenue scaling law is not agent-hours-per-client, i.e. the only structurally anti-body-shop vehicle. This judge also ranked T1 dead last as convergence pressure incarnate: "when the thesis's own success metric would reward the swarm for becoming a faster body shop, my lens ranks it last." The dissent stands as a standing constraint on the winner: if the T3 seam scales by adding more 1:1 audits, it becomes T1's body shop; the one-to-many gradient shape must re-enter the portfolio.

**Partial dissent — TIME TO RECEIPT judge (voted T3, demerit recorded):** T3's "no production caller of set_economic_spine" slightly overstates — plumbing exists at `organism.py:600` and `agent_runner.py:1725` — though the operational conclusion (dollars exert no live selection pressure today) survives verification.

**Partial dissents — EVIDENCE QUALITY judge (voted T3, corrections recorded):** (a) T3's weakest citation form is `spine.py:477` cited for a method's *absence*; (b) T1/T2/T4 all name the telic-bridge field `economic_amount_usd` where the code says `economic_value_usd` (`telic_bridge.py:218`) — the wire-builders must use the real name; (c) T2's governance claim that "a WIP slot exists" contradicts the CLAUDE.md digest (10 active tracks at max 10 — no slot without a closure; T3 got this right); (d) T2 uniquely surfaced a real, confirmed gap the winner must inherit: MAP-Elites has no customer axis (`archive.py:379-390`); (e) T4's `ls ~/darshan_site` claim conflates this checkout with the operator's machine.

**Structural dissent absorbed into the winner:** T2's five-wire compounding plan and T1's free-ratchet-wedge distribution idea are not rejected — the judges repeatedly noted T3 folds the wire-work in at agent (abundant) rather than operator (scarce) cost, and that T1/T2 become the correct *second* motion once receipt #1 proves the pipe.

---

## 6) What the Consensus Implies the Swarm Should Build First

Ordered; agent-executable items marked [fleet], operator-only marked [OPERATOR].

1. **[OPERATOR, ~1 hour, phone-scale] Two decisions:** (a) ratify the revenue wedge at the reduced $500–$1,500 scope — the gate open since 2026-07-05 (`reports/revenue_wedge/first_cash_receipt_status.md` step 1); (b) make the Darshan site-deployment decision (`ACTIVE_TRACK.yaml` next_item 2, "from phone is fine"). Every other item is downstream of these.
2. **[fleet] Build the two fitness wires before any receipt lands** — with a custody split (correction, Codex review 2026-07-19): wire (a), `revenue_receipt_to_fitness()` as the twin of `research_reward_to_fitness` (`archive.py:231-262`) — paid_usd→economic_value (13% weight, `archive.py:33`), on-time→performance, refund/dispute→safety=0 — lands on `dharma_swarm/archive.py`, owned by `organism-rewire-2026-07`; wire (b), widening `record_fitness_observation` beyond correctness-only (`evolution.py:2682-2705`, :2701), touches `dharma_swarm/evolution.py`, which is in NO track's `owned_surfaces` — it requires an explicit operator routing/admission decision before any edit, per the ownership rules; ship it as a separate PR from wire (a), never bundled. Use the real field name `economic_value_usd` (`telic_bridge.py:218`).
3. **[fleet] Fix or retire the dead EconomicSpine hook:** either give `RevenueSpine` a real `get_agent_stats` and call `engine.set_economic_spine` in a production path, or delete the pretense — today the alias mismatch (`spine.py:477` vs `evolution.py:481`) silently yields neutral 0.5 (`evolution.py:489-490`).
4. **[fleet] Run `audit_kit.py` against the public repos of 3 operator-chosen warm contacts**; produce three one-page sample findings as outreach artifacts (`scripts/revenue_wedge/audit_kit.py` scan → sealed JSON receipt → render).
5. **[fleet] Record ginko_brier predictions before outreach** ("contact N pays by date D"; "finding converts to follow-on"), resolved from RevenueSpine JSONL (`ginko_brier.py:84-130,133-168`), plus a pytest ratchet: monotone resolved-count, non-regressing Brier, non-regressing revenue-component `fitness_over_time` (`archive.py:867-881`).
6. **[OPERATOR] 3 emails + up to 4 calls;** close ONE at $500–$1,500 upfront; deliver readout; emit the One-Wire guardian receipt with `domain=paid_governance_engagement`, stratified independence fields scrutinized hard (warm-contact caveat from the winner's own risk section).
7. **[fleet] Verify end-to-end:** the receipt appears as an economic_value-bearing `ArchiveEntry` and in `dgc evolve trend`.
8. **[fleet, from T2's absorbed dissent] Add a customer-value descriptor to `MAPElitesGrid.compute_feature_coords`** (`archive.py:379-390`) so diversity preservation retains customer-serving niches.
9. **[fleet, from Lens E] Re-home `honest_arr`** before the first dollar arrives — its owning track retired 2026-07-17 (`ACTIVE_TRACK.yaml:1999-2024`; `tam_axes.py:137-143`) — and add a `spawned_work` key to the Darshan issue-receipt schema (`ACTIVE_TRACK.yaml:1953-1959`) so editorial law 6 becomes mechanical, not prose.
10. **[fleet, cheap hedge from Lens C/T1] Package the delta-ratchet as a standalone installable** (days of work, zero entanglement, `delta_ratchet.py:44-57`) — the free-install external-contact fallback and the wedge for whatever motion follows receipt #1.

---

## 7) Open Questions for the Next Research Cycle

1. **The KEEL date.** Recover `docs/plans/THE_KEEL_2026-07-17.md` into the checkout or from the operator; the 2026-10-17 trigger is currently unciteable (`grep -rn '2026-10-17'` → zero) and cannot govern track decisions until cited.
2. **The operator gate itself.** The single decision has sat open since 2026-07-05 (13 days at deliberation time; duration corrected per Codex review 2026-07-19). Is there a mechanical forcing function (a Routine, a dated auto-escalation, a ratchet on days-since-gate-opened) that converts operator-gate staleness into a visible governance signal instead of silent $0? This is the deliberation's named common-mode failure — it deserves its own instrumented answer.
3. **Warm-receipt independence.** What concretely qualifies a warm-network payment for the One-Wire `client is not dharma-swarm-controlled` field? Define the test before receipt #1, not after.
4. **Receipt #2's shape — the T4 dissent question.** After the first 1:1 receipt, does the seam scale as more audits (T1's body shop, punished by the Transcendence judge) or pivot one-to-many (T4's cohort, 4x gradient per operator-hour)? Gather the missing evidence: can the war-story essays travel without an audience? Run the 2–3 essay experiment as a cheap probe.
5. **Track topology.** Portfolio is at WIP max 10/10 (CLAUDE.md digest; T2's "slot exists" claim was wrong). If the seam warrants its own `revenue-external-humans-served` track, which track closes? Or does the seam live inside existing surfaces indefinitely?
6. **The Aviator Verify window.** How fast is the merge-governance white space (Lens A) closing? Track Verify's adoption and GitHub's Agent HQ bundling quarterly; the premium hosted-gate follow-on (T2's endgame) depends on the gap staying open 1–2 quarters.
7. **EU AI Act Art. 12 buyers.** Applicability 2026-08-02 (spec:153) lands in two weeks. Does a real attestation buyer exist at solo-operator sales scale, or is that a funded-company market? (Lens D's seam remains unpriced.)
8. **Darshan monetization signal.** After Issue One ships, what reader evidence actually arrives through anti-feed channels (`DARSHAN_CHARTER_2026-07-12.md:56-57`), and does the `spawned_work` loop emit typed swarm work in practice — measured, not chartered?
9. **Detector-gradient telemetry.** When foreign repos run the delta-ratchet, by what channel do their failure modes and false positives return to the detector table (`delta_ratchet.py:97-166`)? Design the return wire before the installs, or the "every install is gradient" claim is the next prose-only compounding story.

---

*End of round 1 record. Append round 2 below when receipt #1 resolves or 30 days elapse, whichever first.*