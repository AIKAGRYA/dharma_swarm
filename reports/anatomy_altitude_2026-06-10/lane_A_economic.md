# Lane A — Economic Engine Deep-Read (2026-06-10)

**Question:** How does "the system funds itself" actually work today, across three horizons — scrappy (cashclaw), disciplined (capital_lab), strategic (the self-funding institution)?

**Method:** 10 files read end-to-end (not skimmed): `cashclaw_claim_and_do.py` (461L), `cashclaw_multi_platform_scan.py` worktree (129L) + standalone v2 (643L), `cashclaw_revenue_hydra.py` (1805L), `honest_evidence.py` (175L), `risk_governor.py` (335L), `broker_paper_membrane.py` (967L), `contracts.py` (195L), `scout_daemon.py` (443L), `intelligence.py` (276L). Plus full reads of `VENTURE_CELL_PORTFOLIO.yaml`, `ARJUNA.md` (incl. 2026-06-06 Krishna Inversion amendment), `STRATEGY_VERDICT.md`, and headers of `NORTH_STAR_ARCHITECTURE.md`, `ROADMAP_TO_PARITY.md`, `alpha_evidence.py`. Runtime verification: test suites executed, live PR states queried via `gh`, scheduler state and state-dirs inspected.

---

## 0. Headline (honest capability, one paragraph)

Lifetime revenue is **$0 — verified, not inherited from prior audits**: every bounty PR the system has ever opened is still OPEN/unmerged as of 2026-06-10 (live `gh pr view` on all six). The near-term engine (cashclaw) RUNS — it scans, claims, implements, and submits real PRs on a real schedule via hermes's scheduler — but has converted nothing to cash. The mid-game engine (capital_lab) is the highest-quality code in the economic stack (33/33 tests, real detect-and-halt risk controls, López de Prado-grade statistics) but is **fixture-only by explicit design**: `LIVE_READINESS = 0`, no market data, no broker, no capital, and it lives on a side branch, not main. The long-term shape exists only as doctrine (ARJUNA, VENTURE_CELL_PORTFOLIO, north-star docs) — and the portfolio's own governance says the quiet part out loud: the `revenue-external-humans-served` spine objective has **no active track** (`~/dharma_swarm/CLAUDE.md` and `~/dharma_swarm_live/CLAUDE.md`, "Spine objectives" block). The three horizons currently do **not** feed each other; they are three disconnected organs sharing only a worldview.

---

## 1. Horizon 1 — Scrappy near-term: cashclaw (bounty/revenue hydra)

### 1a. What exists, where

Three generations, in chronological order:

1. **Hydra (governed, lease-gated)** — branch `cashclaw/revenue-hydra-v1` at `~/dharma_swarm_cashclaw`, 8 commits ahead of main (`git log main..HEAD`: 227895ec5 "revive CashClaw Revenue Hydra from stash — 14K LOC, 19 modules, 9 tests" → 25d1e2c27 "push-token human gate"). Driver: `scripts/revenue/cashclaw_revenue_hydra.py` (read end-to-end, 1805L). Library: `dharma_swarm/revenue/` on this branch adds 11 modules main lacks (`cashclaw_autopilot.py`, `live_intake.py`, `live_intake_sources.py`, `action_gateway.py`, `idea_gauntlet.py`, `cashclaw_evolution.py`, `cashclaw_employees.py`, …).
2. **Claim-and-do (aggressive, thin)** — `scripts/revenue/cashclaw_claim_and_do.py` (read end-to-end) + `cashclaw_multi_platform_scan.py` + `cashclaw_claim_tracker.py` + `cashclaw_evolution_runner.py`/`cashclaw_breed_variants.py`.
3. **Standalone repo** — `~/cashclaw` (own git repo, main branch, 3 commits). `cashclaw_claim_and_do.py` is byte-identical to the worktree copy (md5 `0af31cdd…` both). The newest-generation scanner is here: `cashclaw_multi_platform_scan.py` v2.0 (643L, read end-to-end — GitHub wide-search 20 queries + org scans + Polar.sh + Superteam + batched GraphQL competition detection writing `likely_claimed` per bounty) and `cashclaw_expanded_scan.py` (339L). README states the charter: "Generate real USD. Headline metric: dollars in bank… PRs shipped: 20+ across 7 repos. Revenue earned: $0. Phase: Naked Validation (falsification protocol)" (`~/cashclaw/README.md`).

