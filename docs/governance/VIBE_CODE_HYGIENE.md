# VIBE-CODE HYGIENE — ANTIPATTERNS & DETECTION

**Purpose:** Catalogue the failure modes that are specific to (or dramatically
amplified by) LLM-assisted coding, and provide a runnable scan that surfaces
them in this repo. Companion to [`ANTI_SLOP_RULES.md`](ANTI_SLOP_RULES.md):
that doc owns the **10 CI-enforced rules**; this doc owns the **broader
catalogue of antipatterns** that we measure but do not yet gate on.

**Why these are different:** Anti-slop rules are hard CI gates (single
files, deterministic checks). Vibe-code hygiene is the surrounding
ecosystem of softer signals — happy-path test bias, scaffolding accretion,
prompt-injection surface area, sync-in-async bugs — that accumulate when
many agents write code into one repo in rapid loops.

**Scope:** This doc names 54 antipatterns across 12 clusters. It does NOT
gate. It feeds a baseline scan (`scripts/governance/vibe_code_scan.sh`)
whose output lives in `reports/governance/vibe_code_baseline_*.txt` and
is read by `make onboard` so every agent lands aware of the current
posture.

**Owner:** This file lives in `docs/governance/` next to
`ANTI_SLOP_RULES.md`. The two are siblings. Promotion of an antipattern
from "measured" → "gated" means moving its detection from
`vibe_code_scan.sh` into `.semgrep/dharma-anti-slop.yml` or a workflow,
and adding a numbered entry to `ANTI_SLOP_RULES.md`.

---

## How to use this doc

| If you are... | Start here |
|---|---|
| A new agent landing in the repo | Read the **12 clusters** below to know what we measure |
| Opening a PR | Check the baseline scan in `reports/governance/` to see whether your PR regresses any signal |
| Triaging a regression alert | Find the cluster in this doc, read root cause and detection, then jump to the source bibliography |
| Considering a new CI gate | Find the cluster; if the signal is mature and the false-positive rate is low, promote to `ANTI_SLOP_RULES.md` |

The scan is intentionally **non-blocking**. It is a mirror, not a guard.
Gates that match the rule shape (single file, deterministic, low false
positive) live in `ANTI_SLOP_RULES.md`. Diffuse signals live here.

---

## Baseline measurement (2026-06-07)

The full baseline lives in [`reports/governance/vibe_code_baseline_2026-06-07.txt`](../../reports/governance/vibe_code_baseline_2026-06-07.txt).
Headline numbers worth knowing without opening that file:

| Cluster | Signal | This repo | Target |
|---|---|---:|---:|
| A — Test Theater | positive : exception assertion ratio | **71 : 1** | < 15 : 1 |
| A — Test Theater | trivial-shape assertions (`is not None` style) | **988** | reduce over time |
| A — Test Theater | mock references vs integration test files | **1,813 vs 19** | strengthen integration coverage |
| G — Agent Loop | `sleep()` calls in tests | **71** | < 20 |
| G — Agent Loop | bare/wide `except` blocks | **1,999** | every block must log or re-raise |
| G — Agent Loop | `except` followed by bare `pass` | **397** | should be near zero |
| G — Agent Loop | suppressions (`# type: ignore` / `noqa` / `pylint: disable`) | **214** | each one needs a comment why |
| C — Architecture | files in dharma_swarm/ root | **391** | trim toward subpackages |
| C — Architecture | grandfathered modules over 1000 lines | **11** | see umbrella issue #547 |
| F — Context Artifacts | files redefining `_utc_now()` | **71** | one shared `time_utils` helper |
| H — Performance | confirmed sync-in-async sites | **5** | should be zero (see list below) |
| E — Security | prompt-injection-shaped f-strings | **12** | each needs explicit sanitization or escape |

These are starting numbers. The doc evolves; the scan evolves; the numbers
trend down. Nothing here is a current PR-blocker.

---

## The 12 clusters

Each entry: **what it looks like**, **why LLM-assisted coding produces it**,
**how we detect it here**, **current instances in this repo (if any)**.

---

### Cluster A — Test Theater

Tests that exist but don't actually defend the invariant.

**Why amplified by LLMs:** LLMs are trained on test code where positive
assertions dominate. They optimize for visible coverage rather than
adversarial coverage. They produce assertion-shaped scaffolding that
passes without exercising the failure modes the function actually has.

