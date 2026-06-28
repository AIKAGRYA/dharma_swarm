# Pramāṇa Probe — Roadmap (self-generated backlog)

We do **not** source prompts by scraping anyone's catalog. The topics below are
derived from first principles and the CS/cog-sci canon (`FOUNDATIONS.md`) — the
common, durable failure modes of software. Each becomes a prompt the same way:
name the invariant, root it in a lineage, **route to ground truth**, **run it on
this repo**, and **return clean** when clean. A cron can crank one per tick with
no human paste step.

Status: ✅ shipped · ▶ next · ◻ backlog

## Shipped (19)
dependency-risk-triage ✅ · circular-dependency-triage ✅ · coupling-hotspot-map ✅ ·
god-object-decomposition-plan ✅ · performance-bottleneck-triage ✅ · retry-audit ✅ ·
seed-data-generator ✅ · error-handling-rules ✅ · minimal-repro-builder ✅ ·
bug-trace-before-fix ✅ · feature-flag-wrap ✅ · dead-code-scan ✅ ·
hardening-checklist ✅ · onboarding-brief ✅ · recording-to-sop ✅(drafted) ·
n-plus-one-query-scan ✅ · resource-leak-scan ✅ · secret-leakage-scan ✅ ·
logging-context-audit ✅

**+batch 6 (7):** ⭐ ai-slop-index (FLAGSHIP) · complexity-inflation-scan ·
duplication-ratio-scan · wildcard-import-audit · test-mirrors-implementation ·
ai-agent-security-audit · interface-replaceability-audit — **26 shipped total.**

**+batch 7 (7):** race-condition · flaky-test · llm-call-hygiene · migration-safety ·
doc-code-drift · invariant-extractor · pii-in-logs.

**+batch 8 (16) — v0.0.1 COMPLETE:** idempotency-key · deadlock-lock-order ·
cache-invalidation · transaction-boundary · api-breaking-change · boundary-input-
validation · authz-coverage · injection-ssrf · critical-path-instrumentation ·
stale-closure-effect-deps · graceful-shutdown · coverage-gap-by-risk ·
assertion-quality · config-drift · legacy-modernization · compliance-pii-readiness.

## ✅ v0.0.1 COMPLETE — 49 prompts across 25 themes + flagship
The curated first-principles backlog is fully built. Every item ran on
`dharma_swarm` ground truth. Further growth comes from new angles (`SOURCES.md`)
and operator requests, not from padding. The cron/next-session continues any
new angles added below.

_(backlog markers below are historical; all are now ✅.)_

## v0.1.0 — SHIPPED: the runner (from adversarial review)

An external reviewer ran 5 prompts and found the cardinal sin: 2 of 5 demos didn't
reproduce (complexity used a homemade proxy instead of the named `radon`; the cycle
"shipped→0" was true only on an unmerged branch; the flagship overstated ratchet
coverage 4→2 and mixed scopes). All three are corrected **and** an executable runner
is shipped so demos are run, not trusted.

- ✅ **runner shipped: `probe/`** — a package (`_common.py`, `signals.py`, `probe.py`,
  `test_probe.py`) covering **13 signals**, each routed to its real instrument (radon,
  npm/pip audit, git log, AST+Tarjan, `vulture`, PyPI). It operationalizes the
  confidence rubric, enforces return-clean, and has **6 self-tests** proving
  return-clean AND detection (incl. the `TYPE_CHECKING`-exclusion and Type-1 clone
  cases). (Supersedes the first-cut `runner/slop_probe.py` from v0.0.2, now folded in.)
- ✅ **confidence rubric** — HIGH/MEDIUM/LOW/UNASSESSED defined in `FOUNDATIONS.md`;
  the vibe knob is gone.
- ✅ **demos regenerated from runner output** for the flagship and the corrected
  prompts (complexity, circular-deps, duplication, dead-code), plus the three new
  dimensions.
- ▶ **runner: every remaining prompt** — extend `probe/signals.py` to the prompts that
  still carry hand-written demos; regenerate each from runner output. (Now at 13:
  added `cycles` via AST+Tarjan and `duplication` via structural clone clustering;
  `dead_code` routed to `vulture`.)
