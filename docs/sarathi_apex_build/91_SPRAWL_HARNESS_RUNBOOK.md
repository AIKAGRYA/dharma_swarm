# 91 — Sprawl Harness Runbook: the one-command gate that fails

**Custody: PROVEN (this file's central script was run red on the dirty tree and
green on a collapsed tree, 2026-07-06). fable_composer, independent-verification seat.**

This is the operational companion to `90_ANTI_SPRAWL_HARNESS.md`. That doc gives
the principle (Surface Claim before writing). This doc gives the **enforcement**,
because the principle already existed and did not hold.

## The diagnosis, stated as evidence not opinion

The operator runs `make onboard` / `make orient` before most builds and *still*
gets sprawl. Here is why, with receipts:

| What already exists | Receipt | Did it stop sprawl? |
|---|---|---|
| Axiom **A1 NO FLAT-PACKAGE GROWTH** | `docs/governance/SOVEREIGN_MANIFEST.md:418` | No |
| Axiom **A2 NO DUPLICATE IMPLEMENTATIONS** | `docs/governance/SOVEREIGN_MANIFEST.md:421` | No |
| Orientation (`make onboard`, `make orient`) | onboard renders axioms + tracks | No |
| A surface registry (`ACTIVE_SURFACE_MANIFEST.yaml`, 803 lines) | repo root | No |
| **A script that returns non-zero on a duplicate** | *did not exist* | — |

`holon_bridge.py` / `holon_runtime.py` each have ~138 copies across ~69 trees.
The rule against this was written. The orientation described the estate. The
surface file declared intent. **Nothing failed a build when the 139th copy
appeared.** Orientation is a map; a map does not stop you walking off a cliff.

> The missing primitive was never another document. It was an exit code.

## Second finding that makes the collapse tractable

"138 copies" sounds catastrophic; it is mostly mirror noise. Distinct-content
census (`shasum` of tracked copies) shows only **~3-4 distinct implementations**
of `holon_bridge.py` in-repo — the rest are worktree mirrors of the same bytes.
So the real drift to reconcile is ~3-4 files, not 138. Count contents, not paths.

## The harness: one script, three checks, one exit code

`scripts/governance/sprawl_guard.py` — read-only, deterministic, no model, and
deliberately Python-3.9-safe so it can run in a pre-commit hook where the system
interpreter may be old. It enforces:

1. **Singleton symbols.** A small declarative registry (`SINGLETON_SYMBOLS`) of
   "there must be exactly one definition of this." Ships with `load_holon` and
   `holon_wake_cycle`; add any symbol that should have one home. Extra
   definitions outside the canonical file = finding.
2. **Forbidden imports.** Retired forks (`holon.holon_bridge`,
   `holon.holon_runtime`) must not be imported by runtime code = finding.
3. **Copy-drift census.** Reports tracked copies AND distinct contents per
   watched filename, so "138 copies" is read correctly as "N real versions".

Exit code: `0` clean, `1` on any finding. That is the whole contract.

## Proven behavior (receipts, 2026-07-06)

```text
# On the current dirty tree (holon/ fork present):
$ python3 scripts/governance/sprawl_guard.py ; echo EXIT=$?
  FAIL def load_holon  -> extra definition: holon/holon_bridge.py
  FAIL def holon_wake_cycle -> extra definition: holon/holon_runtime.py
  RESULT: 2 FINDING(S)
  EXIT=1

# On a collapsed tree (fork deleted, canonical only):
  RESULT: CLEAN — no sprawl findings.
  EXIT=0
```

Ran under `/usr/bin/python3` = Python 3.9.6 without a collection error, so it is
safe for the pre-commit path (unlike the repo's 3.10+ runtime modules).

## This IS the collapse definition-of-done

The 136->1 / 138->1 collapse (see `12_LOAD_HOLON_COLLAPSE_PLAN.md`) is "done"
when, on a clean branch off `origin/main`:

```bash
python3 scripts/governance/sprawl_guard.py   # exits 0
```

No narrative "I consolidated it" is accepted. The gate is the judge.

## How to make it stick (in order of leverage)

1. **Local one-liner now** (works today, zero new infra):
   `cd ~/dharma_swarm && python3 scripts/governance/sprawl_guard.py`
2. **Makefile target** (proposed): a `sprawl-guard` target that runs the script,
   then add `sprawl-guard` to `agent-build-closeout` so no PR closes over a new
   duplicate.
3. **pre-commit hook** (proposed `.pre-commit-config.yaml` entry): run the guard
   on commit; a new duplicate primitive cannot even be committed.
4. **CI job** (proposed): the same command as a required check. Belt and braces.

## The generalization beyond holons

The operator said "almost everything I do ends up scattered." The holon case is
one instance of one pattern: **a primitive with no declared single home + no gate
that fails on a second home**. The fix generalizes exactly:

- When you build something that should be singular, add one line to
  `SINGLETON_SYMBOLS` (symbol + canonical path + why).
- When you retire a module, add one line to `FORBIDDEN_IMPORTS`.
- The gate does the rest, forever, with an exit code.

Adding to the registry is the new cost of creating a primitive. It is one line.
That is the "much much simpler" the operator asked for: not more reading, one
declaration and one gate.

## The three-line ritual (replaces "I ran make onboard and hoped")

```bash
cd ~/dharma_swarm
make onboard                                   # orient (unchanged)
python3 scripts/governance/sprawl_guard.py     # PROVE no duplicate before you write
# ... build ...
python3 scripts/governance/sprawl_guard.py     # PROVE you did not add one
```

Orientation answers "where am I." The guard answers "did I just make it worse."
Only the second one has teeth.
