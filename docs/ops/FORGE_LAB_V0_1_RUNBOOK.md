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

## Bounded operator-control slice

The current development release implements finite, receipt-backed inspection,
a hermetic control-plane pilot, and one narrowly bounded unattended EXPLORE
oneshot. It does **not** implement an unattended `explore-open` campaign,
promotion, backup mutation, a general persistent supervisor, or a scientific
recursive-improvement claim. Those broader commands remain nonzero and fail
closed.

Start with the truthful doctor. A nonzero exit is expected until immutable
source, anchored state, a fresh two-provider live receipt, the isolated Docker
grader, at least one eligible task in the anchored taskbed, the managed
provider cron, and retirement of legacy controls all pass:

```bash
rsi doctor --json
rsi reconcile --json
rsi worker list --json
rsi alerts list --json
rsi archive inspect --json
```

`reconcile`, worker, alert, archive, campaign list/status/progress/events, and
doctor are read-only. `reconcile --apply` and `campaign events --follow` are
explicit refusals in this slice.

Provider configuration inspection never claims callability. The only passing
selftest is a live receipt with at least one callable route; confirm admission
requires two distinct provider entitlements, not two model-family labels. A
bounded operator refresh is:

```bash
export RSI_LAB_STAGED_MODELS='model-id-on-provider-a,model-id-on-provider-b'
rsi provider selftest \
  --profile staged --live --require-independent-routes 2 \
  --timeout-s 20 --max-probes 4 --min-refresh-interval-s 3600 --json
```

Live selftests write append-only `rsi_lab.provider_selftest.v2` receipts with a
collision-proof ID. Each receipt binds the immutable source commit/package,
selected profile and model IDs, route requirement, timeout, provider-call cap,
and alias policy under a content digest. Refresh cooldown reuse requires that
exact policy digest and a valid receipt digest. Zhipu's immediately succeeding
GLM minor alias is accepted only after a second bounded probe of the declared
served ID returns callable content; arbitrary family substitutions still fail.

