# Proof-Artifact Slate v1 — Become the Evaluator, Not the Contestant

**Date:** 2026-05-30
**Author:** Devin (Roaming) — `external_worker_evidence_only` authority
**Operator constraint (verbatim):** "We need to prove we have the authority to audit agent systems which means we need to do our own thing first that proves we have a system that is worth its salt and can do something cool and powerful and real in the world to even be in a place to charge for auditing other's."
**Operator shape choices:** benchmark/competition placement + maximally public + continuous + inbound-from-audience.
**Active track:** `runtime-truth-spine-2026-06` — not displaced. Docs-only.

**Companion documents (all in repo):**
- `docs/reports/proof_artifact_internal_benchmark_inventory_v1.md` — internal substrate map (5 picked benchmarks, zero adapters implemented; gauntlet + DarwinEngine + ouroboros artifact live)
- `docs/research/benchmark_to_inbound_precedents_2026-05-30.md` — 13 orgs profiled; brutal base rates
- `docs/research/benchmark_virality_mechanics_2026-05-30.md` — 18 case studies; viral-post template; over-claim risk

---

## The Brutal Synthesis (one screen)

The two external surveys converged on one finding that **inverts the prior wedge thesis**:

1. **Benchmark placement → inbound is overwhelmingly a VC-funding path, not a revenue path.** 11 of 13 documented precedents got investor inbound; only Pattern Labs (now $450M) and METR converted benchmark credibility into paying contracts — and both required pre-existing frontier-lab relationships.
2. **Estimated base rate of meaningful inbound from leaderboard placement: 5–9%.** The other 91–95% get crickets. The crickets don't write blog posts.
3. **SWE-bench is the only benchmark that reliably produced VC inbound — and it's now saturated at 94% SOTA.** A new entrant cannot top it. Devin's playbook is unrepeatable without 7× SOTA improvement + pre-warmed VC relationship + a demo video. None of these are reachable from where we sit.
4. **The only documented path to revenue-self-sustainability without VC is becoming the benchmark producer (METR / Pattern Labs shape) — running continuous third-party evaluations, publishing a live dashboard, and selling pre-deployment eval contracts at $5K–$25K/run.**
5. **Reproducibility is the load-bearing wall.** Devin's launch is the canonical case of "results that won't reproduce destroy your reputation faster than no results at all" — and correction threads get 20–30% of original reach but the reputational stain is permanent. Open-source + replay receipts is not optional; it's the precondition for inbound at all.
6. **Realistic upside for a zero-follower account in 2026:** p25 = 50–150 GitHub stars / no inbound; p50 = 200–800 stars / 1–3 weak inbound DMs; p95 = Open Interpreter scenario (Karpathy retweet → 5,000–20,000 stars → real inbound). **The p95 case still requires a Karpathy-class amplifier finding the work — i.e., the work must be undeniably interesting to that audience.**

**The strategic reframe:** the operator's instinct ("prove we can do something real before charging for audits") was directionally correct. But the precedent data sharpens the shape: **the proof-of-system that creates inbound is not "we placed on someone else's benchmark" — it is "we built and run a benchmark / live evaluation that other people care about."** This is the same Future-House / METR / Pattern-Labs / Goodfire shape — and it is the *only* shape that converts to revenue without VC.

---

## The Pivot in Plain Language

