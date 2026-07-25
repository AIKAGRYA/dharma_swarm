---
id: phantom-deps-audit
version: 0.1.0
theme: 01-supply-chain-integrity
status: tested
reproduce: "python docs/stop-the-slop/probe/probe.py phantom_deps <pkg> --online"
invariant: >
  An imported package that does not exist on the index is not a typo — it is a
  supply-chain attack surface. LLMs hallucinate plausible-sounding import names in
  5–30% of outputs (slopsquatting), and attackers pre-register those names with
  malware. The invariant: every third-party import must resolve to a real,
  pre-existing distribution; an unresolved import is a CANDIDATE, never a verdict,
  until existence is checked against ground truth (the package index).
lineage:
  - "Spracklen et al. 2025 — package hallucination / 'slopsquatting' (5–30% of LLM installs name non-existent packages)"
  - "Thompson 1984 — Reflections on Trusting Trust: trust no dependency you didn't verify"
  - "Dhuliawala et al. 2023 — Chain-of-Verification: verify each claim against a tool before asserting"
ground_truth_tools: ["AST import extraction", "importlib.metadata (installed dists)", "the package index (PyPI/npm) existence API", "stdlib module list"]
returns_clean: true
---

## Prompt

> Audit this codebase for **phantom / hallucinated dependencies**. The invariant
> (slopsquatting research, Thompson): an import that resolves to *no real package*
> is a supply-chain attack surface — attackers pre-register hallucinated names. Your
> job is to find third-party imports that **do not exist on the index**, without
> ever accusing a real-but-uninstalled package.
>
> **Hard rules (do not violate, even to produce a fuller report):**
> 1. **Extract imports from the AST, then classify each** as: stdlib (safe),
>    first-party (a module/package in this repo), installed third-party (present in
>    `importlib.metadata`), or **unresolved**.
> 2. **Unresolved ≠ phantom.** An unresolved import may simply be uninstalled in
>    this environment. Mark it a CANDIDATE at LOW confidence. **Do not call it
>    phantom on local evidence alone.**
> 3. **Route to the index for the verdict.** For each candidate, query the package
>    index (PyPI/npm) for existence. Only a confirmed **404** is a phantom (RED,
>    MEDIUM+ confidence). A **200** means real-but-uninstalled (GREEN/AMBER, not a
>    security finding). Account for the import-name ≠ distribution-name gap
>    (`cv2`→`opencv-python`, `sklearn`→`scikit-learn`, `PIL`→`pillow`, …).
> 4. **Confirm survivors aren't local.** Before declaring phantom, check the import
>    isn't a sibling module loaded via `sys.path` manipulation or a namespace
>    package — those are first-party, not hallucinations.
> 5. **Return clean.** If every import resolves or exists on the index, say
>    `No phantom dependencies. N imports, all resolve.` Do not manufacture one.
>
> **Output:** unresolved imports as a table (`import → file:line → exists-on-index?
> → verdict`), the phantom count distinct from the real-but-uninstalled count, and
> for each phantom the exact `file:line` and the index URL that 404s.

## Why it's built this way

The naive prompt — "list suspicious imports" — manufactures findings: it flags every
uninstalled-but-real package (`torch`, `redis`) as suspicious, drowning the one that
matters. The danger is precisely inverted: a *real* package you haven't installed is
harmless; a *hallucinated* name an attacker has squatted is RCE on `pip install`. So
the discipline is a two-stage gate — local resolution narrows to candidates, then the
**index is the only ground truth for existence** (Chain-of-Verification). Offline, the
honest answer is "candidates, unverified," not an accusation.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-27, `--online` (PyPI existence check live):

```
| Signal       | Measured                                                           | Grade | Confidence | Confirm with                                                |
|--------------|--------------------------------------------------------------------|-------|------------|-------------------------------------------------------------|
| Phantom deps | 1 hallucinated/phantom of 24 unresolved (23 real-but-uninstalled)  | RED   | MEDIUM     | verify the package exists AND predates this project on PyPI |

Detail (PyPI existence check (live)):
  PHANTOM: run_agent  ← build_engine.py:100
```

- **23 of 24** unresolved imports exist on PyPI — real packages merely uninstalled in
  this venv (`torch`, `redis`, `playwright`, …). The naive scan would have flagged all
  24; this one correctly clears 23.
- **1 candidate 404s: `run_agent` @ `build_engine.py:100`.** Confidence is **MEDIUM,
  not HIGH** — and rule 4 explains why: confirming reveals it's imported right after
  `sys.path.insert(HERMES_DIR, …)`, i.e. an **external local module on an injected
  path**, not a hallucinated PyPI package. **True phantom count for this repo: 0.** The
  MEDIUM grade and the mandatory "confirm" step are what stop this from becoming a false
  accusation — exactly the discipline a phantom-deps tool exists to enforce on itself.
- **Offline behavior (also tested):** without `--online`, the same scan returns the 24
  as LOW-confidence candidates with `pressure=0` and the text "NOT phantom-confirmed —
  run --online." It refuses to accuse on local evidence alone.

## Changelog

- **v0.1.0** (2026-06-27) — new dimension. AST import classification → PyPI existence
  check; offline returns LOW-confidence candidates (refuses to accuse), online grades
  true 404s as phantom; import-name→dist-name alias map; sys.path/local-module guard.
  Tested on `dharma_swarm`: 23/24 unresolved are real-but-uninstalled, the 1 "phantom"
  is a sys.path-injected local module → true phantom count 0.
