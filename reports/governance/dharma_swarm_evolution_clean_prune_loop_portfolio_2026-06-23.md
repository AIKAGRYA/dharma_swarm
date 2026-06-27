# Dharma Swarm evolution / clean / prune loop portfolio

Date: 2026-06-23 23:21 JST
Operator request: scan the dharma_swarm repo + surrounding ecosystem and research the best loops to put in place so the organism can evolve, clean itself, and prune repo/ecosystem sprawl.

This is an evidence-backed operating design, not a completion receipt. It modifies no code. It names existing owners first and proposes only loops that can bind to receipts.

## 0. Current ground truth snapshot

Primary repo: `/Users/dhyana/dharma_swarm`
Branch: `telos-ai-seed-v0-from-sandbox`
HEAD shown by `make onboard`: `cd610be3cc`
Repo state from `make onboard`: ahead 9, behind 219 vs origin/main; dirty files 212.
Local `git status` during this scan showed 200+ dirty files and many untracked surfaces.

Active portfolio from `make onboard`:
- 11 active tracks, WIP at max.
- 7 tracks reported shippable but require operator lifecycle review.
- Unshipped blockers:
  - `loop-closure-2026-06`: missing `reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md` and `reports/loop_closure/RETROSPECTIVE.md`.
  - `cybernetics-codex-stewardship-2026-06`: missing admission + runtime heartbeat receipts.
  - `telos-ai-morning-refinery-2026-06`: missing first external acted receipt.
  - `helm-worldclass-terminal-2026-06`: missing golden captures, ratchet, live tmux receipt, closeout.

Live ops from `make onboard`:
- `live_process_census.json` is stale by ~83.5h.
- 17 surfaces: 12 live, 2 blocked, 2 stale, 1 stopped.
- Proof gaps include daemon runtime provider model, holon L4 proof, stale NATS hot contact ACK, stale remote AGNI.

PR state from ecosystem scan:
- 9 open PRs in `AmitabhainArunachala/dharma_swarm`.
- Several are draft governance/ops reports; several are dirty/blocked/failing pytest or Coherence Delta.
- GitHub token now works from `~/.hermes/.env`: login `AmitabhainArunachala`, scopes `gist, read:org, repo, workflow`.

Cron / ecosystem state:
- Repo `cron_jobs.json`: 26 jobs, 24 enabled.
- Live `.dharma` cron: 33 jobs, only 4 enabled and current.
- Hermes cron: 56 jobs, many enabled but mostly last-run around 2026-06-20; `github-pr-clearer-3x-daily` exists but had not successfully run from cron at scan time.
- This confirms scheduler split-brain: repo intent, `.dharma` cron, and Hermes cron disagree.

A2A / fleet state:
- `.dharma/a2a_bus/conjunction/latest` reported score 60/100, partial.
- Agents labeled active/operational are stale by thousands of minutes.
- 25 A2A tasks: 11 claimed, 7 completed, 2 expired, 5 pending; 11 claimed tasks lack terminal receipts.

Worktree state:
- 13 dharma_swarm worktrees/sibling checkouts.
- Several dirty, detached, behind, or divergent.
- Canonical-root ambiguity remains: `/Users/dhyana/dharma_swarm` is the map target, but other reports/worktrees still generate plausible truth surfaces.

## 1. Design law

Do not add another report loop unless it closes into action.

Every loop below must satisfy:

```text
observe -> classify waste -> choose one bounded action -> execute or route -> verify -> record receipt -> prevent recurrence
```

This is the KaizenOps contract. Anything that stops at “diagnosis” is theater unless it feeds a named action owner and a verifier.

## 2. Loop stack to put in place

### L0 — Canonical root and scheduler authority loop

Purpose: stop split-brain before optimizing anything else.

