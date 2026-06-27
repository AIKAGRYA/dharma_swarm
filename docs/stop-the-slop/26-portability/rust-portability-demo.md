---
id: portability-rust
title: "Portability proof — a Rust repo gets honest UNASSESSED, not false-GREEN"
section: 26-portability
status: reference
kind: demonstration
instruments: [git, AST, line-count]
confidence: HIGH
generated_by: docs/stop-the-slop/probe/probe.py
---

# Portability proof — a Rust repo gets honest UNASSESSED, not false-GREEN

> **Objection this kills:** *"It only works on your own Python codebase."* The
> honest answer is two-part: signals whose instrument genuinely travels
> (file size in lines, git history) **run and report**; signals that depend on a
> Python AST **refuse to run** and say so — they return **UNASSESSED**, never a
> manufactured clean verdict on a language they cannot parse.

## The fixture

[`BurntSushi/ripgrep`](https://github.com/BurntSushi/ripgrep) — a real, large
Rust codebase: 99 `.rs` files, 0 `.py` files. Cloned at depth 600.

## Runner output (emitted verbatim — not hand-written)

```
python docs/stop-the-slop/probe/probe.py index .   # run inside the ripgrep clone
```

```
# AI-Slop Index — ripgrep

| Signal               | Measured                                      | Grade | Confidence | Confirm with                                                         |
|----------------------|-----------------------------------------------|-------|------------|----------------------------------------------------------------------|
| God objects          | 2 files ≥3000 ln (max 7,779)                  | AMBER | HIGH       | wc -l on the listed files                                            |
| Complexity inflation | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | gocyclo (Go) / rust-code-analysis (Rust) / lizard (multi-lang)       |
| Import cycles        | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | language-specific cycle check (go vet, cargo-modules)                |
| Wildcard imports     | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | language-specific import linter                                      |
| Silent swallows      | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | language-specific error-handling lint                                |
| Broad catches        | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | language-specific error-handling lint                                |
| Coupling             | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | language-specific import graph (e.g. go list, cargo-modules)         |
| Dead code            | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | language-specific dead-code analysis (e.g. staticcheck, cargo-udeps) |
| Duplication          | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | jscpd / pmd-cpd (multi-language token clone detectors)               |
| Churn/revert         | 0/8 commits are reverts (0.0%) in 90d         | GREEN | HIGH       | git log --grep=revert --since                                        |
| Phantom deps         | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | language-specific dependency resolver (e.g. cargo, go mod)           |
| Change coupling      | 0 file-pairs co-change ≥8x at ≥60% confidence | GREEN | HIGH       | git log --name-only; inspect the pairs for a hidden contract         |
| Narrative comments   | UNASSESSED (no .py sources at this path)      | —     | UNASSESSED | language-aware comment analysis                                      |

**Composite: MODERATE.** RED 0 / AMBER 1 / GREEN 2 / UNASSESSED 10.
```

god-objects detail (the instrument that travels found a real Rust god object):

```
  7779  crates/core/flags/defs.rs
  3987  crates/printer/src/standard.rs
```

## The integrity test: before vs after

This whole demo exists to prove the probe does **not** manufacture a clean
verdict off-language. Running the **pre-fix** runner (the version committed before
this track) against the same ripgrep clone:

| Signal | Before fix | After fix | Why the change is the point |
|---|---|---|---|
| God objects | **GREEN** — `0 modules ≥3000 ln` | **AMBER** — `2 files ≥3000 ln (max 7,779)` | The old probe only counted `.py`, so it **missed a 7,779-line Rust file** and called it clean. Line-count travels; it now finds it. |
| Complexity, Import cycles, Wildcard, Silent swallows, Dead code, Duplication, Phantom deps, Narrative comments | **GREEN** (×8) | **UNASSESSED** (×8) | These are Python-AST instruments. The old probe parsed zero `.py`, found zero problems, and reported GREEN — a **false-clean verdict on a language it never read**. They now refuse. |
| Coupling, Broad catches | **AMBER** (manufactured) | **UNASSESSED** | Both were hard-pinned grades; on a repo they can't read they emitted AMBER out of nothing. They now refuse. |
| Churn/revert, Change coupling | GREEN | GREEN | Git-history instruments — already language-agnostic; unchanged. |

**Before:** `RED 0 / AMBER 3 / GREEN 10 / UNASSESSED 0` — a confident, mostly-green
verdict, **including a clean bill on god objects while a 7,779-line file sat in
the tree.** That is exactly the manufactured finding this library condemns.

**After:** `RED 0 / AMBER 1 / GREEN 2 / UNASSESSED 10` — the one travelling
structural signal flags the real god object; the two git signals report; the ten
Python-only signals honestly abstain.

## The discipline in one line

A signal must **either** travel to all languages (god objects by line count, churn
and co-change by git history) **or** declare UNASSESSED on languages it cannot
parse. GREEN means *"the instrument ran and found nothing."* UNASSESSED means
*"the instrument could not run here."* Collapsing the second into the first is the
single most common way an analysis lies, and the probe is built so it can't.

## Honest limitation (documented, not hidden)

Python detection keys on the `.py` extension. ripgrep ships one **extensionless**
Python benchmark script (`benchsuite/benchsuite`); the probe does not analyse it,
because shebang-sniffing every extensionless file trades a clean rule for
heuristic false-positives. The result is faithful to the rule it states: *0 `.py`
files → Python-AST signals UNASSESSED.*
