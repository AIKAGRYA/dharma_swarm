# RSI Lab exact-code synchronization

## Authority and meaning of “exact”

The canonical authority is the full commit at
`refs/heads/rsi-lab/canonical` in
`https://github.com/AmitabhainArunachala/dharma_swarm.git`. Neither a Mac
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
  bin/rsi-run -> .../current/repo/scripts/forge_lab/rsi-legacy-retired
  bin/rsi-loop -> .../current/repo/scripts/forge_lab/rsi-legacy-retired
  bin/rsi-env -> .../current/repo/scripts/forge_lab/rsi-legacy-retired
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

Every mutating legacy entry point is transactionally retired on managed
activation: `rsi-run`, `rsi-loop`, `rsi-fix-substrate`, `rsi-keys-refresh`, and,
on Meghadharma, `rsi-env` and `rsi-update-main`. The prior file is first moved
to a unique timestamped `*.legacy-*` backup, then the public name is atomically
linked to the sourceable/executable `rsi-legacy-retired` stub. If any link fails,
the wrapper transaction restores the prior names. Node readiness fails when an
alias drifts from the retirement stub.

The managed environment entry point is `rsi-lab-env`; it is intentionally not
retired. Before activation, remove or replace any crontab line that invokes a
newly retired name—especially the historical ten-minute `rsi-keys-refresh`
probe. Sync does not silently edit operator crontabs, and leaving that line in
place would create repeated exit-64 noise rather than provider evidence.

Do not repair drift with `rsync`, `scp` of a working tree, a force-push, or by
copying state directories. Preserve evidence, fix the canonical branch, create
a fresh plan, and run the managed apply path.
