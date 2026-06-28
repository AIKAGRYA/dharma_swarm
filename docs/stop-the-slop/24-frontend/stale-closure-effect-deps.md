---
id: stale-closure-effect-deps
version: 0.0.1
theme: 24-frontend
status: tested
invariant: >
  A React effect/callback closes over the props/state of the render it was created in.
  If the dependency array omits a value the effect uses, the effect runs with a STALE
  closure — old data, a listener bound to an old handler, a setInterval reading the
  first render's state. The deps array must list every reactive value the effect reads;
  an empty/incomplete array is a correctness bug, not an optimization.
lineage:
  - "referential transparency / closures — a closure captures its defining scope, frozen"
  - "React's exhaustive-deps rule — the deps must match what the effect reads"
  - "the stale-closure footgun (Abramov) — intervals/listeners reading frozen state"
ground_truth_tools: ["the react-hooks/exhaustive-deps lint", "AST: useEffect/useCallback deps vs referenced vars", "intervals/listeners capturing state"]
returns_clean: true
---

## Prompt

> Audit React **stale closures / effect dependencies**. The invariant: an effect/callback
> freezes the values it closes over at creation; if the dependency array omits a reactive
> value the effect *uses*, it runs stale. Find `useEffect`/`useCallback`/`useMemo` whose
> deps **omit a value referenced in the body**, and especially `setInterval`/event
> listeners that read state with an empty `[]` (classic stale-closure: forever reading
> the first render's value). For each: the hook, the missing dep, the bug (stale read /
> stale handler / leaked listener), the fix (add the dep / use a ref / functional setState
> / cleanup). **Route to `eslint-plugin-react-hooks` exhaustive-deps** — it's the real
> instrument. **Return clean** if deps are exhaustive.

## Why it's built this way

This is a real correctness bug class (not style) and there's a *precise* linter for it —
so the discipline is run exhaustive-deps and explain the *why* (closures freeze scope),
plus catch the interval/listener case the lint sometimes can't see across indirection.

## Demonstration run

**Target:** `dashboard/` (Next.js/React), 2026-06-25.

- **Surface:** **63** `useEffect` call sites in the dashboard. Each is a stale-closure
  candidate if its deps are incomplete.
- **The instrument:** `eslint-plugin-react-hooks`'s **exhaustive-deps** rule is the
  ground truth — recommend confirming it's enabled at **error** (not warn/off) in the
  dashboard's ESLint config; if off, that's the finding (the bug class is unguarded). Then
  the priority manual check: any `useEffect` with `setInterval`/`addEventListener` + `[]`
  deps reading state — the forever-stale case. UNASSESSED-per-site until the lint runs;
  the prompt hands the instrument + the high-risk pattern, not a guessed list.

## Changelog

- **v0.0.1** (2026-06-25) — stale-closure/effect-deps (closures/exhaustive-deps). Tested
  on `dashboard/`: 63 `useEffect` sites → route to exhaustive-deps-at-error + manual
  interval/listener-with-`[]` check; honest per-site UNASSESSED pending the lint.
