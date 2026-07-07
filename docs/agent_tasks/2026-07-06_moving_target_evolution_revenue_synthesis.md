# Moving-Target Evolution × Revenue — Design Council Synthesis

Date: 2026-07-06 (JST). Council: 9 agents (1 grounding + 6 ideation families + adversarial rank + defense/salvage), 773,401 tokens, 0 errors. Workflow run wf_70de267f-18b. READ-ONLY review; every load-bearing claim carries file:line or URL in the run record.

Operator reframe under test: apply the SAME evolution principle/tools that make DGM work on SWE-bench to an EXTERNAL, MOVING, real-world target whose un-gameable acceptance RECEIPT is SIMULTANEOUSLY the fitness signal AND the revenue event (one loop, no separate "wire findings back into DGM" pipe — that pipe was Agent Boundary CI's fatal flaw).

---

## OPERATOR CORRECTION (2026-07-06, applied post-synthesis — supersedes framing below where they conflict)

1. **"Zero certified promotions ever" is a BUILD-STATE, not a verdict.** The RSI lab is still being BUILT; the real-grade pipe has been run only once or twice (JOIN smoke). Evolution has NOT been given a fair trial and failed — it is UNTESTED, not disproven. Do not read "never demonstrated lift" as skepticism that it CAN; that connotation is withdrawn. The moat is untested because the instrument isn't finished, full stop.

2. **The "one loop where the market receipt IS the fitness" framing MUDDIES the lab and is rejected.** Making the noisy, reputation-gated, un-samplable live-market grade into the lab's fitness function is the "confuse lab equipment with the experiment" failure (CLAUDE.md). The correct architecture is CLEAN SEPARATION: the RSI lab stays a pure, controlled, gated science instrument (SWE-bench + controls + one-door promotion), finishes on its own timeline, and its only output is a CERTIFIED CHAMPION scaffold. The live-bounty market is a strictly DOWNSTREAM deployment organ that receives an already-certified champion and deploys it outward — market noise NEVER flows back into the lab's fitness. The salvage's own "evolve on the internal dense gradient, deploy the champion on the market" already collapses the 'one loop' back into this clean separation.

3. **Ordering: LAB FIRST.** The live work is the chassis build (`~/.dharma/forge_v1/CHASSIS_HANDOFF_PROMPT_2026-07-06.md`). The live-bounty revenue idea is a downstream, LATER, SEPARATE arc — it does not start until the lab produces a champion worth deploying, and it must not be fused into the half-built lab now. This document is a MAP of the eventual monetization exit, not a mandate to act. The read-only bounty recon in §4 is optional market-intel, NOT the next move; it is parked.

---

---

## 0. The orchestrator's earlier error — resolved: `both_partly`

- Operator was RIGHT: a real, un-gameable SWE-bench Docker grade EXISTS and is runnable. `~/ds_forge_v1_scoreboard/dharma_swarm/forge_v1/run_real.py` + `swebench_real.py::verify_prediction` over the official harness; a real MODEL-generated patch (sympy__sympy-22914, forge_batch arm, not gold) passed hidden FAIL_TO_PASS under Docker; gold→resolved / empty→false discrimination proven; 742 run dirs under `~/.dharma/forge_v1/swebench_runs`.
- Orchestrator was PARTLY right: the PRODUCTION self-improvement loop in `main` still runs on self-report fitness (`dharma_swarm/autoresearch_loop.py:329-364` = 0.5·own-pytest + 0.3·AST-elegance + 0.2·size). The real-grade DGM wiring exists ONLY in the `ds_forge_spine_v0` side worktree (`feat/rsi-lab`), shadow-only, `promote_eligible:false`, never promoted to main.
- The fact NEITHER of us flagged, and the crux of everything below: **ZERO certified promotions have ever occurred, even on the easy frozen SWE-bench.** The `confirm` split returns 0 explore instances (`forge_fitness.py:89`); every real-grade run closed inconclusive_low_power. The evolution edge has never once demonstrated lift. "The pipe is clean, not that evolution happened" — `RSI_LAB_PHASE2_PLAN.md:5`.

## 1. The answer to the reframe: YES, such a target exists — and it demotes Boundary CI

**Winner (score 78/100, passes all 6 hard gates): LIVE SOFTWARE REPAIR = "SWE-bench unfrozen."** Point the existing Forge DGM machinery at the LIVE PAID company-posted bounty market (Algora-class outcome-buyers, not volunteer-charity issues). The **merged-AND-PAID PR** is a single artifact from which fitness is inseparable from revenue — you cannot obtain the grade except by submitting and being paid.

Why it wins on exactly the axes the reframe privileges:
- **Purest one-loop of all six.** Payout receipt = fitness label AND revenue event, atomically. (Agent-eval fails here: its fitness — "does the frontier fail?" — is computable by calling APIs yourself with no buyer, so signal and revenue are separable pipes.)
- **Most machinery reused, least new build.** The dense un-gameable gradient is the SWE-bench Docker harness ALREADY WIRED in the spine worktree (`forge_fitness.grade_genome` with injectable `runner_fn`, ArmSpec scaffold genome, `verify_promotion` one-door). New surface = a payout-receipt grader adapter + bounty/honeypot triage policy + disclosed-identity harness.
- **Only family whose first dollar needs no B2B sales lease.** A stranger merges your public PR and their platform pays — the single most direct assault on the verified #1 bottleneck (0/113 outreach approved, gauntlet HOLD since 2026-05-27, 1 star, "publish-and-measure last mile").

**Agent Boundary CI: DEMOTED (fold_into_another, 34/100).** Under the reframe it fails gate_one_loop (its clean dense receipt — an OSS security-PR merge — is FREE; its revenue tier — a paid boundary bounty — is sparse AND payer=grader = disputable, so fitness and revenue DIVERGE, reinstating the exact two-pipe defect relocated) and is borderline-forbidden (one step from generic red-team, an explicit KILL signal in its own source packet). Durable value = an INTERNAL immune-system verifier, never a standalone product.

## 2. The brutal truth the winner survives only by facing

Strongest attack (VERIFIED, survives-partially): the winner's "why us not incumbent" rests entirely on a DGM evolution edge that is BOTH unproven AND, on this target, un-runnable.
- **Un-runnable on the live market:** reputation is a scarce, single-identity, ban-forever asset (curl killed its bounty program specifically to stop AI-slop; Ghostty bans-forever). You cannot run the thousands of cheap A/B live attempts DGM needs.
- **Unproven anywhere:** zero certified promotions ever (§0).

Salvage DEFUSES the un-runnable half with real code, does NOT defuse the unproven half:
- Defused: evolve on the ALREADY-BUILT free dense internal gradient (`pr_suite_harvester.py` + `pr_suite_grader.py` — fresh post-cutoff PRs held out by knowledge cutoff, real clone+pytest FAIL_TO_PASS, free and moving), then DEPLOY only the champion on the live paid market. "Evolve on density, deploy on the moving target."
- NOT defused: making evolution runnable ≠ making it lift. Moat downgraded from **asset to hypothesis-to-test**.

Therefore the one-loop test MUST become a **TWO-metric test**:
- (a) one disclosed-identity PR to one low-competition company-posted bounty **MERGES-AND-PAYS** — the payout receipt, NOT merge alone (honeypots merge without paying); AND
- (b) the **evolved champion out-merges a plain-frontier+triage baseline** on the free internal fresh-PR gradient — because without (b), the winner is a commodity coding agent the market already zero-merges 27/30, and "surpass incumbents" stays an untested hypothesis.

Honest dissent to hold: the winner may be a superb fitness engine but a **negative-margin product** (best-documented autonomous-bounty case ~$500/30d and declining; first loop may be ~$50 revenue vs ~$200 x86-cloud grading spend + a burned reputation slot; Devin/Factory at $1.5B are pivoting to outcome pricing in this exact lane). If margin never goes positive, the operator's "sellable that surpasses incumbents" need may be better served by the strong_alt (ground-truth-answers, higher value-per-unit).

## 3. The blended organism (strictly stronger than the pure winner)

`live-swe-repair` is the single revenue-bearing OUTER loop. Every rejected family becomes an internal organ that plugs one of the winner's named weaknesses — 4 of 5 with VERIFIED substrate:

| Organ | From | Role | Substrate |
|---|---|---|---|
| HEART (dense gradient) | ground-truth-answers | evolve champion on free fresh-PR density, not the scarce live market | `pr_suite_harvester.py` + `pr_suite_grader.py` (built) |
| IMMUNE SYSTEM | boundary-ci | mandatory pre-submission verifier; no secret-exfil / boundary-violating patch ever leaves under the scarce identity | FAB-01..05 + `execution_lease.py` authority check |
| INTEGRITY CLAMP | market-pnl | `spend`/`external_contact` structurally clamped; no payout moves without a 2nd explicit lease | `broker_paper_membrane.py` AuthorityFence pattern (LIVE_AUTHORITY=False + deny-scan) |
| REPUTATION NOTARY + premium | security-bounty | huntr CVE attestation bootstraps disclosed-identity credibility; CVE-fix PRs = higher-$/unit sub-type | huntr channel |
| TRIAGE SENSOR | agent-eval | frontier-differential probe (free, no buyer) routes scaffold only to bounties where it actually lifts merge-rate | frontier-failure probe |

SEQUENCE (do NOT build all five before the first paid receipt): organ 2 (immune system) as a mandatory safety pre-req + organ 1's already-built harvester as the gradient FIRST; organs 3/4/5 are hardening only after the loop closes AND evolution-lift shows a positive number.

## 4. The single operator decision — and the free recon that precedes it

- **Decision (later):** grant ONE bounded single-PR `external_contact` lease (forbidden-by-default in `execution_lease.py`) for the two-metric loop test — materially lighter than the never-granted B2B sales lease every other path dies on — while the AuthorityFence keeps `spend` structurally clamped so no payout moves without a second lease.
- **First (now, no lease, no track slot, mutates nothing):** read-only bounty recon. Enumerate currently-live COMPANY-POSTED bounties (outcome-buyers) on Algora/GitHub; filter to (a) <~3 existing claim attempts, (b) a difficulty band the current SWE-bench-evolved scaffold already clears, (c) a maintainer/platform history of actually PAYING on merge (honeypot filter). Output ≤5 candidate first-loop targets + the exact reward-payout webhook fields a grader adapter must read. This sizes the winnable niche and the true payout-not-merge receipt shape so the operator decides the lease against a sized niche, not a hope.

## 5. What this does NOT change

- WIP 11/11: a new BUILD track needs operator lifecycle action; the recon needs none.
- The name still drops "Forge" (collision with `semobj.dharma_forge_proving_ground`); the external product is buyer-legible ("live PR-bounty repair"), the internal lane name settles at name-drift preflight.
- Production self-improvement STILL points at self-report fitness in main; "reuse the machinery" means reuse the SIDE-WORKTREE real-grade seam, which is itself shadow-only and unpromoted.
- No live capital, no forbidden shapes, no outreach performed. The recon is read-only.

## Provenance / self-criticism

- The two structural killers (zero promotions ever; live-market un-samplable) are VERIFIED, not inferred — they are the load-bearing findings, and they mean the honest headline is "a real one-loop candidate whose moat is an untested hypothesis," not "a proven wedge."
- External economics (bounty payouts, incumbent funding, OSS backlash) are web-sourced 2026-07-06; treat as directional.
- The blend's un-proven-evolution-lift half is not defused by any organ — only metric (b) of the two-metric test can defuse it, and it has never been run.
