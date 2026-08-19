# Dharma Helm Live Slice 1 — Typed Truth and Read-Only Membrane

Status: recovery implementation contract
Authored: 2026-08-09
Recovery baseline: `43e93f6de62f787789ca4be28cfcd848e7aeec29`
Interrupted baseline: `bb2c5174e30413d78a5e2ed7193e9e7eb84bf1a4`
Work packet: `WP-HELMSLICE1-RFC1-RFC2`
Issue lock: `HELM-SLICE1-POST-AUDIT-LOCK` on Wayfinder issue #1277

## Outcome

Slice 1 provides one honest primary-agent chat turn behind a physical no-tools membrane, a fixed seven-seat Helm OnCall census, a Python-owned evidence evaluator, and a terminal truth band that remains visible in every layout. It does not claim that unavailable models are live. A run is `ON_CALL` only at 7/7; otherwise it is visibly `LIVE_DEGRADED`, `CLOCK_SKEW`, or `UNKNOWN`.

The small language-design contribution is executable: positive epistemic modality is a constructor restriction. Only `evaluate_route_verification` may construct `RouteVerdict.ON_CALL`; provider success, key presence, model registration, caller-supplied verdicts, and terminal transport state are not admissible proof.

## Non-negotiable laws

1. Python is the sole authority for RouteVerification and the seven-seat projection.
2. TypeScript decodes and renders the Python projection; it never promotes, refreshes, clamps, or preserves positive truth on its own.
3. Before the first authoritative projection, and after reconnect or runtime-epoch change, the UI is `UNKNOWN ?/7`.
4. `ON_CALL` means exactly 7/7 fresh, non-synthetic, identity-matched, verifier-accepted receipts in the current runtime epoch.
5. A successful provider completion is necessary but never sufficient for `ON_CALL`.
6. A future timestamp is `CLOCK_SKEW`, never fresh. Expiry is exclusive: `observed_at <= now < expires_at`.
7. Maximum evidence lifetime is 24 hours. A caller cannot configure a larger TTL.
8. No command, tool, task, swarm, evolution, A2A, seed, write, or subprocess effect may originate from a Slice-1 primary chat turn.
9. Raw user input is preserved byte-for-byte through classification and provider dispatch, except that empty input and NUL are rejected.
10. Missing or malformed command outcomes and unsupported/stub commands fail closed and never render as completed.

## Fixed OnCall census

Order is part of the schema. It is independent of `EVOLUTION_ROSTER` and the general model pool.

| Index | Seat ID | Logical lineage | Admissible served route identities |
|---:|---|---|---|
| 0 | `fable-5` | `fable-5` | `claude_code:claude-fable-5`, `fable:fable-5` |
| 1 | `gpt-5.6` | `openai-gpt-5.6` | `codex:gpt-5.6`, `openai:gpt-5.6` |
| 2 | `grok-4.5-4.6-lineage` | `xai-grok-4.5-4.6` | `openrouter:x-ai/grok-4.5`, `openrouter:x-ai/grok-4.6`, `xai:grok-4.5`, `xai:grok-4.6` |
| 3 | `fugu-ultra` | `sakana-fugu-ultra` | `sakana:fugu-ultra` |
| 4 | `kimi-k3` | `moonshot-kimi-k3` | `kimi_code:k3`, `moonshot:kimi-k3`, `openrouter:moonshotai/kimi-k3` |
| 5 | `opus-5.0` | `anthropic-opus-5.0` | `claude_code:claude-opus-5.0`, `anthropic:claude-opus-5-0` |
| 6 | `opus-4.8` | `anthropic-opus-4.8` | `claude_code:claude-opus-4.8`, `anthropic:claude-opus-4-8` |

These tuples describe accepted identity evidence, not route availability. A tuple absent from current runtime registration remains `UNKNOWN`; this slice must not add a fake adapter or alias to make the count greener.

## Python truth types

The implementation exposes immutable typed values from `dharma_swarm.model_status`:

- `RouteVerdict`: `ON_CALL`, `UNKNOWN`, `REJECTED`, `CLOCK_SKEW`.
- `HelmSeat`: seat ID, display label, logical lineage, ordered admissible provider/model tuples.
- `RouteEvidence`: claimed seat/lineage, requested provider/model, served provider/model, success, synthetic flag, observation and expiry times, verifier identity/version/decision, receipt reference/hash, and runtime epoch.
- `RouteVerification`: schema, seat, verdict, reason, evaluated time, runtime epoch, and sanitized evidence identity.
- `HelmOnCallProjection`: schema, aggregate state, count, total, ordered seven verifications, evaluated time, and runtime epoch.

Wire schemas are exact versioned strings:

- `dharma.helm.route_verification.v1`
- `dharma.helm.on_call_projection.v1`

The accepted verifier identity is exactly `dharma.route_verifier@1.0.0`. Receipt hashes are lowercase 64-character SHA-256 values. Receipt references are non-empty durable identifiers. Timestamps are timezone-aware RFC 3339 values.

## Positive constructor proof obligations

`evaluate_route_verification` returns `ON_CALL` only when every obligation below holds:

- the evidence seat and logical lineage equal the expected fixed seat;
- provider completion succeeded and is explicitly non-synthetic;
- requested and served identity are present, and served provider/model is in that seat's allowlist;
- observation and expiry are timezone-aware;
- observation is not in the future;
- expiry is later than observation and no more than 24 hours later;
- evaluation time is strictly before expiry;
- verifier ID is `dharma.route_verifier`, version is `1.0.0`, and the verifier accepted;
- receipt reference is durable/non-empty and the SHA-256 is structurally valid;
- the receipt is not duplicated in the projection batch and is not in the caller-supplied replay set;
- evidence runtime epoch exactly equals the bridge's current per-boot runtime epoch.

