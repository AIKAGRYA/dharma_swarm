---
id: config-drift-audit
version: 0.0.1
theme: 21-drift-and-entropy
status: tested
invariant: >
  Configuration is code's hidden state: an env var, flag, or setting that exists in one
  environment but not another (or with a different value) causes "works on my machine"
  and prod-only failures. Config must be declared in one schema, validated at startup
  (fail fast on missing/invalid), and have safe defaults — not read ad hoc via
  os.environ.get scattered across the codebase with silent fallbacks that mask
  misconfiguration.
lineage:
  - "12-factor III — config in the environment, strictly separated from code"
  - "fail-fast (Shore) — validate config at boot, don't discover it missing at runtime"
  - "Shannon — drift is measurable divergence (entropy) between environments"
ground_truth_tools: ["enumerate every env var / setting read", "is it declared+validated centrally or read ad hoc?", "diff config keys across env templates"]
returns_clean: true
---

## Prompt

> Audit **config drift & hygiene**. The invariant (12-factor, fail-fast): config is hidden
> state; an env var present in one environment and absent in another is a prod-only bug.
> (1) **Enumerate** every `os.environ`/`process.env`/settings read across the codebase.
> (2) Are they **declared and validated centrally** (one schema, fail-fast at boot), or
> read ad hoc with **silent `.get(..., default)` fallbacks** that mask a missing value?
> (3) **Diff** the keys against the env templates (`.env.example`) — keys read-but-not-
> documented, or documented-but-unread, are drift. For each: the key, the risk (silent
> wrong behavior in prod), the fix (central typed config + startup validation). **Return
> clean** for a centralized, validated config.

## Why it's built this way

The failure is a config that *silently defaults* instead of failing loudly — the
`os.environ.get("X", fallback)` scattered everywhere hides misconfiguration until prod
behaves subtly wrong. 12-factor + fail-fast is the cure: one schema, validated at boot.
The discipline is enumerating reads and diffing against the documented set.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Pattern to check:** the repo reads config via `os.environ.get(...)` in many places
  (e.g. `DHARMA_SPINE_DISPATCH`, provider keys, `TINY_ROUTER_BACKEND`). The audit
  enumerates these and asks: is there **one** typed settings object validated at startup,
  or are they read ad hoc with silent defaults? Scattered `.get` with fallbacks = drift-
  prone (a typo'd or missing var silently takes the default).
- **Diff:** compare the set of env vars actually read against `.env`/templates and the
  governance env docs — flag read-but-undocumented keys (operators won't set them) and
  documented-but-unread (stale). The provider-routing track already centralizes keys in
  `api_keys` — credit that; flag the rest.
- **Fix:** a central `Settings` (Pydantic `BaseSettings`) validated at boot turns silent
  drift into a loud startup error. Output: the enumeration + the drift diff + the
  centralization recommendation.

## Changelog

- **v0.0.1** (2026-06-25) — config-drift audit (12-factor/fail-fast/Shannon): enumerate
  reads, central+validated vs ad-hoc-silent-default, diff vs templates. Tested on
  `dharma_swarm`: scattered `os.environ.get` with fallbacks flagged as drift-prone;
  `api_keys` centralization credited; Pydantic `BaseSettings` boot-validation as the fix.
