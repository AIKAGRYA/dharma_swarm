# RSI Lab exact-code synchronization

## START_HERE

The only supported code deployment path is the versioned `rsi sync` controller.
On the Mac operator host, inspect, plan, apply the returned content-addressed
manifest, and read back all three identities:

```bash
rsi sync status --json
rsi sync plan --json
rsi sync apply \
  --manifest sha256:<64-hex-plan-digest> \
  --request-id operator-YYYYMMDD-daily-lane \
  --remote meghadharma \
  --json
rsi sync status --remote meghadharma --json
```

An explicitly requested one-step plan/apply and a verified-release rollback are:

```bash
rsi sync converge \
  --request-id operator-YYYYMMDD-converge \
  --remote meghadharma \
  --json

rsi sync rollback \
  --release <40-character-lowercase-release-sha> \
  --request-id operator-YYYYMMDD-release-rollback \
  --remote meghadharma \
  --json
```

Do not substitute `rsync`, `scp` of a working tree, a pull in the active
checkout, or a state-directory copy. Sync receipts establish release/code
identity only. They do not establish provider availability, evaluation quality,
promotion authority, scientific improvement, or mutable-state equivalence.

After activation, run the single read-only daily projection on Meghadharma:

```bash
rsi daily status --json
```

It stays non-ready until reconciliation, the model/API on-ramp, a sealed
admitted taskpack, the installed scheduler, and the last bounded closeout all satisfy
their own authorities.
`ready_for_next_run`, `last_cycle_healthy`, and `awaiting_first_run` distinguish
pre-run readiness from historical cycle health; closeout success is rederived
from the exact child-result and log artifacts, not trusted from path strings.

### Model/API on-ramp

Credential handoff is one provider at a time. Apply prompts with hidden input;
no supported argument carries the secret value:

```bash
rsi provider credential status --provider zhipu --json
rsi provider credential plan --provider zhipu --json
rsi provider credential apply \
  --provider zhipu \
  --plan-digest sha256:<64-hex-plan-digest> \
  --request-id operator-YYYYMMDD-zhipu-key \
  --json
```

For a secret-manager pipe, add `--stdin`; it reads exactly one line. Never put
a secret literal in argv, shell history, JSON, logs, or a request ID. Repeat the
value-free status/plan/apply flow for every required provider.

Inspect the exact source-owned catalog and active profile, then plan/apply the
same three role bindings:

```bash
rsi provider models list --json
rsi provider models status --json

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

Omit `--expected-current-digest` only when status reports that no current
profile exists. For every replacement, add
`--expected-current-digest sha256:<current-profile-digest>` to both plan and
apply. Rollback is a new monotonic activation of an ancestor profile:

```bash
rsi provider models rollback \
  --request-id operator-YYYYMMDD-model-rollback \
  --expected-current-digest sha256:<current-profile-digest> \
  --target-profile-digest sha256:<ancestor-profile-digest> \
  --json
```

Only `runtime_selectable: true` catalog rows are configuration-onboardable.
Unknown providers and provider/model IDs whose execution is ambiguous require a
provider-qualified runtime implementation; unknown exact routes require a
reviewed source change. A plan reporting `implementation_required` or
`source_change_required` must not be forced through apply. Model activation is
role selection only: it makes no provider call, loads no credential, edits no
source or weights, attests no quality/availability, and grants no promotion
authority.

Run the bounded staged live proof after credentials and role activation:

```bash
rsi provider selftest \
  --profile staged --live --require-independent-routes 2 \
  --timeout-s 20 --max-probes 6 --min-refresh-interval-s 3000 \
  --json