### 1b. What RUNS (verified)

- **Scheduler loop RUNS — in hermes's own scheduler, not OS crontab.** `~/.hermes/cron/jobs.json` carries five live cashclaw jobs, all `enabled: true, last_status: ok`: `cashclaw-evolution-scan` (every 240m, 17 completed), `cashclaw-daily-claim-scan` (daily 05:00, 5 completed), `cashclaw-claim-status-check` (every 6h, 11 completed), `cashclaw-evolution-breed` (weekly, 1 completed), `Bounty Scanner (2h)` (12 completed). This confirms and extends the 2026-06-08 memory finding.
- **Scan output is fresh**: `~/.cashclaw/latest_scan.json` modified 2026-06-10 18:00 (today).
- **Real external PRs exist** (live-verified via `gh pr view`, all `OPEN merged=null`):
  - claude-builders-bounty #2587 ($75) and #2588 ($150) — tracked in `~/.cashclaw/evolution.db` `claims` table with live PR-status JSON (`updated_at: 2026-06-10T09:00Z`, `merged: false`)
  - SecureBananaLabs/bug-bounty #5488 ($780 claimed value; demo-repo payout risk flagged in prior audit stands)
  - xevrion-v2/agent-playground #1389/#1390/#1391 ($50 each, claimed 2026-06-09/10 — NEW since the 06-08 audit; the loop is still producing)
  - commaai/openpilot #38152 (MetaDrive macOS fix, 2026-06-09 — a credibility PR, not a bounty)
- **Claim tracker RUNS**: evolution.db rows carry refreshed PR state (review_comments, additions), proving `cashclaw_claim_status-check` polls and writes.
- **Hydra test suite green**: `tests/test_cashclaw_revenue_hydra.py` — **21 passed in 0.25s** (executed this session).

### 1c. The human gate — graded honestly

Two different gate designs coexist:

- **Hydra gate (real, layered):** the hydra is structurally incapable of external mutation. Every cycle runs `CashClawAutopilot` in `mode: "dry_run"` (`cashclaw_revenue_hydra.py:176`), every packet must pass `build_lease_preflight` (lines 488–593: source-open check, hard-risk needles incl. prompt-exfiltration and wallet-action needles at lines 63–73, AI-forbidden-text check line 531, physical-world-dependency check line 533), a competition probe (lines 622–708, blocks at ≥3 matching open PRs / ≥3 claim comments / reserved-protocol detection, lines 980–991), a clone-only feasibility probe explicitly labeled "Rung 1 authority: public clone/read only… no fork, no branch push, no PR" (lines 711–724), and a killshot quality gate requiring ≥90 on five scores plus passing-test receipts (lines 22–28, 1455–1532). External action requires the operator to utter an exact approval phrase: `"APPROVE REVENUE LEASE {lease_id}"` (line 1655); the lease-request file self-declares `status: draft_only_not_granted` (line 1660). **Grade: RUNS as a no-side-effects scanner; the entire external-action arm is WIRED-BUT-DORMANT pending operator leases — by design.**
- **Claim-and-do gate (positional, partly decorative):** the docstring promises "`--push-token` is required to fork+push+PR… NEVER call gh pr create or git push without explicit push-token" (`cashclaw_claim_and_do.py:20–23`), and the script genuinely contains no push/PR-creation code — `claim_bounty()` terminates at `status: "ready_for_work"` (line 297). **However, the `--push-token` argument is parsed at line 380 and never read again — zero enforcement logic exists.** The push instruction is instead embedded in the task file handed to a downstream Claude Code agent ("After implementing, create a PR using: gh pr create…", line 288). So the gate holds because a human must point an agent at the task file, not because the token mechanism works. Clean finding: **the token is dead code**; the real gate is the missing push path plus the downstream human-in-the-loop. The six live PRs above prove the downstream submit path is exercised in practice.

