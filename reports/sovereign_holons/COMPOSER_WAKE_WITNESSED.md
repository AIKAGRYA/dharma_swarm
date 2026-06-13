# Composer Wake Witnessed

date: 2026-06-11
verifier: codex_composer
scope: Build A readiness gate B-A3/B-A14, one-shot unattended wake proofs only

## Verdict

PASS for one-shot unattended wake proof on both composer seats.

This does not install or ratify a permanent standing wake loop. It proves the
launch substrate can wake both seats headlessly and write receipts.

## Fable proof

- Receipt: `/Users/dhyana/.dharma/a2a_bus/collab/convergence/RUN_RECEIPT_wake_proof.md`
- Launch source: `launchd`, label `com.dharma.fable-wake-proof`
- Fired: `2026-06-11T03:28:03Z`
- CLI result: `claude -p` exit code `0`
- Response: `FABLE_WAKE_PROOF_OK`
- State file: `/Users/dhyana/.dharma/a2a_bus/state/fable_composer.json`
- State heartbeat: `2026-06-11T03:28:13Z`
- Route recorded by receipt: `claude_code headless via Keychain OAuth = Max plan`
- Cost ledger check: no `anthropic_api` entries found for `2026-06-11` in
  `/Users/dhyana/.dharma/costs/daily_ledger.jsonl`

## Codex proof

- Receipt: `/Users/dhyana/.dharma/a2a_bus/collab/convergence/RUN_RECEIPT_codex_wake_proof.md`
- Launch source: `launchd`, label `com.dharma.codex-wake-proof`
- First attempt: `2026-06-11T03:36:00Z`, exit code `127`, failed because
  launchd's default PATH could not find `node`
- Repair: added launchd-safe PATH to the one-shot script
- Second attempt: `2026-06-11T03:40:03Z`
- CLI result: `codex exec` exit code `0`
- Response: `CODEX_WAKE_PROOF_OK`
- Mechanics verified: `--skip-git-repo-check`, stdin closed with `/dev/null`,
  cwd intentionally set to non-repo `~/.dharma`
- State file: `/Users/dhyana/.dharma/a2a_bus/state/codex_composer.json`
- State heartbeat: `2026-06-11T03:40:22Z`
- State proof status: `passed`

## Files Changed For Codex Proof

- `/Users/dhyana/.dharma/external_agents/codex_composer/wake/codex_composer_wake.py`
  now adds `--skip-git-repo-check` to `codex exec` and closes stdin with
  `subprocess.DEVNULL`.
- `/Users/dhyana/.dharma/agents/codex_composer/wake/one_shot_wake_proof.sh`
  is the one-shot proof script.
- `/Users/dhyana/Library/LaunchAgents/com.dharma.codex-wake-proof.plist`
  scheduled the one-shot proof.

## Remaining Boundary

This closes the one-shot wake evidence gap for Build A readiness. It does not
close the permanent recurring-wake deliverable. Per the merged workflow, the
standing loop remains a P6 proposal and requires operator ratification.
