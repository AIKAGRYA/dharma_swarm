# Remote Holon Fast Path — Executable Evidence

Date: 2026-07-12 JST
Base commit: `5d1fa0fa5c` (`origin/main` at worktree creation)

This is a compact review index, not an authority artifact. Source and executable
tests remain authoritative.

## Boundary map

| Boundary | Implementation | Adversarial proof |
|---|---|---|
| Canonical plan/apply | `bootstrap.py:109,152,232` | `tests/test_holon_bootstrap.py` |
| Fixed SSH preflight | `ssh_preflight.py:86,168,216,413` | `tests/test_remote_holon_ssh_preflight.py` |
| Package-owned talk/run | `_holons.py:98,196` | installed-like subprocess in `tests/test_dgc_cli.py` |
| Fail-closed lease scope | `execution_lease.py:120,194` | `tests/test_execution_lease.py` |
| Typed task/action scope | `codex_composer_wake_loop.py:734,893` | `tests/test_codex_composer_wake_loop.py` |
| Per-cycle lease validity | `codex_composer_wake_loop.py:1283,1345,1401` | expiry-between-cycles fixture in the same test file |
| Safe tmux target | `codex_composer_wake_loop.py:1542` | option/colon/space/traversal rejection fixture |
| Scoped key interface | `scripts/dkeys.py:591,625,669,713,743` | `tests/test_dkeys.py` |

Semantic rule added at the task consumer:

```text
LeaseRequired<Task> without Declared<requested_actions> -> Blocked
Declared<Actions> union ConservativeProjection<Text> -> RequestedScope
ValidatedLease<Agent, Task, RequestedScope, Expiry, Revocation> -> CycleCapability
```

Natural-language projection can narrow a declared action scope but cannot
replace the typed declaration. Empty allowed action/path scopes deny requested
work. Baseline denials are unioned and cannot be removed by a caller.

## Local executable results

```text
267 passed, 1 unrelated dependency deprecation warning
```

The combined suite covered all holon bridge/runtime/health/smoke tests plus the
new dkeys, bootstrap, SSH preflight, execution-lease, wake-loop, and DGC CLI
tests.

```text
ruff: all changed Python files clean (legacy dgc_cli unused-import codes excluded)
git diff --check: pass
compileall on changed runtime modules: pass
make agent-build-preflight: exit 0
  syntax-check OK
  F821 blockers OK
  13,616 tests collected
  onboard door OK
targeted closeout regression suite: 147 passed, 1 skipped
Forge bypass hook through repository Python: FORGE_BYPASS_GUARD_OK
```

`make agent-build-closeout` additionally proved:

```text
gitleaks: 3,296 commits scanned; no leaks found
runtime contract tests: 22 passed
closeout final status: blocked because the repository's pre-existing live NATS
production evidence is 10 days stale (24-hour freshness gate)
```

No broker-topology mutation or live NATS matrix refresh was authorized or
performed as part of this holon fast-path change.

`dkeys` host/source checks:

```text
repository scripts/dkeys.py == installed ~/.dharma/bin/dkeys
sha256 both = 6651bdea86899183fcd5cfe91eae8d12d4aa5e7a7eef801f0e3bc369be597564
installed mode=0700
raw environment export refused
inline secret argument refused
scoped child injection kept requested ref and removed unrequested stored ref
safe JSON contained no mask or length fields
```

No live provider test was triggered by key writes; `--test` is explicit.

## Live read-only host evidence

All calls used the fixed `dgc agent remote-preflight` path. No remote write,
deploy, bootstrap, sync, secret-value read, or key count occurred.

| Host | Auth observed | User | Materialization | Identity readiness | Activation |
|---|---:|---|---:|---:|---:|
| agni | yes | root | false | false | false |
| meghadharma | yes | root | false | false (identity JSON only; active prompt absent) | false |
| rushabdev | yes | root | false | false | false |

The fixed probe disables ControlMaster/ControlPath for a fresh hardened proof,
even though ordinary operator SSH retains multiplexing. It rejects IP literals,
`user@host`, default-only DNS destinations, metacharacters, unsafe holon names,
unallowlisted output, reflected stderr, and symlinked key stores.
`ProxyCommand` and `ProxyJump` are pinned to `none` for this proof path.

## Council feedback incorporated

Round 1 found that repeated wake checked its lease only at process start. The
loop now revalidates before every cycle and halts on expiry/revocation.

Round 2 found an unvalidated tmux session target and a documentation ambiguity
about ControlMaster. Session tokens now use an anchored safe-token grammar and
the docs explicitly distinguish ordinary SSH from the fresh fixed probe.

The final full-evidence round had five exact required lanes pass at score 95
(`glm-5.2`, `qwen3-coder:480b-cloud`, `deepseek-v4-pro`, `minimax-m3`, and
Nemotron Ultra) with a fresh persistent `palantir-pilot` witness. The exact
`kimi-k2.7-code` lane repeatedly returned schema-invalid truncated reasoning.
A supplemental schema-remediation run passed on an actual `kimi-k2.5` fallback,
which is useful critique but does not satisfy the required Kimi 2.7 identity.
The default-council formal gate therefore remains hold; it is not represented as
six-lane consensus.

## Intentionally still closed

- Remote mutation under root.
- Global key-store replication.
- Persistent activation without signed/attested ExecutionLease v2.
- Provider readiness inferred from a file.
- Grok/xAI provider coercion; xAI remains unsupported and fails bootstrap.
- Broad ambient LaunchAgent key environments; each daemon still needs a scoped
  dependency migration.