Existing owners:
- `make onboard`
- `docs/governance/CANONICAL_DOC_STACK.md`
- `docs/governance/ACTIVE_TRACK.yaml`
- `ACTIVE_SURFACE_MANIFEST.yaml`
- `~/.hermes/config/global_pulse_map.json`
- repo `cron_jobs.json`
- live `.dharma/cron/jobs.json`
- Hermes `~/.hermes/cron/jobs.json`

Loop:
1. Read one machine-readable canonical-root file.
2. Compare all schedulers and maps against it.
3. Emit a reconciliation report with three buckets: canonical, duplicate, retired.
4. Disable or mark non-canonical loops only after operator approval.
5. Write a receipt showing before/after scheduler counts.

Cadence: daily until green, then weekly.

Verifier:
- `make onboard`
- compare repo cron vs `.dharma` cron vs Hermes cron counts.
- check global pulse map repo root.

First action:
- Create `docs/ops/CANONICAL_RUNTIME_ROOT.yaml` or equivalent small owner file.
- Make global pulse, PR clearer, and cron reconciliation read it.

Why first: with 13 worktrees and three scheduler planes, evolution loops can improve the wrong body.

### L1 — Daily KaizenOps one-action metabolism loop

Purpose: convert observation into one verified improvement per cycle.

Existing owners:
- `docs/governance/KAIZENOPS.md`
- `docs/state/BROKEN_REGISTER.md`
- `docs/governance/ACTIVE_TRACK.yaml`
- `scripts/governance/check_track_status.py`
- `scripts/runtime/live_ops_census.py`
- hygiene scans

Loop:
1. Run/read `make onboard` receipt.
2. Read latest live ops census, PR queue snapshot, hygiene baseline, broken register.
3. Pick exactly one waste item by score:
   - blocks active track closure,
   - repeats across cycles,
   - causes PR/CI failure,
   - stale truth surface,
   - duplicate loop/scheduler writer.
4. Route one bounded work packet with owner, files, verifier, stop condition.
5. Verify and write `reports/kaizenops/YYYY-MM-DD_<slug>.md/json`.
6. If no action taken, explicitly mark `NO_ACTION` and why.

Cadence: daily, preferably after morning onboard refresh.

Verifier examples:
- `make docops-integrity`
- `make hygiene-check`
- `python3 scripts/governance/check_track_status.py`
- `python3 scripts/runtime/live_ops_census.py --write`
- PR queue before/after counts.

Acceptance metric:
- At least one waste item moved to verified/blocked-with-owner each cycle.
- Diagnosis-only cycles count as failures after 2 repeats.

### L2 — PR control-plane loop

Purpose: stop PR pileups, duplicate governance reports, stale drafts, and failing CI from accumulating.

Existing owners:
- `.github/workflows/stale-pr.yml`
- `.github/workflows/pr-dedupe.yml`
- `.github/workflows/bot-pr-limit.yml`
- `.github/workflows/pr-ci-health.yml`
- `scripts/governance/pr_ci_health.py`
- `scripts/runtime/pr_merge_control.py`
- `docs/ops/PR_REVIEW_CONTROL.md`
- Merge Master Mike surfaces
- Hermes PR clearer: `/Users/dhyana/.hermes/scripts/pr_clearer.py`

Loop:
1. Snapshot all open dharma_swarm PRs.
2. Bucket each PR:
   - mergeable green,
   - needs rebase/conflict repair,
   - failing required check,
   - duplicate/superseded,
   - draft stale/report-only,
   - human decision required.
3. Execute one safe action class per cycle:
   - rerun failed workflow for transient failures,
   - enable auto-merge on green PRs,
   - close/label only if governance rules explicitly allow,
   - comment with exact blocker when human decision is required.
4. Emit queue receipt: before/after open count, stale count, failed-check count, actions.

Cadence:
- 3x/day for PR clearer, constrained to `AmitabhainArunachala/dharma_swarm` first.
- Weekly stale/dedupe remains GitHub Actions.

Immediate patch needed:
- Add a repo filter to `/Users/dhyana/.hermes/scripts/pr_clearer.py` so it does not mutate all authored PRs across all repos by default.
- Make cron run report-only first, then action mode after one clean dry-run.

