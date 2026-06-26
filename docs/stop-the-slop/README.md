# STOP THE SLOP — **PRAMĀṆA PROBE**

> guru-grade code prompts for builders, rooted in the history of computer &
> cognitive science and verified against ground truth.

**Name (settled):** **Pramāṇa Probe.** *Pramāṇa* (Sanskrit) is "the valid means by
which one arrives at accurate knowledge — perception, measurement, proof"; a
*probe* is the instrument that takes the measurement. Together: **knowledge earned
by a valid instrument, not by guessing** — this library's entire thesis, in a name
native to the host repo (`dharma_swarm/pramana.py`). Outer brand: **"Stop the
Slop."** Soul-name: **Pramāṇa Probe.**

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
- **Stand on the shoulders.** Each prompt names its **lineage** — the
  computer-/cognitive-science result it descends from (see `FOUNDATIONS.md`).
  Old-school first principles (Dijkstra, Parnas, Tarjan, Thompson, Shannon,
  Hoare) are not decoration; they are *why* the analysis is correct. Bleeding-
  edge tooling is just those ideas mechanized. A finding rooted in a theorem
  outranks a finding rooted in a vibe.

### Analysis prompts vs generation prompts — same discipline, two faces

"Route to ground truth" means different things by task type, but it is the same
rule:

- **Analysis** (audit/triage): ground truth = **run the instrument** — the
  profiler, the advisory DB, the SCC algorithm — and rank by what it measures.
- **Generation** (seed scripts, rules blocks, scaffolds): ground truth =
  **faithfulness to the real artifact** — parse the actual schema/codebase, ban
  the anti-patterns that are *actually present* (with counts), and **refuse to
  invent** a field, a finding, or a rule you can't point at. Inventing is the
  generative form of slop.

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
lineage: [<the CS/cog-sci results it descends from — see FOUNDATIONS.md>]
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

| # | Theme | Defends the invariant | Lineage | Prompts |
|---|---|---|---|---|
| 01 | **Supply-chain & dependency integrity** | "A dependency is a liability you don't control; risk = exploitability × reachability × blast radius, never staleness." | Thompson *Trusting Trust* '84; Saltzer–Schroeder '75 | `dependency-risk-triage` (v0.0.1) |
| 02 | **Module topology & acyclicity** | "The import graph must be a DAG; a load-time cycle is a latent boot failure. Rank by load-time danger, not cycle length." | Dijkstra THE '68; Parnas '72; Tarjan SCC '72; Kahn '62 | `circular-dependency-triage` (v0.0.1) |
| 03 | **Performance & cost** | "Optimize only what a profiler proves dominates; a bottleneck is a measured share, not a guess. Amdahl bounds the payoff; name the floor." | Knuth '74; Amdahl '67; Gregg (USE/flame); Jain | `performance-bottleneck-triage` (v0.0.1) |
| 04 | **Resilience & retries** | "A retry must be bounded, jittered, narrow, and idempotent — or it's an outage amplifier. Find the canonical primitive and measure adoption." | Metcalfe–Boggs '76; Nygard '07; Brooker (jitter) | `retry-audit` (v0.0.1) |
| 05 | **Test data & fixtures** | "Seed data must be schema-faithful, referentially sound, production-distributed, edge-covering, and reproducible. Don't invent fields." | Claessen–Hughes (QuickCheck) '00; Myers (boundaries); Codd '70 | `seed-data-generator` (v0.0.1) |
| 06 | **Error handling** | "An error is information; swallowing it destroys it. Ban the anti-patterns actually present, with counts — not a generic checklist." | Goodenough '75; Parnas (fail-fast); Pike (errors-are-values) | `error-handling-rules` (v0.0.1) |
| 07 | **Debugging & reproduction** | "A repro fails for the right reason or it's questions; a fix without a traced causal chain is a guess — fix the cause, not the crash site." | Zeller '02 (delta debugging); Popper; Weiser '81 (slicing); Kildall '73 | `minimal-repro-builder` (v0.0.1) · `bug-trace-before-fix` (v0.0.1) |
| 08 | **Change management & flags** | "A flag is ONE boundary with a safe default and a removal path; scattering checks is a 2^N state explosion." | Parnas '72; Fowler (branch-by-abstraction); Knuth | `feature-flag-wrap` (v0.0.1) |
| 09 | **Dead code & reachability** | "Deletion requires proof of unreachability; dynamic/string/framework references defeat static proof, so grade confidence and protect contracts." | Aho–Sethi–Ullman (dead-code elim); tree-shaking | `dead-code-scan` (v0.0.1) |
| 10 | **Production hardening** | "Hardening is triage, not rewrite: rank by P(incident)×blast-radius; every finding names the line, the mechanism, and the consequence." | Nygard '07; Gray '85; Saltzer–Schroeder '75 | `hardening-checklist` (v0.0.1) |
| 11 | **Onboarding & comprehension** | "A brief transfers the system's theory; be faithful to real paths or say you can't — fidelity over fluency." | Naur '85; Parnas (module guide); Brooks | `onboarding-brief` (v0.0.1) |
| 12 | **Knowledge capture** _(adjacent)_ | "An SOP is faithful to observed actions; flag the unclear, never invent a step." | Gilbreth (motion study); Gawande; Polanyi | `recording-to-sop` (v0.0.1, drafted) |
| 13 | _Invariant & contract discovery_ | _(reserved)_ | Hoare '69; Meyer (DbC) | — |
| 14 | _Drift & entropy control (ratchets/baselines)_ | _(reserved)_ | Shannon (entropy); Lehman's laws | — |