- ◻ **advisory-DB provenance** — pin advisory IDs + snapshot date in security/dep demos.
- ◻ **CI wiring** — wire the runner's RED exits into a check.
- ✓ **clean-repo + non-Python/JS demos** — SHIPPED (v0.1.1, `26-portability/`): a clean Python repo grades CLEAN (RED0/AMBER0/GREEN13); ripgrep (99 `.rs`, 0 `.py`) gets honest UNASSESSED on all 10 Python-AST signals while god-objects (line count) and churn/co-change (git) travel. Includes a before/after showing the pre-fix runner called a 7,779-line Rust file "clean." Two return-clean fixes: `coupling`/`broad_catches` can now grade GREEN, not pinned at AMBER.

## v0.1.0 — proposed angles (operator greenlight before building)

Genuine future angles, each with a real invariant + lineage + a runnable demo on
this repo. **Not built** — listed here so growth stays vetted, never padded.

- ◻ **accessibility-audit** (frontend) — WCAG: every interactive element keyboard-
  reachable + labeled; the dashboard is real UI · *WCAG; POUR principles*
- ◻ **unbounded-growth-scan** — data structures that grow without a bound (lists/dicts/
  queues that only append) — a slow OOM distinct from resource leaks · *bounded resources*
- ◻ **missing-index-inference** — queries whose WHERE/JOIN columns lack an index; route to
  EXPLAIN, never guess · *Codd; query planner as ground truth*
- ◻ **type-coverage / any-creep** — untyped escape hatches (`Any`, `# type: ignore`,
  untyped defs) that defeat the type checker · *Milner (types); gradual typing*
- ◻ **feature-flag-debt** — stale flags long past rollout (the removal breadcrumb from
  `feature-flag-wrap`, now overdue) · *Lehman; flag lifecycle*
- ◻ **build-reproducibility** — same source → same artifact; unpinned deps / timestamps /
  ordering defeat it · *reproducible-builds.org; supply-chain integrity*
- ◻ **slo-error-budget** — are the critical paths' SLOs defined and measured? · *Google SRE*
- ◻ **logging-level-hygiene** — DEBUG/INFO/ERROR used correctly; log spam vs silence · *Gray*
- ◻ **i18n-readiness** — hardcoded user-facing strings, locale-unsafe formatting · *Unicode/CLDR*

(The armed cron is instructed to no-op when the v0.0.1 backlog is empty — it will not
build these until they're moved above the line by operator greenlight.)

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

### From the landscape survey (see SOURCES.md) — new angles
- ◻⭐ **ai-slop-index** (**FLAGSHIP**) — score AI-generated slop via *measurable* signals: duplication ratio, complexity inflation, test-mirrors-implementation, architectural coherence, dead code, wildcard imports. The brand keystone — composes several existing prompts into one index. · *Larridin AI Slop Index; arXiv 2508.14727 (Wildcard #1, dead code 34–42%)*
- ◻ **ai-agent-security-audit** — prompt-injection / tool-permission / agent attack surface (run on dharma_swarm's own agent layer) · *doneyli 5-phase; OWASP LLM Top 10*
- ◻ **interface-replaceability-audit** — can an implementation be swapped without ripple? seams over entanglement · *Eskil Steenberg; Parnas*
- ◻ **wildcard-import-audit** — `import *` / re-export sprawl; the #1 measured AI smell · *arXiv 2508.14727*
- ◻ **test-mirrors-implementation** — tests that assert structure not behavior (the "asserts presence" caveat, sharpened) · *Goodenough; Weyuker*
- ◻ **duplication-ratio-scan** — copy-paste clusters; a core slop signal · *Fowler (duplication = #1 smell)*
- ◻ **complexity-inflation-scan** — cyclomatic/cognitive complexity vs necessity · *McCabe '76; Cognitive Complexity (Campbell)*
- ◻ **legacy-modernization-plan** — risk areas + cleanup priorities + AI-ready context pack · *Feathers (Working Effectively with Legacy Code)*
- ◻ **compliance-pii-readiness** — PII handling, retention, audit-log presence (code-level, not legal advice) · *GDPR/data-minimization; Saltzer–Schroeder*
- ◻ **llm-call-hygiene** — for codebases that *call* LLMs: token budgets, prompt-injection at the call site, retry/idempotency, cost caps · *OWASP LLM Top 10; Nygard*

## Cron contract (proposed)
One tick = pick the top ▶/◻ item → derive the prompt (invariant + lineage) →
**run it on `dharma_swarm/` for a real demo** → save under its theme → commit to
the library branch → mark it ✅ here. No human paste step. Unattended, reviewable
by diff. Cadence and item-cap operator-set.
