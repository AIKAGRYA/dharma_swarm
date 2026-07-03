# Handoff — Highest-ROI Campaigns (2026-07-03)

**Role:** cold-start handoff for a fresh build instance. Everything needed to pick up the highest-return work **that requires no operator infrastructure** and drive it, without re-deriving this session's context.
**Source:** session `claude/repo-audit-fable5-roadmap-l5oosz` — full-repo fresh-eyes audit (3 parallel deep sweeps), Phase 1 spine-adoption endgame shipped, Phase 1B live organs shipped, VPS provisioning kit shipped. Companion docs: `docs/plans/FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md` (the strategy), `docs/architecture/SPINE_ADOPTION_NARRATIVE.md` (what "live" means).
**Rule:** if this file disagrees with `make onboard`, `ACTIVE_TRACK.yaml`, a receipt, or the code, trust those. This is a pointer + priority document, not authority.

---

## 0. First 10 minutes (do this before anything)

```bash
make onboard                                             # current reality
python3 scripts/governance/trust_gate_status.py          # the C1..C5 scoreboard (the real KPIs)
python3 scripts/governance/check_track_status.py 2>&1 | grep -E "SHIPPABLE|blocker|WARN"
git log --oneline origin/main..HEAD                      # what this branch added vs main
```

Read: `foundations/THE_ORGANISM.md`, `docs/vision_maps/NORTH_STAR.md` §2/§8/§11, `CLAUDE.md` Transcendence Principle. Then this file.

---

## 1. Where things stand (the one-screen truth)

**Shipped this session (on this branch, pushed):**
- `runtime-truth-spine-adoption-2026-06` — **CLOSED/SHIPPED.** Bypass allowlist drained to zero; every production dispatch flows through `a2a/spine_adapter.submit_task_via_spine` (one EvidenceReceipt each), held at zero by ratchet + uplift guard. GATE 1 was operator-witnessed. This weeks-old track is done.
- Phase 1B organs: cockpit **Spine Pulse panel**, Go sense-organ **toolchain hardening** (Loop 5b verified live locally), **dispatch-dropoff quarantine tool**.
- **VPS provisioning kit** (`scripts/ops/vps_cloud_init.yaml`, litestream sidecar, RUNBOOK §3e phone flow).

**The live-loops reality — READ THIS so you don't chase a non-problem:**
- 0 of 13 cybernetic loops are CLOSED_LIVE (11 HARNESS_PROVEN, 2 BLOCKED on One Wire quorum).
- **This is no longer a code problem.** Every code fix that was blocking live closure shipped. The only remaining reason is that **nothing runs persistently** — the daemon needs an always-on host (VPS), and that provisioning is stuck on the operator's DigitalOcean mobile-access friction (droplet `178.128.87.170` / id 551239034, name likely `ubuntu-s-2vcpu-4gb-120gb-intel-sgp1-01`). **Do not spend a coding session trying to make loops CLOSED_LIVE — you cannot, without the host.** When the host exists, RUNBOOK §3e has the exact sequence.
- The 2 BLOCKED loops (12/13) are gated on the One Wire external-receipt quorum (N=3/5, M=1/3) — doctrine holding, and *the revenue campaign below is what fills that quorum.*

**Trust gate today (the real KPIs, from `trust_gate_status.py`):**
`C1 0.79 AMBER · C2 0.05 RED · C3 0.30 RED · C4 0.34 RED · C5 0.20 RED`. Two of three spine objectives — `revenue-external-humans-served` and `research-depth` — have **zero active track** (`ACTIVE_TRACK.yaml`; BR-022).

---

## 2. The ROI ranking (work that needs NO operator infra)

Everything here is fully executable in a coding session — hermetic, no VPS, no credentials the operator must provision (except where a decision is flagged). Ranked by return.

