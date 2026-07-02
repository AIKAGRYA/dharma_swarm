# NVIDIA Skill Steward Assignment - 2026-06-30

## Decision

Assign the `NVIDIA/skills` skill set to `qwen_code` as the house machine-learning specialist.

## Rationale

The installed NVIDIA skill stack is mostly practical ML engineering: accelerated computing, model training, inference, deployment, GPU/runtime diagnostics, NeMo, TAO, Holoscan, DeepStream, cuOpt, RAPIDS, Jetson, Omniverse, RAG, and physical-AI workflows.

`qwen_code` is already a registered living agent with software-engineering capability evidence and manual, evidence-only authority. That makes it a good specialist seat for technical ML work without granting it broad governance power.

## Recorded Changes

- Updated `/Users/dhyana/.dharma/agents/qwen_code/living_agent.json`
  - role: `machine_learning_specialist`
  - department: `machine_learning`
  - specialist seat: `house_machine_learning_specialist`
  - owned skill stack: `NVIDIA/skills`
  - authority remains: `external_worker_evidence_only`
- Updated `examples/agents/qwen_code.registration.json`
  - source registration now preserves the ML-specialist assignment.
- Added `docs/agents/qwen_code/ML_SPECIALIST_CHARTER.md`
  - contains routing rules, summon contract, and verification standard.

## Operating Rule

Default NVIDIA/ML skill tasks to `qwen_code`.

Escalate:

- measurement/benchmark claims to `forge_measurement_guardian` or `ci_measurement_guardian`;
- architecture/governance questions to `codex_composer` or `opus_composer`;
- infrastructure/runtime repair to `conductor_codex` or Codex workcells;
- external vendor research to `perplexity-computer`.

## Boundary

This assignment does not make `qwen_code` a sovereign holon and does not expand write/approval authority.
