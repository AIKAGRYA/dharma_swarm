# boot_sub_swarm Dry-Run Follow-On Plan

Date: 2026-05-28
Status: follow-on plan only
Scope: docs plan; no code changes in this pass

## Order

This work is sequenced after the DGM foundation lands and is verified. Do not start it until the DGM path has a green baseline for proposal, gate, evaluation, archive lineage, and `AgentRunner.run_task()` delegation. Sub-swarms should not become another speculative runtime before the parent can safely evolve, evaluate, and record its own changes.

## Objective

Add a dry-run-only `boot_sub_swarm` planning surface that can read a `spawn_sub_swarm_spec()` JSON file and produce a deterministic boot plan plus receipt. The first deliverable proves the interface, validation, lifecycle shape, and safety gates without starting any child process.

Hard rule: this phase must not spawn, fork, exec, SSH, Docker-run, tmux-start, launchd-load, or otherwise start a live child swarm process. A dry-run receipt is the only allowed output.

## Interfaces

- Existing input: `dharma_swarm.world_actions.spawn_sub_swarm_spec(output_dir, mission_name, mission_thesis, roles=None)` creates `*.subswarm.json` with `mission_name`, `mission_slug`, `created_at`, `thesis`, `roles`, `status`, and `source`.
- New dry-run entrypoint: `boot_sub_swarm(spec_path, *, dry_run=True, output_dir=None, resource_target="local", parent_channel="filesystem") -> WorldActionResult`.
- Dry-run payload: normalized mission identity, roles, resource target, parent-child channel, planned lifecycle states, planned command preview as data, safety checks, and `spawn_allowed: false`.
- Receipt path: write a `*.boot-dry-run.json` receipt next to the spec or under the supplied output directory.
- Error contract: invalid JSON, missing required fields, unsupported status, unsafe resource target, or `dry_run=False` must return a failed `WorldActionResult` without side effects beyond an optional rejected receipt.

## Test Targets

- Extend `tests/test_world_actions.py` with `TestBootSubSwarmDryRun`.
- Cover valid spec -> dry-run receipt emitted with `spawn_allowed: false`.
- Cover missing required fields -> failure and no boot plan.
- Cover `dry_run=False` -> rejected until a later live-spawn design exists.
- Monkeypatch `subprocess.run`, `subprocess.Popen`, and any process-spawn adapter to raise; the dry-run test must still pass without calling them.
- Verify no filesystem writes outside the temp output directory except the explicit receipt.
- Run targeted tests first: `pytest -q tests/test_world_actions.py`.
- Run doc gate for the docs-only change: `python3 scripts/docops/check_docops_integrity.py --changed-from origin/main`.

## Non-Goals

- No live sub-swarm process.
- No VPS provisioning on AGNI, RUSHABDEV, local Mac, Docker, tmux, launchd, or SSH.
- No Redis, NATS, A2A, or durable broker implementation.
- No changes to `DarwinEngine`, `AgentRunner`, `SwarmManager`, provider routing, or Telos gate internals.
- No first carbon-market sub-swarm launch.
- No CLI surface beyond whatever later implementation needs to exercise the dry-run interface.

## Exit Criteria

- The dry-run API can consume the existing spec format and emit a stable receipt.
- Tests prove the implementation refuses live spawning.
- The plan remains downstream of DGM foundation in docs, tests, and PR body wording.
