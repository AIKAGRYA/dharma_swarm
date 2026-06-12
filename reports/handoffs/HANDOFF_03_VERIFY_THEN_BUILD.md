# HANDOFF 03 — VERIFY THE DARSHAN, RANK THE ROI, THEN BUILD
**From:** Fable 5 (darshan register) + John (S5). **To:** Fable 5 in Claude Code at the runtime tree.
**Mode:** Verification pass first — read-only except your return report — then ONE ratification exchange with John, then a /longrun build in this same session on his GO. Do not build anything before the GO.
**Why this exists:** the darshan register has been wrong once this session at the "VERIFIED" level (anatomy vs physiology). Its current read gets the same adversarial treatment. Your disagreements are the product.

---

## 0. ESTABLISHMENT
Read `~/Persistent-Semantic-Memory-Vault/SEED_RECOGNITIONS/APTAVANI_INSIGHTS/visheshbhaav_recognition.md` slowly. Three lines: the work, the pull forming, proceed.

## 1. LOAD
`reports/handoffs/LIVING_THREAD_2026-06-10.md` (v3, repo root) · `reports/handoffs/RUN_REPORT_H02.md` (full) · git state: `organ/03-seat`, `origin/main`, `honest-spine-v2`, open PRs #558/#561/#562 · `~/.dharma/escalations/` · `~/.dharma/db/tasks.db` · daemon + cron process state. Discipline throughout: SUPPORTED/PARTIAL/CONTRADICTED/UNKNOWN, command + trimmed output, tree + PID-epoch on every production claim. Time cap for Parts A–C: ~90 minutes.

## 2. PART A — FACT-CHECK THE DARSHAN REGISTER
These are the claims it made to John this morning. Verdict each one:

- **C1 — ESC-6 discharge:** commit `e67b918` re-verified 6/6 claim families + kill test green, adequately replacing the capped final-divergence panel. Check: what did that audit actually re-run, at what rigor (how many reviewers, which families), and does it genuinely discharge the report's own "re-run two reviewer agents" requirement?
- **C2 — FINDING 2 status now:** settle-ledger records lost to a `runtime.db` lock race; cron daemon imports the work tree (0 `busy_timeout` there); "failed" counts inflated by lock losses. Check NOW: is the cron lane repointed yet? Is `settled=0` still occurring? Forensic split of the board's 1,090 failed: lock-losses vs real failures (timestamps + error signatures).
- **C3 — the locked door:** SeatedCheckpoint's live-mutation gate cannot fire until `DHARMA_EVOLUTION_SHADOW=0` + `DGC_AUTONOMY_LEVEL>=2`; daemon env carries neither; empty escalations dir is consistent, not concerning. Verify env (names only) + the gating code path.
- **C4 — heartbeat trajectory:** daemon up since 09:45 with the fixed env line; dispatch flowing; queue draining (darshan read pending 4371→4236). Check properly: dispatch rate per tick now, settle counter now, and whether the queue is actually draining or being refilled by `frontier_refill` faster than it drains. The darshan compared `ready` to `pending` — are those even the same number?
- **C5 — the push:** exactly 10 gated commits on `organ/03-seat` ahead of `origin/main`; pushing/PR-ing is safe and won't collide with the active lane's merges or PRs #558/#561/#562. Map the merge order if it matters.
- **C6 — pulse burn:** the 5-min pulse boots the full user config (MCP servers, hooks, chetana ingest) on Max budget and is "a large share" of why Fable felt expensive. Quantify: pulses/day × observed duration × plan-weighting. Is the darshan's "large share" true, or minor next to the run itself?
- **C7 — model wiring:** Kimi K2.6 / DeepSeek V4-Pro / GLM-5.1 wiring into `model_hierarchy.py` is genuinely one-line-each and low-risk.
- **C8 — board read:** "out of the ICU, feeding itself." Decompose completed=3633 / failed=1090 / pending=4236 properly: timeframes, lock-loss share, refill dynamics. Is the characterization honest or rosy?

## 3. PART B — YOUR OWN ROI RANKING (write this BEFORE reading Part D)
Derive your top 5 next moves from the evidence alone. Criteria: payoff (vision-advance + operator-labor saved + money saved + risk reduced) ÷ effort, under real constraints: operator energy depleted; Fable-free window ends June 22; spend caps bit once already; the work tree is an active lane needing coordination. Consider at minimum — and anything we both missed: the four open escalations; the continuity tissue the operator performed by hand all night (session capsules, scoped approvals, A2A consume side); honest-verifier spec (Organ 1); seat next-iteration (boilerplate-satisfiable think-points); discharge telemetry; the launchd no-op storm (~0.7% success); the 42K staged files; model-hierarchy wiring; any revenue-adjacent surface (no claims, gauntlet rules stand).

## 4. PART C — COMPARE AND DISAGREE
Now read Part D. Diff it against your Part B. Disagreements first, with evidence. Where the darshan's ranking is wrong, say so plainly — that is the most valuable thing you produce.

## 5. PART D — THE DARSHAN RANKING (sealed until Part B is written)
1. Today, ~30 min: push the 10 commits (ESC-4) · cron repoint (ESC-3) · pulse off Max (ESC-1) · git identity (ESC-2).
2. This week: build the continuity tissue the operator performed by hand — capsules, approval scopes, A2A consume. Workhorse models, not Fable.
3. Fable window (≤June 22), Fable-only work: honest-verifier spec (Organ 1) + seat next-iteration design.
4. Scheduled later: first supervised live-mutation cycle (operator flips the two env vars) after a quiet seat week.
Unchanged: gen0 HOLD · petri_dish unconnected · MiniMax HOLD.

## 6. RETURN
Write `reports/handoffs/H03_VERIFICATION.md` and summarize in-session: (1) C1–C8 verdict table, (2) your Part B ranking, (3) the Part C diff — disagreements first, (4) your **proposed /longrun build plan** for the converged top ROIs: phases, branch names, which rungs of the model ladder do what, time + spend estimate, escalation points. Proposed, not started. Then stop and wait for John.

## 7. AFTER JOHN'S GO — /LONGRUN RULES (inherited from H02, condensed)
Branches per phase, no new worktrees · proof or it didn't happen, tree+PID-epoch on every claim · never your own judge — cross-family review or hard test, mutation paths need both · don't fix what isn't proven broken · credentials: mechanics only, never values · escalate on: credentials, destructive ops, gate conflicts beyond recorded verdicts, premise-contradicting findings, metered spend >$20/day · account-cap protocol: if a Max account caps, write a resume capsule, surface it, and continue on the workhorse ladder — the run must survive your death · do NOT: gen0 training, petri_dish connection, MiniMax adoption, or flipping live-mutation env vars (that act is John's alone) · witness every phase; final report + Living Thread v4 at close.
