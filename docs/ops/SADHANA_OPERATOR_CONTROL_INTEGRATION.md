# SADHANA operator-control integration contract

This additive slice publishes authenticated control candidates; it owns no
campaign state. HTTP `202` means only `RequestAccepted`. Authority application
and effect observation are separate claims with separate evidence.

Pinned contracts:

- control semantics: `69a0eb088277882e333ac41a6fb7014f6ed9d792e6d4a4b2b8510f20de15077c`
- HTTP binding: `9e1aec44c75cf6b24341389b8227f57fe4d4cf48328992f2125bffca34fcf3eb`
- active authority binding: `495f16964248948c68f97b5ec02b7e5d3e00e006979bf283ea783127e303d52d`

The earlier preintegration authority digest is superseded and is not admitted.

## Authority lane

Compose `OperatorControlInboxReconciler` into `CampaignService` in the same
process. While holding `CampaignControlGate`, invoke it before each campaign
cycle:

```python
await reconciler.reconcile_once(
    SupervisorControlCallbacks(apply=self._apply_operator_control)
)
```

The only callback is async:

```python
apply(
    request: OperatorControlRequest,
    operator_login: str,
    source_envelope_sha256: str,
) -> Awaitable[AuthorityApplication]
```

The owner transaction must first perform an exact durable
request/idempotency/envelope lookup, including for an expired inflight replay.
If no prior application exists, it applies freshness, exact campaign-session
CAS, and immutable receipt creation atomically. It returns the byte-equivalent
application on replay. A new expired request is rejected without mutation.

`AuthorityApplication` binds exact `request_id`, `idempotency_key`,
`envelope_sha256`, `status`, `authority_receipt_ref`, and
`authority_receipt_sha256`; `effect_observed` must remain false. Only `APPLIED`
or `REJECTED` terminalize. `DEFERRED` remains in `inflight` for bounded replay.
Pause preserves queued work; resume targets the exact paused generation.

Normal custody is `normal -> inflight -> applied|rejected`. Claims and moves are
no-follow, single-link, no-replace operations. Invalid poison is quarantined
with a bounded redacted rejection receipt. Terminal sidecars use schema
`dharma.sadhana.operator_control_terminal.v1` and bind the three pinned digests
as raw lowercase hex fields `control_semantics_sha256`,
`control_http_binding_sha256`, and `control_authority_binding_sha256`. An inbox
ACK or moved file is not the authority claim; the authority-owned CAS/receipt is.

## Release lane

Run the ASGI ingress only as:

```text
python -m scripts.runtime.sadhana_control_api
127.0.0.1:18421
POST /v1/operator-control/requests
```

`uvicorn` is fixed to loopback with proxy headers and access logging disabled.
Required configuration is:

- `CREDENTIALS_DIRECTORY/operator_bearer`: exact EOF, visible ASCII, 32–512 bytes
- `CREDENTIALS_DIRECTORY/control_hmac_key`: exact EOF, 32–4096 arbitrary bytes except CR/LF
- `SADHANA_CONTROL_TAILSCALE_LOGIN_FILE`: exact EOF, visible ASCII, 1–254 bytes
- `SADHANA_CONTROL_EXPECTED_ORIGIN`: one exact canonical HTTPS origin
- optional normal/emergency inbox overrides; defaults are under
  `/run/dharma-sadhana/control`

The five custody directories are `normal`, `emergency`, `inflight`, `applied`,
and `rejected`. The API writes only `normal` or `emergency` and never reads or
writes terminal receipts.

The root emergency path unit must admit filesystem custody first, then reuse:

```python
decode_and_verify_envelope(
    raw,
    secret,
    now,
    expected_actions={ControlAction.EMERGENCY_STOP},
)
```

Candidate failures are `OperatorControlError` subclasses. Import, type,
configuration, and other runtime failures must remain visible rather than be
quarantined as poison. Compare the returned `operator_login` to the root-owned
login credential and bind the filename using `control_filename`. Emergency
verification always uses strict current freshness. Root validates and stops the
target before it writes its authoritative receipt; a runtime move is not that
receipt. Shared adversarial vectors are in
`tests/fixtures/sadhana_operator_control_vectors.v1.json`.

## Dashboard bridge and evidence

Tailscale Serve injects identity into Next. The filesystem route
`POST /dharma-internal/operator-control` is the immediate proxy; it forwards to
the fixed loopback endpoint and injects the bearer from the server-only
`SADHANA_CONTROL_BEARER_FILE`. It forwards exactly Content-Type, Origin,
`Tailscale-User-Login`, and `X-Sadhana-CSRF`, plus injected Authorization. The
CSRF value is exactly `sadhana-10-20260823`. The browser receives neither the
bearer nor port 18421, and the route is deliberately outside the observer's
broad `/api` rewrite.

The UI reads only the optional top-level snapshot sibling
`operator_control_evidence`, schema
`dharma.sadhana.operator_control_evidence.v1`, with this exact field set:

```text
schema_version, claim_stage, control_state, campaign_generation,
transition_sequence, request_id, idempotency_key, action,
source_envelope_sha256, authority_receipt_ref, authority_receipt_sha256,
authority_applied_at, effect_state, effect_receipt_ref,
effect_receipt_sha256, effect_observed_at
```

Evidence joins the pending HTTP result on request ID, idempotency key, action,
and source-envelope digest, and must advance the known generation/sequence.
Missing, malformed, partial, or stale evidence stays
accepted-awaiting-authority/unknown. A separate current-campaign panel renders
only strictly parsed durable evidence, so refresh does not depend on browser
pending state. A connection loss while sending emergency stop is reported as
delivery-outcome-unknown: it is neither synthesized acceptance nor rejection.
Disconnect after emergency acceptance is expected but is not effect proof.
Approve/reject remain visibly disabled and return `501` with no inbox write
until an exact proposal/effect/warrant contract is admitted.
