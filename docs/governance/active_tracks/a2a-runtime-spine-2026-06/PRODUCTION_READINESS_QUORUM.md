# A2A Production Readiness Quorum

Role: readiness rule for subtrack `05-persistent-agent-workflow-and-quorum`.

The operator asked for consensus from at least two persistent agents with IDs
and at least three model families. This file makes that rule machine-checkable
before the track can claim production readiness.

## Required Quorum

Production readiness requires:

- at least two persistent agent IDs;
- at least three distinct model families;
- every reviewer reports a numeric readiness percentage;
- median readiness is at least 80%;
- no reviewer reports a red blocker;
- every claim cites a local receipt or file path that resolves on disk;
- one reviewer must be adversarial/security-minded;
- one reviewer must be operations/devops-minded.

## Reviewer Record Shape

Each reviewer writes one JSON record under:

```text
reports/a2a/prod_readiness_quorum/YYYY-MM-DD/<agent_id>.json
```

Required fields:

```json
{
  "schema_version": "dharma.a2a.prod_readiness_reviewer.v1",
  "agent_id": "codex_composer",
  "model_family": "openai",
  "role": "ops_verifier",
  "readiness_percent": 0,
  "verdict": "not_ready",
  "red_blockers": [],
  "evidence_refs": [],
  "created_at": "UTC timestamp"
}
```

The aggregate quorum writes:

```text
reports/a2a/prod_readiness_quorum/latest.json
```

The aggregate must contain:

```json
{
  "schema_version": "dharma.a2a.prod_readiness_quorum.v1",
  "status": "READY",
  "readiness_percent_median": 80
}
```

Validate and optionally write the aggregate with:

```bash
python3 scripts/runtime/a2a_prod_readiness_quorum.py --date YYYY-MM-DD
python3 scripts/runtime/a2a_prod_readiness_quorum.py --date YYYY-MM-DD --write-latest
```

The active-track gate checks for `"status": "READY"` in `latest.json`; a
`NOT_READY` aggregate is a useful receipt but cannot satisfy production quorum.
The validator also rejects reviewer records whose `evidence_refs` are empty,
URL-only, or point at missing local files. This is deliberate: production
confidence must rest on inspectable repo/runtime receipts, not unverifiable
citations.

## Soliciting Reviewers

Generate request packets and a solicitation receipt with:

```bash
python3 scripts/runtime/a2a_prod_readiness_solicit.py --date YYYY-MM-DD
```

That writes:

```text
reports/a2a/prod_readiness_quorum/YYYY-MM-DD/requests/<agent_id>.json
reports/a2a/prod_readiness_quorum/YYYY-MM-DD/SOLICITATION_RECEIPT.json
```

The solicitation script does not send the packets and does not claim quorum.
Live delivery must be proven separately with an A2A/NATS send receipt. The first
AGNI delivery receipt for this track is:

```text
reports/a2a/prod_readiness_quorum/2026-06-13/FABLE_COMPOSER_SOLICITATION_NATS_SEND.json
```

That receipt proves `PUBLISH_ACCEPTED` into `DHARMA_A2A` for
`dharma.a2a.fable_composer`; it does not prove handler ack, semantic reply, or
production readiness.

## Delivery Status Receipt

Reviewer requests can be published while the target agent remains dark. Record
that state without consuming the target inbox with:

```bash
python3 scripts/runtime/a2a_prod_readiness_delivery_status.py --date YYYY-MM-DD --probe-live --write --write-latest
```

That writes:

```text
reports/a2a/prod_readiness_quorum/YYYY-MM-DD/QUORUM_DELIVERY_STATUS.json
reports/a2a/prod_readiness_quorum/latest_delivery_status.json
```

The delivery-status receipt separates:

- reviewer record present;
- publish accepted but not delivery-verified;
- pending durable delivery;
- delivered but no reviewer record;
- probe failure.

It is read-only against NATS. It runs `consumer info` only; it does not pull,
ack, drain, or otherwise mutate a target agent inbox.

## Reviewer Route Health Receipt

When reviewer records are missing, route failure must also be machine-readable.
Classify each requested reviewer route with:

```bash
python3 scripts/runtime/a2a_reviewer_route_health.py --write --write-latest --json
```

That writes:

```text
reports/a2a/prod_readiness_quorum/YYYY-MM-DD/REVIEWER_ROUTE_HEALTH.json
reports/a2a/prod_readiness_quorum/latest_route_health.json
```

The route-health receipt reads request packets, reviewer records,
delivery-status receipts, live-handler repair plans, reviewer-attempt receipts,
and local persistent-agent identity/state files. It does not send, pull, ack,
start, stop, or claim review. Its job is to say whether the route is satisfied,
provider-blocked, handler-stalled, or unproven.

## Blocker Status Receipt

Reviewer records are evidence and should not be hand-edited when the substrate
changes. Classify old reviewer red blockers against current receipts with:

```bash
python3 scripts/runtime/a2a_quorum_blocker_status.py --write --write-latest --json
```

That writes:

```text
reports/a2a/prod_readiness_quorum/YYYY-MM-DD/QUORUM_BLOCKER_STATUS.json
reports/a2a/prod_readiness_quorum/latest_blocker_status.json
```

The blocker-status receipt separates stale/resolved red-blocker text from
current production blockers. It does not clear the quorum gate. If it finds
stale red blockers, the correct action is to collect fresh reviewer records
against the latest receipts, not to edit old reviewer JSON.

## Current 2026-06-13 State

Current aggregate:

```text
reports/a2a/prod_readiness_quorum/latest.json
```

As of the latest refresh, the aggregate is `NOT_READY` with:

- reviewer records present for `codex_composer` (`openai`), `qwen_code`
  (`alibaba`), and `gemini_reviewer` (`google`);
- reviewer records still missing for `fable_composer` and `hermes_m5`;
- delivery status `CONSUMER_EMPTY_NO_DELIVERY` for Fable and Hermes after the
  post-Qwen consumer reset, meaning there is no current backlog and still no
  target-owned reviewer receipt;
- three persistent agent IDs and three model families witnessed;
- red blockers reported by all three existing reviewers;
- median readiness below the required 80%.
- blocker-status receipt
  `reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_BLOCKER_STATUS.json`
  reports `BLOCKED_BY_CURRENT_EVIDENCE`: 13 reviewer red blockers total, 4
  stale/resolved, 2 partially resolved, and 7 still current.
- route-health receipt
  `reports/a2a/prod_readiness_quorum/2026-06-13/REVIEWER_ROUTE_HEALTH.json`
  reports `ROUTE_HEALTH_BLOCKED`: `fable_composer` is provider-credit blocked
  on the documented `claude -p` route, and `hermes_m5` is
  provider-timeout/handler-stalled on the `hermes -z` route.

Attempt receipts:

- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T190713Z-fable_composer-claude_cli_failed.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T195938Z-fable_composer-claude_cli_credit_failed.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T201843Z-fable_composer-claude_cli_smoke_credit_failed.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T190826Z-hermes_m5-hermes_cli_timeout.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T202230Z-hermes_m5-hermes_cli_timeout.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T191130Z-devin-roaming-2987d222-devin_cli_quota_failed.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T191012Z-qwen_code-qwen_cli_raw.md`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T193929Z-gemini_reviewer-gemini_cli_raw.md`

The Qwen and Gemini reviews are useful diversity evidence, not production
readiness. Qwen reported `not_ready`, readiness `42`, and red blockers. Gemini
reported `not_ready`, readiness `62`, and red blockers. The Fable, Hermes, and
Devin attempts produced no reviewer record because their provider routes failed
or timed out.

## What The Quorum Must Judge

1. NATS broker topology is bounded and documented.
2. Hot-contact sends prove at least `HANDLER_ACKED`.
3. Domain replies can prove `DOMAIN_RECEIPTED`.
4. File inboxes are dock/mirror surfaces, not live-contact authority.
5. Shared graph/vector/board surfaces cite owners and do not become authority.
6. A2A external gateway and cloud agents authenticate identity before entering
   internal subjects.
7. Active-track docs, runbooks, and receipts are findable from this subtree.
8. The reset/drain receipt proves before/after state.

## Production Confidence Language

Allowed:

- "80% confidence from quorum; red blockers zero; evidence paths listed."
- "ready for limited operator-supervised production."

Not allowed:

- "100% prod" unless every completion criterion in `ACTIVE_TRACK.yaml` passes
  and the quorum file exists.
- "agent replied" from publish or bridge ack alone.
- "semantic graph is authoritative" from retrieval quality alone.