Acceptance metric:
- Open dharma_swarm PR count trends below 5.
- No duplicate ops-report PRs older than latest cycle unless explicitly retained.
- Failed required checks have a named owner within 24h.

### L3 — Runtime truth freshness loop

Purpose: make live-state claims fresh enough to use.

Existing owners:
- `scripts/runtime/live_ops_census.py`
- `scripts/runtime/runtime_truth_closeout.py`
- `scripts/runtime/runtime_truth_burn_in.py`
- `.github/workflows/runtime-truth.yml`
- `~/.dharma/ops/live_process_census.json`
- Runtime DB under `~/.dharma/state/runtime.db`

Loop:
1. Refresh live ops census.
2. Run closeout gate against runtime truth criteria.
3. If stale/blocked surfaces exist, route exactly one to KaizenOps.
4. Distinguish stale label from live label; stale operational surfaces cannot be called active.
5. Write freshness receipt.

Cadence: every 2h if daemon is live; daily if development-only.

Verifier:
- `python3 scripts/runtime/live_ops_census.py --write`
- `python3 scripts/runtime/runtime_truth_closeout.py`
- optional `runtime_truth_burn_in.py` for soak.

Acceptance metric:
- live ops census age < 6h.
- No “active” label if heartbeat age exceeds SLA.
- Runtime packets include mission_id/idempotency/artifact_refs where expected.

### L4 — Dead-code and module-diet pruning loop

Purpose: shrink repo surface safely without deleting dynamic/runtime entrypoints.

Existing owners:
- `docs/governance/hygiene/`
- `scripts/governance/vibe_code_scan.sh`
- `scripts/governance/hygiene/scan.sh`
- `.github/workflows/module-budget.yml`
- `scripts/governance/check_module_budget.py`
- `ACTIVE_SURFACE_MANIFEST.yaml`
- `docs/governance/ANTI_SLOP_RULES.md`

Loop:
1. Run static/dead-code scans: vulture, ruff F401/F811, module-budget, import graph, file age, ACTIVE_SURFACE_MANIFEST coverage.
2. Classify candidates:
   - A: safe mechanical cleanup (unused imports, trivial dead locals).
   - B: quarantine candidates (unreferenced modules, dated scripts, duplicate wrappers).
   - C: forbidden auto-delete (CLI, runtime spine, receipts, migrations, plugin registration, ontology, A2A, public API).
3. A-class: small PR with scan output + tests.
4. B-class: quarantine/deprecation marker + one-cycle observation window before deletion.
5. C-class: advisory only.

Cadence: weekly.

Verifier:
- `make hygiene-audit`
- `make hygiene-check`
- `make module-budget`
- `vulture dharma_swarm scripts api` with allowlist.
- `make test-hygiene` for test changes.

Acceptance metric:
- LOC/module count decreases without test regression.
- Duplicate wrappers reduce.
- Quarantine queue drains or gets promoted back with evidence.

### L5 — Worktree and branch quarantine loop

Purpose: make parallel work visible and prunable without losing work.

Existing owners:
- `git worktree list`
- `make onboard` parallel lanes section
- old scripts: `worktree_cleanup_2026-06-10.sh`, `worktree_cleanup_second_pass_2026-06-11.sh`, `worktree_triage_manifest.py`

Loop:
1. Enumerate every worktree and sibling repo.
2. For each: branch, upstream, ahead/behind, dirty count, latest commit, associated PR if any, active-track surface if any.
3. Bucket:
   - canonical active lane,
   - PR-backed lane,
   - dirty unbacked lane,
   - detached report lane,
   - prunable missing/stale lane,
   - archived old repo.
4. For prunable: create a bundle/patch backup first, then require operator approval for deletion.
5. For dirty lanes: create closeout packet, not immediate deletion.

Cadence: weekly, and before any “clear all PRs” automation.

