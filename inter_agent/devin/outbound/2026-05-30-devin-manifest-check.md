# Devin Outbound — PR-H2 Manifest Check (ACTIVE_SURFACE_MANIFEST ↔ Repo Reality)

**From:** Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only`
**Date:** 2026-05-30
**Branch:** `devin/2026-05-30-manifest-check` (sibling to `devin/2026-05-30-proof-artifact-pivot`, parent PR #382)
**Active track:** `runtime-truth-spine-2026-06` — not displaced.
**Frozen surfaces touched:** none.
**Doctrine posture:** zero new substrate, zero meta-framework, zero parallel governance. Tightens an existing manifest into an enforced invariant.

## What this is

A response to the operator's question about robustness, future-proofing, and "Python spaghetti plate" risk, framed as the highest-leverage-per-LOC PR in the modularity hardening slate.

`ACTIVE_SURFACE_MANIFEST.yaml` already exists. 657 lines. Schema v2. Last updated 2026-05-20. It declares state_dir, api_routers, hot_path_modules, governance_rules, dashboard_surfaces, agents, integrations, loops. It is documentation today. **This PR makes it an enforced invariant.**

Drift between manifest and code reality was already accumulating: `revenue_router` and `fleet_router` were wired in `api/main.py` but not declared in the manifest; one loop entry pointed at a `shakti_loop.py` file that did not exist. The checker catches drift the moment it appears.

## What landed

Net: **+540 LOC of stdlib Python + 23 LOC of YAML + 3 reconciliation edits to the manifest itself.** No new dependencies (PyYAML already present). No code edits to any frozen surface. No new packages. No new abstractions.

1. `tools/manifest_check.py` (~540 LOC, pure stdlib + PyYAML)
   Five checks, three modes:
   - `manifest_parseable` — YAML parses, schema_version ∈ {2}
   - `routers_declared_and_wired` — every manifest `api_routers[]` entry exists on disk **and** is `include_router`'d in `api/main.py`; bidirectional. AST-parsed, not regex.
   - `agents_modules_exist` — every `agents[].module`, `hot_path_modules[].module`, `loops[].module`, `recursive_discovery_surfaces[].owner_module` file exists.
   - `state_dir_paths_via_helper` — counts raw `~/.dharma/...` literals under `dharma_swarm/*.py` (excluding the canonical `daemon_config.py`). Budget-bounded: pre-existing literals are grandfathered; new literals fail CI. Budget ratchets down only via explicit `--update-budget`. Current ceiling: **28**.
   - `evidence_receipt_uniqueness` — the canonical two `class EvidenceReceipt:` definitions at `dharma_swarm/operator_core/closure_v0.py` and `dharma_swarm/spine/receipt.py` must both exist, and **no third** definition is allowed. This is PR-H1's CI piece, folded in here — same pattern, same PR. Adding a third EvidenceReceipt fragments the truth surface; the checker refuses.

   CLI modes:
   - `--check` (default, CI): exit 1 on any error.
   - `--report -v`: human-readable summary; exit 0 regardless of findings.
   - `--update-budget`: ratchet `state_dir_literals` to current count; write `tools/manifest_check_budgets.json`; exit 0.

2. `tools/manifest_check_budgets.json` — `{"state_dir_literals": 28}`. Floor for the literal-count ratchet.

3. `.github/workflows/manifest-check.yml` — minimal Actions workflow mirroring `spine-check.yml`. Runs on push/PR to `main`. Python 3.12. Installs PyYAML. Runs `python tools/manifest_check.py`. Exit code = PR status.

4. `.pre-commit-config.yaml` — adds `dharma-manifest-check` hook in the local-hooks block, alongside the existing `dharma-test-hygiene`, `dharma-contract-tests`, `dharma-uplift-guards`, `dharma-docops-integrity` hooks. Always-runs, system language.

5. `ACTIVE_SURFACE_MANIFEST.yaml` — three reconciliation edits:
   - Added `api_routers[]` entries for `revenue` (`/api/revenue`) and `fleet` (`/api/fleet`) — both were already live in `api/main.py`, just undeclared.
   - Corrected `loops[shakti_perception].module` from `dharma_swarm/shakti_loop.py` (does not exist) to `dharma_swarm/shakti.py` (exists, 200 LOC, is exactly the Shakti perception layer the manifest entry describes).

6. `docs/reports/modularity_and_future_proofing_audit_v1.md` (358 lines) — the full audit that justifies the 5-PR hardening slate (PR-H1 receipt convergence, **PR-H2 manifest checker [this PR]**, PR-H3 providers god-module split, PR-H4 storage package, PR-H5 openapi-typescript codegen). Includes topology stats, god-module ranking, EvidenceReceipt duplication analysis, storage fragmentation count, concept-debt enumeration.

7. `docs/reports/polyglot_proposal_critical_review_v1.md` (313 lines) — the rejection report for the prior Python+Rust+Go+Lean rewrite proposal. Included here because it establishes the doctrine boundary this PR operates inside: the operator's concern is real modularity, not language pluralism. The audit and PR-H2 are the substantive response.

## Final state

```
$ python tools/manifest_check.py --report -v

manifest-check info:
  state_dir_paths_via_helper: literals=28, budget=28, offender files=19

manifest-check: all checks passed.
```

Exit code 0. Five checks pass. Drift baseline locked.

## What this catches the next time someone tries it

- Wiring a new router into `api/main.py` without declaring it in the manifest → CI fail.
- Removing a manifest-declared router from `api/main.py` → CI fail.
- Renaming or deleting an `agents[].module` file without updating the manifest → CI fail.
- Adding a new `~/.dharma/...` literal anywhere under `dharma_swarm/` instead of routing through `daemon_config` → CI fail. (Existing 28 grandfathered; ratchet-down only.)
- Defining a third `class EvidenceReceipt:` anywhere in the repo → CI fail.
- Removing one of the two canonical `class EvidenceReceipt:` definitions without editing `_CANONICAL_RECEIPT_SITES` in the checker in the same PR → CI fail.

## What this is not

- Not a new substrate. The manifest already existed.
- Not a new framework. One stdlib script.
- Not parallel governance. Reports to the existing manifest as authoritative.
- Not a refactor. Zero behavior changes. Manifest YAML is the only "code" edit, and only to declare reality.
- Not "future-proofing for new models" — that's **PR-H3** (split `providers.py` god-module, 3,005 LOC, 20 providers, into `providers/` package + `register_provider()` decorator). See `docs/reports/modularity_and_future_proofing_audit_v1.md` §5.
- Not "stop the storage spaghetti" — that's **PR-H4**.

## Why this is the right move first

PR-H1's surface area is one rename of a class plus 53 import migrations. PR-H2's surface area is one new tool + four YAML lines + one workflow file, and it **also enforces PR-H1's invariant** (check 5: receipt uniqueness) without requiring the actual rename today. That means PR-H2 buys time: until PR-H1 lands, the checker proves the two-receipts state is *deliberately frozen at two*, not silently growing toward three.

Highest leverage-per-LOC in the slate. Ships first. Unblocks the rest.

## Operator decision points

1. **Accept this PR as-is, then queue PR-H3** (providers god-module split): yes / no / modify.
2. **Ratchet down `state_dir_literals` budget to 28 immediately**: this PR locks it at 28. PR-H4 (storage package) will drive it down further. Acceptable.
3. **Allow checker to evolve `_CANONICAL_RECEIPT_SITES` when PR-H1 lands**: yes / no. (PR-H1 will need to edit the checker's hardcoded set in the same PR that renames the second class.)

## Anti-doctrine self-check

- Builds AGI? No.
- Uncontrolled self-modification? No — the checker has no write authority over the repo except `tools/manifest_check_budgets.json`, which is gitignored-by-convention-not (committed for ratchet floor).
- Autonomous capital deployment? No.
- Autonomous external messaging? No.
- Deceptive memetic engineering? No.
- Parallel governance? No — defers to `ACTIVE_SURFACE_MANIFEST.yaml` as the single source of declared truth.
- Vague prose? Five checks, deterministic, AST-parsed, exit-code-driven.
- New substrate? No.
- Meta-framework? No — one script.

Authority compliance: this notice + open PR + await operator merge. No autonomous merge.
