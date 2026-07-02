# Track Acceptance Strength Report

Advisory anti-slop membrane: this scores the *strength of evidence required* by active track criteria.

## Summary

- Active tracks: **6**
- Thin declared tracks: **6**
- Warnings: **21**

## Active tracks

| Track | Criteria | Max strength | Thin ratio | Evidence state | Recommendation | Warnings |
|---|---:|---:|---:|---|---|---:|
| runtime-truth-reconciliation-2026-06 | 11 | 1 | 100% | declared-shippable | declared-shippable only: criteria are file/prose backed | 4 |
| runtime-truth-nats-2026-06 | 2 | 1 | 100% | declared-shippable | declared-shippable only: criteria are file/prose backed | 3 |
| runtime-truth-spine-adoption-2026-06 | 8 | 1 | 100% | declared-shippable | declared-shippable only: criteria prove named files/patterns exist; do not claim loop/system closure complete | 4 |
| loop-closure-2026-06 | 5 | 1 | 100% | declared-shippable | declared-shippable only: criteria prove named files/patterns exist; do not claim loop/system closure complete | 4 |
| truth-graph-platform-2026-06 | 15 | 1 | 100% | declared-shippable | declared-shippable only: criteria are file/prose backed | 4 |
| composer-holon-spine-longrun-2026-06 | 6 | 1 | 100% | declared-shippable | declared-shippable only: criteria are file/prose backed | 2 |

## Warning details

### `runtime-truth-reconciliation-2026-06`
- **thin_declared_shippable** (WARN): most/all criteria are file_exists or file_contains checks → prefer declared-shippable; add command/test/runtime criteria before stronger claims
- **runtime_scope_claim** (WARN): runtime/substrate language should be backed by integration or runtime receipts → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **platform_scope_claim** (WARN): platform/system language should not be promoted from thin file criteria alone → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **truth_scope_claim** (WARN): truth/canonical language should be backed by behavior plus negative/adversarial checks → downgrade claim language until at least strength 4 (negative/adversarial test proves failure mode) is present

### `runtime-truth-nats-2026-06`
- **thin_declared_shippable** (WARN): most/all criteria are file_exists or file_contains checks → prefer declared-shippable; add command/test/runtime criteria before stronger claims
- **runtime_scope_claim** (WARN): runtime/substrate language should be backed by integration or runtime receipts → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **truth_scope_claim** (WARN): truth/canonical language should be backed by behavior plus negative/adversarial checks → downgrade claim language until at least strength 4 (negative/adversarial test proves failure mode) is present

### `runtime-truth-spine-adoption-2026-06`
- **thin_declared_shippable** (WARN): most/all criteria are file_exists or file_contains checks → prefer declared-shippable; add command/test/runtime criteria before stronger claims
- **system_scope_closure** (WARN): closure language implies an observed runtime path, not only files/prose → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **runtime_scope_claim** (WARN): runtime/substrate language should be backed by integration or runtime receipts → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **truth_scope_claim** (WARN): truth/canonical language should be backed by behavior plus negative/adversarial checks → downgrade claim language until at least strength 4 (negative/adversarial test proves failure mode) is present

### `loop-closure-2026-06`
- **thin_declared_shippable** (WARN): most/all criteria are file_exists or file_contains checks → prefer declared-shippable; add command/test/runtime criteria before stronger claims
- **system_scope_closure** (WARN): closure language implies an observed runtime path, not only files/prose → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **runtime_scope_claim** (WARN): runtime/substrate language should be backed by integration or runtime receipts → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **truth_scope_claim** (WARN): truth/canonical language should be backed by behavior plus negative/adversarial checks → downgrade claim language until at least strength 4 (negative/adversarial test proves failure mode) is present

### `truth-graph-platform-2026-06`
- **thin_declared_shippable** (WARN): most/all criteria are file_exists or file_contains checks → prefer declared-shippable; add command/test/runtime criteria before stronger claims
- **runtime_scope_claim** (WARN): runtime/substrate language should be backed by integration or runtime receipts → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **platform_scope_claim** (WARN): platform/system language should not be promoted from thin file criteria alone → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present
- **truth_scope_claim** (WARN): truth/canonical language should be backed by behavior plus negative/adversarial checks → downgrade claim language until at least strength 4 (negative/adversarial test proves failure mode) is present

### `composer-holon-spine-longrun-2026-06`
- **thin_declared_shippable** (WARN): most/all criteria are file_exists or file_contains checks → prefer declared-shippable; add command/test/runtime criteria before stronger claims
- **runtime_scope_claim** (WARN): runtime/substrate language should be backed by integration or runtime receipts → downgrade claim language until at least strength 5 (integration/runtime receipt proves path) is present

## Rubric

- **0** — file exists
- **1** — file contains required structured fields
- **2** — command exits 0 with receipt
- **3** — test proves positive behavior
- **4** — negative/adversarial test proves failure mode
- **5** — integration/runtime receipt proves path
- **6** — independent reproduction
- **7** — clean promotion with rollback and caveats
