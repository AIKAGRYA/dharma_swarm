# 01 — Current State Capture (2026-07-07)

> **Dated evidence:** This captures the pre-merge collapse worktree. Use
> [`../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md)
> for current-main body synthesis and its dated runtime witness; use onboarding
> and `docs/state/LIVE_OPS_DASHBOARD.md` for current operating state.

All commands below were read-only and run from
`/Users/dhyana/ds_holon_collapse_20260707` on the clean branch.

## Git state

```text
### git status --short --branch
## feat/holon-system-collapse-base...origin/feat/holon-system-collapse-base

### git rev-parse HEAD
8a3a2e657cbd22c387827fa3ed18e00ff26fea2b

### git branch --show-current
feat/holon-system-collapse-base

### git log -1 --oneline
8a3a2e657 sarathi: port reversibility-gated wake brick
```

## Agent list snapshot

```text
### .venv/bin/python -m dharma_swarm.dgc_cli agent list
[holon] provider 'sakana' -> 'sakana' is not a valid ProviderType; defaulting to claude_code
Available autonomous agents:
  researcher, coder, scout, reviewer, witness
Registered sovereign holons:
  artha_cream, codex_composer, codex_worker_spine, cybernetics_codex,
  devin-roaming-2987d222, fable_composer, fugu_ultra, hermes-m5,
  livelihood_loom_ceo, magpie, merge_master_mike, operator_guide_cursor,
  opus_composer, palantir_pilot, repo_cartographer, sakshi_auditor, sarathi
Sarathi line: model=gemini-2.5-flash, compass_signals=1
```

## Agent status snapshot

```text
### .venv/bin/python -m dharma_swarm.dgc_cli agent status --json
The command returned 17 registered holons. Sarathi was registered with
model `gemini-2.5-flash`, `kill_requested=false`, and `compass_signal_count=1`.
The same Sakana provider warning appeared for `fugu_ultra`.
```

This proves registration/identity visibility only. It does **not** prove Sarathi
has an unattended wake loop.

## Runtime home counts

```text
~/.dharma/agents 63
~/.dharma/ginko/agents 52
docs/agents 5
~/.dharma/a2a/cards 49
~/.dharma/external_agents 26
~/.dharma/a2a_bus/inboxes 166
```

Boundary note: these mutable homes are context and drift evidence only. Fixing
identity-home drift belongs to the agent-admission semantic-commons track, not
this collapse lane.
