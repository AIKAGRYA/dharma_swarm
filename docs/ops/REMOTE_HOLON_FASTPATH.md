# Remote Holon Fast Path

Current as of 2026-07-12. This is the operator path for finding, materializing,
and eventually activating the same canonical holon on another host. It creates
no second agent registry and never copies the global credential store.

## The Type Boundary

```text
Observed<SSHAuthentication> != Authorized<RemoteBootstrap>
Plan<HolonMaterialization> + ExplicitApply -> Materialized<ReadOnlyHolon>
ValidatedLease<Agent, Task, Action, Expiry> -> RepeatedWakeCapability
SecretRef<Provider> -> ScopedChildEnvironment
```

An SSH success proves only that this Mac can authenticate. A key-presence
check proves only that a regular file exists with a safe mode. Neither is a
deployment grant, a provider-health proof, or authority to copy secrets.

Execution-lease v1 is a local checksummed scope receipt, not an operator
signature. The runtime says so in its validation result. Remote mutation stays
closed until the signed/attested v2 authority seam exists.

## One Local Door

Inspect the idempotent plan (read-only):

```bash
dgc agent bootstrap codex_remote --from-agent codex_composer
```

Materialize it locally after reviewing the plan:

```bash
dgc agent bootstrap codex_remote --from-agent codex_composer --apply
dgc agent status codex_remote --json
```

The command writes the canonical `~/.dharma/agents/<name>` identity and active
prompt, composes the existing roaming onboarding surfaces, round-trips through
`load_holon`, and reads no provider secret. Repeating the same command is a
no-op. Conflicting identity claims fail closed; they are never overwritten.

Unknown providers also fail closed. In particular, `xai`/Grok is not yet a
`ProviderType`, so a `grok_build` directory must not be represented as a live
Grok holon until a real xAI adapter and subscription/API authentication route
land.

## Scoped Key Use

Safe status and one-child injection on the Mac:

```bash
dkeys safe-json
dkeys exec XAI_API_KEY -- your-command --flag
```

`dkeys exec` removes every other stored provider variable from the child
environment and injects only the named references. It invokes the command
directly without a shell. `dkeys env` and inline `dkeys add VAR=value` are
disabled.

Never run the untracked `sync_agent_keys_to_vps.sh` in apply mode. Full-store
replication, remote raw backups, and self-asserted approval flags are not a
secret-broker design.

## Read-Only VPS Reality

Fresh strict SSH probes on 2026-07-12 established:

```bash
dgc agent remote-preflight agni --name codex_composer
dgc agent remote-preflight meghadharma --name codex_composer
dgc agent remote-preflight rushabdev --name codex_composer
```

| Alias | SSH auth | Login | Repo | Venv/package | Canonical Codex identity | Key-store metadata |
|---|---|---|---|---|---|---|
| `agni` | observed | `root` | missing | missing | missing | regular file, safe mode |
| `meghadharma` | observed | `root` | present | venv missing | identity JSON present; active prompt missing | regular file, safe mode |
| `rushabdev` | observed | `root` | missing | missing | missing | missing |

All three aliases now resolve locally with `IdentitiesOnly=yes`,
`StrictHostKeyChecking=yes`, and `ForwardAgent=no`. ControlMaster remains
enabled for ordinary operator SSH sessions. The fixed preflight deliberately
sets `ControlMaster=no` and `ControlPath=none` so it cannot inherit an older
connection that was opened under weaker options; a fresh proof currently
finishes in roughly two seconds for the three-host sweep. It also pins
`ProxyCommand=none` and `ProxyJump=none`; aliases that require an executable
proxy fail closed instead of inheriting one from ambient SSH configuration.

This matrix is not a deployment green light. Every host currently logs in as
root. `rushabdev` also has historical custody risk around a unique data copy;
do not repurpose or mutate it merely because authentication currently works.
All three currently report `materialization_ready=false` and
`activation_ready=false` through the fixed preflight.

## Remote Activation Gate

A host becomes bootstrap-ready only when all of these are true:

1. A dedicated non-root deploy/runtime account exists.
2. Host identity remains pinned and agent forwarding remains off.
3. A reviewed immutable package/archive is present with Python 3.11+ and its
   environment.
4. The same `dgc agent bootstrap` plan succeeds on that host.
5. Provider access is delivered as a scoped, non-exportable secret grant to one
   child process—not as the global key file.
6. A host/agent/action-bound, expiring, revocable authority grant validates.
7. `dgc agent status <name> --json` and one bounded model probe emit fresh
   receipts.
8. Repeated wake is separately authorized; a non-empty string is never a
   lease.

The next infrastructure slice is therefore artifact delivery plus a non-root
runtime account, followed by signed authority v2. Copying more keys would make
the system faster to compromise, not faster to instantiate.
