# Pramāṇa Probe — the executable runner

The library's thesis is **route to ground truth, return clean, never manufacture.**
Markdown alone can't prove that — so this directory makes it falsifiable. Each signal
runs the *real* instrument (radon, git, the AST, PyPI) and emits the row that
instrument earned. Every "Demonstration run" in the prompts is regenerated from this
output, so a buyer can reproduce every number instead of trusting prose.

> This is the single thing that separates an anti-slop product from slop: a tool that
> condemns "trust-me findings" cannot itself ship trust-me findings.

## Usage

```bash
# composite AI-Slop Index (all signals) over a package
python probe.py index <path>

# one signal
python probe.py complexity <path>
python probe.py phantom_deps <path> --online   # --online enables PyPI existence check

# machine-readable
python probe.py index <path> --json
```

No third-party install is required to run it; signals whose dedicated tool is absent
degrade honestly (see the confidence rubric) rather than guessing. `radon` upgrades
the complexity signal from a LOW proxy to HIGH; `vulture` upgrades dead-code from
UNASSESSED to a real result. `cycles` and `duplication` are pure-stdlib (AST +
Tarjan SCC; AST function-body hashing) and need no install at all.

## Signals and where each routes

| Signal | Instrument (ground truth) | Confidence ceiling | Returns clean? |
|---|---|---|---|
| `god_objects` | AST line count per module | HIGH | yes (0 → GREEN) |
| `complexity` | **radon cc** (proxy AST only if radon absent) | HIGH (LOW on proxy) | yes |
| `cycles` | AST import graph + **Tarjan SCC** (load-time vs `TYPE_CHECKING`/lazy) | HIGH | yes (DAG → GREEN) |
| `wildcard_imports` | AST `ImportFrom` with `*` | HIGH | yes |
| `silent_swallows` | AST `ExceptHandler` whose body is a sole `pass` | HIGH | yes |
| `broad_catches` | AST `ExceptHandler` catching `Exception`/bare | HIGH | yes |
| `coupling` | AST static import fan-in/fan-out | MEDIUM (dynamic wiring invisible) | yes |
| `dead_code` | `vulture` if present, else **UNASSESSED** | MEDIUM / UNASSESSED | yes |
| `duplication` | AST function-body hashing (Type-1 clones; `jscpd` for Type-2/3) | MEDIUM | yes (0 → GREEN) |
| `churn` | `git log` revert rate, 90-day window | HIGH | yes |
| `phantom_deps` | unresolved imports × **PyPI existence** (`--online`) | MEDIUM | yes |
| `change_coupling` | `git log --name-only` co-change association rules | HIGH | yes |
| `narrative_comments` | comment-restatement regex (PROXY) | LOW | yes |

## The confidence rubric (the vibe knob, killed)

Confidence is a function of *how the row was produced*, never a feeling:

- **HIGH** — a dedicated instrument ran on complete input (radon for complexity, the
  AST for syntactic facts, git for history).
- **MEDIUM** — a real instrument ran but a structural blind spot remains (static
  import graph can't see dynamic wiring; import-name ≠ PyPI dist-name).
- **LOW** — only a proxy or partial signal was available (regex for narrative
  comments; AST branch-count when radon is absent).
- **UNASSESSED** — no faithful proxy exists, so the runner refuses to grade
  (dead-code without `vulture`). UNASSESSED is an honest answer, never inferred.

The composite headline is driven **only** by HIGH/MEDIUM-confidence RED signals.
A LOW or UNASSESSED axis is reported but can never manufacture an "ELEVATED."

## Scope normalization

The composite never sums signals measured over different denominators into one
grade. `run_index` prints the explicit scope (denominator) of every axis, and the
flagship demo runs every signal over the same `dharma_swarm/` root. This fixes the
review finding that the old index silently mixed per-package and whole-repo counts.

## Hermetic by default

The runner does no network I/O unless you pass `--online`. Offline, `phantom_deps`
reports unresolved-import *candidates* at LOW confidence and explicitly refuses to
call them "phantom" — because "unresolved locally" is not "hallucinated." Only with
`--online` (PyPI is the ground truth for existence) does it grade a true phantom.

## Self-tests

```bash
python test_probe.py        # or: python -m pytest test_probe.py
```

The tests (6) prove the two properties the product lives on: **return-clean** (clean
code grades GREEN, not "something") and **detect** (planted slop goes RED with the
right evidence), plus that `phantom_deps` refuses to accuse offline, `complexity`
routes to radon when present, `cycles` counts a load-time cycle as RED while
excluding `TYPE_CHECKING`-only and function-local back-edges, and `duplication`
returns clean on unique code then flags an exact Type-1 clone at MEDIUM.