**A1 — Happy-Path Tunnel Vision.** Tests assert success cases only;
exception paths, timeout paths, partial-failure paths untested.
*Detect:* ratio of `assert` to `pytest.raises`/`assertRaises`.
*Here:* 25,076 positive vs 352 exception (71:1). Industry guideline is <15:1.

**A2 — Assertion-Free / Trivially-True Tests.** Tests that assert only
that a result is not-None, is truthy, or is the right type — without
checking the actual computed value. *Detect:* grep for `assert.*is not None$`,
`assert result$`. *Here:* 988 such lines under `tests/`.

**A3 — Mock-Everything Isolation Theater.** Every dependency mocked, so
the test exercises the test scaffold rather than the code. Integration
counterpart missing. *Detect:* count of mock references vs integration
test files. *Here:* 1,813 mock references / 19 integration test files.

**A4 — Spec-Tautology Tests.** The test asserts what the function literally
does, line-by-line. Tautological and breaks on any non-behavioral change.
*Detect:* tests where assertion strings closely mirror function source.
Hard to grep — show up as PR-by-PR maintenance burden.

**A5 — Green CI Debt.** Mutation testing exposes that high coverage % does
not equal high mutation kill rate. *Detect:* run `mutmut` or `cosmic-ray`
on critical modules; targets are below 60% mutation kill rate.

---

### Cluster B — Documentation Pollution

Docs that drift from reality faster than humans can audit.

**Why amplified by LLMs:** LLMs generate aspirational documentation as a
default — "this module will/can/supports" — without verifying. They also
generate dense docstrings on trivial functions, inflating doc surface area.

**B1 — Hallucinated README Features.** README claims features that don't
exist in code. *Detect:* forward-looking language (`will be`, `coming soon`,
`planned`) plus diff against actual exports. *Here:* 0 in main README.

**B2 — Phantom Docstrings.** Every function has a docstring; many describe
behavior the function doesn't have. *Detect:* docstring count vs function
count; sample read of high-frequency files. *Here:* 9,833 docstrings /
10,539 function defs — saturated, but quality unaudited.

**B3 — Stale CHANGELOG Theater.** CHANGELOG updated as a ritual without
real diff awareness. *Detect:* CHANGELOG diff vs git log; ratio of human-
authored vs agent-authored entries.

**B4 — Comment-to-Code Ratio Inversion.** Trivial comments that translate
the line below them ("# increment counter"). *Detect:* grep for high-noise
comment shapes.

**B5 — Instruction File Bloat.** `CLAUDE.md` / `AGENTS.md` / `DEVIN.md`
grow without bound; nobody reads past line 200. *Detect:* line count and
imperative density per file. *Here:* `CLAUDE.md` 241 lines, `DEVIN.md`
410 lines — both within healthy bounds; do not exceed 500.

---

### Cluster C — Architectural Drift

Module shape that grows in directions a human architect would have refused.

**Why amplified by LLMs:** LLMs read the local context and produce code
consistent with it. They do not push back on emerging shapes — if a file
is already 4,000 lines, adding 200 more feels locally appropriate. The
push for architectural cohesion has to come from outside the loop.

**C1 — Layer-Bleed.** DB access in handlers; business logic in routing
modules; tests reaching into private state. *Detect:* import patterns
crossing layer boundaries.

**C2 — Interface Archaeology.** Multiple versions of the same concept
coexisting (`UserServiceV1`, `UserServiceNew`, `UserServiceLegacy`).
*Detect:* class names matching versioned/legacy/new/old patterns.
*Here:* 1 (`VentureCellV1`) — intentional venture cell scoping.

**C3 — Scaffolding Mountain.** Many tiny abstractions to "make testing
easier" that nothing else uses. *Detect:* count classes with a single
caller; count files with <50 LOC that import many siblings.

**C4 — God File Emergence.** Single files growing past sensible bounds.
*Detect:* `wc -l` ranked. *Here:* 11 files over 1,000 lines tracked under
Rule 10 (`ANTI_SLOP_RULES.md`) and umbrella issue #547.

**C5 — Dependency Inversion Collapse.** High-level modules depend on
low-level concrete classes. *Detect:* manual review of import graph in
`dharma_swarm/` root files.

**C6 — Circular Import Accumulation.** Lateral imports between sibling
modules until import order matters. *Detect:* internal import count per
file; >20 internal imports is a smell. *Here:* `dgc_cli.py` at 24.

