# Wedge Candidate Slate v1 — 30-Day Time-to-First-Dollar

**Date:** 2026-05-29
**Author:** Devin (Roaming) — `external_worker_evidence_only` authority
**Trigger:** Operator shelved PR #372 (Research Cell). "Research is important but not the right wedge for self-sustaining economic funding."
**Filter:** 30-day time-to-first-dollar. Self-sustaining means revenue > burn.
**Companion documents:**
- `docs/reports/wedge_resurvey_burn_and_substrate_audit_v1.md` — internal substrate inventory + burn audit
- `docs/research/wedge_precedents_sub90day_revenue_2026-05-29.md` — external precedent survey (18 cases)
**Active track:** `runtime-truth-spine-2026-06` — not displaced. Docs-only.

---

## The Brutal Synthesis (one screen)

**The external survey's headline finding:** 54% of indie-hacker AI products make exactly $0. The Pieter Levels / Tony Dinh / Danny Postma stories required 20k–350k existing followers. Without an existing audience, the same products make $200–$500 in week 1, not $5k MRR.

**The one path that reaches $2k/mo in 30 days without an audience:** direct outreach consulting or audit services with a specific named deliverable and a $2k–$5k price point. **Everything else takes 60–180 days.**

**The wedge IS NOT:** a SaaS product, a paid subscription brief without an audience, mech-interp research, a benchmark release, GitHub Sponsors, or a no-code/AI-wrapper micro-product.

**The wedge IS:** **Done-for-you agent-system audits** ($1.5k–$5k per engagement) anchored on Dharma Swarm's existing audit-graph + `gauntlet` + `closure_v0` receipt substrate. Two paid audits in 30 days = $3–10k. Three paid audits in 30 days = covers 2 months of burn.

This is the only path the data supports.

---

## The Pivot in Plain Language

