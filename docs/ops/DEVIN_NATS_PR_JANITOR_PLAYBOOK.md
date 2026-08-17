# Devin NATS PR Janitor Playbook

Status: active coordination contract.

Purpose: make Devin a live, evidence-only member of the Merge Master Mike PR
team. The goal is coordinated PR synthesis and conditional merge execution:
use AGNI NATS for live intent/dependency checks, GitHub for PR truth, local
receipts for audit, and Mike for final merge action only when the deterministic
gate is clean.

## Identity

- Agent UID: `devin-roaming-2987d222`
- Callsign: `devin`
- Model identity: `cognition/devin`
- Authority: `external_worker_evidence_only`
- Local legacy adapter: `dharma_swarm/a2a/executors/devin_executor.py`
- Fleet manifest: `dharma_swarm/persistent_fleet_manifest.json`
- Git rendezvous fallback: `inter_agent/devin/{inbound,outbound,shared}/`

Devin may inspect, synthesize, packetize, review, and recommend. Devin may not
merge, approve, push, mark human approval, resolve review threads, mutate
protected source, or bypass governance.

## Secrets

Use secret storage. Do not paste credentials in PR comments, chat transcripts,
docs, or committed files.

Required AGNI NATS secret names for the GitHub-hosted Mike backlog workflow:

```text
MERGE_MASTER_MIKE_NATS_URL=wss://157.245.193.15:8443
MERGE_MASTER_MIKE_NATS_USER=merge_master_mike
MERGE_MASTER_MIKE_NATS_PW=<stored secret>
```

Compatibility fallback secret names for Devin-only lanes:

```text
DEVIN_NATS_URL=wss://157.245.193.15:8443
DEVIN_NATS_USER=devin
DEVIN_NATS_PW=<stored secret>
```

Optional TLS trust settings for GitHub-hosted runners:

```text
MERGE_MASTER_MIKE_NATS_CA_PEM=<PEM for the CA that signed the AGNI NATS certificate>
MERGE_MASTER_MIKE_NATS_TLS_HOSTNAME=<certificate DNS name, only if different from URL host>
```

Use `MERGE_MASTER_MIKE_NATS_CA_PEM` when AGNI presents a private or self-signed
certificate. The workflow also accepts `DEVIN_NATS_CA_PEM` as a fallback. Do not
disable certificate verification for the Mike lane; either install a public TLS
certificate on AGNI or provide the CA PEM as a repo secret.

Installed surfaces:

- Devin Cloud org secrets: `DEVIN_NATS_URL`, `DEVIN_NATS_USER`, `DEVIN_NATS_PW`
- GitHub Actions repo secrets: `MERGE_MASTER_MIKE_NATS_URL`,
  `MERGE_MASTER_MIKE_NATS_USER`, `MERGE_MASTER_MIKE_NATS_PW`, and
  `DEVIN_NATS_CA_PEM` or `MERGE_MASTER_MIKE_NATS_CA_PEM` when AGNI uses a
  private CA
- AGNI root credential file: `/root/.dharma/nats/devin_cred.txt`
- AGNI Mike credential file: `/root/.dharma/nats/merge_master_mike_cred.txt`

## AGNI NATS Contract

AGNI is the cloud coordination center. For Devin PR work, use AGNI subjects:

```text
dharma.a2a.fleet
dharma.a2a.github_copilot
dharma.a2a.claude
dharma.a2a.devin
dharma.a2a.devin.>
dharma.a2a.codex
dharma.a2a.hermes
dharma.a2a.perplexity
dharma.a2a.merge_master_mike
dharma.a2a.merge_master_mike.>
dharma.a2a.fable_5_cursor
dharma.a2a.fable_5_cursor.>
```

`dharma.a2a.fable_5_cursor` is the inbound subject for the Fable 5 hub
coordinator inside the Cursor IDE (`@FABLE_5_IN_CURSOR`, registration:
`examples/agents/fable_5_cursor.registration.json`). It coordinates lanes and
pre-reviews; like Devin, it never merges, approves, or pushes.

The local filesystem mirror may use `dharma.agent.<uid>.inbox`. Do not treat
that as the AGNI subject contract. Filesystem and git rendezvous paths are audit
and fallback surfaces, not the primary cloud coordination lane.

## Session Protocol

At the start of a PR janitor session:

1. Run `make onboard`.
2. Confirm GitHub auth with `gh auth status`.
3. Confirm queue truth with `make pr-queue`.
4. Connect to AGNI NATS using the Devin secrets.
5. Publish a session announcement to `dharma.a2a.fleet`.
6. Publish a direct coordination note to `dharma.a2a.merge_master_mike`.
7. Write a receipt or markdown summary under the packet/run directory.

The announcement must include:

```json
{
  "kind": "pr_janitor_session_start",
  "from": "devin",
  "to": "fleet",
  "authority": "external_worker_evidence_only",
  "repo": "AIKAGRYA/dharma_swarm",
  "goal": "collaborative PR queue synthesis; Mike may merge only after clean gate"
}
```

## PR Triage Loop

For each selected PR:

1. Pull live GitHub facts with `gh pr view <n> --json ...`.
2. Create or inspect the Mike packet: `make pr-packet PR=<n>`.
3. Ask the fleet for context before recommending merge order:
   - originator intent if known;
   - dependency or supersession relationship to other PRs;
   - runtime surfaces touched;
   - governance blockers;
   - whether the PR should merge, rebase, close, or wait.