### 1d. Safety/quality heuristics in claim-and-do (all RUN, all keyword-grade)

Bounty-label requirement (lines 177–184), $500 value cap (191), 10-star floor with bounty-platform exemption (196–206), crowding skip at ≥3 existing PRs (215–220), risk-keyword skip (`security/vulnerability/exploit/pii/credentials`, 222–228). These are real and execute, but are the same paraphrase-evadable keyword class the 2026-06-01 telos-gate audit documented for self-mod gating.

### 1e. Known data-hygiene defects (verified)

- `~/.cashclaw/claims.json` is **malformed JSON** — begins with a bare comma (verified by parse failure + `head -c 600`). Anything consuming it with `json.load` breaks.
- `evolution.db` third claim row has an **empty primary key** (`claim_id` = ""), and its `result` column is empty while the other two carry live PR state — the SecureBananaLabs claim is half-tracked.

---

## 2. Horizon 2 — Disciplined mid-game: capital_lab

### 2a. What exists, where

Branch `capital-lab/build` at `~/dharma_capital_lab`, **127 commits ahead of main** (+95,870 lines). Package `dharma_swarm/capital_lab/`: `contracts.py` (195L), `honest_evidence.py` (175L), `risk_governor.py` (335L), `broker_paper_membrane.py` (967L), `alpha_evidence.py` (1251L) — first four read end-to-end.

### 2b. Component grades

| Component | Grade | Evidence |
|---|---|---|
| `honest_evidence.py` — Deflated Sharpe (Bailey–López de Prado) w/ skew-kurtosis adjustment + multiple-testing E[max] correction (lines 53–104), leakage detector (110–135), `evaluate_strategy` gate at DSR≥0.95 (141–175) | **RUNS** (as a library) | `test_capital_lab_honest_evidence.py` passes; correct asymptotic E[max] expansion at lines 31–42 |
| `risk_governor.py` — detect-and-halt controls: heartbeat staleness, market-data staleness, drawdown, order-rate, position, gross exposure; latching `engaged` flag blocking subsequent orders until operator `reset()` (76–222); drills are real inject-detect-block-plus-clean-negative-control experiments, "no hard-coded engaged=True literals" (docstring lines 8–11, drills 242–334) | **RUNS** | tests pass; drill receipts computed, not asserted |
| `broker_paper_membrane.py` — full order lifecycle (submit/ack/partial/full/cancel/reject/expire) with hash-chained receipts (`parent_receipt_id`, lines 519–537), idempotent `client_order_id` (66–83, 573–585), ledger↔broker reconciliation that trips the governor on mismatch (605–663), AST-level AuthorityFence denying hyperliquid imports and order-placing call names (107–201) | **RUNS as fixture** | 33/33 capital_lab tests pass in 1.42s (executed this session) |
| `contracts.py` — frozen typed pipeline `Universe → Insight → PortfolioTarget → RiskAdjustedTarget → Order`, FLAT/abstain first-class (line 37), `knowledge_ts` PIT field (99), approved_weight≤requested invariant (156–159) | **RUNS** (as types) | tests pass |
| `alpha_evidence.py` — evidence-only membrane: provider coverage, lineage, 6 leakage traps, 6 required baselines, 6 cost categories, institutional scorecard; `AUTHORITY = "evidence_only"`, `CAPITAL_PERMISSION = "none"` (header lines 24–31) | **WIRED-BUT-DORMANT** | Goal A closeout: **41/100, clean=false, 25 blockers** (`ROADMAP_TO_PARITY.md` "Current honest state") |
| Live trading | **ASPIRATION** | `LIVE_READINESS = 0`, `LIVE_AUTHORITY = False`, `BROKER_WRITE_AUTHORITY = False`, `CLEAN = False` hard-coded module constants in both membrane (lines 24–27) and governor (26–29); membrane status string literally `"fixture_membrane_complete_blocked_live_authority_detected"` (line 30) |

