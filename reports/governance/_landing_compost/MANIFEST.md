# Landing Compost Manifest

Date: 2026-06-14 JST
Goal: `codex-goal:019ec1bc`
Scope: runtime-spine hardening landing

## Policy

This directory is for clear one-off scratch artifacts from the runtime-spine
landing pass. It is not a deletion sink and not a place to hide evidence.

## Composted Files

No repo files were moved into compost during this landing pass.

Reason: the visible repo artifacts are either review evidence, generated
governance evidence, runtime-spine source/tests, or explicitly excluded
Palantir/cybernetics lanes. None was clearly safe one-off scratch.

## External Temporary Outputs

Temporary verifier outputs were written outside the repo and left in place for
local review:

```text
/private/tmp/runtime-spine-landing-20260614/out/spine_bypass_report.json
/private/tmp/runtime-spine-landing-20260614/out/spine_dispatch_mode_report.json
/private/tmp/runtime-spine-landing-20260614/out/runtime_receipt_coverage_report.json
/private/tmp/runtime-spine-landing-20260614/out/live_ops_census.json
/private/tmp/runtime-spine-landing-20260614/state/state/runtime.db
```

These are copied-state/temp-output evidence, not canonical repo artifacts.

