# RUNTIME TRUTH COMMAND CUTOVER

Status: active enforcement map, not a new spine.

This document records the command cutover state for live operator-facing
surfaces. It does not create a new command lifecycle substrate.

## Canonical Substrate

The existing Runtime Truth Spine is the authority:

- `dharma_swarm/spine/identity.py`: `ExecutionIdentity`
- `dharma_swarm/spine/receipt.py`: dispatch `EvidenceReceipt`
- `dharma_swarm/spine/invoke.py`: blessed `invoke_agent` path
- `dharma_swarm/spine/tollbooth.py`: fail-closed gate
- `dharma_swarm/spine/warrant.py`: pre-side-effect `RuntimeWarrant`
- `dharma_swarm/runtime_state.py`: `RuntimeStateStore`, `RuntimeReceipt`,
  and idempotency records

Do not add `WorkCommand`, `WorkRun`, `WorkReceipt`, `command_runs`,
`work_runs`, or a second command ledger.

## Proof Types

| Proof | Owner | Meaning |
|---|---|---|
| `ExecutionIdentity` | `dharma_swarm/spine/identity.py` | Correlation join key for one durable unit of work |
| `RuntimeWarrant` | `dharma_swarm/spine/warrant.py` | Permission receipt required before selected side effects |
| `EvidenceReceipt` | `dharma_swarm/spine/receipt.py` | In-flight dispatch proof |
| `RuntimeReceipt` | `dharma_swarm/runtime_state.py` | Persisted runtime proof |
| `IdempotencyRecord` | `dharma_swarm/runtime_state.py` | Exactly-once side-effect claim |
| `receipt_json` | runtime projection/cache | Query convenience, not source of truth |
| file reports | local projection | Useful evidence, not authority unless named as owner |
| dashboard cards | projection | Operator view, never completion authority |
| onboard rows | projection | First-screen synthesis, not a truth owner |

`RuntimeWarrant` is distinct from the Fourfold Action Warrant. Fourfold is a
read-only governance review for proposed significant actions. RuntimeWarrant is
a persisted, pre-side-effect permission receipt for selected runtime commands.
They may reference the same operator intent later, but they must not share a
state table or substitute for each other.

## Status Labels

- JOINED: default path writes identity, idempotency, and runtime proof through
  the existing spine or RuntimeStateStore.
- ADAPTER_READY: projection or adapter can read receipts, but default path is
  not fully joined.
- OPT_IN_ONLY: safe path exists only behind a flag or explicit command.
- LEGACY: works but bypasses spine identity or runtime receipts.
- QUARANTINE: should not be used until owner proof exists.
- AMBER: plausible, useful, but missing a required proof edge.
- RED: contradicted, forged, unsafe, or overclaimed.

## Command-Surface Matrix

| Surface | Default or opt-in path | ExecutionIdentity | RuntimeWarrant | EvidenceReceipt | RuntimeReceipt | Idempotency before side effect | UI separates sent/delivered/domain/semantic/completed | State | Next receipt required |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `ds-goal` (`scripts/runtime/autonomy_spine.py`) | default CLI path | yes | yes, before kernel wake dispatch | yes, associated inside existing command `RuntimeReceipt` payload | yes | yes, before kernel wake dispatch | cards project mission/task/runtime refs | JOINED | broaden warrant/evidence association to next side-effect surface |
| A2A direct send (`scripts/runtime/a2a_send.py`) | default direct NATS command | yes | yes, before publish | yes, associated inside existing command `RuntimeReceipt` payload | yes | yes, before publish | receipt and card split publish, handler ack, reply, domain receipt | JOINED | keep no-double-write invariant; broaden to bridge/runtime owner only if selected |
| A2A inbox bridge | default bridge receipt path | partial | no | no | file receipt projection | not proven at bridge boundary | card now treats delivery ack as review, not done | ADAPTER_READY | bridge-owned runtime receipt or explicit owner decision |
| A2A reply capture | default capture verifier | partial | no | no | file receipt projection | not applicable to capture-only read | untyped payload is non-semantic; mismatch is RED | ADAPTER_READY | typed domain receipt or semantic reply schema with source identity |
| A2A domain-reply artifact | explicit artifact helper | partial | no | no | author receipt projection | not proven | card distinguishes artifact publish from completion | ADAPTER_READY | target-owned domain receipt consumed by reply capture |
| AgentOps work packets | default governance path | partial | no | no | file report projection | packet-dependent | green gates without runtime refs project partial | AMBER | AgentOps report with trace, receipt, or identity refs |
| registered holon wake | explicit registered wake path | partial | unknown | no | kernel/runtime receipts where wired | partially proven | status views must not grant broad tools | AMBER | focused test: unknown holon fail-closed and registered wake tool scope |
| dashboard/control-surface cards | projection only | no | no | no | no, reads receipts | no side effects | now avoids handler-ack-as-done for A2A | ADAPTER_READY | card status tests for every evidence tier |
| overnight/autopilot command surfaces | explicit scripts | mixed | unknown | unknown | mixed | unknown | not all projected | AMBER | per-script cutover packet or quarantine list |
| Forge/Hydra command surfaces | unclear in this checkout | unknown | unknown | unknown | unknown | unknown | not projected as runnable | RED | fresh run receipt, command path, verifier, and artifact hashes |
| cron/provider rotator surfaces | external/local cron | unknown | unknown | no | external logs only | unknown | not projected as complete | LEGACY | runtime wrapper or explicit external-gated classification |

