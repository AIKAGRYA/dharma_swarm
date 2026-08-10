# Forge Lab v0.1 canonical checkout runbook

This runbook records the Packet A checkout decision for MeghaDharma. It is an
operational projection of `specs/FORGE_LAB_V0_1_0_SPEC.md`; the specification
remains authoritative if this runbook drifts.

The cross-host release and drift contract is defined in
[`RSI_LAB_SYNC.md`](RSI_LAB_SYNC.md). Use `rsi sync`; never copy an active
checkout or mutable state between hosts.

## Canonical roots

Use the stable logical paths below in commands, manifests, receipts, and
operator reports. Do not replace them with the timestamped physical target of
the `current` symlink.

| Purpose | Canonical path |
|---|---|
| Lab base | `/root/rsi-lab/current` |
| Source checkout | `/root/rsi-lab/current/repo` |
| Durable isolated state | `/root/rsi-lab/current/state` |
| Python environment | `/root/rsi-lab/current/.venv` |
| Supplemental Python dependencies | `/root/rsi-lab/current/pydeps` |

`/root/rsi-lab/current` is an atomic symlink to an immutable full-SHA release.
Its `state`, `.venv`, `pydeps`, and optional `secrets` entries are symlinks to
stable host-owned anchors outside the checkout. A code release switch therefore
does not move or copy any database, WAL, archive, credential, or provider key.

New Forge Lab v0.1 work, validation, installation, and campaign commands start
from `/root/rsi-lab/current/repo` and use the other roots in that table.

A normal offline validation shell is:

```bash
BASE=/root/rsi-lab/current
cd "$BASE/repo"
export DHARMA_HOME="$BASE/state/.dharma"
export PYTHONPATH="$BASE/repo:$BASE/pydeps${PYTHONPATH:+:$PYTHONPATH}"
"$BASE/.venv/bin/python" -m pytest -q tests/forge_lab_v1/test_manager_registration.py
```

This validation is repository-local. It does not register or onboard an agent,
connect to NATS, launch a campaign, or start a persistent process.

## `current-main` recovery boundary

`/root/rsi-lab/current-main/repo` is deprecated and recovery-only. It may be
used to inspect or preserve the historical branch, but it must not launch a new
campaign, install the v0.1 control surface, or become the manager registration
endpoint.

Remove the recovery worktree only after all three conditions are true:

1. its branch and any required commits are preserved;
2. its worktree is clean; and
3. no campaign is active.

Do not repoint `/root/rsi-lab/current` through `current-main`. The
`current-main` state, environment, and dependency links already resolve back
through `/root/rsi-lab/current`; repointing the anchor through that directory
would create a path loop.

## Manager registration boundary

The canonical registration card is
`examples/agents/codex_rsi_lab_manager.registration.json`, and its endpoint is
`ssh://meghadharma/root/rsi-lab/current/repo`. The optional, explicitly invoked
registration wrapper is `scripts/agents/register_codex_rsi_lab_manager.sh`; its
default repo, state, environment, and dependency paths are the canonical roots
above.

The `codex_rsi_lab_manager` identity remains an
`external_worker_evidence_only` seat. Registration does not grant production,
NATS, daemon, key, protected-branch, or positive-capability-claim authority.
Path validation must not invoke the wrapper, onboarding, NATS, or any runtime
service.

## Minimum governed campaign lifecycle

First verify that `rsi version` reports
`implementation_status: minimum_safe_blocked_controller`. The minimum lifecycle
is intentionally closure-first: it can plan, instantiate, preflight, receipt,
query, stop, and reconcile, but it has no governed scientific executor. It
therefore cannot spend provider tokens or count a scientific attempt.

Plan the pinned n30-to-1000 definition without a provider call:

```bash
rsi campaign plan --profile forge-lab-n30-to-1000-v1 --json
```

`plan` stores a content-addressed manifest below the canonical state root. The
manifest records null cumulative token, USD, request, deadline, and host caps
when the signed operator envelope did not provide exact values. Null is
unpowered; neither a prompt nor a budget environment variable fills it.

Run accepts only the printed digest:

```bash
rsi campaign run --manifest sha256:DIGEST \
  --identity-receipt /canonical/evidence/sync-status.json \
  --provider-receipt /canonical/evidence/provider-attestation.json \
  --operator-envelope /canonical/evidence/operator-envelope.json \
  --host meghadharma --json
```

If any gate is missing—or while the governed scientific executor remains
unimplemented—`run` exits nonzero after committing one
`forge_lab.blocked_receipt.v1`, closes the lifecycle to `FAILED`, and releases
its fenced lease. Repeating the same request returns the same receipt. It does
not create scratch space or dispatch a provider request.

