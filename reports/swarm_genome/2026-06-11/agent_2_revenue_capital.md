# Agent 2 Receipt: Revenue / Capital / Self-Funding Strategist

Date: 2026-06-11
Mode: read-only scan
Question: How does the organism fund itself and become economically alive?

## Files Read By Family

Mission and governance:
- `docs/agent_tasks/2026-06-11_swarm_genome_convergence_spec.md`
- `docs/governance/ACTIVE_TRACK.yaml`
- `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`
- `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md`

Revenue organs:
- `dharma_swarm/revenue/*.py`
- `scripts/revenue/*.py`
- `docs/offers/agentic-code-governance-sprint.md`
- local `~/.dharma/revenue_*` state

Capital and trading:
- `reports/capital_lab/`
- `dharma_swarm/capital_lab/*.py`
- `dharma_swarm/ginko_*.py`
- `docs/architecture/SHAKTI_GINKO_ORGAN.md`
- `docs/GINKO_ENHANCEMENT_WAVE.md`
- `requirements-ginko.txt`
- local `~/.dharma/ginko`

Scrappy cash motion:
- `reports/anatomy_altitude_2026-06-10/lane_A_economic.md`
- local `~/.cashclaw/*` receipts
- `docs/research/wedge_precedents_sub90day_revenue_2026-05-29.md`

## Claims With Source References

1. Governance already names revenue as a spine objective: `revenue-external-humans-served`, measured by external humans acting and first cash receipt. Source: `docs/governance/ACTIVE_TRACK.yaml:61-64`.
2. No active track currently serves that objective; active tracks serve substrate-nativeness. Sources: `docs/governance/ACTIVE_TRACK.yaml:128-136`, `:240-247`, `:293-300`, `:405-412`.
3. The Venture Cell One Law requires real gated outcomes before status claims. Source: `docs/governance/VENTURE_CELL_PORTFOLIO.yaml:13-16`.
4. Revenue Wedge exists to find the first self-funding offer, with target `$10k`, and human approval for outreach/spend. Sources: `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md:3-14`, `:28-33`, `:58-75`.
5. The clearest sellable wedge is Agentic Code Governance Sprint, priced `$5k-$25k`. Sources: `dharma_swarm/revenue/spine.py:142-168`, `docs/offers/agentic-code-governance-sprint.md:1-5`, `:97-102`.
6. RevenueSpine can track target, outreach, engagement, payment, and reinvestment, but local state appears operationally empty beyond one offer row. Source: `dharma_swarm/revenue/spine.py:49-74`.
7. RevenueScout is wired but starved; code skips GitHub without `GITHUB_TOKEN`, and local cycles show zero targets/drafts. Source: `dharma_swarm/revenue/scout_daemon.py:164-173`.
8. Scout intel source path likely points at the wrong root by resolving `dharma_swarm/dharma_swarm` before `docs/offers`. Source: `dharma_swarm/revenue/scout_daemon.py:253-256`.
9. CashClaw is the freshest near-cash motion but still unpaid: local DB has submitted PR claims, `claims.json` is malformed, and prior report records lifetime revenue `$0`. Source: `reports/anatomy_altitude_2026-06-10/lane_A_economic.md:9-12`, `:48-51`.
10. Capital Lab is deliberately fixture/paper-only: live readiness, live authority, and broker write authority are false/zero. Sources: `dharma_swarm/capital_lab/broker_paper_membrane.py:1-6`, `:24-30`; `dharma_swarm/capital_lab/risk_governor.py:24-29`.
11. Capital Lab alpha evidence is partial and blocked: score around 41, clean false, no live authority. Source: `reports/capital_lab/goal_a_12h/GOAL_A_CLOSEOUT_20260606T023150Z.md:1-12`, `:40-58`.
12. Ginko is economic intelligence and paper-trading substrate, not live capital; live gates require much stronger Brier evidence. Sources: `dharma_swarm/ginko_orchestrator.py:17-20`, `dharma_swarm/ginko_brier.py:1-10`, `:369-405`.

## Revenue Organ Map