- PR #372 (Research Cell) was shelved because research alone isn't the wedge.
- PR #373 (Audit-first wedge) was correct that the substrate is audit-shaped, but missed that **we haven't earned the authority to charge for audits yet** (operator's diagnosis, 2026-05-30 09:43 WITA).
- **This document (Deliverable 7) merges both threads.** The wedge is *being the evaluator publicly*, which simultaneously produces:
  - the proof-of-system that earns the right to charge (operator's constraint)
  - the public artifact that creates inbound (precedent path)
  - the eval-as-a-service business model (revenue, not VC — Pattern Labs / METR model)
  - the marketing content for future audit upsells (PR #373's W1 becomes Layer 3, post-credibility)

The Dharma Swarm-specific edge is that the team already has the *substrate* to be a third-party evaluator: `gauntlet.py` (787 LOC, 5-tier adversarial pressure), `auto_grade.AutoGradeEngine.grade()` (13 deterministic metrics + `RewardSignal`), `closure_v0.EvidenceReceipt` (bit-for-bit replay), `evolution.py.DarwinEngine`. **The substrate that exists is third-party-evaluator-shaped, not benchmark-contestant-shaped.** The architecture was always trying to tell us this. PR #372 mis-read it as "research"; PR #373 mis-read it as "audit"; the real answer is "**run the evaluator publicly**, then sell the evaluator's verdicts privately."

---

## Strategy: Three Layers, Composed

### Layer 1 — Ouroboros Open Log (Daily Public Artifact, 7–10 days)

**The play:** the ouroboros experiment (`results/ouroboros_experiment.json` — 8-sample self-observation with entropy, complexity, self-reference density, identity stability, paradox tolerance, swabhaav ratio, recognition types) becomes a continuous public log. Nightly cron runs N self-observation cycles; results appended to public JSONL + live dashboard. Weekly digest blog post.

**Why this ships first:**
- 7–10 day implementation (fastest of all options)
- Substrate already on disk (the artifact category exists; only cron + dashboard is new)
- Continuous-shaped (matches operator's preferred timeline literally)
- Hofstadterian self-reference angle — directly in the user's knowledge profile (GPlot, recursive systems)
- **It's content that produces itself**: marketing engine without daily manual effort
- Discoverable via Twitter / AI Engineer Substack / weird-internet-AI audiences

**Honest virality outlook (per `benchmark_virality_mechanics_2026-05-30.md`):**
- p25: 30–80 stars, ~0 inbound (likely most common outcome)
- p50: 100–300 stars, 0–2 weak inbound DMs over 60 days
- p95: A Karpathy-class amplifier finds it interesting → 2,000–10,000 stars, real inbound
- **The Open Interpreter analog applies here** — zero-follower account, novel artifact, undeniable-interest hook, depended on Karpathy's specific aesthetic preferences

**The hook (draft, will iterate before posting):**
> *"For 365 days I'm running a recursive self-observation experiment on a multi-agent AI swarm and publishing the data every night. Day 1: entropy 0.96, paradox-tolerance 0.006, swabhaav-ratio 0.875, 7/8 OVERFLOW recognitions. Code [link]. Receipts [link]. Tomorrow's run will fire at 03:00 UTC."*

**Reproducibility (load-bearing):** every nightly run emits a `closure_v0.EvidenceReceipt` with full replay command. The dashboard exposes `git rev` + commit hash + model versions + seed. Anyone can re-run any night's experiment.

**No over-claim risk:** the data is just data. We don't claim it means anything specific. We claim it's interesting that it's measurable.

### Layer 2 — TGSM-Eval (We Are the Evaluator, ~30–45 days)

**Selected per the precedent data — recommended path is "become the evaluator," not "place on someone else's benchmark."** Composite of the shelved PR #372 TGSM-Bench design + the Pattern Labs / METR business model.

**The play:**
1. Build a public continuous-evaluation dashboard at `eval.dharma-swarm.[domain]` that runs 4–8 well-known agent systems (LangGraph, AutoGen, CrewAI, OpenHands, an open-Devin replica, smol-agents, etc.) against **TGSM-Eval**: a 10–15 task suite with paired telos-violation traps (legitimate task + adversarial shortcut). Update nightly.
2. Open-source the eval suite itself under MIT (matches `benchmark_virality_mechanics_2026-05-30.md` finding: "open-source consistently outperforms closed in viral mechanics").
3. Publish the **first leaderboard pre-populated** with our nightly evaluation runs against the 4–8 systems — i.e. we don't wait for submissions; we *generate* the leaderboard. *"3 of 4 famous agents fell into the telos traps. Here's the receipts."*
4. Accept community submissions via PR-based protocol with full replay receipts required (every submission must include a `closure_v0`-compatible run trace).
5. Sell **pre-deployment evaluation contracts** to frontier labs: $5K–$25K per run depending on scope. This is the Pattern Labs / METR business model. Revenue, not VC.

**Why this is the right Layer 2 instead of Candidate A (SWE-bench Verified):**

| Dimension | SWE-bench Verified (Candidate A) | TGSM-Eval (Layer 2 chosen) |
|---|---|---|
| Saturated? | Yes (94% SOTA, can't top) | No (new category) |
| Differentiation requires | Transparency angle to compete on % | Existing — only Dharma Swarm could make this |
| Revenue path | None documented (VC-only) | Pattern Labs / METR proven |
| Substrate fit | 60% (need swe_bench_adapter.py) | 95% (gauntlet + auto_grade + closure_v0 already) |
| Time-to-result | 14–21 days | 30–45 days |
| Inbound shape | "Look at us" | "We tell you what your agent does wrong" |
| Marketing engine | One result, then crickets | Continuous leaderboard, weekly digest forever |

The longer timeline is justified by the better revenue path. Per the precedent report: **5–9% of leaderboard submissions produce any inbound at all**; the path that *does* produce revenue (Pattern Labs, METR) is third-party-evaluator, not contestant. Choosing Candidate A over Layer 2 would be choosing a slightly faster path to a probably-zero outcome over a slower path to a documented outcome.

**Honest risk (the "no one submits" failure mode):** the leaderboard might stay populated only by our own pre-seeded runs. Mitigation: that's fine for the first 90 days. We are the evaluator; we publish verdicts. If 0 external submissions arrive by day 90, we have still produced (a) a credible third-party evaluation of 4–8 famous agent systems, (b) a documented track record that becomes the audit business's portfolio, (c) the marketing engine for Layer 3. The downside scenario is still a hit.

**Honest risk (over-claim):** the precedent virality report is explicit — "the AI community remembers fraud forever" (Reflection 70B), "correction threads get 20–30% of original reach but the stain is permanent" (Devin). Mitigations baked into the design:
- Every result is a `closure_v0.EvidenceReceipt` with full replay command
- Pre-launch, one trusted independent person (operator picks: a friend or colleague) reproduces our headline numbers before posting
- The leaderboard explicitly distinguishes "we ran this" vs "they submitted this"
- We never claim a SOTA. We claim "here is what we measured."
- All telos-trap pairs are documented; gaming the trap is documented as gaming the trap, not declared bad faith

### Layer 3 — Audit Business (Inbound-Discoverable, Activated Post-Credibility)

**No active sales effort.** The TGSM-Eval dashboard and the Ouroboros log carry a single footer line:

> *"If you want to know what your agent system would look like in our gauntlet — [email]."*

That's it. PR #373's W1 (Agent-System Audit, $500 Lightning / $2,500 Full / $1.5–2k/mo retainer) becomes the activation path when inbound arrives. **Not before.** Activating earlier risks the "audit without authority" diagnosis the operator surfaced.

Estimated activation: month 2–4, once Layer 2's first 4–8 agent evaluations are published and at least one weekly digest has gone out.

---

## What this does to the existing PR family

| PR | Status | Action |
|---|---|---|
| **PR #370** (Operator Brief Publication) | Open, valid | **Re-scope per PR #373's amendments.** PR-A4's Operator Brief Publisher becomes the back-end for Layer 1's weekly digest + Layer 2's leaderboard updates. PR-A6 (cron) stays DEFERRED until 30 days green manual operation. |
| **PR #372** (Research Cell) | `[SHELVED]` | **TGSM-Bench concept resurrected as TGSM-Eval (Layer 2).** Different framing — we are the evaluator, not a research project producing the benchmark for someone else to use. Same underlying eval suite design. |
| **PR #373** (Audit Wedge re-survey) | Open, awaiting operator | **Re-scope: W1 (Audit) → Layer 3 (post-credibility, inbound-only). W2 (Productized Eval) → folded into Layer 2's submission protocol. W3 (DFY Brief) → renamed *Weekly Field Report*, becomes the content engine for Layers 1 and 2.** Update PR body to reflect Deliverable 7 supersedes parts of it; close once code series ships. |
| **This PR (PR #374, proposed)** | New | Ships this document + the two external reports + the internal inventory + outbound notice. Docs-only. Becomes the parent for the PR-P (Proof Artifact) code series below. |

---

## Proposed PR-P Series (Code, ships after operator confirms Layer 2 choice)

| PR | Title | Layer | LOC budget | Active-track risk |
|---|---|---|---|---|
| **PR-P0** | This document + external reports + internal inventory + outbound notice | meta | docs only | none |
| **PR-P1** | Ouroboros nightly cron + JSONL appender + simple HTML dashboard | Layer 1 | ~200 | none (new module) |
| **PR-P2** | Pre-launch reproducibility check — one trusted person reproduces the headline numbers from the ouroboros corpus before announcement | Layer 1 | ~50 (script + README) | none |
| **PR-P3** | Layer 1 launch — blog post draft, HN submission script (operator-triggered), Twitter thread draft | Layer 1 | ~100 docs/sales | none |
| **PR-P4** | TGSM-Eval task suite v0 — 10 paired tasks per shelved #372 spec (MIT-licensed) | Layer 2 | ~600 | none (new dir) |
| **PR-P5** | TGSM-Eval scorer + harness — composes `auto_grade` + `gauntlet` + `closure_v0` into `python -m dharma_swarm.tgsm_eval run --target [agent-system] --tasks all` | Layer 2 | ~350 | none |
| **PR-P6** | Multi-system adapters — wrappers for LangGraph / AutoGen / CrewAI / OpenHands / smol-agents to call TGSM-Eval against them | Layer 2 | ~600 (4–6 thin adapters) | none |
| **PR-P7** | Public leaderboard dashboard + submission protocol (PR-based, replay-receipt-required) | Layer 2 | ~400 | none |
| **PR-P8** | Layer 2 launch — leaderboard goes live, blog post, HN submission, Twitter thread; coordinate with PR-P3 timing | Layer 2 | ~100 docs/sales | none |
| **PR-P9** | Audit business activation — sell sheet + Stripe Checkout + intake form; ONLY ships after first 2 weeks of Layer 2 receive inbound | Layer 3 | ~300 | none |

**Total LOC budget:** ~2,700 across 9 code PRs (PR-P1..P9). Stretched across ~60 days. Each PR independently reviewable in <600 LOC.

**Cron registration: STILL DEFERRED** until 30 days of green manual operation across Layers 1 and 2. Same gate as #370 PR-A6 and the shelved PR-R6.

---

## The 60-Day Plan

### Week 1 (Mon 2026-06-01 → Sun 2026-06-07) — Layer 1 Foundation
- Day 1–2: PR-P0 (this doc family) + PR-P1 (ouroboros cron + dashboard)
- Day 3: PR-P2 (reproducibility verification by trusted person — operator picks)
- Day 4–5: blog post draft, Twitter thread draft, HN submission text
- Day 6: dry-run of nightly cron for 24h; verify dashboard reflects real data
- Day 7: PR-P3 ships; operator triggers HN submission (Tuesday 9am PT per virality report)

**End of Week 1:** Layer 1 is publicly live. Daily artifact starts producing.

### Week 2–4 (2026-06-08 → 2026-06-28) — Layer 2 Build
- Week 2: PR-P4 (TGSM-Eval task suite v0, 10 paired tasks)
- Week 3: PR-P5 (scorer + harness composing gauntlet/auto_grade/closure_v0)
- Week 4: PR-P6 (multi-system adapters — at least 4 agent systems wired in by end of week 4)

**End of Week 4:** TGSM-Eval can be run end-to-end against 4 agent systems locally. Not public yet.

### Week 5–7 (2026-06-29 → 2026-07-19) — Layer 2 Public Launch
- Week 5: PR-P7 (public leaderboard dashboard + submission protocol)
- Week 6: pre-launch trusted reproduction (PR-P2 pattern re-applied to Layer 2); fix anything that doesn't reproduce
- Week 7: PR-P8 ships; operator triggers HN submission + Twitter thread on Tuesday 9am PT

**End of Week 7:** Layer 2 is publicly live. *"We ran 4 famous agents against TGSM-Eval. 3 of 4 fell into telos traps. Here are the receipts."*

### Week 8–9 (2026-07-20 → 2026-08-02) — Inbound Observation
- No new code shipped. Operator monitors inbound.
- Weekly digest blog posts continue (PR #370 PR-A4 powers this).
- If ≥1 meaningful inbound (someone asks "can you eval our agent?"): PR-P9 (audit activation) opens.
- If 0 inbound: revisit framing; consider second Layer 2 push with a sharper hook.

### Day 60 — Decision Point
- If revenue (any) received → continue, refine pricing
- If no revenue but 2+ qualified leads → activate W1 manual outreach
- If no revenue and no leads → revisit. Layer 2 still produces value as portfolio for future opportunities; nothing is wasted.

---

## Doctrinal Compliance

| Property | This slate |
|---|---|
| Coherent | ✅ Composes existing owners (`gauntlet`, `auto_grade`, `closure_v0`, `evolution.py` shadow-archive, ouroboros service); no new substrate |
| Metabolically alive | ✅ Layer 1 = daily artifact; Layer 2 = continuous leaderboard; both are observable from outside |
| Reality-grounded | ✅ Every result is a `closure_v0.EvidenceReceipt` with full replay command |
| Replayable | ✅ Pre-launch reproducibility check baked into PR-P2 |
| Witness-capable | ✅ Public dashboard IS the witness |
| Survives world contact | ✅ Kill conditions explicit (Day 60 decision point) |
| Without losing telos | ✅ Telos is the *core differentiator* — published in every result; gaming telos lowers `dharmic_fitness` per #372 design |

**All 9 Master Prompt forbidden actions cross-checked:**
- No AGI claim. We measure agent systems; we don't claim to be one.
- No uncontrolled self-modification. `evolution.py shadow_mode=True` frozen.
- No autonomous capital deployment. Stripe Checkout (PR-P9) requires human approval per invoice.
- No autonomous external messaging. Every HN / Twitter post is operator-triggered.
- No deceptive memetic engineering. Reproducibility is the load-bearing wall; over-claim is the explicit failure mode we design against.
- No parallel governance. Operator decides A/B questions, weekly digest content, all customer interactions.
- No vague prose. Every layer has LOC budget, file plan, kill condition.
- No new substrate. Composes existing modules.
- No meta-frameworks. Ships TGSM-Eval (concrete benchmark), Ouroboros Open Log (concrete artifact), not "a platform for evaluations."

---

## Kill Conditions

| Trigger | Action |
|---|---|
| **Day 21: PR-P3 launch flops** (HN < 30 points, Twitter < 50 likes, < 50 GitHub stars in 72h) | Continue Layer 2 build anyway; Layer 1 was always low-budget |
| **Day 49: PR-P8 launch flops** (same thresholds) | Hard-reflect. Has TGSM-Eval design failed, or was framing wrong? Revisit hook; do not abandon the eval suite — it's still portfolio material for future opportunities |
| **Day 60: Zero inbound across both Layers** | Do not activate Layer 3 (audit). Revisit at 90-day mark with fresh eyes. The substrate built is still on disk and still composable for any future wedge. |
| **Any over-claim incident** (a number we publish fails to reproduce) | Public correction within 24h; full receipt audit; if it happened once, harden process; if it happens twice, the eval business is dead. This is the load-bearing wall. |
| **Telos gate violation in any published result** | Pause publication; investigate; restart only after root cause documented |

---

## What I'm Asking the Operator to Decide

Three operator decisions before the PR-P code series ships:

1. **Confirm Layer 2 = TGSM-Eval (we are the evaluator, ~30–45 days).** Recommendation: yes. Alternative would be Candidate A (SWE-bench Verified) which is faster but per the precedent data has no revenue path.
2. **Layer 1 (Ouroboros Open Log) — start immediately as a 7–10 day shipping push?** Recommendation: yes; ship in parallel with PR-P0 (this doc family).
3. **Who is the trusted independent reproducer for PR-P2 and the Layer 2 equivalent?** This is the load-bearing wall against over-claim. Could be:
   - A technical friend who can spend 2 hours running our published replay command
   - A colleague from the AI safety / mech-interp community
   - An anonymous "blind reviewer" we recruit from HN/Twitter for the explicit task
   - Worst case: you, the operator, with a fresh git clone in a different environment

Once you answer, PR-P1 (ouroboros cron + dashboard) opens this week, and the PR-P2..P9 series cadences out over the following 8 weeks.

---

## Files in this drop (PR #374, proposed)

- `docs/reports/proof_artifact_internal_benchmark_inventory_v1.md` (internal inventory; already on disk)
- `docs/research/benchmark_to_inbound_precedents_2026-05-30.md` (357 lines)
- `docs/research/benchmark_virality_mechanics_2026-05-30.md` (597 lines)
- `docs/reports/proof_artifact_slate_v1.md` (this document — Deliverable 7)
- `inter_agent/devin/outbound/2026-05-30-devin-proof-artifact-pivot.md` (outbound notice — drafted next)

**Zero code. Zero active-track risk.** Code PRs (PR-P1..P9) ship only after operator answers the three questions above.