Verifier:
- `git worktree list --porcelain`
- `git status --short --branch` in each worktree.
- `gh pr list` mapping branches to PRs.

Acceptance metric:
- No unknown dirty worktree older than 7 days without owner/status.
- Prunable worktrees backed up before removal.

### L6 — DGM / Darwin shadow-evolution loop

Purpose: evolve code only where fitness is real and non-gameable.

Existing owners:
- `dharma_swarm/evolution.py`
- `dharma_swarm/diff_applier.py`
- `dharma_swarm/dgm_loop.py`
- `dharma_swarm/archive.py` / `EvolutionArchive` / `FitnessScore`
- `phase2_darwin_diff_report.md`
- active `loop-closure-2026-06`

Loop:
1. Select one narrow, evaluable target from KaizenOps or CI failure.
2. Generate candidate patch in isolated branch/worktree.
3. Run objective evaluator bundle:
   - targeted tests,
   - full related tests,
   - docops/hygiene if touched,
   - security scans if relevant,
   - runtime receipt invariant if spine-adjacent.
4. Archive parent/candidate digests and fitness vector.
5. Promote only if Pareto-dominates baseline and does not modify evaluator/gate surfaces.
6. Keep shadow mode default until Loop 1 runtime closure is proven.

Cadence: weekly at first; per-candidate once L1-L5 are stable.

Hard forbidden autonomous mutation surfaces:
- fitness/evaluator code,
- CI gate definitions,
- receipt ledger implementation,
- merge authority code,
- secrets/auth/deploy paths,
- hidden/holdout evals.

Acceptance metric:
- Candidate fixes one measured failure or reduces measured complexity without regression.
- Archive can explain why rejected candidates failed.

### L7 — GEPA-style prompt/skill/governance text evolution loop

Purpose: improve agent instructions and review rubrics from real failures, not vibes.

Existing owners:
- Hermes skills and memory system.
- `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md`
- `docs/ops/PR_REVIEW_CONTROL.md`
- PR template and review control docs.
- KaizenOps waste classes.

Loop:
1. Collect 10-50 historical traces of a repeated agent failure: shallow verification, duplicate PR, missing receipt, wrong authority, stale doc citation.
2. Split into feedback set + holdout set.
3. Generate candidate prompt/skill/rubric mutation.
4. Evaluate against holdout for fewer failures, no verbosity bloat, correct tool use, receipt preservation.
5. Promote only with eval receipt.

Cadence: weekly or after 3 repeated failures of same class.

Verifier:
- small fixture corpus of prior transcripts/PR bodies.
- LLM judge allowed only as advisory; final gate checks concrete markers: owner named, verifier command named, no unsupported completion claim.

Acceptance metric:
- Fewer repeated agent mistakes in future KaizenOps/PR review cycles.
- Skills/docs shrink or stay same length unless justified.

### L8 — Memory and knowledge curation loop

Purpose: prevent memory/wiki/notes from becoming stale command surfaces.

Existing owners:
- Hermes memory/skills.
- `~/wiki` curated KB.
- Chetana raw wiki layer.
- Semantic Commons in dharma_swarm.
- Staging promotion job in repo cron: `staging_promote` / `scripts/consume_review_marks.py`.

Loop:
1. Identify top used, stale, contradictory, and duplicate memories/notes.
2. Check each against owner file or live receipt.
3. Promote only if it prevents repeated steering and has stable owner path.
4. Prune if contradicted, duplicate, expired, or too vague to operationalize.
5. Update skill only if a tested workflow succeeded.

Cadence: weekly.

Verifier:
- source path exists,
- owner file still says it,
- no contradiction with `make onboard` / ACTIVE_TRACK / runtime receipts.

Acceptance metric:
- Fewer stale handoff TODOs treated as commands.
- Fewer duplicated wiki/memory claims.

### L9 — A2A/NATS transport-and-semantics loop

Purpose: separate delivery ACKs from semantic work, and stop stale agents being called alive.