```

### Taskpack and reconciliation gates

The taskpack manifest is a sealed, newline-terminated `.jsonl` path, not a
digest reference. Plan and apply must use identical manifest bytes, cutoff, and
mode:

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

The admitted daily `search_only_public_swebench` mode validates an exact
official-SWE-bench-shaped public row contract, but does not cryptographically
prove membership against a pinned official dataset seal. Because public
pretraining contamination remains possible, its evidence is permanently
`EXPLORE_ONLY`, `promotion_eligible: false`, and `confirm_eligible: false`.
It is the admitted daily lane. `governed_fresh` remains fail-closed with
`MODEL_CUTOFF_AUTHORITY_REQUIRED` until authoritative cutoff evidence exists
for every active role; an operator-entered date is not sufficient authority.

Default reconciliation is read-only. The only supported repair is the
receipt-backed stale projection finding `ACTIVE_CAMPAIGN_MISSING_RUN`:

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

Retry an unknown reconciliation outcome only with the exact same plan digest,
campaign ID, and request ID. There is no generic `rsi recover` operation.

### Daily scheduler, HALT, and evidence boundary

The provider refresh installer is separately plan/apply controlled. Its single
managed cron entry runs hourly at minute `:17`:

```bash
/root/rsi-lab/bin/rsi-provider-refresh-install --plan
/root/rsi-lab/bin/rsi-provider-refresh-install \
  --apply --plan-digest sha256:<digest-from-plan> \
  --request-id operator-YYYYMMDD-provider-refresh
rsi doctor --json
```

The EXPLORE timer runs once per UTC day at `03:35` with at most `25m` randomized
delay (`OnCalendar=*-*-* 03:35:00 UTC`, `RandomizedDelaySec=25m`). Sync installs
the versioned wrapper but never writes `/etc/systemd/system` and never enables a
timer. First obtain a green doctor, a fresh two-provider receipt, and one
operator-supervised proof. Start that proof immediately after the managed
minute-`:17` provider refresh completes, with enough time for the 2,700-second
fuse to finish before the next hourly refresh. A refresh during the child
re-admission window intentionally invalidates the parent-bound receipt; if the
window is not clear, do not reserve the run:

```bash
/root/rsi-lab/bin/rsi-unattended-explore --timeout-seconds 2700
```

Only after that proof succeeds, manually install and verify the units with the
commands in [Install the bounded systemd oneshot](#install-the-bounded-systemd-oneshot).

Emergency stop is a host latch followed by stopping future scheduling; there
are no `rsi halt/start/stop` commands:

```bash
install -o root -g root -m 0600 /dev/null \
  /root/rsi-lab/state/.dharma/forge_lab/HALT
systemctl stop rsi-lab-explore.timer
systemctl status rsi-lab-explore.service --no-pager
rsi daily status --json
```

If HALT polling does not terminate an active oneshot, use
`systemctl stop rsi-lab-explore.service`. Before recovery, inspect doctor,
reconciliation, alerts, journals, Docker, the receipt chain, and the budget
chain. Only after the underlying finding is repaired may the operator remove
the latch and restart the installed timer:

```bash
rsi doctor --json
rsi reconcile --json
rsi alerts list --json
journalctl -u rsi-lab-explore.service --since '36 hours ago' --no-pager
unlink /root/rsi-lab/state/.dharma/forge_lab/HALT
systemctl start rsi-lab-explore.timer
systemctl status rsi-lab-explore.timer --no-pager
rsi daily status --json
```

The fixed `1 x 1 x 1` run reserves `$1.25`/five logical slots, with hard ceilings
of `$3`/12 per UTC day and `$40`/120 per UTC month. Reservations are not
refunded after crashes. A digest-bound reconciliation row records complete
actual provider cost when trustworthy billing evidence exists, or typed
`null` with `unavailable`/`ambiguous` completeness otherwise. Reconciliation
never adds a second charge or refund; conflicting replay fails closed, while an
exact replay returns the original row. Actual cost or logical calls above the
reservation are durably receipted and reject the run. Provider receipts,
model profiles, taskpack actions, reconciliation receipts/quarantine, and the
unattended ledger/receipts/runs live under
`/root/rsi-lab/state/.dharma/forge_lab/`. Every unattended closeout is
`EXPLORE_ONLY` with `positive_rsi_claim: false`; neither sync nor daily operation
is a promotion or scientific recursive-improvement claim. The expanded
operator sequence and exact artifact paths are in
[`FORGE_LAB_V0_1_RUNBOOK.md`](FORGE_LAB_V0_1_RUNBOOK.md#start_here).

## Authority and meaning of “exact”

The canonical authority is the full commit at
`refs/heads/rsi-lab/canonical` in
`https://github.com/AIKAGRYA/dharma_swarm.git`. Neither a Mac
working tree nor an unversioned VPS script is an authority.

