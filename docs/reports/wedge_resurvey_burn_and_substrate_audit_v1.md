# Wedge Re-Survey Pre-Work — Burn Audit + Monetizable Substrate Inventory

**Date:** 2026-05-29
**Trigger:** Operator shelved PR #372 (Research Cell pivot). Research is important but not the right wedge for self-sustaining economic funding. New filter: **30-day time-to-first-dollar.**
**Companion:** External precedent survey running in parallel; final synthesis (Deliverable 6) merges this audit with that survey.
**Active track:** `runtime-truth-spine-2026-06` — not displaced. This is docs-only.

---

## Headline findings

1. **The $2k/mo burn figure is operator-reported, not measured.** `VENTURE_CELL_REVENUE_WEDGE.md:33` still reads `current_known_burn = 0 (pre-launch)`. The substrate to measure burn exists (`dharma_swarm/llm_burn.py`, `cost_tracker.py`, `BurnReportFact` schema) but has never been run against a real cost log. **First action recommended: instrument the burn before designing the wedge.** Cannot optimize what is not measured.

2. **Free-provider escape hatch is already coded.** `llm_burn.py:21-33` defines `FREE_PROVIDERS = {local, nvidia_nim, ollama, ollama_cloud, openrouter_free}` and `FREE_MODEL_MARKERS = (":free", "glm-5", "kimi-k2.5", "minimax-m2.7")`. **If the $2k/mo burn is mostly cloud-LLM, a 60-80% cut is reachable in days without losing capability** — and this should be done in parallel with wedge work, not as an alternative.

3. **The repo already has a substantial paid-product surface.** `api/` mounts ~20 FastAPI routers including `revenue`, `opportunities`, `evolution`, `lineage`, `dashboard_new`, `chat`, `fleet`. The product layer is already on disk — what's missing is auth, billing, and a single useful externally-visible endpoint.

4. **The candidate wedges that fit the 30-day filter are NOT research-output. They are services/products that wrap the substrate already on disk.** Specifically: agent-system audit-as-a-service, code-graph snapshot reports, paid eval reports, opportunity-pipeline-as-a-service, custom Cron-driven brief subscriptions. Each has paying analogs in the wild.

---

## Part 1 — Burn Audit (where does $2k/mo go, and what can be cut today)

### What we know without instrumenting

| Source | Status | Notes |
|---|---|---|
| Operator-reported total | $2k/mo | Stated this session; no breakdown |
| Governance doc claim | `current_known_burn = 0 (pre-launch)` | `VENTURE_CELL_REVENUE_WEDGE.md:33`. Stale by months. |
| Code-side instrumentation | **Built, unrun** | `llm_burn.py` (normalizes cost logs), `cost_tracker.py` (161 LOC, has `log_cost` + `cost_summary`), `BurnReportFact` schema — never wired to a real log file. |

### What can be measured in <1 day

1. Run `dharma_swarm.cost_tracker.cost_summary(since_hours=720)` (30-day window) against whatever local cost log exists. If empty, the burn is happening outside the cost-tracker — i.e. via raw Anthropic / OpenAI / OpenRouter dashboards.
2. Pull last-30-day invoices from each LLM provider's billing dashboard (Anthropic console, OpenAI usage, OpenRouter, Cursor sub, Claude Code sub, etc.). 15-minute manual task.
3. Pull last-30-day infra invoices (Vercel, Render, Fly, Railway, Cloudflare, GitHub Actions overage, etc.). 10-minute manual task.
4. Categorize: (a) per-call API spend (variable), (b) flat subscriptions (Cursor, Claude Pro, GPT Plus, etc.), (c) infra (hosting, CI), (d) one-shot tools (book purchases, course subs).

### What can be cut today (regardless of wedge)

Code-side artifacts say the cuts below are reachable without losing capability — the routing infrastructure already understands free providers:

