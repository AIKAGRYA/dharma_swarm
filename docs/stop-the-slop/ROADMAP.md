# Pramāṇa Probe — Roadmap (self-generated backlog)

We do **not** source prompts by scraping anyone's catalog. The topics below are
derived from first principles and the CS/cog-sci canon (`FOUNDATIONS.md`) — the
common, durable failure modes of software. Each becomes a prompt the same way:
name the invariant, root it in a lineage, **route to ground truth**, **run it on
this repo**, and **return clean** when clean. A cron can crank one per tick with
no human paste step.

Status: ✅ shipped · ▶ next · ◻ backlog

## Shipped (13)
01 dependency-risk-triage ✅ · 02 circular-dependency-triage ✅ ·
03 performance-bottleneck-triage ✅ · 04 retry-audit ✅ · 05 seed-data-generator ✅ ·
06 error-handling-rules ✅ · 07 minimal-repro-builder ✅ + bug-trace-before-fix ✅ ·
08 feature-flag-wrap ✅ · 09 dead-code-scan ✅ · 10 hardening-checklist ✅ ·
11 onboarding-brief ✅ · 12 recording-to-sop ✅(drafted)

## Backlog — by theme (invariant · lineage)

### Concurrency & correctness
- ▶ **race-condition-audit** — shared mutable state crossed by concurrent paths is a bug until proven serialized · *Lamport happens-before '78*
- ◻ **idempotency-key-audit** — every retried mutation needs an idempotency key or it double-applies · *REST idempotency; Nygard*
- ◻ **deadlock-lock-order** — locks acquired in inconsistent order can deadlock; prove a global order · *Dijkstra (dining philosophers); Coffman conditions*

### Data & queries
- ▶ **n-plus-one-query-scan** — a query inside a loop over rows is O(n) round-trips; the canonical ORM perf bug · *Codd; route to query logs/EXPLAIN*
- ◻ **migration-safety** — a schema change must be backward-compatible with the running version (expand/contract) · *Lehman's laws; zero-downtime deploy*
- ◻ **cache-invalidation-audit** — every cache needs a correct, bounded invalidation; staleness is a correctness bug · *Phil Karlton's "two hard things"*
- ◻ **transaction-boundary-audit** — multi-write operations must be atomic or compensating; partial writes corrupt state · *Gray (ACID)*

### API & contracts
- ◻ **api-breaking-change-detector** — your own API has a semver contract; flag breaking changes to callers · *Hyrum's law; Meyer DbC*
- ◻ **boundary-input-validation** — validate/normalize all input at the trust boundary, once · *Saltzer–Schroeder; Postel (carefully)*

### Security
- ◻ **authz-coverage** — every mutation/read of protected data must pass an authorization check; find the ungated ones · *Saltzer–Schroeder least privilege*
- ◻ **secret-leakage-scan** — secrets in code/logs/responses; route to a real scanner (gitleaks), not regex vibes · *Kerckhoffs; defense in depth*
- ◻ **injection-ssrf-surface** — untrusted input reaching a sink (SQL, shell, URL fetch) · *taint analysis; OWASP*

### Observability
- ◻ **logging-context-audit** — every error log carries operation + scoping IDs + cause; find the blind spots · *Gray; structured logging*
- ◻ **critical-path-instrumentation** — the paths that matter have metrics/traces; rank by user impact · *Gregg USE method*
- ◻ **pii-in-logs-scan** — personal data must not land in logs; find the leaks · *privacy-by-design*

### State & lifecycle
- ◻ **resource-leak-scan** — files/sockets/connections opened without guaranteed cleanup · *RAII; Dijkstra*
- ◻ **stale-closure-effect-deps** (frontend) — effects/closures capturing stale state; the React footgun · *referential transparency*
- ◻ **graceful-shutdown-audit** — in-flight work drained on shutdown; no torn state · *Gray; crash-only software (Candea–Fox)*

### Tests
- ◻ **flaky-test-detector** — sources of nondeterminism (time, order, network, randomness) · *Dijkstra (testing shows presence); run-to-run diff*
- ◻ **coverage-gap-by-risk** — coverage ranked by code risk, not % · *Weyuker; mutation testing*
- ◻ **assertion-quality-audit** — tests that run but assert nothing meaningful (the "asserts presence" caveat made real) · *Goodenough*

### Invariant & contract discovery (theme 13)
- ◻ **invariant-extractor** — infer the implicit pre/postconditions a function relies on; surface the unstated ones · *Hoare '69; Daikon (Ernst)*

### Drift & entropy control (theme 14)
- ◻ **doc-code-drift** — docs/comments that contradict the code they describe · *Lehman; Knuth literate programming*
- ◻ **config-drift-audit** — config/env that diverges across environments · *Shannon entropy; 12-factor*

### Comprehension & structure
- ◻ **coupling-hotspot-map** — fan-in/fan-out hotspots; the modules a change ripples through · *Parnas; Martin (instability metric)*
- ◻ **god-object-decomposition-plan** — a single-responsibility decomposition for an oversized module (e.g. this repo's 5,255-line file) · *Parnas; SRP*

## Cron contract (proposed)
One tick = pick the top ▶/◻ item → derive the prompt (invariant + lineage) →
**run it on `dharma_swarm/` for a real demo** → save under its theme → commit to
the library branch → mark it ✅ here. No human paste step. Unattended, reviewable
by diff. Cadence and item-cap operator-set.