The operator was right twice in two days:
1. Research is not the wedge (Friday 10:25).
2. Operator Brief Publication infrastructure is not the wedge either (the implicit point — #370's wedge is publication, not revenue).

Both pivots share a root cause: **building infrastructure without first selling the outcome.** The substrate is the most expensive part to acquire (and we already own it — ~5000 LOC of evaluation surface). The substrate is also the *least valuable* part to a customer. Customers pay for outcomes — a 10-page audit PDF with findings — not for the codebase that produces the PDF.

Wedge candidates in this slate are scored on whether they let us **sell outcomes built on existing substrate.** Anything that requires new substrate before the first dollar is disqualified.

---

## Scoring Framework

Each wedge scored on six dimensions (from external precedents survey §5):

| Dimension | Why it matters |
|---|---|
| **D1. Time-to-first-dollar (30d feasibility)** | Operator's hard filter |
| **D2. Substrate reuse %** | Higher → less new code → less active-track risk → lower opportunity cost |
| **D3. Audience independence** | We have no documented audience. Wedges that require an audience are disqualified at the 30-day target. |
| **D4. Active-track risk** | Cannot touch `spine/**`, `orchestrator.py`, `agent_runner.py`, `runtime_state.py`, etc. |
| **D5. Sales cycle realism** | Cold outreach must convert at >0.5% to hit numbers |
| **D6. Outcome legibility** | Customer can immediately understand what they get and why it's worth $X |

Each dimension scored 1–5; total /30.

---

## The Slate (ranked)

### W1 — Agent-System Audit Reports (★★★★★ — 28/30)

**The product:** A 7–14 day adversarial audit of a customer's agent or multi-agent system. Deliverable: a 10–20 page PDF with findings (failure modes, telos-violation traps, replay-grade evidence receipts), scored on Dharma Swarm's 13-metric `auto_grade` axis + gauntlet's 5-tier pressure tests. Customer keeps the receipts; we keep the (sanitized) findings as case-study material.

**Substrate already on disk:**
- `dharma_swarm/audit_graph.py` family (per memory of prior sessions; verified by repo search)
- `closure_v0.EvidenceReceipt` — bit-for-bit replay-grade provenance
- `benchmarks/gauntlet.py` (787 LOC, 5-tier adversarial pressure)
- `dharma_swarm/auto_grade/engine.AutoGradeEngine.grade()` (13 deterministic metrics)
- `dharma_swarm/lineage.py` + `api/routers/lineage.py` — provenance graph queryable
- `dharma_swarm/agent_constitution.py`, `telos_substrate.py`

**Substrate gap (must build before first $):**
- A 1-page sell sheet (PDF) describing the deliverable
- Stripe Checkout link or simple invoicing
- A PDF report template (`docs/templates/audit_report_template.md`)
- An NDA/MSA template (one-pager, lawyer-reviewed for $200 if needed)
- ~3 hours of work, not 3 weeks

**Pricing:**
- Tier 1 — "Lightning Audit" (self-serve scan + 1-page summary): **$500 flat**
- Tier 2 — "Full Audit" (7-day engagement, 15-page report, 1 hr debrief call): **$2,500 flat**
- Tier 3 — "Continuous Audit" (monthly retainer, ongoing): **$1,500–$2,000/mo**

**Time-to-first-dollar (30d feasibility):** **HIGH.**
Precedent: jxnl.co — $140k deal in month 3 from one viral HN post; first paid client ~week 3-4 ([jxnl.co](https://jxnl.co/writing/category/consulting/)). Solo AI consulting baseline: $1.5k–$3k first engagement at week 3–4 with cold outreach. We have stronger substrate than the median solo AI consultant — closure_v0 receipts and gauntlet are uncommon differentiators.

**Honest priors (from precedent §3 Category 3):**
- Week 1–2: publish 2–3 highly specific LinkedIn/HN/Twitter posts about agent failure modes
- Week 3–4: DM 10–20 founders building on agents/LLMs, offer a free 1-hour architecture review
- Week 5–6: close 1–2 paid engagements at $1.5k–$3k each
- Month 2–3: hit $2k MRR via repeat + referrals

**Outcome legibility:** **★★★★★** "We will tell you how your agent system fails, with replayable evidence, before your users do." Concrete, expensive-sounding, and matches what enterprise customers already pay $20k–$50k for ([RAG consulting market reference](https://jxnl.co/writing/category/consulting/)).

**Active-track risk:** **None.** Audit reports are docs-only outputs from existing read-only surfaces. No edits to spine/orchestrator/runtime_state.

**Score breakdown:**

| Dim | Score | Note |
|---|---|---|
| D1 — 30d first-$ | 5 | Cold outreach to 20 prospects realistically yields 1–2 conversions in 30 days |
| D2 — Substrate reuse | 5 | 90%+ of value delivered by existing modules |
| D3 — Audience independence | 5 | Cold outreach works at this price point |
| D4 — Active-track risk | 5 | Zero |
| D5 — Sales cycle realism | 3 | Requires actual outreach effort — the biggest risk |
| D6 — Outcome legibility | 5 | Audit = legible to any technical buyer |
| **Total** | **28/30** | |

---

### W2 — Productized Eval Reports (★★★★ — 24/30)

**The product:** A 48-hour structured eval of a customer's agent outputs. Customer sends 50–200 prompt/response pairs; we return a 5-page report scoring them on Dharma Swarm's 13 `auto_grade` metrics with cited failure modes and recommended fixes. Faster, narrower, cheaper than W1.

**Substrate:**
- `dharma_swarm/auto_grade/engine.py` (13-metric deterministic scoring)
- `dharma_swarm/ecc_eval_harness.py` (842 LOC, 11 evaluator functions)
- `dharma_swarm/cascade_domains/research.py`

**Gap:**
- Intake form (Google Form is fine for v0)
- Stripe Checkout
- Report template
- ~2 hours of work

**Pricing:** $500–$1,500 per eval. Recurring if customer wants weekly/monthly eval of their agent in production.

**Time-to-first-dollar:** **HIGH.** Faster than W1 because lower friction (no engagement, no NDA, no calls). Lower revenue per sale. Precedent: solo AI micro-consulting on Upwork — 2-4 weeks to first paid engagement, $750–$1,500 deliverables ([micro-consulting solo dev pattern, precedent #9](../research/wedge_precedents_sub90day_revenue_2026-05-29.md#2-precedent-comparison-table)).

**Risk:** Lower price point means need 4+ sales to clear $2k. Distinguishing from Patronus / Galileo / LangSmith requires positioning. Realistic positioning: "I run your agents through 5 adversarial tiers, not just LLM-judge scoring."

**Score breakdown:**

| Dim | Score |
|---|---|
| D1 — 30d first-$ | 5 |
| D2 — Substrate reuse | 5 |
| D3 — Audience independence | 4 |
| D4 — Active-track risk | 5 |
| D5 — Sales cycle realism | 2 (need volume) |
| D6 — Outcome legibility | 3 (vs Patronus/Galileo: less obvious differentiation) |
| **Total** | **24/30** |

**Strategic role:** This is the **funnel into W1.** Customer pays $500 for a productized eval; if their system has serious findings, they upgrade to the $2,500 full audit. W2 is the lead magnet for W1.

---

### W3 — Done-for-You Operator Briefs (Wizard of Oz of PR #370) (★★★★ — 22/30)

**The product:** A custom weekly intelligence brief delivered to a specific customer on a specific topic (their competitors, their tooling landscape, their hiring market). Manually produced using Dharma Swarm's cascade_domains/research + opportunity_dispatcher; delivered via email or shared Notion doc.

**Substrate:**
- `dharma_swarm/cron_runner.py`
- `dharma_swarm/daily_operating_brief.py`
- `dharma_swarm/cascade_domains/research.py`
- `dharma_swarm/opportunity_dispatcher.py` + `opportunity_refill.py`
- PR #370's PR-A4 (Operator Brief Publisher) — about to land

**Gap:**
- Customer intake (1-1 sales conversation per customer)
- Per-customer topic template
- ~1 hour of manual curation per brief per week

**Pricing:** $200–$800/mo per customer. Boutique. 5–10 customers = $1k–$8k MRR.

**Time-to-first-dollar:** **VERY HIGH** (Wizard-of-Oz pattern; first dollar plausible in week 1 from a single sale).

**Precedent:** AI automation agency / done-for-you SMB ([precedent #16](../research/wedge_precedents_sub90day_revenue_2026-05-29.md#2-precedent-comparison-table)) — 60–75% pilot-to-paid conversion when free 2-week pilot offered. Time to first $: 2-4 weeks. Time to $2k MRR: 45–75 days.

**Strategic role:** This is **PR #370 sharpened, not shelved.** The Operator Brief Publisher infrastructure becomes the back-end for W3 customers. Specifically — the reader is **NOT** "AI builders." The reader is **a named individual or company** who pays for their custom brief.

**Score breakdown:**

| Dim | Score |
|---|---|
| D1 — 30d first-$ | 5 |
| D2 — Substrate reuse | 4 |
| D3 — Audience independence | 5 |
| D4 — Active-track risk | 4 (PR #370 dependency) |
| D5 — Sales cycle realism | 2 (1-1 sales is slow per dollar) |
| D6 — Outcome legibility | 2 (custom briefs are squishy) |
| **Total** | **22/30** |

---

### W4 — Opportunity Pipeline SaaS (★★ — 15/30) — NOT RECOMMENDED at 30d filter

**Why scored:** included for completeness because `dharma_swarm/opportunity_dispatcher.py` + `api/routers/opportunities.py` is the most production-ready surface in the repo.

**Why not recommended:** SaaS at the 30-day filter is disqualified by the survey. Median solo AI SaaS makes $100–$500 MRR at 3 months ([§3 Category 1](../research/wedge_precedents_sub90day_revenue_2026-05-29.md#category-1-paid-api-wrappers--micro-saas)). Auth + multi-tenant + billing is real work for 30 days. Distribution requires an audience we don't have.

**Future role:** Revisit at 90-day mark *after* W1/W2/W3 generate revenue + audience.

---

### W5 — Paid Newsletter Subscription (★★ — 14/30) — NOT RECOMMENDED at 30d filter

**Why not recommended at 30d:** Without an audience, subscription newsletters take 60–180 days to hit $2k MRR even with strong content. Ben's Bites grew 0→110k subscribers over 13 months ([precedent #10](../research/wedge_precedents_sub90day_revenue_2026-05-29.md#2-precedent-comparison-table)). The same content as a *lead magnet* (free) is more valuable than as a paid product (which has no buyers yet).

**Strategic role:** The **free** version of this — weekly intelligence post on LinkedIn / X — is the **distribution channel for W1.** It's marketing, not revenue.

---

## The Recommended Sequence

**Three-week sprint to first dollar, then three-month flywheel.**

### Week 1 (Tue 2026-06-02 → Mon 2026-06-08): Foundation

1. **Burn audit** (1 day). Run `dharma_swarm.cost_tracker.cost_summary` against real logs; pull last-30-day invoices from each provider. Output: `docs/reports/burn_report_2026-05-29.md`. Cut subscriptions + reroute petri_dish workers to `openrouter:free` per `llm_burn.py:21`. **Target: $2k → $600/mo within 2 weeks.** Wedge-agnostic. Highest-leverage immediate move.
2. **Sell sheet for W1 (Lightning Audit + Full Audit).** 1-page PDF, names what the customer gets and the price. Output: `docs/sales/audit_sell_sheet_v0.pdf`.
3. **Report template for W1.** Markdown skeleton of the 15-page Full Audit deliverable. Output: `docs/templates/audit_report_template.md`.
4. **One LinkedIn or HN post** about a specific agent-system failure mode, demonstrating Dharma Swarm's `gauntlet` finding it. Run gauntlet against an *open-source* agent repo (e.g. AutoGen, CrewAI, LangChain agent example) and publish the findings. **This is both content and a case study.**
5. **First 10 outreach DMs.** To founders running multi-agent systems. Offer: free 30-minute architecture review.

### Week 2 (Tue 2026-06-09 → Mon 2026-06-15): First Calls

6. **Free 30-min reviews with 3–5 inbound responses.** Use the conversation to refine the pitch.
7. **One paid Lightning Audit** ($500) by end of week 2 = first dollar. Realistic if 3+ calls landed in week 2.
8. **Second LinkedIn/HN post** — different failure mode from a different OSS agent system. Audience-building continues.
9. **Set up Stripe Checkout** for the two audit tiers. ~1 hour.

### Week 3 (Tue 2026-06-16 → Mon 2026-06-22): First Full Audit

10. **One paid Full Audit engagement** ($2,500) starts. 7-day delivery.
11. **Continue outreach** — another 10 DMs targeting people who engaged with the LinkedIn posts.
12. **Free 2-week pilot offer** for one selected prospect (W3 wedge — done-for-you brief). Pilot conversion target: 60–75% per precedent #16.

### Week 4 (Tue 2026-06-23 → Mon 2026-06-29): Deliver, Refine

13. **Deliver the Full Audit.** Customer keeps the report; sanitized findings (with permission) become case-study material for W1 sales material.
14. **First Full Audit invoice paid** → $2,500 in revenue (cumulative ~$3k after Lightning Audit).
15. **Convert pilot W3 customer** if applicable → +$300–$800/mo recurring.

**End-of-month target: $3,000–$3,800 cumulative revenue + 1 active W3 retainer.**

### Month 2–3: Flywheel

- 1 Full Audit per 2 weeks → $5,000/mo
- 2–4 active W3 retainers → $600–$3,200 MRR
- 1–2 Lightning Audits per week → $1,000–$2,000/mo
- **Realistic month-3 target: $4,000–$6,000/mo gross revenue, against $600–$800/mo burn.**

That is the self-sustaining position the operator asked for.

---

## What This Means for PR #370 and PR #372

**PR #372** (Research Cell pivot) — already marked `[SHELVED]`. No further action.

**PR #370** (Operator Brief Publication wedge) — **NOT shelved, NOT primary either.** Recommended action: **re-scope from "Publication infrastructure as primary wedge" to "Publication infrastructure as W3 back-end + W1 case-study delivery channel."** Three concrete amendments:

1. PR-A4's "Operator Brief Publisher" becomes the back-end for W3 (done-for-you briefs to named customers), not a public publication.
2. PR-A4's first issue is *not* "the inaugural Dharma Swarm operator brief"; it is *"audit findings on [OSS agent system X]"* — a piece of W1 marketing.
3. PR-A6 (cron registration) stays DEFERRED — same logic as before.

This is a re-scoping of #370, not a rejection of it. The new PR family proposed below adds the audit wedge alongside #370's existing infrastructure.

---

## Proposed PR Family — PR-W Series

Sibling PRs to #370. Engine is **revenue-first**, substrate-reuse-maximizing.

| PR | Title | Type | LOC budget | Active-track risk | Depends on |
|---|---|---|---|---|---|
| **PR-W0** | This document + burn audit deliverable | docs | ~200 + burn report | none | — |
| **PR-W1** | Audit Wedge Kit — sell sheet, report template, NDA template, pricing | docs/sales | ~300 docs | none | PR-W0 |
| **PR-W2** | Burn audit + free-provider routing for petri_dish workers | infra | ~100 (config only) | none | — |
| **PR-W3** | Audit harness — wires gauntlet + auto_grade + closure_v0 into a CLI: `dharma audit <target-repo>` | new module | ~300 | none (composes existing) | PR-W1 |
| **PR-W4** | Stripe Checkout integration + Calendly scheduler page (statically hosted) | infra | ~150 | none (new dir) | PR-W1 |
| **PR-W5** | Productized Eval Report (W2 wedge) — intake form + delivery template | new module | ~200 | none | PR-W3 |
| **PR-W6** | W3 (DFY Brief) — repurpose PR-A4 of #370 as customer-named-recipient channel | depends on #370 PR-A4 | ~100 | none | #370 PR-A4 + PR-W4 |

**Total LOC budget:** ~1,150. Engine-first, revenue-anchored.

**Cron registration:** **STILL DEFERRED.** Same gate as PR-R6: 30 days of green manual operation first.

---

## Doctrinal Verification

| Property | This slate |
|---|---|
| Coherent | ✅ Composes existing owners (`audit_graph`, `auto_grade`, `gauntlet`, `closure_v0`, `lineage`, `opportunity_dispatcher`); no new substrate. |
| Metabolically alive | ✅ Each W ships a runnable artifact and a saleable outcome; revenue is the deterministic acceptance signal. |
| Reality-grounded | ✅ Wedge ranking is grounded in 18 external precedents, not vision. |
| Replayable | ✅ Every audit deliverable is a `closure_v0.EvidenceReceipt` chain — bit-for-bit replay is the W1 differentiator. |
| Witness-capable | ✅ Customer receives receipts; we keep sanitized case-studies. |
| Survives world contact | ✅ Kill condition: $0 revenue at day 45 → re-evaluate; $0 at day 90 → hard pivot. |
| Without losing telos | ✅ Audits sell *honesty about agent failure modes* — directly aligned with Jagat Kalyan constraint. |

**All 9 Master Prompt forbidden actions cross-checked:**
- No AGI claim; this is a services business.
- No uncontrolled self-modification; substrate stays read-only.
- No autonomous capital deployment; Stripe Checkout requires human approval per invoice.
- No autonomous external messaging; all outreach DMs require operator approval.
- No deceptive memetic engineering; audit findings are reality-grounded.
- No parallel governance; defers to operator on pricing + customer selection.
- No vague prose; every wedge has concrete pricing, deliverable, timeline.
- No new substrate; reuses existing modules.
- No meta-frameworks; ships sell sheets + report templates + Stripe.

---

## Kill Conditions for the Wedge

| Trigger | Action |
|---|---|
| **Day 30: $0 revenue** | Cancel outreach approach; revisit pitch; check if pricing too high (drop Lightning Audit to $250) or too low |
| **Day 45: <$1,500 cumulative** | Hard-pivot: try W2 (Productized Eval) as primary instead of W1 |
| **Day 90: <$2k MRR cumulative** | Acknowledge wedge missed; revisit Pieter Levels-style audience-first path; accept 6–18 month timeline |
| **Telos violation** (e.g., audit findings inflated to upsell) | Cancel the contract, refund the customer, document publicly |

---

## What I'm Asking the Operator to Decide

**Three questions:**

1. **Does W1 (Agent-System Audit Reports) match your willingness to do sales calls + cold outreach?** This is the hidden assumption that breaks 70% of solo AI consulting attempts (precedent §3 Category 2). If the answer is "no," the slate's top recommendation flips to W2 (Productized Eval — lower-touch, higher-volume).
2. **Do you have any existing audience / inbound / warm leads I should know about?** (Twitter, GitHub stars, prior consulting clients, AI safety community contacts, Mt. Kailash research community, JLPT community.) Changes 30-day prospects materially.
3. **Operator Brief Publication (PR #370) — repurpose per the three amendments above, or fully shelve in favor of the audit wedge?**

Once you answer, I'll open the PR-W series as a sibling PR family to #370 — same engine-first pattern as PR-R was, but revenue-anchored instead of research-anchored.

---

## Files in this drop (PR-W0)

- `docs/reports/wedge_resurvey_burn_and_substrate_audit_v1.md` (internal substrate inventory + burn audit, already on disk)
- `docs/reports/wedge_candidate_slate_v1.md` (this document — Deliverable 6)
- `docs/research/wedge_precedents_sub90day_revenue_2026-05-29.md` (external precedents, 355 lines)
- `inter_agent/devin/outbound/2026-05-29-devin-wedge-resurvey.md` (outbound notice — drafted next)

**Zero code. Zero active-track risk.** Code PRs (PR-W1..W6) ship only after operator answers the three questions above.
