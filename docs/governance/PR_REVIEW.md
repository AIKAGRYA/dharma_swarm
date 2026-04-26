# PR Review (CodeRabbit) and Dependency Updates (Renovate)

Phase 3 of the governance install adds two SaaS integrations.
Both require **one-time GitHub App authorization** by the repo owner.

## CodeRabbit (PR review)

### Setup (manual, one-time)

1. Visit https://www.coderabbit.ai
2. Sign in with the GitHub account that owns `AmitabhainArunachala/dharma_swarm`.
3. Authorize the CodeRabbit GitHub App on this repo (granular scope).
4. Free tier: unlimited reviews on public repos, 14-day trial on private.
5. Confirm the app is installed: GitHub → repo → Settings → Integrations.

The `.coderabbit.yaml` at repo root takes effect on the next PR open.

### What it does

On each PR opened against `main`, `promote/**`, or `governance/**`:

1. Posts a high-level summary of changes.
2. Walks the diff with inline comments. Path-level instructions in
   `.coderabbit.yaml` direct the reviewer to look for specific
   dharma_swarm anti-patterns:
   - `tests/**` → flag default `RuntimeStateStore()` instantiation
   - `dharma_swarm/swarm.py` → flag worktree-mirror divergence
   - `dharma_swarm/orchestrator.py` → flag duck-typed pool calls
   - `dharma_swarm/providers.py` → flag bypassed provider factory
   - `scripts/**` → flag `git add -A` and `shell=True`
   - `.github/workflows/**` → flag tag-pinned actions and unsafe perms
3. Runs bundled static analyzers (`ruff`, `semgrep` on `.semgrep`,
   `gitleaks`, `actionlint`, `markdownlint`, `yamllint`) and surfaces
   their findings inside the PR conversation.

### Driving CodeRabbit explicitly

```
@coderabbit summary
@coderabbit review
@coderabbit resolve
@coderabbit help
```

The config sets `chat.auto_reply: false` so CodeRabbit only responds
to explicit `@coderabbit` mentions; otherwise it's quiet after the
initial review post.

### Tuning false positives

Edit `.coderabbit.yaml`:

- Add path entries to `path_filters` to ignore additional dirs.
- Edit `path_instructions` to refine what the reviewer looks for in
  a specific area.
- Switch `profile: chill` → `assertive` for stricter review when
  collaborators are added.

## Renovate (dependency updates)

### Setup (manual, one-time)

1. Visit https://github.com/apps/renovate
2. Install on `AmitabhainArunachala/dharma_swarm` (granular scope).
3. Renovate opens a "Configure Renovate" onboarding PR; merge or close
   (`renovate.json` already exists at repo root, so onboarding is a no-op).
4. Renovate creates a `dependency dashboard` issue showing all
   outdated deps and update plans.

### What it does

- Scans `pyproject.toml`, `requirements-dev.txt`, `requirements-ginko.txt`,
  and `setup.py` for outdated Python packages.
- Scans `.github/workflows/**` for outdated GitHub Actions.
- Opens up to 3 concurrent PRs (configurable) on Monday mornings (Asia/Makassar TZ).
- Pins GitHub Actions to commit SHAs (`pinDigests: true`) so a re-tag
  cannot silently change CI behavior.

### Package rules summary (`renovate.json`)

| Group | Packages | Behavior |
|---|---|---|
| testing toolchain | `pytest*`, `hypothesis*` | Single grouped PR weekly |
| LLM provider SDKs | `anthropic`, `openai`, `ollama`, `litellm` | Grouped PR; 3-day minimum age; manual merge |
| ML stable surface | `torch`, `transformers`, `accelerate`, `transformer-lens`, `sae-lens`, `nnsight` | Major bumps disabled (manual override only) |
| FastAPI stack | `fastapi`, `pydantic`, `uvicorn` | Major bumps wait 14 days |
| GitHub Actions | all | Pin to commit SHA, weekly schedule |

### When a Renovate PR fails CI

- Phase 2 CI gates (CodeQL, Semgrep, Gitleaks, tests) run on every
  Renovate PR. Failed gates surface inline; do not merge until green.
- For test failures from a transitive change: roll forward
  (fix the test) rather than disabling the package update.
- For a CodeQL alert from a new package: triage in the Security tab,
  then either fix or allowlist with justification.

### Vulnerability alerts

`vulnerabilityAlerts.enabled: true` makes Renovate open security PRs
the moment a vuln is published (no schedule wait). Labeled `security`,
`renovate`. Triage same-day for CRITICAL/HIGH severity.

## Skipped intentionally

- **Qodo Merge / PR-Agent**: redundant with CodeRabbit on this repo.
  Reconsider if CodeRabbit's review quality drops below threshold.
- **Cursor Bugbot**: requires Cursor IDE; this codebase is Claude Code.
- **Greptile**: deferred unless Sourcegraph (Phase 5) proves insufficient.