Existing owners:
- `.dharma/a2a_bus/conjunction/latest.{md,json}`
- A2A scripts in repo and Hermes.
- `nats-cleanup`, `nats-inbox-drain`
- `scripts/runtime/a2a_inbox_bridge.py`
- A2A preflight worktree.

Loop:
1. Read file-bus and NATS state.
2. Classify each agent: fresh semantic responder, transport-only, stale, missing, invalid receipt.
3. Reclaim expired/claimed-no-receipt tasks after SLA.
4. Emit a single conjunction score and exact blockers.
5. Do not count `HANDLER_ACKED` or transport delivery as semantic completion.

Cadence: every 30-60m if fleet active; otherwise daily.

Verifier:
- latest conjunction JSON.
- terminal receipts for claimed tasks.
- NATS consumer state if NATS is canonical transport.

Acceptance metric:
- No stale agent listed as active.
- Claimed-without-terminal-receipt count trends to zero.

### L10 — DE_BUG_CORRAL sweeping and relevance loop

Purpose: keep the bug corral alive as a real composting/sweeping organ, not a stale graveyard or another report pile.

Current evidence from 2026-06-23 scan:
- `scripts/governance/name_drift_preflight.py` exists and says it routes naming-drift evidence into `DE_BUG_CORRAL`.
- `make bug-corral-scan` exists and calls that script.
- repo `cron_jobs.json` declares `de_bug_corral_scan` every 6h.
- live `.dharma` cron has a De Bug Corral job, but subagent evidence says it was erroring with `shell handler command is not allowlisted: python3`.
- Running the scan during this report produced 558 hits routed to proposed files:
  - `DE_BUG_CORRAL/01.md`: 4
  - `DE_BUG_CORRAL/02.md`: 9
  - `DE_BUG_CORRAL/03.md`: 495
  - `DE_BUG_CORRAL/04.md`: 5
  - `DE_BUG_CORRAL/07.md`: 26
  - `DE_BUG_CORRAL/09.md`: 19
- The same run reported `canonical_dir_present: False` and `canonical_index_present: False`. This is the key bug: the sweeper exists, but the corral it routes into is absent on this branch.

Loop:
1. Sweep:
   - run `make bug-corral-scan` or `scripts/governance/name_drift_preflight.py` with JSON + markdown outputs under `~/.dharma/logs/`.
   - use repo `.venv/bin/python` or `/opt/homebrew/bin/python3.11`, not cron’s generic `python3`, until the allowlist/runtime is fixed.
2. Normalize:
   - dedupe repeated generated-report hits.
   - ignore stale `MISSING` claims when the file now exists.
   - collapse repeats by `(route, source_path, normalized_text_hash)`.
3. Route:
   - every hit maps to one canonical corral file, not scattered docs.
   - proposed route map:
     - `00.md`: index, policy, sweep status.
     - `01.md`: declared-vs-actual interface/name mismatch.
     - `02.md`: hygiene / anti-slop naming signals.
     - `03.md`: repo-wide naming and structural drift.
     - `04.md`: generated inventory / evidence drift.
     - `07.md`: active-track / doctrine pointer drift.
     - `09.md`: corral path / provenance drift.
4. Compost:
   - each route file has sections: `new`, `accepted`, `in_progress`, `resolved`, `false_positive`, `stale_generated`.
   - a sweep may add or update entries only; it may not delete unresolved history.
5. Act:
   - KaizenOps selects at most one corral item per day as the next corrective action.
   - every selected item gets owner, file surface, verifier command, and stop condition.
6. Verify:
   - resolved item requires a verifier, usually one of:
     - `make semantic-commons-check`
     - `make bug-corral-scan ARGS="--strict-semantic-commons --limit 20"`
     - `make docops-integrity`
     - targeted test such as `tests/test_name_drift_preflight.py`.
7. Age out:
   - false positives and stale generated claims are marked, not silently removed.
   - repeated false positives feed back into scanner filters.