`MAX_ROUTE_VERIFICATION_TTL = timedelta(hours=24)` is a fixed constant and a mutation-tested boundary. Deserialization never accepts a supplied positive verdict as authority. Re-rendering an already evaluated projection is idempotent; it is not a new evaluation and does not consume the receipt again.

## Aggregate state machine

```text
connect / reconnect / epoch change -> UNKNOWN ?/7
authoritative projection, 7 ON_CALL -> ON_CALL 7/7
authoritative projection, 0..6 ON_CALL -> LIVE_DEGRADED N/7
any future-dated seat evidence -> CLOCK_SKEW N/7
malformed schema/order/seat set -> UNKNOWN ?/7
```

The projection contains exactly seven seats in the fixed order. TypeScript rejects wrong schema, duplicate/missing/reordered seats, wrong total, count disagreement, unknown enum values, or runtime-epoch disagreement. Legacy `live_routable`, provider-route receipts, `routePolicy.ready`, and freshness helpers cannot feed this state.

## Bridge transport

The bridge emits a dedicated `helm.on_call_projection` event whose data is the serialized Python projection. It emits an authoritative baseline before claiming any seat and emits a new projection only after Python evaluation. A new `_runtime_owner_id` is the runtime epoch, so process restart invalidates all prior positive evidence without a new durable truth store.

Provider completion receipts may remain useful diagnostics, but are not a terminal positive constructor. A provider response can become evidence only after durable receipt creation and evaluation against the obligations above.

## Read-only no-tools primary turn

The server, not the caller, classifies the raw prompt. Caller-supplied bootstrap intent is ignored. Only either of these whole-input forms enters command handling:

- an explicit registered slash command; or
- an exact registered bare command accepted by the existing registry.

Conversational matching, substring inference, or extracting one command from a multi-clause prompt is forbidden. The locked adversarial prompt is classified as chat, remains byte-identical, and executes zero commands/tools/tasks/evolutions/spawns/A2A/seeds/writes.

The exact locked fixture is 239 UTF-8 bytes with SHA-256 `27c971750f276c07e759c8b005530e284908d2768d9cc10da51deea1294e5197`:

> show me the visual map of my ecosystem and what is alive right now, list all agents live now, all running projects. get 3 agents on a long run build and have them finish BUNKI. seed SIS. run 10 RSI evolution runs. get the A2A mesh running.

Admissible primary-chat transports must physically suppress tools:

- Claude Code: empty tools, `plan` permission mode, strict empty MCP config, empty settings, one turn.
- OpenRouter-compatible chat: omit tool definitions and set the transport's no-tool choice where supported.
- Codex CLI: excluded from Slice-1 live proof while its adapter exposes the `shell` tool.

Provider-supplied tool/task/command lifecycle events are rejected, not buffered. Provider text is narration with `authority=NONE`, `narration_verified=false`, and `state_promotion_allowed=false`. A successful chat session proves only that a no-tools inference response arrived.

## Command outcomes

Every `command.result` carries one explicit outcome:

- `completed`: handler returned `ok=true` and work is complete;
- `accepted`: a supported operation was accepted but has not completed;
- `unsupported`: no real handler exists, including stubs/placeholders;
- `failed`: handler failed or the outcome is missing/malformed.

Only `completed` may render a completion check. `unsupported` and `failed` end the command session unsuccessfully. No compatibility default may translate `ok=false` or a missing outcome to complete.

## Terminal truth surface

The terminal owns no alternate truth evaluator. It strictly decodes `helm.on_call_projection`, stores it only for the current bridge connection/runtime epoch, and renders a persistent OnCall truth band in compact, wide, zen, and scroll modes. The band shows aggregate state, exact `N/7` or `?/7`, and ordered seat verdicts/reasons. It resets synchronously on disconnect/reconnect before processing later events.

`terminal/src/app.tsx` is at its ratchet ceiling at the base commit. Integration must extract code and leave it no longer than 3,934 lines. New protocol modules use concrete typed interfaces rather than adding generic `Record<string, unknown>` debt.

## Required verification

- Python evaluator tests: all positive obligations and independent negative controls for synthetic, identity mismatch, unverified, missing receipt/hash, replay, stale, future, naive time, TTL over 24 hours, expiry boundary, runtime-epoch mismatch, duplicate seat/receipt, wrong order, and forged verdict.
- Bridge tests: exact compound fixture, forged bootstrap intent, raw-byte preservation, NUL/empty rejection, tool/task event rejection, no-tools provider args, unsupported/stub outcomes, failure session end, and runtime-epoch reset.
- Terminal tests: strict decode, wrong version/order/count, reconnect reset, legacy promoter isolation, missing/false command outcome, all layouts, width/ratchet, and golden output.
- Governed negative control: changing the 24-hour constant to 48 hours must make `test_route_verification_rejects_ttl_over_24_hours` fail.
- Bounded live journey: at most 14 provider calls, one safe primary reply, switch to a second genuinely verified OnCall seat and receive a reply, and inspect one real read-only organism facet. Every mutation/evolution/spawn/task/A2A/seed/write counter remains zero.

## Completion and honest block

Code completion is not live completion. Final status is:

- `LIVE_VERIFIED` only with fresh 7/7 RouteVerification plus the complete no-tools journey;
- `LIVE_DEGRADED` when an authoritative projection has fewer than seven verified seats;
- `LIVE_PROOF_BLOCKED` when external provider availability or credentials prevent the required proof.

If live proof is blocked, the receipt names every missing seat and exact external blocker. It must not weaken the evaluator, synthesize a route, purchase quota, change credentials, deploy, merge, or call unavailable mutations to improve the score.
