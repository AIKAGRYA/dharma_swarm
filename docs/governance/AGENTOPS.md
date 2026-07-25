# AgentOps v0 + Session Entry v1

AgentOps v0 is a local governance wrapper for repo-agent work. It turns a
machine-readable work packet into a bounded worktree run with scope checks,
declared gates, structured reports, and an optional local commit candidate.

It is not a daemon, live swarm, product surface, dashboard, API, merge bot, or
push mechanism. It does not run autonomous loops.

## Work Packet

JSON is mandatory for Session Entry packets. YAML remains accepted for legacy
v0 packets only when PyYAML is already installed; AgentOps adds no dependency.

Required fields:

```json
{
  "id": "agentops-doc-check",
  "base_ref": "HEAD",
  "branch": "chore/example-agentops-job",
  "worktree": "/tmp/dharma-agentops-example",
  "intent": "Run a harmless documentation check in an isolated worktree.",
  "allowed_files": ["docs/governance/AGENTOPS.md"],
  "forbidden_files": ["api/**", "dashboard/**", "dharma_swarm/telos_gates.py"],
  "gates": [
    {
      "name": "diff-check",
      "command": "git diff --check"
    }
  ],
  "commit": {
    "allowed": false,
    "message": "chore(agentops): example"
  },
  "approval": {
    "before_commit": true,
    "before_merge": true
  }
}
```

`gates[].command` is parsed with `shlex` and executed without an implicit
shell. This is syntactic admission, not an arbitrary-command sandbox or proof
of transitive behavior. Session Entry packets are trusted declarative code:
shell-control tokens and known direct shell/wrapper or mutating-Git forms are
rejected, but an admitted interpreter or alternate client can still perform
process, network, or filesystem I/O. Never treat gate parsing alone as proof
that a command cannot indirectly merge, push, invoke a shell, or use the
network.

Private lexical mechanics live in
`dharma_swarm/operator_core/onboarding/_command_lexical.py`; public grammar and
every final admission decision remain in `contract.py`. Before an admitted
direct Git gate executes,
`run_agent_work_packet.py` must use the contract-owned environment builder to
remove inherited `GIT_*` process controls case-insensitively and then set only
`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`, and
`GIT_OPTIONAL_LOCKS=0`. The runner also applies that builder before a
negative-control environment is encoded into `env -i` argv; packet-supplied
environment remains fail-closed.

Legacy gates may omit `expected_exit`, which adapts to `0`. A declared
`expected_exit` is graded against the actual process exit and both values are
retained in the report.

## Session Entry v1

A new implementation packet extends—not renames—the v0 shape with
`negative_controls` and `session_entry`:

```json
{
  "id": "example-track-WP-1",
  "base_ref": "<exact 40-character SHA>",
  "branch": "agent/example-wp-1",
  "worktree": ".",
  "allowed_files": ["docs/governance/AGENTOPS.md"],
  "forbidden_files": ["api/**", "dashboard/**"],
  "gates": [{"name": "tests", "command": "python3 -m pytest -q", "expected_exit": 0}],
  "negative_controls": [
    {"name": "outside-envelope", "command": "python3 -m pytest -q -k outside", "expected_exit": 0}
  ],
  "session_entry": {
    "schema": "dharma_swarm.session_entry.v1",
    "tool_versions": {"python": "3.12", "git": "2.51"},
    "authority_precedence": ["executable", "tests", "locks", "git", "owner_files"],
    "work_packet": "WP-1",
    "active_track": "example-track-2026-07",
    "owner": "<owner matching the selected active track>",
    "collision": {"status": "clear", "checked_at_sha": "<same exact SHA>", "details": []},
    "interface_mismatches": [],
    "closest_existing_implementation": ["docs/governance/AGENTOPS.md"],
    "honest_blockers": [],
    "rollback": "revert the packet-scoped implementation commit",
    "packet_digest": "<stable_digest of the packet with only this field omitted>"
  }
}
```

The omitted v0 fields (`intent`, `commit`, and `approval`) remain mandatory.
Angle-bracket values above are illustrative and must be replaced. Session Entry
validation additionally requires:

- an external packet path and exact packet `stable_digest` after omitting only `session_entry.packet_digest`;
- a generic `WP-*` work-packet identifier bound injectively to the
  track-specific packet id; no campaign prefix is privileged;
- at least one gate, with `work_packet` bound to the packet id and every
  declared tool version freshly probed for exact equality;