| Action | Mechanism | Expected cut |
|---|---|---|
| Route `petri_dish` workers to `openrouter:free` models | `experiments/petri_dish/llm_client.py` already supports openrouter; mark workers with `FREE_PROVIDERS` per `llm_burn.py:21` | 80-95% of petri_dish call cost |
| Route `auto_grade` deterministic scoring off LLM entirely | Scoring is pure-function per `auto_grade/engine.py`; no LLM needed | 100% of any LLM-graded path |
| Cap any cron-driven loop with `--max-usd-per-run` flag (pattern in `dharma_swarm/cost_tracker.py`) | Already a pattern in the codebase; just needs flag passed | Prevents tail-blowups |
| Audit subscriptions: Cursor + Claude Pro/Max + GPT Plus + Cursor + Replit + extras | Cancel anything not used weekly | $20-80/mo per unused sub |
| Drop OpenRouter premium-model fallback when free-tier suffices | Configuration only | 30-60% of openrouter spend |

**A defensible target:** $2k/mo → $300-600/mo within 2 weeks while measuring, without giving up any current capability. Lower burn → lower revenue bar → easier wedge to find. **This is the single highest-leverage move and is wedge-agnostic.**

### Burn-audit deliverable (first concrete work product)

```
docs/reports/burn_report_2026-05-29.md
```
Format: per-provider monthly spend, top-10 most expensive call patterns, top-5 cuttable items with estimated savings, monthly burn-target proposal (current $2k → target $X).

**Estimated effort:** 1 day. Substrate already on disk.

---

## Part 2 — Monetizable Substrate Inventory (what could a paying user touch in 30 days)

Each entry: **what's already on disk** (the substrate), **what's missing for a paying user** (the delta), **plausible price point**, **30-day feasibility** (subjective, T-shirt sized).

### S1 — Agent-System Audit Reports

**What's on disk:**
- `dharma_swarm/audit_graph.py`, `code_graph_analyzer.py` family of modules (per memory of prior sessions)
- `closure_v0.EvidenceReceipt` — replay-grade provenance
- `dharma_swarm/lineage.py` + `api/routers/lineage.py` — provenance graph queryable via HTTP
- `benchmarks/gauntlet.py` 5-tier adversarial pressure
- `dharma_swarm/agent_constitution.py`, `telos_substrate.py`

