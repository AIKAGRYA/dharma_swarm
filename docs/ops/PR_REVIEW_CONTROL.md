# PR Review Control

Status: local operator control surface.

Purpose: make GitHub PR review and merge decisions receipt-backed, dual-agent,
and fast enough for a large open-PR queue. This does not replace GitHub branch
protection, CI, AgentOps, or human approval. It gives Codex and Claude Code the
same packet, then blocks merge unless deterministic gates and both reviews are
present.

## Why `@terminal-review` Was Brittle

`.github/workflows/codex-mention-router.yml` now owns the GitHub-side
`@terminal-review` response: it creates the same deterministic packet/gate
summary comment that the local CLI prints. The older
`scripts/codex_mention_bridge.py` remains a local webhook bridge for inbound
experiments and now defaults to `@codex`, not `@terminal-review`. It is not the
merge authority. PR Review Control is pull-based from the local operator
machine: it asks GitHub for live state, writes packets under `~/.dharma`, and
does not depend on inbound webhooks.

## Commands

```bash
make pr-queue
make pr-packet PR=397
make pr-reviewers
make pr-run-codex PR=397 ARGS="--timeout-s 240"
make pr-run-claude PR=397 ARGS="--timeout-s 240"
make pr-gate PR=397
make pr-merge PR=397 ARGS="--confirm merge-pr-397"
```

`make pr-run-codex` uses `codex exec --ephemeral` with
`model_reasoning_effort="medium"` by default so queue reviews do not inherit an
unbounded xhigh interactive profile. Override with
`DHARMA_CODEX_REVIEW_REASONING_EFFORT=high` or `CODEX_REVIEW_COMMAND=...` when a
single PR deserves a slower review.

`make pr-run-claude` prefers `/Users/dhyana/.npm-global/bin/claude -p
--max-turns 8` and removes `ANTHROPIC_API_KEY` from the Claude process by
default. This prevents a depleted Anthropic Console key from hijacking Claude
Code subscription auth, and the max-turn cap makes quota/auth failures surface
as receipts instead of silent stalls. To force API-key billing for a funded key,
set:

```bash
DHARMA_CLAUDE_REVIEW_USE_API_KEY=1 make pr-run-claude PR=397
```

To override the binary entirely:

```bash
CLAUDE_REVIEW_COMMAND="/Users/dhyana/.npm-global/bin/claude -p" make pr-run-claude PR=397
```

Reviewer runs are bounded. The default wall-clock timeout is 600 seconds, or
`CODEX_REVIEW_TIMEOUT_SECONDS` / `CLAUDE_REVIEW_TIMEOUT_SECONDS` when set. To
tighten one run:

```bash
make pr-run-codex PR=397 ARGS="--timeout-s 120"
make pr-run-claude PR=397 ARGS="--timeout-s 120"
```

Use a live probe when auth says Claude is logged in but runtime/quota may be
stale:

```bash
make pr-reviewers ARGS="--live-probe --probe-timeout-s 20"
```

`make pr-merge` is dry-run by default. It prints the `gh pr merge` command only
after the gate passes. To execute, add `--execute` and the exact confirmation
token:

```bash
make pr-merge PR=397 ARGS="--confirm merge-pr-397 --execute"
```

High-risk and critical PRs require `--human-approved` plus
`--human-approval-note` even when Codex and Claude both provide review receipts.

## Receipt Layout

```text
~/.dharma/pr_review/
  queue/
    latest.json
    latest.md
  pr-397/
    20260531T000000Z/
      FACTS.json
      REVIEW_PACKET.md
      DIFF.patch
      PR_BODY.md
      changed_files.txt
      PROMPT_CODEX.md
      PROMPT_CLAUDE.md
      codex_review.md
      claude_review.md
      MERGE_GATE.json
      MERGE_GATE.md
```

The packet includes current mergeability, CI rollup, Coherence Delta status,
changed files, hot-path risk, unresolved review-thread count when GitHub
GraphQL is available, and a `DIFF.patch` snapshot so reviewers do not need to
start with broad repository scans.

## Merge Gate

The gate blocks when any of these are true:

