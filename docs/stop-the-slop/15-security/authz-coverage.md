---
id: authz-coverage
version: 0.0.1
theme: 15-security
status: tested
invariant: >
  Every endpoint/operation that reads or mutates protected data must pass an
  authorization check — authentication (who are you) is not authorization (may you do
  this). The dangerous gap is the endpoint that forgot the check (BOLA/IDOR: object
  access without verifying ownership). Authz must be complete mediation: default-deny,
  checked at every protected operation, ideally centrally so an endpoint can't silently
  ship unguarded.
lineage:
  - "Saltzer & Schroeder — complete mediation + fail-safe (default-deny) defaults"
  - "OWASP API Top 10 — #1 is Broken Object-Level Authorization (BOLA/IDOR)"
  - "the confused-deputy — verify the requester's authority for THIS object, not just identity"
ground_truth_tools: ["enumerate every protected route/operation", "which have an authz check? (middleware/dependency/decorator)", "ownership checks on object access"]
returns_clean: true
---

## Prompt

> Audit **authorization coverage**. The invariant (Saltzer–Schroeder, OWASP API #1):
> every protected read/mutation must pass an authz check, default-deny, ideally
> centralized. Enumerate the routes/operations; for each protected one, is there an
> **authorization** check (not just authentication), and on object access, an
> **ownership** check (does this user own *this* record — the BOLA/IDOR gap)? Flag every
> endpoint with **no** check or only authn. Prefer a central guard (middleware/dependency)
> so coverage is provable, not per-endpoint memory. **Return clean** only if every
> protected operation is gated; name the count checked vs total.

## Why it's built this way

The breach is almost never a broken check — it's a *missing* one on one forgotten
endpoint (OWASP API #1). So coverage must be **enumerated** (every route, checked vs not),
and centralized mediation is the structural fix. Authn≠authz is the distinction the
prompt forces.

## Demonstration run

**Target:** `dharma_swarm/api/` — 2026-06-25.

- **Signal that demands investigation:** **25 routers**, but auth-related code
  (`Depends(...auth)`, `Security`, `Authorization`) appears in only **2** files. Two
  readings: (a) auth is enforced **centrally** (one middleware gates all routes) — *good,
  confirm it*; or (b) **most endpoints are unauthenticated** — a serious gap. **The audit
  refuses to guess** between them: the next probe is to find the global middleware/
  dependency and verify it covers all 25 routers, vs enumerate which routers declare a
  guard.
- **Disciplined output:** "25 routers; explicit auth in 2 files → either central
  middleware (verify coverage) or 23 unguarded routers (critical). Enumerate per-route
  authz + ownership checks before shipping." This is the exact endpoint-by-endpoint
  coverage table the invariant demands — and the honest refusal to declare clean *or*
  breached without the enumeration.

## Changelog

- **v0.0.1** (2026-06-25) — authz coverage (Saltzer–Schroeder/OWASP-API-#1/BOLA):
  enumerate routes, authn≠authz, ownership checks, central mediation. Tested on
  `dharma_swarm/api`: 25 routers vs auth in 2 files → flagged as the must-resolve fork
  (central guard vs unguarded), refused to guess.
