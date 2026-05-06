# AgentOps v0

AgentOps v0 is a local governance wrapper for repo-agent work. It turns a
machine-readable work packet into a bounded worktree run with scope checks,
declared gates, structured reports, and an optional local commit candidate.

It is not a daemon, live swarm, product surface, dashboard, API, merge bot, or
push mechanism. It does not run autonomous loops.

## Work Packet

The first supported packet format is JSON. YAML is accepted only when PyYAML is
already installed; AgentOps v0 does not add dependencies.

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

## Reports

Each non-dry run writes:

```text
reports/agentops/<job_id>/<timestamp>/report.json
reports/agentops/<job_id>/<timestamp>/report.md
```

Reports include the job id, base ref, branch, worktree, intent, scope patterns,
changed files, untracked files, gate exit codes and output, final git status,
commit hash when created, and human approval flags.

## Commit Policy

AgentOps may create a local commit candidate only when:

- `commit.allowed` is true
- every gate exits 0
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
