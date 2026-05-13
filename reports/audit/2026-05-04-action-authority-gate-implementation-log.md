# Action Authority Gate Implementation Log

**Date:** 2026-05-04  
**Worktree:** `/Users/dhyana/dharma_swarm_action_authority_spec`  
**Branch:** `chore/action-authority-gate-spec`

## Implemented

- Added a central runtime helper module: `dharma_swarm/action_authority/runtime.py`.
- Added tier-scoped Fourfold evidence thresholds through `min_evidence_files_for_tier`.
- Wired AAG checks into:
  - orchestrator dispatch
  - AgentRunner local write/edit/shell tools
  - AutonomousAgent side-effect and world-action tools
  - `world_actions.py`
  - REST ontology/workflow API mutation paths
  - dashboard chat write/edit/shell/agent-control tools
  - ToolRegistry dispatch
  - LocalSandbox and LocalSandboxProviderAdapter execution
  - DiffApplier apply/apply-and-test
  - cron job dispatch
  - A2A dispatch
  - roaming dispatch/poller git and command surfaces
- Preserved default-off behavior through `DHARMA_ACTION_AUTHORITY_GATE`.
- Preserved shadow behavior as effective allow with recorded/would-block decision.
- Enforce mode now blocks representative high-authority side effects when no matching Fourfold warrant exists.
- Added `WitnessLog` support to `GateDecisionRecord` persistence:
  - `GateDecisionRecord.witness_log_id`
  - `GateDecisionRecord.has_witness_log -> WitnessLog`
  - `TelicSeam.record_gate_decision` creates and links the witness log.

## Verification

Commands run:

```bash
python -m py_compile dharma_swarm/action_authority/gate.py dharma_swarm/action_authority/runtime.py dharma_swarm/orchestrator.py dharma_swarm/agent_runner.py dharma_swarm/autonomous_agent.py dharma_swarm/world_actions.py dharma_swarm/api.py api/chat_tools.py dharma_swarm/tool_registry.py dharma_swarm/contracts/runtime_adapters.py dharma_swarm/diff_applier.py dharma_swarm/cron_runner.py dharma_swarm/sandbox.py dharma_swarm/a2a/a2a_server.py dharma_swarm/roaming_dispatch_daemon.py dharma_swarm/roaming_poller.py dharma_swarm/telic_seam.py dharma_swarm/ontology.py
pytest -q tests/test_action_authority_gate.py tests/test_telic_seam.py tests/test_diff_applier.py tests/test_sandbox.py tests/test_tool_registry.py tests/test_world_actions.py tests/test_autonomous_agent.py tests/test_a2a.py tests/test_api.py tests/test_chat_tools.py tests/test_cron_runner.py tests/test_runtime_contract_adapters.py tests/test_agent_runner.py tests/test_ontology_registry.py tests/test_roaming_dispatch_daemon.py tests/test_roaming_poller.py
git diff --check
```

Result:

- `py_compile` passed.
- Targeted pytest set: `388 passed, 3 warnings`.
- `git diff --check` passed.

Warnings observed:

- Existing pytest config warning: unknown `timeout` option.
- Existing unknown `pytest.mark.timeout` warnings in `tests/test_agent_runner.py`.

## Not Yet Done

- No TUI/terminal adapter code was changed in this slice. That path must use the `terminal-guardian` workflow and compact-terminal verification.
- No broad enforce rollout flag was enabled. Runtime default remains off.
- No full-suite run was performed. The recent full suite is known to be long; this implementation used compile plus targeted tests over changed surfaces.
- Existing branch state was already ahead/behind `origin/main`; no rebase or merge was attempted.

## Operational Guidance

The next safe move is to keep AAG in default-off/shadow mode while collecting would-block evidence on real runs. Enforce should be enabled surface by surface only after reviewing shadow logs and attaching valid Fourfold warrants where required.
