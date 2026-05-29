# Devin Outbound — Wedge Re-Survey (30-Day Time-to-First-Dollar)

**From:** Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only`
**Date:** 2026-05-29
**Branch:** `devin/2026-05-29-wedge-resurvey` (forked from `devin/2026-05-28-autonomous-activation-architect`, parent PR #370)
**Active track:** `runtime-truth-spine-2026-06` — not displaced.
**Supersedes:** PR #372 (Research Cell pivot) — `[SHELVED]` by operator earlier today.

## What landed

Three docs + this notice. **Docs-only. Zero code. Zero active-track risk.**

1. `docs/reports/wedge_resurvey_burn_and_substrate_audit_v1.md` — internal substrate inventory + burn audit. Found: $2k/mo burn figure is operator-reported, not measured (`VENTURE_CELL_REVENUE_WEDGE.md:33` still says `current_known_burn = 0`). `dharma_swarm/llm_burn.py` and `cost_tracker.py` already exist — burn-instrumentation substrate is on disk, just unrun. Free-provider routing (`FREE_PROVIDERS = {local, nvidia_nim, ollama, openrouter_free, ...}`) is already coded.
2. `docs/research/wedge_precedents_sub90day_revenue_2026-05-29.md` — 18 external precedents (Tony Dinh, Pieter Levels, jxnl.co, Ben's Bites, Patronus, etc.) with brutal honesty about survivorship bias. Headline: 54% of indie-hacker AI products make $0; the outliers all had 20k–600k existing audience.
3. `docs/reports/wedge_candidate_slate_v1.md` — **Deliverable 6.** Six wedges scored on six dimensions; top-3 recommended.

## The brutal one-line synthesis

**The only path that reaches $2k/mo in 30 days without an existing audience is direct outreach with a $2k–$5k audit deliverable.** Everything else takes 60–180 days. The Pieter Levels playbook required 350k Twitter followers built over a decade.

## Top recommendation

**W1 — Agent-System Audit Reports.** $500 Lightning Audit + $2,500 Full Audit + optional $1,500–$2,000/mo retainer. Substrate (`audit_graph`, `auto_grade`, `gauntlet`, `closure_v0`, `lineage`) is 90% already on disk. Gap is a sell sheet + report template + Stripe Checkout — ~3 hours of work, not 3 weeks. Realistic first dollar week 2–3; $3–4k cumulative revenue by day 30 if 1–2 sales close.

**W2 — Productized Eval Reports** ($500–$1.5k per eval) as the funnel into W1.

**W3 — Done-for-You Operator Briefs** as PR #370 sharpened, NOT shelved. PR-A4's Operator Brief Publisher becomes W3's customer-named-recipient back-end, not a public publication.

## What this does to PR #370

**Not shelved. Re-scoped.** Three amendments:
1. PR-A4's Operator Brief Publisher becomes W3 back-end (named-customer delivery), not public Brief.
2. PR-A4's first issue is audit findings on an OSS agent system — i.e. W1 marketing material.
3. PR-A6 (cron) remains DEFERRED.

## Concrete next-30-days plan

Week 1: burn audit + cut subscriptions ($2k → $600/mo target). Sell sheet + report template. One LinkedIn/HN post running gauntlet against an OSS agent system.
Week 2: free 30-min reviews with 3–5 inbound. One paid Lightning Audit ($500) by end of week 2.
Week 3: one paid Full Audit engagement ($2,500). Stripe Checkout live.
Week 4: deliver the audit, collect invoice, convert one W3 pilot.

**End-of-month target: $3,000–$3,800 cumulative.** Self-sustaining position by month 3.

## What I'm asking the operator to decide

1. **Are you willing to do cold outreach + 1-1 sales calls?** This is the hidden assumption that breaks 70% of solo AI consulting attempts. If "no," W2 (lower-touch productized eval) becomes the primary.
2. **Existing audience / warm leads I should know about?** (Twitter, GitHub stars, prior consulting clients, AI safety community, Mt. Kailash community, JLPT community.) Changes priors materially.
3. **PR #370 — re-scope per the three amendments, or fully shelve in favor of audit wedge?**

Once you answer, I open the PR-W series (PR-W1..W6, ~1,150 LOC budget) as a sibling PR family to #370.

## Doctrinal compliance

| Doctrine | Compliance |
|---|---|
| Coherent | ✅ Composes existing owners; no new substrate |
| Metabolically alive | ✅ Each W ships a saleable outcome; revenue is the deterministic acceptance signal |
| Reality-grounded | ✅ Grounded in 18 external precedents |
| Replayable | ✅ Audit deliverable IS a `closure_v0.EvidenceReceipt` chain |
| Witness-capable | ✅ Customer receives receipts |
| Survives world contact | ✅ Kill condition: $0 at day 45 → hard pivot to W2 |
| Without losing telos | ✅ Audits sell *honesty about agent failure modes* — aligned with Jagat Kalyan |

All 9 Master Prompt forbidden actions cross-checked clean.

## Authority

`external_worker_evidence_only`. All code PRs (PR-W1..W6) require operator approval before merge.