- no angle-bracket placeholder anywhere in the submitted packet;
- `worktree: "."`, resolved only after the runner proves its current directory
  is the repository root;
- an ACTIVE selected track whose owner matches the packet;
- every sibling track's owned surface in `forbidden_files`;
- recomputed exact, containment, glob-intersection, and actual-file collision
  checks agreeing with the declared clear result; and
- an explicit expected exit for every negative control.

## Scope Gate

`allowed_files` and `forbidden_files` use repo-relative glob patterns.
Forbidden patterns override allowed patterns.

AgentOps inspects:

- tracked changed files
- staged files
- untracked files

The run fails closed if any changed file is outside `allowed_files`, if any
changed file matches `forbidden_files`, or if an untracked file is outside the
allowed scope.

## Worktree Behavior

The runner creates the declared worktree from `base_ref` and `branch`, or
attaches to an existing worktree when the path, branch, and base ancestry match.
By default it refuses an already-dirty target worktree before gates run. For a
human-reviewed post-agent verification run, `--allow-existing-changes` permits
existing changes while still enforcing the scope gate.

Dry-run mode is available with `--dry-run` or `--inspect`. It reads and validates
the packet, prints intended actions, and does not create a worktree, run gates,
write reports, or commit.

For Session Entry v1, inspect is the edit-admission bootstrap: the packet must
be outside the repository, `HEAD` must equal `base_ref`, the branch must match,
and the worktree must be clean. After inspect succeeds, copy the packet bytes
unchanged to `reports/agentops/work_packets/<packet-id>.json`. A non-dry run
requires that tracked-path copy to exist and be byte-identical. Committed-range
scope enforcement is applied by packet-aware preflight and closeout.

Negative controls run one at a time in disposable clones. Linux uses a chroot
jail directly as root, through an unprivileged user namespace, or through
passwordless `sudo` with an immediate UID/GID drop. macOS uses `sandbox-exec`.
Runtime and dependency files placed in a jail are byte copies, never hard
links. A host without a real write-confinement mechanism fails closed. Source
symlinks and environment routes are rejected; fixture mutations remain usable.

## Reports

Session Entry non-dry execution requires `--report-root <external-path>`. The
resolved path must be outside both the worktree and Git administrative state,
including through symlinks. Final report parents are revalidated immediately
before creation and write. It writes the existing report schema beneath:

```text
<report-root>/reports/agentops/<job_id>/<timestamp>/report.json
<report-root>/reports/agentops/<job_id>/<timestamp>/report.md
```

Reports include the job id, base ref, branch, worktree, intent, scope patterns,
changed files, gate and negative-control expected/actual exits and output, final
git status, commit hash when created, and human approval flags. Legacy v0 keeps
its historical in-worktree report fallback for compatibility; new Session Entry
packets never use it.

## Commit Policy

AgentOps may create a local commit candidate only when:

- `commit.allowed` is true
- every gate and negative control exits with its declared expected value
- the scope gate passes
- `approval.before_commit` is false
- the worktree contains only allowed changes

If `approval.before_commit` is true, AgentOps records that human approval is
required and refuses to commit. If `approval.before_merge` is true, AgentOps
records the boundary in the report. AgentOps v0 never merges and never pushes.

## Human Boundary

AgentOps v0 makes a repeatable local workflow, not an authority transfer. The
human operator remains responsible for approving integration, interpreting
quality, and deciding what should enter the main rollup.

## Positive Gate Command Admission

Positive gates pass one fail-closed command-family allowlist before any
subprocess execution (`scripts/governance/run_agent_work_packet.py`,
`admit_gate_command`). Admitted families: the contract-owned read-only Git
grammar, `python -m pytest …`, `python -m ruff check …`, the enumerated
read-only governance/DocOps scripts (never with `--write-context`), and the
enumerated Make targets with only `PACKET=`/`ARGS=` variables. Everything
else — inline interpreters (`python -c`, `node -e`), network clients
(`gh`, `ssh`, `curl`, `wget`), shell-capable wrappers, unknown executables,
and any gate carrying packet-supplied environment — fails closed before it
runs. Negative controls are exempt: they exist to prove rejection and run
jailed. This is command-family confinement, not a semantic proof (an
allowlisted script can itself perform I/O); syscall/no-network evidence is a
separate verification boundary. Extending the table is a
governance-reviewed admission change.