### #1 — Arena Truth (C2). The single highest-leverage work in the repo.
**Why #1:** C2 = 0.05 is the lowest real number on the board, and it is the *thesis*. The last measured swarm lift is **-0.1** (`reports/anatomy_altitude_2026-06-10/lane_E_organism_vision.md`) — the swarm currently **loses to its best single agent**. Every downstream ambition (capability claims, the revenue wedge's credibility, the grant/YC narrative, DGM-style self-improvement) sits on top of whether the swarm actually beats its best seat. Nothing else de-risks the whole venture as much per token.
**Track:** `orchestration-arena-v1-2026-06` (ACTIVE). Its open blocker IS this: *"best-single-model controls + budget-parity proof on every arena run before any capability claim."*
**Fully hermetic:** frozen taskpack, deterministic scorer, MAP-Elites archive, DPI — no external creds, no live host.
**⚠ Before you start:** local arena work is **ahead of origin/main** (operator has an un-pushed local checkout with more evolved arena/genome code). Check `git branch -a | grep -iE "arena|forge|coordination"` and `git log origin/main -- dharma_swarm/coordination/` first. If the local branches never arrive, build against main's `dharma_swarm/coordination/**` + `dharma_swarm/council/**` — the controls are additive either way. There is a state-dossier prompt for the operator's local agent at the end of the roadmap doc; if that dossier lands, read it first.
**First PR (concrete):**
1. Add a **best-single-model control arm** to every arena run: the same taskpack scored by the single strongest seat, at **budget parity** (equal token/call budget to the swarm — instrument and assert it).
2. Add **significance gating**: report lift with a confidence interval, not a point estimate; no "win" claim below significance.
3. Wire the scorecard + DPI receipts into a **read-only governance report surface** (the track's non-blocker item 1 — do it here so the number is visible).
4. **If lift stays ≤ 0, that is the finding** — then run the diagnosis the Transcendence Principle prescribes (`CLAUDE.md`): measure the Krogh-Vedelsby diversity term and error-correlation across seats, and attack the weakest of the three conditions (candidate order: quality aggregation in orchestrator fan-in; correlated errors from same-family seats; routing that ignores specialty).
**Doctrine (do not violate):** zero trained weights in v1; only `CANONICAL_ORIGIN_MAIN` checkouts feed fitness (never dirty/local state); no capability claim without the parity control; market P&L never a per-iteration selection signal.
**Done =** every arena run carries a parity-controlled best-single-model arm; C2's evidence line cites a *fresh* measured lift (any sign) replacing the 2026-06-10 −0.1; a written diagnosis memo if lift ≤ 0.

### #2 — Revenue Wedge (C3). Opens the doctrine-mandated next objective.
**Why #2:** `revenue-external-humans-served` has no active track and `organism-rewire` item 8 explicitly says the next track opened MUST serve it. Recorded revenue: $0 against NORTH_STAR §11's 90-day "funds itself totally." And it's the wedge where **the repo's existing over-investment IS the product** — converting cost into inventory. It also feeds the One Wire quorum that unblocks Loops 12/13.
**The wedge:** `docs/offers/agentic-code-governance-sprint.md` — a $5K–$25K, 3–7 day paid engagement selling exactly what this repo over-built for itself: slop-scans (71 hygiene patterns), provenance mapping, CI ratchets, agent-governance review signals (AI-A1…E1). Shorter path than Darshan/trading/courses.
**Open a NEW track:** `revenue-wedge-governance-sprint-2026-07`, `serves: revenue-external-humans-served` (BR-022 packet A). Add to `ACTIVE_TRACK.yaml` under `active_tracks:` then `python3 scripts/governance/render_active_track_includes.py`. WIP is fine (spine-adoption closed, so you're at 4).
**First PR (concrete):**
1. Extract the hygiene/ratchet/provenance tooling into a **target-repo-agnostic audit kit** — point it at *any* repo, produce the ranked slop/provenance report the offer promises. (Sources: `scripts/governance/hygiene/scan.py`, the ratchet counters, `docs/governance/hygiene/**`.)
2. A **deliverable generator** — the report an engineering lead pays for, rendered from scan receipts.
3. Run it **end-to-end against a non-dharma fixture repo in CI** (that's the acceptance test; no real client needed to prove the machine works).
4. Engagement receipts flow through the existing `RevenueSpine` (`dharma_swarm/revenue/`, `/api/revenue`) — human-approver-gated outreach preserved (`revenue.py:80`); paid work enters fitness ONLY via One Wire (`EXTERNAL_GRADIENT_PORTFOLIO_SPEC.md`).
5. Create the missing gate-evidence surface `reports/revenue_wedge/first_cash_receipt_status.md`, honest at $0 until it isn't.
**Operator-gated (flag, don't block on):** wedge ratification, pricing, any real outreach — code acceptance is "nothing on our side blocks a paid engagement," not actual cash.
**Done =** audit kit runs against a fixture repo in CI; deliverable renders from receipts; the gate-evidence file exists.

### #3 — R_V P0 Bridge (research-depth). Opens the other unowned objective; reopens the lane that died with COLM.
**Why #3:** NORTH_STAR §2 stakes the "measurable awareness" claim on a falsifiable program, and the P0 gate — R_V and L4 compression on the *same* forward passes — **has never been co-tested**, yet the code already exists (`dharma_swarm/l4_rv_correlator.py`, self-described "THE MISSING EXPERIMENT", + `rv.py`/`system_rv.py`/`swarm_rv.py`/`bridge.py`). The COLM calendar death killed the *paper*, not the program (see the roadmap doc's research inventory).
**CPU-startable:** Rung 1 (lexical-confound control) and wiring the receipted eval loop don't need GPU; only the full transformer sweep does (rent-by-hour later, operator-gated).
**Open a NEW track:** `rv-bridge-p0-2026-07`, `serves: research-depth`. Same admission steps as #2.
**First PR (concrete):** run Rung 1 + the P0 co-test from `docs/research/self_reference_attractor/RESEARCH_PROGRAM.md`; wire it as a **receipted eval loop** (frozen prompts, deterministic pipeline, receipts to an owned report surface) so it survives sessions instead of dying with a deadline; purge stale COLM refs (`benchmarks/README.md:455`, `docs/telos-engine/`, `research/economic_value_tracking/README.md:325`, `dharma_swarm/living_map.py:411`); deadlines live in `~/.dharma/research_deadlines.json`, NEVER hardcoded (that was the bug).
**Done =** one receipted P0 run with the correlation reported either way; Rung 1 result in `foundations/EMPIRICAL_CLAIMS_REGISTRY.md`; zero stale-COLM refs.

### Cross-cutting (ride existing tracks; pick up when a primary stalls)
- **C-1 Governance rent ledger** (BR-022 packet B): read-only per-gate prevented-drift vs coordination-tax; wire the Krogh-Vedelsby term (now in `archive.py`) into gate-addition review. HARD RULE: do NOT add new governance machinery to close this.
- **C-2 BR-014** (`telos_gates.py:512`): the `BHED_GNAN` gate hard-passes — the most-central Gnani gate is inert. Fix routes through `GateRegistry.propose()` (direct edits governance-forbidden). Natural pairing with #1's aggregation work.
- **C-3 C5 memory first-token** (0.20 RED): 3 sections render before the memory kernel in `context_compiler.py`; making it first-token moves a trust-gate KPI directly.
- **C-4 God-object diet, opportunistic only:** worst offenders `thinkodynamic_director.py` (5255), `telos_substrate.py` (4512), `runtime_state.py` (4003). Carve ONLY when a campaign already owns the surface — no standalone refactor track (that repeats the inward-spiral failure mode).

---

## 3. Recommended first move

**Start #1 (Arena Truth).** It has an owned ACTIVE track, needs no new-track admission, is fully hermetic, and moves the number that gates everything else. Sequence: check for the operator's local arena branches → if absent, build the best-single-model + budget-parity control against main's `coordination/` → run it → report the honest lift → if ≤ 0, write the diagnosis. That single result changes every other conversation in the portfolio.

If you want breadth instead of depth, open the **Revenue Wedge (#2)** track in parallel — it's surface-disjoint from arena and serves the unowned objective the doctrine says is next.

---

## 4. Operator decision queue (do not silently block on these)

1. **VPS host** (unblocks all live-loop closure): DigitalOcean droplet `178.128.87.170` — operator hit mobile-access friction (root-password reset email pending). RUNBOOK §3e Path A/B when reachable. NOT a coding task.
2. **Arena:** whether to push the local arena checkout to origin so a remote instance can build on the most-evolved code (state-dossier prompt at end of roadmap doc).
3. **Revenue wedge:** ratify the offer, pricing, outreach policy.
4. **Research:** venue choice + GPU access for the full R_V sweep (Rung 1 doesn't need it).
5. **Mike:** ratify D1–D4 + provision the ANTHROPIC repo secret for the cloud reviewer (small, additive, unblocks human-PR auto-merge).
6. **TTL:** re-verify or retire any track past its 21-day verify TTL.

---

## 5. Anti-goals (inherited — do not violate to "make progress")

- No capability claim from the arena without best-single-model + budget-parity controls.
- No weakening/bypassing any telos gate, ratchet, or the One Wire quorum to close a loop or wedge.
- No new governance mechanism to fix governance (BR-022's own warning).
- No trained weights in Arena v1; no market P&L as per-iteration selection signal.
- No dirty/local/candidate state feeding arena fitness — only CANONICAL_ORIGIN_MAIN.
- No standalone big-bang god-object refactor; carve only inside owned campaign surfaces.
- No new truth stores, receipt systems, or parallel naming schemes; extend existing owners.
- No committing credentials, ever.

---

## Appendix — evidence pointers (so you can verify, not trust)

- Strategy: `docs/plans/FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md`
- Spine "live" definition + GATE 1: `docs/architecture/SPINE_ADOPTION_NARRATIVE.md`
- Loop status: `reports/loop_closure/cybernetics_codex/latest_audit.md`
- Trust gate evidence: `reports/governance/trust_gate_status.json`
- Broken register (7 open, incl. BR-003 self-evolution, BR-014 inert gate, BR-022 outward-edge): `docs/state/BROKEN_REGISTER.md`
- Arena doctrine: track `orchestration-arena-v1-2026-06` in `ACTIVE_TRACK.yaml`; `docs/architecture/EXTERNAL_GRADIENT_PORTFOLIO_SPEC.md`
- Revenue assets: `docs/offers/agentic-code-governance-sprint.md`, `dharma_swarm/revenue/`, `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`
- R_V assets: `docs/research/self_reference_attractor/RESEARCH_PROGRAM.md`, `dharma_swarm/l4_rv_correlator.py`, `dharma_swarm/rv.py`
- VPS when the host exists: `docs/ops/RUNBOOK.md` §3e, `scripts/ops/vps_cloud_init.yaml`
