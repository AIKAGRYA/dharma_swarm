# SPEC-001 v2: Mechanical Hardening — Reality-Grounded Rewrite

**Role:** `working_plan` (per `docs/AGENTS.md` document types). Not canon, not
an active_spec until approved through the normal admission path.
**Status:** DRAFT, pending operator approval.
**Supersedes:** SPEC-001 v1 (received via operator paste, never committed).
v1 is not revised but replaced; its factual premises failed audit.
**Audit basis:** read-only audit of `AIKAGRYA/dharma_swarm` @ `ed0ed1801`
(branch `vision/command-fused-20260813`, dirty tree) and
`AmitabhainArunachala/vibe-halt` @ `dfc0551` (branch
`claude/track2-w4-clockskew-honesty`), 2026-08-18.

---

## 0. Corrections Register — what v1 got wrong

Every module named in v1 exists. Almost every "current state" description was
wrong. This register is the reason v2 exists.

| v1 claim | Verified reality |
|---|---|
| `gnani_lodestone.py` is regex/keyword heuristics, "60% slop", refactor into AST policy engine | It is a boot-time **content seeder** (`GnaniLodestone.seed_all()`, 607 lines) injecting philosophical marks/objectives into `StigmergyStore`/`ConceptGraph`/`TelosGraph`/`TaskBoard`. Zero AST analysis. No `IntentPayload`/`GnaniReceipt` type exists anywhere in the repo. |
| `samvara.py` is a rate limiter, "20% slop" | It is a HOLD-cascade **diagnostics engine** (`SamvaraEngine.on_hold()`, 523 lines). Rate limiting and token budgets already exist at `providers.py:547` and `orchestrator.py:1145`. |
| `.github/workflows/pudgala-rigor.yml` is slop CI | It exists (55 lines) and runs a real claim/evidence binding gate (`scripts/governance/check_claim_evidence_binding.py`, advisory Stage 0). It is one of **48 workflows**. |
| `anekanta_gate.py`/`jagat_kalyan.py` need multi-model consensus built | `anekanta_gate.py` is a working keyword-frame gate (Pydantic `AnekantaResult`, wired into `telos_gates.py`, `sheaf.py`). A real 3-model council already exists: `model_council_e2e.py` (581 lines, draft/critique/synthesis) plus `dharma_swarm/council/`. |
| `ouroboros.py`/`meta_daemon.py`/`loop_supervisor.py` are retry loops in costume | `loop_supervisor.py` is a genuine watchdog (stall detection, retry-storm windows, 4-rung intervention ladder). `ouroboros.py` does real behavioral-fitness scoring and AST profiling. Neither is self-modification — that part of v1's *goal* was correct. |
| `geometry.py`/`info_geometry.py`/`coalgebra.py` are "80% slop" math | All three contain real numpy mathematics: Björck–Golub principal angles via SVD, participation ratio, Fisher information estimation, natural gradient, F-coalgebra over the evolution pipeline. |
| Phase 1: build PyO3 bindings for vibe-halt | **Contradicts vibe-halt's recorded design.** The workspace is deliberately zero-dependency and hermetic (`unsafe_code = "forbid"`). PyO3/maturin appear nowhere. The Python runner in `clients/python/` was *removed* for fabricating evidence ("Python must never be a second simulator"); its own docstring commits to a **subprocess client of `vh-cli`** as the integration path. |
| Guardrail: every destructive Python action runs inside a vibe-halt cassette | Beyond current substrate capability. Cassettes record/replay **LLM requests inside Tier-2 subprocess runs** (`vh-sandbox`), not whole agent loops, filesystem writes, or git mutations. |
| Job 3: schema parity against JSON schemas in `corpus/SCHEMA.md` | `corpus/SCHEMA.md` is a Markdown table spec for bug-corpus entries. No JSON schemas exist in vibe-halt. |
| vibe-halt is a skeleton to be filled in | It is ~17.4k lines of working Rust: determinism kernel (`vh-core`), chain-hashed traces (`vh-trace`), fault injection (`vh-gremlin`, `vh-multiverse`), cassette sandbox (`vh-sandbox`), replay soak (`vh-verify`), delta-debugging shrink (`vh-shrink`), CLI (`vh-cli`). Compiles clean offline; 11-entry measured bug corpus. |

Additional repo-state facts that gate any implementation:

- dharma_swarm's working tree is **dirty** (10 modified tracked files) on a
  non-main branch. `make onboard` currently exits non-zero (broken register:
  9 open-like entries). Governance (`AGENTS.md`, `CLAUDE.md`) requires
  onboarding + `make agent-build-preflight PACKET=<path>` before edits.