### 2c. The lab's own honesty (notable — this code does NOT narrate past its build)

`ROADMAP_TO_PARITY.md` states plainly: *"No market data. No validated strategy. No real broker. No capital. No track record."* and names **provider famine as #1 risk** ("our entire edge is multi-model decorrelation and right now we have ~1 reliably-live family… partly an operator decision (fund the keys)"). The membrane's own blocker list records `agni_hyperliquid_live_capable_repo_present` and `HYPERLIQUID_PRIVATE_KEY_alias_present` as standing live-authority hazards it refuses to certify around (`broker_paper_membrane.py:797–807`). The strategy research (`STRATEGY_VERDICT.md`, 14 dossiers) concludes: *"The durable edge is not a strategy. It's the discipline… The strategies are commodities; the BS-detector (R3) and the honest combiner (R5) are the moat."* This is the anti-Profit-Mirage stance of `NORTH_STAR_ARCHITECTURE.md` (cites arXiv 2510.07920: published agentic-fund returns evaporate under leakage correction).

### 2d. Dock status — clean negative

`dharma_swarm/capital_lab/` is **not on origin/main** (`git ls-tree origin/main` empty in both worktrees) and appears as **untracked (`??`) stray files** in the `~/dharma_swarm` worktree (qwen/spine-adoption branch) — present on disk, owned by no commit there. Committed only on `capital-lab/build`. No module on main imports it. capital_lab also has **no cell entry** in VENTURE_CELL_PORTFOLIO.yaml — its nearest ancestor is `shakti-ginko` (status: INCUBATING, "Trading Lab cell is live-on-Agni (paper-only, hard-gated)", lines 108–113).

---

## 3. Horizon 3 — Strategic: revenue code on main + the billion-dollar shape

### 3a. `dharma_swarm/revenue/` on main (8 modules, 2509 lines)

- `scout_daemon.py` (read end-to-end): scout→ingest→parse→route→draft cycle; "Rule: NO AUTONOMOUS SPAM. Outreach drafts require human approval… it does NOT send messages" (lines 12–13). Registered as a real cron handler: `cron_runner.py:183` `_run_revenue_scout`, dispatch at `:876–877`. **RUNS — and the log proves it runs mostly on empty**: `~/.dharma/revenue_scout/cycle_log.jsonl` has **256 cycles since 2026-05-11, only 19 nonzero, 233 failed with "GITHUB_TOKEN not set"** (computed this session). The engine turns over every cycle and scouts nothing because one env var is absent in the cron environment. This is the single cheapest fix in the entire economic stack.
- `intelligence.py` (read end-to-end): regex/keyword claim extraction → competitor profiles → revenue patterns → `route_to_spine` creating `RevenueTarget`s for patterns with `dharma_swarm_fit ≥ 0.4` (lines 166–197). Persistence to `~/.dharma/revenue_intel/` works (`signal_log.jsonl` exists). **RUNS, low-signal** (keyword-grade parsing, hardcoded `estimated_value_usd=5000.0` in the inline scout, `scout_daemon.py:231`).
- `spine.py`, `telic_bridge.py`, `wedge_pipeline.py` — present on main; the spine is the target/offer/outreach state-store the daemon writes into. Wedge pipeline ties to `campaign-xray`, which the gauntlet **HELD at 28/100, revenue_usd: 0** (`VENTURE_CELL_PORTFOLIO.yaml:91–101`).

### 3b. Ecosystem position (axis d)

