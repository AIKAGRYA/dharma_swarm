---
id: portability-clean-repo
title: "Return-clean proof — a deliberately clean repo grades CLEAN"
section: 26-portability
status: reference
kind: demonstration
instruments: [radon, vulture, git, AST]
confidence: HIGH
generated_by: docs/stop-the-slop/probe/probe.py
---

# Return-clean proof — a deliberately clean repo grades CLEAN

> **Claim under test:** "RETURN CLEAN when there's nothing to fix." A probe that
> can only ever find problems is a finding-manufacturer wearing an anti-slop
> costume. The honest behaviour is: on clean code, **every axis returns GREEN or
> UNASSESSED**, the composite is **CLEAN**, and the highest-leverage fix is
> *"None — return clean."*

## The fixture

`cleanlib` is a small, well-factored Python library written specifically as a
return-clean target — not this repo, so the result can't be an artifact of
tuning the probe to one codebase. It is five modules under `src/cleanlib/`
(`geometry`, `stats`, `text`, `cli`, `__init__`) plus a behavioural test suite.
Every function is pure and short; exceptions are **narrow and raised**, never
`except: pass`; imports form a DAG; there are no `import *`, no duplicated
bodies, no god objects.

## Runner output (emitted verbatim — not hand-written)

```
python docs/stop-the-slop/probe/probe.py index src/cleanlib --online
```

```
# AI-Slop Index — cleanlib/src/cleanlib

| Signal               | Measured                                                         | Grade | Confidence | Confirm with                                                 |
|----------------------|------------------------------------------------------------------|-------|------------|--------------------------------------------------------------|
| God objects          | 0 files ≥3000 ln                                                  | GREEN | HIGH       | wc -l on the listed files                                    |
| Complexity inflation | 0 fns cc>20; worst cc=5 (run @ cli.py:32)                         | GREEN | HIGH       | radon cc -n D                                                |
| Import cycles        | 0 load-time cyclic SCC(s); 0 total cyclic SCC(s)                  | GREEN | HIGH       | grimp / import-linter contract                               |
| Wildcard imports     | 0                                                                 | GREEN | HIGH       | grep -rn 'import \*'                                          |
| Silent swallows      | 0 (except…: pass)                                                 | GREEN | HIGH       | ratchet silent_exception_swallows                            |
| Broad catches        | 0 (except Exception/bare)                                         | GREEN | HIGH       | review each for log + re-raise vs swallow                    |
| Coupling             | max fan-in 2 (geometry); max fan-out 3 (cli)                     | GREEN | MEDIUM     | grimp / pydeps import graph                                  |
| Dead code            | 0 items (vulture ≥80%)                                            | GREEN | MEDIUM     | vulture + string-ref grep before delete                      |
| Duplication          | 0 clone clusters; 0 cloned fns (0.0% of 11)                       | GREEN | MEDIUM     | jscpd / pmd-cpd for Type-2/3 clones                          |
| Churn/revert         | 0/1 commits are reverts (0.0%) in 90d                            | GREEN | HIGH       | git log --grep=revert --since                                |
| Phantom deps         | 0 hallucinated/phantom of 0 unresolved                           | GREEN | MEDIUM     | verify the package exists AND predates this project on PyPI  |
| Change coupling      | 0 file-pairs co-change ≥8x at ≥60% confidence                    | GREEN | HIGH       | git log --name-only; inspect the pairs for a hidden contract |
| Narrative comments   | ~0 restate-the-code comments (0.0% of 0)                         | GREEN | LOW        | human read of the flagged lines                              |

**Composite: CLEAN.** RED 0 / AMBER 0 / GREEN 13 / UNASSESSED 0.
**Drivers (high-confidence RED): none.**
**Highest-leverage fix:** None — no high-confidence RED axis. Return clean.
```

## Why this is the hard case, not the easy one

Two signals had to be **fixed to make this honest**, because they were
hard-wired so they could never say GREEN — the exact "always finds something"
smell this library exists to kill:

- **Coupling** was pinned at AMBER regardless of measurement. Now it returns
  GREEN below a fan-in hotspot threshold (`COUPLING_HOTSPOT = 8`) and AMBER above
  it — never auto-RED, because static fan-in is a *lead* to confirm with a real
  import graph, not a verdict. This repo's max fan-in is **2** → GREEN.
- **Broad catches** was pinned at AMBER even at a count of **0**. Zero broad
  catches is genuinely clean; any present are AMBER (broad-but-logged-and-re-raised
  is legitimate), never auto-RED.

A regression guard: pointing the same fixed runner at this repo (`dharma_swarm/`)
keeps **coupling AMBER (fan-in 188)** and **broad catches AMBER (1,865)** — the
GREEN floors only let genuinely clean code return clean; they never downgrade a
real finding.

## What a clean grade does *not* mean

`CLEAN` here means *the instruments ran and found nothing actionable* — it is the
GREEN sibling of UNASSESSED, not a synonym. Every row above is a tool that
**executed** (radon parsed 11 functions, vulture scanned for dead code, git read
the history). The probe earned the word "clean"; it did not assume it.