An `IN_SYNC` result proves that GitHub, the Mac release, and the Meghadharma
release agree on all of the following:

- full Git commit and root tree;
- clean checkout status;
- `uv.lock` SHA-256;
- Forge package version; and
- SHA-256 for the versioned CLI, sync controller, wrappers, lockfile, and this
  operating runbook.

The host OS, machine architecture, Python executable, and Python version are
attested separately. They are not expected to be byte-identical: the Mac is
arm64 macOS and Meghadharma is amd64 Linux. Both must run Python 3.11 or newer
and pass the same offline release checks.

Mutable state is deliberately excluded. The sync controller never copies
`state`, archives, SQLite databases or WAL files, secrets, OAuth material, or
provider credentials. Meghadharma remains authoritative for campaign state.

## Normal operator flow

Read-only status is the default operation:

```bash
rsi sync status
rsi sync status --json
```

To pin and inspect the canonical identity before switching anything:

```bash
rsi sync plan --json
```

Apply the returned content-addressed manifest with an auditable request ID:

```bash
rsi sync apply \
  --manifest sha256:<64-hex-plan-digest> \
  --request-id operator-YYYYMMDD-purpose \
  --json
```

For an explicitly requested one-command convergence, plan and apply can be
combined:

```bash
rsi sync converge --request-id operator-YYYYMMDD-purpose --json
```

The explicit command is idempotent. It prepares detached releases on both
hosts, verifies their exact identity, runs the versioned offline test slice,
and only then atomically changes `current`. It makes no model/provider call.

Rollback requires a previously verified full SHA and intentionally creates
drift from GitHub when that SHA is not the canonical branch head:

```bash
rsi sync rollback \
  --release <40-character-release-sha> \
  --request-id operator-YYYYMMDD-rollback \
  --json
```

Always run `rsi sync status --json` after rollback or repair.

## Host layout

Mac:

```text
~/.dharma/rsi-lab/
  cache/dharma_swarm.git
  releases/<full-sha>/repo
  current -> releases/<full-sha>
  runtime/.venv -> host Python environment
  runtime/pydeps
  state/
  plans/
  receipts/
~/.dharma/bin/rsi -> .../current/repo/scripts/forge_lab/rsi
~/.dharma/bin/rsi-lab-env -> .../current/repo/scripts/forge_lab/rsi-env
~/.dharma/bin/rsi-provider-refresh -> .../current/repo/scripts/forge_lab/rsi-provider-refresh
~/.dharma/bin/rsi-provider-refresh-install -> .../current/repo/scripts/forge_lab/rsi-provider-refresh-install
~/.dharma/bin/rsi-unattended-explore -> .../current/repo/scripts/forge_lab/rsi-unattended-explore
```

Meghadharma:

```text
/root/rsi-lab/
  cache/dharma_swarm.git
  releases/<full-sha>/repo
  current -> releases/<full-sha>
  state -> preserved pre-migration state directory
  runtime/.venv -> preserved host environment
  runtime/pydeps -> preserved host dependencies
  secrets -> preserved host-only secret directory
  plans/
  receipts/
  bin/rsi -> .../current/repo/scripts/forge_lab/rsi
  bin/rsi-lab-env -> .../current/repo/scripts/forge_lab/rsi-env
  bin/rsi-provider-refresh -> .../current/repo/scripts/forge_lab/rsi-provider-refresh
  bin/rsi-provider-refresh-install -> .../current/repo/scripts/forge_lab/rsi-provider-refresh-install
  bin/rsi-unattended-explore -> .../current/repo/scripts/forge_lab/rsi-unattended-explore
```

