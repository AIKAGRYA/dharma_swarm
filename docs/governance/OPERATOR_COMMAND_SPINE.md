# Operator Command Spine v0

The Operator Command Spine is the narrow Python boundary that turns fuzzy human
operator intent into a governed AgentOps packet draft and turns completed
AgentOps reports back into learning evidence.

It is not a new runtime subsystem, dashboard, API surface, ontology migration,
provider router, memory authority, merge bot, or live-swarm launcher.

## Loop

```text
human prompt
  -> prompt intent
  -> IntentRouter decomposition
  -> optional KnowledgeStore prescriptions
  -> optional MissionState attachment
  -> AgentOps work-packet draft
  -> AgentOps report review
  -> human YDS rating capture
  -> Rust-readiness decision for stable deterministic kernels
```

The v0 implementation lives in
`dharma_swarm/operator_core/command_spine.py` and the non-executing CLI is
`scripts/governance/plan_operator_command.py`.

## Dry-Run First

The planner drafts an AgentOps-compatible packet shape, but it does not write
that packet, create a worktree, run gates, commit, merge, push, or launch live
autonomy.

Example:

```bash
python scripts/governance/plan_operator_command.py \
  --prompt "Build the operator command spine and add regression tests" \
  --allowed-file dharma_swarm/operator_core/** \
  --allowed-file tests/test_operator_command_spine.py \
  --allowed-file docs/governance/**
```

If `allowed_files` are inferred rather than operator-provided, the plan marks
`requires_human_scope=true` and the next step is to tighten scope before running
AgentOps.

## Report Ingestion

`review_agentops_reports()` reads one or more AgentOps `report.json` files or a
directory containing reports. It summarizes gate health, scope cleanliness,
commit state, approval state, waste patterns, and exactly one next
recommendation.

## Human YDS Boundary

`record_human_yds_rating()` appends explicit human/operator/Dhyana ratings to a
JSONL ledger. AI cannot assign authoritative YDS ratings. Non-human sources are
rejected.

The ledger path is explicit. A reasonable local default for callers is:

```text
~/.dharma/yds/human_quality_ratings.jsonl
```

## Rust Boundary

Rust is not introduced into the command spine. The spine is semantic,
human-facing, and still stabilizing, so Python remains the correct orchestration
layer.

`evaluate_rust_readiness()` is the phase gate for future Rust extraction. A
component is only a Rust candidate when it is:

- deterministic
- boundary-stable
- covered by green focused tests
- driven by a concrete hot-path, security, or Python-pain reason

Good future Rust candidates are scope/diff validation, append-only ledger
integrity, hash-chain verification, and high-volume report scanning. Intent
routing, mission planning, YDS semantics, and operator dialogue stay Python.