## Default-Path Cutover Metric

This metric counts command surfaces by default-path enforcement, not by adapter
readiness:

| Class | Count | Surfaces |
|---|---:|---|
| default path has RuntimeStateStore idempotency before side effect | 2 | `ds-goal`, A2A direct send |
| default path has RuntimeWarrant before side effect | 2 | `ds-goal`, A2A direct send |
| default path has persisted RuntimeReceipt | 2 | `ds-goal`, A2A direct send |
| default path has direct `EvidenceReceipt` association | 2 | `ds-goal`, A2A direct send |
| projection/card only | 4 | A2A bridge, reply capture, domain reply, dashboard/control cards |
| AMBER or RED bypass needing next slice | 5 | AgentOps refs, holon wake, overnight/autopilot, Forge/Hydra, cron/rotator |

`EvidenceReceipt` association here means the command builds a
`dharma_swarm.spine.receipt.EvidenceReceipt` and embeds its JSON plus compact
ref inside the existing command `RuntimeReceipt` payload. It intentionally does
not write a second `dispatch_evidence` `RuntimeReceipt` row.

## Runtime Warrant Criteria

The current RuntimeWarrant gate is intentionally narrow and fail-closed:

1. the `(surface, action)` pair must be explicitly registered;
2. requested claim names are normalized before policy checks;
3. a non-empty requested claim boundary is required;
4. RuntimeStateStore idempotency must be claimed before the side effect;
5. the idempotency row must actually exist and match `run_id`, `task_id`,
   `trace_id`, `correlation_id`, and `status=started`;
6. requested claims must be in the surface/action allowlist and must not be a
   prohibited pre-action claim such as `completed`, `live_contact`,
   `semantic_reply`, `revenue_live`, or `live_trading`;
7. denied warrants persist a blocked `runtime_warrant` receipt when an
   execution identity exists.

## Evidence Semantics

A2A evidence is layered:

1. sent: command attempted publish;
2. publish accepted: broker accepted the packet;
3. delivered: handler or bridge saw it;
4. domain receipt: typed domain receipt exists;
5. semantic reply: typed payload claims peer/model processing;
6. completed: task or runtime owner records work completion.

No lower layer implies a higher layer.

## Remaining Bypass Classification

| Bypass | Classification | Why | Next move |
|---|---|---|---|
| A2A bridge receipts are file projections | ADAPTER_READY | useful receipt files, not persisted runtime owner | choose bridge owner or keep projection-only |
| AgentOps green reports without runtime refs | AMBER | gates prove local checks, not runtime binding | require trace/receipt refs for bound state |
| registered holon wake | AMBER | registered wake path exists, but fail-closed scope needs fresh focused proof | test unknown holon fail-closed and registered wake tool scope |
| overnight/autopilot command surfaces | AMBER | broad bucket mixes scripts with different side-effect risk | split per script and cut over or quarantine individually |
| Forge/Hydra runnable claims | RED | no fresh run receipt in this pass | run or stop claiming runnable |
| cron/provider rotator surfaces | AMBER | side-effecting external paths still rely on external logs and cron context | runtime wrapper or explicit external-gated classification |

## External Authority Guardrails

| Claim | Classification | Why | Next move |
|---|---|---|---|
| live trading authority | RED | external/legal authority absent | explicit human/legal warrant before any live path |
| revenue/external-human proof | AMBER | active runtime tracks do not cover it | 72h external proof sprint with payment/reply/artifact receipts |
