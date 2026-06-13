# 01 — Truth Verifiers

Consolidated findings on what the docs say vs what the code does vs what is wired in the runtime. The truth-verification corpus.

**As of:** 2026-06-13  
**Sources merged:** 19 files (~200KB)  
**Live owners pointed to:** `docs/state/BROKEN_REGISTER.md`, `INTERFACE_MISMATCH_MAP.md`, `docs/governance/REPO_GOVERNANCE_AUDIT.md`, `docs/architecture/VERIFICATION_LANE.md`  

## Live owners (KEEP-LIVE — NOT in this corral, pointed to)

These are the canonical ledgers/maps for declared-vs-actual truth. The Bug Corral does not duplicate them; it points to them. Deleting any of these would break CI, onboarding, or canon.

| Path | Role |
|------|------|
| `docs/state/BROKEN_REGISTER.md` | Append-only BR-NNN ledger of broken/stale/degraded surfaces. The live 'what is broken today' owner. |
| `INTERFACE_MISMATCH_MAP.md` | Auto-maintained interface-level declared-vs-actual gap log (guardian_crew.py). The live substrate for this file. |
| `docs/governance/REPO_GOVERNANCE_AUDIT.md` | CANON (per docs/AGENTS.md): owns contradictions/staleness. |
| `docs/architecture/VERIFICATION_LANE.md` | Active read-only verifier doctrine for DGC + dharma_swarm. |
| `docs/governance/REALITY_DEBT_LEDGER.md` | Anti-overclaim firewall: high-value claims still needing proof. |

## Index of merged findings

