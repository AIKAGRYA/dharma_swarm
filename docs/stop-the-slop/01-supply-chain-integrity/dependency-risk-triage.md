---
id: dependency-risk-triage
version: 0.0.1
theme: 01-supply-chain-integrity
status: tested
invariant: >
  A dependency is a liability you do not control. Its risk is
  (exploitability of a known flaw) × (reachability into shipped/runtime code) ×
  (blast radius) × (abandonment). "Versions behind latest" is a weak proxy and
  is often anti-correlated with risk — the most dangerous package is frequently
  the newest one with a fresh CVE.
lineage:
  - "Thompson 1984 — Reflections on Trusting Trust (you can't trust code you didn't create)"
  - "Saltzer & Schroeder 1975 — least privilege; rank by reachable privilege"
ground_truth_tools: [npm audit, npm outdated, pip-audit, osv-scanner]
returns_clean: true
---

## Prompt

> You are auditing a dependency graph as a **liability surface you do not
> control**. Your job is not to find things to fix — it is to report the truth,
> ranked by real exploitable risk, and to say plainly when there is nothing to do.
>
> **The invariant you defend:** a dependency's risk is
> `exploitability × reachability × blast_radius × abandonment`. "Versions behind
> latest" is at best a weak proxy and is frequently *anti-correlated* with risk:
> the most dangerous package is often the newest one carrying a fresh advisory.
> **Never rank by version distance.**
>
> **Hard rules (do not violate, even to produce a fuller-looking report):**
>
> 1. **Route to ground truth first.** Do not infer vulnerabilities from version
>    strings. Run the ecosystem's real advisory tooling and quote it verbatim:
>    - npm/pnpm/yarn → `npm audit --json` (+ `npm outdated --json` for lag)
>    - Python → `pip-audit` or `osv-scanner` (don't forget the lockfile/req files)
>    - If a required tool is **not installed/available**, that is itself a
>      finding: emit `<ecosystem> UNASSESSED — no <tool> present` and do **not**
>      fabricate a verdict for it.
> 2. **Rank by severity × reachability × blast radius — not staleness.** A
>    dev-only, optional, or platform-binary dependency carrying a flaw is
>    near-zero risk. A *runtime* dependency reachable from request/data handling
>    with a high-severity advisory is the top of the list.
> 3. **Separate three different things.** "Behind latest", "has an advisory", and
>    "abandoned" are distinct. Report version lag only as informational context,
>    never as a standalone risk grade.
> 4. **Don't flag finished software as stagnant.** A pre-1.0 leaf whose locked
>    version *equals* the latest published version, with no advisory, is "done,"
>    not rotting. Stagnation requires an open advisory OR a last-publish age
>    beyond a stated threshold — not a version shape.
> 5. **Return clean when clean.** If the advisory tool reports zero and nothing is
>    abandoned-with-a-flaw, the entire output is:
>    `No actionable dependency risk. N packages, 0 advisories.` followed by the
>    informational lag appendix. Do **not** manufacture findings to fill a template.
> 6. **Every recommendation carries its own risk.** For each fix give the exact
>    upgrade target, whether it is semver-major (breaking), and whether one
>    upgrade clears multiple advisories.
>
> **Output contract** — only for REAL hotspots, ordered by computed risk:
> - `package @ installed → fix-version (breaking? yes/no)`
> - dependency class: `runtime | dev | optional | peer | platform-binary`
> - advisory: id/title + severity, **quoted from the tool**
> - blast radius: number of dependents; shortest path `root → … → pkg`
> - reachability: is it plausibly reachable from shipped code? one line.
> - action: the single command, and exactly which advisories it clears
>
> Then append:
> - `Informational — version lag (NOT risk):` the notable behind-latest packages
> - `UNASSESSED:` any ecosystem whose tool was missing
>
> **Stop when** every advisory the tool reported is accounted for and ranked, and
> each ecosystem is assessed or explicitly marked unassessed. Do not pad.

## Why it's built this way

The prompt this rewrites asked the model to grade dependencies by "versions
behind latest," "0.x stagnation patterns," and "depth ≥ 5 in the tree." Run
against a real repo, all three are near-useless:

- **Version distance is blind to the real risk.** A current package with a fresh
  CVE (e.g. `next@16`, latest major) scores *zero* on "versions behind" yet is
  the single highest runtime risk in the tree. The heuristic literally cannot see
  it.
- **The 0.x heuristic is mostly false positives.** Platform binaries
  (`@img/sharp-*`), tooling (`@jridgewell/*`, `@eslint/*`), and convention-pre-1.0
  libraries (`lucide-react`) all version below 1.0 and are perfectly maintained.
- **Modern lockfiles are flat.** npm v3 dedupes; "depth ≥ 5" finds nothing.

So this version inverts the design: it **runs the advisory database** instead of
guessing from version strings, ranks by **exploitability and reachability**,
treats version lag as context only, and is explicitly allowed — required — to
**return clean**. The "guru" quality is the restraint and the routing to truth,
not extra sections.

## Demonstration run

**Target:** `dharma_swarm` repo, 2026-06-25. Ecosystems present: npm
(`dashboard/`, `desktop-shell/`) and Python (`pyproject.toml`,
`requirements-*.txt`). Tooling run: `npm audit --json`, `npm outdated`,
registry checks. (Compare: the original heuristic prompt found **0** real CVEs
on this same tree and mis-flagged harmless transitive stragglers as "HIGH.")

### `dashboard/` — 8 advisories (3 high, 4 moderate, 1 low)

| # | Package @ installed → fix | class | advisory (severity) | dependents | reachability |
|---|---|---|---|---|---|
| 1 | `next@16.1.6` → **16.2.9 (non-breaking)** | **runtime** | HTTP request smuggling in rewrites; null-origin Server Actions CSRF bypass; multiple DoS (**high**) | direct | **Yes — the framework serves every request.** Top risk. |
| 2 | `picomatch` → 4.0.4 / patched | dev/build | ReDoS via extglob; method injection in POSIX classes (**high**) | 8 | Build/lint only — low real exposure. |
| 3 | `flatted` → patched | dev | Prototype pollution via `parse()` (**high**) | via `flat-cache`→eslint | Dev-time cache; not shipped. |
| 4 | `postcss` → cleared by `next@16.2.9` | build | XSS via unescaped `</style>` in stringify (**moderate**) | many | Build-time CSS. |
| 5 | `brace-expansion@1.1.12` → patched | dev | Zero-step sequence DoS; `max` bypass (**moderate**) | 1 | Build/lint only. |
| 6 | `js-yaml` → patched | dev | Quadratic-complexity DoS via merge keys (**moderate**) | via `@redocly/openapi-core` | `openapi-typescript`, dev. |
| 7 | `@redocly/openapi-core` → patched | dev | (via `js-yaml`) (**moderate**) | 1 | Dev codegen. |
| 8 | `@babel/core` → patched | build | Arbitrary file read via `sourceMappingURL` (**low**) | many | Build-time. |

**Highest-leverage action:** `npm i next@16.2.9` — **non-breaking**, clears the
#1 runtime high (`next`) **and** the `postcss` moderate in one move. Remaining
items are dev/build-chain; clear with `npm audit fix` and verify the build.

### `desktop-shell/` — **clean**

`No actionable dependency risk. 0 advisories.` (The honest "nothing to do here"
the heuristic prompt is incapable of returning.)

### Python — **UNASSESSED**

`pyproject.toml` + `requirements-dev.txt` + `requirements-ginko.txt` exist, but
**no `pip-audit` / `osv-scanner` is installed** — so the repo's *primary*
language has **no supply-chain scanning at all**. This is the most important
finding on the tree, and the version-distance heuristic would never surface it.
Action: `pip install pip-audit && pip-audit -r requirements-dev.txt` (and add it
to CI).

### Informational — version lag (NOT risk)

`zustand` is locked at both `4.5.7` and `5.0.11` (a direct dep at two majors;
latest 5.0.14) — worth de-duping but no advisory. `immer 10.2.0` (via recharts;
latest 11.x), `eslint 9` (latest 10, days old), `lucide-react 0.577` (latest
1.x) — all current-enough, none carry advisories.

## Changelog

- **v0.0.1** (2026-06-25) — initial rewrite of a third-party kit's
  package-lock-analysis prompt. Replaced version-distance/0.x/depth heuristics
  with: ground-truth advisory tooling, exploitability×reachability×blast-radius
  ranking, ecosystem-aware (npm + Python) coverage, explicit UNASSESSED handling,
  and a mandatory return-clean path. Tested against `dharma_swarm` (found 8 real
  advisories the heuristic version missed entirely; correctly returned clean on
  `desktop-shell` and flagged Python as unscanned).
