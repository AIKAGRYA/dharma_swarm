# codex_composer Orientation Substrate Receipt

Status: integration receipt, not a promotion receipt.
Owner track: `agent-admission-semantic-commons-2026-06`.
Serves: `substrate-nativeness`.

## What Landed

- Semantic Commons now names `CodexComposer`, `Sanctum`, `Holocron`,
  `HolocronNest`, `Aerie`, `LandingDock`, and `FactoryDroid`.
- `LivingDock` remains the canonical per-agent home object.
- `Sanctum`, `Holocron`, and `HolocronNest` are LivingDock subspaces, not
  authority roots.
- `Aerie` is seed-stage operator-facing fleet projection language.
- `LandingDock` is seed-stage onboarding/session-orientation projection
  language.
- `FactoryDroid` is the preferred spelling for the seed tooling identity;
  `DroidFactory` resolves only as a compatibility alias.
- `Aaverie` is a forbidden typo near miss.
- `SessionOrientation` now has L5 Seat Load for named-agent loading after
  route and authority are known.
- `codex_composer` has a manual, read-only wake/orientation shell exposed
  through Make.

## Filesystem Projection

Canonical LivingDock projection:

```text
~/.dharma/agents/<agent_uid>/
```

External evidence/sandbox staging:

```text
~/.dharma/external_agents/<agent_uid>/
```

Reserved codex_composer slots remain under the external sandbox until a later
promotion admits real authority:

```text
~/.dharma/external_agents/codex_composer/nest/holocron/
~/.dharma/external_agents/codex_composer/nest/aerie/
~/.dharma/external_agents/codex_composer/nest/landing_dock/
~/.dharma/external_agents/codex_composer/nest/droid_factory/
```

## North Star Service

`docs/vision_maps/NORTH_STAR.md` names substrate nativeness as the top-tier
guide for the rest of the organism. This integration serves that by making
agent-seat names resolvable through the governed alias layer before runtime or
search work starts.

Trust gate support:

- The operator can run `make onboard-agent AGENT_NAME=codex_composer` and see a
  bounded orientation receipt instead of a hidden daemon claim.
- The wake shell records what it observed, what it accepted as read-only, and
  what required an execution lease.
- The shell does not treat publish acceptance as live collaboration.

Canon metabolism support:

- The hierarchy/APEX draft language has been metabolized into Semantic Commons
  objects, aliases, forbidden aliases, and L5 SessionOrientation routing.
- Runtime mutation remains owned by existing code and receipt owners.
- No `AgentHome`, duplicate map, duplicate receipt store, queue, cockpit
  authority, or permanent wake loop was introduced.

Truthful cybernetic loop support:

- `codex-composer-once` is a bounded read-only cycle.
- `codex-composer-start` refuses repeated activation without an explicit
  activation lease.
- Receipts/status/heartbeat files are the only intended writes from the shell.

## Non-Claims

This receipt does not claim D4 promotion, D5/APEX readiness, semantic
collaboration, live Droid orchestration, PR authority, or permanent wake-loop
readiness.

PR #683's filesystem-native substrate remains pending external substrate work.
No `fs_substrate` package was copied here.

## Follow-On Plan

1. Consume PR #683 after merge as the filesystem-native substrate instead of
   duplicating its package.
2. Define a Scheduler/CronEnvelope registry before any standing wake-loop
   activation.
3. Build a FactoryDroid adapter only after the seed identity is explicitly
   promoted from Semantic Commons seed status.
4. Add a D4 promotion verifier for `codex_composer` covering identity,
   LivingDock projection, fresh heartbeats, semantic inbox drain, domain
   receipt, semantic receipt, and decorrelated verification.
