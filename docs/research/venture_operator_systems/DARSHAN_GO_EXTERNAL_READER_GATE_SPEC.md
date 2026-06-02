# Darshan-Go External Reader Gate Spec

Date: 2026-06-02
Status: implementation-ready design
Owner surface: `dharma_swarm/venture_cell/darshan/`

## Decision

The Darshan external-reader/contact gate must be backed by accepted Go evidence receipts.

Go is the evidence organ only. Python/Dharma governance owns validation, gate decisions, TaskBoard state, Chetana ingest, DecisionLog, and any advancement to DONE.

## Current State

Darshan governance already requires at least one external-reader event before DONE. The policy lives in `docs/governance/VENTURE_CELL_DARSHAN.md`.

Darshan schemas currently have:

- `DecisionDelta.evidence_refs`
- `GateDecisionRecord.evidence_refs`
- `AttentionLedger.reader_feedback_observed`
- `SourceRecord.receipt_path`
- `ExternalOperatorObservation.artifacts_or_urls`
- `ExternalOperatorObservation.screenshot_refs`
- `ExternalOperatorObservation.missing_receipts`

Missing: a typed external-reader event model and typed Go receipt references.

Go evidence receipts already have:

- `receipt_id`
- `correlation_id`
- `source`
- `source_url`
- `observed_at`
- `content_hash`
- `event_uid`
- `schema_version`
- `status`
- `payload`

Python bridge already requires `schema_version == go_evidence_receipt.v0` and `status == accepted`.

## Schema Additions

Add these models to `dharma_swarm/venture_cell/darshan/schema.py`.

```python
class ExternalReaderEventType(str, Enum):
    READ = "read"
    REPLY = "reply"
    INSPECTION = "inspection"
    DECISION = "decision"
    CONTACT_ATTEMPT = "contact_attempt"


class GoEvidenceReceiptRef(DarshanBaseModel):
    receipt_path: str
    receipt_id: str = ""
    correlation_id: str = ""
    source: str = "darshan_external_reader"
    source_url: str = ""
    observed_at: str = ""
    content_hash: str = ""
    event_uid: str = ""
    schema_version: str = "go_evidence_receipt.v0"
    status: Literal["accepted", "rejected", "missing", "invalid"] = "missing"


class ExternalReaderEvent(DarshanBaseModel):
    event_id: str = Field(default_factory=lambda: new_id("reader"))
    artifact_id: str
    event_type: ExternalReaderEventType
    reader_label: str = ""
    reader_contact_hash: str = ""
    contact_surface: str = ""
    summary: str = ""
    occurred_at: str = Field(default_factory=utc_now_iso)
    human_approved_contact: bool = False
    consent_public: bool = False
    privacy_notes: list[str] = Field(default_factory=list)
    go_receipt: GoEvidenceReceiptRef
    evidence_refs: list[str] = Field(default_factory=list)
```

Extend `DecisionDelta`:

```python
external_reader_events: list[ExternalReaderEvent] = Field(default_factory=list)
```

Countable DONE events are `read`, `reply`, `inspection`, and `decision`. `contact_attempt` is useful evidence but does not satisfy the gate.

## Go Receipt Payload Contract

Recommended Go receipt:

```json
{
  "schema_version": "go_evidence_receipt.v0",
  "source": "darshan_external_reader",
  "source_url": "mailto-hash://... or https://...",
  "status": "accepted",
  "payload": {
    "artifact_id": "darshan-...",
    "event_type": "reply",
    "reader_label": "external_reader_001",
    "reader_contact_hash": "sha256:...",
    "contact_surface": "email",
    "summary": "Reader replied with a substantive inspection.",
    "human_approved_contact": true,
    "consent_public": false,
    "privacy_redacted": true
  }
}
```

The payload must never contain raw private email addresses, phone numbers, private message bodies, payment secrets, or OAuth tokens. Hash/redact private contact details before receipt emission.

## Gate Validator

Add a new Python module:

`dharma_swarm/venture_cell/darshan/external_reader_gate.py`

Public API:

```python
class ExternalReaderGateResult(DarshanBaseModel):
    artifact_id: str
    pass_gate: bool
    countable_events: int
    checked_events: int
    accepted_receipts: list[str]
    rejected_receipts: list[str]
    missing_receipts: list[str]
    errors: list[str]
    warnings: list[str]


def validate_external_reader_gate(bundle_path: Path) -> ExternalReaderGateResult:
    ...
```

