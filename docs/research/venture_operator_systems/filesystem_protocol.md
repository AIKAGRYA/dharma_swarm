# Venture Operator Dossier Filesystem Protocol

**Date:** 2026-05-27  
**Purpose:** Define how Dharma Swarm stores observations about Cofounder, Polsia, and adjacent operator systems.

---

## Canonical Runtime Log

```text
~/.dharma/venture_cell/DARSHAN/external_operator_observations.jsonl
```

Each line is an `ExternalOperatorObservation` from:

```text
dharma_swarm/venture_cell/darshan/schema.py
```

Use:

```text
python -m dharma_swarm.venture_cell.darshan.cli log-operator
```

This is the append-only operational memory of what happened.

## Repo Dossier

```text
docs/research/venture_operator_systems/
  README.md
  cofounder_darshan_onboarding_2026-05-27.md
  operator_comparison_matrix_2026-05-27.md
  dharma_swarm_native_operator_target.md
  filesystem_protocol.md
```

This is the curated study layer: interpreted findings, comparisons, design implications, and next architecture.

## Observation Fields To Preserve

For each external-operator interaction, capture:

- operator;
- track: collaborator, observatory, or benchmark;
- VentureCell;
- surface;
- session phase;
- prompt given;
- expected output;
- response summary;
- actions observed;
- agent roles visible;
- artifacts or URLs;
- screenshot references;
- capabilities observed;
- limitations observed;
- allowed scope;
- forbidden scope;
- quality score;
- autonomy risk score;
- human intervention points;
- missing receipts;
- reusable operator pattern;
- Dharma Swarm design implication;
- follow-up task.

## Interpretation Rule

Do not trust screenshots as complete truth. Treat them as field observations.

Each observation should be converted into at least one of:

- a capability to copy;
- a boundary to enforce;
- a missing receipt to build;
- a future operator primitive;
- a risk to avoid;
- a Darshan task.

## Cofounder Active Logging Rule

Every meaningful Cofounder interaction should be logged if it changes one of:

- Darshan business plan;
- brand/design;
- website;
- distribution;
- sales/revenue;
- publishing;
- task routing;
- approval flow;
- managed service setup;
- analytics;
- external outreach.

## Polsia Benchmark Logging Rule

If Polsia is later used, log both:

```text
~/.dharma/venture_cell/DARSHAN/external_operator_observations.jsonl
~/.dharma/venture_cell/DARSHAN/polsia_observations.jsonl
```

The first is canonical. The second preserves Polsia-specific history.

## Native Operator Build Rule

No external-operator lesson counts until it becomes one of:

- a code primitive;
- a VentureCell lifecycle field;
- a TaskBoard adapter;
- an ontology object/action;
- a Chetana memory;
- a DecisionLog entry;
- a public Darshan workflow;
- a refusal/correction gate;
- a dashboard/control-surface requirement.

The dossier exists so Dharma Swarm can eventually build its own Cofounder/Polsia-like operating interface with deeper gates, better receipts, and less capture risk.