The original chassis and `current-main` recovery worktree are retained. The
first managed activation anchors their resolved mutable paths before switching
`current`, avoiding a symlink loop or live database move.

## Safety gates and recovery

Activation refuses:

- a manifest whose digest, repository, ref, test contract, or file set changed;
- a canonical branch that moved after planning;
- a dirty or identity-mismatched release;
- an unexpected concurrent `current` change;
- a non-symlink `current` path;
- an operator `DEPLOYMENT_BLOCK`;
- an active Forge/RSI campaign manifest or known campaign process (tmux
  session names are recorded as operator-console evidence only); or
- a remote outside the explicit SSH allowlist.

SSH is non-interactive, host-key checked, identity-only, and has agent,
password, and keyboard-interactive authentication disabled. Receipts record
the plan digest, previous/target releases, runtime fingerprint, guard evidence,
wrapper paths, and readback identity. They explicitly state that mutable state
and provider calls were not part of synchronization.

`/root/rsi-lab/bin/rsi-update-main` is retired because it edited a live
checkout and could continue after a failed fetch. Its original file is retained
under a timestamped `rsi-update-main.legacy-*` name on first activation.

The pre-existing `/root/rsi-lab/bin/rsi-env` remains solely for the preserved
legacy-v0 wrapper set; replacing it would silently change those historical
launchers. The managed environment entry point is `rsi-lab-env`. Legacy-v0
launchers are noncanonical custody surfaces and must not be used to claim or
repair synchronization.

The managed `rsi` and `rsi-lab-env` wrappers resolve `current` to its physical
full-SHA release before exporting `RSI_LAB_REPO`. In production they also pin
`RSI_LAB_STATE`, `DHARMA_HOME`, the Python executable, dependencies, and
`RSI_LAB_PROVIDER_SELFTEST_ROOT`, and `PYTHONPATH` to that release's stable
host-owned links. Provider writers and all admission/readiness readers therefore
use the same state-anchored receipt directory. Inherited values cannot
select a mutable checkout or a second state root. The opt-in
`RSI_LAB_DEV_SOURCE=1` escape hatch exists for repository tests and is not a
production launch mode. Verify this contract with:

```bash
pytest -q tests/forge_lab_v1/test_cli_contract.py \
  -k 'launcher or inherited_source_state'
```

## Retire the unversioned provider cron

`rsi doctor --json` fails readiness while it observes any legacy
`rsi-keys-refresh` script/cron, a `current-main/state/rsi_runs` log target, an
old `keys_status.json`, or the historical `kimi`/`moonshot` rows projected from
the same probe result. It also requires exactly one versioned refresh entry.
The doctor returns paths and hazard names, never key values or raw crontab
content.

After activating the release, inspect the finite plan and then apply it with a
request ID:

```bash
/root/rsi-lab/bin/rsi-provider-refresh-install --plan
/root/rsi-lab/bin/rsi-provider-refresh-install \
  --apply --plan-digest sha256:<digest-from-plan> \
  --request-id operator-YYYYMMDD-retire-legacy-refresh
rsi doctor --json
```

The installer removes the legacy refresh and `current-main` log entries,
renames the old executable to a recoverable timestamped `legacy-*` custody
path, similarly renames the obsolete `current-main` run log and legacy
`keys_status.json` artifacts, deduplicates any prior managed entry, and
installs one hourly invocation of `rsi-provider-refresh` at minute `:17`
(`17 * * * *`). The replacement invokes the versioned provider selftest with at
most six probes, a 3,000-second minimum refresh interval, and a two-provider
requirement. Provider credential values are resolved in-process; they never
appear in cron argv or its receipt. The installer is plan-only by default. Its
apply rechecks the exact pre-install crontab digest, requires the inspected plan
digest, and binds a stable request ID to one immutable receipt; it must not be
run from an unverified release.

