# PR Review Control

Status: local operator control surface.

Purpose: make GitHub PR review and merge decisions receipt-backed, dual-agent,
and fast enough for a large open-PR queue. This does not replace GitHub branch
protection, CI, AgentOps, or human approval. It gives Codex and Claude Code the
same packet, then blocks merge unless deterministic gates and both reviews are
present.

## Why `@terminal-review` Was Brittle

The workflow file is still named `.github/workflows/codex-mention-router.yml`,
but its current workflow name is `merge-master-mike-router`. It no longer acts
as a generic Codex webhook forwarder. It routes owner/member/collaborator PR
mentions into deterministic Merge Master Mike packet/gate/comment flows, and
conditional merge is only armed by an explicit `merge when clean` command.
Local PR Review Control remains pull-based from the operator machine: it asks
GitHub for live state, writes packets under `~/.dharma`, and does not depend on
inbound local webhooks.

## CI Truth Contract

`docs/governance/CI_TRUTH_CONTRACT.json` is the machine-readable CI membrane.
It separates required checks from advisory checks, names the local repro
command, assigns an owner, and states whether autofix is allowed.

```bash
make ci-truth ARGS="--pr 397"
make ci-truth ARGS="--rollup-json /path/to/status-rollup.json"
```

Merge Master Mike consumes this contract in `make pr-packet`, `make pr-gate`,
`make pr-mike`, and `make pr-merge`. Required CI entries block merge when they
are missing, pending, failed, cancelled, timed out, or action-required.
Advisory entries are reported as degraded warnings with repro commands; raw
GitHub failing checks still block through the normal rollup gate.

This keeps authority split cleanly:

- ACI / CI truth contract defines what CI evidence means.
- Merge Master Mike coordinates packets, reviewers, gates, comments, and
  conditional clean-gate merge requests.
- Branch protection remains the final GitHub enforcement layer.

## Commands

```bash
make pr-queue
make ci-truth ARGS="--pr 397"
make pr-mike
make pr-packet PR=397
make pr-reviewers
make pr-run-codex PR=397
make pr-run-claude PR=397
make pr-gate PR=397
make pr-merge PR=397 ARGS="--confirm merge-pr-397"
```

## GitHub Comment Adapter

`.github/workflows/codex-mention-router.yml` is the GitHub-hosted Merge Master
Mike adapter. It runs from the default branch checkout, not from untrusted PR
code, and can only merge when explicitly asked to `merge when clean` after the
deterministic gate is clean.

Call Mike from a PR comment or review-thread comment:

```text
@merge-master-mike
@merge_master_mike
@mix-master-mike
@mix_master_mike
@mike
@terminal-review
```

The workflow also supports manual dispatch with a `pr` input from the GitHub
Actions UI. A normal PR comment mention always posts a fresh visible Mike
comment; manual dispatch may update the stable
`<!-- dharma-pr-review-control:auto -->` comment.

This is not the official `@claude` GitHub Actions path. No Claude GitHub app or
Anthropic/Claude repository secret is assumed here. If that route is adopted,
credential installation and secret rotation are separate operator actions before
any workflow can be declared live.

For a PR-specific mention, the GitHub adapter does only this:

1. create a deterministic packet for the PR;
2. run the merge gate;
3. optionally run Mike's guarded `gh pr merge --auto` path when the comment says
   `merge when clean` or manual dispatch sets `merge_when_clean=true`;
4. render and post the Mike status comment.

When a comment asks for backlog work with language such as `all open PRs`,
`open pull requests`, `backlog`, `queue`, or `PR cleanup`, the same router runs
the backlog fanout path in packet-only mode for up to five PRs, attempts the A2A
NATS session with Mike credentials when configured, posts a fresh visible summary
comment, and uploads the Mike receipts as a workflow artifact. This is still
evidence fanout, not unconditional merge authority. The hosted comment adapter
does not require NATS by default; set `MERGE_MASTER_MIKE_NATS_REQUIRED=true` as
a repository variable only when the NATS secrets are configured and JetStream ack
verification must hard-block the run.

It does not run local Codex or Claude reviewer processes, because the
GitHub-hosted runner does not have the operator machine's tmux, NATS, Claude
Code subscription session, Codex local session, or `~/.dharma` receipt nest. It
also does not approve, push, mark human approval, resolve review threads, or
bypass branch protection.

Plain mentions are packet/gate/comment only. Conditional merge requires an
explicit command:

```text
@merge_master_mike merge when clean
```

In that mode Mike still blocks unless the required reviewer receipts are present
and acceptable. The default quorum is `codex,claude`. The special
`required_reviewers=none` policy is reserved for docs-low automation where the
dispatcher has already limited the diff to documentation/report projections.

## Greptile Review Intake

Greptile comments are an external automated review signal that must be captured
into one local system instead of living only as scattered GitHub threads.