Cadence:
- Sweep every 6h once runtime is fixed.
- Human/KaizenOps triage daily.
- Route-file cleanup weekly.
- Scanner filter tuning only when false positives repeat across 2+ sweeps.

Immediate implementation packet:
1. Create the missing canonical corral skeleton:
   - `DE_BUG_CORRAL/00.md`
   - `DE_BUG_CORRAL/01.md`
   - `DE_BUG_CORRAL/02.md`
   - `DE_BUG_CORRAL/03.md`
   - `DE_BUG_CORRAL/04.md`
   - `DE_BUG_CORRAL/07.md`
   - `DE_BUG_CORRAL/09.md`
2. Add a `DE_BUG_CORRAL/SWEEP_RECEIPT_SCHEMA.md` or inline schema in `00.md`.
3. Fix live cron invocation to use the repo venv interpreter and allowed shell command.
4. Add a compact digest writer so 558 raw hits become a small route delta, not markdown sludge.
5. Add a strict check: if the canonical corral index is missing, the sweep exits nonzero in CI/preflight mode but still writes a diagnostic receipt in cron mode.

Acceptance metrics:
- canonical index exists.
- latest sweep receipt age < 6h.
- raw hits are deduped into route deltas.
- at least one corral item per day is either accepted, resolved, or explicitly marked false-positive/stale.
- repeated false positives decrease over time.
- no `python3` allowlist failure in live cron.

Do not do:
- do not let the sweeper directly edit ontology or Semantic Commons.
- do not auto-delete corral history.
- do not count “558 hits found” as progress; progress is routed, deduped, acted, verified.
- do not create noncanonical `docs/bug-corral*` paths.

### L11 — Fitness contract and anti-reward-hacking loop

Purpose: make evolution non-gameable.

Existing owners:
- `docs/governance/PR_QUALITY_GATES.md`
- `docs/governance/ANTI_SLOP_RULES.md`
- Runtime Truth receipt stack.
- ActiveTrack non-goals.

Loop:
1. Every proposed autonomous improvement declares target fitness dimensions.
2. Gate checks whether patch touches evaluators, tests, workflows, receipts, or scoring code.
3. If yes, human review required unless the BetCard explicitly says test/evaluator bug.
4. Run negative control or known-bad check where possible.
5. Archive candidate result with cost and verifier output.

Cadence: per evolution candidate / per PR claiming score improvement.

Proposed dimensions:
- correctness,
- truthfulness/receipt support,
- minimality,
- maintainability/module budget,
- security,
- operability/runtime truth,
- cost,
- PR queue health,
- human/external value.

Acceptance metric:
- No PR can improve a score by weakening its evaluator without explicit labeled review.

## 3. Keep / merge / prune decisions

Keep and strengthen:
- KaizenOps.
- ActiveTrack governance.
- Runtime Truth / live ops census.
- Loop Supervisor.
- PR stale/dedupe/bot-limit/CI-health/Merge Master Mike, but unify the view.
- DocOps/hygiene/module-budget gates.
- Darwin shadow-evolution, but keep shadow default.

Merge / consolidate:
- PR clearer + PR CI health + Merge Master Mike into one PR control-plane receipt.
- Repo cron + `.dharma` cron + Hermes cron into a scheduler reconciliation dashboard before adding jobs.
- Free evolution / Darwin / DGM variants under one archived candidate-selection path.
- A2A state tick writers under one canonical writer.
- Runtime backlog firebreak / A2A stale reaper / provider credit checks into live ops + loop supervisor.

Quarantine / prune:
- Stale prompt cron jobs pointing to `~/dgc-core`, `~/agni-workspace`, old `~/jagat_kalyan` paths unless live path proof exists.
- Dated worktree cleanup scripts after replacing with current triage tool.
- Draft governance report PRs older than latest successful report, after operator review.
- Stale agent liveness labels that lack fresh semantic receipts.