| # | Original path | Date | Grade | Summary |
|---|----|------|-------|---------|
| 1 | [`reports/governance/runtime_truth_command_cutover_baseline_2026-06-12.md`](#section-1-reports-governance-runtime-truth-command-cutover-baseline-2026-06-12-md) | 2026-06-12 | ENDURING | Baseline receipt for the 2026-06-12 runtime-truth command cutover pass: 63 dirty files before pass, on branch holon/spine-v1 @ f0d03ffaf4. |
| 2 | [`reports/governance/runtime_truth_command_cutover_after_action_2026-06-12.md`](#section-2-reports-governance-runtime-truth-command-cutover-after-action-2026-06-12-md) | 2026-06-12 | ENDURING | After-action for the 2026-06-12 command cutover: enforced the existing spine; created no new command spine. |
| 3 | [`reports/anatomy_altitude_2026-06-10/lane_B_truth.md`](#section-3-reports-anatomy-altitude-2026-06-10-lane-b-truth-md) | 2026-06-12 | ENDURING | Lane B (truth) of the 6-lane anatomy-altitude system x-ray: live spine vs declared spine, every claim cites file:line, clean negatives are first-class. |
| 4 | [`docs/sovereign_holons/STATE_OF_TRUTH.md`](#section-4-docs-sovereign-holons-state-of-truth-md) | 2026-06-13 | ENDURING | Reality-vs-intention state-of-truth for sovereign_holons (the one place that records what is wired and what is not). |
| 5 | [`docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md`](#section-5-docs-governance-runtime-truth-command-cutover-md) | 2026-06-13 | ENDURING | Active enforcement map for the runtime-truth command cutover (records command cutover state for live operator-facing surfaces). |
| 6 | [`reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md`](#section-6-reports-governance-runtime-truth-spine-v2-subagent2-v1-verification-md) | 2026-06-06 | ENDURING | Spine v2 subagent-2 verification: clean-HEAD v1 claim falsified; verified against worktree /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 @ 2737b26d. |
| 7 | [`reports/governance/runtime_truth_spine_v2_report.md`](#section-7-reports-governance-runtime-truth-spine-v2-report-md) | 2026-06-06 | ENDURING | Spine v2 report: v1 claim corrected, built from a clean worktree at current origin/main not from the dirty developer checkout. |
| 8 | [`reports/governance/runtime_truth_spine_v2_evidence_plan.md`](#section-8-reports-governance-runtime-truth-spine-v2-evidence-plan-md) | 2026-06-06 | ENDURING | Spine v2 evidence bundle plan: audit source boundary, clean audit baseline d5ebc456 from the clean-main architecture worktree. |
| 9 | [`docs/research/RUNTIME_TRUTH_SPINE_COMPLETION_PLAN.md`](#section-9-docs-research-runtime-truth-spine-completion-plan-md) | 2026-06-06 | ENDURING | Runtime Truth Spine completion plan: stabilize the spine as substrate; no ontology refactor, no ingestor rewrite, no runtime behavioral change. |
| 10 | [`docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md`](#section-10-docs-reports-converged-seam-audit-runtime-truth-spine-md) | 2026-06-06 | ENDURING | Converged seam audit (routing x pool x A2A x provider): one shared diagnosis and one shared build direction before more agent-fabric work. |
| 11 | [`docs/reports/DGC_FORENSIC_TRUTH_REPORT_2026-03-08.md`](#section-11-docs-reports-dgc-forensic-truth-report-2026-03-08-md) | 2026-04-04 | RESOLVED-HIST | DGC forensic truth report (2026-03-08): static code audit + executable command verification on /dharma_swarm branch split/2026-03-08 @ 8077792. |
| 12 | [`docs/state/DASHBOARD_FIDELITY_AUDIT.md`](#section-12-docs-state-dashboard-fidelity-audit-md) | 2026-06-05 | ENDURING | Dashboard data-fidelity audit (2026-05-20): provider keys present; remaining env-alias and provider-auth fidelity gaps. |
| 13 | [`reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md`](#section-13-reports-dashboard-dashboard-wiring-audit-2026-03-19-md) | 2026-03-23 | RESOLVED-HIST | Older dashboard wiring audit (2026-03-19): backend contract mostly live, Claude lane health-check defect. Superseded by DASHBOARD_FIDELITY_AUDIT but kept as historical baseline. |
| 14 | [`docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md`](#section-14-docs-research-palantir-ontology-vocabulary-census-andon-reconciliation-md) | 2026-06-05 | ENDURING | Andon reconciliation (Codex audit vs ground truth): verdict matrix. Load-bearing finding — ontology.py:594-639 execute_action logs success without applying mutations; InterruptGate auto-approve at cascade.py:36. |
| 15 | [`docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-A.md`](#section-15-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-perplexity-a-md) | 2026-06-05 | ENDURING | Andon slice A (identity sprawl) evidence backing the reconciliation. |
| 16 | [`docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-B.md`](#section-16-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-perplexity-b-md) | 2026-06-05 | ENDURING | Andon slice B (envelope schemas) evidence backing the reconciliation. |
| 17 | [`docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-C.md`](#section-17-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-perplexity-c-md) | 2026-06-05 | ENDURING | Andon slice C (authority+execution) evidence backing the reconciliation. |
| 18 | [`docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-D.md`](#section-18-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-devin-d-md) | 2026-06-02 | ENDURING | Andon slice D (workflow-state owners) evidence. |
| 19 | [`docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-E.md`](#section-19-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-devin-e-md) | 2026-06-02 | ENDURING | Andon slice E (A2A protocol vs work-queue conflation) evidence. |

---

## Section 1 — `reports/governance/runtime_truth_command_cutover_baseline_2026-06-12.md` <a id="section-1-reports-governance-runtime-truth-command-cutover-baseline-2026-06-12-md"></a>

> **Original path:** `reports/governance/runtime_truth_command_cutover_baseline_2026-06-12.md`  
> **Source date:** 2026-06-12  
> **Author/Owner:** AmitabhainArunachala  
> **Size:** 2,719 bytes  
> **sha256:** `6f6a94b56c9a5a1d8030dbca18dabaef8fce983cc3bbafd778fb85ba4c5bc19b`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Baseline receipt for the 2026-06-12 runtime-truth command cutover pass: 63 dirty files before pass, on branch holon/spine-v1 @ f0d03ffaf4.

### Verbatim content

### Runtime Truth Command Cutover Baseline Receipt

Generated: 2026-06-12
Worktree: `/Users/dhyana/dharma_swarm_main`

#### Branch And HEAD

- Branch: `holon/spine-v1`
- HEAD: `f0d03ffaf4 fix(runtime): repair ds-goal entrypoint`
- Baseline divergence from `origin/main`: ahead 5, behind 3

#### Dirty Worktree Truth

Baseline `make onboard` reported 63 dirty files before this cutover pass.
Dirty areas already included tests, `scripts/runtime`, operator-core, control
surface, and generated governance reports. This pass preserved unrelated dirty
work and only edited the files named in the after-action.

#### Active Tracks

`make onboard` projected two active tracks:

- `runtime-truth-reconciliation-2026-06`: ACTIVE, SHIPPABLE
- `runtime-truth-nats-2026-06`: ACTIVE, SHIPPABLE

Projected spine coverage gaps:

- no active track for `revenue-external-humans-served`
- no active track for `research-depth`

#### Runtime Truth Claims

Latest onboard runtime compact before edits:

- runtime DB: `/Users/dhyana/.dharma/state/runtime.db`
- latest receipt: `runtime_receipts:rr_b38bdcee9c944307`
- run id: `kernel_run_75b788dc28db44d8`
- task id: `codex-runtime-truth-smoke-20260611t090734z-t01`
- heartbeat/progress: stalled by artifact progress
- completion: completed by receipt
- retry: retry equivalent

#### Spine Adoption Metric

Observed `reports/governance/spine_adoption_metric.json` baseline:

- joined count: 12
- adapter-ready count: 3
- joined or adapter-ready: 93.8 percent
- joined percent: 75.0 percent
- legacy count: 1
- missing count: 0
- non-joined targets: `tool_registry_dispatch`, `self_modification_loop`,
  `mcp_tool_access`, `legacy_no_identity_escape_hatch`

#### AMBER And RED Claims

- AMBER: runtime saturation is partial until default command paths prove
  idempotency, runtime receipts, and dispatch evidence.
- AMBER: revenue and external-human proof are absent from active tracks.
- AMBER: research-depth proof is absent from active tracks.
- AMBER: AgentOps green gates without runtime refs must not project as bound.
- RED: live trading authority without explicit external/legal authority.
- RED: Forge/Hydra runnable claims without a fresh run receipt.

#### Known Cutover Targets

- `scripts/runtime/autonomy_spine.py` (`ds-goal`)
- `scripts/runtime/a2a_send.py`
- `scripts/runtime/a2a_reply_capture.py`
- `dharma_swarm/board/adapters/a2a_send_adapter.py`
- `dharma_swarm/operator_core/operating_facts.py`
- onboarding runtime truth compact summary

#### Substrate Track State

The active substrate tracks were already projected as shippable by onboarding.
This receipt does not upgrade that to full runtime saturation. It records the
starting point for a narrower command cutover enforcement pass.

---

## Section 2 — `reports/governance/runtime_truth_command_cutover_after_action_2026-06-12.md` <a id="section-2-reports-governance-runtime-truth-command-cutover-after-action-2026-06-12-md"></a>

> **Original path:** `reports/governance/runtime_truth_command_cutover_after_action_2026-06-12.md`  
> **Source date:** 2026-06-12  
> **Author/Owner:** AmitabhainArunachala  
> **Size:** 7,875 bytes  
> **sha256:** `b70af30c08b2ee78723c69d71cde196d5391524d7bdd21c904bfb3c57b507b5c`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** After-action for the 2026-06-12 command cutover: enforced the existing spine; created no new command spine.

### Verbatim content

### Runtime Truth Command Cutover After-Action

Generated: 2026-06-12
Worktree: `/Users/dhyana/dharma_swarm_main`
Branch: `holon/spine-v1`
HEAD at verification: `f0d03ffaf4`

#### Summary

This pass enforced the existing Runtime Truth Spine. It did not create a new
command spine, command ledger, `WorkCommand`, `WorkRun`, `WorkReceipt`,
`command_runs`, or `work_runs`.

#### Implemented

- Added `docs/governance/SWARM_GENOME.md` as the compact first-token map.
- Added `docs/governance/REALITY_DEBT_LEDGER.md` with the required
  `claim | current custody | proof missing | owner | next receipt | allowed language`
  table.
- Added `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md` with the command
  matrix, default-path adoption metric, evidence semantics, and bypass list.
- Wired `SWARM_GENOME.md` into the max-five first-read stack and registered
  the new governance docs in DocOps.
- Updated onboarding to show runtime `mission_id`, artifact-ref count, the
  first-token map, and the reality-debt count.
- Updated runtime truth summaries to include `mission_id` and `artifact_refs`.
- Updated AgentOps projection so green gates plus clean scope are only `bound`
  when runtime truth refs are present.
- Cut over A2A direct send to `ExecutionIdentity` and `RuntimeStateStore`
  idempotency before direct NATS publish, with a command-level `RuntimeReceipt`.
- Removed unsafe JetStream-to-core fallback after ambiguous publish errors and
  made A2A send receipt file creation atomic under concurrent retries.
- Added the first Runtime Warrant layer in `dharma_swarm/spine/warrant.py`.
  A2A direct send now requires a pre-publish warrant, and ds-goal run now
  requires a pre-kernel-wake warrant. Warrant denial blocks the side effect.
- Refined Runtime Warrant criteria after a broader connection pass: claim names
  are normalized, unknown surface/action pairs fail closed, blank claim
  boundaries fail closed, and idempotency now requires a matching
  RuntimeStateStore row rather than a boolean flag alone.
- Added direct `EvidenceReceipt` association for A2A direct send and ds-goal.
  Each command builds a `spine.EvidenceReceipt` and embeds its JSON plus compact
  ref inside the existing command `RuntimeReceipt` payload. This intentionally
  does not create a `dispatch_evidence` runtime receipt row or a second receipt
  hierarchy.
- Hardened A2A reply capture so untyped replies are non-semantic and
  untyped `domain_receipt: true` self-assertions cannot escalate evidence tier.
- Updated A2A BoardStore cards so handler delivery ack projects as `review`,
  not `done`.
- Hardened `ds-goal` so mission IDs and existing symlink mission directories
  cannot escape state root and idempotency is claimed before kernel wake
  dispatch.
- Hardened AgentOps and ds-goal BoardStore projections so local `done` status
  requires runtime or kernel proof refs before projecting as complete.
- Added a static guard test banning parallel command-spine source symbols.
- Refreshed `reports/governance/spine_adoption_metric.json`.
- Added `reports/governance/command_cutover_metric.json`.

#### Verification

- `python3 -m compileall` on touched runtime, governance, board, and test files:
  passed.
- Focused first slice:
  `pytest -q tests/test_a2a_send.py tests/test_a2a_reply_capture.py tests/test_control_surface_a2a_cards.py tests/test_autonomy_spine_cli.py tests/test_runtime_truth_projection_fields.py tests/test_operating_facts.py tests/test_runtime_truth_command_cutover.py tests/test_ds_goal_board_adapter.py tests/test_control_surface_ds_goal_cards.py`
  passed: 47 tests.
- Full handoff-listed focused suite:
  `pytest -q tests/test_runtime_truth_spine_v2_evidence.py tests/test_runtime_state_invariants.py tests/test_spine_persistence_invariant.py tests/test_autonomy_spine_cli.py tests/test_ds_goal_board_adapter.py tests/test_a2a_send.py tests/test_a2a_inbox_bridge.py tests/test_a2a_reply_capture.py tests/test_a2a_domain_reply_artifact.py tests/test_a2a_send_board_adapter.py tests/test_control_surface.py tests/test_control_surface_ds_goal_cards.py tests/test_control_surface_a2a_cards.py tests/test_runtime_truth_projection_fields.py tests/test_operating_facts.py tests/test_runtime_truth_command_cutover.py`
  passed: 174 tests, 1 existing FastAPI/Starlette deprecation warning.
- Broader runtime/control-surface slice:
  `pytest -q tests/test_runtime_warrant.py tests/test_runtime_state.py tests/test_spine_mapping_receipts.py tests/test_runtime_truth_spine_v2_evidence.py tests/test_runtime_state_invariants.py tests/test_spine_persistence_invariant.py tests/test_autonomy_spine_cli.py tests/test_ds_goal_board_adapter.py tests/test_a2a_send.py tests/test_a2a_inbox_bridge.py tests/test_a2a_reply_capture.py tests/test_a2a_domain_reply_artifact.py tests/test_a2a_send_board_adapter.py tests/test_control_surface.py tests/test_control_surface_ds_goal_cards.py tests/test_control_surface_a2a_cards.py tests/test_runtime_truth_projection_fields.py tests/test_operating_facts.py tests/test_runtime_truth_command_cutover.py tests/test_agentops_board_adapter.py tests/test_spine_adoption_metric.py`
  passed: 218 tests, 1 existing FastAPI/Starlette deprecation warning.
- Evidence association slice:
  `pytest -q tests/test_a2a_send.py tests/test_autonomy_spine_cli.py`
  passed: 28 tests.
- `make onboard`: passed.
- `make docops-integrity`: passed, including hygiene integrity.
- `python3 scripts/governance/spine_bypass_report.py`: passed as warning-only
  report, 7 `.submit()` sites classified, 0 unknown.
- `python3 tools/spine_adoption_metric.py --output reports/governance/spine_adoption_metric.json`: passed.
- `git diff --check`: passed.
- `make agent-build-closeout`: advanced past hygiene audit, Semgrep, gitleaks,
  governance contract tests, NATS substrate contract/tests, and uplift guards,
  then failed the repo-level module-budget gate because
  `dharma_swarm/context_compiler.py`,
  `dharma_swarm/operator_core/living_agent_kernel.py`, and
  `dharma_swarm/operator_core/runtime_truth.py` exceed the 1000-line budget
  relative to `origin/main`. This is a branch-level merge blocker, not a
  RuntimeWarrant or EvidenceReceipt-association test failure.

#### Remaining Bypasses

| Bypass | Classification | Reason | Next PR slice |
|---|---|---|---|
| A2A inbox bridge runtime owner | ADAPTER_READY | bridge file receipt is useful but projection-only | choose bridge RuntimeState owner or explicitly keep projection-only |
| A2A domain reply semantic authority | AMBER | typed domain receipts are distinguished, but semantic reply still depends on payload claims | add source identity and schema validation for semantic reply claims |
| AgentOps reports without runtime refs | AMBER | now projects partial, not bound | require runtime refs in green report promotion path |
| AgentOps/ds-goal cards without runtime closeback | AMBER | local done now projects review, not complete | promote only when runtime or kernel refs exist |
| registered holon wake broad-tool proof | AMBER | not fully audited in this pass | focused test for registered wake tool scope and unknown-name fail-closed |
| Forge/Hydra runnable claims | RED | no fresh run receipt/verifier/artifact hash in this pass | run or quarantine; do not claim runnable |
| live trading authority | RED | requires operator/legal/exchange authority | explicit external warrant before any live path |
| revenue/external-human proof | AMBER | no active track or external receipt here | 72h external human served / first cash sprint |

#### Next Slice

The next narrow PR should move to the remaining non-joined side-effect
surfaces: AgentOps runtime refs, registered holon wake scope proof,
overnight/autopilot split, Forge/Hydra quarantine-or-proof, and cron/provider
rotator runtime wrapping. Keep bridge and dashboard surfaces projection-only
unless a single RuntimeState owner is selected.

---

## Section 3 — `reports/anatomy_altitude_2026-06-10/lane_B_truth.md` <a id="section-3-reports-anatomy-altitude-2026-06-10-lane-b-truth-md"></a>

> **Original path:** `reports/anatomy_altitude_2026-06-10/lane_B_truth.md`  
> **Source date:** 2026-06-12  
> **Author/Owner:** —  
> **Size:** 19,014 bytes  
> **sha256:** `4ac9eb6ddd69307a662b3a39270b4f523e83e0ef3cb32e68a83698695cc9a717`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Lane B (truth) of the 6-lane anatomy-altitude system x-ray: live spine vs declared spine, every claim cites file:line, clean negatives are first-class.

### Verbatim content

### Lane B — TRUTH FABRIC Deep Read
**Date:** 2026-06-10 · **Question:** how close is "the system cannot lie to itself or its operator" to being real?
**Method:** end-to-end reads of 12+ files across 6 worktrees; live SQLite verification against `~/.dharma/state/runtime.db`; `spine_bypass_report.py` executed live. Every claim cites file:line. Clean negatives are first-class.

---

#### Headline Answer

The truth fabric is **two systems wearing one name**, and only one of them is alive:

1. **The identity/ledger layer (ExecutionIdentity + RuntimeReceipt) RUNS.** `execution_identities` has **1,570 rows, latest written today 2026-06-10 13:44 UTC**; `runtime_receipts` has **583 rows (2026-06-01 → 2026-06-09)** with six production writer modules. This is real, persisting, queryable truth.
2. **The dispatch-evidence layer (EvidenceReceipt + invoke_agent) is WIRED-BUT-DORMANT.** The flag `DHARMA_SPINE_DISPATCH` is default-OFF and set nowhere persistent (verified: no hits in `~/.zshrc`, `~/.dharma/cron/`, `~/Library/LaunchAgents/`, Makefile, run_operator.sh). The receipt persistence sink `spine/persistence.py:persist_receipt` has **zero production callers**. Re-verified clean negative: **`delegation_runs.receipt_json` = 0 / 3,495 rows** (column exists, never written).

Provider honesty: on main, **8 of ~11 provider classes can still silently convert a reasoning-only model response into an empty string** — the system literally reporting "the model said nothing" when it said something. The Jun 10 `honest-spine-v2` WIP fixes 7 of them but is **uncommitted** and `providers_extended.py` is only partially converted.

Rough calibration: identity join-key ~70% real · runtime ledger ~50% real (selected paths only) · dispatch evidence ~15% real · provider honesty ~60% on main, ~85% if the WIP lands · substrate constitution = unmerged spec whose receipt mandate is enforced nowhere.

---

#### Tension 1 Resolved: SIX spine generations exist; main's `dharma_swarm/spine/` is canonical

| Gen | Location / branch | Date | Content | Fate |
|---|---|---|---|---|
| G1 "agent truth spine" | `~/dharma_swarm_truth_spine` (`chore/agent-truth-spine`) | May 5 | governance truth spine (commit `efeb0cabd`: INTERFACE_MISMATCH_MAP rewrite, mismatch_registry, BUILD_SESSION_ENTRYPOINT) + **command spine v0** (commit `fdd97f4bf`: `operator_core/command_spine.py`, 587 lines) | **Never merged.** `command_spine.py` absent from main's `operator_core/` (verified `ls`); only branches containing `fdd97f4bf` are this one + `cleanup/agent-truth-spine-salvage-2026-05-13`. Docs-layer ideas (BUILD_SESSION_ENTRYPOINT, mismatch registry) reached main via other PRs. |
| G2 substrate constitution | `~/dharma_swarm_substrate_spec` (`docs/swarm-substrate-spec-2026-05-20`) | May 20 | `docs/architecture/SWARM_SUBSTRATE.md` (833 lines, 7-layer architecture) | **Doc never merged** (file absent from main, no commit touches that path on main). But its Tranche 1 (BoardStore facade) **did ship separately**: `dharma_swarm/board/{facade,event_log,models}.py` exists on main; track `boardstore-facade-2026-05` closed SHIPPED. |
| G3 runtime-truth v1 | `~/worktrees/dharma_swarm_runtime_truth_spine_v1` (`codex/runtime-truth-spine-v1`) | Jun 1 | ExecutionIdentity + runtime ledger tables + TRCR-9999-ALPHA tracer | **Never committed** — work sits as uncommitted modifications + untracked `spine/identity.py` on a HEAD at #409 (`git status` shows ` M` ×6, `??` ×3). v2's report confirms: "Clean `HEAD` did not contain the v1 spine" (v2_report.md:16). |
| G4 runtime-truth v2 | `~/worktrees/dharma_swarm_runtime_truth_spine_v2` (`codex/runtime-truth-spine-v2`) | Jun 1 | v1 ported + adapters + receipt vocabulary + fail-closed InterruptGate; commit `2ea5a8e8f`, 4,477 insertions, 159 tests passing | **Merged to main.** `spine/identity.py` is byte-identical between v2 worktree and `~/dharma_swarm_live` (verified by `diff`). Main carries the v2 tables (`runtime_state.py:211/234/252`: `execution_identities`, `runtime_receipts`, `idempotency_records`). Track `runtime-truth-spine-2026-06` closed SHIPPED 2026-06-04. |
| G5 merged dispatch spine | `~/dharma_swarm_live/dharma_swarm/spine/` (`runtime/live` @ `dc72312f0`) | Jun 4–9 | `invoke.py` (55L), `receipt.py` (135L), `persistence.py` (57L), `routing.py` (35L), `tollbooth.py` (36L), `adapters.py` (327L), `identity.py` (191L) + WS3 flag in `orchestrator.py` (PR #557, merged Jun 9) | **CANONICAL.** This is the only spine that exists on main. |
| G6 honest spine v2 | `~/worktrees/dharma_swarm_honest_spine_v2` (`honest-spine-v2`) | Jun 10 | provider message-extraction honesty + pulse bare-mode skip | **WIP.** 1 commit (`c53f24adc`, pulse.py) + uncommitted diffs to `providers.py` (8 call sites), `providers_extended.py` (import only), `tests/test_providers_quality_track.py` (+86 lines). |

**Canonical = G5 (main's `spine/` package) + G4's ledger inside `runtime_state.py`.** G1's command spine and G2's spec doc are orphaned generations; G3 was absorbed into G4; G6 is in-flight.

---

#### Tension 2 Resolved: receipts persist — but only ONE of the two receipt systems

**Clean negative, re-verified 2026-06-10:**
```
sqlite3 ~/.dharma/state/runtime.db "SELECT COUNT(*), SUM(receipt_json IS NOT NULL) FROM delegation_runs"
→ 3495 | 0
```
The morning finding stands. The mechanism is now precisely located:

- `spine/persistence.py:50-57` (`persist_receipt`) and `:35-47` (`ensure_receipt_column`) have **zero callers outside the spine module and tests** (repo-wide grep over `dharma_swarm/`, `scripts/`, `api/`). The migration that created the `receipt_json` column ran at some point (column exists in live schema), but no production code path ever writes it.
- The WS3 dispatch path stores its EvidenceReceipt **in memory only**: `orchestrator.py:2232` `self._last_evidence_receipt = receipt` and `:2233` `td.metadata["evidence_receipt_id"] = str(receipt.receipt_id)`. Even with `DHARMA_SPINE_DISPATCH=1`, `receipt_json` would stay 0 — `persist_receipt` is never called from `_run_task_via_spine`.
- The flag itself is checked at exactly one site (`orchestrator.py:2286`) and is set in no persistent environment surface on this machine. **Flag-gated + flag-never-set = the dispatch evidence path has never run in production.**

**But the OTHER receipt system persists for real:**
```
runtime_receipts:        583 rows, 2026-06-01 → 2026-06-09
execution_identities:  1,570 rows, 2026-06-01 → 2026-06-10 13:44 UTC (today)
idempotency_records:       0 rows  (clean negative: idempotency substrate unexercised)
```
Receipt-type distribution: `delegation_run` (107 claimed / 75 failed / 41 running / 35 completed), `task_claim` (mirror counts), `artifact` + `artifact_written` (35 each). Writers on main, all live code: `runtime_lifecycle.py:265,347,454`, `message_bus.py:850`, `task_board.py:271`, `artifact_store.py:155`, `a2a/a2a_server.py:370`, `a2a/nats_transport.py:164,202,220,282`, `opportunity_refill.py:307`.

The Jun 9 tail of `runtime_receipts` is the **WS3 GATE 1 verification itself**: rows for `gate1-real-agent-α` (5) and `gate1-ctrl-agent` (10) at 14:37–14:38 UTC. So GATE 1's "receipt fires on real chokepoint" was proven against the *runtime ledger*, while the *EvidenceReceipt* produced by the same dispatch lived and died in process memory. The two receipt layers share correlation identity by doctrine (`receipt.py:90-96` exports `dharma.correlation_id` aliasing `trace_id`) but only one has a durable home.

**Identity propagation into the legacy table is thin:** `delegation_runs.trace_id` is non-empty in only **110 / 3,495 rows (3.1%)**. The join key exists; the old rows mostly don't carry it. (Side observation: 2,028 / 3,495 = 58% of all delegation runs ever recorded are `failed`.)

---

#### Tension 3 Resolved: what the substrate spec declares vs. what code does

`SWARM_SUBSTRATE.md` (read end-to-end, 833 lines) is a constitution that was **never ratified** — absent from main — yet partially obeyed:

- Declared (line 30-32): *"agents decompose it into typed work, claim visible cards, produce receipts, verify outcomes, and remain interruptible through one observable control plane."* — Receipts: partially real (runtime ledger, selected paths). Interruptibility: v2 flipped `InterruptGate` to fail-closed (`checkpoint.py:78,102` per v2_report.md:112).
- Declared (line 499): *"Completion requires at least one receipt or an explicit no-check reason."* — **Enforced nowhere.** Orchestrator completion path (`orchestrator.py:2333-2337`) writes `last_completed_at`/`last_result_chars` with no receipt requirement; honors-checkpoint gating exists (`:2304-2320`) but only for tasks carrying a completion contract.
- Declared (line 580-591): BoardStore facade over TaskBoard/OperatorBridge/RuntimeStateStore — **shipped** (`dharma_swarm/board/` on main).
- Declared (line 691-701): noticer forbidden actions incl. *"submitting directly to Darwin/evolution pipelines from notice-only mode"* — consistent with the WS4a/WS4b gate work but not implemented by this spec's machinery.
- The spec's self-assessment is honest: *"The missing layer is not capability. It is convergence"* (line 96-99). That diagnosis is still exactly right on Jun 10.

The doc's authority chain was superseded: the live constitution-equivalent is now `ACTIVE_TRACK.yaml` (2 active tracks: `runtime-truth-reconciliation-2026-06` + `runtime-truth-nats-2026-06`, both serving `substrate-nativeness`) plus the doctrine lines embedded in track definitions: *"Receipts may differ by closure layer. Correlation identity must not"* (v1/v2 worktree CLAUDE.md) and *"Read models project truth from owners; they do not become authority"* (live CLAUDE.md, reconciliation track).

---

#### Axis 1 — Working-code docks (verified live)

| Dock | Evidence | Status |
|---|---|---|
| `ExecutionIdentity` join-key | `spine/identity.py:29-52` — frozen dataclass, 6 required keys (`trace_id, correlation_id, task_id, run_id, claim_id, idempotency_key`), `require_for_dispatch()` fail-fast at `:146-156` | **RUNS** — 1,570 DB rows, written today |
| Runtime ledger | `runtime_state.py:211,234,252` (3 spine tables), `record_receipt_for_identity` at `:2398` | **RUNS** — 583 receipts, 6 organ writers |
| Identity adapters | `spine/adapters.py:155+` `identity_from_carrier` over 10 carrier shapes (a2a/task/dispatch/message/artifact/ontology/tool/checkpoint/proposal) | **RUNS** — adopted in 9 production modules (opportunity_dispatcher ×7, task_board ×6, message_bus ×5, artifact_store ×4, tool_registry, ontology, diff_applier, contracts/*) |
| Tollbooth | `spine/tollbooth.py:16-36` — fail-closed only when `require_identity=True` | RUNS where adopted; permissive by default |
| Runtime truth projector | `operator_core/runtime_truth.py:1-6` — *"opens runtime.db in SQLite read-only mode and projects what is already there"* | **RUNS** — merged; active track's read-model owner |
| Bypass accounting | `scripts/governance/spine_bypass_report.py` — executed live: **7 `.submit()` sites: 1 spine-adopted, 5 intentional-bypass allowlisted, 1 docstring** | **RUNS** — warning-only, does not fail CI |
| WS3 dispatch chokepoint | `orchestrator.py:2164-2236` `_run_task_via_spine` + flag check `:2286` | **WIRED-BUT-DORMANT** — flag default OFF, set nowhere |
| A2A spine submit | `a2a/a2a_bridge.py:78-205` `submit_via_spine` | **WIRED-BUT-DORMANT** — zero callers (grep: only its own definition + docstring references) |
| EvidenceReceipt persistence | `spine/persistence.py:50` | **ASPIRATION** — zero callers; 0/3,495 |
| Provider extraction honesty (main) | extractor `providers.py:154-163` (content → reasoning → reasoning_details fallback) used at 4 OpenAI-family sites (`:355,1024,1215,1289`); **`msg.content or ""` remains at `:1363,1437,1511,1585,1659,1733,1800`** (SiliconFlow, Together, Fireworks, GoogleAI, SambaNova, Mistral, Chutes) + NIM dict-path `:556` + `providers_extended.py:86,152,213` | **content-drop gap RUNS in production** |

#### Axis 2 — Vision docks (quoted)

- `spine/invoke.py:2,44-48`: *"invoke_agent — the one blessed agent invocation path. PR A: thin pass-through… PR B: A2A becomes the default invoker. PR C+: every router collapses onto this signature."* — We are at PR A, flag-off. PR B/C are roadmap text living inside the docstring.
- `spine/receipt.py:4-6`: *"OTel is an EXPORT ADAPTER, not the truth surface. The receipt itself is the canonical record."* — A canonical record that is never durably recorded (see Tension 2).
- `spine/persistence.py:8`: *"No new persistence surface — this writes to the existing canonical store."* — True in design, false in practice: it writes to nothing.
- v1/v2 track doctrine (worktree CLAUDE.md): *"Every dispatch produces exactly one receipt. No more generic dispatch_dropoff."* — `dispatch_dropoff` still exists on main (`orchestrator.py:2157` `source="dispatch_dropoff"`).
- v2 report's own bottom line (v2_report.md:247): *"The v2 branch does not claim the entire platform is canonical yet… 16 surfaces: Joined 5/16 (31.25%), joined-or-adapter-ready 9/16 (56.25%)."* — Unusually honest self-grading; matches what I found.
- `SWARM_SUBSTRATE.md:499`: *"Completion requires at least one receipt or an explicit no-check reason."* — the constitution's strongest truth clause; unenforced.
- WIP test header (`honest_spine_v2/tests/test_providers_quality_track.py:+795`): *"Reasoning-only or list-typed message content must never collapse to ''. Fixed in Honest Spine v2 Phase 0; previously only OpenAIProvider was routed through _extract_openai_compatible_message_text."*

#### Axis 3 — Anatomy: organ / surface / spine

- **Spine (skeleton):** `ExecutionIdentity` is the vertebra; it is the only artifact shared by all six generations and the only one with live production writes today. The v2 design choice — *"dependency-light so runtime producers can import it without creating circular ownership"* (`identity.py:4-6`) — is why it survived merge while everything heavier stalled.
- **Organs:** runtime_lifecycle (delegation/claim/artifact receipts), message_bus (consumption receipts + idempotency gate), task_board, artifact_store, a2a_server, nats_transport — each writes receipts through `record_receipt_for_identity`, i.e., the organs joined the ledger without local rewrites, exactly as `adapters.py:3-6` intended.
- **Surfaces:** two declared truth surfaces — (a) the runtime ledger (authority), (b) `operator_core/runtime_truth.py` packets (read-only projection). The doctrine separating them (*"Read models project truth from owners"*) is structurally respected: the projector opens the DB read-only and refuses to migrate (`runtime_truth.py:3-5`).
- **Vestigial organs:** `command_spine.py` (G1, 587 lines, unmerged), `SWARM_SUBSTRATE.md` (G2, unmerged), v1 worktree's uncommitted spine (G3, superseded), `submit_via_spine` (G5, callerless). Four of six generations left organs that nothing circulates blood through.

#### Axis 4 — Ecosystem position

- Two ACTIVE tracks own the fabric: `runtime-truth-reconciliation-2026-06` (operator; owns `operator_core/**`, `runtime_state.py`) and `runtime-truth-nats-2026-06` (codex; owns NATS transport contacts). Surface separation is the declared safety boundary. `runtime-truth-spine-2026-06` closed SHIPPED 2026-06-04.
- The live CLAUDE.md still says *"Substrate-nativeness is currently estimated at ~10–15%"* (live CLAUDE.md, "CRITICAL" section) while the 2026-06-09 ground-truth pass measured 81.2% for the runtime spine specifically — a stale doctrine number sitting in the first-read file. The spine-vs-spine confusion documented in project memory is reproduced inside the repo's own onboarding doc.
- Cross-worktree drift is the live hazard: the canonical spine exists in 1 of 6 generations; agents landing in the wrong worktree (e.g., v1, where the spine is uncommitted) would read a different truth. G6 (honest-spine-v2) is based on current main, which is the correct pattern.
- The bypass report's allowlist (5 intentional `.submit()` bypasses, all in `a2a/`) is the honest migration ledger for "PR B" — but it is warning-only and not wired to fail CI.

#### Axis 5 — Grading summary (RUNS / WIRED-BUT-DORMANT / ASPIRATION)

| Component | Grade |
|---|---|
| ExecutionIdentity + `execution_identities` table | **RUNS** (writes today) |
| RuntimeReceipt ledger (`runtime_receipts`, 6 writers) | **RUNS** (583 rows; selected paths only) |
| Identity adapters in 9 organ modules | **RUNS** |
| runtime_truth read-only projector | **RUNS** |
| spine_bypass_report accounting | **RUNS** (warning-only) |
| BoardStore facade (`board/`) | RUNS (not load-tested in this lane) |
| InterruptGate fail-closed default | RUNS (merged via v2) |
| WS3 `_run_task_via_spine` + EvidenceReceipt emission | **WIRED-BUT-DORMANT** (flag OFF everywhere) |
| `a2a_bridge.submit_via_spine` | **WIRED-BUT-DORMANT** (0 callers) |
| RoutingDecision | WIRED-BUT-DORMANT (constructed only at the 2 dormant sites) |
| `persist_receipt` / `delegation_runs.receipt_json` | **ASPIRATION** (0 callers; 0/3,495) |
| `idempotency_records` | ASPIRATION at runtime (0 rows; helpers exist + tested) |
| Provider extraction honesty across all providers | **ASPIRATION on main** (8 classes drop reasoning-only content); WIP G6 fixes 7, uncommitted; `providers_extended.py:86,152,213` still unconverted even in WIP |
| invoke_agent as "the only invocation path" (PR B/C) | ASPIRATION (1 of 7 submit sites adopted) |
| `SWARM_SUBSTRATE.md` Layer-6 receipt mandate | ASPIRATION (doc unmerged, clause unenforced) |
| command spine v0 (G1) | ASPIRATION/orphaned (never merged) |

---

#### What would most move "cannot lie to itself" toward real (evidence-ranked)

1. **One call:** invoke `persist_receipt(receipt, db)` from `orchestrator.py:2232` and `submit_via_spine` — turns the canonical record from in-memory to durable. The sink, schema, and column already exist.
2. **Land G6:** commit the honest-spine-v2 provider diff and finish `providers_extended.py:86,152,213` — closes the only path by which the system actively misreports model output today.
3. **Set the flag somewhere real** (daemon env or launchd) after GATE review — the dispatch evidence path has literally never run outside tests.
4. **Fix the stale 10–15% line in live CLAUDE.md** — the truth fabric's own onboarding doc carries a falsified number on the fabric itself.
5. **Decide the fate of orphan generations** (G1 command spine, G2 spec doc): merge as depth-on-demand docs or compost — six generations is itself a legibility cost.

*Files read end-to-end: spine/{invoke,receipt,identity,persistence,routing,tollbooth,adapters}.py (live), orchestrator.py:2140-2340, a2a_bridge.py:60-220, runtime_truth.py header, SWARM_SUBSTRATE.md (833L), runtime_truth_spine_v1_report.md (169L), runtime_truth_spine_v2_report.md (247L), honest_spine_v2 full diffs + pulse commit, providers.py extraction sites both branches.*

---

## Section 4 — `docs/sovereign_holons/STATE_OF_TRUTH.md` <a id="section-4-docs-sovereign-holons-state-of-truth-md"></a>

> **Original path:** `docs/sovereign_holons/STATE_OF_TRUTH.md`  
> **Source date:** 2026-06-13  
> **Author/Owner:** opus_composer  
> **Size:** 6,583 bytes  
> **sha256:** `0d1ce43970046846fd2ad92efbb432dd471bac8e41d16a9d2366ee5f3a0cd844`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Reality-vs-intention state-of-truth for sovereign_holons (the one place that records what is wired and what is not).

### Verbatim content

### STATE OF TRUTH — Docs vs. Code vs. Wired

**Written:** 2026-06-08 (evening) · **Author:** opus_composer, by reading the actual source, not the docs
**Why this file exists:** Everything else in this folder describes what we *intend* to build. This file
is the one place that separates **what the docs promise** from **what the code already does** from
**what is actually wired up and runs**. It was written by reading the functions line-by-line with a
hostile verifier, because narration has outrun the build before.

---

#### The one-paragraph truth

We are building a **sovereign holon**: taking a *registered persistent agent* (an identity on disk —
name, soul, memory, authority, banks) and giving it a path to **actually run as itself, under its own
gate and authority**, while still being a governed cell of the swarm. The **design is fully written
and now consolidated in this folder.** The **runtime is mostly not built.** Of the six pieces the design
calls "organs," **one is genuinely wired and working** (the model/provider door), **two exist but don't
enforce** (the gate fails open; the authority policy is never read at run time), **two exist only as
inert data** (the registry returns a dict nobody runs; only 5 hardcoded preset agents are reachable, not
the 15+ registered ones), and **the central piece — the bridge from a registration record to a running,
gated agent — does not exist at all.** Tonight's `talk_sl.py` spike proved you can *talk* to an agent by
feeding its identity as a prompt, but that path bypasses the gate, the authority limits, and the banks —
so it is the cheap shell, not the governed bridge.

---

#### The map (verified 2026-06-08 against `/Users/dhyana/dharma_swarm/dharma_swarm/`)

| # | Organ | What the DOCS say | What the CODE actually is (file:line) | Wired & running? |
|---|-------|-------------------|----------------------------------------|------------------|
| 1 | **Agent registry** | "Load a registered agent and run it" | `agent_registry.py:329` `load_agent()` returns a **plain dict**. Callers (`agent_runner.py:2502/2632/3276`) use it for **metrics/logging only**. No path turns the dict into a running agent. | ❌ Data only — read, never run |
| 2 | **Wake loop + gate** | "Each cycle is telos-gated; unsafe actions blocked" | `persistent_agent.py:425` `_check_gate()` → **fail-open**: any exception `return None` (line ~442), and the caller treats `None` as "proceed." Gate is **advisory**, not mandatory. | ⚠️ Exists, **fails open** |
| 3 | **Reasoning brain** | "Any registered agent wakes with its own identity" | `autonomous_agent.py:1457` `PRESET_AGENTS` = **5 hardcoded** (researcher, coder, scout, reviewer, witness). A registered name like `strategy_librarian` falls through to a **generic stub identity** (`autonomous_agent.py:~1563`). The 15+ registered selves are **not reachable**. | ⚠️ Real for 5 presets, **not** for registered agents |
| 4 | **Authority / autonomy policy** | "A registered agent may only do what its policy allows" | `external_agent_registration.py:136` `AutonomyPolicy` is **validated at registration** (refuses dangerous flags) but its **own docstring says it is not read back at runtime**. Grep confirms: **zero** runtime reads of `autonomy_policy.can_*`. | ❌ Metadata only — never enforced on a running agent |
| 5 | **Model / provider door** | "Free-first model routing, live fallback" | `runtime_provider.py:158/434` `resolve_runtime_provider_config()` / `create_runtime_provider()` are **actually called** by the run path (`autonomous_agent.py:1584`, `thinkodynamic_director.py`, `consolidation.py`). | ✅ **Genuinely wired** — the one real organ |
| 6 | **THE BRIDGE** (record → running gated agent) | "First brick: turn `merge_master_mike`'s record into a running, gated holon" | **Absent.** No `SovereignBridge`, no `record_to_runtime()`, no `dgc agent run-registered`. `dgc agent` exposes only `wake`/`list`/`runs`, all **preset-only** (`dgc_cli.py:590-600`). | ❌ **Does not exist** |

Legend: ✅ wired & enforcing · ⚠️ exists but weak/partial · ❌ doc-only or absent.

**Score: 1 of 6 real-and-wired · 2 exist-but-don't-enforce · 2 inert data · 1 absent.**

---

#### What this means for the build (step zero the plan currently skips)

The reconciled plan (`05_RECONCILED_PLAN.md`) is right about *what* to build, but it assumes a clean
single codebase. Two facts found by hand on 2026-06-08 change the first step:

1. **`living_agent_kernel.py` — the governance organ the "governed bridge" depends on — is NOT in the
   main repo at all.** It lives only in `dharma_capital_lab/` and `dharma_swarm_lak_e2e/` (both checkouts
   of the same GitHub repo), and those two copies have **drifted** from each other.
2. **The literal first-brick file, `external_agent_registration.py`, is forked**: 510 lines in
   `dharma_swarm/` vs. 527 in `dharma_capital_lab/`. ~40 top-level checkouts of the same repo exist.

So **step zero is "pick the canonical runtime and get `living_agent_kernel` into it"** — before writing
the bridge, decide which of the ~40 copies is the source of truth. The plan jumps straight to step one.

---

#### The honest build sequence (corrected)

0. **Decide the canonical runtime worktree** and pull `living_agent_kernel` + reconcile the 510/527
   `external_agent_registration` fork into it. *(Not in the current plan — add it.)*
1. Write the **bridge**: a function/CLI (`dgc agent run-registered <name>`) that loads a registration
   record, resolves its provider (organ 5 ✅ already works), builds a `PersistentAgent` with the
   record's real identity, and starts its wake loop. *(Organ 6 — the absent piece.)*
2. **Make the gate mandatory**: remove the fail-open `except → return None` in `_check_gate` (organ 2).
3. **Enforce `autonomy_policy` at runtime**: read `can_*` before the agent acts (organ 4).
4. Make registered agents reachable (organ 3) — load identity from the registry, not `PRESET_AGENTS`.
5. Prove it on **`merge_master_mike` first**, then the richer Perplexity/seed shape.

When all five are done, organs 1–6 go green and the holon is real — not narrated.

---

#### Provenance of this file

Every claim above was verified by reading source on 2026-06-08 via gitnexus + contextplus + direct read.
The gate fail-open and the `autonomy_policy`-never-read findings are the two load-bearing ones; both were
confirmed by quoting the exact code. If you change any of these files, re-verify and update this table —
this is the file that must never be allowed to drift from the code.

---

## Section 5 — `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md` <a id="section-5-docs-governance-runtime-truth-command-cutover-md"></a>

> **Original path:** `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md`  
> **Source date:** 2026-06-13  
> **Author/Owner:** —  
> **Size:** 9,273 bytes  
> **sha256:** `d640298c1806c0391b50427b3c29c240b75282fc723c78e1e96190137859ec8b`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Active enforcement map for the runtime-truth command cutover (records command cutover state for live operator-facing surfaces).

### Verbatim content

### RUNTIME TRUTH COMMAND CUTOVER

Status: active enforcement map, not a new spine.

This document records the command cutover state for live operator-facing
surfaces. It does not create a new command lifecycle substrate.

#### Canonical Substrate

The existing Runtime Truth Spine is the authority:

- `dharma_swarm/spine/identity.py`: `ExecutionIdentity`
- `dharma_swarm/spine/receipt.py`: dispatch `EvidenceReceipt`
- `dharma_swarm/spine/invoke.py`: blessed `invoke_agent` path
- `dharma_swarm/spine/tollbooth.py`: fail-closed gate
- `dharma_swarm/spine/warrant.py`: pre-side-effect `RuntimeWarrant`
- `dharma_swarm/runtime_state.py`: `RuntimeStateStore`, `RuntimeReceipt`,
  and idempotency records

Do not add `WorkCommand`, `WorkRun`, `WorkReceipt`, `command_runs`,
`work_runs`, or a second command ledger.

#### Proof Types

| Proof | Owner | Meaning |
|---|---|---|
| `ExecutionIdentity` | `dharma_swarm/spine/identity.py` | Correlation join key for one durable unit of work |
| `RuntimeWarrant` | `dharma_swarm/spine/warrant.py` | Permission receipt required before selected side effects |
| `EvidenceReceipt` | `dharma_swarm/spine/receipt.py` | In-flight dispatch proof |
| `RuntimeReceipt` | `dharma_swarm/runtime_state.py` | Persisted runtime proof |
| `IdempotencyRecord` | `dharma_swarm/runtime_state.py` | Exactly-once side-effect claim |
| `receipt_json` | runtime projection/cache | Query convenience, not source of truth |
| file reports | local projection | Useful evidence, not authority unless named as owner |
| dashboard cards | projection | Operator view, never completion authority |
| onboard rows | projection | First-screen synthesis, not a truth owner |

`RuntimeWarrant` is distinct from the Fourfold Action Warrant. Fourfold is a
read-only governance review for proposed significant actions. RuntimeWarrant is
a persisted, pre-side-effect permission receipt for selected runtime commands.
They may reference the same operator intent later, but they must not share a
state table or substitute for each other.

#### Status Labels

- JOINED: default path writes identity, idempotency, and runtime proof through
  the existing spine or RuntimeStateStore.
- ADAPTER_READY: projection or adapter can read receipts, but default path is
  not fully joined.
- OPT_IN_ONLY: safe path exists only behind a flag or explicit command.
- LEGACY: works but bypasses spine identity or runtime receipts.
- QUARANTINE: should not be used until owner proof exists.
- AMBER: plausible, useful, but missing a required proof edge.
- RED: contradicted, forged, unsafe, or overclaimed.

#### Command-Surface Matrix

| Surface | Default or opt-in path | ExecutionIdentity | RuntimeWarrant | EvidenceReceipt | RuntimeReceipt | Idempotency before side effect | UI separates sent/delivered/domain/semantic/completed | State | Next receipt required |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `ds-goal` (`scripts/runtime/autonomy_spine.py`) | default CLI path | yes | yes, before kernel wake dispatch | yes, associated inside existing command `RuntimeReceipt` payload | yes | yes, before kernel wake dispatch | cards project mission/task/runtime refs | JOINED | broaden warrant/evidence association to next side-effect surface |
| A2A direct send (`scripts/runtime/a2a_send.py`) | default direct NATS command | yes | yes, before publish | yes, associated inside existing command `RuntimeReceipt` payload | yes | yes, before publish | receipt and card split publish, handler ack, reply, domain receipt | JOINED | keep no-double-write invariant; broaden to bridge/runtime owner only if selected |
| A2A inbox bridge | default bridge receipt path | partial | no | no | file receipt projection | not proven at bridge boundary | card now treats delivery ack as review, not done | ADAPTER_READY | bridge-owned runtime receipt or explicit owner decision |
| A2A reply capture | default capture verifier | partial | no | no | file receipt projection | not applicable to capture-only read | untyped payload is non-semantic; mismatch is RED | ADAPTER_READY | typed domain receipt or semantic reply schema with source identity |
| A2A domain-reply artifact | explicit artifact helper | partial | no | no | author receipt projection | not proven | card distinguishes artifact publish from completion | ADAPTER_READY | target-owned domain receipt consumed by reply capture |
| AgentOps work packets | default governance path | partial | no | no | file report projection | packet-dependent | green gates without runtime refs project partial | AMBER | AgentOps report with trace, receipt, or identity refs |
| registered holon wake | explicit registered wake path | partial | unknown | no | kernel/runtime receipts where wired | partially proven | status views must not grant broad tools | AMBER | focused test: unknown holon fail-closed and registered wake tool scope |
| dashboard/control-surface cards | projection only | no | no | no | no, reads receipts | no side effects | now avoids handler-ack-as-done for A2A | ADAPTER_READY | card status tests for every evidence tier |
| overnight/autopilot command surfaces | explicit scripts | mixed | unknown | unknown | mixed | unknown | not all projected | AMBER | per-script cutover packet or quarantine list |
| Forge/Hydra command surfaces | unclear in this checkout | unknown | unknown | unknown | unknown | unknown | not projected as runnable | RED | fresh run receipt, command path, verifier, and artifact hashes |
| cron/provider rotator surfaces | external/local cron | unknown | unknown | no | external logs only | unknown | not projected as complete | LEGACY | runtime wrapper or explicit external-gated classification |

#### Default-Path Cutover Metric

This metric counts command surfaces by default-path enforcement, not by adapter
readiness:

| Class | Count | Surfaces |
|---|---:|---|
| default path has RuntimeStateStore idempotency before side effect | 2 | `ds-goal`, A2A direct send |
| default path has RuntimeWarrant before side effect | 2 | `ds-goal`, A2A direct send |
| default path has persisted RuntimeReceipt | 2 | `ds-goal`, A2A direct send |
| default path has direct `EvidenceReceipt` association | 2 | `ds-goal`, A2A direct send |
| projection/card only | 4 | A2A bridge, reply capture, domain reply, dashboard/control cards |
| AMBER or RED bypass needing next slice | 5 | AgentOps refs, holon wake, overnight/autopilot, Forge/Hydra, cron/rotator |

`EvidenceReceipt` association here means the command builds a
`dharma_swarm.spine.receipt.EvidenceReceipt` and embeds its JSON plus compact
ref inside the existing command `RuntimeReceipt` payload. It intentionally does
not write a second `dispatch_evidence` `RuntimeReceipt` row.

#### Runtime Warrant Criteria

The current RuntimeWarrant gate is intentionally narrow and fail-closed:

1. the `(surface, action)` pair must be explicitly registered;
2. requested claim names are normalized before policy checks;
3. a non-empty requested claim boundary is required;
4. RuntimeStateStore idempotency must be claimed before the side effect;
5. the idempotency row must actually exist and match `run_id`, `task_id`,
   `trace_id`, `correlation_id`, and `status=started`;
6. requested claims must be in the surface/action allowlist and must not be a
   prohibited pre-action claim such as `completed`, `live_contact`,
   `semantic_reply`, `revenue_live`, or `live_trading`;
7. denied warrants persist a blocked `runtime_warrant` receipt when an
   execution identity exists.

#### Evidence Semantics

A2A evidence is layered:

1. sent: command attempted publish;
2. publish accepted: broker accepted the packet;
3. delivered: handler or bridge saw it;
4. domain receipt: typed domain receipt exists;
5. semantic reply: typed payload claims peer/model processing;
6. completed: task or runtime owner records work completion.

No lower layer implies a higher layer.

#### Remaining Bypass Classification

| Bypass | Classification | Why | Next move |
|---|---|---|---|
| A2A bridge receipts are file projections | ADAPTER_READY | useful receipt files, not persisted runtime owner | choose bridge owner or keep projection-only |
| AgentOps green reports without runtime refs | AMBER | gates prove local checks, not runtime binding | require trace/receipt refs for bound state |
| registered holon wake | AMBER | registered wake path exists, but fail-closed scope needs fresh focused proof | test unknown holon fail-closed and registered wake tool scope |
| overnight/autopilot command surfaces | AMBER | broad bucket mixes scripts with different side-effect risk | split per script and cut over or quarantine individually |
| Forge/Hydra runnable claims | RED | no fresh run receipt in this pass | run or stop claiming runnable |
| cron/provider rotator surfaces | AMBER | side-effecting external paths still rely on external logs and cron context | runtime wrapper or explicit external-gated classification |

#### External Authority Guardrails

| Claim | Classification | Why | Next move |
|---|---|---|---|
| live trading authority | RED | external/legal authority absent | explicit human/legal warrant before any live path |
| revenue/external-human proof | AMBER | active runtime tracks do not cover it | 72h external proof sprint with payment/reply/artifact receipts |

---

## Section 6 — `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md` <a id="section-6-reports-governance-runtime-truth-spine-v2-subagent2-v1-verification-md"></a>

> **Original path:** `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md`  
> **Source date:** 2026-06-06  
> **Author/Owner:** Dhyana (V1 Verification Agent)  
> **Size:** 6,838 bytes  
> **sha256:** `b8a0f52562c1f9d1d2098c0bbb7a5b0d73070979bc3a430a5506f2b3c41274d5`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Spine v2 subagent-2 verification: clean-HEAD v1 claim falsified; verified against worktree /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 @ 2737b26d.

### Verbatim content

### Runtime Truth Spine v2 - Subagent 2 V1 Verification

Role: V1 Verification Agent

Worktree: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2`

HEAD: `2737b26d7ed8dbee9c828ba64d5a6c9ec128b859`

#### Verdict

Clean HEAD at `2737b26d` does not contain the v1 Runtime Truth Spine implementation. The current v2 working tree does contain the v1 candidate implementation, but it is dirty: seven implementation files are staged, while `dharma_swarm/spine/identity.py` and `tests/test_runtime_truth_spine_v1.py` are untracked.

Therefore:

- Clean-HEAD claim status: falsified.
- Dirty v2 working-tree candidate status: verified by focused and adjacent tests.

#### Exact Commands And Results

```bash
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 rev-parse HEAD
```

Result: `2737b26d7ed8dbee9c828ba64d5a6c9ec128b859`

```bash
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 status --short --branch
```

Initial result: `## codex/runtime-truth-spine-v2...origin/main`

Later exact porcelain result after inspecting the working tree:

```text
M  dharma_swarm/a2a/a2a_server.py
M  dharma_swarm/a2a/node_gateway.py
M  dharma_swarm/message_bus.py
M  dharma_swarm/orchestrator.py
M  dharma_swarm/runtime_lifecycle.py
M  dharma_swarm/runtime_state.py
M  dharma_swarm/spine/__init__.py
?? dharma_swarm/spine/identity.py
?? tests/test_runtime_truth_spine_v1.py
?? reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md
```

```bash
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 grep -n "ExecutionIdentity\|MissingExecutionIdentity\|get_run_ledger\|runtime_receipts\|idempotency_records\|try_begin_idempotent_side_effect\|TRCR-9999-ALPHA\|trcr-9999-alpha\|external_a2a_task_id" HEAD -- dharma_swarm tests
```

Result: no matches, exit code 1.

```bash
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 ls-tree -r --name-only HEAD | rg "^(dharma_swarm/spine/identity.py|tests/test_runtime_truth_spine_v1.py)$"
```

Result: no matches, exit code 1.

```bash
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 ls-files --error-unmatch dharma_swarm/spine/identity.py
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 ls-files --error-unmatch tests/test_runtime_truth_spine_v1.py
```

Result: both fail with `pathspec ... did not match any file(s) known to git`.

```bash
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 diff --cached --stat
```

Result:

```text
dharma_swarm/a2a/a2a_server.py    |  97 ++++++
dharma_swarm/a2a/node_gateway.py  |  33 +-
dharma_swarm/message_bus.py       |  79 ++++-
dharma_swarm/orchestrator.py      |  39 ++-
dharma_swarm/runtime_lifecycle.py | 219 +++++++++++-
dharma_swarm/runtime_state.py     | 715 +++++++++++++++++++++++++++++++++++++-
dharma_swarm/spine/__init__.py    |   8 +
7 files changed, 1161 insertions(+), 29 deletions(-)
```

```bash
env HOME=/private/tmp/dharma_spine_v2_verify_home python -m compileall -q dharma_swarm/spine/identity.py dharma_swarm/runtime_state.py dharma_swarm/runtime_lifecycle.py dharma_swarm/a2a/a2a_server.py dharma_swarm/a2a/node_gateway.py dharma_swarm/message_bus.py dharma_swarm/orchestrator.py
```

Result: passed, exit code 0.

```bash
env HOME=/private/tmp/dharma_spine_v2_verify_home pytest -q tests/test_runtime_truth_spine_v1.py
```

Result: `4 passed, 1 warning in 0.95s`.

```bash
env HOME=/private/tmp/dharma_spine_v2_verify_home pytest -q tests/test_runtime_truth_spine_v1.py tests/test_runtime_state.py tests/test_runtime_lifecycle.py tests/test_a2a_spec_conformance.py tests/test_message_bus.py tests/test_orchestrator.py
```

Result: `133 passed, 2 warnings in 11.62s`.

```bash
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 diff --cached --check
git -C /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 diff --check
```

Result: both passed, exit code 0.

#### Working-Tree Candidate Evidence

The current dirty v2 working tree contains:

- `dharma_swarm/spine/identity.py`: defines `ExecutionIdentity`, `MissingExecutionIdentity`, and `require_execution_identity`.
- `dharma_swarm/runtime_state.py`: adds `execution_identities`, `runtime_receipts`, `idempotency_records`, artifact `trace_id`, `record_execution_identity*`, `record_runtime_receipt*`, `try_begin_idempotent_side_effect*`, `complete_idempotent_side_effect*`, `was_side_effect_performed`, `list_child_runs`, `describe_run`, and `get_run_ledger`.
- `dharma_swarm/runtime_lifecycle.py`: adds `ensure_execution_identity`, `require_identity` controls, task-claim/delegation/artifact receipts, and artifact `trace_id` propagation.
- `dharma_swarm/a2a/a2a_server.py`: adds RuntimeStateStore-backed A2A identity mapping and idempotency before handler dispatch.
- `dharma_swarm/message_bus.py`: adds optional RuntimeStateStore-backed idempotency before event insertion.
- `tests/test_runtime_truth_spine_v1.py`: proves missing identity failure, TRCR-9999-ALPHA run reconstruction, A2A external/internal mapping, artifact run_id/trace_id, and duplicate idempotency suppression.

#### V1 Claim Status

| Claim | Clean HEAD 2737b26d | Dirty v2 working-tree candidate |
|---|---|---|
| `ExecutionIdentity` exists | falsified | verified |
| `RuntimeStateStore` has receipt tables/APIs | falsified | verified |
| `RuntimeStateStore` has idempotency APIs | falsified | verified |
| `get_run_ledger(run_id)` exists | falsified | verified |
| TRCR-9999-ALPHA tests exist | falsified | verified |
| A2A maps external task ID to internal run/task/trace/correlation | falsified | verified by test |
| Artifacts carry `run_id` and `trace_id` in selected path | falsified | verified by test and SQL assertion |
| Duplicate idempotency key gates before side effect | falsified | verified by A2A side-effect count and MessageBus event count |

#### Corrections Required

1. Decide whether Subagent 2 should treat staged/untracked v2 working-tree changes as the implementation candidate. If yes, add the untracked `dharma_swarm/spine/identity.py` and `tests/test_runtime_truth_spine_v1.py` to the candidate patch; without them the staged code imports an untracked module and the proof test is not tracked.

2. Do not claim the v1 spine exists on clean `HEAD 2737b26d`. It exists only in the current dirty v2 working tree at this verification point.

3. Preserve the passing isolated test command using `HOME=/private/tmp/dharma_spine_v2_verify_home` or another explicit isolated home/state dir. This avoids accidental contention with developer-local `~/.dharma` runtime state.

4. If the synthesis wants clean-main evidence, commit or otherwise materialize the candidate files on the v2 branch, then rerun the same commands against the new commit and replace the current dirty-working-tree evidence level with tracked-source/test-backed evidence.

---

## Section 7 — `reports/governance/runtime_truth_spine_v2_report.md` <a id="section-7-reports-governance-runtime-truth-spine-v2-report-md"></a>

> **Original path:** `reports/governance/runtime_truth_spine_v2_report.md`  
> **Source date:** 2026-06-06  
> **Author/Owner:** Dhyana (Codex)  
> **Size:** 11,531 bytes  
> **sha256:** `e07ca1ec928e86606e5e94072ccc4f41047259928bde9389aae29fed63ef5c54`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Spine v2 report: v1 claim corrected, built from a clean worktree at current origin/main not from the dirty developer checkout.

### Verbatim content

### Runtime Truth Spine v2 Report

#### Executive Summary

Runtime Truth Spine v2 was built from a clean worktree at current `origin/main`, not from the dirty developer checkout.

- Worktree: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2`
- Branch: `codex/runtime-truth-spine-v2`
- Base SHA: `2737b26d7ed8dbee9c828ba64d5a6c9ec128b859`
- Base commit: `feat(governance): schema-alignment gate (KARMA) + typed-proposal envelope [Stage-1 additive, post-OMS] (#408)`
- Tracked files at base: 2737
- External systems: no live Palantir, NATS, Temporal, or paid LLM calls were made.

The v1 claim was independently verified and corrected:

- Clean `HEAD` did not contain the v1 spine. Static checks found no `ExecutionIdentity`, `runtime_receipts`, idempotency ledger table, or `TRCR-9999-ALPHA` tracer.
- The v1 spine was ported into this clean v2 branch from the v1 worktree, then verified with tests.
- v2 broadens the spine with compatibility adapters, receipt vocabulary and helpers, fail-closed human interrupt behavior, a gated free-text result path, surface coverage tests, and evidence documentation.

Final verification:

- `159 passed, 2 warnings in 11.99s`
- `python -m compileall` passed on the changed runtime modules.
- `git diff --check` passed before the final report was written.

#### Six-Subagent Build

Exactly six bounded subagents were spawned and all completed before synthesis.

1. Surface Inventory Agent, Poincare, `019e830f-d1bf-7791-9c7f-9c361f2927c7`
   - Mapped ingress, dispatch, event, artifact, tool, ontology, graph, and self-mod surfaces.
   - Classified each as joined, adapter-ready, quarantine/transitional, or missing.

2. V1 Verification Agent, Halley, `019e830f-e9fd-7ea3-bef9-f070c27de852`
   - Falsified v1 presence on clean `HEAD`.
   - Verified the ported v1 candidate with focused and adjacent test suites.
   - Wrote `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md`.

3. Organ Adapter Agent, Sagan, `019e830f-fd39-7db0-be92-84621d5c0ea9`
   - Added spine adapter helpers in `dharma_swarm/spine/adapters.py`.
   - Covered A2A tasks, TaskBoard tasks, Orchestrator dispatch, MessageBus/event payloads, artifact records, tool calls, ontology action payloads, graph/checkpoint payloads, and self-mod/proposal payloads.

4. Receipt Saturation Agent, Archimedes, `019e8310-1662-70b2-9809-bdecb8ae17f1`
   - Added receipt vocabulary and RuntimeStateStore helper APIs.
   - Added durable receipt support for side-effect intent/completion, artifact writes, message consumption, idempotency consumption, ontology action receipts, child run receipts, and self-mod receipts.

5. Bypass/Tollbooth Agent, Huygens, `019e8310-35db-73c3-90bb-2369debda844`
   - Changed `InterruptGate` to fail closed by default.
   - Gated Orchestrator free-text file writes behind explicit structured metadata.
   - Queued C2 ontology enforcement for the next slice instead of overmixing it into this runtime spine build.

6. Tracer/Evidence Captain, Peirce, `019e8310-563d-7ed2-b86d-cbbd9b041897`
   - Added v2 evidence tests and surface matrix.
   - Verified tracer reconstruction, missing identity failures, idempotency before side effects, and artifact identity fields.
   - Wrote `reports/governance/runtime_truth_spine_v2_evidence_plan.md`.

#### Changed Files

Runtime spine and adapters:

- `dharma_swarm/spine/identity.py`
- `dharma_swarm/spine/adapters.py`
- `dharma_swarm/spine/__init__.py`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/runtime_lifecycle.py`

Ingress, dispatch, events, artifacts, and tollbooths:

- `dharma_swarm/a2a/a2a_server.py`
- `dharma_swarm/a2a/node_gateway.py`
- `dharma_swarm/message_bus.py`
- `dharma_swarm/orchestrator.py`
- `dharma_swarm/checkpoint.py`

Tests and evidence:

- `tests/test_runtime_truth_spine_v1.py`
- `tests/test_runtime_truth_spine_v2_adapters.py`
- `tests/test_runtime_truth_spine_v2_evidence.py`
- `tests/test_runtime_truth_spine_v2_tollbooth.py`
- `tests/test_runtime_state.py`
- `tests/test_runtime_lifecycle.py`
- `tests/test_checkpoint.py`
- `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md`
- `reports/governance/runtime_truth_spine_v2_evidence_plan.md`
- `reports/governance/runtime_truth_spine_v2_report.md`

#### Main Implementation Points

Canonical identity:

- `ExecutionIdentity` is defined in `dharma_swarm/spine/identity.py:29`.
- `RuntimeLifecycle.ensure_execution_identity` enforces identity creation and persistence for selected runtime paths in `dharma_swarm/runtime_lifecycle.py:76`.

Compatibility adapters:

- `identity_from_carrier` in `dharma_swarm/spine/adapters.py:155`
- `adapt_execution_identity` in `dharma_swarm/spine/adapters.py:276`
- `runtime_receipt_kwargs` in `dharma_swarm/spine/adapters.py:303`

Durable ledger and receipts:

- Runtime receipt vocabulary starts at `dharma_swarm/runtime_state.py:308`.
- Side-effect intent/completion helpers start at `dharma_swarm/runtime_state.py:2229`.
- Message consumption helper starts at `dharma_swarm/runtime_state.py:2299`.
- Ontology action receipt helper starts at `dharma_swarm/runtime_state.py:2314`.
- Self-mod receipt helper starts at `dharma_swarm/runtime_state.py:2364`.
- Run ledger reconstruction starts at `dharma_swarm/runtime_state.py:2765`.

Tollbooth changes:

- `InterruptGate` now defaults to `auto_approve=False` in `dharma_swarm/checkpoint.py:78` and `dharma_swarm/checkpoint.py:102`.
- Orchestrator free-text path extraction now requires `task_metadata.get("allow_free_text_result_path") is True` in `dharma_swarm/orchestrator.py:2467`.

#### Surface Coverage

The v2 evidence matrix classifies 16 surfaces.

- Classified: 16 / 16, 100%
- Joined: 5 / 16, 31.25%
- Joined or adapter-ready: 9 / 16, 56.25%

Joined surfaces include the selected runtime spine path:

- A2A/local ingress
- RuntimeLifecycle delegation path
- RuntimeStateStore ledger
- selected artifact/completion receipt path
- selected idempotency path

Adapter-ready surfaces include:

- TaskBoard task payloads
- Orchestrator dispatch payloads
- MessageBus/event payloads
- tool call payloads
- ontology action payloads
- graph/checkpoint payloads
- self-mod/proposal payloads

Remaining quarantined or missing surfaces are listed in the evidence plan and should not be treated as canonical until joined or wrapped.

#### Done Criteria Status

- V1 claims independently verified or corrected: done. Clean `HEAD` lacked v1; ported candidate passes tests.
- Every major organ has status joined, adapter, quarantine, or missing: done in the v2 surface matrix.
- At least three real surfaces beyond original tracer path wired or adapter-ready: done.
  - Tool call payloads can carry adapted identity.
  - Ontology action payloads can carry adapted identity.
  - Graph/checkpoint payloads can carry adapted identity.
  - Self-mod/proposal payloads can carry adapted identity.
  - MessageBus/event payloads can carry adapted identity.
- No artifact/side effect in selected surfaces lacks `run_id` and `trace_id`: done for selected tested surfaces.
- Duplicate idempotency tested before side effects: done for selected RuntimeStateStore/A2A and MessageBus paths.
- Missing identity fails on selected runtime boundaries: done for selected RuntimeStateStore and RuntimeLifecycle boundaries.
- TRCR-9999-ALPHA tracer reconstructs ingress-to-artifact by `run_id`, `trace_id`, and `correlation_id`: done in `tests/test_runtime_truth_spine_v2_evidence.py`.

#### Tests Run

Focused and adjacent verification:

```bash
env HOME=/private/tmp/dharma_spine_v2_test_home pytest -q \
  tests/test_runtime_truth_spine_v1.py \
  tests/test_runtime_truth_spine_v2_adapters.py \
  tests/test_runtime_truth_spine_v2_evidence.py \
  tests/test_runtime_truth_spine_v2_tollbooth.py \
  tests/test_runtime_state.py \
  tests/test_runtime_lifecycle.py \
  tests/test_a2a_spec_conformance.py \
  tests/test_message_bus.py \
  tests/test_checkpoint.py \
  tests/test_orchestrator.py
```

Result:

```text
159 passed, 2 warnings in 11.99s
```

Compile verification:

```bash
python -m compileall -q \
  dharma_swarm/spine/identity.py \
  dharma_swarm/spine/adapters.py \
  dharma_swarm/runtime_state.py \
  dharma_swarm/runtime_lifecycle.py \
  dharma_swarm/a2a/a2a_server.py \
  dharma_swarm/a2a/node_gateway.py \
  dharma_swarm/message_bus.py \
  dharma_swarm/orchestrator.py \
  dharma_swarm/checkpoint.py
```

Result: passed.

Diff whitespace check:

```bash
git diff --check
```

Result: passed before this final report was added.

#### Remaining Gaps

1. C2 ontology tollbooth is still queued, not completed in this slice.
   - `ActionDef.modifies` and `ActionDef.requires_approval` still need to become enforced runtime contracts.
   - This was intentionally not mixed into the v2 runtime spine saturation work.

2. Receipt helpers are broader than their call-site coverage.
   - RuntimeStateStore can now record message, ontology, self-mod, idempotency, side-effect, artifact, and child receipts.
   - Actual hot-path call sites still need to be wired one by one for MessageBus consumption, OntologyRegistry action execution, and self-mod proposal/gate/apply/verify/promote/revert.

3. More runtime boundaries need mandatory identity.
   - TaskBoard create/create_batch, ArtifactStore and EngineArtifactStore writes, ToolRegistry side effects, graph/checkpoint resume, and ontology action execution should reject missing identity or adapt from a parent identity.

4. Compatibility adapters are intentionally permissive.
   - They make identity carryable across organs.
   - They do not yet make every organ canonical. Canonical enforcement belongs at the runtime ledger boundary and selected hot-path gateways.

5. Context+ static analysis was not accepted as final evidence.
   - The Context+ tool targeted `/Users/dhyana/dharma_swarm`, the dirty default checkout, not this clean v2 worktree.
   - Compile and pytest results from this clean worktree are the valid evidence.

#### Next Three Slices

1. Close the C2 ontology tollbooth.
   - Enforce `ActionDef.modifies` and `ActionDef.requires_approval` in the action execution chokepoint.
   - Write `ontology_action_requested` before the mutation and `ontology_action_applied` only after the mutation.
   - Tests must prove that declared modifies actually mutate, approval-required actions block without approval, and missing identity fails.

2. Wire receipt helpers into hot call sites.
   - MessageBus: record `message_consumed` and idempotency receipts before handler side effects.
   - Ontology: record action request/apply receipts around enforced mutations.
   - Self-mod: record proposal, gate, apply, verify, promote, and revert receipts as a closed loop.
   - Tests must prove ledger reconstruction by `run_id`, `trace_id`, `correlation_id`, and proposal/action/message IDs.

3. Promote adapter-ready surfaces to mandatory identity boundaries.
   - TaskBoard task creation, artifact stores, tool runner side effects, graph/checkpoint resume, and self-mod proposal ingestion should require identity or derive it from a parent identity.
   - Tests must prove missing identity fails and duplicate idempotency does not repeat side effects.

#### Bottom Line

The v2 branch does not claim the entire platform is canonical yet. It makes the spine real on one tracer-backed path, verifies v1 instead of trusting it, broadens identity compatibility across connected organs, adds durable receipt vocabulary and helper APIs, closes two concrete bypasses, and leaves a classified surface matrix for the remaining saturation work.

---

## Section 8 — `reports/governance/runtime_truth_spine_v2_evidence_plan.md` <a id="section-8-reports-governance-runtime-truth-spine-v2-evidence-plan-md"></a>

> **Original path:** `reports/governance/runtime_truth_spine_v2_evidence_plan.md`  
> **Source date:** 2026-06-06  
> **Author/Owner:** Dhyana (Tracer/Evidence Captain)  
> **Size:** 7,806 bytes  
> **sha256:** `2d5eafcdaebdb580966e03fb7c6c8a9689655043a6fe707da5457a9a57895f5b`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Spine v2 evidence bundle plan: audit source boundary, clean audit baseline d5ebc456 from the clean-main architecture worktree.

### Verbatim content

### Runtime Truth Spine v2 Evidence Bundle Plan

Subagent: Tracer/Evidence Captain

Audit source boundary:

- Clean audit baseline: `d5ebc456` from the clean-main architecture audit.
- v2 worktree: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2`.
- v2 HEAD inspected by this subagent: `2737b26d7ed8dbee9c828ba64d5a6c9ec128b859`.
- Source truth rule: tracked clean-main files are source truth. Current v2 working-tree edits are build candidates until committed. Untracked files are evidence candidates only after they are intentionally added.
- External systems: no live Palantir, NATS, Temporal, or paid LLM calls.

#### Evidence Bundle Layout

The final v2 evidence bundle should be written under:

`reports/governance/runtime_truth_spine_v2_evidence/`

Expected files:

- `evidence_manifest.md` - SHA, branch, dirty status, test commands, runtime restrictions.
- `surface_matrix.md` - every major organ with `joined`, `adapter-ready`, `quarantine`, or `missing`.
- `surface_matrix.json` - machine-readable copy of the same matrix.
- `tracer_payload.json` - fixed TRCR-9999-ALPHA IDs and expected fields.
- `id_mapping_table.md` - external A2A task ID, task ID, run ID, trace ID, correlation ID, claim ID, idempotency key, artifact ID.
- `trace_timeline.md` - ingress, claim, run, artifact, idempotency, completion receipts.
- `sqlite_query_results.txt` - selected read-only SQL proving runtime tables contain the chain.
- `pytest_results.txt` - exact test command and result.
- `verdict.md` - coverage percentage, proven surfaces, quarantines, missing surfaces, next slices.

#### Surface Matrix

Coverage definition:

- `joined`: carries Canonical ExecutionIdentity and writes RuntimeStateStore facts/receipts on the selected path.
- `adapter-ready`: can accept or emit ExecutionIdentity through a compatibility surface, but enforcement is not complete.
- `quarantine`: intentionally excluded from runtime truth claims until wrapped or demoted.
- `missing`: no sufficient identity/ledger enforcement on the selected evidence surface.

| Surface | Status | Evidence expectation |
| --- | --- | --- |
| A2A local submit | joined | RuntimeStateStore identity, A2A receipt, idempotency record before handler side effect |
| A2A HTTP node gateway | adapter-ready | Top-level identity fields are parsed/serialized across request/response |
| RuntimeLifecycle task claim | joined | `record_task_claim(require_identity=True)` fails without identity and writes receipt with run/trace |
| RuntimeLifecycle delegation run | joined | `record_delegation_run(require_identity=True)` writes run facts and receipt |
| RuntimeLifecycle artifact record | joined | `record_artifact(require_identity=True)` persists artifact with run_id and trace_id |
| MessageBus emit_event with idempotency_key | joined | RuntimeStateStore idempotency begins before event insert; duplicate emits no second event |
| Orchestrator result persistence | adapter-ready | Provenance/artifact path carries run_id, trace_id, correlation_id; hard boundary still pending |
| TaskBoard task metadata | adapter-ready | Metadata can carry execution_identity; mandatory enforcement still pending |
| Checkpoint human interrupt | adapter-ready | Checkpoint can carry identity; durable wait/approval receipts still pending |
| Ontology execute_action | missing | C2 tollbooth slice must enforce `ActionDef.modifies` and `requires_approval` |
| Tool registry side effects | missing | Tool calls need mandatory identity plus side_effect_intent/complete receipts |
| Graph/workflow checkpoints | missing | Graph checkpoint identity and resume receipts are not saturated |
| Self-modification proposals | missing | proposal/gate/apply/verify/promote/revert receipts are not saturated |
| NATS/JetStream path | quarantine | Not selected for local deterministic evidence; no live NATS calls |
| MCP server/tool access | missing | MCP/tool boundary needs an adapter before side effects |
| Free-text file extraction | quarantine | Regex path writes must stay quarantined until deterministic tollbooth exists |

Coverage:

- Classified surfaces: 16/16 = 100%.
- Joined surfaces: 5/16 = 31.25%.
- Joined or adapter-ready surfaces: 9/16 = 56.25%.
- Missing or quarantined surfaces: 7/16 = 43.75%.

#### TRCR-9999-ALPHA Expectations

Fixed IDs:

- `external_a2a_task_id`: `TRCR-9999-ALPHA`
- `task_id`: `task-trcr-9999-alpha`
- `run_id`: `run-trcr-9999-alpha`
- `trace_id`: `trc-trcr-9999-alpha`
- `correlation_id`: `corr-trcr-9999-alpha`
- `claim_id`: `claim-trcr-9999-alpha`
- `artifact_id`: `artifact-trcr-9999-alpha`
- `idempotency_key`: `idem-trcr-9999-alpha`

Required proof:

- `RuntimeStateStore.get_run_ledger(run_id)` returns identity, run, artifacts, receipts, children, and idempotency records.
- A2A ingress maps `TRCR-9999-ALPHA` to internal `task_id`, `run_id`, `trace_id`, and `correlation_id`.
- Parent run can answer "who spawned this child" through `list_child_runs(parent_run_id)` / `get_run_ledger(parent).children`.
- Every selected artifact has non-empty `run_id` and `trace_id`.
- A2A handler side effect sees an idempotency row with status `started` before handler execution.
- MessageBus event insert sees RuntimeStateStore idempotency before the event row exists.
- Duplicate idempotency key does not repeat the selected side effect.

#### Missing Identity Failure Boundaries

Selected hard-fail boundaries:

- `RuntimeLifecycle.record_task_claim(..., require_identity=True)`
- `RuntimeLifecycle.record_delegation_run(..., require_identity=True)`
- `RuntimeLifecycle.record_artifact(..., require_identity=True)`

Expected result:

- Missing trace/correlation/claim identity raises `MissingExecutionIdentity`.
- No partial rows are written to `task_claims`, `delegation_runs`, or `artifact_records`.

Not yet hard-fail by design:

- A2A local ingress currently adapts and fills missing fields where possible. It is selected as an adapter/join surface, not as the missing-identity hard boundary.

#### Tests Added By This Subagent

New test scaffold:

`tests/test_runtime_truth_spine_v2_evidence.py`

Test cases:

- `test_v2_surface_matrix_is_classified_and_quantified`
- `test_v2_missing_identity_fails_selected_runtime_boundaries`
- `test_v2_trcr_9999_alpha_reconstructs_chain_of_custody`
- `test_v2_a2a_idempotency_exists_before_handler_side_effect`
- `test_v2_message_bus_idempotency_happens_before_event_insert`

#### Verification Commands

Run from `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2`:

```bash
python -m compileall -q dharma_swarm/runtime_state.py dharma_swarm/runtime_lifecycle.py dharma_swarm/a2a/a2a_server.py dharma_swarm/a2a/node_gateway.py dharma_swarm/message_bus.py dharma_swarm/checkpoint.py dharma_swarm/orchestrator.py dharma_swarm/spine
pytest -q tests/test_runtime_truth_spine_v1.py tests/test_runtime_truth_spine_v2_evidence.py
pytest -q tests/test_runtime_state.py tests/test_runtime_lifecycle.py tests/test_a2a_spec_conformance.py tests/test_message_bus.py tests/test_checkpoint.py
git diff --check
```

#### Final Report Outline

The synthesis report should include:

1. Clean-Source Boundary
2. Changed Files
3. Surface Coverage Table
4. TRCR-9999-ALPHA Chain of Custody
5. Missing Identity Failure Results
6. Idempotency Before Side Effect Results
7. Artifact and Side-Effect Identity Results
8. Quarantined Surfaces
9. Remaining Gaps
10. Next Three Slices

Next three slices:

1. Make A2A ingress require externally supplied identity for production-mode boundaries instead of always adapting missing fields.
2. Convert C2 ontology tollbooth declarations into enforced `ActionDef.modifies` and `requires_approval` behavior with ontology action receipts.
3. Add mandatory side_effect_intent and side_effect_complete receipts to tool, graph checkpoint, and self-modification proposal paths.

---

## Section 9 — `docs/research/RUNTIME_TRUTH_SPINE_COMPLETION_PLAN.md` <a id="section-9-docs-research-runtime-truth-spine-completion-plan-md"></a>

> **Original path:** `docs/research/RUNTIME_TRUTH_SPINE_COMPLETION_PLAN.md`  
> **Source date:** 2026-06-06  
> **Author/Owner:** —  
> **Size:** 22,871 bytes  
> **sha256:** `e931d82f0620a5de12f52e56a8fdef984b8268fd864a175f8ed2306173fcd2e3`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Runtime Truth Spine completion plan: stabilize the spine as substrate; no ontology refactor, no ingestor rewrite, no runtime behavioral change.

### Verbatim content

### Runtime Truth Spine — Completion Plan / Definition of Done

**Status:** ACTIVE TRACK (Spine saturation phase)
**Scope:** Stabilize the Runtime Truth Spine as the substrate. No ontology refactor, no ingestor rewrite, no runtime behavior change outside spine scope.
**Evidence basis:** Direct inspection of `dharma_swarm/spine/` (899 lines, 8 files), 26-site import surface, `tools/spine_adoption_metric.py` output, and the spine test suite (38 spine tests passing locally; v2 build report cites 159 passing).

> Doctrine: **one invariant, one invocation path, one receipt.** The spine is the canonical event substrate; projections and caches live above it. Treat the spine as the substrate and complete it before building the Verified Experiment Loop on top.

---

#### 1. Current Spine Map

| Path | Role | Current status | Import sites / dependents | Risk |
|---|---|---|---|---|
| `dharma_swarm/spine/__init__.py` | Public surface + correlation-spine doctrine; exports identity, receipt, routing, invoke, adapters | Stable; `__all__` frozen | Import root for all 17 non-test sites | Med — any signature change ripples to all dependents |
| `dharma_swarm/spine/identity.py` | Canonical `ExecutionIdentity` (join-key set), `require_execution_identity`, `from_metadata` | Joined (metric: `identity_contract` joined) | `adapters`, `tollbooth`, `ontology`, `runtime_state`, `runtime_lifecycle`, A2A | High — the truth owner; bugs corrupt all lineage |
| `dharma_swarm/spine/receipt.py` | `EvidenceReceipt` canonical artifact; OTel GenAI export; token/cost fields | Stable; OTel is export adapter only | `invoke`, `persistence`, `artifact_store` | High — canonical proof object |
| `dharma_swarm/spine/adapters.py` | Carry identity across organs (no routing/dispatch/persist); per-surface field mapping | Largest file (327 lines); adapter-ready for 4 surfaces | `a2a_server`, `message_bus`, `task_board`, `artifact_store`, `ontology`, `tool_registry` | Med-High — implicit per-surface heuristics could mis-map identity |
| `dharma_swarm/spine/tollbooth.py` | Fail-closed gate: require identity + RuntimeStateStore before side effects | Joined; small + deterministic | `ontology` (`require_execution_tollbooth`), opportunity_dispatcher | High — the promotion/gating chokepoint |
| `dharma_swarm/spine/routing.py` | `RoutingDecision` canonical value object | Shape-only (7 routers not yet collapsed onto it) | `invoke` | Low-Med — adoption incomplete but non-blocking |
| `dharma_swarm/spine/invoke.py` | The one blessed `invoke_agent` path (pass-through + receipt) | PR-A pass-through stage; not yet default invoker | spine internal | Med — full collapse (PR C+) deferred, acceptable |
| `dharma_swarm/spine/persistence.py` | Projection-only helper targeting `delegation_runs.receipt_json`; idempotent column migration | Stable; 0 production callers; **not** a canonical runtime receipt writer | spine internal | Med — must not be promoted into a second `RuntimeReceipt` writer |

Adjacent (in-scope dependents, not part of the 8-file core): `dharma_swarm/runtime_state.py` (RuntimeStateStore ledger), `dharma_swarm/runtime_lifecycle.py`, `dharma_swarm/a2a/a2a_server.py`, `dharma_swarm/message_bus.py`, `dharma_swarm/task_board.py`, `dharma_swarm/tool_registry.py`, `dharma_swarm/artifact_store.py`, `dharma_swarm/ontology.py`, `dharma_swarm/opportunity_dispatcher.py`, `dharma_swarm/diff_applier.py`, `dharma_swarm/revenue/spine.py`.

**Adoption metric (current):** 16 mission surfaces — **8 joined, 4 adapter-ready (75% joined-or-adapter-ready), 1 missing, 1 quarantine, 2 legacy.** Goal floor: **≥95%.** Non-joined surfaces: `tool_registry_dispatch`, `ontology_action_tollbooth`, `self_modification_loop`, `workflow_checkpoint_replay`, `mcp_tool_access`, `nats_jetstream_transport`, `opportunity_refill_research_backend`, `legacy_no_identity_escape_hatch`.

---

#### 2. Spine Invariants

| Invariant | Why required | Existing support | Missing support | Test needed |
|---|---|---|---|---|
| Canonical identity is the owner of truth | Every durable unit of work needs one join-key set; prevents silent renames | `ExecutionIdentity` frozen dataclass; `require_for_dispatch` | None critical; ensure no adapter generates identity at hard boundaries | Property test: identity round-trips through all adapter surfaces unchanged |
| EvidenceReceipt creation + validation | One canonical in-flight artifact per dispatch attempt; basis of all later evidence | `EvidenceReceipt`, `to_otel_span`, `to_dict` | Validation of required-field completeness before association/projection/export | Test: receipt with missing trace_id rejected by association/projection path |
| trace/correlation identity continuity | Cross-layer joins (A2A ↔ dispatch ↔ closure) must share one value | `correlation_id` = `trace_id` alias; doctrine in `__init__.py` | Enforcement that all 3 layers carry the same correlation value | Test: same correlation_id appears on receipts across layers a request traverses |
| Cost/token attachment | Equal-budget comparison (Verified Loop dependency) | `input_tokens`/`output_tokens`/`cost_usd`/`latency_ms` on receipt | Guarantee these are populated on real dispatch, not just constructible | Test: live invoke path populates usage fields |
| Tamper-evident history / Merkle interaction | Auditability of the run ledger | `runtime_state` receipt ledger; `merkle_log.py` | Confirm receipt ledger is (or chains to) tamper-evident store | Test: ledger tamper detection / hash continuity |
| Tollbooth / gating semantics | Fail-closed before side effects in required mode | `require_execution_tollbooth` (identity + RuntimeStateStore) | Apply tollbooth at remaining non-joined side-effecting surfaces | Test: side effect without identity raises in required mode (exists for ontology; extend) |
| Provenance source-artifact → result-artifact | Lineage from input to output artifact | `artifact_id`/`run_id`/`causation_id`/`parent_run_id` fields; artifact_store adapter | End-to-end provenance assertion across a full run | Test: provenance chain from source artifact to result artifact replayable |
| Stable import surface | 17 dependents must not break | Frozen `__all__`; dependency-light identity module | Lock the public surface against accidental change | Test/CI: import-surface snapshot test (assert exported names) |
| Backward compat with ontology + memory kernel | Ontology already imports `spine.identity` + `spine.tollbooth` | Confirmed imports at `ontology.py:42-43`; `spine_ref` properties | None require change — must remain unchanged | Existing ontology tests must stay green (no spine-driven regressions) |
| Test coverage expectations | DoD gate | 7 spine test files (38 tests pass locally) | Coverage on adapter per-surface mapping + correlation continuity | Targeted coverage pass on `adapters.py` surface branches |

---

#### 3. Definition of Done

| Requirement | Status | Evidence | Remaining work |
|---|---|---|---|
| All existing spine tests passing | ✅ Met (local) | 38 passed across the 7 spine test files; v2 report cites 159 suite-wide | Re-run in CI on the integration branch |
| All import sites still valid | ✅ Met | 17 non-test import sites resolve; `__all__` exports intact | Add import-surface snapshot test to lock it |
| EvidenceReceipt lifecycle documented | ◑ Partial | `receipt.py` docstrings + `__init__.py` closure-layer doctrine | Add a short `docs/` lifecycle note (create→associate/project→export) |
| Identity semantics documented | ◑ Partial | `identity.py` docstrings; correlation-spine doctrine | Document trace_id vs correlation_id rule in one place |
| Provenance chain testable | ◑ Partial | fields exist; artifact adapter present | Add end-to-end provenance test (source→result) |
| trace/correlation context stable | ✅ Met | alias enforced in receipt + identity | Add cross-layer continuity test |
| Cost/token hooks identified | ✅ Met | `input_tokens`/`output_tokens`/`cost_usd`/`latency_ms` | Confirm population on live dispatch (test) |
| No ontology refactor required | ✅ Met | ontology imports spine read-only; unchanged | Hold the line — do not touch ontology |
| No ingestor rewrite required | ✅ Met | ingestor untouched | Hold the line |
| No runtime behavior change outside spine scope | ✅ Met | spine changes are additive (adapters/tollbooth/receipts) | Keep slices additive; quarantine, never delete |

**Net DoD position:** Spine is **substantively done and stable** (tests green, imports valid, identity/receipt/tollbooth joined). Remaining work is **saturation + documentation + targeted tests**, not new architecture. The two genuine blockers to "100% substrate" are: (a) closing the **legacy ledger bypass** (`runtime_state.py` sync helpers), and (b) landing **mapping receipts** for the parallel lineages (workflow_id, proposal_id, event_id, ontology_action, engine_artifact).

---

#### 4. Minimal Code Work, If Any

| Possible patch | File(s) | Why needed | Risk | Should do now? |
|---|---|---|---|---|
| Import-surface snapshot test | `tests/` (new test only) | Locks the 17-dependent public surface against accidental break | Very low (test-only) | **Yes** — pure safety, reversible |
| Cross-layer correlation-continuity test | `tests/` (new test only) | Proves the core invariant the whole spine is built on | Low (test-only) | **Yes** — formalizes existing behavior |
| End-to-end provenance test (source→result artifact) | `tests/` (new test only) | DoD requires provenance be testable | Low (test-only) | **Yes** — additive |
| EvidenceReceipt lifecycle + identity doc note | `docs/` (new doc only) | DoD requires documented lifecycle/semantics | None (docs-only) | **Yes** — reversible |
| Close legacy ledger bypass (quarantine sync helpers) | `runtime_state.py` (`create_task_claim_sync`/`create_delegation_run_sync`) | Until closed, adoption metric is structurally dishonest | **Med** — touches runtime; this is Slice A of an existing tracked plan (PR #425/#430) | **Defer to the existing slice owner** — clearly within active track but not a same-name quick patch; coordinate, don't free-hand |
| Mapping receipts for 5 parallel lineages | per Slice C of PR #425 | Drives adoption toward ≥95% | Med | **Defer to existing slice** — already specced (#436 landed slice-c mapping receipts; remainder tracked) |

**Rule applied:** Only the test-only and docs-only patches are proposed for *now* (smallest safe, reversible). The runtime-touching items (legacy bypass, remaining mapping receipts) are already owned by the tracked spine-adoption slices (#425/#430/#435/#436/#446) — **do not free-hand them in this lane.** If a slice is unassigned, stop and ask before implementing.

---

#### 5. Tests

| Test path | What it proves | Current status | Gap |
|---|---|---|---|
| `tests/test_runtime_truth_spine_v1.py` | Core v1 invariants (identity, receipt shape) | ✅ Passing | — |
| `tests/test_runtime_truth_spine_v2_adapters.py` | Adapter identity carry across surfaces | ✅ Passing | Per-surface branch coverage in `adapters.py` |
| `tests/test_runtime_truth_spine_v2_evidence.py` | EvidenceReceipt creation/serialization | ✅ Passing | Required-field completeness before association/projection/export |
| `tests/test_runtime_truth_spine_v2_tollbooth.py` | Fail-closed gating semantics | ✅ Passing | Extend to remaining non-joined surfaces |
| `tests/test_runtime_truth_spine_adoption.py` | Adoption invariants | ✅ Passing | — |
| `tests/test_spine_adoption_metric.py` | Metric script correctness | ✅ Passing | — |
| `tests/test_spine_mapping_receipts.py` | workflow_id↔run_id and other mapping receipts | ✅ Passing | Coverage for remaining lineages |
| (new) import-surface snapshot | Public surface stability | ❌ Missing | Add (test-only) |
| (new) cross-layer correlation continuity | The global identity invariant | ❌ Missing | Add (test-only) |
| (new) end-to-end provenance | source→result lineage | ❌ Missing | Add (test-only) |

**Run strategy:** Run the **targeted spine subset first** (the 7 files above + any new tests) — it is fast (~9s) and isolates spine regressions. Run the **full suite** only before merging the integration branch, to confirm no dependent (ontology, runtime_lifecycle, a2a) regressed. Targeted-first, full-before-merge.

---

#### Adoption Definition Reconciliation

> **Updated for PR #469 (`spine(adoption-slice-1): A2A bridge dispatches through invoke_agent()`, branch `devin/1780548631-spine-a2a-adoption`, open).** The first real dispatch-ownership path now exists. The model below is revised to distinguish *where* on the surface adoption lands.

Two apparently different findings were on the table:

- **Devin report:** Spine types are shipped, but **zero production dispatches flow through `invoke_agent()`**.
- **This report:** Spine v2 is **75% joined-or-adapter-ready, 12/16 surfaces**.

**These were never contradictory — they measure different things.** The 75% figure measures **identity adoption** (does a surface import the spine and adapt/attach `ExecutionIdentity` + preserve correlation continuity?). The Devin finding measures **dispatch ownership** (does real execution flow through the one blessed `invoke_agent()` path and emit a canonical `EvidenceReceipt`?). Before #469 the second had not started; #469 starts it on exactly one opt-in path.

##### What changed with #469

**Before #469:** no runtime caller of `invoke_agent()` anywhere; no runtime surface emitted a spine `EvidenceReceipt`.

**After #469 (verified against the branch):**
- `a2a/a2a_bridge.py` gains an **opt-in** `submit_via_spine()` that dispatches through `invoke_agent()` and returns **exactly one** `EvidenceReceipt` (one constructed per outcome branch: ok / failed / cancelled / dropped).
- Exactly-one-receipt behavior is **tested** (`tests/test_spine_adoption_dispatch.py`: `test_a2a_bridge_dispatch_emits_exactly_one_evidence_receipt`, plus identity-preservation and failure-source tests).
- The existing **default `A2AServer.submit()` / direct A2A paths still bypass the Spine** — `submit_via_spine()` is a new method, not the default route.
- The receipt is **returned to the caller, not persisted** — no `persist_receipt` / `ensure_receipt_column` call in the new code.
- Token/cost fields are deliberately left `None` (A2A dispatch does not yet carry provider token counts).
- `orchestrator.py`, `agent_runner.py`, and `swarm.py` remain **Level 0** (no spine import).
- **Verified Experiment Loop runtime remains blocked.**

##### Adoption levels (explicit)

| Level | Definition |
|---:|---|
| 0 | No Spine awareness |
| 1 | Imports Spine types |
| 2 | Can adapt/attach `ExecutionIdentity` |
| 3 | Preserves cross-layer correlation identity |
| 4 | Real dispatch path flows through `invoke_agent()` |
| 5 | Exactly one `EvidenceReceipt` emitted per logical dispatch |
| 6 | EvidenceReceipt associated to persisted `RuntimeReceipt` / trace-linked / cost-token fields attached where available |
| 7 | Bypass guard active and allowlist shrinking to zero |

##### Four axes of adoption (added post-#469)

A single per-module "level" hid an important distinction that #469 makes unavoidable: a module can reach Level 4–5 on *one method* while its *default path* still bypasses the Spine. Adoption must therefore be read on four axes:

1. **Method-level adoption** — at least one method on the surface reaches the level (e.g. `submit_via_spine()` reaches L4–L5).
2. **Module-level adoption** — the surface as a whole (its identity/correlation posture) reaches the level.
3. **Default-path adoption** — the path callers hit *by default* reaches the level (the honest "is real traffic covered?" axis).
4. **Persisted-runtime association adoption** — the emitted in-flight `EvidenceReceipt` is associated to the persisted runtime receipt, trace-linked, and cost/token attached where available (Level 6), not just constructed in memory.

The 75%/12-of-16 metric reflects **module-level** identity adoption (L2–L3). #469 is the first **method-level** L4–L5 datapoint, with **default-path** and **persisted-runtime association** adoption still at zero.

##### Per-surface / per-method mapping

Evidence-based from inspection of `main` plus PR #469's branch. "Adoption level" is the **highest level reached by any path** on the surface; the four axis columns disambiguate where that level actually lands.

| Surface / method | Adoption level | Method-level? | Default path? | EvidenceReceipt emitted? | Runtime receipt associated? | Remaining gap |
|---|---:|---|---|---|---|---|
| `a2a/a2a_bridge.py` → `submit_via_spine()` *(new, #469)* | 5 | Yes (opt-in) | No | Yes — exactly one, tested | No | Make a default/blessed route; prove association with the existing runtime receipt/projection if needed; attach cost/token (L6) |
| `a2a/a2a_bridge.py` → `submit()` / default | 1 | n/a | Yes | No | No | Route default traffic through the spine path |
| `a2a/a2a_server.py` | 3 | Partial | No | No | No | Dispatch through `invoke_agent`; emit one receipt |
| `runtime_state.py` | 3 (+partial 7) | No | No | No (projection helper exists, unused) | No | Close legacy bypass (allowlist→0); keep `receipt_json` projection-only and prove single runtime owner |
| `runtime_lifecycle.py` | 3 | No | No | No | No | Emit receipt on lifecycle dispatch |
| `task_board.py` | 2 | No | No | No | No | Correlation continuity; receipt on claim dispatch |
| `message_bus.py` | 2 | No | No | No | No | Correlation on send/consume; receipt |
| `artifact_store.py` | 2 | No | No | No | No | Provenance receipt on artifact record |
| `tool_registry.py` | 2 | No | No | No | No | Tollbooth on side-effecting calls; receipt |
| `ontology.py` | 2 | No | No | No | No | Mapping receipt for ontology actions — **no refactor** |
| `diff_applier.py` | 2 | No | No | No | No | Receipt on self-mod apply (proposal→apply→verify) |
| `opportunity_dispatcher.py` | 2 | No | No | No | No | Correlation continuity; receipt on dispatch |
| `agent_runner.py` | 0 | No | No | No | No | Adopt identity; route real agent runs through `invoke_agent` — **primary L4 target for Verified Loop** |
| `orchestrator.py` | 0 (1 partial) | No | No | No | No | Adopt spine identity; dispatch through `invoke_agent`; emit `EvidenceReceipt` and associate to a single runtime receipt — **primary L4 target for Verified Loop** |
| `swarm.py` | 0 | No | No | No | No | Adopt identity at top-level swarm dispatch |

**Key reading:** #469 proves the dispatch-ownership pattern works (method-level L5 with exactly-one-receipt under test), but **default-path** and **persisted-runtime association** adoption are still zero across the fleet, and the surfaces the Verified Loop runs experiments through — `agent_runner.py`, `orchestrator.py`, `swarm.py` — remain **Level 0**.

##### Explicit statement

> **Adapter-ready adoption does not yet prove dispatch-owned EvidenceReceipt emission. PR #469 demonstrates method-level dispatch ownership on one opt-in A2A path (exactly one EvidenceReceipt, tested), but default-path and persisted-runtime association adoption remain zero. Verified Experiment Loop runtime remains blocked until the dispatch surfaces used by experiments — at minimum `agent_runner.py`, `orchestrator.py`, and `swarm.py` — emit exactly one EvidenceReceipt per logical dispatch on their default path, and those in-flight receipts are associated to a single persisted RuntimeReceipt / trace-linked without minting a second runtime receipt.**

---

#### Final Output

##### 1. Exact files inspected
- `dharma_swarm/spine/__init__.py`, `identity.py`, `receipt.py`, `adapters.py`, `tollbooth.py`, `routing.py`, `invoke.py`, `persistence.py`
- `dharma_swarm/ontology.py` (confirmed spine imports at lines 42–43), `dharma_swarm/runtime_state.py`, `dharma_swarm/execution_profile.py`
- `tools/spine_adoption_metric.py`, `reports/governance/spine_adoption_metric.json`
- Spine tests: `tests/test_runtime_truth_spine_v1.py`, `..._v2_adapters.py`, `..._v2_evidence.py`, `..._v2_tollbooth.py`, `test_runtime_truth_spine_adoption.py`, `test_spine_adoption_metric.py`, `test_spine_mapping_receipts.py`
- Verified-Loop-adjacent assets: `archive.py`, `experiment_log.py`, `decision_ontology.py`, `canary.py`, `self_research.py`, `merkle_log.py`, `experiments/petri_dish/models.py`
- Agent prompts: `NEXT_SPRINT_PROMPT.md`, `CLAUDE_CODE_LIVE_FIRE_PROMPT.md`; open PRs #425, #426, #431; merged #427/#430/#435/#436/#446

##### 2. Exact files created or modified
- **Created:** `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md` (RFC, design-only)
- **Created:** `docs/research/RUNTIME_TRUTH_SPINE_COMPLETION_PLAN.md` (this document)
- **Modified:** none. No runtime code, migrations, dependencies, or renames.

##### 3. Spine Definition of Done
Substantively met: spine tests green, 17 import sites valid, identity/receipt/tollbooth joined, cost/token hooks present, ontology/memory-kernel backward-compatible. Remaining to reach 100% substrate: close the legacy ledger bypass and land the remaining mapping receipts (both owned by existing tracked slices), plus add 3 test-only and 1 docs-only artifacts.

##### 4. Verified Experiment Loop RFC summary
Design-only RFC at `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md` defining 10 core objects, two lifecycles (mapped onto existing `PromotionState`/`EvidenceTier`), a fail-closed promotion gate, and recommended defaults for held-out evals (human-seeded/system-expanded/human-approved), budget (hybrid), and authority (shadow-auto-eval, human-gated promotion). It reuses existing assets (DarwinEngine, MAP-Elites archive, Merkle log, canary, decision ontology, petri dish) and introduces no new identity, ledger, or transport.

##### 5. Remaining blockers before implementation
- Legacy ledger bypass in `runtime_state.py` not yet closed → adoption metric not yet honest at 100%.
- Remaining mapping receipts (subset of the 5 parallel lineages) outstanding.
- Adoption at 75% joined-or-adapter-ready; floor target ≥95%.
- These are owned by existing spine-adoption slices — coordinate, do not free-hand.

##### 6. Should Spark Ingestor remain deferred?
**Yes.** No ingestor work this lane. The Verified Loop's MVI consumes ingestor output only after Spine DoD.

##### 7. Should Semantic Ontology remain deferred?
**Yes.** Ontology already imports the spine read-only and must remain unchanged. No refactor.

##### 8. Next safest action
Add the three test-only artifacts (import-surface snapshot, cross-layer correlation continuity, end-to-end provenance) and the one docs-only lifecycle note in the Spine lane; in parallel, route the RFC for review. Both are reversible and touch no runtime behavior. Defer the legacy-bypass and remaining-mapping-receipt work to the existing tracked slices — stop and confirm ownership before implementing those.

---

## Section 10 — `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` <a id="section-10-docs-reports-converged-seam-audit-runtime-truth-spine-md"></a>

> **Original path:** `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md`  
> **Source date:** 2026-06-06  
> **Author/Owner:** AmitabhainArunachala (Perplexity+Codex converged)  
> **Size:** 16,203 bytes  
> **sha256:** `bfbc9240d56155dcd15f895e70db10b64488a2eb70033a0c0cd79efdcad8a51b`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Converged seam audit (routing x pool x A2A x provider): one shared diagnosis and one shared build direction before more agent-fabric work.

### Verbatim content

### Converged Seam Audit — Runtime Truth Spine

**Date:** 2026-05-28  
**Repo:** `AmitabhainArunachala/dharma_swarm`  
**Status:** Converged audit between the Perplexity seam audit provided by John and Codex review in ChatGPT.  
**Purpose:** Establish one shared diagnosis and one shared build direction before more agent-fabric work begins.

---

#### 0. Signature / Sign-off

This document is the single consensus artifact for the current routing × pool × A2A × provider seam review.

- **Perplexity audit position:** Accepted as the implementation-level diagnosis: the A2A module is clean, while `agent_runner.py`, `swarm.py`, `orchestrator.py`, and `providers.py` carry the bulk of the complexity and accretion.
- **Codex / ChatGPT position:** Accepted as the system-level prescription: do not add more fabric first; compress the system around one blessed runtime rail.
- **Converged position:** Build the Runtime Truth Spine before expanding persistent agent fabric.

This is not a claim that every line below was independently authored by both systems. It is the shared synthesis John asked to preserve as the working doctrine for the next build step.

---

#### 1. Final Verdict

Dharma Swarm is not fake AI vapor. It is a real system with several strong organs.

But it is not elegant and simple across the board yet.

The accurate diagnosis is:

> **Dharma Swarm is agent-built system accretion: roughly real engineering with concentrated bloat in a few high-gravity files.**

The strongest recent layer is A2A. The most tangled older layers are the orchestrator / runner / swarm lifecycle core.

The system is bleeding-edge in selected places:

- A2A Tier-1 compatibility
- cross-agent task semantics
- context IDs
- cycle detection
- many provider lanes
- telos / witness / extension concepts
- lifecycle and evidence ambitions

But it is behind its own ambition in one critical way:

> There is no single obvious path an agent author should call when they want work to happen.

An agent still has to infer whether to use:

- `A2AClient`
- `SwarmManager`
- `Orchestrator`
- `AgentPool`
- `AgentRunner`
- provider router
- `MessageBus`
- `SessionLedger`
- runtime lifecycle
- telemetry plane
- witness
- telos seam
- provenance log
- operator brief persistence

That is the core problem.

---

#### 2. Shared Diagnosis

Perplexity and Codex converged on the same root issue from two angles.

| Axis | Implementation audit | System audit | Joint verdict |
|---|---|---|---|
| A2A | Clean, focused modules | Real protocol substrate after PR #362 | Good foundation |
| Orchestrator | Architecturally right, organizationally heavy | Too many responsibilities in dispatch path | Needs compression |
| AgentRunner | `run_task` is too large and accreted | Provider call, memory, evidence, registry, telos, lineage all mixed | Biggest tangle |
| SwarmManager | Wiring god object | Too many subsystem references and unclear entrypoint | Needs assembly boundary |
| providers.py | Functionally useful, file-level hoarding | Provider abstraction is good but bloated | Split later, not first |
| Truth surfaces | Many overlapping persistence systems | No canonical receipt | Biggest cognitive load |

The disease is not lack of features. The disease is unclear ownership of runtime truth.

---

#### 3. What Is Clean

##### A2A Layer

The A2A layer is now the cleanest major seam.

It has focused files:

- `dharma_swarm/a2a/a2a_server.py`
- `dharma_swarm/a2a/a2a_client.py`
- `dharma_swarm/a2a/agent_card.py`
- `dharma_swarm/a2a/node_gateway.py`
- `dharma_swarm/a2a/node_registry.py`
- `dharma_swarm/a2a/a2a_bridge.py`

After PR #362 it supports:

- 8 task states
- `context_id`
- strict-ish part construction
- artifacts/history split
- AgentSkill / AgentCard
- supported interfaces and security declarations
- gateway paths
- cycle detection lifecycle
- backward compatibility

This layer should be treated as infrastructure, not rewritten.

##### Provider Abstraction

The provider abstraction itself is good:

- providers implement `complete()`
- providers implement `stream()`
- missing API keys are tolerated until use
- many provider lanes exist

The problem is organizational, not conceptual: too many provider classes live in one file.

##### AgentPool Concept

`AgentPool` is simple and lock-protected. Its design is mostly fine.

The problems are:

- it is buried inside `agent_runner.py`
- `get_result()` returns `None` only to satisfy an interface
- the dispatch path still relies on looking runners back up after routing

---

#### 4. What Is Tangled

##### `AgentRunner.run_task`

This is the biggest localized tangle.

It nominally means:

> take a task, produce a result string

But it also performs or triggers:

- lifecycle event emission
- provider routing
- provider call
- response interpretation
- observability traces
- guardrails
- memory write-back
- mem-action parsing
- lineage recording
- retrieval outcome recording
- idea uptake
- fitness signaling
- AgentRegistry logging
- telic seam outcome/value/contribution recording
- error handling
- state transitions

That is too much for one method.

However, decomposing it immediately is not the first move. If it is decomposed before the blessed rail exists, the repo may simply get 12 helper methods orbiting the same unclear center.

##### `SwarmManager`

`SwarmManager` currently acts as a manual dependency-injection container, lifecycle shell, subsystem registry, crew spawner, bootstrapper, and runtime coordinator.

This is understandable historically, but it creates high cognitive load.

The long-term direction is to extract assembly/wiring into a dedicated assembly layer. But again, not first.

##### `Orchestrator`

The orchestrator has good basic architecture:

- ready tasks
- idle agents
- dispatch assignment
- fan-out/fan-in
- topology genome handling

But it also owns too much lifecycle and failure complexity.

The immediate problem is not that the orchestrator is large. The immediate problem is that the dispatch boundary is not canonicalized into one receipt and one invocation path.

##### Truth-Surface Explosion

The repo has too many plausible answers to the question:

> Where does “what happened” get recorded?

Known truth/persistence surfaces include:

- `session_ledger.py`
- `runtime_lifecycle.py`
- `telemetry_plane.py`
- `agent_registry.py`
- `witness.py`
- `engine/event_memory.py`
- `operator_brief/persistence.py`
- `board/event_log.py`
- `sakshi/provenance_log.py`
- `message_bus.py`
- `lineage.py`
- `telic_seam.py`

Some of these may be valuable. The issue is not that they exist. The issue is that none is clearly the canonical record.

The system needs one root fact stream and derived views.

---

#### 5. Current Root Invariant

The next layer should be built around this invariant:

```text
Task exists
+ Runner exists
+ Dispatch claim exists
+ Context exists
+ Routing decision exists
+ Provider call is attempted or explicitly skipped
+ Evidence receipt exists
= safe execution path
```

If any link fails, the system must say which link failed.

No more generic `dispatch_dropoff` ambiguity.

No more guessing whether a failure was provider/API-key related when execution never reached the provider.

---

#### 6. The Blessed Spine

The system should converge on one runtime rail:

```text
Objective
  → Task
  → RoutingDecision
  → DispatchClaim
  → Runner
  → ProviderCall
  → Artifact
  → EvidenceReceipt
```

Everything else attaches to this spine:

- A2A attaches at Task / context / Artifact boundaries.
- Telos attaches as pre/post gates on RoutingDecision and EvidenceReceipt.
- Witness attaches as an audit plugin over EvidenceReceipt.
- AgentRegistry becomes a derived identity/fitness view.
- Telemetry becomes an export of EvidenceReceipt.
- Dashboard reads EvidenceReceipt or derived projections.
- Provider feedback becomes part of RoutingDecision and EvidenceReceipt.
- SessionLedger/runtime lifecycle become canonical sinks or compatibility mirrors during migration.

---

#### 7. Tier 1 Build Direction

##### Fix 1 — Runtime Truth Spine

Define one canonical `EvidenceReceipt` for dispatch execution.

A receipt should include at minimum:

```yaml
evidence_id:
trace_id:
context_id:
task_id:
agent_id:
routing_decision_id:
claim_id:
runner_exists:
task_exists:
claim_status:
provider:
model:
provider_attempted:
result_artifact_ids:
error:
error_source:
started_at:
finished_at:
latency_ms:
metadata:
```

Result and error should be one-of in spirit: a completed receipt has result artifacts; a failed receipt has error/error_source.

Every dispatch should produce exactly one receipt.

During migration, this receipt may also write to existing surfaces. But the receipt is the canonical object.

##### Fix 2 — One Agent Invocation API

Create a single blessed API:

```python
async def invoke_agent(task: Task, agent_id: str, context_id: str) -> EvidenceReceipt:
    ...
```

This is the internal rail agents call.

It can delegate internally to existing systems:

- Orchestrator
- AgentPool
- AgentRunner
- A2AClient
- provider router
- runtime lifecycle

But callers should not need to know those details.

The agent-author question becomes simple:

> “How do I ask an agent to do work?”

Answer:

> `invoke_agent(...)`

##### Fix 3 — One RoutingDecision Object

Define one canonical routing object:

```python
@dataclass
class RoutingDecision:
    decision_id: str
    context_id: str
    task_id: str
    agent_id: str
    provider: str
    model: str
    reason: str
    scores: dict[str, float]
    fallback_plan: list[str]
    created_at: str
```

This should replace scattered implicit decisions across:

- `_select_idle_agent`
- A2A discovery
- ModelRouter
- IntentRouter
- topology genome selection
- provider fallback

Do not replace all of those systems in one PR. First make them emit or consume this shared object.

---

#### 8. OTel / GenAI Position

The EvidenceReceipt should be designed so it can serialize cleanly into OpenTelemetry GenAI spans.

Important nuance:

OpenTelemetry has official GenAI semantic conventions for agent spans, model spans, events, exceptions, metrics, and provider-specific systems such as OpenAI and Anthropic. But the OpenTelemetry GenAI page currently marks the status as **Development**, with explicit opt-in guidance for latest experimental GenAI conventions.

Therefore:

- Do not claim OTel GenAI is a fully stable default standard.
- Do design EvidenceReceipt with OTel-compatible field names where practical.
- Do include `trace_id`, `span_id` or equivalent, provider, model, operation, token counts, latency, error type, and result metadata.
- Do make OTel export an adapter, not a second truth surface.

The correct framing:

> EvidenceReceipt is the canonical internal receipt. OTel GenAI serialization is an export format / interoperability lane.

---

#### 9. Anti-Accretion Rule

To prevent another truth surface from appearing, add a CI/governance rule:

> Any new file under `dharma_swarm/` that imports `sqlite3` or `aiosqlite` must declare in its module docstring how it relates to the `EvidenceReceipt` stream.

Allowed roles:

- canonical store
- derived view
- plugin sink
- denormalized cache
- migration compatibility mirror

If a file cannot state its relation to EvidenceReceipt, it should not create a new persistence surface.

This is the kill switch against future AI-accretion.

---

#### 10. What Not To Do Next

Do not immediately:

- build a new agent fabric framework
- introduce NATS / Redis / gRPC
- shard providers first
- rewrite SwarmManager first
- decompose all of `run_task` first
- create another dashboard truth source
- add another registry
- create another event log
- add another spiritual/metaphoric naming layer

Those may all become valid later. But doing them before the spine will increase surface area.

---

#### 11. Recommended PR Sequence

##### PR 1 — Runtime Truth Spine

Goal:

- Add `EvidenceReceipt`
- Add receipt creation at the dispatch boundary
- Split `dispatch_dropoff` into precise reasons
- Confirm task-missing vs runner-missing vs both-missing
- Store or mirror receipts through existing runtime lifecycle without creating a new competing truth surface if possible

Acceptance tests:

- normal task + runner path emits success receipt
- missing task emits `task_missing` receipt
- missing runner emits `runner_missing` receipt
- missing both emits `task_and_runner_missing` receipt
- provider failure is not confused with dispatch dropoff

##### PR 2 — Blessed Invocation API

Goal:

- Add `invoke_agent(task, agent_id, context_id)`
- Make it return `EvidenceReceipt`
- Use existing Orchestrator/AgentPool/AgentRunner underneath
- Do not change broad behavior

Acceptance tests:

- one local agent invocation succeeds
- failed invocation returns structured receipt
- A2A task context flows into receipt
- existing orchestrator tests still pass

##### PR 3 — RoutingDecision

Goal:

- Add canonical `RoutingDecision`
- Make current routing emit it
- Attach it to dispatch claim / receipt metadata
- Do not rewrite all routing logic yet

Acceptance tests:

- route_next emits decision
- A2A delegation can attach decision
- provider/model selection recorded
- fallback plan recorded when used

##### PR 4 — Refactor After Spine

Only after PRs 1–3:

- decompose `AgentRunner.run_task`
- move `AgentPool` to `agent_pool.py`
- remove or fix lying `get_result` protocol
- split provider classes into provider files
- extract `SwarmAssembly` from `swarm.py`

The spine tells us where to cut.

---

#### 12. Final Consensus Statement

Is Dharma Swarm elegant and simple across the board?

No.

Is it AI slop?

Not primarily. It is real engineering with agent-built accretion. The bloat is concentrated and fixable.

Is it bleeding-edge?

Selectively yes. A2A and multi-provider ambition are strong. Runtime truth and observability need compression.

What is the next move?

Not more fabric. Not more abstractions. Not a rewrite.

The next move is:

```text
One invariant.
One invocation path.
One routing decision.
One evidence receipt.
One dashboard truth surface.
```

That is the 1000x simplification.

---

#### 13. Master Prompt for Devin

Use this prompt for the next implementation agent:

```markdown
You are Devin working in `AmitabhainArunachala/dharma_swarm` after PR #362 merged.

Do not build new agent fabric first.

Read `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` completely before touching code.

Your mission is PR 1: Runtime Truth Spine.

Implement the smallest behavior-preserving spine that makes every dispatch produce one canonical EvidenceReceipt or equivalent runtime lifecycle record.

Start by auditing the current dispatch boundary in `dharma_swarm/orchestrator.py`, especially `_assign_dispatch`, `route_next`, `_handle_task_failure`, and runtime lifecycle claim recording.

Confirm the current `dispatch_dropoff` failure shape from `state/runtime.db` if a live DB is available. If no live DB is available, add tests that simulate:

1. task missing after route selection
2. runner missing after route selection
3. both missing
4. normal execution path
5. provider failure after runner/task exist

Then implement:

- precise dropoff error sources: `task_missing`, `runner_missing`, `task_and_runner_missing`
- structured receipt metadata with task/runner/claim/context fields
- one receipt per attempted dispatch
- no provider/API-key blame unless execution reaches provider call
- no new persistence surface unless it is explicitly declared as canonical/derived/plugin/cache/migration mirror

Do not decompose `AgentRunner.run_task` in this PR except where absolutely necessary.
Do not split providers.
Do not rewrite SwarmManager.
Do not introduce NATS, Redis, gRPC, or a new daemon.
Do not create a second event log.

Add tests and documentation.

PR title suggestion:

`feat(runtime): add dispatch EvidenceReceipt spine and precise dropoff causes`

Success criteria:

- every dispatch path has a receipt
- missing task and missing runner are distinguishable
- existing A2A/fleet/handoff/orchestrator tests pass
- no new truth surface appears without declaration
- the next PR can cleanly add `invoke_agent(...)`
```

---

## Section 11 — `docs/reports/DGC_FORENSIC_TRUTH_REPORT_2026-03-08.md` <a id="section-11-docs-reports-dgc-forensic-truth-report-2026-03-08-md"></a>

> **Original path:** `docs/reports/DGC_FORENSIC_TRUTH_REPORT_2026-03-08.md`  
> **Source date:** 2026-04-04  
> **Author/Owner:** John Shrader  
> **Size:** 8,115 bytes  
> **sha256:** `f6f3116a855ed1f3cb9558db5bd3b23288582b69132bdebddcc907ca06ac90d5`  
> **Grade:** RESOLVED-HIST  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** DGC forensic truth report (2026-03-08): static code audit + executable command verification on /dharma_swarm branch split/2026-03-08 @ 8077792.

### Verbatim content

### DGC Forensic Truth Report (2026-03-08)

#### Scope
- Repo: `~/dharma_swarm`
- Branch: `split/2026-03-08` @ `8077792`
- Audit mode: static code audit + executable command verification + full pytest evidence log

#### Executive Verdict
- DGC is **real and operational** as a local self-evolving orchestrator with gating, scoring, archive lineage, swarm orchestration, TUI runner, and CLI control paths.
- DGC is **not yet the full blueprint stack** (LangGraph/Temporal/Neo4j/RAPTOR are not wired in Python runtime code).
- NVIDIA lanes are **implemented as clients + CLI commands**, but currently **runtime blocked** in this environment (no reachable local services).
- Memory continuity across TUI restarts is now wired to session restore, but cross-session continuity still depends on which entrypoint you run and whether data was externalized.

#### Hard Evidence (Commands)
- Full tests: `1745 passed, 5566 warnings in 36.20s`
- Warning pressure: `RuntimeWarning=2`, `asyncio deprecation warnings=10`
- Mission status (strict+tracked): `exit_code=3` (tracked wiring 0/8; accelerator checks blocked).
- Core health check command reports healthy trace/failure metrics.

Evidence files:
- `reports/forensic_pytest_output.txt`
- `reports/forensic_mission_status.json`
- `reports/forensic_status.txt`
- `reports/forensic_health_check.txt`
- `reports/forensic_rag_health.txt`
- `reports/forensic_flywheel_jobs.txt`

#### Architecture Reality Matrix
| Claim | Reality | Evidence |
|---|---|---|
| Darwin self-evolution loop | **Implemented** (propose -> gate -> test/sandbox -> evaluate -> archive -> optional auto-commit) | `dharma_swarm/evolution.py` lines ~1-1365 |
| Planner/Executor split | **Implemented in Darwin cycle plan artifact** | `dharma_swarm/evolution.py` lines ~97-223 |
| Mandatory think points | **Implemented in gate system + tests** | `dharma_swarm/telos_gates.py`; `tests/test_telos_gates.py` |
| Circuit breaker / repeated failure signature | **Implemented** | `dharma_swarm/evolution.py` lines ~243-282, ~944-953 |
| Swarm orchestration + ledgers | **Implemented** | `dharma_swarm/orchestrator.py`; `dharma_swarm/session_ledger.py` |
| TUI session continuity restore | **Implemented** | `dharma_swarm/tui/app.py` lines ~164-215 |
| TUI stale runner lock recovery | **Implemented** | `dharma_swarm/tui/app.py` lines ~276-281 and ~418-430; `tui/engine/provider_runner.py` line ~72 |
| Provider matrix | **Partial** (many providers implemented in `providers.py`; TUI runner path only wires Claude adapter) | `dharma_swarm/providers.py`; `dharma_swarm/tui/engine/provider_runner.py` lines ~90-99 |
| Qdrant knowledge backend | **Partial/optional** (client-backed store + fallback local) | `dharma_swarm/engine/knowledge_store.py` |
| Neo4j graph memory | **Not wired in runtime code** | `rg` count = 0 for `neo4j` in Python package code |
| LangGraph workflows | **Not wired in runtime code** | `rg` count = 0 for `langgraph` / `StateGraph` |
| Temporal durable execution | **Not wired in runtime code** | `rg` count = 0 for `temporalio` |
| NVIDIA RAG/Data Flywheel clients | **Implemented but runtime blocked here** | `dharma_swarm/integrations/*.py`, `dgc_cli` rag/flywheel cmds, mission-status accelerators |

#### Module Census (File-by-File)
- Python module files audited: **114**
- Status: `{'data_or_script': 11, 'implemented': 101, 'abstract_or_stub': 2}`
- Maturity: `{'verified': 80, 'lightly_verified': 23, 'unverified_or_indirect': 9, 'foundation_abstract': 2}`

Abstract/stub boundary files:
- `dharma_swarm/providers.py` (NotImplementedError markers: 2)
- `dharma_swarm/providers_extended.py` (NotImplementedError markers: 3)

Largest unverified-or-indirect modules (by LOC):
- `dharma_swarm/jikoku_instrumentation.py` LOC=449 domain=core
- `dharma_swarm/protocols/recursive_reading.py` LOC=447 domain=core
- `dharma_swarm/jikoku_fitness.py` LOC=179 domain=core
- `dharma_swarm/tui/engine/governance.py` LOC=121 domain=tui
- `dharma_swarm/tui/widgets/prompt_input.py` LOC=86 domain=tui
- `dharma_swarm/tui/commands/palette.py` LOC=85 domain=tui
- `dharma_swarm/tui/widgets/tool_call_card.py` LOC=83 domain=tui
- `dharma_swarm/tui/widgets/thinking_panel.py` LOC=61 domain=tui
- `dharma_swarm/tui/theme/dharma_dark.py` LOC=37 domain=tui

Complete file-by-file table:
- `reports/forensic_file_truth_table.md`
- `reports/forensic_file_map.json`
- `reports/forensic_file_inventory.json`

#### Build History (What Happened)
- Commit history in this repo has **15 commits** from initial core package to current cron/daemon and TUI/session layers.
- Major progression observed in order: core package -> real LLM calls -> pulse daemon/startup crew -> orchestrator -> v1 godel-claw -> TUI modernization -> engine foundations -> cron wiring.

Timeline (oldest -> newest):
- `40c61cc Phase 1: DHARMA SWARM core package — 13 modules, 115 tests passing`
- `882cdc0 Phase 1.5: Real LLM calls + genome wiring from PSMV ecosystem`
- `1105a9f Add pulse daemon (wraps claude -p) and startup crew (5 PSMV roles)`
- `ce034e2 Add autonomous orchestrator: DGC spawns Claude Code swarms on demand`
- `3af6c95 (tag: pre-overnight-build-20260304) pre-overnight-build checkpoint`
- `f23d403 (tag: v1.0.0-godel-claw, origin/main) godel-claw v1: governed self-evolution, living layers, and unified dgc runtime`
- `db963f4 ops: add CI and split-brain guard, canonicalize verification dgc path`
- `fc85017 tui: stream claude output with cancellable runs; pulse: raise headless timeout`
- `693c476 tui: add explicit clipboard paste/copy support and key bindings`
- `75d127d feat(tui): add native /chat handoff to full Claude UI`
- `73d9fb4 feat(cli): add native Claude chat mode and default-mode switch`
- `b8f04f1 Unify DGC TUI v1.1 provider engine and preserve living-layer research corpus`
- `accc003 (origin/v2-gap-closure) Harden TUI stream runner against oversized NDJSON lines`
- `249ded3 feat(engine): add spine/memory foundation and quality-track tests`
- `8077792 (HEAD -> split/2026-03-08, v2-gap-closure, self-optimize-1772973848, main) feat(pulse): add cron-scheduled jobs with safe idempotent execution`

#### Reality Gaps That Matter Most
1. **Infra parity gap**: blueprint mentions LangGraph/Temporal/Neo4j, but Python runtime code currently does not wire them.
2. **Tracked wiring gap**: mission-status strict tracked lane fails because critical files are local/untracked in current worktree (`tracked_count=0/8`).
3. **Accelerator runtime gap**: NVIDIA endpoints unreachable right now; integrations are code-complete but service-lane incomplete.
4. **Warning debt**: 5,566 warnings (mostly asyncio policy deprecations), plus provider timeout coroutine warning signal in test output.
5. **Automation semantics gap**: allout loop executes only mapped actions; unmapped high-level TODOs degrade to noop/skips, generating backlog artifacts faster than substantive mutation.

#### Plain-Language Bottom Line
DGC is not fake. It is a substantial, running system with real autonomy machinery and real tests. The issue is not "nothing exists"; the issue is **layer mismatch**: core orchestrator/evolution logic is real, while some advertised infrastructure lanes are still declarative or optional, and operational wiring (tracked files + live services) is what is currently failing mission-readiness gates.

#### Recommended Next 7 Actions (High ROI)
1. Commit and track the 8 strict mission-status wiring files so tracked lane can pass.
2. Fix provider timeout warning path in `_SubprocessProvider.complete()` and reduce async-policy warning churn.
3. Add one executable end-to-end smoke that must pass: `dgc mission-status` + `dgc status` + one safe evolution dry run.
4. Promote NVIDIA services from optional probes to deterministic start/verify scripts with clear failure diagnostics.
5. Expand `execute_single_step()` mappings so top-ranked backlog items do real work (not noop fallback).
6. Add explicit policy doc for when auto-commit is allowed versus queued for human review.
7. Decide now whether LangGraph/Temporal/Neo4j stay in phase-2 roadmap or get removed from near-term claims to keep narrative truthful.

---

## Section 12 — `docs/state/DASHBOARD_FIDELITY_AUDIT.md` <a id="section-12-docs-state-dashboard-fidelity-audit-md"></a>

> **Original path:** `docs/state/DASHBOARD_FIDELITY_AUDIT.md`  
> **Source date:** 2026-06-05  
> **Author/Owner:** Devin (architecture review)  
> **Size:** 6,603 bytes  
> **sha256:** `5e552702eda74809412618840dd293dc30e3b5541b572a742c63e551dab39499`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Dashboard data-fidelity audit (2026-05-20): provider keys present; remaining env-alias and provider-auth fidelity gaps.

### Verbatim content

### Dashboard Data Fidelity Audit

**Date:** 2026-05-20
**Author:** Devin (architecture review)
**Revision:** 1 — post-dkeys normalization

#### Context

Provider keys are now present and multiple runtime lanes complete
successfully (OpenRouter, OpenAI, NVIDIA NIM, Ollama, Cerebras confirmed).
Remaining issues are env alias normalization (fixed in this PR), stale
process restart, and provider-specific failures (Groq access-denied,
SiliconFlow/Moonshot auth failures, Anthropic low credits).

This audit maps every dashboard page to its backend endpoint(s) and
assesses data fidelity: does the endpoint return real, meaningful data
when providers are live?

#### Fidelity Categories

| Category | Meaning |
|---|---|
| **LIVE** | Endpoint returns real data from running system state |
| **PROVIDER-GATED** | Endpoint exists and works, but data is sparse until agents dispatch (needs live LLM) |
| **STUB** | Frontend page exists but backend endpoint is missing or returns placeholder |
| **BROKEN** | Endpoint or page has a known bug preventing data flow |

#### Page-by-Page Assessment

##### Tier 1: LIVE (real data flowing now)

| Page | Route | API Endpoint(s) | Status |
|---|---|---|---|
| Control Surface | `/dashboard/control-surface` | `/api/control-surface/rows`, `/api/control-surface/summary` | LIVE — 95 reconciled rows |
| Command Post | `/dashboard/command-post` | `/api/chat/status`, `/api/chat` (SSE) | LIVE — 6 profiles, streaming works |
| Runtime | `/dashboard/runtime` | `/api/health` | LIVE — system health |
| Overview | `/dashboard` | `/api/overview` | LIVE — swarm summary |
| Modules | `/dashboard/modules` | `/api/modules` | LIVE — truth map |
| Conv. Log | `/dashboard/log` | `/api/commands/traces` | LIVE — trace history |
| Claude Chat | `/dashboard/claude` | `/api/chat` | LIVE — profile-specific |
| GLM-5 Chat | `/dashboard/glm5` | `/api/chat` | LIVE — profile-specific |
| Qwen3.5 Chat | `/dashboard/qwen35` | `/api/chat` | LIVE — profile-specific |

##### Tier 2: PROVIDER-GATED (endpoint exists, data sparse until agents run)

| Page | Route | API Endpoint(s) | Status | What populates it |
|---|---|---|---|---|
| Agents | `/dashboard/agents` | `/api/agents`, `/api/agents/spawn` | PROVIDER-GATED | Spawning an agent requires LLM provider |
| Tasks | `/dashboard/tasks` | `/api/commands/tasks` | PROVIDER-GATED | Tasks created by running agents |
| Evolution | `/dashboard/evolution` | `/api/evolution/archive`, `/api/evolution/fitness-trend`, `/api/evolution/dag` | PROVIDER-GATED | DarwinEngine needs agent runs |
| Telemetry | `/dashboard/telemetry` | `/api/telemetry/overview`, `/api/telemetry/routing`, `/api/telemetry/economics`, +5 more | PROVIDER-GATED | Telemetry accumulates from LLM calls |
| Stigmergy | `/dashboard/stigmergy` | `/api/stigmergy/marks`, `/api/stigmergy/heatmap`, `/api/stigmergy/hot-paths`, `/api/stigmergy/high-salience` | PROVIDER-GATED | Marks written by active agents |
| Lineage | `/dashboard/lineage` | `/api/lineage/{id}/dag`, `/api/lineage/{id}/provenance`, `/api/lineage/{id}/impact` | PROVIDER-GATED | Requires artifact IDs from agent runs |
| Ontology | `/dashboard/ontology` | `/api/ontology/types` | PROVIDER-GATED | Types exist but richness depends on agent activity |
| Gates | `/dashboard/gates` | `/api/verify/*` | PROVIDER-GATED | Gate checks run during agent dispatch |
| Audit | `/dashboard/audit` | `/api/verify/*` | PROVIDER-GATED | Same as gates |
| Eval | `/dashboard/eval` | `/api/evolution/*` | PROVIDER-GATED | Eval data from agent fitness scoring |
| Models | `/dashboard/models` | `/api/agents` (model field) | PROVIDER-GATED | Model usage stats from agent runs |
| Qwen3.5 Telemetry | `/dashboard/qwen35/telemetry` | `/api/telemetry/*` | PROVIDER-GATED | Profile-specific telemetry |
| Timeline | `/dashboard/timeline` | `/api/viz/timeline` | PROVIDER-GATED | Time-series from agent events |

##### Tier 3: STUB / MISSING ENDPOINT

| Page | Route | Expected Endpoint | Status | Fix |
|---|---|---|---|---|
| Observatory | `/dashboard/observatory` | `/api/agents/observatory` | **STUB** — endpoint does not exist | Need to implement observatory endpoint in `api/routers/agents.py` |
| Ecosystem | `/dashboard/ecosystem` | `/api/viz/snapshot`, `/api/viz/events` | Partial — viz endpoints exist but ecosystem graph needs ReactFlow data | Wire viz snapshot to ecosystem ReactFlow component |
| Synthesizer | `/dashboard/synthesizer` | Unknown | **STUB** — multi-source aggregation page, no dedicated endpoint | Design synthesizer API |
| Workflows | `/dashboard/workflows` | None | **STUB** — "Coming soon" placeholder | Future work |
| Blocks | `/dashboard/blocks` | None | **STUB** — "Coming soon" placeholder | Future work |

#### Env Alias Mismatches (Fixed in This PR)

| dkeys name | dharma_swarm name | Status |
|---|---|---|
| `GEMINI_API_KEY` | `GOOGLE_AI_API_KEY` | **Fixed** — normalize_env_aliases() + load_runtime_env.sh |
| `NVIDIA_API_KEY` | `NVIDIA_NIM_API_KEY` | **Fixed** — normalize_env_aliases() + load_runtime_env.sh |
| `NIM_API_KEY` | `NVIDIA_NIM_API_KEY` | Already aliased (load_runtime_env.sh) |
| `PERPLEXITY_API_KEY` | `PPLX_API_KEY` | **Fixed** — normalize_env_aliases() + load_runtime_env.sh |

#### Provider Status (from user's local audit)

| Provider | Key Present | Status |
|---|---|---|
| OpenRouter | Yes | **Working** |
| OpenAI | Yes | **Working** |
| NVIDIA NIM | Yes | **Working** |
| Ollama | Yes | **Working** |
| Cerebras | Yes | **Working** |
| Anthropic | Yes | **Low credits** — blocked |
| Groq | Yes | **Access denied** |
| SiliconFlow | Yes | **Auth failure** |
| Moonshot | Yes | **Auth failure** |
| Google AI / Gemini | Yes (as GEMINI_API_KEY) | **Fixed** — alias normalization |

#### Summary

- **9 pages fully LIVE** — producing real data now
- **13 pages PROVIDER-GATED** — endpoints exist, data sparse until agents dispatch (which is now possible with working providers)
- **5 pages STUB** — need backend work (Observatory, Ecosystem wiring, Synthesizer, Workflows, Blocks)
- **4 env alias mismatches** — 3 fixed in this PR, 1 already handled

#### Recommended Next Actions

1. **Restart stale processes** — Any operator/API process started before dkeys updates needs restart to pick up normalized env vars
2. **Spawn a test agent** — With OpenRouter/OpenAI working, spawn one agent to validate the full pipeline (agent → task → trace → telemetry → dashboard)
3. **Implement `/api/agents/observatory`** — Most impactful missing endpoint
4. **Wire Ecosystem page** — Connect viz snapshot to ReactFlow component

---

## Section 13 — `reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md` <a id="section-13-reports-dashboard-dashboard-wiring-audit-2026-03-19-md"></a>

> **Original path:** `reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md`  
> **Source date:** 2026-03-23  
> **Author/Owner:** AmitabhainArunachala  
> **Size:** 3,573 bytes  
> **sha256:** `a6d59bb66d369f768c385acfb40855ad49b60f9fb3415aa0e875ec1106ea5801`  
> **Grade:** RESOLVED-HIST  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Older dashboard wiring audit (2026-03-19): backend contract mostly live, Claude lane health-check defect. Superseded by DASHBOARD_FIDELITY_AUDIT but kept as historical baseline.

### Verbatim content

### Dashboard Wiring Audit — 2026-03-19

#### Current state

- The dashboard/backend contract is mostly live. The FastAPI surface behind `dashboard/` is not broadly broken.
- Endpoint probe status: overview, agents, health, commands, evolution, ontology, stigmergy, modules, chat status, provider status, eval, audit, observatory, and supervisor routes all returned `200`.
- The immediate operational issue was the Claude lane: the resident Claude profile only treated `claude auth status` as "healthy", so a Max account at model/quota limit still looked available in the UI.

#### What is fully wired

- `dashboard/src/app/dashboard/page.tsx`
- `dashboard/src/app/dashboard/agents/page.tsx`
- `dashboard/src/app/dashboard/agents/[id]/page.tsx`
- `dashboard/src/app/dashboard/audit/page.tsx`
- `dashboard/src/app/dashboard/claude/page.tsx`
- `dashboard/src/app/dashboard/command-post/page.tsx`
- `dashboard/src/app/dashboard/ecosystem/page.tsx`
- `dashboard/src/app/dashboard/eval/page.tsx`
- `dashboard/src/app/dashboard/evolution/page.tsx`
- `dashboard/src/app/dashboard/gates/page.tsx`
- `dashboard/src/app/dashboard/glm5/page.tsx`
- `dashboard/src/app/dashboard/lineage/page.tsx`
- `dashboard/src/app/dashboard/log/page.tsx`
- `dashboard/src/app/dashboard/models/page.tsx`
- `dashboard/src/app/dashboard/modules/page.tsx`
- `dashboard/src/app/dashboard/observatory/page.tsx`
- `dashboard/src/app/dashboard/ontology/page.tsx`
- `dashboard/src/app/dashboard/qwen35/page.tsx`
- `dashboard/src/app/dashboard/stigmergy/page.tsx`
- `dashboard/src/app/dashboard/synthesizer/page.tsx`
- `dashboard/src/app/dashboard/tasks/page.tsx`

#### Intentional placeholders

- `dashboard/src/app/dashboard/blocks/page.tsx`
  Commented placeholder only.
- `dashboard/src/app/dashboard/workflows/page.tsx`
  Commented placeholder only.

#### Partial or thin wiring

- `api/graphql/schema.py`
  Query/subscription TODOs remain.
- `api/routers/graphql_router.py`
  `connection_graph` traversal and `search` semantic search are stubbed or empty.
- `dashboard/src/lib/api.ts`
  `fetchTask()` still fetches all tasks and filters client-side because no individual task endpoint exists.
- `dashboard/src/components/ui/ErrorBanner.tsx`
  Global banner only checks `/api/health`; it does not surface provider-specific degradation.

#### Claude lane findings

- Primary Claude dashboard lane is `resident_claude` and runs through the local Claude CLI, not the Anthropic API key path.
- Previous status logic only asked whether Claude CLI was logged in.
- That means "logged in but capped" looked healthy.

#### Fixes added in this pass

- Added an optional backup profile: `Claude Opus 4.6 Alt`.
- The alt profile uses an isolated Claude CLI home via `DASHBOARD_ALT_CLAUDE_HOME`.
- The backup lane is hidden until that alternate Claude home is actually logged in.
- Added chat status metadata:
  `available`, `availability_kind`, `status_note`.
- Added absolute-path guardrails for alternate Claude homes so the agent keeps using the real swarm state under `/Users/dhyana/.dharma`.
- Added setup notes to `dashboard/README.md` and `.env.template`.

#### Remaining recommended work

- Add provider degradation surfacing to the shared dashboard chrome, not just per-chat error banners.
- Decide whether the alt Claude lane should eventually become a full resident operator instead of the current backup CLI lane.
- Either implement or hide GraphQL/semantic-search surfaces until they return real data.
- Add a dedicated `GET /api/commands/tasks/{id}` endpoint so the frontend stops filtering task lists client-side.

---

## Section 14 — `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md` <a id="section-14-docs-research-palantir-ontology-vocabulary-census-andon-reconciliation-md"></a>

> **Original path:** `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md`  
> **Source date:** 2026-06-05  
> **Author/Owner:** —  
> **Size:** 11,855 bytes  
> **sha256:** `b11903ac868ce33ffdbdfb990d787c590cf17d45fed0d64c797d631c9c4fae70`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Andon reconciliation (Codex audit vs ground truth): verdict matrix. Load-bearing finding — ontology.py:594-639 execute_action logs success without applying mutations; InterruptGate auto-approve at cascade.py:36.

### Verbatim content

### Andon Reconciliation — Codex Audit vs Repo Ground Truth

**Reconciled by:** perplexity-computer
**At:** 2026-06-01T06:50Z
**Inputs:** verdicts/perplexity-A.md (identity), verdicts/perplexity-B.md (envelopes), verdicts/perplexity-C.md (authority+execution)
**Branch:** perplexity-grounding/1780289724-vocabulary-census
**Andon state:** verdicts in; reconciliation drafted; cord ready for operator close decision.

This document is **not** a doctrine update. It is a single-source-of-truth summary of what the Codex audit got right, what it got wrong, what it missed, and what (if anything) Layer-2 Revision 3 should name.

---

#### Headline pattern across A + B + C

**Codex is directionally correct on fragmentation, but evidentially sloppy.** It pattern-matches on the smell of duplication and is right that the repo has real ID/envelope sprawl. But it (a) hallucinates names (`correlation_key`, "spec envelope", `nats_a2a_bridge.py`), (b) miscounts (NATS wire formats, the 8th envelope, the 4-way `claim_id` collision it listed as one), (c) confuses domain stores with ontology authorities (C1), and (d) audits its own **untracked working-tree files** as if they were repo state (C4). Net: the audit is a usable smoke signal pointing roughly at real engineering debt, not a reliable specification of that debt.

---

#### Verdict matrix (one row per Codex claim)

| # | Codex claim | Slice verdict | Reality (cite) |
|---|---|---|---|
| 1 | 10+ incompatible ID schemes | **partially_confirmed** | A — 13 surfaces real. `correlation_id` is *aliased to `trace_id`* by `spine/__init__.py:15-24` and `spine/receipt.py:94-96` (Codex missed this). `correlation_key` does not exist (`verdicts/perplexity-A.md` table row). `claim_id` quietly fragments into 4 surfaces with 4 generators — *worse than Codex claimed*, Codex listed it once. |
| 2 | 7 envelope schemas, pairwise incompatible | **partially_confirmed** | B — 6 of 7 confirmed and only 3 of 15 pairwise paths have translators (real sparse bridging). 7th "spec envelope" does not exist as code. NATS undercounted — there are at least 3 ad-hoc wire formats. An 8th envelope (`CanonicalEvent` at `dharma_swarm/engine/events.py:58`) was missed by Codex entirely. |
| 3 | 5–7 ontology stores claim authority | **overstated** | C1 — single two-layer stack: `OntologyRegistry` (in-memory) + `OntologyHub` (SQLite), accessed through one shared singleton `get_shared_registry()` (`ontology_runtime.py:116`). Codex counted domain stores (`ArtifactStore`, `CheckpointStore`, etc.) as ontology authorities. They are not. |
| 4 | `execute_action` at `ontology.py:637` logs success without applying mutations | **confirmed** | C2 — `ontology.py:594-639` sets `result="success"` unconditionally, never reads `ActionDef.modifies`, never calls `update_object`. No test asserts mutation. **This is real and is the load-bearing engineering finding of the entire audit.** |
| 5 | InterruptGate auto-approves without handler (toy) | **partially_confirmed** | C3 — production singleton at `cascade.py:36` is wired `callback=None, auto_approve=True`. A full callback+timeout+filesystem path exists in the class (`checkpoint.py:114-119`). Codex's "toy" framing is lazy; the architectural primitive is there, the wiring choice in production is the gap. |
| 6 | A2A is both external protocol and internal work queue (dangerous conflation) | **not directly verified this round** | Slice E was not picked up by perplexity; goes back to fleet for any agent. |
| 7 | NATS bridge publishes without canonical envelope | **wrong** | C4 — `nats_a2a_bridge.py` is **untracked working-tree code** that has never been on `main` or this branch. Codex audited code that does not exist in the repo. |
| 8 | Multiple workflow-state owners, no `workflowRun` boundary | **not directly verified this round** | Slice D was not picked up by perplexity; goes back to fleet. |

---

#### What Codex MISSED that matters (Slice F findings, pulled from A/B/C side-notes)

1. **`claim_id` 4-way collision (from A).** Four independent surfaces, four generators, zero FKs. Query for `claim_id` in one store has no defined relationship to any other. **This is the single sharpest identity problem in the repo and Codex listed it as one item.**

2. **`agent_id` is type-inconsistent (from A).** Sometimes UUID hex (`AgentConfig.id`), sometimes role name string (`"claude"`, `"orchestrator"`). Same field, different runtime types depending on call site. `AGENT_IDENTITY_UNIFICATION.md` was archived as unfinished.

3. **`CorrelationContext` is voluntary, not enforced (from A).** A real unification layer exists at `correlation_context.py:113-155` but no ID-bearing struct (`DelegationRun`, `A2ATask`, `TaskClaim`) reads from it on construction. The unification is theoretical.

4. **`idempotency_key` has two incompatible generators (from A).** `_new_id("idem")` (random UUID) on the board side; `_stable_id(...)` (SHA-256 of content) on memory-promotion side. Same name, structurally incompatible — a random key cannot replay-dedupe; a hash key cannot be found by random lookup.

5. **`trace_id` has two generators on the A2A path (from A).** `correlation_context._new_trace_id()` produces `trc_<hex>`; `A2ATask.trace_id` defaults to empty string. Correlation chain breaks silently when A2A is in the loop.

6. **`CanonicalEvent` exists and is uncatalogued (from B).** A real 8th envelope at `dharma_swarm/engine/events.py:58`.

7. **NATS wire fragmentation is 3+, not 1 (from B).** Codex named NATS as one envelope; the bus actually carries 3+ ad-hoc dict shapes.

---

#### Implications for Layer-2 Revision 3 (field-bridge types)

Now I can answer the question that triggered the andon — *should Revision 3 of PROPOSED_VOCABULARY.md add field-bridge types?* For each candidate I had on the table:

##### `executionIdentity` (unified ID model) — **PROCEED, but re-scope**

- ✅ Justified by A. 13 surfaces are real.
- 🔄 Re-scope: the headline isn't "many ID names." It's that **(i)** `claim_id` fragments 4 ways with no FK contract, **(ii)** `CorrelationContext` exists but is voluntary, **(iii)** `agent_id` is type-inconsistent. A field-bridge type named `executionIdentity` should *name the contract that `CorrelationContext` already tries to be* — making the voluntary mechanical.
- 🔗 Field invariant: A2A `Task.id` / LangGraph `thread_id` / Temporal `WorkflowExecution.RunId` / OpenTelemetry `trace_id`. All of these are versions of the same concept (a durable boundary for a unit of execution). Naming `executionIdentity` does what John asked — bridges the field invariant *and* names what dharma_swarm already half-built.

##### `runEnvelope` (canonical wire envelope) — **PROCEED**

- ✅ Justified by B. 6 real envelopes, sparse bridging (3/15 translators), 3+ NATS wire shapes, 8th envelope uncatalogued.
- 🔗 Field invariant: A2A message envelope / LangGraph `BaseMessage` / Temporal `Payload` / NATS message + headers / OpenTelemetry `Span` attributes. Real cross-protocol convergence.

##### `workflowRun` (durable execution boundary) — **DEFER pending Slice D**

- ⚠️ Slice D was not verified this round (no agent picked it up). The "no `workflowRun` boundary" claim is unverified.
- 🔍 Action: get Slice D verdict before naming this. `DelegationRun` at `runtime_state.py:368` may already be the boundary, in which case the move is renaming, not inventing.

##### `authority` (meta-type declaring canonical owner per Layer-2 object) — **KILL**

- ❌ C1 invalidates this. There is one canonical ontology stack with a singleton accessor. The "5–7 authorities" rhetoric was Codex misreading domain stores. No need for a meta-type to declare what's already singular.

##### Binding fix for `actionDefinition` + `gateDecision` — **CRITICAL, NOT A NEW TYPE**

- C2 is the real bug. The existing `actionDefinition.modifies` is declared but **not read** by `execute_action`. The existing `gateDecision` passes but **mutation never fires**. This is Layer 1.5 (binding) work, not Layer 2 (naming).
- 🔧 The right move: keep the Revision 2 types, file a separate engineering ticket against `ontology.py:594-639` to honor `ActionDef.modifies`. **Do not invent a new type to solve a binding bug.**

##### `interrupt` / `humanReview` — **PROCEED narrowly**

- C3 verdict is mixed. The class exists; production wiring pins auto-approve. A field-bridge type `humanReview` (or `interrupt`) matching LangGraph's `interrupt` / Temporal's `Signal` / A2A's `input-required` state would name the contract production should adopt.

##### `subject` / `stream` (NATS event-channel) — **DEFER**

- B revealed NATS wire fragmentation but didn't reveal a missing event-channel concept. Subjects exist; envelopes don't. Address envelope (`runEnvelope`) first.

##### `trace` / `causalLink` (OpenTelemetry invariant) — **MERGE into `executionIdentity`**

- A showed `trace_id` is already aliased to `correlation_id` by the spine. The bridge type is already half-named. Fold this into the `executionIdentity` contract; don't proliferate.

##### `toolBinding` (MCP-era invariant) — **OUT OF SCOPE this round**

- Nothing in the audit or the verdicts touches MCP. Defer.

---

#### Final Revision-3 shape (proposed, conditional on operator approval)

If the operator closes the andon and authorizes Revision 3, the change set is:

**Add (3 new types, narrowly scoped):**

1. `executionIdentity` — names the contract `CorrelationContext` already half-implements, plus `claim_id` deduplication policy. Field invariant: A2A `Task.id` / LangGraph `thread_id` / Temporal `RunId` / OpenTelemetry `trace_id`.
2. `runEnvelope` — canonical wire envelope. Field invariant: A2A message / LangGraph `BaseMessage` / NATS message + headers.
3. `humanReview` (or `interrupt`) — names the existing InterruptGate's intended contract. Field invariant: LangGraph `interrupt` / Temporal `Signal` / A2A `input-required`.

**Defer (pending slices D, E):**

4. `workflowRun` — needs Slice D verdict on workflow-state ownership.

**Kill:**

5. `authority` meta-type — C1 invalidates.

**File as engineering ticket, not vocabulary:**

6. C2 binding bug — `execute_action` does not honor `ActionDef.modifies`. Separate PR; Revision 2 types are correct; the implementation needs to catch up.

**Out of scope this round:**

7. `toolBinding`, `subject`/`stream`, separate `trace`/`causalLink` (folded into `executionIdentity`).

---

#### What the operator needs to decide

1. **Close andon?** Three out of six slices have verdicts (A, B, C). Slices D (workflow-state) and E (A2A external/internal collision) were not picked up by perplexity-computer this round; no other agent has posted a verdict yet. **Option (i):** close andon now and ship narrow Revision 3 (add `executionIdentity`, `runEnvelope`, `humanReview`; defer `workflowRun`). **Option (ii):** keep andon open another tick to wait for D/E verdicts from claude/devin/hermes/mike before finalizing.
2. **File C2 separately?** The mutation-binding bug is real engineering debt that should not block vocabulary work. Recommend filing as separate issue against `ontology.py:637`.
3. **Field-invariant naming check:** the three proposed names (`executionIdentity`, `runEnvelope`, `humanReview`) are deliberately chosen to match A2A / LangGraph / Temporal / OpenTelemetry vocabulary while also naming what dharma_swarm already half-built. Operator approval needed on the names themselves before they enter PROPOSED_VOCABULARY.md.

---

#### What we will NOT do without operator approval

- Will not amend `PROPOSED_VOCABULARY.md`.
- Will not file the C2 binding bug as a separate PR (operator decides whether to scope it that way).
- Will not extend the andon scope or reopen verdicts already accepted.
- Will not declare Codex's untracked working-tree code (C4 ghost files) as repo state, ever.

---

## Section 15 — `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-A.md` <a id="section-15-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-perplexity-a-md"></a>

> **Original path:** `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-A.md`  
> **Source date:** 2026-06-05  
> **Author/Owner:** perplexity-computer  
> **Size:** 17,717 bytes  
> **sha256:** `f1f3e1e8ce1d880b1875aad25f83daf9d1300ea55700c1c2027c3e8935594c77`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Andon slice A (identity sprawl) evidence backing the reconciliation.

### Verbatim content

### Slice A Verdict — Identity Schemes
**Agent:** perplexity-computer  
**Branch:** perplexity-grounding/1780289724-vocabulary-census  
**Verified at:** 2026-06-01  
**Method:** `grep -rn` across `dharma_swarm/` (Python source only). No editorializing without citation.

---

#### ID Inventory Table

| id_name | defined_at (file:line) | type | primary_consumers | cross_references_to | verdict |
|---|---|---|---|---|---|
| `task_id` (as field) | `dharma_swarm/models.py:156` (`Task.id`) · `dharma_swarm/runtime_state.py:368` (`DelegationRun.task_id`) · `dharma_swarm/contracts/common.py:55` (`RunDescriptor.task_id`) | `str` (bare uuid hex, no prefix; generated by `_new_id()` at `models.py:150`) | `agent_runner.py`, `orchestrator.py`, `telic_seam.py`, `ecc_eval_harness.py`, `a2a_bridge.py`, `contracts/runtime_adapters.py` | `run_id`, `claim_id`, `A2ATask.dharma_task_id` | `truly_distinct` |
| `run_id` | `dharma_swarm/runtime_state.py:387` (`DelegationRun.run_id`) · `dharma_swarm/contracts/common.py:55` (`RunDescriptor.run_id`) · `dharma_swarm/artifact_manifest.py:54` | `str` (prefix `run_` via `RuntimeState.new_run_id()` at `runtime_state.py:2030`) | `context_compiler.py`, `artifact_store.py`, `contracts/intelligence_adapters.py`, `contracts/intelligence_evaluation_services.py` | `task_id`, `claim_id`, `parent_run_id`, `holder_run_id` | `truly_distinct` |
| `thread_id` | `dharma_swarm/gateway/base.py:36` (`GatewayEvent.thread_id`) · `dharma_swarm/tui/screens/btw.py:100` (local var `self._thread_id`) | `str \| None` (Telegram message thread ID, or a local `btw-{timestamp}-{hex}` string) | `gateway/telegram.py:126`, `gateway/runner.py:177`, `tui/screens/btw.py:242` (reused as `session_id`) | `session_id` (aliased in `btw.py:242`) | `truly_distinct` — Telegram-domain concept, not a swarm-execution ID |
| `claim_id` (TaskClaim) | `dharma_swarm/runtime_state.py:352` (`TaskClaim.claim_id`) | `str` (generated by `RuntimeState.new_claim_id()` at `runtime_state.py:2036`, prefix `clm_`) | `runtime_lifecycle.py`, `operator_bridge.py`, `opportunity_dispatcher.py`, `contracts/runtime_adapters.py:168`, `spine/receipt.py` | `task_id`, `agent_id`, `session_id` | `truly_distinct` — runtime mutual-exclusion lock on a `Task` |
| `claim_id` (DharmaCorpus) | `dharma_swarm/dharma_corpus.py:93` (`Claim.id`, format `DC-YYYY-NNNN`) | `str` (sequential human-readable, assigned by `DharmaCorpus.propose()` at `dharma_corpus.py:217`) | `claim_graph.py`, `context.py`, `semantic_governance.py`, `dgc_cli.py:634` | none (self-contained corpus; `claim_graph.py` references `.id` not `claim_id`) | `duplicated` — same name, completely different domain: `TaskClaim.claim_id` is a runtime mutex; `DharmaCorpus.Claim.id` is an ethical-corpus identifier. No shared type, no shared generator. |
| `claim_id` (auto_research) | `dharma_swarm/auto_research/models.py:80` (`ClaimRecord.claim_id`) | `str` (generated as `f"{brief.task_id}-claim-{len(claims)+1}"` at `auto_research/claim_graph.py:37`) | `auto_research/claim_graph.py` only | `task_id` (embedded in value) | `duplicated` — third distinct `claim_id` surface: derives from `task_id`, uses neither `DC-YYYY-NNNN` format nor `clm_` prefix |
| `claim_id` (DecisionOntology) | `dharma_swarm/decision_ontology.py:106` (`DecisionClaim.claim_id`) | `str` (generated by local `_new_id()` at `decision_ontology.py:30`, bare uuid hex) | `decision_ontology.py` internally only | none | `duplicated` — fourth surface, fourth generator |
| `event_id` | `dharma_swarm/board/event_log.py:64` (`BoardEvent.event_id`, `NewType EventId`) · `dharma_swarm/board/facade.py:118` | `EventId` = `NewType("EventId", str)` (prefix `evt_` via `_new_id("evt")` at `contracts/intelligence_evaluation_services.py:22`) | `board/event_log.py`, `board/facade.py`, `board/models.py`, `contracts/intelligence_evaluation_services.py`, `engine/event_memory.py` | `card_id`, `idempotency_key`, `trace_id` | `truly_distinct` |
| `source_event_id` / `source_event_ids` | `dharma_swarm/artifact_manifest.py:60` · `dharma_swarm/contracts/intelligence_adapters.py:262` | `str` / `list[str]` (opaque reference, no fixed generator) | `artifact_store.py`, `contracts/intelligence_adapters.py`, `contracts/intelligence_evaluation_services.py` | `event_id` (by convention, not enforced) | `truly_distinct` — a provenance back-pointer, not a unique event key itself |
| `correlation_id` | `dharma_swarm/economic_engine.py:82` (`Transaction.correlation_id`) · `dharma_swarm/operator_core/closure_v0.py:44,65,84,103,117,126` (multiple closure structs) · `dharma_swarm/spine/__init__.py:15,24` (doc) | `str` (in `economic_engine`: aliased from `correlation_context.trace_id` at `economic_engine.py:168-172`; in `closure_v0`: caller-supplied; in `spine`: documented alias for `trace_id`) | `economic_engine.py`, `closure_v0.py`, `spine/receipt.py:94-96` | `trace_id` (explicit alias in `spine/receipt.py:94-96` and `economic_engine.py:168`) | `aliased` — not an independent ID. `spine/receipt.py:94` explicitly documents: *"on the dispatch layer it is `trace_id`"*; `economic_engine._get_correlation_id()` returns `get_correlation().trace_id`. The closure_v0 layer assigns its own value but the `spine` contract mandates it must equal `trace_id` across layers. |
| `idempotency_key` | `dharma_swarm/board/event_log.py:77` (`BoardEvent.idempotency_key`) · `dharma_swarm/board/models.py:130,173` · `dharma_swarm/economic_engine.py:81` · `dharma_swarm/knowledge_ops/memory_promotion_executor.py:70,96` | `str` (generated via `_new_id("idem")` at `board/facade.py:96`; or `_stable_id(...)` at `memory_promotion_executor.py:327,345`; or caller-supplied in `economic_engine`) | `board/adapters/taskboard_adapter.py`, `board/facade.py`, `economic_engine.py`, `memory_promotion_executor.py` | `event_id` (co-located on `BoardEvent`); `receipt_id` (co-located on promotion executor) | `truly_distinct` — deduplication key, not an entity identity. Two different generation strategies (`_new_id` vs `_stable_id` hash) exist in the same codebase with no shared interface. |
| `lease_id` | `dharma_swarm/runtime_state.py:387` (`WorkspaceLease.lease_id`) · `dharma_swarm/board/models.py:82` (`ClaimLease.lease_id`, `NewType LeaseId`) | `str` in `WorkspaceLease` (prefix `lease_` via `RuntimeState.new_lease_id()` at `runtime_state.py:2033`); `LeaseId = NewType("LeaseId", str)` in `board/models.py` | `runtime_state.py`, `context_compiler.py:523`, `flywheel_exporter.py:582` | `holder_run_id` (FK to `run_id`), `card_id`, `agent_id` | `duplicated` — two `lease_id` surfaces: `WorkspaceLease` (filesystem zone lock) and `ClaimLease` (board card mutual exclusion). Both generate with prefix `lease_`; neither references the other. |
| `proposal_id` | `dharma_swarm/auto_proposer.py:104` (optional field) · `dharma_swarm/autoresearch_loop.py:118` · `dharma_swarm/correlation_context.py:65` (`CorrelationContext.proposal_id`) · `dharma_swarm/evolution.py:193` | `str` (stored as bare `.id` from an `ActionProposal` ontology object; see `telic_seam.py:97-130`) | `correlation_context.py`, `telic_seam.py`, `agent_runner.py:2155-2166`, `evolution.py` | `task_id` (via `telic_seam._proposal_map: task_id -> proposal_id` at `telic_seam.py:78`) | `truly_distinct` — ontology-layer action identity; bridged to `task_id` by `TelicSeam._proposal_map` but that map is in-memory only with no persistence guarantee |
| `contribution_id` | `dharma_swarm/telic_seam.py:478` (return value of `record_contribution()`) · `dharma_swarm/trace_attractor/models.py:203` | `str` (ontology object `.id` generated by `OntologyRegistry.create_object("Contribution", ...)`) | `telic_seam.py:686`, `trace_attractor/projector.py:150,215,240` | `value_event_id`, `agent_id`, `task_id` (via proposal chain) | `truly_distinct` |
| `correlation_key` | **not found** anywhere in `dharma_swarm/` Python source or any `.md` file (only in the andon brief itself) | n/a | n/a | n/a | `obsolete` — Codex named this; it does not exist in the codebase |
| `agent_id` | `dharma_swarm/models.py:AgentConfig.id` (not called `agent_id`) · `dharma_swarm/board/models.py:21` (`AgentId = NewType(...)`) · `dharma_swarm/active_inference.py:73,94,125` · `dharma_swarm/agent_memory_manager.py:62` · `dharma_swarm/contracts/common.py:58,83` | `str` (bare uuid hex or caller-supplied name string; `AgentConfig.id` uses `_new_id()` at `models.py:150`; elsewhere plain string like `"claude"`) | Nearly all modules | `task_id`, `claim_id`, `run_id`, `contribution_id` | `truly_distinct` — but **type-inconsistent**: sometimes a UUID hex (from `AgentConfig.id`), sometimes a role name string like `"orchestrator"` or `"claude"` (see `telic_seam.py:109` `agent_id=agent_id` where value comes from `AgentRunner.agent_id` which returns a name string at `agent_runner.py:1654`) |
| `A2ATask.id` | `dharma_swarm/a2a/a2a_server.py:211` (`A2ATask.id`, `default_factory=lambda: uuid.uuid4().hex[:16]`) | `str` (16-hex, no prefix) | `a2a_server.py`, `a2a_client.py`, `node_gateway.py`, `a2a_bridge.py` | `dharma_task_id` (FK: `A2ATask.dharma_task_id` at `a2a_server.py:217` maps to `Task.id`) · emitted as `"task_id"` key in NATS signals at `a2a_bridge.py:173,276` | `truly_distinct` — A2A protocol-scoped task identity. The field `dharma_task_id` is the explicit cross-reference to the swarm `Task.id`, but it is optional (`str = ""`), so the link is non-mandatory. |
| `context_id` | `dharma_swarm/a2a/a2a_server.py:209` (`A2ATask.context_id`) · `dharma_swarm/a2a/a2a_client.py:143` | `str` (server-generated, groups related A2A tasks per A2A 1.0 spec) | `a2a_client.py` (delegation-chain loop guard), `spine/receipt.py:42` (`EvidenceReceipt.context_id`) | none explicit | `truly_distinct` — A2A 1.0 session grouping, unrelated to `CorrelationContext.session_id` despite overlapping semantics |
| `session_id` | `dharma_swarm/artifact_manifest.py:48` · `dharma_swarm/contracts/common.py:56` · `dharma_swarm/correlation_context.py:62` · `dharma_swarm/runtime_state.py:340` (`SessionState`) | `str` (format varies: `"opp-{uuid4}"` at `opportunity_dispatcher.py:133`, `"provider-smoke-{uuid4}"` at `provider_smoke.py:340`, `f"btw-{timestamp}-{hex}"` at `tui/screens/btw.py:100`) | Virtually all modules | `run_id`, `task_id`, `trace_id` | `truly_distinct` — but **format is uncontrolled**: no single generator, no enforced prefix |
| `trace_id` | `dharma_swarm/correlation_context.py:52` (`CorrelationContext.trace_id`, `default_factory=_new_trace_id` with prefix `trc_`) · `dharma_swarm/spine/receipt.py:38` (`EvidenceReceipt.trace_id`) · `dharma_swarm/a2a/a2a_server.py:222` (`A2ATask.trace_id`) | `str` (prefix `trc_{uuid4().hex[:16]}` via `correlation_context._new_trace_id`) | `board/event_log.py`, `artifact_manifest.py`, `artifact_store.py`, `fractal/room_bridge.py`, `spine/receipt.py`, `a2a_server.py` | `correlation_id` (aliased per `spine/__init__.py:20`) | `aliased` to `correlation_id` at the spine layer; genuinely independent generators in `a2a_server.py` (no prefix, no factory) vs. `correlation_context.py` (prefix `trc_`) — meaning two `trace_id` values on the same request may not match |
| `receipt_id` | `dharma_swarm/spine/receipt.py:41` (`EvidenceReceipt.receipt_id`, type `UUID`) · `dharma_swarm/board/models.py:111` (`ReceiptId = NewType("ReceiptId", str)`) · `dharma_swarm/knowledge_ops/memory_promotion_executor.py:94` · `dharma_swarm/memory_kernel/burn_in.py:25` · `dharma_swarm/operator_core/closure_v0.py:64` | `UUID` in `spine/receipt.py`; `str` everywhere else | `spine/receipt.py`, `board/models.py`, `memory_kernel/`, `operator_core/closure_v0.py`, `recursive_discovery.py` | none explicit | `duplicated` — five separate `receipt_id` surfaces with no shared FK and mismatched types (`UUID` vs `str`) |

---

#### Headline Verdict for Slice A

**`partially_confirmed`**

Codex's count of "10+" incompatible ID schemes is numerically correct — this audit surfaces **at minimum 13 distinct identifier surfaces** in `dharma_swarm/` Python source (`task_id`, `run_id`, `thread_id`, `A2ATask.id`, `event_id`, `idempotency_key`, `lease_id`, `proposal_id`, `contribution_id`, `agent_id`, `context_id`, `session_id`, `receipt_id`), plus `trace_id`/`correlation_id` which are aliased-but-inconsistently-generated. The count is confirmed; the characterization requires qualification:

1. **Confirmed incompatibility**: `claim_id` exists as four independent surfaces (`TaskClaim.claim_id` at `runtime_state.py:352`, `DharmaCorpus.Claim.id` at `dharma_corpus.py:93`, `ClaimRecord.claim_id` at `auto_research/models.py:80`, `DecisionClaim.claim_id` at `decision_ontology.py:106`) with four different generators and zero cross-references. `receipt_id` similarly exists on five surfaces with mismatched types (`UUID` vs `str`). `lease_id` appears on two independent structures (`WorkspaceLease` and `ClaimLease`) with overlapping semantics but no shared registry.

2. **Partially refuted: `correlation_id` is not fully incompatible**. The `spine/receipt.py:94–96` explicitly documents `correlation_id` as an alias for `trace_id` and the `spine/__init__.py:15–24` mandates cross-layer identity continuity. `economic_engine._get_correlation_id()` at `economic_engine.py:168–172` reads from `correlation_context.trace_id`. There IS a partial unification attempt via `CorrelationContext` (`correlation_context.py:52–65`) that carries `trace_id`, `proposal_id`, `session_id`, and `cell_id` together. Codex did not flag this layer.

3. **`correlation_key` does not exist** anywhere in Python source — it is absent, not merely undocumented. Verdict for that specific name: `obsolete` (Codex hallucination or stale reference).

4. **No unified model exists**, confirmed. `CorrelationContext` bridges `trace_id`, `proposal_id`, and `session_id` but does not encompass `task_id`, `run_id`, `claim_id`, `lease_id`, `event_id`, `A2ATask.id`, or `receipt_id`. The `DelegationRun` dataclass at `runtime_state.py:368–383` is the closest structural bridge (holds `run_id`, `task_id`, `claim_id`, `session_id`, `parent_run_id`) but it is a runtime record, not a type-level identity model.

---

#### What I Observed That Codex Did NOT Flag

1. **`claim_id` is a four-way collision, not a single incompatible ID.** Codex listed `claim_id` once. In reality there are four independent `claim_id` surfaces with four generators and zero mutual FK constraints: (a) runtime execution lock (`TaskClaim.claim_id`, prefix `clm_`), (b) ethical corpus (`DharmaCorpus.Claim.id`, sequential `DC-YYYY-NNNN`), (c) research grounding (`auto_research.ClaimRecord.claim_id`, derived from `task_id`), (d) decision record (`DecisionClaim.claim_id`, bare uuid hex). A query on `claim_id` in one store has no defined relationship to any other store. This is the most acute identity collision in the codebase.

2. **`agent_id` is type-inconsistent, not merely duplicated.** `AgentConfig.id` at `models.py:156` is a UUID hex; the same field propagated as `agent_id` in `telic_seam.py:109`, `active_inference.py:73`, and `agent_memory_manager.py:62` can be a human-readable name string (e.g. `"claude"`, `"orchestrator"`) depending on call site. There is a `AGENT_IDENTITY_UNIFICATION.md` that was archived as stale at `/home/user/workspace/ds/AGENT_IDENTITY_UNIFICATION.md` (one-liner: *"Snapshot, do not trust without re-verification"*), indicating the unification effort was never completed.

3. **`trace_id` has two incompatible generators on the same A2A task path.** `CorrelationContext._new_trace_id()` at `correlation_context.py:48` always produces `trc_{uuid4().hex[:16]}`. `A2ATask.trace_id` at `a2a_server.py:222` is `str = ""` (empty default, no factory). When `a2a_bridge.py` maps an A2A task to NATS signals at `a2a_bridge.py:276–286`, it emits both `"task_id": task.id` and the task's `trace_id`; if `trace_id` was never populated, the correlation chain breaks silently with no error.

4. **`idempotency_key` has two structurally different generation strategies with no shared interface.** `board/facade.py:96` uses `_new_id("idem")` (random UUID), which is non-deterministic. `memory_promotion_executor.py:327` uses `_stable_id(prefix, *parts)` (SHA-256 of content), which is deterministic. Both are called `idempotency_key` but one cannot substitute for the other — a random key on replay will not deduplicate; a hash key on the board side will not be found. No abstraction enforces the contract.

5. **`session_id` has no controlled generator.** At least three distinct generation patterns appear: `f"opp-{uuid4().hex[:8]}"` (`opportunity_dispatcher.py:133`), `f"provider-smoke-{uuid4().hex[:12]}"` (`provider_smoke.py:340`), and `f"btw-{datetime:%H%M%S}-{secrets.token_hex(2)}"` (`tui/screens/btw.py:100`). The last is also assigned directly as `session_id=` at `btw.py:242`. No single factory or validator normalizes session IDs; cross-store joins on `session_id` depend on caller discipline, not type enforcement.

6. **`CorrelationContext` is not enforced at any boundary.** The context manager at `correlation_context.py:113–155` and the `contextvars`-based propagation are voluntary. Nothing in `DelegationRun`, `A2ATask`, or `TaskClaim` construction reads from `CorrelationContext`; those structs all take `session_id`/`trace_id` as caller-supplied strings. The unification layer exists but is not mechanically connected to the ID-bearing structs.

---

*Scope note: this audit covered all `.py` files under `dharma_swarm/`. Non-Python config files (YAML, TOML), test files, and scripts outside `dharma_swarm/` were not surveyed. `correlation_key` was also searched repo-wide (`.py` + `.md`) and confirmed absent.*

---

## Section 16 — `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-B.md` <a id="section-16-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-perplexity-b-md"></a>

> **Original path:** `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-B.md`  
> **Source date:** 2026-06-05  
> **Author/Owner:** perplexity-computer  
> **Size:** 14,546 bytes  
> **sha256:** `01cc6870a6b7e9341c0ce36bea55f8618477f9fbc30a9307f7cd333ccba5a52e`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Andon slice B (envelope schemas) evidence backing the reconciliation.

### Verbatim content

### Slice B Verdict — Envelope Schemas

**Agent:** perplexity-computer  
**Slice:** B (Codex claim #2 — "7 envelope schemas, pairwise incompatible")  
**Branch:** perplexity-grounding/1780289724-vocabulary-census  
**Timestamp:** 2026-06-01  
**Verdict:** `partially_confirmed`

---

#### Envelopes Found and Characterized

##### 1. RuntimeEnvelope

**Path:** `dharma_swarm/runtime_contract.py:41–50`

**Fields:**
| Field | Type |
|---|---|
| `contract_version` | `str` |
| `event_id` | `str` |
| `event_type` | `str` |
| `emitted_at` | `str` (ISO-8601) |
| `source` | `str` |
| `agent_id` | `str` |
| `session_id` | `str` |
| `trace_id` | `str` |
| `payload` | `dict[str, Any]` |
| `checksum` | `str` (SHA-256) |

**Purpose:** Append-only, content-addressed event record for the runtime event log (`event_log.py:33`); checksum enforces integrity on write.

**Consumers:** `dharma_swarm/event_log.py`, `dharma_swarm/evaluation_registry.py`, `dharma_swarm/session_event_bridge.py`, `dharma_swarm/flywheel_exporter.py`, `dharma_swarm/memory_lattice.py`, `dharma_swarm/orchestrator.py`, `dharma_swarm/canonical_replay.py`.

---

##### 2. MessageBus row (messages table)

**Path:** `dharma_swarm/message_bus.py:27–35` (DDL); `dharma_swarm/models.py:243–255` (Python model)

**Fields (SQLite DDL → `Message` model):**
| Field | Type |
|---|---|
| `id` | `TEXT` / `str` |
| `from_agent` | `TEXT` / `str` |
| `to_agent` | `TEXT` / `str` |
| `subject` | `TEXT` / `Optional[str]` |
| `body` | `TEXT` / `str` |
| `priority` | `TEXT` / `MessagePriority` |
| `status` | `TEXT` / `MessageStatus` |
| `created_at` | `TEXT` / `datetime` |
| `read_at` | `TEXT` / `Optional[datetime]` |
| `reply_to` | `TEXT` / `Optional[str]` |
| `metadata` | `TEXT` (JSON) / `dict[str, Any]` |

**Purpose:** Agent-to-agent async message store (SQLite-backed pub/sub); carries durable inter-agent tasks and notifications.

**Note:** `MessageBus` also has an `events` sub-table (`message_bus.py:57–67`) with a distinct 7-column schema (`event_id`, `event_type`, `task_id`, `agent_id`, `source_pid`, `occurred_at`, `payload`). This is a second flat schema living inside the same SQLite file. It does NOT overlap with `RuntimeEnvelope`.

---

##### 3. A2ATask

**Path:** `dharma_swarm/a2a/a2a_server.py:184–233`

**Fields:**
| Field | Type |
|---|---|
| `id` | `str` (hex, 16 chars) |
| `context_id` | `str` |
| `from_agent` | `str` |
| `to_agent` | `str` |
| `status` | `A2ATaskStatus` (8 states) |
| `history` | `list[A2AMessage]` |
| `messages` | `list[A2AMessage]` (alias of history) |
| `artifacts` | `list[A2AArtifact]` |
| `capability` | `str` |
| `dharma_task_id` | `str` |
| `created_at` | `str` (ISO-8601) |
| `updated_at` | `str` (ISO-8601) |
| `result` | `str` |
| `error` | `str` |
| `trace_id` | `str` |
| `extensions` | `list[A2AExtension]` |
| `metadata` | `dict[str, Any]` |

**Purpose:** A2A 1.0 spec-conformant work unit — the primary inter-agent task container for request/response lifecycle and artifact delivery.

---

##### 4. OnboardingReceipt (A2A receipt schema)

**Path:** `dharma_swarm/roaming_onboarding.py:101–113`

**Fields:**
| Field | Type |
|---|---|
| `receipt_id` | `str` |
| `agent_uid` | `str` |
| `callsign` | `str` |
| `team_id` | `str` |
| `department` | `str` |
| `squad_id` | `str` |
| `harness` | `str` |
| `endpoint` | `str` |
| `dock_path` | `str` |
| `card_path` | `str` |
| `telemetry_db_path` | `str` |
| `receipt_path` | `str` |
| `created_at` | `str` (ISO-8601) |

**Purpose:** Frozen onboarding paper trail written once per agent registration; consumed by `registry_hydrator.py` to populate `NodeRegistry`.

---

##### 5. NATS contact envelope

**Actual location:** `/home/user/workspace/nats/` — **not** inside `dharma_swarm/`. There is no Python NATS client library in `dharma_swarm/` at all (`dharma_swarm/a2a/node_gateway.py:20` lists "gRPC / NATS transport bindings (Tier 2)" as **not yet implemented**).

NATS envelopes are bare-text or ad hoc JSON dicts assembled in `/home/user/workspace/nats/`.

**Two formats observed:**

**a) Text-header format** (`nats/a2a_client.py:44`):
```
[perplexity->claude] <ISO-timestamp>\n<body>
```
Fields: routing header (prefix string), freeform body. No typed schema.

**b) Structured JSON dict** (`nats/_andon_broadcast.py:16–32`):
| Field | Type |
|---|---|
| `kind` | `str` |
| `severity` | `str` |
| `from` | `str` |
| `to` | `str` |
| `at` | `str` |
| `subject_line` | `str` |
| `branch` | `str` |
| `...` | various |

**c) Presence beacon** (`nats/presence_heartbeat.py:50–63`):
| Field | Type |
|---|---|
| `agent` | `str` |
| `callsign` | `str` |
| `version` | `str` |
| `role` | `str` |
| `subscribes` | `list[str]` |
| `publishes` | `list[str]` |
| `pid` | `int` |
| `host` | `str` |
| `ts` | `str` |
| `uptime_s` | `int` |
| `beacon_seq` | `int` |

**Purpose:** Inter-process fleet coordination over the agni VPS NATS broker. No schema enforcement — Codex's claim that there is a single "NATS contact envelope" understates the fragmentation: there are at least three ad hoc shapes on the wire.

---

##### 6. SignalBus dict

**Path:** `dharma_swarm/signal_bus.py:95–113`

**Schema:** Untyped `dict[str, Any]` with one mandatory key:
| Field | Type |
|---|---|
| `"type"` | `str` (e.g. `"ANOMALY_DETECTED"`, `"LIFECYCLE_TASK_STARTED"`) |
| `*` | arbitrary — caller-defined additional keys |

**Example shapes from call sites:**
- `agent_runner.py:2431`: `{"type": "LIFECYCLE_TASK_STARTED", "agent": str, "task_id": str, "task_title": str, "timestamp": str}`
- `a2a_bridge.py:269`: `{"type": str, "task_id": str, "from": str, "to": str, "capability": str, "status": str}`

**Purpose:** In-process synchronous loop-to-loop heartbeat bus (single asyncio event loop); explicitly NOT the inter-agent message bus (`signal_bus.py:1–12`).

---

##### 7. "Spec envelope" — NOT FOUND as a code artifact

Codex lists a "spec envelope" as the 7th schema. No Python class, dataclass, or Pydantic model named `SpecEnvelope` or similar exists in the repo. Three candidate interpretations were checked:

- `ControlSurfaceEnvelope` (`dharma_swarm/operator_core/control_surface_models.py:98`): an API **response wrapper** (`schema_version`, `request_id`, `generated_at`, `source_errors`, `freshness_window`, `data`) used only by the control surface API router. This is plausible as Codex's intended "spec envelope."
- `CanonicalEvent` (`dharma_swarm/engine/events.py:58`): a provider-neutral LLM event envelope used internally by `dharma_swarm/engine/`. Fields: `event_type`, `timestamp`, `event_id`, `source_agent`, `target_agent`, `session_id`, `artifact_id`, `payload`, `metadata`.
- Spec documents (`docs/architecture/SWARM_BOARDSTORE_SPEC.md`, `docs/architecture/SHAKTI_GINKO_ORGAN.md`): describe envelope shapes in prose/table but contain no code artifacts.

**The 7th "spec envelope" is unidentified as a distinct code artifact.** If Codex meant `ControlSurfaceEnvelope`, that schema is an API response wrapper — a different concern from the 6 message-carrying envelopes.

---

#### Field Overlap Table

Rows = fields; columns = envelopes. ✓ = present, — = absent.

| Field | RuntimeEnvelope | MessageBus `messages` | A2ATask | OnboardingReceipt | NATS (JSON) | SignalBus dict |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `id` / `event_id` / `receipt_id` | ✓ (`event_id`) | ✓ (`id`) | ✓ (`id`) | ✓ (`receipt_id`) | — | — |
| `from_agent` / `from` | — | ✓ (`from_agent`) | ✓ (`from_agent`) | — | ✓ (`from`) | — |
| `to_agent` / `to` | — | ✓ (`to_agent`) | ✓ (`to_agent`) | — | ✓ (`to`) | — |
| `created_at` / `emitted_at` / `at` / `ts` | ✓ (`emitted_at`) | ✓ (`created_at`) | ✓ (`created_at`) | ✓ (`created_at`) | ✓ (`at`/`ts`) | — |
| `agent_id` / `agent` | ✓ (`agent_id`) | — | — | ✓ (`agent_uid`) | ✓ (`agent`) | ✓ (`agent`) |
| `session_id` | ✓ | — | — | — | — | — |
| `trace_id` | ✓ | — | ✓ | — | — | — |
| `payload` / `body` / `metadata` | ✓ (`payload`) | ✓ (`body`+`metadata`) | ✓ (`metadata`) | — | ✓ (body) | ✓ (free keys) |
| `checksum` | ✓ | — | — | — | — | — |
| `status` | — | ✓ (`status`) | ✓ (`status`) | — | — | — |
| `type` / `event_type` | ✓ (`event_type`) | — | — | — | ✓ (`kind`) | ✓ (`type`) |
| `source` / `callsign` | ✓ (`source`) | — | — | ✓ (`callsign`) | ✓ (`from`) | — |
| `contract_version` | ✓ | — | — | — | — | — |
| `endpoint` | — | — | — | ✓ | — | — |
| `history` / `artifacts` | — | — | ✓ | — | — | — |
| `capability` | — | — | ✓ | — | — | — |
| `dharma_task_id` | — | — | ✓ | — | — | — |

**Observations:**
- No two envelopes share a common required field set. `trace_id` overlaps only `RuntimeEnvelope` ↔ `A2ATask`.
- `from_agent` / `to_agent` routing appears in `MessageBus.messages`, `A2ATask`, and NATS — three independent namings of the same semantic with no shared type.
- `RuntimeEnvelope` is the only schema with a `checksum` integrity field.
- `SignalBus` is the only schema with no identity field at all.

---

#### Translator Inventory

The following code paths translate **between** envelope types:

| Path | From | To | File:line |
|---|---|---|---|
| `A2ABridge.trishula_message_to_a2a_task` | TRISHULA `dict` (file-based) | `A2ATask` | `dharma_swarm/a2a/a2a_bridge.py:74` |
| `A2ABridge.a2a_task_to_trishula_message` | `A2ATask` | TRISHULA `dict` | `dharma_swarm/a2a/a2a_bridge.py:187` |
| `A2ABridge._emit_signal` | `A2ATask` fields | `SignalBus` dict | `dharma_swarm/a2a/a2a_bridge.py:263–283` |
| `SessionEventBridge.session_start / session_interaction / session_end` | `SessionEvent` | `RuntimeEnvelope` | `dharma_swarm/session_event_bridge.py:51+` |
| `MessageBusGatewayAdapter` | `Message` (MessageBus row) | gateway message dict | `dharma_swarm/contracts/runtime_adapters.py:519` |
| `RuntimeInteropAdapter.export_snapshot` | `RuntimeEnvelope` + `Message` + A2A | flat dict snapshot | `dharma_swarm/contracts/runtime_adapters.py:783` |
| `hydrate_from_receipts` | `OnboardingReceipt` JSONL | `RemoteNode` in `NodeRegistry` | `dharma_swarm/a2a/registry_hydrator.py:79` |

**Gaps — no translator found:**
- `RuntimeEnvelope` → `A2ATask`: no code path. A `RuntimeInteropAdapter` snapshot includes both but does not map fields one-to-one.
- `RuntimeEnvelope` → `SignalBus` dict: no code path.
- `MessageBus.messages` row → `A2ATask`: no code path. `A2ABridge` converts TRISHULA file-inbox messages, not `MessageBus` rows.
- `OnboardingReceipt` → any of the 5 other envelopes: no code path beyond registry hydration.
- NATS wire formats → any internal envelope: no code path in `dharma_swarm/`; NATS lives entirely in `/home/user/workspace/nats/`.

---

#### Headline Verdict for Slice B

**`partially_confirmed`** — and leaning toward **`incompatible-and-unbridged`**.

**Confirmed:** 6 of the 7 envelopes exist and are genuinely incompatible (no shared type signature, no common required field set). `A2ABridge` translates TRISHULA↔A2ATask and emits A2ATask events to `SignalBus`; `SessionEventBridge` translates session events into `RuntimeEnvelope`. These two bridges cover ~3 of the 15 possible pairwise paths.

**Overstated in one dimension:** The "7th envelope" (Codex's "spec envelope") does not exist as a distinct code artifact. The closest candidates are `ControlSurfaceEnvelope` (an API response wrapper, not a message-carrying envelope) and `CanonicalEvent` (an LLM engine event, not a coordination envelope). Codex appears to have combined two unrelated things into a single count.

**Understated in another dimension:** NATS is not one envelope — it is at least three ad hoc wire formats (text-header, `kind`-keyed JSON, presence beacon) with no schema enforcement. Codex's count of "7" likely undercounts the NATS fragmentation.

The count is off (6 confirmed code envelopes, not 7), but the structural diagnosis — independent schemas with almost no shared field surface and sparse bridging — is accurate.

---

#### What I Observed That Codex Did NOT Flag

1. **NATS is outside `dharma_swarm/` entirely.** `dharma_swarm/a2a/node_gateway.py:20` explicitly declares NATS/gRPC as "Tier 2 — not yet implemented." The live NATS coordination visible in `/home/user/workspace/nats/` is operated by a separate process (`agni_daemon.py`, `a2a_client.py`, `presence_heartbeat.py`) with no schema contract enforced anywhere. Codex counted "NATS contact envelope" as if it were a defined schema; it is an ad hoc string format with at least three in-practice shapes. This is worse than Codex implied.

2. **`MessageBus` contains two disjoint sub-schemas.** The `messages` table and the `events` table (`message_bus.py:57–67`) are both inside `MessageBus` but carry entirely different fields. Codex's "MessageBus rows" conflates them into one. The `events` table (`event_id`, `event_type`, `task_id`, `agent_id`, `source_pid`, `occurred_at`, `payload`) is closer semantically to `RuntimeEnvelope` than the `messages` table is, yet there is no code that bridges between them.

3. **`CanonicalEvent` is an 8th envelope Codex missed entirely.** `dharma_swarm/engine/events.py:58` defines `CanonicalEvent` — a provider-neutral event envelope for LLM orchestration events with 9 fields including `event_id`, `source_agent`, `target_agent`, `session_id`, `artifact_id`, `payload`. It overlaps semantically with `RuntimeEnvelope` but has no adapter connecting them. It is consumed only within `dharma_swarm/engine/` and never referenced by `event_log.py` or `evaluation_registry.py`.

4. **`SessionEventBridge` is the only translator that converts INTO `RuntimeEnvelope`** (`dharma_swarm/session_event_bridge.py:51`). All other envelope types remain isolated. The `RuntimeInteropAdapter` (`contracts/runtime_adapters.py:740`) bundles multiple envelope types into a flat snapshot dict but does not provide bidirectional field mapping — it is a projection, not a translator.

5. **`trace_id` overlaps `RuntimeEnvelope` and `A2ATask` but is wired differently.** `RuntimeEnvelope.trace_id` is auto-generated at creation (`runtime_contract.py:68`); `A2ATask.trace_id` is an optional carry-through (`a2a_server.py:213`) with no mechanism forcing them to be the same value across a single agent interaction. This means a single causal chain (operator → A2ATask → RuntimeEnvelope events) has two independent `trace_id` lineages with no join key — an observability gap Codex did not name.

---

## Section 17 — `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-C.md` <a id="section-17-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-perplexity-c-md"></a>

> **Original path:** `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-C.md`  
> **Source date:** 2026-06-05  
> **Author/Owner:** perplexity-computer  
> **Size:** 15,998 bytes  
> **sha256:** `c09c1215e13686c0b75703002eab829671be65e2c7d4853f1e90e4bfc25f3e52`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Andon slice C (authority+execution) evidence backing the reconciliation.

### Verbatim content

### Andon Slice C — Authority & Execution
**Agent:** perplexity-computer  
**Branch:** perplexity-grounding/1780289724-vocabulary-census  
**Verified at:** 2026-06-01  
**Slice covers:** C1 (5–7 ontology stores), C2 (execute_action log vs mutation), C3 (InterruptGate auto-approve), C4 (NATS bridge envelope)

---

#### C1: "5–7 ontology/registry stores claim authority"

##### Evidence

**All classes matching `class.*Store|Registry|Ontology|Catalog|Index`** in `dharma_swarm/` (non-test, production only) with ontology-adjacent scope:

| Class | File | Writes to it? | Reads from it? |
|---|---|---|---|
| `OntologyRegistry` | `dharma_swarm/ontology.py:300` | `register_type`, `register_link`, `register_action`, `create_object`, `update_object`, `delete_object`, `link_objects`, `execute_action` | `get_type`, `get_types`, `get_links_for`, `get_action_def`, `get_object`, etc. |
| `OntologyHub` | `dharma_swarm/ontology_hub.py:43` | `store_object`, `delete_object`, `store_link`, `store_action_execution`, `sync_from_registry` | `load_into_registry`, `search_objects` |
| `OntologyGraph` | `dharma_swarm/ontology_query.py:36` | None (read-only query facade wrapping a registry) | `traverse`, `find`, `shortest_path` |
| `OntologyObj` (not a registry) | `dharma_swarm/ontology.py:185` | N/A — Pydantic model, not a store | N/A |

**The singleton chain is explicit:**

- `dharma_swarm/ontology_runtime.py:22` declares `_SHARED_REGISTRY: OntologyRegistry | None = None` and `_SHARED_HUB: OntologyHub | None = None`.
- `get_shared_registry()` at `ontology_runtime.py:116` is the single factory: it calls `OntologyRegistry.create_dharma_registry()`, then hydrates from `OntologyHub` (SQLite at `~/.dharma/ontology.db`), and caches in `_SHARED_REGISTRY`.
- Every API caller routes through `get_shared_registry()`: `api/routers/ontology.py:40`, `api/routers/agents.py:45`, `api/routers/graphql_router.py:236`, `api/main.py:104`, `dharma_swarm/api.py:114`, `dharma_swarm/custodians.py:450`, `dharma_swarm/engine/store_sync.py:79`, `dharma_swarm/ontology_agents.py:102`.
- `OntologyHub` is the persistence layer **subordinate** to `OntologyRegistry`, not a competing authority. Its role is defined at `ontology_hub.py:43–50`: "Wraps the in-memory OntologyRegistry with a SQLite persistence layer."
- `OntologyGraph` (`ontology_query.py:36`) is a read-only query wrapper — it takes a registry as constructor arg and does not write.

**What is NOT a competing authority:**  
The grepping found 70+ `class.*Store/Registry` hits, but these are domain-specific stores (`ArtifactStore`, `CheckpointStore`, `StigmergyStore`, `RuntimeStateStore`, `ModelRegistry`, `AgentRegistry`, `BridgeRegistry`, `ConceptRegistry`, etc.) that operate in their own domains and do NOT hold or write ontology objects/types/actions. They are NOT competing ontology stores.

**Conclusion on C1:**  
The authoritative ontology plane is `OntologyRegistry` (in-memory, type system + object instances) backed by `OntologyHub` (SQLite persistence). These are one stack, not competitors. `OntologyGraph` is a read-only query lens. The claim of "5–7 stores claiming authority" cannot be grounded in the code — no 5–7 distinct classes hold or mutate ontology types/objects/actions.

**Verdict: overstated.** The actual structure is a two-layer singleton (`OntologyRegistry` + `OntologyHub`) with a single shared runtime accessor (`get_shared_registry`). Codex appears to have counted all store-like classes repo-wide, not just those touching the ontology object graph.

---

#### C2: "`execute_action` at `ontology.py:637` logs success WITHOUT applying mutations"

##### Evidence

**Full `execute_action` body** (`dharma_swarm/ontology.py:594–639`):

```python
def execute_action(
    self,
    object_type: str,
    action_name: str,
    object_id: str,
    params: dict[str, Any],
    executed_by: str = "system",
    gate_check: Callable[[str, dict[str, Any]], dict[str, str]] | None = None,
) -> ActionExecution:
    action_def = self.get_action_def(object_type, action_name)
    execution = ActionExecution(...)

    if action_def is None:
        execution.result = "failed"
        ...
        return execution

    # Telos gate check
    if gate_check and action_def.telos_gates:
        gate_results = gate_check(action_name, params)
        ...
        if any(v == "BLOCK" for v in gate_results.values()):
            execution.result = "blocked"
            ...
            return execution

    # Security check
    obj_type = self._types.get(object_type)
    if obj_type and obj_type.security.telos_required and not gate_check:
        execution.result = "blocked"
        ...
        return execution

    execution.result = "success"          # ← line 637
    self._action_log.append(execution)    # ← line 638
    return execution                      # ← line 639
```

**Line 637 is the success assignment. Lines 638–639 append to audit log and return. There is no mutation call anywhere in this function body.** The `ActionDef` model carries a `modifies: list[str]` field (defined at `ontology.py:140`) that declares *which fields an action intends to modify*, but `execute_action` never reads `action_def.modifies` and never calls `update_object`. The mutation declared in the schema does not happen.

**Call sites and wrapping:**

- `dharma_swarm/logic_layer.py:254` (`ApplyAction.execute`): calls `registry.execute_action(...)`, inspects `execution.result` for `"blocked"` or `"failed"`, then marks its own `BlockResult` as `SUCCESS`. It does NOT call `registry.update_object` or any mutation after. The success path returns `{"action": ..., "object_id": ..., "gate_results": ...}` with no object state change.
- `dharma_swarm/api.py:229` (`execute_action` HTTP handler): calls `reg.execute_action(...)` and returns the `ActionExecution` object. No downstream mutation.
- `dharma_swarm/custodians.py:450`: reads from shared registry but does not call `execute_action`.

**Tests** (`tests/test_ontology_registry.py:345–404`):

```python
def test_execute_success(self, registry):
    obj, _ = registry.create_object("Experiment", {"name": "test", "status": "designed"})
    result = registry.execute_action("Experiment", "Run", obj.id, {"gpu": "A100"})
    assert result.result == "success"
```

No test asserts that `obj.properties["status"]` changed to any expected post-action value. Tests verify only `result.result == "success"` and gate/block behavior — not mutation effect. `test_action_history` (`ontology_registry.py:396–404`) verifies that `execute_action` calls appear in `action_history`, again without checking object-state change.

**Git history:** The `git log -p dharma_swarm/ontology.py` trace shows that `execute_action` was introduced in the v0.6.0 commit (`b442d0e`) alongside `ActionDef.modifies`. The `modifies` field was part of the original schema design but `execute_action` was never wired to apply those modifications. This was not a regression — the mutation was never implemented. The `modifies` field is purely declarative metadata for OAG/LLM context (`describe_type` at `ontology.py:695` surfaces it as `"deterministic"/"LLM"` annotation).

**Verdict: confirmed.** `execute_action` at `ontology.py:637` records `"success"` in the audit log without applying any field mutations to the target object. `ActionDef.modifies` (defined at `ontology.py:140`) lists intended mutations but is never consumed by the execution path. The gap is not a regression — it was never wired. Codex's claim is precisely correct on the mechanism.

**Sharpness note:** The claim says "logs success without applying mutations." The word "log" in Codex's framing is slightly off — line 638 appends to `_action_log` which is an audit trail, not a structured logger call. But the structural defect (declared mutations not applied) is correct.

---

#### C3: "`InterruptGate` auto-approves without a handler (toy)"

##### Evidence

**Full `InterruptGate.__init__`** (`dharma_swarm/checkpoint.py:97–106`):

```python
def __init__(
    self,
    callback: Callable[[InterruptRequest], Any] | None = None,
    timeout_seconds: float = 300.0,
    auto_approve: bool = True,
) -> None:
    self._callback = callback
    self._timeout = timeout_seconds
    self._auto_approve = auto_approve
    self._pending: dict[str, asyncio.Future[InterruptResponse]] = {}
```

**`auto_approve` defaults to `True`.**

**`interrupt()` method** (`dharma_swarm/checkpoint.py:108–152`):

```python
async def interrupt(self, request: InterruptRequest) -> InterruptResponse:
    if self._callback is None and self._auto_approve:
        return InterruptResponse(
            request_id=request.id,
            decision=InterruptDecision.APPROVE,
            reason="auto-approved (no interrupt handler registered)",
        )
    # ... callback path ...
```

When `callback=None` (the default) and `auto_approve=True` (the default), any interrupt request returns `APPROVE` immediately without any operator involvement. The module-level singleton in `cascade.py:36` is:

```python
_interrupt_gate = InterruptGate()
```

This is `InterruptGate()` with no arguments — `callback=None`, `auto_approve=True`. The singleton is used by every `LoopEngine` that does not explicitly pass its own gate (`cascade.py:117`: `self._gate = interrupt_gate or _interrupt_gate`).

**Handler attachment point:** Yes — `callback: Callable` is a constructor parameter. But it must be wired at instantiation. There is no `register_handler()` or `set_callback()` method. The `resolve()` method (`checkpoint.py:154`) resolves pending futures but cannot install a callback retroactively. The module-level singleton therefore permanently operates in auto-approve mode unless the `LoopEngine` caller supplies its own gate.

**What Codex calls "toy":** The docstring at `checkpoint.py:94–95` says explicitly: _"If no callback is set, interrupts auto-approve (backward compatible)."_ This is by design, not accidental. But the production singleton is wired without a callback, making every gate-phase interrupt in `cascade.py` auto-approve in practice.

**Tests** (`tests/test_checkpoint.py:142–209`): Cover `auto_approve=True` (no callback), `manual resolve`, `timeout auto-approve`, `timeout auto-reject`. Tests validate the behavior correctly — including that `InterruptGate(auto_approve=True)` with no callback returns `APPROVE`. No test verifies that a handler is registered before use in production cascade runs.

**Verdict: partially_confirmed.** The auto-approve-without-handler behavior is real and present at `checkpoint.py:114–119`. The module-level singleton at `cascade.py:36` runs permanently in this mode. However, "toy" overstates — the design is intentional backward-compatibility scaffolding, and a full callback path with timeout + filesystem persistence exists at `checkpoint.py:121–150`. The defect is that the production singleton does not wire a callback; it is architectural incompleteness, not toy code.

---

#### C4: "NATS bridge publishes without canonical envelope (bypasses spine)"

##### Evidence

**NATS does not exist in this branch's codebase.**

A comprehensive search across all Python files in the repo (`find . -name "*.py" | xargs grep -l "nats\|NATS"`) returns exactly **one file**: `dharma_swarm/a2a/node_gateway.py:20`, which mentions NATS only in a comment:

```python
### Not yet implemented (future follow-up):
###   - gRPC / NATS transport bindings (Tier 2)
```

There is no `nats_a2a_bridge.py`, no `a2a_nats_contact.py`, no `nc.publish`, no `js.publish`, no `NatsBridge` class, no NATS client import anywhere in the codebase on this branch.

**Git history context:** NATS implementation files (`nats_a2a_bridge.py`, `a2a_nats_contact.py`, `a2a_durable_projection.py`, `a2a_stale_claim_reaper.py`) are referenced in `docs/agent_tasks/claude_guidance_perplexity_computer_2026-05-31.md:11` as **Codex's untracked files on a local working tree** — they are not on `main` and not on this branch. The NATS substrate was formally scoped out of the current active tracks until the doctrine amendment (#396, merged 2026-05-31) and is listed as a proposed concurrent track (`proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml`, `proposed_tracks/spine-adoption-2026-06.yaml`) not yet declared active.

**Verdict: wrong.** There is no NATS bridge in the repo on this branch. The Codex claim audited a snapshot that included Codex's own local untracked working-tree files, not the committed codebase. The claim cannot be evaluated against the current branch state because the subject of the claim does not exist here. If and when `nats_a2a_bridge.py` is merged, the envelope enforcement question becomes live — but on this branch, C4 is categorically wrong.

---

#### Slice C Headline

Three of four Codex claims in Slice C have grounding in the code, but accuracy varies sharply. **C2 is the only fully confirmed claim and the sharpest defect**: `execute_action` at `ontology.py:637` unconditionally records `"success"` and appends to the audit log without applying field mutations declared in `ActionDef.modifies`, and no test exercises mutation effect. **C3 is partially confirmed**: `InterruptGate` does auto-approve without a handler, the production singleton in `cascade.py` is wired without a callback, but this is intentional backward-compat scaffolding with a real callback path present. **C1 is overstated**: the repo has one canonical ontology stack (`OntologyRegistry` + `OntologyHub`) accessed through a single shared singleton (`get_shared_registry` in `ontology_runtime.py`); Codex appears to have conflated domain-specific stores (artifact, stigmergy, checkpoint, etc.) with ontology authority stores. **C4 is wrong**: no NATS bridge exists in the committed codebase on this branch — Codex audited its own untracked local files.

---

#### What Codex Did NOT Flag

1. **`ActionDef.modifies` is a dead schema field.** Ninety-plus `modifies=[...]` declarations exist across `ontology.py` (e.g., `ontology.py:910`, `:914`, `:878`, `:1599`) but the field is never consumed at execution time. The entire "typed, transactional mutation" promise in the `ActionDef` docstring (`ontology.py:130–135`: _"Every mutation is an Action that commits atomically... auditable, reversible, and gated"_) is aspirational, not operative. Codex flagged the symptom (log without mutation) but not the systemic implication: the ontology action model presents as a transaction system but provides no actual mutation guarantee on any object field anywhere in the execution path.

2. **`OntologyHub.sync_from_registry` is called only at persist time, not at action-execute time.** Writes to `OntologyRegistry._objects` (via `create_object`, `update_object`) ARE persisted via `persist_shared_registry` → `hub.sync_from_registry` (`ontology_runtime.py:141–159`). But `execute_action` never calls this path. If a caller invokes `execute_action` and the process crashes before `persist_shared_registry` is called, the action execution is lost from SQLite even though `_action_log` had it in memory. This is an action-log durability gap distinct from the mutation gap.

3. **`InterruptGate.resolve()` has no authentication.** `checkpoint.py:154–163`: `resolve(response)` accepts any `InterruptResponse` from any caller that knows a `request_id`. Since `request_id` is a UUID hex written to a filesystem directory (`INTERRUPT_DIR`), any process with filesystem read access can forge approval of any pending interrupt. No caller identity is verified.

4. **`execute_action` is the only write path without a security role check.** `create_object` and `update_object` in `OntologyRegistry` are guarded by `check_security` calls (referenced in `ontology.py:280–292`). `execute_action` at `ontology.py:594–639` checks `telos_required` but NOT `write_roles` — a caller with no write permission can execute any action on any object as long as it passes telos gates or the type is not `telos_required`.

---

## Section 18 — `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-D.md` <a id="section-18-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-devin-d-md"></a>

> **Original path:** `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-D.md`  
> **Source date:** 2026-06-02  
> **Author/Owner:** Devin  
> **Size:** 5,926 bytes  
> **sha256:** `971b871b4e2b075cb82b8b053dde3deca727190990d6e2cfe8c02b937f4ea65c`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Andon slice D (workflow-state owners) evidence.

### Verbatim content

### Slice D — Workflow State Ownership

**Agent:** devin-roaming-2987d222 (serial AGT-DEVIN_ROAMING_2987D222)
**Verdict date:** 2026-06-01T07:20Z
**Codex claim:** Multiple workflow-state owners. No `workflowRun` boundary. LangGraph-style state graph absent.

---

#### Method

Grep + read across all `dharma_swarm/**/*.py` for classes containing `State`, `Run`, `Loop`, `Workflow`, `Task`, `Session` in their names. Traced state persistence (SQLite, JSONL, in-memory) and ownership (who writes, who reads).

---

#### Findings

##### 1. Inventory of state owners

| # | Module | State class | Persistence | Scope |
|---|--------|------------|-------------|-------|
| 1 | `runtime_state.py` | `SessionState`, `TaskClaim`, `DelegationRun`, `RuntimeStateStore` | SQLite (`~/.dharma/state/runtime.db`) | **Primary control plane** — sessions, task claims, delegation runs, session events |
| 2 | `models.py` | `AgentState`, `SwarmState`, `Task` | In-memory (via SwarmManager) | Agent pool + task board snapshots |
| 3 | `swarm.py` | `SwarmCoordinationState`, `SwarmManager` | In-memory + delegates to `TaskBoard` | Top-level coordinator; owns agent pool, orchestrator, task board |
| 4 | `orchestrate_live.py` | (no dedicated class) | Passes `STATE_DIR` to ~15 subsystems | **Loop host** — `run_swarm_loop()` instantiates SwarmManager, MessageBus, LoopSupervisor, all subsystem agents |
| 5 | `loop_supervisor.py` | `LoopHealth`, `StateChangeTracker`, `LoopSupervisor` | JSONL at `~/.dharma/loop_supervisor/` | Watchdog over orchestrate_live loops — stall detection, retry storms |
| 6 | `mission_contract.py` | `MissionState`, `CampaignState` | JSONL at `~/.dharma/missions/` | Mission lifecycle (planned→active→complete) |
| 7 | `iteration_depth.py` | `InitiativeStatus`, ledger | JSONL at `~/.dharma/iteration/` | Quality ratchet — seed→growing→solid→shipped |
| 8 | `overnight_director.py` | `DurableState` | JSON/JSONL at `~/.dharma/overnight/<run>/` | Long-horizon run persistence (spec + plan + runbook + audit) |
| 9 | `operator_core/contracts.py` | `CWS` (see §3) | Not persisted (contract type) | Typed contract for workflow snapshots |
| 10 | `rea_runtime.py` | `WaitState`, `WaitStateKind` | SQLite (runtime.db) | REA wait states (approval, feedback, resource) |
| 11 | `amiros.py` | `AMIROSRegistry` | JSONL at `~/.dharma/amiros/` | Research provenance chain (experiments, claims, artifacts) |
| 12 | `hibernation.py` | `JobState` | Not examined in detail | Hibernation job lifecycle |
| 13 | `economic_spine.py` | `MissionState` (enum) | Via runtime_state tables | Economic mission lifecycle states |

##### 2. Who is the primary state owner?

**`runtime_state.py:RuntimeStateStore`** is the primary durable state surface. It's a WAL-backed SQLite store providing:
- Session lifecycle (`sessions` table)
- Task claim tracking (`task_claims` table)
- Delegation run tracking (`delegation_runs` table)
- Session event log (`session_events` table with FTS5)
- Correlation context threading

`orchestrate_live.py` is the primary **loop host** — it instantiates `SwarmManager`, which in turn owns `TaskBoard` and the agent pool. But `orchestrate_live.py` doesn't own state itself; it delegates state persistence to `RuntimeStateStore` + various JSONL ledgers.

##### 3. Is there a missing `workflowRun` boundary?

**Partially confirmed.** There is no single `workflowRun` type that encapsulates a full execution lifecycle (start→tasks→outcome→feedback). Instead:

- `DelegationRun` (`runtime_state.py:368`) tracks individual task delegations but not the enclosing workflow
- `MissionState` (`mission_contract.py:104`) tracks mission-level lifecycle but not individual run instances
- `LoopHealth` (`loop_supervisor.py:32`) tracks tick-level health but not semantic workflow boundaries
- The workflow-state contract at `operator_core/contracts.py:217` (hereafter **CWS**) exists as a **typed contract** with `workflow_id`, `status`, `active_lane_ids`, `blocked_by` — but it is not persisted or populated at runtime. It's a declared shape with no producer.

The gap: a workflow starts in `orchestrate_live.py`, tasks get claimed via `RuntimeStateStore`, results flow back through agent responses, but there is no durable record that says "workflow run X started at T1, included tasks [A, B, C], ended at T2 with outcome Y." The `DelegationRun` comes closest but is scoped to a single delegation, not a workflow boundary.

##### 4. Multiple owners — harmful or cosmetic?

**Cosmetic fragmentation, not operational collision.** The state owners serve different scopes:
- `RuntimeStateStore` = durable control plane (sessions, claims, delegations)
- `SwarmManager` = in-memory runtime snapshot
- `LoopSupervisor` = health watchdog (read-only consumer of loop ticks)
- `MissionState` = strategic planning layer
- `IterationDepth` = quality ratchet

No two modules write to the same table or file. The "multiple owners" are layered, not competing. The issue is not that they collide — it's that no layer unifies them into a single `workflowRun` boundary.

---

#### Headline Verdict: **partially_confirmed**

Codex's claim that "multiple workflow-state owners" exist is **confirmed** — there are at least 13 distinct state surfaces. The claim that they lack a `workflowRun` boundary is **confirmed** — CWS (`contracts.py:217`) exists as a contract but has no runtime producer. However, the claim is **overstated** in framing: these are **layered** state surfaces serving different concerns (control plane, mission strategy, quality tracking, health monitoring), not competing owners fighting over the same data. The fragmentation is structural (missing unifying type), not pathological (conflicting writes).

The "LangGraph-style state graph absent" observation is **confirmed** and the most actionable finding: there is no first-class `workflowRun` that traces from dispatch through execution to outcome.

---

## Section 19 — `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-E.md` <a id="section-19-docs-research-palantir-ontology-vocabulary-census-andon-verdicts-devin-e-md"></a>

> **Original path:** `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-E.md`  
> **Source date:** 2026-06-02  
> **Author/Owner:** Devin  
> **Size:** 5,799 bytes  
> **sha256:** `7bb758eb86a578037db35144dd5b7c91d9925f03cae5861880ac8b77a8f12512`  
> **Grade:** ENDURING  
> **Disposition:** MERGE — original to be deleted in Phase E.  
> **Summary:** Andon slice E (A2A protocol vs work-queue conflation) evidence.

### Verbatim content

### Slice E — A2A External/Internal Collision

**Agent:** devin-roaming-2987d222 (serial AGT-DEVIN_ROAMING_2987D222)
**Verdict date:** 2026-06-01T07:25Z
**Codex claim:** `A2ATask` is used both for external (cross-org) protocol AND internal (intra-swarm) work queue — "dangerous conflation."

---

#### Method

Traced every instantiation and import of `A2ATask` across the codebase. Categorized each call site as external-facing (network boundary, remote agents) or internal (intra-process dispatch). Checked for state leak, auth confusion, or replay risk at each boundary.

---

#### Findings

##### 1. All `A2ATask` instantiation sites

| # | File | Line | Direction | Context |
|---|------|------|-----------|---------|
| 1 | `a2a/a2a_server.py:257` | `server.submit(A2ATask(...))` | Internal | Docstring example — orchestrator→reviewer delegation |
| 2 | `a2a/a2a_client.py:348` | `A2ATask(from_agent=..., to_agent=..., capability=...)` | Internal | `A2AClient.delegate()` — intra-swarm task delegation via discovery+dispatch |
| 3 | `a2a/a2a_bridge.py:120` | `A2ATask(from_agent=..., to_agent=..., history=[...])` | **Bridge** | `trishula_message_to_a2a_task()` — converts TRISHULA inbound messages to A2ATask |
| 4 | `a2a/node_gateway.py:210` | `A2ATask(from_agent="remote", ...)` | **External** | `_parse_task_from_body()` — HTTP endpoint accepting tasks from remote A2A nodes |

##### 2. Architecture analysis

The A2A subsystem has a **three-layer** design:

1. **`A2AServer`** (`a2a_server.py`) — Local-first task store. "Tasks are dispatched via direct function calls" (docstring line 248). Maintains its own task store "separate from (but linked to) the dharma_swarm task board" (line 250). This is the **internal** layer.

2. **`A2AClient`** (`a2a_client.py`) — Discovery + delegation client. Uses `CardRegistry` to find agents, submits to `A2AServer`. Includes cycle detection (`_MAX_DELEGATION_DEPTH = 10`) and chain tracking. This is the **internal routing** layer.

3. **`NodeGateway`** (`node_gateway.py`) — FastAPI router exposing HTTP endpoints for remote agents. API key auth via `X-A2A-Key` header. Localhost bypass only with explicit env var. This is the **external boundary** layer.

4. **`A2ABridge`** (`a2a_bridge.py`) — Bidirectional bridge between TRISHULA (legacy message format) and A2A. Converts inbound TRISHULA messages → `A2ATask` and outbound `A2ATask` results → TRISHULA messages. This is the **protocol translation** layer.

##### 3. Does `A2ATask` serve both external and internal?

**Yes.** The same `A2ATask` dataclass is used:
- **Internally:** `A2AClient.delegate()` creates an `A2ATask` for intra-swarm delegation (agent-to-agent within the same process).
- **Externally:** `NodeGateway._parse_task_from_body()` creates an `A2ATask` from an HTTP request body originating from a remote node.
- **Bridge:** `A2ABridge.trishula_message_to_a2a_task()` converts filesystem-based TRISHULA messages into `A2ATask`.

##### 4. Is the conflation harmful?

**No — it is intentional and well-bounded.** The evidence:

**Auth isolation exists.** The `NodeGateway` enforces `X-A2A-Key` auth on all external requests (`node_gateway.py:161-163`). Internal `A2AClient` calls bypass the gateway entirely — they call `A2AServer.submit()` directly. There is no path where an external request reaches the server without auth.

**Source tagging exists.** The `A2ABridge` stamps `metadata["source"] = "trishula"` on all bridge-ingested tasks (`a2a_bridge.py:127`). The `NodeGateway` stamps `from_agent = "remote"` on external tasks (`node_gateway.py:211`). Internal tasks carry the actual agent name. So the origin is always distinguishable.

**Task store is separate.** The `A2AServer` docstring explicitly states it maintains "its own task store for A2A lifecycle tracking, separate from (but linked to) the dharma_swarm task board" (`a2a_server.py:249-250`). The `dharma_task_id` field bridges the two stores when needed.

**Cycle detection prevents replay.** `A2AClient._check_cycle()` tracks active delegation chains per `context_id` and enforces a depth limit of 10. This prevents re-entrancy regardless of source.

**No state leak path found.** Internal tasks don't expose internal state to external consumers. External tasks enter through the gateway, get processed by the server, and results are returned through the gateway. The `_strip_internal_fields()` function (`node_gateway.py:181`) removes internal fields before serialization.

##### 5. What Codex missed

The dual use is not an accident — it follows the **A2A 1.0 spec** design, where the same task model represents work regardless of transport. The `A2ATask` is a **protocol-level unit of work**, not a transport-specific one. The three-layer architecture (server/client/gateway) provides the necessary boundary enforcement.

The one genuine gap: `A2ATask.from_agent` is a plain string with no typed distinction between "local agent name" and "remote node identity." A future `executionIdentity` type could strengthen this. But today, the `metadata["source"]` tag and gateway auth provide functional separation.

---

#### Headline Verdict: **overstated**

`A2ATask` IS used for both external and internal work — that part is factually correct. But the framing as "dangerous conflation" is **wrong**. The architecture deliberately separates the auth boundary (gateway), the routing layer (client), and the execution layer (server). Source tagging, auth enforcement, cycle detection, and separate task stores prevent the state-leak / auth-confusion / replay risks Codex flagged. The dual use is a design choice conforming to A2A 1.0 spec, not an oversight. The only real improvement opportunity is stronger typing on agent identity (string → typed identity), which is cosmetic, not dangerous.

---

## Provenance footer

This file consolidates 19 source files totalling 200,845 bytes. Every byte of original content above the 'Verbatim content' marker is reproduced. Header levels in original content are demoted by two levels to fit this file's TOC. File:line citations and dates inside content are preserved.

Phase D verifier (when written) will confirm zero-loss by comparing the verbatim blocks here to the original sha256s recorded in this file and in `09_PROVENANCE.md`.
