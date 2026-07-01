# Packet 09: Cybernetics And Loop Closure

Packet ID: `ctx.cybernetics-loop-closure`

Use when touching the 13 cybernetic loops, Loop 1 provider trunk, One Wire,
loop supervisor, closure receipts, cybernetics codex, or verifier-ranker proof.

Do not use for generic governance docs unless a loop closure claim is involved.

## Authority Model

- Intent owner: `loop-closure-2026-06` and
  `cybernetics-codex-stewardship-2026-06` tracks
- Map owner: `CYBERNETIC_LOOP_MAP.md`
- Steward owner: `docs/ops/CYBERNETICS_CODEX.md`
- Runtime owner: `dharma_swarm/loop_supervisor.py`, provider/runtime dispatch,
  relevant loop modules
- Proof owner: loop closure receipts, verifier-ranker receipts, One Wire quorum
  evidence, targeted tests

Core invariant: a loop is not closed until it senses, interprets, constrains,
acts, and adapts on real data with receipts to its declared owner.

## Mission

Convert cybernetic-loop ambition into executable closure. The system should not
mistake a dossier, demo, or internal artifact for adaptive loop closure.

## First Reads

L0 Safety:

- `make onboard`
- `docs/agents/cybernetics_codex/CONTEXT_ENGINEERING.md`

L1 Route:

- `loop-closure-2026-06` track block
- `cybernetics-codex-stewardship-2026-06` track block
- `CYBERNETIC_LOOP_MAP.md`

L2 Owners:

- `dharma_swarm/loop_supervisor.py`
- `docs/ops/CYBERNETICS_CODEX.md`
- `scripts/agentops/verifier_ranker_v0_*`
- provider and dispatch owners for Loop 1

L3 Evidence:

- `reports/loop_closure/**`
- `reports/agentops/verifier_ranker_v0/**`
- `reports/agentops/semantic_receipts/**`
- `reports/governance/runtime_spine_*`

L4 Search:

- `rg -n "sense|interpret|constrain|act|adapt|One Wire|quorum|loop closure|Loop 1" CYBERNETIC_LOOP_MAP.md docs reports dharma_swarm scripts tests`

L5 Seat:

- `cybernetics_codex` only after loading its context desk and current receipts.

## Live Probes

```bash
make onboard
python3 scripts/agentops/verifier_ranker_v0_verify_package.py
```

Run loop-specific tests when touching code. For provider trunk work:

```bash
pytest tests/test_runtime_provider.py tests/test_provider_smoke.py tests/test_orchestrate_live.py
```

For TELOS/external loops:

```bash
pytest tests/test_telos_morning_refinery.py
```

## Retrieval Contract

- Query: "13 loops sense interpret constrain act adapt owner receipts"
  Source family: cybernetic loop map and loop closure reports.
- Query: "One Wire invariant external acted receipts quorum"
  Source family: loop docs, governance reports, external receipt files.
- Query: "Loop 1 provider chain dispatch_dropoff closure"
  Source family: provider/runtime reports and tests.

## Operating Loop

1. Identify the loop number and declared owner.
2. State which phase is missing: sense, interpret, constrain, act, or adapt.
3. Confirm real-data input and receipt path.
4. Make one narrow closure improvement.
5. Verify with targeted test or receipt.
6. Update status honestly: closed, partial, blocked, or not started.
7. Never let internal-only artifacts affect archive fitness.

## Guardrails

- Do not call a demo a loop closure.
- Do not omit failed checks.
- Do not weaken telos gates or One Wire quorum.
- Do not let internal artifacts touch archive fitness.
- Do not create a new receipt system.
- Do not smooth over contradictions between runtime evidence and docs.

## Context Budget

- Tiny: `make onboard`, cybernetics context desk, this packet.
- Standard: tiny plus loop map, current loop report, owner module, verifier.
- Deep: standard plus Loop 1 provider chain reports, One Wire evidence, tests,
  and semantic receipts.

## Done Criteria

Complete means:

- loop number and phase are named;
- real input, constraint, action, adaptation, and receipt are present or blocked
  explicitly;
- verifier/test output is recorded;
- no external proof claim is made without external acted receipt.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.cybernetics-loop-closure.
For every claim, name the loop number and phase: sense, interpret, constrain,
act, adapt. Demos and reports are not closure. Closure requires real data,
constraints, action, adaptation, and receipts to the declared owner. Preserve the
One Wire invariant and verify with the narrowest loop-specific gate.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.cybernetics-loop-closure",
  "loop_id": "",
  "phase_touched": "sense|interpret|constrain|act|adapt",
  "owner_surface": "",
  "real_data_source": "",
  "action_taken": "",
  "adaptation_observed": "",
  "receipts": [],
  "tests": [],
  "status": "closed|partial|blocked|not_started",
  "next_blocker": ""
}
```