4. Run deterministic gate: `make pr-gate PR=<n>`.
5. If assigned as a reviewer, write `devin_review.md` plus a receipt in the
   packet directory. Do not impersonate Codex or Claude receipts.
6. Publish a PR-specific note to NATS:

```text
dharma.a2a.merge_master_mike
```

7. Summarize: `GO`, `NO_GO`, `WAIT`, `CLOSE_DUPLICATE`, `REBASE_FIRST`, or
   `NEEDS_OPERATOR`.

## Merge Policy

Devin never merges.

Mike may merge only under `merge_mode=auto-when-clean` and only when the merge
gate returns `MERGE_CANDIDATE`.

The clean merge gate requires:

- PR is not draft;
- PR is mergeable;
- required checks are passing;
- no unresolved review threads;
- Coherence Delta fields are substantive;
- required reviewer receipts are present, for example
  `copilot_review_receipt.json`, `claude_review_receipt.json`,
  `devin_review_receipt.json`;
- high-risk and critical PRs have explicit `--human-approved`.

The operator still holds final authority for:

- changing Mike's merge policy;
- GitHub approvals;
- public comments unless explicitly delegated;
- money;
- credentials;
- protected branch exceptions;
- governance exceptions.

High-risk and critical PRs require explicit human approval even when all machine
gates are green.

## GitHub Actions Coordination

The GitHub-hosted Mike adapter is:

```text
.github/workflows/codex-mention-router.yml
```

Call it from a PR:

```text
@merge-master-mike
@merge_master_mike
@mix-master-mike
@mix_master_mike
@MERGE_MASTER_MIKE
@mike
@terminal-review
```

Plain mentions are packet/gate/comment only. The workflow runs from
default-branch code, creates a deterministic packet, runs the merge gate, and
posts/updates the Mike comment. It does not use PR-head code.

Conditional merge requires an explicit command:

```text
@mix_master_mike merge when clean
```

That command uses `gh pr merge --auto --squash --delete-branch` only after the
deterministic gate returns `MERGE_CANDIDATE`; blocked gates write a skipped
merge receipt instead of merging.

The backlog-wide GitHub Actions entrypoint is:

```text
.github/workflows/merge-master-mike-backlog.yml
```

Use **Actions -> merge-master-mike-backlog -> Run workflow**. Start with:

```text
mode=packet-only
max_prs=5
limit=100
statuses=GITHUB_GREEN_NEEDS_PACKET,NEEDS_AGENT_REVIEW
required_reviewers=copilot,claude,devin
merge_mode=off
merge_method=squash
nats_required=true
```

Use `merge_mode=auto-when-clean` only after the run is expected to contain the
required reviewer receipts. In that mode, Mike uses `gh pr merge --auto
--squash --delete-branch` by default and writes `MIKE_MERGE_RECEIPT.json` for
every processed PR. Blocked PRs get a skipped merge receipt, not a merge.

This workflow runs default-branch code, writes Mike queue/fanout receipts as an
Actions artifact, and publishes a PR janitor A2A session to:

```text
dharma.a2a.fleet
dharma.a2a.merge_master_mike
dharma.a2a.github_copilot
dharma.a2a.claude
dharma.a2a.devin
dharma.a2a.codex
dharma.a2a.hermes
dharma.a2a.perplexity
```

The NATS receipt is fail-closed. If any `MERGE_MASTER_MIKE_NATS_*` secret is
present, all three primary Mike secrets are required. If the Mike family is
absent, the workflow falls back to the legacy `DEVIN_NATS_URL`,
`DEVIN_NATS_USER`, and `DEVIN_NATS_PW` names. Missing required values record
`NATS_SECRETS_MISSING` and exit non-zero when `nats_required=true`. If
JetStream publish is not ack-verified, the run records `NATS_PUBLISH_FAILED` or
`NATS_ACK_FAILED`; do not claim live fleet collaboration from that run. If the
failure is `CERTIFICATE_VERIFY_FAILED`, add `MERGE_MASTER_MIKE_NATS_CA_PEM` or
`DEVIN_NATS_CA_PEM` as a GitHub Actions repo secret, or move AGNI behind a
publicly trusted TLS certificate, then rerun the backlog workflow.

## Fallbacks

If AGNI NATS is unavailable:

1. Report `NATS_BLOCKED` with exact connection error.
2. Use GitHub comments and local packet receipts only.
3. Do not claim live inter-agent consensus.
4. Do not merge based on fallback-only coordination unless the operator
   explicitly approves.

If Devin Cloud is unavailable:

1. Keep Mike dry-run or packet-only.
2. Use Codex plus an explicitly named backup reviewer only if the gate records
   `--allow-backup-reviewer` and the reason.
3. Keep the PR in `NEEDS_AGENT_REVIEW` or `NEEDS_OPERATOR` when no independent
   reviewer receipt exists.

## Success Receipt

A good Devin/Mike PR janitor pass produces:

- NATS session-start message to `dharma.a2a.fleet`;
- direct coordination message to `dharma.a2a.merge_master_mike`;
- packet path for each PR;
- gate verdict for each PR;
- required reviewer receipts for the configured quorum;
- `MIKE_MERGE_RECEIPT.json` for every merge-authorized processed PR;
- Devin review or blocker receipt when Devin reviewed;
- one queue-level summary with merge order and close/rebase recommendations;
- no hidden approval, source push, unconditional merge, or governance bypass.
