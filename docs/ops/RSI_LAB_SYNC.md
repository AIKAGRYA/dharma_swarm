# RSI Lab exact-code synchronization

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
  --request-id operator-YYYYMMDD-purpose
```

For an explicitly requested one-command convergence, plan and apply can be
combined:

```bash
rsi sync converge --request-id operator-YYYYMMDD-purpose
```

The explicit command is idempotent. It prepares detached releases on both
hosts, verifies their exact identity, runs the versioned offline test slice,
and only then atomically changes `current`. It makes no model/provider call.

Rollback requires a previously verified full SHA and intentionally creates
drift from GitHub when that SHA is not the canonical branch head:

```bash
rsi sync rollback \
  --release <40-character-release-sha> \
  --request-id operator-YYYYMMDD-rollback
```

Always run `rsi sync status` after rollback or repair.

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
- an active Forge/RSI campaign manifest, recognizable tmux session, or known
  campaign process; or
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
`PYTHONPATH` to that release's stable host-owned links. Inherited values cannot
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
  --apply --request-id operator-YYYYMMDD-retire-legacy-refresh
rsi doctor --json
```

The installer removes the legacy refresh and `current-main` log entries,
renames the old executable to a recoverable timestamped `legacy-*` custody
path, similarly renames the obsolete `current-main` run log and legacy
`keys_status.json` artifacts, deduplicates any prior managed entry, and
installs one hourly invocation of `rsi-provider-refresh`. The replacement
invokes the versioned provider
selftest with at most four probes, a one-hour minimum refresh interval, and a
two-provider requirement. Provider credential values are resolved in-process;
they never appear in cron argv or its receipt. The installer is plan-only by
default and must not be run from an unverified release.

The replacement writes append-only `rsi_lab.provider_selftest.v2` receipts.
Cooldown reuse is valid only when the receipt digest and its source/config/probe
policy digest validate exactly; a receipt from a different release, staged
model list, timeout, call ceiling, route requirement, or alias policy is not a
cache hit.

Do not repair drift with `rsync`, `scp` of a working tree, a force-push, or by
copying state directories. Preserve evidence, fix the canonical branch, create
a fresh plan, and run the managed apply path.