The map grows as prompts are added; themes are not fixed in advance.

## Productization note (read before extracting)

This library is seeded inside `dharma_swarm` for convenience while we build it.
When it becomes a real offering, **graduate it to its own repo** — sellable
product IP should not be entangled with this repo's governance, license, or
history. Treat the path here as a staging area, not the final home.

## Changelog

- **2026-06-25** — library seeded as **Stop the Slop**; format + thematic map +
  `FOUNDATIONS.md` lineage canon defined.
  - `01/dependency-risk-triage` v0.0.1 — rewrite of a kit's lockfile prompt;
    found 8 real advisories this repo's heuristic missed.
  - `02/circular-dependency-triage` v0.0.1 — rewrite of a kit's cycle-detection
    prompt; AST + Tarjan SCC over `dharma_swarm/`. Full graph: 12 SCCs; rigorous
    load-time pass (`TYPE_CHECKING` excluded): **exactly 1** genuine boot-risk
    cycle (provider/router) — now fixed (load-time graph → DAG). Demo also keeps
    the author's own first-draft over-count as the cautionary case.
  - `03/performance-bottleneck-triage` v0.0.1 — rewrite of Vaylo Studios' "perf
    from logs" prompt; routes to a profiler instead of guessing. `-X importtime`
    on `dharma_swarm` found `models` = 21% of boot (29 eager Pydantic builds),
    Amdahl-bounded, and named pydantic/ssl/stdlib as irreducible floor.
- **2026-06-25 (batch 2)** — codename **PRAMĀṆA** pencilled in; added the
  analysis-vs-generation discipline note.
  - `04/retry-audit` v0.0.1 — rewrite of a kit's retry-finder. Found the canonical
    `resilience.RetryPolicy` **under-adopted** (4 importers), credited 2 correct
    ad-hoc backoffs, flagged 8 `while True` loops UNCONFIRMED (not guessed).
  - `05/seed-data-generator` v0.0.1 — rewrite of a kit's seed prompt (generation:
    faithfulness-or-stop). Honest applicability note — `dharma_swarm` has no
    relational schema to seed; demoed the discipline on real Pydantic models
    instead of faking a DB.
  - `06/error-handling-rules` v0.0.1 — rewrite of a kit's `.cursorrules` prompt
    (generation: ban what's measured). Grounded the bans in the repo's real 244
    silent swallows + 2,275 broad catches; spared the narrow intentional ones.
- **2026-06-25 (batch 3)** — name **settled: Pramāṇa Probe**.
  - `07/minimal-repro-builder` v0.0.1 — rewrite of a kit's repro prompt. Tested
    against a real audit claim (telos "GATES=13 vs 11"): verified `CORE_GATES==11`,
    returned **NOT REPRODUCED + questions** instead of fabricating a failing test
    (and quietly fact-checked the audit).
  - `08/feature-flag-wrap` v0.0.1 — rewrite of a kit's flag prompt. Audited the
    repo's real `DHARMA_SPINE_DISPATCH`: already a single-boundary, default-OFF
    flag → returned clean, proposed no churn.
  - `09/dead-code-scan` v0.0.1 — rewrite of a kit's dead-code analyzer. 181 orphan-
    module candidates, correctly **capped at MEDIUM** (this repo loads dynamically);
    registry/API/CLI files marked LOW — review checklist, never auto-delete.
- **2026-06-25 (batch 4)** — debugging theme gains a sibling; 3 new themes (10–12).
  - `07/bug-trace-before-fix` v0.0.1 — trace-before-fix (Weiser slicing). Demoed on
    the real provider/router chain: pinned the cause to the eager `__init__` import
    (hop 1), which is where the fix landed — not the crash site.
  - `10/hardening-checklist` v0.0.1 — production triage (Nygard/Gray). On
    `web_search.py`: 5 line+mechanism findings (must-fix = unchecked `choices[0]`
    shape at :126); cleared the auth/secret bucket (return-clean).
  - `11/onboarding-brief` v0.0.1 — fidelity-over-fluency (Naur/Parnas/Brooks). Real
    verified brief for `dharma_swarm` + pointer to its own `make onboard`.
  - `12/recording-to-sop` v0.0.1 (**adjacent, drafted**) — knowledge capture; honest
    non-applicability (no recording here to test, not faked).