Do not place credentials in `RSI_LAB_STAGED_MODELS` or any command argument.
The scheduled form and legacy-cron retirement are documented in
[`RSI_LAB_SYNC.md`](RSI_LAB_SYNC.md#retire-the-unversioned-provider-cron).

### Five-attempt offline pilot

The only runnable campaign profile is `pilot-five-offline`. Planning writes a
content-addressed manifest. Running it executes exactly five deterministic,
paired seed/child fixture checks with zero provider calls, tokens, and dollars:

```bash
rsi campaign plan --profile pilot-five-offline --json
rsi campaign run \
  --manifest sha256:<digest-from-plan> \
  --request-id operator-YYYYMMDD-offline-pilot --json
rsi campaign list --json
rsi campaign status <campaign-id> --json
rsi campaign progress <campaign-id> --json
rsi campaign events <campaign-id> --json
```

Every attempt and lifecycle transition is durable. The closeout modality is
`ControlPlaneTestOnly`, the scientific verdict is `inconclusive`, and
`positive_rsi_claim` is always false. Repeating `campaign run` with the same
manifest and request ID returns the existing closeout; changing the request ID
creates a separately receipted pilot. Verify five independent invocations with:

```bash
pytest -q tests/forge_lab_v1/test_campaign_control.py \
  -k five_independent_campaign_invocations
```

Events carry `previous_event_digest`/`event_digest`; attempts carry
`previous_attempt_digest`/`attempt_digest`; the exclusive-create closeout seals
both ordered digest lists. On interruption, `campaign run` validates the exact
fixed schedule and permits at most one attempt receipt written just before its
missing event, then resumes without overwriting or duplicating evidence. A
truncated log, gap, extra receipt, bad link, or digest mismatch fails closed and
is shown as `CORRUPT` by read-only status.

### Grading and confirm boundary

Production EXPLORE refuses the host PR-suite pytest grader. SWE-bench uses the
official harness, but the Forge adapter recreates each stopped candidate
container with Docker networking disabled, an empty host environment,
capabilities dropped, no-new-privileges, a read-only root, bounded writable
testbed/tmp space, and exact PID/CPU/memory limits. The inspected Docker config
emits an `rsi_lab.grader_isolation_proof.v1`; any missing control blocks the
grade from comparable evidence. Infrastructure, generation, and budget
non-observations are separate classes. Only an executed comparable official
evaluator returning false can mint `MeasuredNegative`.

Confirm candidate generation additionally requires an explicit, fresh
provider-selftest receipt attesting two distinct live provider entitlements:

```bash
python -m dharma_swarm.forge_lab.confirm_swebench \
  --instance <swebench-verified-instance> \
  --solver-model <slot-resolvable-model> \
  --provider-receipt <provider-selftest-receipt>
```

The availability receipt grants no judge authority. A confirm control run
(`--control`) uses gold/empty patches and needs no model provider.

### Bounded unattended EXPLORE oneshot

Do not schedule `python -m dharma_swarm.forge_lab.cli run` or `rsi newrun
--execute` directly. Those interactive entry points enforce shadow mode and,
for `newrun`, immutable source, but they do not own a host lock, HALT check,
fresh doctor boundary, daily/monthly ledger, external watchdog, or systemd
receipt chain. They are therefore **not unattended-ready**.

The production-only `rsi-unattended-explore` wrapper admits one fixed run only
when all of the following are simultaneously true:

- `current` resolves to a clean full-SHA release from the canonical AIKAGRYA
  remote and its release manifest binds that SHA;
- `RSI_LAB_STATE`/`DHARMA_HOME` resolve to the explicit host state root;
- the state-anchored `forge_v1/taskbed.db` is schema-valid and exposes at least
  one eligible EXPLORE task without mutating the ledger during doctor;
- the HALT file is absent and the nonblocking host lock is available;
- `rsi doctor` is ready, including retirement of legacy provider controls;
- a valid live provider receipt, no older than one hour, attests two distinct
  callable provider entitlements for this exact release; and
- the official SWE-bench Docker daemon is reachable. Candidate grading still
  must emit a complete `rsi_lab.grader_isolation_proof.v1` to become comparable.

The child shape is permanently `generations=1`, `children=1`, `tasks=1`. It
uses only `freeform_single`, disables continuation calls, reserves four logical
provider-call slots before launch, hard-caps each grade at 8,000 tokens and
$0.25 accounting cost, and caps recorded experiment generation at 24,000
tokens. The parent polls the HALT latch at most every two seconds and terminates
the child process group when it appears, recording
`InconclusiveOperatorHalt`. The parent also applies a 2,700-second subprocess
timeout; systemd adds a second 2,800-second fuse. Scratch code is a standalone
exact-commit clone under state, so execution never writes the immutable release
Git dir.

Reservations are conservative: $1/four logical call slots per run,
$3/12 slots per UTC day, and $30/120 slots per UTC month. They are never
refunded after a crash. These dollars are **not vendor billing telemetry**, and
transport-level retries are not separately metered; absence of authoritative
billing remains an explicit limitation. The budget ledger and run receipts are
strict, fsync-backed hash chains. A truncated row, bad link, changed digest,
fifth logical dispatch, stale receipt, dirty release, Docker failure, or HALT
file refuses the run before additional spend.

Run one operator-supervised smoke only after `rsi doctor --json` is green:

```bash
/root/rsi-lab/bin/rsi-unattended-explore --timeout-seconds 2700
```

The result modality is always `EXPLORE_ONLY`; `positive_rsi_claim` is always
false. `inconclusive_low_power` and a genuinely executed comparable
`measured_negative` are successful service closeouts. Infrastructure,
generation, budget, timeout, or malformed-receipt outcomes fail the service so
operations can alert. The versioned oneshot and timer units are documented in
[`RSI_LAB_SYNC.md`](RSI_LAB_SYNC.md#install-the-bounded-systemd-oneshot).

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