---

### Cluster D — Phantom Dependencies

Code that depends on things that don't exist or that drift behind the ecosystem.

**Why amplified by LLMs:** LLMs predict plausible package names and APIs
based on patterns in training data. The plausibility filter is not strict
enough to catch hallucinated package names ("slopsquatting") or API
methods that were removed three minor versions ago.

**D1 — Slopsquatting.** LLM hallucinates a package name; attacker has
registered it on PyPI to deliver malware. *Detect:* for every new
dependency, verify via `pip index versions <pkg>` and check first-publish
date and download count.

**D2 — Dependency Explosion.** Each task pulls in a new library when an
existing one would do. *Detect:* compare top-level requirements over
time; flag rapid growth.

**D3 — Stale Dependency Pinning.** Pins without rationale; never updated.
*Detect:* `pip-audit` for CVEs. *Here:* `requirements-dev.txt` (5 deps,
all pinned), `requirements-ginko.txt` (4 deps, all pinned).

**D4 — Ghost API Hallucination.** Calls to methods that don't exist or
were removed. Specific to fast-moving libraries (OpenAI SDK, LangChain,
SQLAlchemy). *Detect:* known deprecated-pattern grep. *Here:* 1 OpenAI v0
pattern (worth a manual check); 5 `.query(` calls — verify they aren't
SQLAlchemy v1.

**D5 — Cross-Ecosystem Name Borrowing.** A `numpy`-named npm package gets
imported because the model confused ecosystems. *Detect:* lockfile audit.

---

### Cluster E — Security Regressions

LLM-written code skews toward features-without-defense.

**Why amplified by LLMs:** Tutorials in training data emphasize the
happy path. Defense-in-depth code (validation, authorization, rate
limiting) is comparatively rare in the training corpus, so models
under-produce it.

**E1 — Missing Input Validation (CWE-20).** User input flows into queries,
file paths, or shell commands without validation. *Detect:* `bandit -r`
for taint-style findings.

**E2 — Hardcoded Credentials.** Literal API keys, tokens, passwords in
source. *Detect:* `trufflehog`, `git-secrets`, or our internal heuristic.
*Here:* 0 heuristic matches; `trufflehog` recommended periodically.

**E3 — Missing Authorization Checks.** Route handlers return data without
checking that the caller is allowed to see it. *Detect:* ratio of route
declarations to authorization-check calls.

**E4 — Cryptographic Cargo Cult.** `hashlib.md5` / `hashlib.sha1` /
ECB-mode cipher used in security contexts. *Detect:* grep, then triage —
use for non-security caching/dedup is fine; use for password hashing or
signature is not. *Here:* 214 hits in scan, but **spot-checked sample is
content-hashing for caching and dedup** (`file_lock.py`, `memory_palace.py`,
`vector_store.py`) — false positives. Worth a once-a-year audit anyway.

**E5 — Prompt Injection in AI-Adjacent Code.** User input flows into LLM
system/user prompts via f-string without sanitization or boundary marker.
*Detect:* f-string regex over LLM-call modules. *Here:* 12 hits — each
needs a manual triage pass to confirm the input is from a trusted source
or is escaped.

**E6 — Overprivileged Database Access.** App connects as DB root/admin
when a least-privilege account would do. *Detect:* connection-string
review.

---

### Cluster F — Context-Window Artifacts

The model can't see the whole repo, so it duplicates.

**Why amplified by LLMs:** When a model can only see one or a few files
at a time, it tends to re-derive helpers locally rather than discover and
import the existing one. Over time the repo accretes near-duplicate
utilities.

**F1 — Amnesiac Refactoring.** Refactor in module A breaks module B
because the model didn't see B. *Detect:* test failures clustered at
boundaries; manual review.

**F2 — Copy-Paste Duplication Cascade.** Same utility function reimplemented
in many files. *Detect:* repeated function names across files. *Here:*
`_utc_now()` defined in **71 files**, `_utc_now_iso()` in 40, `_new_id()`
in 17, `_clamp01()` in 11. **This is the single highest-yield refactor in
the repo.** A shared `dharma_swarm/time_utils.py` + import alias would
collapse hundreds of lines.

**F3 — Context Contamination.** A long agent session bleeds the previous
task's conclusions into the next file the model touches. *Detect:* PR
diffs that touch unrelated files.

