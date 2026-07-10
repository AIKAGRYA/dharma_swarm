# Titanium-Grade Repository Hardening Plan

**Doc role (per `docs/AGENTS.md`):** `working_plan` — a bounded internal-hardening campaign, not repo-level authority. It creates no new runtime substrate or governance owner and remains subordinate to `CLAUDE.md`, `docs/governance/ACTIVE_TRACK.yaml`, and the canonical document stack.

## Main purpose

1. Make every repository verification signal truthful, reproducible, and failure-sensitive on a clean clone.
2. Raise security, runtime correctness, state integrity, typing, testing, and wiring to an independently credible enterprise standard.
3. Establish a trusted internal substrate before permitting new product features, venture cells, or live self-evolution.

## Objective

The repository itself is the product until an independent engineer can clone, understand, test, deploy, and trust it without access to the author's machine.

GitHub stars are not an engineering acceptance criterion. Public reproducibility, secure defaults, explicit ownership, recoverable state, and trustworthy verification are.

## Titanium-grade standard

The repository must be:

- secure by default;
- hermetic and reproducible;
- fully testable from a clean clone;
- failure-sensitive, with no false-green checks;
- crash-recoverable;
- explicit about state ownership;
- typed at public boundaries;
- observable without reading raw logs;
- free of hidden author-machine dependencies;
- behaviorally tested rather than existence-tested;
- modular enough for independent contributors; and
- honest about `LIVE`, `PARTIAL`, and experimental surfaces.

## Best next long-running goal

### Make `main` truthfully green from a clean clone

This precedes runtime hardening because the adversarial audit found that the measuring instruments themselves are not yet consistently trustworthy:

- `verifier-selfcheck` reported `ALL GATES FUNCTIONAL` while `make test-fast` was broken;
- missing Semgrep was treated as a successful skip;
- CI required-check definitions disagreed;
- a duplicate JSON key silently removed pytest and gitleaks classifications;
- strict DocOps was red while the PR check was green;
- Go presence was mistaken for Go compatibility;
- `uplift-guards` could wait indefinitely on stdin; and
- repository verification and live-host readiness were mixed together.

Until these are corrected, later green results remain provisional.

## Phase 0 — Verification truth

Phase 0 should land as several reviewable PRs under existing surface owners. It must not become one giant hardening PR or a new catch-all framework.

### 0.1 Hermetic bootstrap

- Pin and install Python, Go 1.26, Bun, Node, Semgrep, and gitleaks.
- Use the existing lockfiles in every test and deployment lane.
- Remove dependency-installation paths that suppress failure with `|| true`.
- Ensure one bootstrap command works on a fresh Linux clone.
- Remove reliance on user-site packages, shell profiles, and author-local paths.

### 0.2 Repair the verifier

- Make `verifier-selfcheck` execute meaningful behavioral tests or narrow its success claim.
- Diagnose and fix the suite-order or resource leak causing the deterministic ten-second timeout.
- Probe Go version and module compatibility, not merely `which go`.
- Close stdin and add bounded timeouts to governance subprocesses.
- Make missing required tools fail rather than skip green.

### 0.3 Separate hermetic and live verification

Repository CI must not depend on a live daemon receipt.

- The hermetic lane owns code, tests, contracts, static analysis, and fixtures.
- The live-host lane owns NATS freshness, daemon receipts, provider keys, and VPS state.
- Live requirements report explicit `NEEDS_HOST`, never `PASS` and never an ambiguous failure.
- Existing state and receipt owners remain authoritative; this phase creates no new truth store.

### 0.4 Unify CI authority

- Remove duplicate JSON keys.
- Establish one required-check manifest consumed by CI Truth, automerge, Merge Master Mike, and parity checks.
- Verify the manifest against actual branch protection.
- Reject reviews bound to stale heads.
- Ensure manual Mike dispatch cannot proceed when required checks are absent.
- Decide and enforce the human-review policy explicitly.

