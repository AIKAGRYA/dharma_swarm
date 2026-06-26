# Prompt Library — guru-grade code prompts for builders

A versioned, evidence-routed family of prompts for taking AI-generated software
from "it runs" to "it's defensible." Two jobs, one artifact:

1. **Inward** — level up *this* repo from the level of invariants and first
   principles, not surface lint.
2. **Outward** — a packaged, sellable offering (or a free entry tier) for
   builders — "vibe coders" — who can generate code but can't yet *trust* it.

## The one rule that makes this different (and worth paying for)

Most prompt kits are **template-fillers**: they hand the model a beautiful
structure (CRITICAL / HIGH / MEDIUM, depth-5 chains, risk tables) and the model
dutifully *populates* it — even when the honest answer is "nothing to fix." The
output looks like expertise and is frequently hollow. On a clean codebase it
actively misleads, nudging you to churn things that aren't broken.

Every prompt in this library obeys the inverse discipline:

- **Route to ground truth, don't pattern-guess.** Run the real tool (`npm
  audit`, `pip-audit`, the type checker, the test runner, the profiler) and
  quote it. If the tool is absent, say so — never fabricate the verdict.
- **Rank by real risk, not by proxy.** Exploitability × reachability × blast
  radius — not "versions behind," not "file is long," not "looks scary."
- **Return clean when clean.** "No actionable finding, here's the evidence" is
  a *success*, not a gap to fill. Manufacturing findings to fill the template
  is the cardinal sin.
- **Every recommendation carries its own risk.** A fix that breaks the build is
  not a fix.
- **State the invariant first.** Each prompt names the first-principles property
  it defends, so the model reasons from the property, not from the template.

> This discipline is the lesson of the host repo, learned the hard way: a system
> can have the best anti-slop *vocabulary* and almost no anti-slop *enforcement*
> — documenting its slop with precision instead of preventing it. We take the
> lesson (gate, measure, return-clean), not the vocabulary. Prose is not proof.

## Format

Each prompt is one Markdown file with YAML frontmatter and four sections:

```
---
id: <slug>
version: <semver>          # version lives here + in git history, not in filenames
theme: <thematic-map key>
status: draft | tested | published
invariant: <the first-principles property this prompt defends>
ground_truth_tools: [<the real tools it must run>]
returns_clean: true        # asserts the prompt can and will say "nothing to fix"
---

## Prompt
<the copy-paste prompt itself — self-contained>

## Why it's built this way
<the design notes: what failure mode it avoids, what it routes to>

## Demonstration run
<a real run against a real repo, with the date and the honest output>

## Changelog
<vX.Y.Z — what changed and why>
```

Versions evolve **in place** (git is the version store); the frontmatter
`version` is the label. We don't proliferate `name.v1.md`, `name.v2.md`.

## Thematic map

| # | Theme | Defends the invariant | Prompts |
|---|---|---|---|
| 01 | **Supply-chain & dependency integrity** | "A dependency is a liability you don't control; risk = exploitability × reachability × blast radius, never staleness." | `dependency-risk-triage` (v0.0.1) |
| 02 | _Invariant & contract discovery_ | _(reserved)_ | — |
| 03 | _Architecture & boundary analysis_ | _(reserved)_ | — |
| 04 | _Failure-mode & resilience_ | _(reserved)_ | — |
| 05 | _Test integrity & verification_ | _(reserved)_ | — |
| 06 | _Drift & entropy control (ratchets/baselines)_ | _(reserved)_ | — |

The map grows as prompts are added; themes are not fixed in advance.

## Productization note (read before extracting)

This library is seeded inside `dharma_swarm` for convenience while we build it.
When it becomes a real offering, **graduate it to its own repo** — sellable
product IP should not be entangled with this repo's governance, license, or
history. Treat the path here as a staging area, not the final home.

## Changelog

- **2026-06-25** — library seeded; format + thematic map defined; first prompt
  `01/dependency-risk-triage` saved at v0.0.1 (rewrite of a third-party kit's
  lockfile-analysis prompt, tested against this repo).