- PR is draft.
- PR head SHA changed since packet/review generation.
- GitHub says the branch is not mergeable.
- Any check is failing.
- Check rollup is empty or contains an unknown conclusion.
- Checks are pending, unless `--allow-pending` is explicitly passed.
- GitHub review decision is `CHANGES_REQUESTED`.
- Coherence Delta fields are missing or placeholders.
- Review-thread lookup fails or review threads are unresolved.
- `codex_review.md` / `codex_review_receipt.json` is missing, invalid, nonzero-exit, stale-head, or not an `APPROVE` verdict.
- `claude_review.md` / `claude_review_receipt.json` is missing, invalid, nonzero-exit, stale-head, or not an `APPROVE` verdict.
- A review receipt lacks the exact `## Verdict`, `## Findings`,
  `## Missing Tests Or Proof`, and `## Merge Conditions` sections.
- A review receipt is a shallow approval without concrete file/path evidence.
- Risk is `HIGH` or `CRITICAL` and no `--human-approved` flag plus
  `--human-approval-note` receipt is present.

## Agent Contract

Codex and Claude read the same `REVIEW_PACKET.md` and answer from their own
fresh context. The generator of a change must not be the only evaluator of that
change. Each review must put findings first, cite concrete file evidence, and
state exact merge conditions.

## Non-Interactive Claude Reviews

Claude reviews can run unattended only after one of these credentials is valid:

- Claude Code subscription auth with a long-lived token from
  `claude setup-token`.
- A funded Anthropic Console key, explicitly enabled with
  `DHARMA_CLAUDE_REVIEW_USE_API_KEY=1`.

The first OAuth or token grant must be human-approved. After that, the review
lane should be non-interactive until the token expires, is revoked, or the
account runs out of quota.

## Queue Triage

Use `make pr-queue` first. `GITHUB_GREEN_NEEDS_PACKET` means GitHub has no
obvious blocker; it is not merge permission. Typical ordering:

1. Close or repair `BLOCKED_CONFLICT`, `BLOCKED_CHECKS`, and
   `BLOCKED_REVIEW`.
2. Packet and review `GITHUB_GREEN_NEEDS_PACKET` PRs that are low or medium
   risk.
3. Packet high-risk PRs only after the active track and hot-path ownership are
   clear.
4. Keep large or doctrine-changing PRs out of batch merges.

## 58-PR Portfolio Cleanup Wave

Snapshot date: 2026-06-05.

The open-PR portfolio cleanup goal is entropy reduction with integrity, not
maximal merging. Do not try to merge every open PR. Freeze new non-urgent
research, report, generated, and feature PRs until the backlog is below the
operator threshold.

Use Mike as the execution gate:

- `@mix_master_mike` for packet, gate, and cleanup comments.
- `@mix_master_mike merge when clean` only for a PR already selected for merge.
- Mike must keep merge authority conditional on clean mergeability, green CI,
  DocOps/coherence pass, review receipts, conflict checks, and explicit human
  approval where required.

Immediate close batch:

- Generated/report churn: #460, #462, #463, #464, #466, #467, #475, #483,
  #485.
- PR janitor/session reports: #451, #452, #454, #455, #456, #457, #458, #459.
- Superseded spine-adoption docs: #425, #426.
- Duplicate/single Palantir auto-grounding reports unless selected for the
  canonical archive: #413, #415, #419, #420, #423, #424, #432, #434, #439,
  #442.
- Stale stacked docs: #373, unless #370 is retained and #373 is restacked.

Hold for curated review:

- DocOps unblocker: review #453; merge only if still required, otherwise close
  as superseded.
- Governance drafts: #325, #394, #412, #476.
- Canonical research/archive candidates: #405, #410, #414, #422. Keep at most
  one canonical bundle unless a maintainer explicitly accepts multiple archives.
- Runtime/domain batches:
  - Ops/runtime: #332, #465, #431, #344, #323.
  - H-stack: #384, #388, #389, #390, #391.
  - Guardian: #383, #392.
  - Tests-only candidate: #450.
  - Design/docs hold: #402, #461.

For every retained runtime or governance PR, regenerate a fresh packet and
verify base branch, mergeability, CI, DocOps/coherence, runtime test scope,
overlap with current `main`, receipt freshness, and rollback path before any
merge request is issued.