- **Stigmergy + signal bus: genuinely docked.** `scout_daemon._emit_stigmergy` writes `StigmergicMark` to `~/.dharma/stigmergy/marks.jsonl` (lines 352–373) and `_emit_signal` emits `REVENUE_INTEL_INGESTED` on the SignalBus (375–388). This is the one place the economic engine participates in the organism's nervous system.
- **Telos gates / witness: NOT docked.** Clean negative: zero imports of `telos_gates`, `TelosGatekeeper`, `dharma_kernel`, or witness in any cashclaw script or the branch's `cashclaw_autopilot.py`/`idea_gauntlet.py` (grep verified). The gauntlet has a `vision_telos_fit` *scoring weight* (`idea_gauntlet.py:45`) — a number, not a gate. Hydra governance is self-contained (its own preflight/lease JSON files), parallel to, not through, the 11-gate TelosGatekeeper. Same for capital_lab: NORTH_STAR names "telos veto (11 gates)" as the differentiator, but the shipped code enforces via its own RiskGovernor — TelosGatekeeper integration is **ASPIRATION**.
- **Evolution loop: parallel, not shared.** cashclaw has its own Darwin engine (`cashclaw_evolution.py`, `evolution.db` variant fitness, breed cron) entirely separate from `~/.dharma/evolution/archive.jsonl` and DarwinEngine. Two evolution systems, no shared archive.
- **A2A: indirect only.** The bounty loop lives in hermes's scheduler; no `a2a_bus` or spine `invoke_agent` involvement. The active spine-adoption track (`runtime-truth-spine-adoption-2026-06`) doesn't touch revenue surfaces.

### 3c. Vision dock points (axis b)

- **ARJUNA.md** (read in full): the economic engine is governed by the 2026-06-06 Krishna Inversion — "the flatlined self-evolution engine… is the organism's primary function failing, and therefore the five-alarm fire" — and the Amendment 2026-05-30 contact metric: *"one human outside this house is measurably better off."* By that canonical metric, the economic engine's score is the merged-PR count: **zero**. Note also the clean negative: ARJUNA.md contains no occurrence of "revenue", "fund", "money", or "trading" (grep verified) — money-as-fuel is doctrine in `~/.claude/cabinet/worldview/money_as_divine_force.md` and the portfolio's `metabolism:` node, not in the war-doctrine itself.
- **VENTURE_CELL_PORTFOLIO.yaml** (read in full): the metabolism is explicitly *not a domain*: `shakti_ginko: "wealth-metabolism organ, Jagat-Kalyan-DIRECT (trustee-not-possessor; Trading Lab = one cell)"` (line 63). The One Law (line 14): "No cell spawns, grows, or claims status except by closing a strange loop on a real, gated, verifiable outcome." **cashclaw has no cell entry at all** — it operates outside the portfolio's own index, which under the portfolio's rules makes it either an unregistered tentacle or a candidate for the next cell declaration.
- **ACTIVE_TRACK portfolio**: `revenue-external-humans-served — value leaves the house and someone acts on it (**no active track**)` — the governance layer itself records the gap (both `~/dharma_swarm/CLAUDE.md` and `~/dharma_swarm_live/CLAUDE.md` headers, rendered from `docs/governance/ACTIVE_TRACK.yaml`). All 3 active tracks serve substrate-nativeness.

---

## 4. The three horizons — do they feed each other? (axis e synthesis)

**Currently: no. Three isolated metabolic organs.**

1. **Scrappy → Disciplined: no flow.** cashclaw's evolution DB tracks PR fitness; capital_lab's honest-evidence gate scores strategy returns. Nothing maps bounty-loop outcomes into DSR-style evidence, and no shared ledger exists. They don't even share a worktree branch lineage.
2. **Disciplined → Strategic: blocked on operator decisions, by design.** capital_lab's ladder (fixture → external paper broker → data → operator lease → capital) requires: funded provider keys (#1 risk per ROADMAP), market data, a paper broker account, and a merge decision (127 commits off main with no PR). All four are operator moves, none in flight.
3. **Scrappy → Strategic: one thin thread.** The hermes-scheduled loop produces external PRs that build the AmitabhainArunachala contribution graph (openpilot PR included), which is reputation capital for grants/fellowships (`~/cashclaw/README.md` Active Bets 2–4: Anthropic Fellows, Manifund/LTFF, Mercor/Surge — all listed, none with code or receipts: **ASPIRATION**).
4. **Strategic → Scrappy: doctrine flows down correctly.** The hydra's lease architecture is a faithful implementation of the One Law and the narration-outruns-build feedback (its objective_audit literally distinguishes "running_or_incomplete" from "complete" and requires `operator_revenue_lease_not_granted` to PASS, lines 1273–1279 — the audit *passes* by proving it did NOT act externally). Governance discipline is the one place the long-term vision demonstrably shaped near-term code.