Current intake artifacts:

```text
reports/governance/greptile_review_intake_2026-06-18.md
reports/governance/greptile_review_intake_2026-06-18.json
```

Ownership split:

- `docs/ops/PR_REVIEW_CONTROL.md` owns the operational intake shape.
- `docs/governance/MMM_CHARTER.md` owns Merge Master Mike's authority boundary.
- `docs/governance/KAIZENOPS.md` owns the improvement interpretation: recurring
  Greptile findings become waste classes and one-action repair packets.

Merge Master Mike should read Greptile intake when building PR packets/gates.
Greptile findings do not approve, reject, or merge PRs. They are advisory review
inputs. P1 findings are merge blockers unless resolved or explicitly waived by
the operator. P2 findings are advisory for docs-low/report-only PRs, but become
repair-needed for runtime, governance, security, CI, ontology, or merge-control
surfaces.

## Merge Hygiene Quorum

Merge Master Mike is the final repo-hygiene arbiter, but Mike should not turn
every PR into the same three-agent ceremony. The hygiene layer in
[`docs/governance/hygiene/`](../governance/hygiene/README.md) defines both
ordinary `VC-*` code-quality signals and `AI-*` agent-governance signals. Mike
uses those signals to ask final merge questions about fake verification,
instruction trust, dependency provenance, gate gaming, architecture drift, and
maintainer burden.

Reviewer receipts should be risk-tiered:

| Profile | Use when | Required evidence |
|---|---|---|
| `docs-low` | docs-only or generated hygiene updates with green CI | CI, Coherence Delta, Mike packet |
| `code-low` | small non-runtime code change | CI, Coherence Delta, Mike packet, one independent review |
| `runtime-medium` | runtime, governance, memory, provider, or workflow surface | CI, Coherence Delta, Mike packet, two independent reviews |
| `governance-high` | merge authority, security, dependencies, gates, memory promotion, or public claims | CI, Coherence Delta, Mike packet, two independent reviews, human approval |
| `repair-needed` | implementation or conflict repair is actually needed | add Devin or another repair receipt |

Devin is not a default passive reviewer. Devin is a repair and integration lane.
Require a Devin receipt when Devin performed or verified repair work, not merely
because a PR exists.

Hosted backlog comments remain `packet-only` by default. They should surface
which quorum profile appears appropriate, then leave real reviewer execution to
the local operator lane or to a deliberately assigned external worker.

For hosted backlog triage, do not create another workflow. Use one of the
existing entry points:

```text
@merge_master_mike backlog
```

or run GitHub Actions → `merge-master-mike-backlog` with:

- `mode`: `packet-only`
- `max_prs`: `5`
- `merge_mode`: `off`
- `nats_required`: `false`, unless NATS secrets are configured and hard
  verification is desired

Use the GitHub comment adapter for fast PR triage. Use the local persistent Mike
lane for real dual-review fanout:

```bash
make pr-run-codex PR=397
make pr-run-claude PR=397
make pr-gate PR=397
```

For a docs-low generated or projection-only PR, the hosted automerge dispatcher
may call the same adapter with `required_reviewers=none`. That path is not a
general reviewer bypass; the workflow skips any code, workflow, test, runtime,
dashboard, API, or script path.

For Devin-assisted queue cleanup, use the AGNI/NATS playbook:

```text
docs/ops/DEVIN_NATS_PR_JANITOR_PLAYBOOK.md
```

Devin is an evidence-only collaborator under `devin-roaming-2987d222`. His
AGNI NATS lane is for live intent/dependency synthesis with Mike and the fleet;
it does not grant merge, approval, push, comment, credential, or governance
exception authority.

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
`DHARMA_PR_REVIEW_TIMEOUT_S` when set. To tighten one run:

```bash
make pr-run-codex PR=397 ARGS="--timeout-s 120"
make pr-run-claude PR=397 ARGS="--timeout-s 120"
```

## Merge Master Mike Fanout

`make pr-mike` is the minimal CodeRabbit-like lane for Dharma Swarm. It reuses
this PR Review Control surface rather than creating another control plane.

Default run:

```bash
make pr-mike
```

That command:

1. refreshes `make pr-queue`;
2. selects up to three PRs in `GITHUB_GREEN_NEEDS_PACKET` or
   `NEEDS_AGENT_REVIEW`;
3. creates a packet for each selected PR;
4. runs Codex and Claude reviewer lanes;
5. runs the merge gate;
6. writes a local GitHub-comment draft and a Mike receipt.

Receipts land under:

```text
~/.dharma/pr_review/mike_fanout/<run-id>/
  receipt.json
  summary.md
```

Comment drafts land in each packet directory as `GITHUB_COMMENT.md`. The fanout
does not post comments, merge, approve, push, or edit source.