- `RevenueSpine`: semi-working ledger; offer exists; no recorded customers/payments.
- `RevenueScoutDaemon`: semi-live but starved by missing token and likely path bug.
- `scripts/revenue/find_targets.py` and `draft_outreach.py`: semi-working manual prospecting and drafting with no-spam gate.
- `Agentic Code Governance Sprint`: strongest service wedge.
- `Revenue Wedge Pipeline`: semi-working intelligence loop, not directly monetized.
- `Campaign X-Ray`: held/stale; gate score and revenue evidence weak.
- `CashClaw`: closest to external money; PR claims open/unpaid.
- `Darshan`: audience/trust compounding; monetization deferred.
- `Shakti Ginko`: incubating wealth metabolism; Trading Lab paper-only.
- `Capital Lab`: high-quality fixture/paper proof; live trading aspirational and correctly blocked.

## Health Labels

- Working: capital_lab fixture contracts/risk membrane; some revenue codepaths and tests.
- Semi-working: RevenueSpine, RevenueScout, CashClaw PR loop, Ginko signal loop.
- Aspirational: external broker-paper, live trading, scaled Shakti Ginko, grants/fellowships.
- Stale: Campaign X-Ray status, malformed CashClaw claims JSON, thin Brier validation.
- Duplicate: revenue doctrine exists in Venture Cell, Revenue Wedge, economics docs, and active-track objectives without one owner.
- Bloated: capital-lab branch carries large unrelated history; extraction is required.
- Dangerous: treating paper/fixture capital systems as live; autonomous outreach without human approval.
- Unknown: current network state of PR bounties and external prospects.

## Strongest Near-Term Self-Funding Paths

1. Sell Agentic Code Governance Sprint / AI agent audit as direct service.
2. Create a smaller entry offer, for example `$500-$2.5k` paid audit, then upsell governance sprint.
3. Close CashClaw bounty/contract PRs if network verification shows payability.
4. Use Darshan and Loomwork for trust/audience compounding, not immediate revenue.
5. Keep Ginko/Capital Lab future-facing until evidence, paper broker, and operator lease exist.

## Top 10 Findings

1. Revenue doctrine exists, but confirmed cashflow is zero.
2. Fastest self-funding path is service sales, not trading.
3. Agentic Code Governance Sprint is the clearest sellable wedge.
4. RevenueScout is close to producing prospects but blocked by env/path issues.
5. RevenueSpine is structurally ready and operationally empty.
6. CashClaw is closest to external money but unpaid.
7. Capital Lab is honest and non-live by design.
8. Ginko has real risk gates and insufficient predictive evidence.
9. Governance recognizes revenue but does not staff it.
10. Economically alive means first paid external human outcome, not more dashboards.

## Top 10 Weak Spots

1. No active revenue track.
2. No sent outreach.
3. No recorded targets in RevenueSpine.
4. Missing `GITHUB_TOKEN` for scout.
5. Scout offer path likely wrong.
6. CashClaw `claims.json` malformed.
7. CashClaw claims are open/unmerged.
8. Ginko Brier evidence far below live threshold.
9. External paper broker evidence absent.
10. Live trading blocked by correct safety gates, not by a small code task.

## Final Command Map Must Include

- Revenue objective ownership.
- RevenueSpine counts.
- Scout cycle errors and zero-output receipts.
- Pending outreach drafts.
- CashClaw PR claim status.
- Ginko Brier validation.
- Capital Lab live-readiness zeros.
- Dry-run target scouting.
- Draft-only outreach command.
- No-live-trading authority verifier.

## Uncertainties

- PR bounty states were not network-verified.
- No mutating revenue pipeline was run.
- CashClaw partly lives outside this worktree.
- Cron/launchd live state was inferred from logs/state, not restarted.

## Suggested Verifiers

```bash
find ~/.dharma/revenue_spine -maxdepth 1 -type f -print -exec wc -l {} \;
tail -n 20 ~/.dharma/revenue_scout/cycle_log.jsonl
python3 -m json.tool ~/.dharma/ginko/brier_dashboard.json
sqlite3 ~/.cashclaw/evolution.db 'select claim_id,repo,issue_number,status,pr_url,result from claims order by updated_at desc;'
python3 scripts/revenue/find_targets.py --dry-run --max-results 10
python3 scripts/revenue/draft_outreach.py --list-pending
rg -n 'LIVE_READINESS|BROKER_WRITE_AUTHORITY|external_broker_paper_evidence|edge_validated|GITHUB_TOKEN' dharma_swarm reports docs scripts
```
