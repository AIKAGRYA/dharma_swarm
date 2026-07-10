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

`gates[].command` is parsed with `shlex` and executed without a shell. Shell
control tokens are rejected. Gate commands cannot run merge, push, or other
mutating git integration operations.

Legacy gates may omit `expected_exit`, which adapts to `0`. A declared
`expected_exit` is graded against the actual process exit and both values are
retained in the report.

## Session Entry v1

A new implementation packet extends—not renames—the v0 shape with
`negative_controls` and `session_entry`:

```json
{
  "id": "onboard-one-door-WP-O1",
  "base_ref": "<exact 40-character SHA>",
  "branch": "codex/onboard-wp-o1-example",
  "worktree": ".",
  "allowed_files": ["scripts/governance/run_agent_work_packet.py"],
  "forbidden_files": ["docs/governance/ACTIVE_TRACK.yaml"],
  "gates": [{"name": "tests", "command": "python3 -m pytest -q", "expected_exit": 0}],
  "negative_controls": [
    {"name": "outside-envelope", "command": "python3 -m pytest -q -k outside", "expected_exit": 0}
  ],
  "session_entry": {
    "schema": "dharma_swarm.session_entry.v1",
    "tool_versions": {"python": "3.12", "git": "2.51"},
    "authority_precedence": ["executable", "tests", "locks", "git", "owner_files"],
    "work_packet": "WP-O1",
    "active_track": "onboard-one-door-2026-07",
    "owner": "@AmitabhainArunachala",
    "collision": {"status": "clear", "checked_at_sha": "<same exact SHA>", "details": []},
    "interface_mismatches": [],
    "closest_existing_implementation": ["scripts/governance/run_agent_work_packet.py"],
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
scope enforcement is not claimed here; WP-O4 adds it to the existing matcher.

Negative controls run one at a time in disposable clones. Linux uses a chroot
jail (directly as root or through an unprivileged user namespace); macOS uses
`sandbox-exec`. Runtime and dependency files placed in a jail are byte copies,
never hard links. A host without a real write-confinement mechanism fails
closed. Source-pointing symlinks and environment routes are rejected, while
mutations inside the disposable fixture remain available to the control.

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
