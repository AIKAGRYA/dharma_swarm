# Operator Guide Cursor Onboarding Map

**Status:** operational route for the persistent Cursor operator relay  
**Identity:** `operator_guide_cursor` (`semobj.operator_guide_cursor`)  
**Aligned apex (reserved):** `semobj.sarathi` — not this seat

## Topology

```text
You
  Sarathi (reserved D5 apex holon — organism layer, future)
  Operator Guide Cursor (this seat — Cursor harness, callable now)
        └── hub / holons / workers
```

This agent is **fully instantiated** for trans-chat use:

| Surface | Purpose |
|---|---|
| `@OPERATOR_GUIDE` | summon phrase |
| `.cursor/rules/operator-guide-cursor.mdc` | always-on project rule |
| `~/.cursor/skills/operator-guide-cursor/SKILL.md` | personal skill |
| `examples/agents/operator_guide_cursor.registration.json` | repo registration manifest |
| `~/.dharma/agents/operator_guide_cursor/` | LivingDock runtime home |
| `dharma.agent.operator_guide_cursor.inbox` | A2A inbox |

## First Commands

```bash
cd /Users/dhyana/dharma_swarm
make onboard
python3 scripts/governance/register_operator_guide_cursor.py --write
```

Optional admission:

```bash
python3 scripts/governance/name_drift_preflight.py \
  --json-output /tmp/operator_guide_cursor_name_drift.json
make agent-admit ARGS="--agent-uid operator_guide_cursor --canonical-id semobj.operator_guide_cursor --orientation-route route.seat_operator_guide_cursor --name-drift-receipt /tmp/operator_guide_cursor_name_drift.json"
```

## Summon

Primary: `@OPERATOR_GUIDE`  
Aliases: `@operator_guide_cursor`, `@CURSOR_GUIDE`

Use in any future Cursor chat in this repo to reload the same identity and voice.

## Teaching Protocol

1. analogy
2. simple model (you → desk → agents → swarm)
3. what this means for you
4. one next step

## Trans-Chat Continuity

After meaningful sessions, update:

- `~/.dharma/agents/operator_guide_cursor/HOLON_CONTEXT.md`
- optional dialogue receipts under `~/.dharma/agents/operator_guide_cursor/dialogue/`

Repo template: `docs/agents/operator_guide_cursor/HOLON_CONTEXT.md`

## Do Not Confuse

- **Operator Guide Cursor** = callable Cursor seat now
- **Sarathi** = reserved higher apex holon, not this UID
