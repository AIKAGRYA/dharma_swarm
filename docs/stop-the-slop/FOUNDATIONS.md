# FOUNDATIONS — the canon Stop the Slop stands on

Every prompt cites its **lineage**: the result in computer or cognitive science
that makes its analysis *correct* rather than merely plausible. This file is the
shared canon. The point is not erudition — it is that a finding rooted in a
theorem outranks a finding rooted in a vibe, and a vibe coder armed with the
theorem stops shipping slop.

The recurring meta-principle, stated three ways across 80 years:

- **Dijkstra (1972), *The Humble Programmer*** — "Testing shows the presence,
  not the absence, of bugs." → *Absence of a finding is never proof of safety;
  route to a tool that can actually witness the property.*
- **Thompson (1984), *Reflections on Trusting Trust*** — you cannot trust code
  you did not totally create yourself. → *Every dependency is unverified until a
  ground-truth check says otherwise.*
- **Hofstadter (1979), *GEB*** — strange loops and tangled hierarchies; meaning
  is not in the symbol but in the system that interprets it. → *A report's
  structure will seduce you into filling it; the discipline is to let the
  evidence, not the template, decide what exists.*

## Canon by theme

| Lineage | Result | What it licenses in a prompt |
|---|---|---|
| **Dijkstra** (1968, *Go To Considered Harmful*; THE system) | structured control flow; layered systems with a strict ordering | acyclic layering; a cycle is a defect, not a style |
| **Parnas** (1972, *On the Criteria…*) | information hiding; modules decomposed by secrets, not flowcharts | boundaries are contracts; coupling across them is the risk surface |
| **Tarjan** (1972) | strongly-connected components in linear time | *the* algorithm for finding dependency cycles — not regex on imports |
| **Kahn** (1962) | topological sort | a healthy module graph is a DAG; topo-order is the proof |
| **Hoare** (1969, axiomatic basis; CSP) | pre/postconditions; communicating processes | invariants and contracts are checkable, not aspirational |
| **Meyer** (Design by Contract) | obligations/benefits at interfaces | every boundary should state what it promises and requires |
| **Shannon** (1948) | entropy; information as surprise | drift/duplication is measurable entropy, not taste |
| **Saltzer & Schroeder** (1975) | least privilege; economy of mechanism; fail-safe defaults | security findings ranked by reachable privilege, not by scariness |
| **Thompson** (1984) | trusting-trust attack | supply-chain trust must be earned by evidence each time |
| **Lamport** (1978) | happens-before; ordering in distributed systems | concurrency/resilience reasoning about causality, not vibes |
| **Lehman** (laws of software evolution) | systems must be continually adapted or they rot | drift/entropy control is a law, hence a ratchet, not a nag |
| **Knuth** (literate programming; *Art of…*) | rigor + readability as one act | "altitude"/readability findings have a discipline behind them |

## The AI-specific canon (new in v0.1)

Classic CS tells you what *good code* is. The 2024–2025 literature tells you how
*machine-generated* code fails differently from human code — a distinct error
signature — and that is what an anti-slop product must measure. These results
license the new dimensions added in v0.1.

