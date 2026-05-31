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
experiments, but it is not the merge authority. PR Review Control is pull-based
from the local operator machine: it asks GitHub for live state, writes packets
under `~/.dharma`, and does not depend on inbound webhooks.

## Commands

```bash
make pr-queue
make pr-packet PR=397
make pr-reviewers
make pr-run-codex PR=397
make pr-run-claude PR=397
make pr-gate PR=397
make pr-merge PR=397 ARGS="--confirm merge-pr-397"
```

`make pr-run-claude` prefers `/Users/dhyana/.npm-global/bin/claude` and removes
`ANTHROPIC_API_KEY` from the Claude process by default. This prevents a depleted
Anthropic Console key from hijacking Claude Code subscription auth. To force
API-key billing for a funded key, set:

```bash
DHARMA_CLAUDE_REVIEW_USE_API_KEY=1 make pr-run-claude PR=397
```

To override the binary entirely:

```bash
CLAUDE_REVIEW_COMMAND="/Users/dhyana/.npm-global/bin/claude -p" make pr-run-claude PR=397
```

`make pr-merge` is dry-run by default. It prints the `gh pr merge` command only
after the gate passes. To execute, add `--execute` and the exact confirmation
token:

```bash
make pr-merge PR=397 ARGS="--confirm merge-pr-397 --execute"
```

High-risk and critical PRs require `--human-approved` even when Codex and Claude
both provide review receipts.

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
changed files, hot-path risk, and unresolved review-thread count when GitHub
GraphQL is available.

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
- Risk is `HIGH` or `CRITICAL` and no `--human-approved` flag is present.

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
