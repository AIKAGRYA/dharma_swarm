---
id: change-coupling-hotspots
version: 0.1.0
theme: 08-change-management
status: tested
reproduce: "python docs/stop-the-slop/probe/probe.py change_coupling <pkg>"
invariant: >
  Files that change together are coupled — even when no import connects them. This
  LOGICAL (change) coupling, mined from version-control history, predicts defects
  better than static dependency coupling (D'Ambros/Lanza). Two implementation files
  that co-change at high confidence share a HIDDEN CONTRACT: an invariant neither
  file's code states, that a human must remember. The invariant: rank by historical
  co-change association, and distinguish a hidden contract from a benign expected
  pair (a file and its own test).
lineage:
  - "D'Ambros, Lanza, Robbes 2009 — logical/change coupling predicts defects better than structural coupling"
  - "Parnas 1972 — information hiding; a coupling that crosses module secrets is the risk"
  - "Lehman — software evolution: history is data about how a system actually changes"
ground_truth_tools: ["git log --name-only (co-change matrix)", "association-rule confidence/support", "the import graph (to subtract structural coupling)"]
returns_clean: true
---

## Prompt

> Find **change-coupling (logical coupling) hotspots** from version-control history.
> The invariant (D'Ambros/Lanza): files that co-change predict defects better than
> static imports, and a high-confidence co-change with **no import edge** is a hidden
> contract — an invariant the code doesn't state. Mine it, rank it, and don't cry
> wolf on benign pairs.
>
> **Hard rules:**
> 1. **Build the co-change matrix from real history.** Parse `git log --name-only`
>    over a bounded window (exclude merge commits and bulk/reformat commits that
>    touch hundreds of files — they're noise, not coupling).
> 2. **Rank by association strength, not raw count.** For a pair (A,B) report
>    *support* (times co-changed) and *confidence* (P(B changed | A changed)).
>    Require a floor on both (e.g. support ≥ 8, confidence ≥ 60%) so a single
>    coincidental commit can't create a "hotspot."
> 3. **Subtract the expected pairs.** A file co-changing with **its own test**
>    (`foo.py ↔ test_foo.py`) is the *correct* relationship, not a smell — report it
>    as BENIGN. The finding that matters is two **implementation** files coupled in
>    history with **no import edge** between them.
> 4. **Return clean.** If no pair clears the floor, say
>    `No change-coupling hotspots: N commits analyzed, 0 pairs ≥ threshold.`
>
> **Output:** a table (`A ↔ B → support → confidence → has-import-edge? →
> hidden-contract | benign`), and for each hidden contract a one-line hypothesis of
> the unstated invariant the two files silently share.

## Why it's built this way

Static coupling tools see only imports; they are blind to the most dangerous coupling
— two files that must change together but have no code link, so the compiler never
reminds you. History is the only instrument that sees it. But raw co-change is noisy:
bulk reformat commits and the trivially-correct impl↔test pair will dominate a naive
count. So the discipline is association-rule strength on a denoised log, with the
expected pairs explicitly subtracted, so the surviving finding is genuinely a *hidden*
contract.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-27 (`git log --name-only`, last 228 non-merge
commits):

```
| Signal          | Measured                                      | Grade | Confidence | Confirm with                                                 |
|-----------------|-----------------------------------------------|-------|------------|--------------------------------------------------------------|
| Change coupling | 1 file-pairs co-change ≥8x at ≥60% confidence | AMBER | HIGH       | git log --name-only; inspect the pairs for a hidden contract |

Detail (git co-change association rules):
  100% (9x)  consume_review_marks.py  ↔  test_consume_review_marks.py
```

- **Exactly one pair clears the floor**, and rule 3 is what makes the result honest:
  it's `consume_review_marks.py ↔ test_consume_review_marks.py` — an implementation
  file and **its own test**, co-changing 9× at 100% confidence. That is the *correct*
  relationship (you change the code, you change its test), so the real reading is
  **BENIGN — no hidden-contract pairs among implementation files**. A naive change-
  coupling tool would headline this as a top hotspot; the disciplined one labels it
  expected and moves on.
- The absence of impl↔impl hotspots is itself a finding: in the analyzed window, this
  repo's high-confidence co-changes are all code-with-its-test, i.e. the coupling that
  exists is the kind you *want*.

## Changelog

- **v0.1.0** (2026-06-27) — new dimension. Co-change matrix from `git log --name-only`,
  association-rule support/confidence floors, merge/bulk-commit denoising, explicit
  impl↔test "benign" subtraction. Tested on `dharma_swarm`: 1 pair clears the floor and
  it is a benign impl↔test pair → 0 hidden-contract hotspots in the window.
