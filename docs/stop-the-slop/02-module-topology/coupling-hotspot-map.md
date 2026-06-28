---
id: coupling-hotspot-map
version: 0.0.1
theme: 02-module-topology
status: tested
invariant: >
  Change cost is set by coupling. A high fan-in module (many depend on it) makes
  every change ripple widely — touch it carefully, test it hardest. A high fan-out
  module (depends on many) is hard to test in isolation and fragile to others'
  changes. Rank refactor/where-to-be-careful by measured fan-in/fan-out, not by gut.
lineage:
  - "Parnas 1972 — modules decomposed by secrets; minimize inter-module coupling"
  - "Robert Martin — instability metric I = Ce/(Ca+Ce); stable vs volatile modules"
  - "Constantine & Yourdon — coupling/cohesion as the core structural metrics"
ground_truth_tools: ["AST import graph (fan-in/fan-out)", "grimp/pydeps", "the actual call graph"]
returns_clean: true
---

## Prompt

> Map the **coupling hotspots** of this codebase. The invariant (Parnas, Martin):
> change cost is coupling. Build the import/dependency graph and rank modules by
> **fan-in** (how many depend on this — change here ripples widest) and **fan-out**
> (how many this depends on — hard to test in isolation). Don't guess "this looks
> central" — measure it.
>
> **Output two ranked lists with numbers:**
> - **Highest fan-in** — the modules a change ripples through. These need the most
>   tests and the most careful change review; they're your de-facto API.
> - **Highest fan-out** — the modules hardest to unit-test and most fragile to
>   others' edits. Candidates for dependency-injection / interface-narrowing.
> - For each, name *why* it's coupled (a shared type bag? a god object? a registry?)
>   and the **lowest-churn** intervention (split a types module out, inject a
>   dependency, introduce an interface).
>
> **Return clean** if coupling is flat (no module dominates). Do not invent a
> hotspot. Flag shared *type/DTO* modules separately — high fan-in there is often
> fine (a stable contract), not a smell.

## Why it's built this way

Coupling is the measurable form of "hard to change." Martin's instability metric
formalizes it; Parnas's whole 1972 paper is about minimizing it. The discipline is
to **measure fan-in/fan-out from the real graph** and distinguish a healthy shared
contract (stable types) from a genuine god-object hub — a distinction a vibe-read
misses.

## Demonstration run

**Target:** `dharma_swarm/` (784 modules), 2026-06-25. Tool: AST import graph.

**Highest fan-in (change ripples widest):**
`models` (**156** dependents) · `daemon_config` (112) · `runtime_state` (38) ·
`stigmergy` (33).

**Highest fan-out (hardest to test in isolation):**
`swarm` (**57** deps) · `orchestrate_live` (48) · `agent_runner` (42) ·
`dgc_cli` (35) · `evolution` (32).

**Reading it:** `models` at 156 fan-in is the de-facto contract — high fan-in is
*expected* for a shared-types module, **but** it's also the slowest module to
import (21% of boot, per `03/performance`) and any change validates against 156
callers. Intervention: keep it as the contract but split rarely-used models out to
shrink blast radius + boot cost. `swarm` (57 fan-out, 3,227 lines) is the genuine
hub-to-watch — hard to test alone; inject its heaviest collaborators behind
interfaces. `daemon_config` at 112 fan-in is a config singleton — fine, but a
breaking change there is a 112-module event.

## Changelog

- **v0.0.1** (2026-06-25) — coupling map via fan-in/fan-out (Parnas/Martin). Tested
  on `dharma_swarm/`: `models` (156 fan-in, flagged as contract-not-smell but a
  boot/blast-radius cost), `swarm` (57 fan-out, the real hub). Distinguished shared
  contracts from god-object hubs.