Useful bounded modes:

```bash
make pr-mike ARGS="--dry-run --max-prs 5"
make pr-mike ARGS="--packet-only --max-prs 2"
make pr-mike ARGS="--max-prs 1 --timeout-s 180"
```

If a reviewer hangs, fails to spawn, exits non-zero, or returns empty output,
the runner writes a `BLOCKED` markdown artifact plus a JSON receipt. The merge
gate treats that as a hard blocker until the reviewer is re-run cleanly.

## Persistent Merge Master Mike

`make pr-mike` is the PR-only fanout. `make mike-*` is the persistent Mike nest
around that fanout. It adds wake receipts, action logs, status projection, tmux
supervision, and a launchd-ready entrypoint without changing merge authority.

Canonical local commands:

```bash
make mike-bootstrap
make mike-wake
make mike-status
make mike-cycle ARGS="--cycle-mode dry-run --max-prs 5"
make mike-cycle ARGS="--cycle-mode packet-only --max-prs 2"
make mike-cycle ARGS="--cycle-mode review --max-prs 1 --timeout-s 600"
make mike-tmux-start
make mike-tmux-stop
make mike-launchd-plist ARGS="--output ~/Library/LaunchAgents/com.dharma.merge-master-mike.plist"
```

The default persistent posture is `dry-run`. It refreshes queue truth and writes
receipts without spending reviewer quota or touching GitHub. Promote a single
cycle to `packet-only` when Mike should prepare review packets and merge gates.
Promote to `review` only when Codex and Claude reviewer credentials are healthy
and the operator wants a real dual-review attempt.

When Claude credits or login are unavailable, do not fake a Claude receipt.
Use an explicit backup reviewer receipt and record the reason in the gate:

```bash
make pr-gate PR=397 ARGS="--allow-backup-reviewer --backup-reviewers backup_opus,backup_gemini,backup_hermes --backup-reviewer-reason 'Claude Code subscription credits unavailable'"
```

The backup lane preserves the dual-review rule as Codex plus one independent
strong reviewer. It only works when a named backup artifact such as
`backup_opus_review.md` and `backup_opus_review_receipt.json` exists in the
packet directory, the backup verdict is acceptable, and the reason for
replacing Claude is written. High-risk and critical PRs still require
`--human-approved`.

Mike's local nest lives under:

```text
~/.dharma/external_agents/merge_master_mike/
  nest/README.md
  nest/COMMANDS.md
  nest/delegation_lanes.json
  nest/status.json
  cycles/latest.json
  logs/wake_receipts.jsonl
  logs/action_log.jsonl
```

The nest is allowed to coordinate and recommend. It is allowed to merge only
through the conditional clean-gate path. It is still forbidden from approving,
pushing, editing source, marking human approval, bypassing branch protection, or
posting GitHub comments without explicit operator authorization.

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
      DIFF.patch
      PR_BODY.md
      changed_files.txt
      PROMPT_CODEX.md
      PROMPT_CLAUDE.md
      codex_review.md
      codex_review_receipt.json
      claude_review.md
      claude_review_receipt.json
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
- GitHub says the branch is not mergeable.
- Any manifest-required CI context is missing, failing, or pending.
- Non-required check failures and pending states remain visible warnings but do
  not acquire merge authority. `--allow-pending` remains accepted only as a
  deprecated compatibility flag; it never waives a required context.
- GitHub review decision is `CHANGES_REQUESTED`.
- Coherence Delta fields are missing or placeholders.
- Review threads are unresolved.
- A required reviewer output or receipt is missing or invalid.
- Claude is missing and `--allow-backup-reviewer` is absent.
- Claude is missing, backup fallback is enabled, and no named backup reviewer
  receipt is acceptable.
- Backup fallback is enabled without `--backup-reviewer-reason`.
  - Either reviewer timed out, failed to spawn, exited non-zero, or produced empty output.
  - Either reviewer has verdict `REQUEST_CHANGES` or `BLOCKED`.
- Either reviewer has verdict `NEEDS_HUMAN` and no `--human-approved` flag is present.
- Either reviewer has an unknown or malformed verdict.
- Risk is `HIGH` or `CRITICAL` and no `--human-approved` flag is present.

## Agent Contract

Codex and Claude read the same `REVIEW_PACKET.md` and answer from their own
fresh context. The generator of a change must not be the only evaluator of that
change. Each review must put findings first, cite concrete file evidence, and
state exact merge conditions. The first section must be:

```markdown
## Verdict
APPROVE
```

Allowed verdicts are `APPROVE`, `REQUEST_CHANGES`, `BLOCKED`, and
`NEEDS_HUMAN`. The gate rejects placeholder verdict lines such as
`APPROVE | REQUEST_CHANGES | BLOCKED | NEEDS_HUMAN`.

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
