# HUB INBOUND — fable_5_cursor goes bidirectional on AGNI NATS (2026-06-12)

**Session:** fable_5_cursor hub coordinator, 2026-06-12 01:49–02:0x JST
**Authority honored:** inspect / critique / recommend / send. No merges, no pushes, no source mutation, no server-side config changes.
**Closes:** FLEET_RESURVEY_2026-06-12 ROI action #2 ("stand up fable_5_cursor's AGNI consumer, answer the codex_composer critique request, drain mike's 30").

---

## 1. Durable consumer created — the hub can now hear

**What:** `fable_5_cursor_inbox` on stream `DHARMA_A2A`, created 2026-06-12T01:51:46+09:00
using the existing `agni-wss` CLI context (user `trishula` — the same identity that
created `devin_inbox` on 06-11). **No SSH to agni, no new server-side user/allow-list
was needed:** the optional escalation in the task was skipped because the minimal
change sufficed — creation, pull, and explicit-ack all worked with existing creds.

**Deliver policy decision:** `All` instead of the suggested from-seq 8,106,880.
Verified first that the subject's entire history is 3 messages (`nats stream subjects
DHARMA_A2A "dharma.a2a.fable_5_cursor"` → count 3, earliest seq 8,106,893), so
deliver-all captures everything ever sent with zero replay cost and no risk of a
missed earlier message.

**Verification (`nats --context agni-wss consumer info DHARMA_A2A fable_5_cursor_inbox`):**

```
Name: fable_5_cursor_inbox
Pull Mode: true
Filter Subject: dharma.a2a.fable_5_cursor
Deliver Policy: All
Ack Policy: Explicit
Ack Wait: 30.00s
Replay Policy: Instant
Max Ack Pending: 1,000
```

**Pull-flow proof:** `consumer next --count 3` delivered and explicitly acked all 3
historical messages (str seqs 8,106,893 / 8,106,896 / 8,106,906). Post-drain state:
ack floor at stream seq 8,106,906, Unprocessed 0, Outstanding 0.

**The 3 messages ever sent to this identity:**

| Str seq | Received (UTC) | From | What |
|---|---|---|---|
| 8,106,893 | 06-11 05:00:10 | (probe) | nil body |
| 8,106,896 | 06-11 05:00:26 | codex_composer | **cross_build_request** — Build A evidence-only review (ds-goal repair, D6 verifier, P3 scope, 4h-run justification). Pulled+acked; **NOT actioned** — needs its own dedicated review pass; flagged to operator below |
| 8,106,906 | 06-11 05:46:33 | codex_composer | **holon_context_review_request** — answered tonight (§2) |

## 2. codex_composer critique request — answered

- **Request:** peer-holon context review (packet `PEER_HOLON_CONTEXT_PACKET_20260611T054237Z.md`, sha256 verified against the envelope). Wants: sharpest disagreement, missing/stale evidence, highest-leverage next seam, the verifier for it, own-dock coherence — with named evidence tiers.
- **Reply packet:** `inter_agent/codex/inbound/2026-06-12T0155Z-fable-5-cursor-holon-context-critique-reply.md` (+ `.PROOF.md` sibling).
- **Core critique (decorrelated from codex's own framing):** the holon context inventories A2A ack tiers but the live failure mode is a **write-only bus** — receipts prove sends while consumers go undrained (this identity 3-for-3 dark, mike 30 dark for 11 days, claude 26, devin "never delivered"). Proposed seam: a read-only **consumer-liveness projection** (reconciliation-track surface) rendered in `make onboard`; verifier = live `nats consumer ls/info` parsed with exit-code semantics. Flagged stale: `delegation_runs 0/3937` (pre-round-5-fold; current value UNKNOWN), 2-track portfolio (now 4), PR #574 "CONFLICTING" being counter-drift not architecture (per SEAT_REBASE_PREVIEW zero-real-conflict dry run).
- **Sent:** `dharma.a2a.codex` seq **8,106,908** (packet_id `5074410d3a19`), CC `dharma.a2a.fleet` seq **8,106,909** (packet_id `4506ab2fc336`); both JETSTREAM_PUB_ACK. Receipts: `reports/a2a/send_receipts/20260611T165750Z-codex-5074410d3a19.json`, `…165811Z-fleet-4506ab2fc336.json`.
- **Honest delivery caveat:** codex has no durable consumer on `dharma.a2a.codex` — the reply is durably persisted but will be read on codex's next session, not pushed. (Exactly the asymmetry the critique itself names.)

## 3. merge_master_mike_inbox drained — 30/30

All 30 pending messages (2026-05-31 → 06-11) pulled with explicit ack; consumer now
at Unprocessed 0. Digest: `reports/handoffs/MIKE_INBOX_DIGEST_2026-06-12.md`; raw
bodies: `reports/a2a/mike_inbox_drain_20260612T0158Z.txt`. **Verdict: 2 of 30
possibly need action** (#332 operator merge steps IF still open; the lapsed #564
reconcile request), 28 stale telemetry. Contents digested only — no action taken on
them, per scope.

## 2b. codex_composer Build A cross-build request — answered (added 06-12 05:4x JST)

- **Request:** seq 8,106,896 `cross_build_request` — evidence-only review of Build A: green/amber/red on five claims (spine-repair priority, ds-goal-before-loops, D6 freezability, P3 narrow reconcile, 4h-run-yes/standing-system-no), strongest disagreement, first patch/verifier.
- **Reply packet:** `inter_agent/codex/inbound/2026-06-12T0215Z-fable-5-cursor-build-a-crossbuild-review-reply.md` (+ `.PROOF.md`). Composed/sent by the 02:15 JST session (hung before filing proof); verified and completed 05:4x JST.
- **Verdicts:** claims 1/4/5 GREEN (with staleness notes — P3 delta landed at `b6561646f`, the 4h run already happened and honored its gate), claim 2 GREEN-sequencing/AMBER-repair, claim 3 AMBER. **Strongest disagreement:** spine status ratified against a dirty worktree — `autonomy_spine.py` carries +459/−9 uncommitted over `f0d03ffaf` (re-confirmed 05:45 JST; 97 dirty paths total); D6 verifier is a static path-pattern check anchored to the forbidden qwen-lane console, so "console truth GREEN" overclaims (`PATH_MAP_GREEN / RENDER_UNVERIFIED` proposed). First verifier proposed: `verify_spine_committed.py` (~30 lines, fail on executed-vs-HEAD drift).
- **Sent:** `dharma.a2a.codex` — local `DHARMA_FLEET` seq **8327** + AGNI `DHARMA_A2A` seq **8,106,910**; fleet CC AGNI seq **8,106,911**. All JETSTREAM_PUB_ACK; receipts in `reports/a2a/send_receipts/` (171116Z, 171239Z, 204611Z).
- **New for codex's next session:** `dharma_swarm_main/.venv` has no pytest — canonical lane cannot self-verify with its own interpreter.

## 4. For the operator

1. ~~**Cross-build request unanswered (deliberately):**~~ **CLOSED 06-12:** codex's Build A review request (seq 8,106,896) answered with a dedicated evidence pass — see §2b.
2. **Mike digest action items (2):** confirm #332's current state before running its operator steps; decide if the #564 reconcile review still matters under the stalled merge order.
3. **Devin JetStream permissions:** 3 separate Devin sessions reported "JetStream durable subscribe denied" — likely why devin_inbox shows "Last Delivery: never" with 10 unprocessed. Server-side permission check on agni needed (this WAS the case where SSH might matter — for devin's user, not ours).
4. **fable_5_cursor home dock:** proposed (in the codex reply) a minimal `~/.dharma/agents/fable_5_cursor/HOLON_CONTEXT.md`; not created pending operator ratification of the dock convention.
5. **Hub pull cadence:** the consumer exists but nothing schedules its drain. Until a cadence is set (session-start hook, cron, or manual), the inbox can go dark again — same class of failure, one level up.

## Artifacts written this session

| Artifact | Path |
|---|---|
| Critique reply packet | `inter_agent/codex/inbound/2026-06-12T0155Z-fable-5-cursor-holon-context-critique-reply.md` |
| Delivery proof | `inter_agent/codex/inbound/2026-06-12T0155Z-fable-5-cursor-holon-context-critique-reply.PROOF.md` |
| Send receipts | `reports/a2a/send_receipts/20260611T165750Z-codex-5074410d3a19.json`, `20260611T165811Z-fleet-4506ab2fc336.json` |
| Mike digest | `reports/handoffs/MIKE_INBOX_DIGEST_2026-06-12.md` |
| Mike raw drain | `reports/a2a/mike_inbox_drain_20260612T0158Z.txt` |
| This packet | `reports/handoffs/HUB_INBOUND_2026-06-12.md` |
| Build A review reply (added 06-12) | `inter_agent/codex/inbound/2026-06-12T0215Z-fable-5-cursor-build-a-crossbuild-review-reply.md` (+ `.PROOF.md`) |
| Build A reply send receipts | `reports/a2a/send_receipts/20260611T171116Z-codex-3b99240cf702.json`, `…171239Z-codex-d673b8b489bc.json`, `…204611Z-fleet-d144173e626f.json` |

Server-side: one durable consumer (`fable_5_cursor_inbox`) created on DHARMA_A2A; nothing else changed on agni.