The replacement writes append-only `rsi_lab.provider_selftest.v2` receipts.
Cooldown reuse is valid only when the receipt digest and its source/config/probe
policy digest validate exactly; a receipt from a different release, staged
model list, timeout, call ceiling, route requirement, or alias policy is not a
cache hit.

## Install the bounded systemd oneshot

The sync activation installs the immutable `rsi-unattended-explore` wrapper,
but it deliberately does not mutate `/etc/systemd/system` or enable a timer.
After release activation, legacy-provider retirement, one fresh two-provider
selftest, and a **successful operator-supervised oneshot**, manually install and
verify the versioned unit bytes. The stable `/root/rsi-lab/state` anchor may be a
managed symlink, so first resolve it and prove that the physical state root is
not a symlink, is owned by the service user, and is not group/world writable.
The known-safe live physical root is `root:root` mode `0755`; repair a broader
mode explicitly before any timer activation, then inspect each existing custody
ancestor:

```bash
rsi_state_root="$(readlink -e /root/rsi-lab/state)"
test -n "${rsi_state_root}"
test "${rsi_state_root}" != "/"
test -d "${rsi_state_root}"
case "${rsi_state_root}" in
  /root/rsi-lab/state|/root/rsi-lab/*/state) ;;
  *) exit 1 ;;
esac
test ! -L "${rsi_state_root}"
test "$(stat -c '%U:%G' "${rsi_state_root}")" = "root:root"
chmod 0755 "${rsi_state_root}"
stat -c '%U:%G %a %n' \
  "${rsi_state_root}" \
  "${rsi_state_root}/.dharma" \
  "${rsi_state_root}/.dharma/forge_lab" \
  "${rsi_state_root}/.dharma/evolution_worktrees" 2>/dev/null
```

Install with `HALT` present so the first activation of the persistent timer
cannot launch a catch-up run. Starting a timer with `Persistent=true` can make a
missed calendar event immediately eligible:

```bash
install -o root -g root -m 0600 /dev/null \
  /root/rsi-lab/state/.dharma/forge_lab/HALT
install -o root -g root -m 0644 \
  /root/rsi-lab/current/repo/scripts/forge_lab/systemd/rsi-lab-explore.service \
  /etc/systemd/system/rsi-lab-explore.service
install -o root -g root -m 0644 \
  /root/rsi-lab/current/repo/scripts/forge_lab/systemd/rsi-lab-explore.timer \
  /etc/systemd/system/rsi-lab-explore.timer
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/rsi-lab-explore.service \
  /etc/systemd/system/rsi-lab-explore.timer
systemctl enable rsi-lab-explore.timer
systemctl start rsi-lab-explore.timer
systemctl show rsi-lab-explore.timer --no-pager \
  --property=ActiveState,LastTriggerUSec,NextElapseUSecRealtime
systemctl show rsi-lab-explore.service --no-pager \
  --property=ActiveState,ConditionResult,ConditionTimestamp,ExecMainStartTimestamp,Result,ExecMainStatus
```

On first activation, `Persistent=true` may schedule a missed daily event after
the configured randomized delay. Keep `HALT` present until that catch-up has
been condition-skipped and `NextElapseUSecRealtime` identifies the next intended
daily `03:35`-to-`04:00 UTC` window, not merely any future catch-up time. A
condition-skipped timer event may advance `LastTriggerUSec`; it must not advance
`ExecMainStartTimestamp`. Daily health therefore uses the latter as evidence
that the service process actually started and retains the raw timer trigger as
activation evidence that must be accounted for, never as proof that the service
process started. When a trigger is newer than the last closeout, the
skip is accepted only if `ConditionResult=no` and `ConditionTimestamp` falls
between that trigger and five minutes after it; missing, malformed, stale, or
successful condition evidence fails closed.

Only after the timer is active, the service is not running, no unaccounted
service execution is newer than the supervised closeout, and the next elapse is
the intended daily window should the operator remove the latch and recheck both
timer and daily status:

