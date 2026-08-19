# Merge-queue canary receipt — 2026-08-18

**Executes:** yes-sheet ratification row 8
(docs/plans/YES_SHEET_RATIFICATION_2026-08-18.md:21): "Run merge canary; flip
low-risk auto-merge per the 2026-07-29 grant." Grant of record:
docs/ops/OPERATOR_RULING_2026-07-29_AUTO_WITH_DECORRELATED_REVIEW.md (witness
prose; enforced policy files win per its :13-18).

## 1. Finding that reshapes the execution

The merge actuator the 2026-07-29 grant contemplated flipping **no longer
exists**. PR #1364 (commit `1fedc5e4`, 2026-08-17) deleted Merge Master
Mike's merge-actuation path because the repository migrated to GitHub's
native merge queue, which performs merges itself
(reports/agentops/work_packets/mike-WP-DEAD-ACTUATOR-REMOVAL-20260817.json:6).
`scripts/governance/automerge_tier_policy.json:30` (`"actuation_enabled":
false`) is consumed by no runtime code — its only other reference is the test
pinning it false (tests/test_automerge_tier_policy.py:549) — and
tests/test_pr_merge_control_no_actuation.py:38-44 structurally forbids a merge
subcommand from returning. Nothing in this receipt re-creates that path.

The live merge mechanism is therefore: **GitHub merge queue + auto-merge +
the six required checks** (docs/governance/PR_QUALITY_GATES.md:266-270;
required set in docs/governance/CI_TRUTH_CONTRACT.json). What the audit's
item 4 (docs/plans/PLAYING_SMALL_AUDIT_2026-08-18.md:49) named as the missing
canary is a live proof that GitHub's server-side protections actually enforce
that mechanism. That proof now exists and is recorded below.

## 2. Server-side canary evidence — five real merge-queue merges, 2026-08-18

All five merges of 2026-08-18 UTC went through branch `main`'s merge queue.
The queue validated each candidate on a synthetic SHA whose queue-branch name
embeds the exact base it was validated against, then fast-forwarded `main` to
the validated SHA — a verifiable compare-and-swap chain:

| # | PR | queue branch (base it validated against) | validated SHA → main |
|---|----|----|----|
| 1 | #1222 | (queue) | `3b2b06a0` |
| 2 | #1331 | (queue) | `5c91eb07` |
| 3 | #1365 | (queue) | `8e2aa377` |
| 4 | #1145 | `gh-readonly-queue/main/pr-1145-8e2aa3775e5c9ad03efbffa419142df9d739cf00` | `6e756d86` |
| 5 | #1129 | `gh-readonly-queue/main/pr-1129-6e756d865ae36de7e92397e67b7b4b77b1fccffe` | `94ea91c8` |

Rows 4-5 show the chain explicitly: #1145 was validated against #1365's
result (`8e2aa377`), produced `6e756d86`; #1129 was validated against
`6e756d86`, produced `94ea91c8`, the `main` tip at receipt time
(`git log origin/main --oneline`). No candidate could land against a stale
base — this is the base-CAS behavior
reports/agentops/work_packets/WP-MIKE-P0-20260813.json:93 required proven.

**Required checks ran on the synthetic SHA and passed** (PR #1129's
validation, all on `94ea91c8`, event `merge_group`):

- pytest (3.11): job 95578578858, run 32092932300, success
  (https://github.com/AIKAGRYA/dharma_swarm/actions/runs/32092932300/job/95578578858)
- pytest (3.12): job 95578578798, same run, success
  (https://github.com/AIKAGRYA/dharma_swarm/actions/runs/32092932300/job/95578578798)
- gitleaks: run 32092932302, success
- DocOps integrity gate: run 32092932326, success
- Coherence Delta PR body: run 32092932314, success
- Onboarding admission parity: run 32092932315, success

**Required-vs-advisory separation is enforced server-side, at job
granularity** — two live demonstrations from the same day:

- PR #1129's queue validation had a **failed** semgrep workflow run
  (32092932356) on the synthetic SHA; the queue merged anyway. Semgrep is not
  in the required set (docs/governance/CI_TRUTH_CONTRACT.json) — correctly
  non-blocking.
- PR #1145's queue validation (run 32091626243, synthetic SHA `6e756d86`) had
  the advisory job "AgentOps packet scope" (job 95574771725) **fail** while
  the required job "Onboarding admission parity" (job 95575064330) in the
  *same workflow* **succeeded** — and the queue merged. GitHub blocks on the
  required context, not the workflow's overall color.

This satisfies titanium-WP-MERGE-QUEUE-READINESS-V2.json:109-111's demand for
real merge-queue candidates with required checks on the exact synthetic SHA
and no failed merge-group workflow among the required contexts — five times
over, not once.

## 3. The grant's named weekly canary — dispatched

The 2026-07-29 grant's §9 canary (seeded reviewer-integrity PR;
OPERATOR_RULING_2026-07-29...md:63-64, implemented in
.github/workflows/loop-watcher.yml:108-197) was dispatched with
`canary=true`: run 32123554714
(https://github.com/AIKAGRYA/dharma_swarm/actions/runs/32123554714),
2026-08-18T09:48:47Z. It opens a `canary-sandbox`-labeled PR carrying a
seeded off-by-one defect; a reviewer that APPROVES it is dropped from
rotation (scripts/governance/loop_watcher.py:256-282). Canary-sandbox PRs are
never mergeable unattended
(scripts/governance/check_automerge_tier_policy.py:370-375). The kill-switch
was verified disengaged before dispatch (no `docs/ops/loop_control/KILLSWITCH`
on `origin/loop-control`).

## 4. State of "the flip" after this receipt

- The flip's substrate — merge queue + auto-merge on `main` — is **already
  live and now proven** (§2). Low-risk PRs reach `main` unattended today by
  arming GitHub auto-merge once required checks and the policy tiers admit
  them.
- Policy of record for tiers is the 2026-08-12 SAFE_P0 ruling inside
  scripts/governance/automerge_tier_policy.json: `docs_low` is the genuinely
  unattended class; every code-class PR still requires a native current-head
  APPROVED review by the allowlisted operator (`:31-45`). This receipt
  changes no tier.
- Remaining preconditions are **operator-hands** and listed on the sitting
  sheet: register the "Automerge tier policy" context in branch protection
  and add its row to scripts/governance/ci_parity_manifest.json in the same
  action (.github/workflows/automerge-tier-policy.yml:16-20 requirement;
  manifest currently lists six contexts, none of them the tier policy).

## 5. Boundaries kept

No edit to automerge_tier_policy.json, pr_merge_control.py, any workflow, or
the no-actuation tests — the entire flip surface is Tier 2 operator
hand-merge by construction (automerge_tier_policy.json:139-171), and this
receipt itself lands only through an operator-merged PR.