`rsi provider selftest --live` is also disabled in this release. Exact route
evidence must eventually be produced by a manifest-bound, signed probe grant
through the same fenced broker used for campaign work; a configuration-only
row or an older unsigned callable row cannot open admission.

Read committed state independently of process output:

```bash
rsi campaign list --json
rsi campaign status forge-lab-n30-to-1000-v1 --json
rsi campaign progress forge-lab-n30-to-1000-v1 --json
rsi campaign events forge-lab-n30-to-1000-v1 --json
rsi campaign stop forge-lab-n30-to-1000-v1 --json
rsi reconcile --json
```

`reconcile` is read-only unless `--apply` is explicit. Apply additionally
requires the exact report file/digest and a request ID, and can only create
enumerated operational directories. No reconciliation or cleanup command can
mint provider, evaluation, lineage, usage, or scientific evidence, and the
minimum cleanup planner performs no deletion.

The external watchdog prototype runs in a separate credential-free process and
is bound to campaign, manifest digest, deadline, and fencing token. Its file
gate is not spend authority and does not satisfy lifecycle acceptance until a
governed broker transactionally observes the same fuse. A stale watchdog
cannot mutate a newer fence.

The legacy `rsi newrun --execute` and
`python -m dharma_swarm.forge_lab.cli run` launch paths are retired and return
`GOVERNED_CAMPAIGN_REQUIRED`.

## Paired harness and unattended schedule candidate

The world-class harness amendment is backward compatible at its scientific
boundary: `legacy_v0` remains readable, while new scientific work must use
`paired_frozen_v1`. A paired campaign freezes, before the first provider call:

1. disjoint logical `train`, `explore`, `confirm`, and `holdout` task IDs and
   their content/provenance hashes;
2. baseline candidate and executed-phenotype identities;
3. evaluator/source identity and repeat seeds; and
4. hard token/USD ceilings covering mutation, baseline evaluation, candidate
   evaluation, confirmation, and the one-use holdout.

Baseline and challenger run on the same task/repeat cells with counterbalanced
arm order. Selection sees only complete, budget-valid EXPLORE pairs. A single
challenger is frozen before CONFIRM, and HOLDOUT is read only after that freeze.
Any persistent champion is research-only, atomically CAS-updated, and cannot
authorize promotion or a positive-lift claim.

PR-suite setup, Git operations, patched repositories, and tests require the
digest-bound execution profile named by `FORGE_PR_SUITE_EXECUTION_PROFILE`.
Production has no host-process fallback. The profile requires a non-root
container user, image digest, no network, read-only root filesystem, all
capabilities dropped, no-new-privileges, and explicit CPU, memory, PID, file,
output, and wall limits. Missing runtime, pinned image, or profile is a graded
failure—not permission to execute locally.

The repository contains source-only systemd candidates:

```text
scripts/ops/systemd/rsi-lab-run.service
scripts/ops/systemd/rsi-lab-run.timer
```

They intentionally have no `[Install]` section and must not be copied, started,
or enabled merely because tests pass. The foreground entrypoint is
`rsi run --unattended`; it reads only
`$RSI_LAB_STATE/.dharma/forge_lab/schedule/active.json`, obtains a global
single-flight lock, checks memory/swap/load, and writes a private attempt
receipt for every success or refusal. It accepts no command-line evidence path.

This amendment does **not** make the candidate a recurring paid runner. The
controller still appends `GOVERNED_EXECUTOR_NOT_IMPLEMENTED`, and a stored
campaign name/request is single-use rather than a cadence-safe campaign
instance. `rsi campaign prepare` now opens the fenced, short-lived provider
probe challenge needed to create a nonce-bound attestation, and paired planning
accepts all-or-nothing proposed ceilings, but neither surface grants spend
authority or opens dispatch. A recurring instance identity, transactional
request accounting, and an implemented scientific-executor handoff are release
blockers before the timer can be considered cron-ready.

Unattended activation remains forbidden until all of these are true at the
same immutable release:

- a root-owned, private, exact-ceiling operator envelope is valid;
- the paired manifest contains explicit cumulative token, USD, request,
  deadline, and host ceilings, with a matching signed envelope;
- three-host code identity and a fresh manifest-bound provider attestation are
  valid, including at least two independent physical transports;
- a governed provider-probe broker consumes the active fenced challenge within
  its TTL and signs the resulting receipt with a deployed trust root;
- the digest-pinned evaluator image/profile passes a supervised isolation
  canary;
- available memory and swap exceed the configured floors;
- the `rsi-lab` service account has only the narrow traversal/state access it
  needs; and
- a supervised paired canary closes cleanly with no residual process,
  container, scratch checkout, reservation, or open receipt.

Until those facts are simultaneously green, the correct scheduled state is
absent/inert and `rsi run --unattended` must fail closed.
