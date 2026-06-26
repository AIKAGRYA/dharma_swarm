---
id: feature-flag-wrap
version: 0.0.1
theme: 08-change-management
status: tested
invariant: >
  A feature flag is ONE decision point at the highest reasonable boundary, with a
  safe default and a documented removal path — never a constant scattered through
  child code. Scattering the check multiplies the states you must reason about
  (2^N for N checks) and guarantees a half-flagged feature. Wrap the entry point;
  don't pepper the leaves.
lineage:
  - "Parnas 1972 — information hiding: isolate the decision behind one interface"
  - "Fowler — branch by abstraction / feature toggles as a single seam"
  - "Knuth — single source of truth; one place to change, one place to remove"
ground_truth_tools: ["grep/AST for every entry point of the feature", "the real flag system", "plan-before-apply diff"]
returns_clean: true
---

## Prompt

> Wrap an existing feature in a flag so it can be toggled per user/environment
> without deleting code. The invariant (Parnas, Fowler): a flag is **one** decision
> point at the **highest reasonable boundary**, with a **safe default** and a
> **documented removal path**. Scattering `isEnabled()` through child code
> multiplies states and produces a half-flagged feature — the thing to prevent.
>
> **Context:**
> - Feature: `[describe — e.g. the analytics widget on /dashboard]`
> - Flag name: `[SNAKE_CASE]`  · System: `[env var | LaunchDarkly | PostHog | config file]`
> - Default for existing users: `[ON | OFF]`
>
> **Do this — and SHOW THE PLAN BEFORE APPLYING:**
> 1. **Find every entry point** where the feature is rendered/called/imported
>    (grep/AST — enumerate them; don't assume there's one).
> 2. **Place a single check at the highest common boundary** that dominates those
>    entry points. Prefer wrapping the one entry over N scattered checks. State
>    *where the flag boundary lives* and why it's the highest reasonable one.
> 3. **Safe fallback when OFF:** previous behavior, or render nothing — whichever
>    preserves the prior contract. **If the fallback is non-obvious, ask** before
>    applying.
> 4. **Define the flag** in the chosen system with the specified default.
> 5. **No flicker:** if the flag read is async, handle the loading state so initial
>    render doesn't flash the wrong branch.
> 6. **Removal breadcrumb** at each check: `// Flag: <name> — remove this check and
>    the else branch when fully rolled out`.
>
> **Output the plan first** — touched files + exactly where the single boundary
> sits — and wait for confirmation before editing. **Return clean:** if the feature
> already has a single clean boundary, say so and don't add ceremony.

## Why it's built this way

The kit's version is already disciplined (highest boundary, ask-if-fallback-
unclear, plan-before-apply). We name the *why*: scattering is a state-space
explosion (Parnas's whole point — hide the decision behind one interface), and a
flag without a removal breadcrumb becomes permanent debt (Knuth's single source of
truth, in reverse). "Wrap the entry, not the leaves" is the load-bearing rule.

## Demonstration run — the return-clean case

**Target:** `dharma_swarm/`, 2026-06-25. The repo already gates a feature
(spine dispatch) behind an env-var flag; we audit it against the invariant.

- `DHARMA_SPINE_DISPATCH` appears in **exactly 2 places**, both in `orchestrator.py`:
  one docstring (`:2274`, documents "default OFF") and **one** runtime check
  (`:2447`, `os.environ.get("DHARMA_SPINE_DISPATCH") == "1"`).
- Verdict against the invariant: **one decision point, at the dispatch boundary,
  default-OFF, documented.** This is the textbook-correct shape — a single seam,
  not scattered leaf checks.

**Return-clean output:** *"`DHARMA_SPINE_DISPATCH` is already a single-boundary,
default-safe flag (1 check in `orchestrator.py:2447`). No change needed; if
anything, add a removal breadcrumb for when spine dispatch is fully rolled out."*

That's the discipline for a *modification* prompt: when the code already satisfies
the invariant, it credits it and proposes nothing — it does not scatter new checks
to look busy. (A heuristic prompt asked to "add a flag" would happily add ceremony.)

## Changelog

- **v0.0.1** (2026-06-25) — rewrite of a kit's feature-flag prompt. Named the
  invariant (one boundary; scattering = 2^N state explosion, Parnas), kept plan-
  before-apply, added return-clean/credit-correct. Tested against `dharma_swarm`'s
  real `DHARMA_SPINE_DISPATCH` flag — confirmed it already meets the invariant
  (single boundary, default OFF) and proposed no churn.
