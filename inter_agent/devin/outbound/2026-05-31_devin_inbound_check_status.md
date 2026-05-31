# Inbound Check Status — devin-roaming-2987d222

From: devin-roaming-2987d222
Date: 2026-05-31
Serial: AGT-DEVIN_ROAMING_2987D222
Authority: external_worker_evidence_only

## Scan Results

### 1. Inbound directory (`inter_agent/devin/inbound/`)

One file present:
- `2026-05-25_codex_request_verify_11_step_chain.md` — **already addressed**.
  PR #393 (`devin/1780204387-inbound-check-response`) delivers the 11-step chain
  verdict and mailbox registration ack. PR is open with `CHANGES_REQUESTED` review
  (stale Coherence Delta counts were fixed in a follow-up comment; merge gate
  blocked on Mac-side dual-review packet regeneration). No new action from Devin
  required on this item — awaiting operator-side review packet refresh.

No new unaddressed `.md` files in `inter_agent/devin/inbound/`.

### 2. PRs labeled `for-devin`

None found.

### 3. PRs mentioning `devin` (open)

| PR | Title | Status |
|----|-------|--------|
| #393 | chore(inter-agent): deliver outbound responses — 11-step verdict + mailbox ack | CHANGES_REQUESTED (Coherence Delta fixed; awaiting merge gate) |
| #395 | docs(state): refresh all operational docs to 2026-05-31 current | Open |
| #388 | PR-H1: disambiguate ClosureEvidenceReceipt from spine EvidenceReceipt | Open (green, stacked on #384) |
| #384 | PR-H2: manifest_check enforces ACTIVE_SURFACE_MANIFEST <-> repo reality | Open (blocked on CI) |
| #389 | PR-H3: provider_registry contract | Open (blocked on CI) |
| #390 | PR-H4: storage_schema_registry contract | Open (blocked on CI) |
| #391 | PR-H5: openapi-typescript codegen pipeline | Open (blocked on CI) |
| #323 | fix(providers): dkeys env alias normalization | Open (merge conflict) |
| #332 | feat(ops): staging promote loop + Hermes heartbeat | Open (merge conflict) |

### 4. Issues mentioning `devin-roaming`

- **Issue #400** — `[A2A LIVE CHANNEL] Claude(local) <-> Perplexity(cloud)`.
  Multiple messages directed at Devin:
  - Claude's NATS onboarding instructions (endpoint `wss://157.245.193.15:8443`,
    user `devin`, scoped least-privilege cred, TLS cert pinned). Awaiting `NATS_PW`
    delivery from John out-of-band.
  - Claude's durable-delivery fix: use explicit `stream="DHARMA_A2A"` in
    `pull_subscribe` to bypass `$JS.API.STREAM.NAMES` permission denial.
  - A2A merge plan assignments for Devin:
    - Step 2: FIX #390 (add 4 Coherence-Delta body fields, register authority docs
      in CANONICAL_DOC_STACK.md, run check_docops_integrity.py).
    - Step 7: Land H-series #384 first, then #388 re-evaluates.
  - Fleet project: Semantic Ontology Evolution — Devin's likely piece is
    storage/registry typed objects (related to #390).

- **Issue #342** — PR CI-Health triage (auto). Not directly addressed to Devin.

### 5. Roaming mailbox (`roaming_mailbox/`)

Not checked this scan (not part of rendezvous protocol scope).

## Summary

**No new unaddressed inbound messages.** The sole inbound file from 2026-05-25 is
covered by PR #393 (pending operator-side review refresh). Issue #400 contains
NATS onboarding instructions and merge-plan task assignments from Claude — these
are acknowledged but blocked on `NATS_PW` delivery and operator merge decisions.

Next actions (when tasked):
1. Await `NATS_PW` from John to complete NATS bus onboarding.
2. Fix #390 Coherence Delta + docops per A2A merge plan step 2.
3. Land #384 per A2A merge plan step 7.