| Lineage | Result | What it licenses in a prompt |
|---|---|---|
| **McCabe** (1976) | cyclomatic complexity = independent paths; you cannot cover N paths with M<N tests | rank complexity by a *measured* path count (radon), not "looks gnarly" |
| **Campbell / SonarSource** (Cognitive Complexity, 2017) | nesting & control-flow breaks, not raw branch count, track human comprehension effort | separate a flat dispatch (high cyclomatic, low cognitive) from nested spaghetti |
| **D'Ambros, Lanza, Robbes** (2009) — logical/change coupling | files that *co-change* in history predict defects better than static coupling | mine git co-change association rules; a hidden contract is a real risk |
| **DeMillo, Lipton, Sayward** (1978) — mutation testing | coverage proves a line *ran*, not that a test would *catch* a bug; the oracle gap is the mutation-score deficit | "test theater" is measurable: a passing suite that kills no mutants asserts nothing |
| **Tufano et al.** (2025, *Propensity Smelly Score*) | smell propensity is a probabilistic, model-comparable signal; AI code skews toward god-classes & method bloat | grade structural smells as a distribution, and expect the AI signature |
| **Spracklen et al.** (2025, *package hallucination / slopsquatting*) | 5–30% of LLM-generated installs name packages that do not exist; attackers pre-register them | a phantom dependency is a supply-chain attack surface, not a typo — check existence against the index |
| **Dhuliawala et al.** (2023, *Chain-of-Verification*) | a model that drafts, then *verifies its own claims against a tool*, hallucinates far less | the prompt's "confirm with <tool>" step is not decoration — it is the verification pass |
| **Larridin / industry AI-Slop Index** | duplication, revert rate, complexity, architectural coherence, test-behavior coverage compose a usable slop score | the flagship composes orthogonal measured signals, never one adjective |

## Composite scoring model (how the index is allowed to combine signals)

A composite that sums incomparable signals into one number *is itself slop*. The
index obeys four rules, enforced by the runner (`probe/probe.py`):

1. **Vector, not scalar.** The index is the full per-axis table first. The headline
   (CLEAN / MODERATE / ELEVATED) is a *summary of drivers*, never a replacement for
   the rows.
2. **Drivers are earned, not averaged.** Only signals that are **RED with HIGH or
   MEDIUM confidence** may drive the headline; they are ranked by `pressure` (a
   bounded 0–1 saturation of how far past threshold the axis is). `≥2` drivers →
   ELEVATED; `1` → MODERATE; `0` high-confidence RED but some RED → "ELEVATED
   (low-confidence — confirm first)"; only AMBER → MODERATE; all clear → CLEAN.
3. **LOW and UNASSESSED never inflate the score.** A proxy (narrative comments) or an
   ungradeable axis (dead code without vulture) is shown for transparency but is
   structurally barred from manufacturing an ELEVATED.
4. **One denominator.** See scope normalization below.

## The confidence rubric (killing the vibe knob)

The review found "MEDIUM confidence" used as an undefined feeling. It is now a
function of *how the row was produced*:

- **HIGH** — a dedicated instrument ran on complete input (radon, the AST for a
  syntactic fact, git for history).
- **MEDIUM** — a real instrument ran but a known structural blind spot remains
  (static import graph can't see dynamic wiring; import-name ≠ PyPI dist-name).
- **LOW** — only a proxy or partial signal was available (a regex; an AST
  branch-count standing in for radon).
- **UNASSESSED** — no faithful proxy exists; the runner refuses to grade rather than
  guess. UNASSESSED is a valid, honest result, never inferred.

## Scope normalization

Every signal in a composite must be measured over the **same denominator**, and that
denominator must be printed. The runner emits a "Scopes per axis" block and the
flagship runs all signals over one `dharma_swarm/` root. This closes the review
finding that the v0 index silently mixed per-package (`dharma_swarm/`) and whole-repo
(incl. `scripts/`, `tests/`) counts into one grade.

## How a prompt uses its lineage

1. **Name the invariant** the lineage establishes (e.g. "the import graph must be
   a DAG" ← Dijkstra/Parnas/Tarjan).
2. **Route to the mechanized form** of that result (e.g. Tarjan SCC over a real
   AST import graph — not "look for `A imports B` patterns").
3. **Rank by the property the theory says matters** (load-time reachability for
   cycles; exploitable privilege for security) — never by a cosmetic proxy.
4. **Return clean** when the property holds. Dijkstra's razor cuts both ways: if
   the witness finds nothing, report nothing — and say what you checked.

New prompts extend this table with the result they descend from. If a prompt
can't name its lineage, it isn't ready — it's a vibe with formatting.