### 0.5 Restore strict DocOps

- Make strict DocOps pass on `main`.
- Fix the rolling reconciliation PR so force-updates trigger checks.
- Stop snapshot PR accumulation.
- Require generated counts to be reproducible, current, and independently checked.

## Phase 0 exit gate

All commands below must complete from a fresh clone:

```bash
make verifier-selfcheck
make test-fast
make test
make lint-blockers
make governance-all
make go-ci
make docops-report
python3 scripts/governance/check_track_status.py
npm --prefix dashboard ci
npm --prefix dashboard run lint
npm --prefix dashboard run build
bun --cwd terminal install --frozen-lockfile
bun --cwd terminal test
git status --short
```

The exit gate permits no unexplained skips, stale evidence, missing tools, dirty files, or success claims broader than the commands actually prove.

## Subsequent priorities

### Phase 1 — Security boundaries

- Require authentication for REST, GraphQL, WebSockets, and webhooks.
- Require TLS for publicly bound services.
- Add boundary validation, bounded inputs, and rate limiting.
- Remove arbitrary shell execution from untrusted proof and scorer paths.
- Route every source mutation path through the one-door promotion authority.

### Phase 2 — Runtime correctness

- Replace the strict `exactly-once` claim with precise side-effect semantics.
- Add provider-backed idempotency or transactional outbox boundaries where possible.
- Introduce daemon ownership fencing.
- Add crash injection at each dispatch and receipt window.
- Define backpressure, retry budgets, quarantine, and terminal failure behavior.

### Phase 3 — State integrity

- Declare canonical ownership for tasks, claims, runs, ontology, memory, and receipts.
- Replace inline best-effort schema edits with versioned migrations.
- Make cross-store transitions explicit and consistency-checked.
- Test backup and restoration onto an empty host.
- Eliminate hidden local-state prerequisites.

### Phase 4 — Wiring truth

- Classify every claimed component by reachable production entrypoint.
- Remove dead or duplicate implementations.
- Mark optional and experimental paths explicitly.
- Convert live wiring claims into behavioral acceptance tests.
- Close interface mismatches rather than guarding permanent split-brain behavior.

### Phase 5 — Maintainability

- Decompose the highest-centrality god modules first.
- Eliminate silent exception swallowing from critical paths.
- Introduce strict typing incrementally at public and stateful boundaries.
- Replace private cross-module coupling with narrow typed interfaces.
- Keep refactoring behavior-preserving and mutation-tested.

### Phase 6 — Test quality

- Expand mutation testing across the trusted computing base.
- Add concurrency, crash, migration, restore, and deployment tests.
- Replace import-only and file-existence criteria with behavior-sensitive checks.
- Generate and verify API contracts across backend, dashboard, and terminal clients.
- Measure test effectiveness, not only test count.

### Phase 7 — Open-source readiness

- Provide a reproducible quickstart.
- Publish stable architectural boundaries and public APIs.
- Add a security policy, release process, dependency update policy, and SBOM.
- Ensure examples and deployment instructions work from clean environments.
- Make contributor workflows independent of private operator state.

## Frozen work

Until Phase 0 closes:

- no new product features;
- no new governance frameworks;
- no new venture cells;
- no live self-evolution;
- no additional dashboards;
- no capability marketing; and
- no broad aesthetic refactors.

The immediate objective is narrow and foundational: make the repository capable of telling the truth about itself.

## Campaign completion condition

The internal-hardening campaign is complete only when an independent engineer can:

1. clone and bootstrap the repository without private state;
2. run every required verification lane successfully;
3. identify one canonical owner for every durable state transition;
4. reproduce crash, recovery, migration, and restore behavior;
5. verify all externally reachable boundaries are secure by default;
6. trace every production claim to a reachable path and failure-sensitive test; and
7. make a bounded contribution without reading or modifying a god module unrelated to the change.