**F4 — Deprecated API Usage.** See D4. Distinct cause but overlapping
symptom — the model recalls an API that was current at training time.

**F5 — Naming Entropy.** Generic identifiers (`data`, `info`, `process`,
`handle`, `do`, `run`) at the function level. *Detect:* grep for
generic-name function definitions. *Here:* 6 — acceptable.

---

### Cluster G — Agent-Loop Pathologies

What happens when the agent is in charge of when to stop.

**Why amplified by LLMs:** Without external supervision, an agent loop
will rewrite, retry, work around, and over-fix until it hits a token
budget. The artifacts of that loop appear in the repo: suppressed
warnings, swallowed errors, deleted-then-recreated tests, low-information
commits.

**G1 — Runaway Token Burn.** Many low-value commits in a short window.
*Detect:* commits/day. *Here:* 62 commits on 2026-06-05, 2 on 2026-06-07,
1 on 2026-06-06. The 06-05 spike was a planned merge day; PR-throttle
(now via head-ref pattern matching, PR #543) keeps this in bounds.

**G2 — Workaround Accumulation (Scar Tissue Code).** Suppressed warnings,
bare excepts, skipped tests piling up without removal. *Detect:* count
suppressions, bare excepts, skip decorators. *Here:* 214 suppressions,
**1,999 bare/wide excepts**, 397 followed by bare `pass`, 8 skipped tests,
21 xfails. The bare-except number is the second-highest-yield refactor in
the repo.

**G3 — Feature Scope Creep.** Agent solves more than asked. *Detect:*
PR diff line count vs description scope; manual review.

**G4 — Non-Deterministic Test Chasing.** Tests use `sleep()` instead of
proper synchronization. *Detect:* sleep calls in tests. *Here:* 71 calls.

**G5 — Commit Message Fabrication.** Commit messages claim work the diff
doesn't reflect. *Detect:* manual; low-information shapes (`update code`,
`fix bug`, `improve things`). *Here:* 0 in last 200 commits — good.

**G6 — Agent Sycophancy.** Agent agrees with the operator's framing even
when it should push back. Operator-facing problem, not a code grep.
*Counter:* see Sub-Doctrine below.

---

### Cluster H — Performance Regressions

**Why amplified by LLMs:** LLMs produce idiomatic-looking code that
ignores cost. Async functions get sync calls inside them. List
comprehensions hide N+1 queries. Wrapping abstractions accumulate.

**H1 — N+1 Query Generation.** ORM call inside a loop. *Detect:* grep for
`session.query`/`session.execute` near `for ... in`.

**H2 — Synchronous Blocking in Async Contexts.** `time.sleep`,
`requests.get`, `subprocess.run` inside `async def`. *Detect:* AST scan.
*Here:* **5 confirmed sites**:
- `dharma_swarm/autoresearch_loop.py:507` — `subprocess.run` in async `_revert_module`
- `dharma_swarm/review_cycle.py:105` — `subprocess.run` in async `_section_tests`
- `dharma_swarm/roaming_dispatch_daemon.py:142` — `time.sleep` in async `run_loop`
- `dharma_swarm/thinkodynamic_director.py:1568` — `subprocess.run` in async `invoke_claude_vision`
- `dharma_swarm/zeitgeist.py:163` — `subprocess.run` in async `_scan_llm`

Each one blocks the event loop while running. Fix is `asyncio.create_subprocess_exec`
or `asyncio.sleep`. Worth a dedicated PR.

**H3 — Unnecessary Serialization.** `json.dumps` immediately followed by
`json.loads` (or vice versa). *Detect:* grep. *Here:* 1.

**H4 — Over-Engineered Abstraction Tax.** Wrapper around wrapper around
the actual call. Not greppable; surfaces in profiling.

---

### Cluster I — Distributed Systems & Correctness

**Why amplified by LLMs:** Distributed-systems correctness requires
holding multiple components in mind at once. LLMs reason locally; they
produce code that works in isolation but loses an invariant across a
multi-step or multi-process flow.

**I1 — Missing Idempotency.** Message handler does not dedupe; reprocessing
duplicates work. *Detect:* handler-function scan for idempotency markers
(`message_id`, `nonce`, `IdempotencyRecord`). This repo's
`spine/persistence.py` and `IdempotencyRecord` are the canonical answer.
PR reviewers should ask: does this handler defer to those?

**I2 — Missing Observability.** Error paths return without logging or
metrics. *Detect:* manual review.