- dharma_swarm already enforces anti-slop mechanically: 10 rules in
  `docs/governance/ANTI_SLOP_RULES.md` (Semgrep + 3 workflows, several
  hard-fail), a 54-pattern hygiene catalogue, module line budgets, and ~30
  governance check scripts. v1's "anti-slop AST linter" job must extend this
  machinery, not duplicate it.
- Pydantic v2 is already pervasive (`pydantic>=2.0` in `pyproject.toml`;
  155 importing files). No mypy/pyright gate exists in CI today.
- The NATS substrate is **local-observation-only** per `make onboard`:
  compatibility mirrors present, no live-transport proof. Any plan step that
  says "hot-reload into the live NATS registry" assumes transport that is not
  proven live.
- vibe-halt's remote is still `AmitabhainArunachala/vibe-halt`. The canon rule
  in `/Users/dhyana/AGENTS.md` mandates `AIKAGRYA` only for dharma_swarm;
  whether vibe-halt has also moved needs operator confirmation before any
  push/PR there.

---

## 1. Guardrails (revised)

1. **Zero-slop means conforming to the existing anti-slop system.** New code
   must pass the 10 existing rules and module budgets. Any new slop detector
   graduates through the documented hygiene pipeline
   (`VIBE_CODE_HYGIENE.md` → advisory → enforced rule), not a bespoke linter.
2. **Deterministic backstop, rescoped to what the substrate proves.**
   Phase 1 scope: agent LLM calls made *through the sandbox adapter* are
   cassette-recorded/replayed (Tier-2 honesty, per vibe-halt's own D2
   bounds). Filesystem/git/DB mutation capture is out of scope until
   vibe-halt ships a D1 backend; v2 does not pretend otherwise.
3. **Integration is subprocess, not FFI.** The bridge is a Python client of
   the `vh` binary (`vh run`, `vh sandbox-demo`, receipts), implementing
   dharma_swarm's existing `Sandbox` ABC (`dharma_swarm/sandbox.py:98`) as
   `VibeHaltSandbox` — exactly the integration both repos' docs already
   describe (vibe-halt `clients/python/`, Phase 4).
4. **Typing as ratchet, not big bang.** Pydantic v2 for all new interfaces
   (repo norm). If a static-typing gate is wanted, introduce it as a
   ratcheting CI job (new/changed files first), following the module-budget
   grandfathering precedent — `pyright --strict` across the whole tree in one
   step would fail on arrival and teach nobody anything.

---

## 2. Module directives (corrected)

Naming principle: keep philosophical names for **new** components where the
operator wants them; do not repurpose existing modules whose real jobs differ
from v1's descriptions.

### 2.1 Intent/policy evaluation — NEW module, not a `gnani_lodestone.py` rewrite

- `gnani_lodestone.py` stays a seeder. Its thin logic (idempotent CRUD
  wrapped in `try/except: return 0`) may be hardened in place, but it is not
  the policy engine v1 described.
- If an AST/policy intent gate is wanted, it is a new component (suggested
  name: `gnani_gate`) and must first dedupe against existing AST machinery:
  `foreman.py` (12 AST sites), `xray.py` (12), `quality_gates.py` (1003-line
  LLM-as-judge gate), `semantic_hardener.py`, `ouroboros.py`, plus
  `telos_gates.py`, `dogma_gate.py`, `promotion_gate.py`. Deliverable 0 of
  this work item is a written dedupe analysis, not code.
- Receipt type (`admitted: bool`, violations, content hash) is a Pydantic v2
  model in `models.py`, the repo's existing model hub.

### 2.2 Circuit breakers — consolidate onto existing primitives

- `samvara.py` stays the HOLD-cascade diagnostics engine. Open question for
  the operator: either (a) make `SamvaraEngine` *execute* its own
  `corrections` (today it diagnoses but never acts), or (b) formally scope it
  as diagnostic-only. That decision belongs in its own micro-PR.
- Token/recursion/rate circuit-breaking belongs with the existing primitives:
  `providers.py:547` (429 backoff) and `orchestrator.py:1145`
  (`context_token_budget`). A `Samvara*`-named governor façade may unify
  them, but note `providers.py` is grandfathered under Rule 10 at 3,096 lines
  (ceiling 3,405) — net-new lines there are rationed.
- Recursion clamp: sub-agent delegation depth is not currently tracked as a
  hard invariant; adding it is legitimate new work, small and real.

### 2.3 CI — extend, dedupe, delete nothing blindly

- `pudgala-rigor.yml` already runs the claim/evidence binding gate; v1's
  replacement text would have destroyed a working check. Extend it (or a
  sibling workflow) instead.
- Before adding any job, map it against the existing 48 workflows
  (`semgrep.yml`, `module-budget.yml`, `kernel-import-boundary.yml`,
  `quality-ratchet.yml`, `hermetic.yml`, …). Several of v1's proposed jobs
  partially exist.
