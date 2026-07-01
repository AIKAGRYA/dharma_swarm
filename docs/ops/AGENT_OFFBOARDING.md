# Agent Offboarding

`make offboard` is the lightweight closeout door for an agent finishing a
substantial work session. It complements `make onboard`.

- `make onboard`: where am I, what is live, what should I read?
- `make offboard`: what did I do, what did I verify, what remains dirty, and
  where should the next agent continue?

Version: `0.0.0.1`

## Default Use

Run this after a scoped task, after narrow verification, and before leaving the
thread:

```bash
make offboard ARGS='--task "context packet v1.1 upgrade" \
  --packet-id ctx.command-plane-governance \
  --owner docs/context_engineering/PACKET_SCHEMA.md \
  --verification "pytest tests/test_context_packet_router.py: 12 passed" \
  --artifact docs/context_engineering/CONTEXT_PACKET_INDEX.json \
  --claim-not-made "repo-wide worktree is clean" \
  --risk "unrelated dirty worktree remains" \
  --next-step "commit or PR only the scoped packet-system files"'
```

By default the command writes:

- `~/.dharma/ops/offboard_receipt.json`
- `~/.dharma/ops/offboard_receipt.md`

These are projections for local/fleet agents. They are not source of truth.

## Durable Repo Receipt

For a big project handoff that should be discoverable from a clone or audit
branch, add `--repo-receipt`:

```bash
make offboard ARGS='--task "large project closeout" --repo-receipt'
```

That also writes a timestamped Markdown and JSON pair under:

```text
reports/handoffs/offboard/
```

Use repo receipts sparingly. Do not create one for every tiny edit.

## What It Records

The v0.0.0.1 receipt records:

- UTC timestamp;
- repo root;
- branch, upstream, head SHA, ahead/behind counts;
- recent commits;
- dirty worktree counts and a capped dirty-file sample;
- task and context packet id;
- owners consulted;
- verification run;
- artifacts produced;
- claims intentionally not made;
- risks or blockers;
- next steps.

It does not run tests, decide merge readiness, or override owner files.

## Relationship To Existing Closeout Gates

`make offboard` is a handoff receipt. It is not the full governance closeout.

Before PR or merge handoff, still run:

```bash
make agent-build-closeout
```

If that heavier target cannot run, record the exact command and failure reason
in `make offboard --risk ... --claim-not-made ...`.

## Audit Discovery

Audit agents should search for:

- `AGENT_OFFBOARD_RECEIPT`
- `OFFBOARD_V0_0_0_1`
- `CONTEXT_PACKET_CLOSEOUT`

Audit agents should also inspect:

- `docs/context_engineering/README.md`
- `docs/context_engineering/CONTEXT_PACKET_INDEX.json`
- `reports/handoffs/`
- latest `~/.dharma/ops/offboard_receipt.*` when local machine state is
  available.