Do not auto-prune:
- runtime spine,
- receipt code,
- A2A/NATS bridge code,
- migration files,
- CLI entrypoints,
- ontology/Semantic Commons,
- public APIs,
- workflow gates,
- fitness evaluators.

## 4. Minimal implementation sequence

### Phase 1 — make truth fresh and bounded

1. Refresh live ops census and runtime closeout.
2. Patch PR clearer to default to `AmitabhainArunachala/dharma_swarm` only and report-only unless `PR_CLEAR_ACTION=1`.
3. Create scheduler reconciliation report comparing repo cron, `.dharma` cron, Hermes cron.
4. Create worktree/branch triage receipt.

Definition of done:
- fresh census < 6h,
- PR clearer dry-run receipt exists with auth true,
- scheduler split-brain table exists,
- all worktrees bucketed.

### Phase 2 — close existing waste, no new loops

1. Use KaizenOps daily one-action loop to close one blocker at a time:
   - Loop 1 receipt,
   - cybernetics codex admission/runtime receipt,
   - stale ops report PRs,
   - A2A claimed-without-terminal-receipt backlog.
2. Do not open new architecture tracks unless operator explicitly chooses.

Definition of done:
- open PR count < 5 or every PR has explicit owner/blocker,
- loop-closure has receipt or named external blocker,
- stale agent labels corrected.

### Phase 3 — pruning with quarantine

1. Run dead-code/module-diet scan.
2. Produce A/B/C delete-confidence buckets.
3. Open one safe mechanical cleanup PR or quarantine packet.

Definition of done:
- one deletion/quarantine PR with verifier output,
- no dynamic/runtime surface auto-deleted.

### Phase 4 — evolution only after gates are stable

1. Build `fitness_contract.yaml` or equivalent.
2. Run one GEPA-style prompt/rubric evolution on PR review/KaizenOps templates.
3. Run one Darwin shadow candidate on a narrow failing test or module-budget issue.

Definition of done:
- candidate archive has parent/candidate digests, eval results, cost, decision.
- no evaluator/gate/receipt code modified without human review.

## 5. Research mapping

Named external patterns that matter here:

- GEPA / reflective prompt evolution: use trajectories + reflections + Pareto selection for prompts/skills/rubrics.
- Darwin Gödel Machine: archive candidate self-modifications; promote only parent-beating verified candidates.
- AlphaEvolve / FunSearch style: only use code evolution where objective evaluators are systematic and hard to game.
- GitHub merge queue / required checks: agents do not decide done; checks and receipts decide eligibility.
- Reward hacking / specification gaming literature: forbid autonomous patches from modifying evaluators/gates/receipt writers when claiming score improvement.
- Agent societies / stigmergy: shared memory helps only above density and with fresh semantic receipts; stale ACKs do not count.

## 6. First concrete next actions

1. Patch `/Users/dhyana/.hermes/scripts/pr_clearer.py` to:
   - default repo filter = `AmitabhainArunachala/dharma_swarm`,
   - action mode gated by `PR_CLEAR_ACTION=1`,
   - report-only default,
   - write before/after PR queue receipt.

2. Add or generate scheduler reconciliation:
   - repo `cron_jobs.json`, `.dharma/cron/jobs.json`, Hermes `~/.hermes/cron/jobs.json`.
   - classify canonical / duplicate / retired / broken.

3. Refresh runtime truth:
   - run `scripts/runtime/live_ops_census.py --write` with correct Python.
   - run runtime closeout gate.
   - route the top stale/blocker to KaizenOps.

4. Generate worktree hygiene receipt:
   - all worktrees, dirty count, ahead/behind, PR mapping.
   - no deletion; just buckets.

5. Open one KaizenOps daily packet from the above, not five.

## 7. What I did not verify

- I did not mutate code.
- I did not run process/port census because a similar command was blocked in a subagent environment.
- I did not run full tests or governance gates; this is a design/report artifact, not a code PR.
- I did not claim any loop is production-ready unless existing owner output already did.