```bash
unlink /root/rsi-lab/state/.dharma/forge_lab/HALT
systemctl status rsi-lab-explore.timer --no-pager
rsi daily status --json
```

The service is `Type=oneshot`, drops its capability and ambient-capability
sets, makes home and the immutable release read-only, writes only
`/root/rsi-lab/state` plus the two public Hugging Face cache roots needed for
offline file locks, forbids namespace creation, and applies systemd process
hardening plus an external timeout. Docker remains a daemon-mediated Unix
socket client; candidate containers never receive that socket. The launcher
pins SWE-bench 4.1 from the root-owned, non-writable dedicated host runtime and
attests the executed SWE-bench, Docker SDK, datasets, Hugging Face Hub, and
PyArrow distribution trees. It refuses a missing, escaped, modified, or
API-incompatible evaluator. Verify
unit syntax and the complete grader runtime
through `rsi doctor --json` before enabling the timer. The provider refresh is
independent and runs hourly at minute `:17`.
The persistent EXPLORE timer fires once per UTC day at `03:35` plus no more than
`25m` randomized delay; the runner's daily/monthly reservation ledger remains
the authoritative admission fuse.

The daily launcher also pins the local Docker socket, clears inherited Docker
TLS/API overrides after credential bootstrap, and requires both CLI and Python
SDK daemon probes. Its task context and grader use only the release-attested
cached image ID: no mutable image pull is permitted after admission, and the
task/image/context binding is rechecked in the child process. Admission also
requires the local-only `SWE-bench_Verified` revision
`c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, Parquet digest
`sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`,
and selected-row SHA-256
`939d1c36810a3400bab68d472d01ac5be33d18939f2cc0b96486ef7db997411c`
to match before reservation. The grader substitutes and rechecks that pinned
loader; only the five-field model-safe task projection reaches models, while
the judge row, gold patch, test patch, and test lists remain outside model and
receipt payloads. See the authority-chain details in
[`FORGE_LAB_V0_1_RUNBOOK.md`](FORGE_LAB_V0_1_RUNBOOK.md#bounded-unattended-explore-oneshot).
The exact task-allocation bridge is permanently typed as EXPLORE and validates
that the allocator receipts one admitted task from the anchored database. The
parent rejects a child result unless its standalone scratch clone reports and
passes guarded cleanup. The parent separately owns a marker-bound per-run
scratch root and removes it through no-follow directory handles after every
child outcome, including timeout, HALT, and SIGKILL. Create, child attestation,
and cleanup bind to the exact directory device/inode and original marker digest,
and the child holds an exclusive directory lease while live. Each invocation
audits prior roots under
the host lock before admission or budget reservation: only roots with an exact
spec plus durable create receipt are recovered; unknown, substituted, or busy
roots are preserved and refuse with zero new spend. The physical state root and
custody ancestors must be owner-controlled and not group/world writable. A
success receipt therefore requires matching create/attest/cleanup proofs plus
lexical path absence; root/ancestor/marker substitution, result-shape, special
files, or cleanup drift fails closed. Ordinary Git repository symlinks are
inventoried and unlinked by directory handle without following their targets.
Create the following file to stop new runs without editing code or units:

```bash
install -o root -g root -m 0600 /dev/null \
  /root/rsi-lab/state/.dharma/forge_lab/HALT
```

Removing `HALT` is an operator action. Before doing so, stop the timer and
inspect doctor, reconciliation, receipts, alerts, Docker health, journals, and
the hash-chained budget ledger. Repair through the owning plan/apply or rollback
surface; then `unlink /root/rsi-lab/state/.dharma/forge_lab/HALT`, restart the
timer, and verify `rsi daily status --json`. This timer is a bounded EXPLORE
collector, not the missing general campaign supervisor and not evidence that
RSI is scientifically humming.

Do not repair drift with `rsync`, `scp` of a working tree, a force-push, or by
copying state directories. Preserve evidence, fix the canonical branch, create
a fresh plan, and run the managed apply path.