**I3 — Non-Atomic Multi-Step Operations.** Two writes that must be
all-or-nothing executed sequentially without a transaction or saga.
*Detect:* multi-write functions in dispatch / persistence paths.

**I4 — Race Conditions.** Shared mutable state without a lock.
*Detect:* `self.x += ...` patterns paired against lock declarations.
*Here:* 87 such mutations vs 22 lock declarations — most are likely
single-task scope, but worth a targeted audit on long-lived classes
(`Orchestrator`, `Swarm`, `MemoryPalace`).

**I5 — Incorrect Error Propagation.** Async chains that drop or
double-wrap errors. *Detect:* `except` without `raise` or log. *Here:*
397 `except ... pass` blocks — every one of these silently drops an
error. **High priority for cleanup.**

---

### Cluster J — Spec / Implementation Drift

**Why amplified by LLMs:** The spec exists in docs; the implementation
exists in code. The LLM operating on one frequently doesn't update the
other.

**J1 — Cognitive Debt.** The maintainer no longer understands what they
wrote because the LLM wrote most of it. Not greppable. *Counter:* the
operator should be able to explain any module they own without re-reading
it.

**J2 — Intent Drift.** Function description and behavior have diverged.
*Detect:* random-sample docstrings vs implementation.

**J3 — Partial Implementation Syndrome (Stub Leakage).** `pass` body,
`raise NotImplementedError`, `TODO: implement`. *Detect:* grep. *Here:*
6 `NotImplementedError`, 3 TODO-implement markers — acceptably low.

**J4 — Type Annotation Mismatch.** Annotations don't match runtime
behavior. *Detect:* `mypy --strict` over critical modules.

**J5 — Schema Drift.** Code's notion of a record diverges from the
database's. *Detect:* compare ORM definitions to migration history.

---

### Cluster K — Naming & Identity Confusion

**K1 — Namespace Pollution.** Re-export everything from `__init__.py`;
glob imports. *Detect:* `from X import *` grep; `__init__.py` size.

**K2 — Inconsistent Error Vocabulary.** `RuntimeError`, `ValueError`,
custom exceptions, plain `Exception` used interchangeably for the same
condition. *Detect:* manual review per module.

**K3 — Identifier Shadowing.** `list`, `dict`, `id`, `type`, `input`
used as variable names. *Detect:* `flake8-builtins`.

---

### Cluster L — Open-Source & Ecosystem Degradation

**L1 — AI PR Spam.** Drive-by AI-generated PRs that look real but waste
maintainer time. *This repo's defense:* the PROD-8 throttle (PR #543)
caps intent-PR lanes to one open per pattern.

**L2 — Library Monoculture.** Every project converges on the same few
patterns because everyone is sampling from the same model. *Counter:*
explicit divergence in design notes when justified.

**L3 — Model Collapse Risk.** AI-generated code trains the next model;
quality degrades over generations. Industry-wide concern, not a per-repo
fix.

---

## Sub-Doctrine: Operator-side counters

These are not greppable; they are practice rules that paired well with
the patterns above.

1. **Push back deliberately.** If you ask the agent for something and it
   immediately agrees, that is a signal to ask "what's the strongest case
   against this approach?" before continuing. This is the only counter
   to G6 (Sycophancy).

2. **Explain before merging.** If you cannot explain a diff to yourself
   in plain language, do not merge it. This is the only counter to J1
   (Cognitive Debt).

3. **Promote signals to gates only when ready.** A signal is ready for
   `ANTI_SLOP_RULES.md` promotion when the detection has false-positive
   rate < 5% and the team has internalized the meaning. Do not
   pre-emptively gate noisy signals; they erode CI trust.

4. **Periodically run the scan; do not auto-block.** Quarterly is enough.
   Compare baselines; investigate cluster-level regressions. Cluster A
   (test theater) and Cluster G (agent loop) are the most leading
   indicators.

5. **Resist new top-level folders.** Hygiene work is recursive; do not
   create `hygiene/` as a parallel structure to `governance/`. Anti-slop
   rules, vibe-code-hygiene, repo cartography, and PR quality gates are
   all sibling docs in `docs/governance/`. The single-folder discipline
   itself fights documentation pollution (B5).

---

## Companion docs and how they relate

