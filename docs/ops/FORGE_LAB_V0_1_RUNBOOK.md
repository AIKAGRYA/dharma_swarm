# Forge Lab v0.1 canonical checkout runbook

This runbook records the Packet A checkout decision for MeghaDharma. It is an
operational projection of `specs/FORGE_LAB_V0_1_0_SPEC.md`; the specification
remains authoritative if this runbook drifts.

The cross-host release and drift contract is defined in
[`RSI_LAB_SYNC.md`](RSI_LAB_SYNC.md). Use `rsi sync`; never copy an active
checkout or mutable state between hosts.

## START_HERE

First verify the release from the Mac operator host:

```bash
rsi sync status --json
```

Then run the operational projection on authoritative Meghadharma from the
activated immutable release. `daily status` is the single read-only projection
for doctor readiness, reconciliation, the active model-role profile, taskpack
custody, the installed systemd bytes/state, and the most recent unattended
closeout:

```bash
rsi daily status --json
```

A healthy projection reports `ready_for_next_run: true` and
`last_cycle_healthy: true`. Before the first supervised closeout,
`awaiting_first_run: true` explains why overall `ok` remains false even when
the pre-run authorities are green. The latest closeout counts only while its
exact child-result and log preimages still validate under the recorded digests.

A nonzero status is a fail-closed finding, not permission to bypass a gate.
Converge code only through the official `rsi sync` commands in
[`RSI_LAB_SYNC.md`](RSI_LAB_SYNC.md#start_here); never use `rsync`, `scp` of a
working tree, or a mutable checkout.

### Credential handoff (secret never in argv)

Inspect and plan one provider at a time, then copy the returned plan digest into
the apply command:

```bash
rsi provider credential status --provider zhipu --json
rsi provider credential plan --provider zhipu --json
rsi provider credential apply \
  --provider zhipu \
  --plan-digest sha256:<64-hex-plan-digest> \
  --request-id operator-YYYYMMDD-zhipu-key \
  --json
```

The apply command prompts with hidden input. There is deliberately no
credential-value flag or positional value. For a secret-manager integration,
add `--stdin` and pipe exactly one secret line; never put a literal secret in
the command, shell history, logs, JSON, or a request ID. Repeat status/plan/apply
for any other required provider, such as `ollama`. The value-free plan, status,
and receipt record only credential names and presence; an unknown provider
returns `IMPLEMENTATION_REQUIRED` rather than creating an ad hoc route or key
store.

If credential apply reports `RECEIPT_WRITE_FAILED` or a later replay reports
`OUTCOME_UNKNOWN`, inspect credential status and the durable intent. Reusing the
same request ID will not reapply a value; use a new request ID only for a
deliberate explicit replacement.

### Activate exact model routes

List the source-owned route catalog and current profile first:

```bash
rsi provider models list --json
rsi provider models status --json
```

The following currently catalogued example binds all three roles while staging
two independent provider entitlements. Plan and apply must repeat the exact six
role flags:

```bash
rsi provider models plan \
  --mutator-provider zhipu --mutator-model glm-5.2 \
  --solver-provider ollama --solver-model deepseek-v4-pro:cloud \
  --verifier-provider zhipu --verifier-model glm-5.2 \
  --json

rsi provider models apply \
  --mutator-provider zhipu --mutator-model glm-5.2 \
  --solver-provider ollama --solver-model deepseek-v4-pro:cloud \
  --verifier-provider zhipu --verifier-model glm-5.2 \
  --plan-digest sha256:<64-hex-plan-digest> \
  --request-id operator-YYYYMMDD-model-profile \
  --json

rsi provider models status --json
```

Omit `--expected-current-digest` only for the first activation, when status
reports no current profile. Every replacement must add
`--expected-current-digest sha256:<current-profile-digest>` to both plan and
apply. Rollback is also compare-and-swap protected; without an explicit target
it selects the immediate predecessor, while a target must be an ancestor:

```bash
rsi provider models rollback \
  --request-id operator-YYYYMMDD-model-rollback \
  --expected-current-digest sha256:<current-profile-digest> \
  --target-profile-digest sha256:<ancestor-profile-digest> \
  --json
```

Only choose rows whose catalog entry says `runtime_selectable: true`. An unknown
provider, an unknown exact route, or a provider/model ID that is ambiguous in
the current runtime is not onboarded by configuration: planning returns
`implementation_required` or `source_change_required`, and the missing
provider-qualified execution path must be implemented and reviewed first.
Activation selects roles only. It does not load credentials, call a provider,
edit source, change weights, attest availability or quality, or grant promotion
authority.

### Stage and prove live callability

After credential handoff and model activation, run the same bounded staged
policy used by the hourly refresher:

```bash
rsi provider selftest \
  --profile staged --live --require-independent-routes 2 \
  --timeout-s 20 --max-probes 6 --min-refresh-interval-s 3000 \
  --json
```

The staged profile uses the active model-role profile when there is no explicit
process-local `RSI_LAB_STAGED_MODELS` override. A configuration-only selftest
(without `--live`) is intentionally non-ready. A live receipt proves bounded
callability under its exact policy; it does not prove model quality or confer
judge/promotion authority.

### Replenish the taskbed through a sealed taskpack

`--manifest` is an actual newline-terminated `.jsonl` file path, while
`--manifest-digest` is the SHA-256 of those exact bytes. Use the same path,
digest, model cutoff, and mode for plan and apply:

```bash
rsi taskpack status --json
rsi taskpack plan \
  --manifest /root/rsi-lab/state/intake/<sealed-taskpack>.jsonl \
  --manifest-digest sha256:<64-hex-manifest-digest> \
  --model-cutoff <ISO-8601-model-cutoff> \
  --mode search_only_public_swebench \
  --json

rsi taskpack apply \
  --manifest /root/rsi-lab/state/intake/<sealed-taskpack>.jsonl \
  --manifest-digest sha256:<64-hex-manifest-digest> \
  --model-cutoff <ISO-8601-model-cutoff> \
  --mode search_only_public_swebench \
  --plan-digest sha256:<64-hex-plan-digest> \
  --request-id operator-YYYYMMDD-taskpack \
  --timeout-seconds 90 \
  --json

rsi taskpack status --json
```

`search_only_public_swebench` is the admitted daily EXPLORE corpus mode. It
checks a strict official-SWE-bench-shaped row contract, but it does not
cryptographically prove membership against a pinned official dataset seal.
Public pretraining contamination therefore remains possible. Its custody is
always `EXPLORE_ONLY`, `promotion_eligible: false`, and
`confirm_eligible: false`; it cannot support a confirm or improvement claim.
`governed_fresh` fails with `MODEL_CUTOFF_AUTHORITY_REQUIRED` until every active
model role has authoritative cutoff evidence and the requested cutoff is no
earlier than the minimum of those authorities. An operator-supplied date alone
is not freshness authority.

### Reconcile a stale active-campaign projection

Broad status remains read-only. The only currently actionable finding is
`ACTIVE_CAMPAIGN_MISSING_RUN`; all other findings refuse mutation. Use the
campaign ID reported by status and preserve the same ID across plan/apply:

```bash
rsi reconcile --json
rsi reconcile --plan --campaign <campaign-id> --json
rsi reconcile --apply \
  --campaign <campaign-id> \
  --plan-digest sha256:<64-hex-plan-digest> \
  --request-id operator-YYYYMMDD-reconcile \
  --json
rsi reconcile --json
```

Apply revalidates the missing-run condition, source, HALT state, locks, and
active-process evidence. It quarantines the stale projection without deleting
history and writes an immutable receipt. If an interrupted apply has an unknown
outcome, retry the exact same apply with the same plan digest and request ID;
there is no generic `rsi recover` command.

### HALT, stop, recover, and start

There are no top-level `rsi halt`, `start`, `stop`, or `recover` commands.
Emergency control is the host latch plus systemd. Latch first so the running
parent can record `InconclusiveOperatorHalt`, then stop future scheduling:

```bash
install -o root -g root -m 0600 /dev/null \
  /root/rsi-lab/state/.dharma/forge_lab/HALT
systemctl stop rsi-lab-explore.timer
systemctl status rsi-lab-explore.service --no-pager
rsi daily status --json
```

If the oneshot does not terminate through its HALT poll, an operator may stop
the current service explicitly:

```bash
systemctl stop rsi-lab-explore.service
```

Before recovery, inspect receipts, alerts, the budget chain, Docker, doctor,
and reconciliation. Repair only through the specific plan/apply or rollback
surface that owns the finding:

```bash
rsi doctor --json
rsi reconcile --json
rsi alerts list --json
journalctl -u rsi-lab-explore.service --since '36 hours ago' --no-pager
rsi daily status --json
```

Only after those checks are understood and repaired, remove the latch and
resume the already-installed timer:

```bash
unlink /root/rsi-lab/state/.dharma/forge_lab/HALT
systemctl start rsi-lab-explore.timer
systemctl status rsi-lab-explore.timer --no-pager
rsi daily status --json
```

Run `/root/rsi-lab/bin/rsi-unattended-explore --timeout-seconds 2700` only as a
supervised proof. Install, verify, enable, and start the systemd units manually
only after that proof succeeds; activation/sync never installs or enables them.
The timer then admits one run daily at `03:35 UTC` with at most `25m` randomized
delay. The independent provider refresh cron runs hourly at minute `:17`.

### Budget, artifacts, and claim boundary

Each fixed `1 x 1 x 1` run reserves `$1.25` and five logical provider-call slots
before launch. The hard reservation ceilings are `$3`/12 slots per UTC day and
`$40`/120 slots per UTC month; reservations are not refunded after a crash.
These are conservative accounting reservations, not authoritative vendor
billing telemetry.

On Meghadharma, inspect the host-owned evidence under:

```text
/root/.dharma/provider_credential_receipts/
/root/rsi-lab/state/.dharma/forge_lab/provider_selftests/
/root/rsi-lab/state/.dharma/forge_lab/model_onboarding/
/root/rsi-lab/state/.dharma/forge_lab/taskpack_actions/
/root/rsi-lab/state/.dharma/forge_lab/reconciliation/
/root/rsi-lab/state/.dharma/forge_lab/unattended_explore/budget_ledger.jsonl
/root/rsi-lab/state/.dharma/forge_lab/unattended_explore/receipts.jsonl
/root/rsi-lab/state/.dharma/forge_lab/unattended_explore/runs/
```

Every unattended result remains `EXPLORE_ONLY` and
`positive_rsi_claim: false`. A successful service closeout is evidence that a
bounded experiment ran and closed under the recorded controls; it is not a
scientific RSI result, production promotion, or evidence that the lab is
generally self-improving.

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
a hermetic control-plane pilot, model/credential/taskpack/reconciliation
plan-apply surfaces, and one narrowly bounded unattended EXPLORE oneshot. It
does **not** implement an unattended `explore-open` campaign, promotion, backup
mutation, a general persistent campaign supervisor, or a scientific
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

Default `reconcile`, worker, alert, archive, campaign
list/status/progress/events, doctor, and `daily status` are read-only.
Reconciliation mutation is limited to the digest-bound `--plan`/`--apply`
workflow for `ACTIVE_CAMPAIGN_MISSING_RUN` documented in `START_HERE`;
`campaign events --follow` remains an explicit refusal in this slice.

Provider configuration inspection never claims callability. The only passing
selftest is a live receipt with at least one callable route; confirm admission
requires two distinct provider entitlements, not two model-family labels. A
bounded operator refresh is:

```bash
rsi provider selftest \
  --profile staged --live --require-independent-routes 2 \
  --timeout-s 20 --max-probes 6 --min-refresh-interval-s 3000 --json
```

Live selftests write append-only `rsi_lab.provider_selftest.v2` receipts with a
collision-proof ID. Each receipt binds the immutable source commit/package,
selected profile and model IDs, route requirement, timeout, provider-call cap,
and alias policy under a content digest. Refresh cooldown reuse requires that
exact policy digest and a valid receipt digest. Zhipu's immediately succeeding
GLM minor alias is accepted only after a second bounded probe of the declared
served ID returns callable content; arbitrary family substitutions still fail.

Do not place credentials in `RSI_LAB_STAGED_MODELS` or any command argument.
With no process-local staged override, the selftest reads the active model-role
profile. The scheduled form and legacy-cron retirement are documented in
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
- an integrity-valid active three-role model profile selects only exact,
  runtime-selectable routes already present in the source-owned catalog;
- read-only reconciliation reports no control-plane finding;
- the HALT file is absent and the nonblocking host lock is available;
- `rsi doctor` is ready, including retirement of legacy provider controls;
- a valid live provider receipt, no older than one hour, attests two distinct
  callable provider entitlements for this exact release; and
- the source-pinned SWE-bench 4.1 evaluator APIs and Docker daemon are
  reachable. Linux launchers pin the local `default` context and Unix socket;
  macOS pins `colima-forge-swebench`. Candidate grading still must emit a
  complete `rsi_lab.grader_isolation_proof.v1` to become comparable.

The child shape is permanently `generations=1`, `children=1`, `tasks=1`. The
seed/control candidate uses `freeform_single`; the one child uses a bounded
`verify_chain` so the configured verifier is actually dispatched. Continuation
calls are disabled. The exact call shape is two seed/control generations, one
mutation, one child solver, and one child verifier. Each call is capped at
8,000 tokens and `$0.25` accounting cost, each candidate at 16,000 tokens and
`$0.50`, and the full experiment at 40,000 tokens. A closeout whose counters do
not prove that exact role shape is non-successful. The parent polls the HALT
latch at most every two seconds and terminates
the child process group when it appears, recording
`InconclusiveOperatorHalt`. The parent also applies a 2,700-second subprocess
timeout; systemd adds a second 2,800-second fuse. Scratch code is a standalone
exact-commit clone under state, so execution never writes the immutable release
Git dir. Before reserving spend, the runner binds the selected task row to a
release-owned fixture containing its task SHA, full stored-payload digest,
cached image ID, platform, and source paths. Only the five-field model-safe
projection (`task_id`, `instance_id`, `repo`, `base_commit`, and
`problem_statement`) plus bounded source context reaches a model. Context is
read from that exact image ID with `--pull=never` and no network.

The judge authority is the local-only `princeton-nlp/SWE-bench_Verified`
snapshot at revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`. Before
the reservation ledger is touched, admission verifies the snapshot Parquet
digest
`sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`
and the complete selected-row SHA-256
`939d1c36810a3400bab68d472d01ac5be33d18939f2cc0b96486ef7db997411c`.
There is no unrevisioned or network fallback. During grading, the isolation
shim replaces the upstream dataset loader with that pinned local loader and
revalidates the complete row before SWE-bench spec generation. The full judge
row, gold-patch body, test-patch body, and test lists are never included in
model inputs or unattended receipt payloads; receipts retain only digests and
counts needed to prove the binding. The spec shim skips its otherwise
unnecessary remote environment-file lookup because the exact prebuilt image is
already attested. Runtime readiness also binds the executed Hub and PyArrow
distribution trees under the dedicated, host-owned grader environment. The
evaluator script is redirected from the read-only
container root into its bounded `/tmp` tmpfs, and RSI-created anonymous testbed
volumes are removed at container closeout.

The unattended task/image fixture is deliberately a release authority, not a
mutable tag trust decision. Adding a new unattended task therefore requires a
reviewed release update with the governed task SHA, exact cached image ID and
platform, and bounded context paths. A missing or changed fixture refuses
before the reservation ledger is touched.

Reservations are conservative: `$1.25`/five logical call slots per run,
`$3`/12 slots per UTC day, and `$40`/120 slots per UTC month. They are never
refunded after a crash. These dollars are **not vendor billing telemetry**, and
transport-level retries are not separately metered; absence of authoritative
billing remains an explicit limitation. The budget ledger and run receipts are
strict, fsync-backed hash chains. A truncated row, bad link, changed digest,
sixth logical dispatch, stale receipt, dirty release, Docker failure, or HALT
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
