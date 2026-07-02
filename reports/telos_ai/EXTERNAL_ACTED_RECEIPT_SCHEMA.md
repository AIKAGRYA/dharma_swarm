# TELOS AI External Acted Receipt Schema

**Track:** `telos-ai-morning-refinery-2026-06`
**Status:** schema only; no external acted receipt exists yet
**Date:** 2026-06-30 Asia/Tokyo

This file defines the minimum evidence required before
`reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md` may be created. It is not
itself the first external acted receipt.

## Non-Negotiable Boundary

The active track forbids processing private user material into repo artifacts
without explicit consent, touching live external accounts, claiming product
market proof, or claiming revenue proof without acted external receipts.

Therefore `FIRST_EXTERNAL_ACTED_RECEIPT.md` must stay absent until at least one
external human has actually acted on a consented TELOS output.

## Required Fields

- `receipt_id`: stable receipt identifier.
- `occurred_at`: exact timestamp of the external action.
- `actor_boundary`: non-identifying description of the external human or
  external system actor.
- `consent_basis`: how the material was allowed to leave private context.
- `input_material_class`: sanitized class of input, not raw private content.
- `output_artifact`: path or link to the consented TELOS output that was acted
  on.
- `external_action`: the action taken by the external human, such as reply,
  adoption, edit, referral, payment, or publication request.
- `evidence_refs`: redacted proof paths or durable references.
- `privacy_redactions`: what was withheld and why.
- `operator_attestation`: short statement that the receipt does not expose
  private material or credentials.

## Creation Rule

Create `reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md` only when the action
exists. A mock, template, design note, internal test, local dashboard render, or
agent self-review does not satisfy this gate.