**What "the system funds itself" means today, honestly:** the system *spends* (API budget caps appear throughout: hydra `cost_cap_usd: 25`/cycle, chetana $3/day) and *earns nothing yet*. The funding loop is open at exactly one point on each horizon: (H1) no bounty PR has merged — and the chosen targets (claude-builders-bounty, SecureBananaLabs, a playground repo) have unproven payout behavior; (H2) no capital, no data, no broker; (H3) no active track owns revenue.

### Smallest closing moves implied by the evidence (not recommendations, observations of the open edges)

- `GITHUB_TOKEN` into the cron env kills 233/256 scout-cycle failures (one env var).
- Fix `~/.cashclaw/claims.json` (leading comma) and the empty-PK evolution.db row.
- The `--push-token` dead argument either gets enforcement or removal — currently it documents a gate that isn't mechanically there.
- A merged $50 xevrion PR would be the first closed revenue loop in system history; the three xevrion PRs (June 9–10) are the nearest-term candidates.
- Declaring a `revenue-external-humans-served` track (the portfolio model explicitly allows 1–10 co-equal tracks) would bring the economic engine inside its own governance for the first time.

---

## 5. Grade table (consolidated)

| Component | Location | Grade |
|---|---|---|
| Multi-platform bounty scanner v2 | `~/cashclaw/cashclaw_multi_platform_scan.py` | **RUNS** (fresh output 06-10) |
| Claim-and-do pipeline | `~/dharma_swarm_cashclaw/scripts/revenue/cashclaw_claim_and_do.py` | **RUNS** (6 live PRs prove the path) |
| `--push-token` enforcement | same, line 380 | **ASPIRATION** (parsed, never checked; gate is positional) |
| Claim tracker / status poll | `cashclaw_claim_tracker.py` + hermes job | **RUNS** (DB rows refreshed 06-10) |
| cashclaw Darwin variants | `cashclaw_evolution_runner.py` / `breed` | **RUNS** (17 scan + 1 breed completions) |
| Revenue Hydra governed loop | `cashclaw_revenue_hydra.py` (branch only) | **RUNS dry-run / WIRED-BUT-DORMANT external arm** (lease never granted; 21/21 tests) |
| Hydra→main dock | imports `cashclaw_autopilot`, `live_intake` | **branch-only — none of it on main** |
| Revenue scout daemon (main) | `dharma_swarm/revenue/scout_daemon.py` + `cron_runner.py:876` | **RUNS-ON-EMPTY** (256 cycles, 233 token failures) |
| Intel ingestor (main) | `dharma_swarm/revenue/intelligence.py` | **RUNS, low-signal** |
| Wedge pipeline / campaign-xray | main + portfolio | **HELD** (gauntlet 28/100, $0) |
| capital_lab contracts/governor/membrane/DSR | `~/dharma_capital_lab/dharma_swarm/capital_lab/` | **RUNS as fixture library** (33/33 tests, this session) |
| capital_lab alpha evidence (Goal A) | `alpha_evidence.py` | **WIRED-BUT-DORMANT** (41/100, clean=false, 25 blockers) |
| capital_lab live trading | — | **ASPIRATION** (LIVE_READINESS=0 by design; not on main; no data/broker/capital) |
| Telos-gate / witness docking of any economic component | — | **ASPIRATION** (clean negative: zero imports) |
| Grants / Mercor / expert-network bets | `~/cashclaw/README.md` | **ASPIRATION** (listed, no artifacts) |
| Lifetime revenue | all horizons | **$0, live-verified 2026-06-10** |
