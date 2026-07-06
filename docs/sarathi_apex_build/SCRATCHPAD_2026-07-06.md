# Scratchpad — Sarathi reconciliation verification, 2026-07-06

This scratchpad is a side ledger for what was checked in this session. It is not
an authority surface; promote only stable conclusions to `00_START_HERE.md` or
`11_PERSISTENT_AGENT_RELATION.md`.

## Commands run

- `make onboard` in `/Users/dhyana/dharma_swarm`.
  - Branch: `agent/magpie-seed`.
  - HEAD: `eeb217b775`.
  - Drift: `39` ahead / `381` behind `origin/main`.
- `bash scripts/runtime/codex_toolbelt_status.sh`.
  - GitNexus/contextplus configured; Sourcegraph missing; local key helper present.
- `python3 -m pytest tests/test_reversibility_gate.py -q`.
  - Failed during collection because `/usr/bin/python3` is Python 3.9.6 and repo imports use 3.10+ union annotations.
- `.venv/bin/python -m pytest tests/test_reversibility_gate.py -q`.
  - Passed: `9 passed in 0.50s`.
- `.venv/bin/python -m pytest tests/test_holon_bridge.py holon/tests/test_standalone_runtime.py -q`.
  - Passed: `43 passed in 0.60s`.
- File counts:
  - `wc -l dharma_swarm/operator_core/reversibility_gate.py tests/test_reversibility_gate.py` → 225 + 90.
  - `git ls-files 'dharma_swarm/holon*' ... | xargs wc -l` for runtime files → 18 files / 5,668 lines.
  - `find ~/.dharma/a2a_bus/leases -maxdepth 2 -type f | wc -l` → 0.
  - `find ~/.dharma/agents/sarathi -type f | wc -l` → 37.
  - executable-code count under Sarathi home (`*.py`, `*.sh`, `*.ts`, `*.js`) → 0.
- Sprawl count:
  - `/Users/dhyana` recursive scan found `holon_bridge.py=138`, `holon_runtime.py=138`, 69 git roots.
- `load_holon` diff copies staged in `/tmp/sarathi_load_holon_diff`.
  - dev-397: SHA-1 `20948569d3f36d01c3982367bcdb764dc0875487`.
  - fork-127: SHA-1 `86a92697c26de6381ef61f2a5b7fcdfbcbd38e81`.
  - deploy/origin-main-204: SHA-1 `192ce506734c9e458e1ea8cce1a0867927e4b150`.

## Uncertainties / corrections

- The exact historical `136 copies / 68 trees` count did not reproduce. Current
  scan sees 138 per filename / 69 git roots. Likely cause: one more worktree/root
  appeared since the prior count, or the prior scan excluded one root.
- The exact `42 committed holon files / 5,668 lines` wording did not reproduce
  as a file count. The line count 5,668 reproduces for the 18 `dharma_swarm/holon*`
  runtime files. A wider holon selector finds many more files because it includes
  standalone package, tests, scripts, reports, and receipt fixtures.
- I have not run the full repository test suite. Only targeted gate + holon bridge/runtime tests were run.
- I have not fetched or rebased a fresh `origin/main`; verification used the
  locally-known `origin/main` ref `0a26db0ee6f1`.

## Meta lesson

The missing harness is not more orientation; it is a write-surface reservation
and duplicate-primitive gate. Agents need to be forced to answer: "what is the
one code home, one runtime home, one docs front door, and which duplicate names
are forbidden?" before they write.

## Step-4 partial close receipts (same session)

Additional implementation after the map/gate verification:

- Registered `sarathi` in `scripts/runtime/codex_composer_wake_loop.py` as a `WakeProfile` (`schema_prefix=dharma.sarathi`, `session=sarathi-wake`) reusing the existing wake shell; no forked wake loop.
- Added a pre-run reversibility seam to `dharma_swarm/holon_runtime.py`: callers may pass `planned_action`; the code-deterministic gate runs before the injected runner and returns `halted:reversibility_gate` before work if the action is not unattended-safe.
- Added tests for Sarathi profile selection/read-only `once`, and for holon wake-cycle gate allow/block/loop propagation.
- Ran real Sarathi read-only wake once:
  - receipt: `~/.dharma/external_agents/sarathi/nest/receipts/sarathi-wake-20260706T092645Z-f6b0e3ad.json`
  - latest: `~/.dharma/external_agents/sarathi/nest/latest_receipt.json`
  - status stayed `wake_loop_active=false`
  - receipt status: `completed_with_missing_context` because `agent_passport`, `bridge_heartbeat`, and `a2a_state` are not present for Sarathi yet.
- Ran one direct governed Sarathi holon cycle with `planned_action="read the status file"`:
  - persisted record: `~/.dharma/agents/sarathi/holon_events.jsonl` cycle `0`
  - embedded `reversibility_gate.action_class=reversible_safe` and `may_execute_unattended=true`
  - status `ran`; no external message, source mutation, or lease self-approval.
- Did NOT start the repeated tmux loop and did NOT flip `wake_loop_active`; activation remains lease-gated.

Verification after the code seam:

- `.venv/bin/python -m pytest tests/test_reversibility_gate.py tests/test_holon_runtime.py tests/test_holon_runtime_integration.py tests/test_codex_composer_wake_loop.py tests/test_holon_bridge.py -q` -> `61 passed in 0.79s`.
- `.venv/bin/python -m py_compile dharma_swarm/operator_core/reversibility_gate.py dharma_swarm/holon_runtime.py scripts/runtime/codex_composer_wake_loop.py scripts/governance/sprawl_guard.py` -> pass.
- Broad `.venv/bin/python -m pytest -q` was attempted and stopped after 4:01 with `1 failed, 574 passed`; failure was `tests/test_active_track_governance.py::test_managed_blocks_in_sync` due generated active-track blocks out of sync in `CLAUDE.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, and `docs/governance/BUILD_SESSION_ENTRYPOINT.md`. This appears unrelated to the Sarathi/holon files and was not auto-rewritten in this scoped commit.