**What's missing for a paying user:**
- Anonymized intake (customer drops their agent repo URL or code archive)
- Sanitization layer (don't leak their code into our training)
- Report template (PDF or markdown delivered via email)
- Payment + scheduling (Stripe Checkout, Calendly)

**Plausible price point:** $500-2,500 per audit (one-shot). Comparable to a security audit of a small agent system. Tier: "self-serve scan" ($500) vs "human-reviewed audit" ($2,500).

**30-day feasibility:** **HIGH.** First customer can be a friend / Twitter contact / HN reader. The audit itself is mostly manual (Wizard-of-Oz pattern from precedents) while automating gradually. First dollar plausibly in week 1-2.

**Why this fits Dharma Swarm specifically:** the audit-graph + gauntlet + telos-substrate + lineage stack IS an agent-system audit tool. The repo's own existence is the demo.

---

### S2 — Operator Brief Subscription (PR #370's wedge — sharpen, don't shelve)

**What's on disk:**
- PR #370's PR-A4 (Operator Brief Publisher) about to ship
- `daily_operating_brief.py` already exists
- `revenue/operator_brief_publisher` planned in PR-A4
- `dharma_swarm/opportunity_dispatcher.py` + `api/routers/opportunities.py` — opportunity pipeline already wired

**What's missing for a paying user:**
- Subscription page (Substack / Beehiiv / Ghost / paid Substack — pick one)
- 1 sample issue + 4 weeks of consistent delivery
- A specific reader (not "AI builders" — "solo devs running multi-agent systems who burn >$1k/mo on LLMs")

**Plausible price point:** $20-50/mo subscription, or $300/yr. 100 subscribers @ $20/mo = $2k MRR. The precedent report (running in parallel) will give the realistic conversion-rate prior.

**30-day feasibility:** **MEDIUM-HIGH.** Cold subscription wedges typically take 60-90 days to hit $2k MRR without an existing audience. Faster if the operator already has 1k+ engaged followers anywhere (Twitter, GitHub, Substack). Need to verify.

**Why this fits Dharma Swarm specifically:** the Brief IS the natural output of the swarm — it's what the system makes. Zero substrate gap. The reason research-organ was wrong: it requires building an oracle first. The Brief requires nothing except writing it.

**This is PR #370's existing wedge. Sharpening means:** picking the specific reader, the specific topic, the specific first issue. Not abandoning #370.

---

### S3 — Eval Report as a Service

**What's on disk:**
- `dharma_swarm/auto_grade/` — 13 deterministic metrics for any agent output
- `dharma_swarm/ecc_eval_harness.py` — 11 evaluator functions + `pass_at_k`
- `benchmarks/gauntlet.py` — 787 LOC of adversarial pressure tests
- `dharma_swarm/cascade_domains/research.py`

**What's missing for a paying user:**
- Intake form: "give me 50 prompts + your agent's outputs and I'll score them on 13 dimensions"
- PDF report generator
- Payment + scheduling

**Plausible price point:** $200-1000 per eval. Recurring if customer wants weekly/monthly eval of their agent in production.

**30-day feasibility:** **MEDIUM.** Higher friction than S1 because the customer has to produce traces, and the value-add is murkier ("why would I pay for scoring vs DIY?"). But there's a real market — Patronus, Galileo, LangSmith all charge for this.

**Why this fits Dharma Swarm specifically:** `auto_grade.AutoGradeEngine.grade()` already exists. 95% of the technical work is done. The gap is intake + delivery.

---

### S4 — Opportunity Pipeline as a Service

**What's on disk:**
- `dharma_swarm/opportunity_dispatcher.py` + `opportunity_refill.py`
- `api/routers/opportunities.py` with `/refill` POST endpoint already implemented
- `OpportunityRow` schema
- 11+ canonical opportunity stages already enumerated

**What's missing for a paying user:**
- Hosted instance (auth, multi-tenant, billing)
- One useful intake source plugged in (Twitter mentions, RSS feed, HN/Reddit watch, etc.)
- Slack/Discord/email delivery channel

**Plausible price point:** $50-200/mo per user. Personal opportunity tracker.

**30-day feasibility:** **MEDIUM-LOW.** Bigger product surface than the others; auth + multi-tenant + billing is real work for 30-day window. But the core engine is the most production-grade of any surface inventoried here.

**Why this fits Dharma Swarm specifically:** `opportunity_dispatcher` is the most concretely-shippable "agent does work for you" surface. Other categories require the customer to bring data; this one generates data for them.

---

### S5 — Custom Cron-Driven Brief Subscriptions (small operator briefs done-for-you)

**What's on disk:**
- `dharma_swarm/cron_runner.py` already exists
- `daily_operating_brief.py` template
- Multi-channel delivery substrate

**What's missing for a paying user:**
- 1-1 sales conversation per customer ("what brief do you want, delivered when, where")
- Templating per customer
- Payment

**Plausible price point:** $200-800/mo per customer. Boutique done-for-you.

**30-day feasibility:** **HIGH.** This is Wizard-of-Oz S2 — manually deliver the Brief to 5-10 customers individually, with their custom topic. No infrastructure needed except email. First dollar plausibly in week 1.

**Why this fits Dharma Swarm specifically:** the same Brief substrate, but the value-add is the human-curated specificity. Doesn't require an audience. Cold outreach feasible.

---

### S6 — Repo-as-a-Demo: Sponsored OSS / GitHub Sponsors

**What's on disk:** The repo itself. ~5000 LOC of evaluation substrate. Goodfire-, Future-House-, METR-adjacent positioning.

**What's missing for a paying user:** Public repo (currently private?), a README that communicates value to AI-safety / alignment funders, a GitHub Sponsors tier setup.

**Plausible price point:** $20-200/mo per sponsor. Realistic monthly revenue 0-$1k unless the repo goes mildly viral. Unreliable.

**30-day feasibility:** **LOW for $2k/mo target.** Sponsorship economics are bad except for known names. Listed for completeness; not recommended as primary wedge.

---

## Ranking matrix (provisional, pre-external-precedent-merge)

Score = (30-day first-dollar probability) × (substrate reuse %) ÷ (active-track risk).

| Wedge | First-dollar prob (30d) | Substrate reuse | Active-track risk | Score (relative) |
|---|---|---|---|---|
| **S1 — Agent-System Audit Reports** | High (~70%) | ~85% | None (docs + new intake) | **★★★★★** |
| **S5 — Custom Cron Briefs (DFY)** | Very High (~85%) | ~70% | None | **★★★★★** |
| **S2 — Operator Brief Subscription** | Medium-High (~50%) | ~95% | None (PR #370 path) | **★★★★** |
| **S3 — Eval Report as a Service** | Medium (~35%) | ~90% | None | **★★★** |
| **S4 — Opportunity Pipeline SaaS** | Medium-Low (~25%) | ~85% | Low (auth + multi-tenant) | **★★** |
| **S6 — GitHub Sponsors** | Low (~10%) | 100% | None | **★** |

**Provisional top-3:** S1 (Audit), S5 (DFY Briefs), S2 (Subscription Brief — i.e. PR #370 sharpened, not killed).

These three are mutually reinforcing: S1 generates testimonials/case-studies that feed S2 content that feeds the S5 sales conversation. They share substrate. **They are not three separate wedges — they are three monetization layers of the same core product (operator brief + audit on agent systems).**

---

## What this means for PR #370

PR #370 is **not the wrong PR**; it was the **wrong abstraction level.** PR #370 ships publication infrastructure for a Brief whose reader and offer are unspecified. The fix is not to shelve #370 but to **specify the reader and the offer** as part of its acceptance criteria:

- **Reader (specific):** solo developers running multi-agent systems who currently burn >$1k/mo on LLMs/tools with unclear ROI. Reachable on: Twitter (AI dev community), HN, indie hackers, Latent Space, AI Engineer World's Fair attendees.
- **Offer:** weekly Operator Brief — what happened in autonomous-agent infra this week, plus one specific audit finding from running Dharma Swarm's tooling against an open agent system. Free for first 4 weeks; $20/mo after.
- **Lead magnet for S1:** every fifth issue includes "I audited [open agent repo] this week; here's what I found." Establishes audit-as-a-service credibility without selling yet.

This sharpens PR #370 rather than replacing it. The new PR family proposed in Deliverable 6 (next document) will: (1) sharpen PR #370 with the reader/offer specification, (2) add S1 (Audit) as a sibling PR-B family, (3) add the burn audit + free-provider routing PR-Z as the highest-leverage immediate win.

---

## Open questions for the operator (will be asked once external precedents subagent completes)

1. Existing audience? (Determines whether S2 conversion rate is realistic at 30 days vs 90+ days.)
2. Willingness to do manual Wizard-of-Oz (S1/S5) vs. only ship infrastructure?
3. Is the repo currently public/private? (Affects S6 + audit-tool credibility-marketing.)
4. Any existing customer leads / inbound interest / "people who have asked about this"?

---

## Next deliverable

`docs/reports/wedge_candidate_slate_v1.md` — **Deliverable 6**. Merges this audit with the external precedent survey (in flight). Picks top wedge (or top-2 with sequencing), specifies the first 5 work packets, ships as sibling to PR #370 (not replacement).