Validation behavior:

1. Load and validate the Darshan bundle using existing `validate_bundle`.
2. Load `decision_delta.json`.
3. Read `external_reader_events`.
4. For every event, load `event.go_receipt.receipt_path` using `load_go_evidence_receipt`.
5. Require `schema_version == go_evidence_receipt.v0`.
6. Require `status == accepted`.
7. Require `source == darshan_external_reader`.
8. Require `source_url` non-empty.
9. Require receipt payload `artifact_id` equals the bundle artifact ID.
10. Require payload `event_type` matches the event.
11. Require event type in `read`, `reply`, `inspection`, or `decision`.
12. Require `human_approved_contact == true` for outreach-sourced events.
13. Return `pass_gate=True` only if at least one countable accepted event exists.

Failure modes:

- No `external_reader_events`: fail with `external_reader_event_missing`.
- URL or summary only, no Go receipt: fail with `go_receipt_missing`.
- Receipt rejected: fail with `go_receipt_rejected`.
- Receipt accepted but wrong source: fail with `wrong_go_receipt_source`.
- Receipt accepted but artifact mismatch: fail with `artifact_id_mismatch`.
- Contact attempt only: warn, but fail DONE gate.
- Private payload not redacted: fail with `privacy_leak_risk`.

## Bundle Semantics

Keep `validate_bundle()` as a draft-structure validator.

Add a stricter advancement validator:

```python
def validate_bundle_for_done(bundle_path: Path) -> BundleValidationResult:
    ...
```

It should call `validate_bundle()` plus `validate_external_reader_gate()`.

Draft bundles can exist without external reader evidence. DONE advancement cannot.

## Control Surface Row

Add a Darshan-specific row, not just a generic Go row:

- id: `darshan.external_reader_go_receipts`
- kind: `venture_cell_gate`
- label: `Darshan External Reader Gate`
- authority_role: `gate`
- truth_owner: `dharma_swarm/venture_cell/darshan/external_reader_gate.py`
- owner_module: `dharma_swarm/venture_cell/darshan/external_reader_gate.py`
- observed_state:
  - `no reader events`
  - `receipt missing`
  - `receipt rejected`
  - `contact attempt only`
  - `external reader accepted`
- coherence_state:
  - `declared_only` when docs require the gate but no events/receipts exist;
  - `partial` when events exist but do not pass;
  - `bound` when at least one accepted countable Go receipt exists.

This row should include receipt IDs, event UIDs, bundle path, artifact ID, and source refs to the gate module, `decision_delta.json`, and receipt path.

## Chetana Ingest

When `validate_external_reader_gate()` passes, stage an atom with:

- title: `Darshan external reader event: {artifact_id}`
- source kind: `receipt`
- tags: `darshan`, `venture-cell`, `external-reader`, `go-receipt`, `contact-gate`
- related paths: bundle path, decision delta, receipt path, source pack
- trust state: staged until reviewer approval
- summary: privacy-redacted event summary

Do not promote automatically.

## Tests

Add tests under `tests/test_darshan_external_reader_gate.py`.

Required tests:

1. Draft bundle with no reader events remains bundle-valid but DONE-gate fails.
2. Decision delta with URL only and no Go receipt fails.
3. Rejected Go receipt fails with rejected reason preserved.
4. Accepted Go receipt with wrong source fails.
5. Accepted Go receipt with artifact mismatch fails.
6. Accepted Go receipt with only `contact_attempt` fails countable gate but records warning.
7. Accepted Go receipt with `reply` passes.
8. Gate result can be projected into a control-surface row.
9. Passing event stages a Chetana atom with receipt refs.
10. No Go-side decision/dispatch/mutation is introduced.

## Acceptance Criteria

- Darshan DONE advancement has a deterministic Python gate.
- At least one accepted Go evidence receipt is required for countable reader/contact proof.
- Draft bundle validation remains possible before contact.
- Control surface shows missing, rejected, partial, and bound states.
- Chetana receives a privacy-redacted staged atom for successful events.
- Human approval remains required for outreach and publishing.
- Go remains evidence-only.