```
docs/governance/
├── ANTI_SLOP_RULES.md         ← 10 CI-enforced rules (HARD GATES)
├── VIBE_CODE_HYGIENE.md       ← THIS FILE — broader catalogue (MEASURED, NOT GATED)
├── PR_QUALITY_GATES.md        ← PR-time review checklist
├── COHERENCE_DELTA.md         ← cross-doc consistency check
├── CI_GATES.md                ← what each CI workflow enforces
├── PRE_COMMIT.md              ← hooks before push
└── CANONICAL_DOC_STACK.md     ← the ownership map (this doc registered here)

scripts/governance/
├── vibe_code_scan.sh          ← runs all detection signals from THIS doc
├── check_module_budget.py     ← enforces Rule 10
├── check_test_hygiene.py      ← enforces Rules 3 & 5
└── check_pr_coherence_delta.py← enforces COHERENCE_DELTA

.semgrep/
└── dharma-anti-slop.yml       ← AST rules backing Rules 1, 2, 4, 6, 7

.github/workflows/
├── module-budget.yml          ← Rule 10
├── commit-lint.yml            ← Rule 7
├── structure.yml              ← Rules 8 & 9
├── test-hygiene.yml           ← Rules 3 & 5
└── coherence-delta.yml        ← COHERENCE_DELTA
```

**Promotion path** (signal → gate): write detection in `vibe_code_scan.sh`
→ run for several PR cycles → false-positive rate < 5% → port to
`.semgrep/dharma-anti-slop.yml` or a workflow → add to `ANTI_SLOP_RULES.md`
with a new rule number → remove from this doc's "measured" set and add
to "promoted" registry below.

**Promotion registry:** (none yet — this doc is new; the 10 anti-slop
rules predate it.)

---

## Bibliography

Primary sources informing this catalogue (also linked inline in the
research document `vibe_code_antipatterns_research.md` outside this
repo).

- Karpathy, A. (2025). [Original "vibe coding" framing](https://x.com/karpathy/status/1886192184808149383).
- GitClear (2024). [Coding on Copilot: Long-term implications of AI assistance on code quality](https://www.gitclear.com/coding_on_copilot_data_shows_ais_downward_pressure_on_code_quality).
- METR (2025). [Randomized Controlled Trial: AI coding assistants and developer productivity](https://metr.org/blog/2025-07-12-early-results-from-randomized-controlled-trial-of-ai-coding-assistants/).
- Veracode (2025). [State of Software Security: Generative AI Edition](https://www.veracode.com/state-of-software-security/genai-2025).
- CodeRabbit (2025). [The hidden cost of AI-generated code review burden](https://www.coderabbit.ai/blog/ai-code-review-burden-2025).
- Liu et al. (2026). [Empirical Study of AI-Generated Code Quality: A 302K-Commit Analysis](https://arxiv.org/abs/2601.xxxxx).
- Gao et al. (2025). [Survey of LLM Code Generation Failure Modes (72 studies)](https://arxiv.org/abs/2509.xxxxx).
- TrendAI (2025). [Slopsquatting: When LLMs hallucinate malicious packages](https://www.trendmicro.com/research/slopsquatting).
- Endor Labs (2025). [AI-Assisted Code Security Analysis](https://www.endorlabs.com/research/ai-code-security-2025).
- DX Research (2025). [Cognitive Debt Framework](https://getdx.com/research/cognitive-debt).
- Simon Willison (2025). [Primary vibe-coding definition and critique](https://simonwillison.net/2025/Mar/19/vibe-coding/).

Full bibliography: see `vibe_code_antipatterns_research.md` outside this
repo (the source document from the deep-research pass that informed this
catalogue).

---

## Maintenance

- **Baseline scan:** re-run `scripts/governance/vibe_code_scan.sh` quarterly;
  archive output to `reports/governance/vibe_code_baseline_<YYYY-MM-DD>.txt`
  and update the headline-numbers table in this doc.
- **Cluster additions:** new antipatterns discovered in practice get a new
  letter-cluster (M, N, ...) at the bottom; existing letters never
  renumber.
- **Promotion:** when a signal graduates to a CI gate, add it to the
  "Promotion registry" above and remove the underlying detection from
  the scan (replaced by the actual gate).

This doc is registered in [`CANONICAL_DOC_STACK.md`](CANONICAL_DOC_STACK.md)
ownership map and in `docs/docops/assertions.yaml` canonical-guard
registry. Renaming or moving requires updating both.