- Rust parity job (run vibe-halt `cargo test --workspace --all-targets` in
  dharma_swarm CI) is legitimate **once the Phase 1 adapter exists** — before
  that it tests a repo this one doesn't depend on.
- "Schema parity" is redefined: generate JSON Schemas from the new Pydantic
  receipt models and pin them against `vh-trace`'s
  `docs/specs/TRACE_FORMAT_V0.md` receipt fields in a test. There are no
  upstream JSON schemas to diff against.

### 2.4 Consensus — extend `model_council_e2e.py`

- Add pairwise semantic divergence scoring (embedding distance) and a
  configurable agreement threshold to the existing council harness
  (`model_council_e2e.py`, draft/critique/synthesis, ≥3 models, A2A control
  plane). Do not build a parallel dispatcher inside `anekanta_gate.py`.
- `anekanta_gate.py` remains the cheap keyword-frame pre-filter it is.
- Destructive-action arbitration (`jagat_kalyan` directive in v1): before
  building, verify against the existing gate stack (`telos_gates.py`,
  `quality_gates.py`, guardian crew) what already intercepts destructive tool
  calls. Two-phase approval for destructive mutations is new and legitimate;
  raw-`rm -rf` detection partially exists in Semgrep rules already.

### 2.5 Strange loop — wire the real watchdog to the real shrinker

- `loop_supervisor.py`'s intervention ladder (LOG_WARNING → PAUSE_LOOP →
  REDUCE_SCOPE → ALERT_DHYANA) is the correct hook point. On repeated task
  failure, hand the failing workload to `vh-shrink` **via the Phase 1
  subprocess adapter** and attach the minimized trace to the alert.
- Meta-agent patch generation and sandbox revalidation become possible only
  after Phase 1; sequence accordingly.
- "Hot-reload into the live NATS registry" is **deferred**: `make onboard`
  reports NATS as local-observation-only. Reintroduce when live transport is
  proven, or reframe as registry-file update + restart.

### 2.6 Math middleware — wiring, not rewriting

- `geometry.py`, `info_geometry.py`, `coalgebra.py` already implement real
  mathematics. The work is connecting them to routing/memory decisions
  (which v1 correctly identified as missing) and adding a KL-divergence
  utility (Fisher metric exists; explicit KL was not found in audit).
- Each wiring site needs a witness: a test showing a routing decision that
  changes because the geometry signal exists.

---

## 3. Roadmap (revised)

| Phase | Scope | Done-when (verifiable) |
|---|---|---|
| **0** | Repo hygiene: clean or branch-isolate the dirty tree; repair the 9 open-like broken-register entries so `make onboard` exits 0; confirm vibe-halt canonical remote; run `make agent-build-preflight` for the first packet | `make onboard` green; branch plan written in the packet |
| **1** | Subprocess bridge: `VibeHaltSandbox` implementing `dharma_swarm/sandbox.py:98 Sandbox(ABC)`; Pydantic v2 receipt models mirroring `vh-verify`/`vh-sandbox` receipts; home per vibe-halt's plan (`clients/python/`) or a dharma_swarm adapter module — decide in packet | An agent workload runs through the adapter; cassette replay of its LLM calls passes; receipts validate against the Pydantic models; tests pass under existing CI |
| **2** | Circuit-breaker consolidation (2.2) + `gnani_gate` dedupe analysis and, if justified, implementation (2.1) | Delegation-depth clamp halts a >5-deep spawn in test; dedupe analysis doc committed before any new gate code |
| **3** | Consensus divergence metrics in `model_council_e2e.py` (2.4); `loop_supervisor` → `vh-shrink` handoff (2.5) | A seeded council disagreement is measured and blocks completion below threshold; a shrunk failing trace is attached to a supervisor alert in test |
| **4** | Geometry/info-geometry routing wiring with witnesses (2.6); typing ratchet CI if still wanted | Each wired signal has a test proving a decision changed; ratchet job green on new files |

No durations are assigned. v1's week numbers were fiction; these phases gate
on evidence, not calendar.

---

## 4. What v2 deliberately dropped from v1

- PyO3/FFI bridge (contradicts substrate design; subprocess chosen instead).
- "Every destructive action in a verified cassette" (substrate can't; Tier-2
  LLM-call cassettes only, honestly bounded).
- Rewrites of `gnani_lodestone.py`, `samvara.py`, the math modules (their
  v1 descriptions were wrong; their real deficits are smaller and specific).
- Wholesale replacement of `pudgala-rigor.yml` (it works).
- Slop percentages as a metric. "60% slop" is not measurable; the repo's
  enforced anti-slop rules and hygiene catalogue are.
