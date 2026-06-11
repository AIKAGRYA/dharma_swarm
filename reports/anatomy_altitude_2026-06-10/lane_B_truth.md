# Lane B — TRUTH FABRIC Deep Read
**Date:** 2026-06-10 · **Question:** how close is "the system cannot lie to itself or its operator" to being real?
**Method:** end-to-end reads of 12+ files across 6 worktrees; live SQLite verification against `~/.dharma/state/runtime.db`; `spine_bypass_report.py` executed live. Every claim cites file:line. Clean negatives are first-class.

---

## Headline Answer

The truth fabric is **two systems wearing one name**, and only one of them is alive:

1. **The identity/ledger layer (ExecutionIdentity + RuntimeReceipt) RUNS.** `execution_identities` has **1,570 rows, latest written today 2026-06-10 13:44 UTC**; `runtime_receipts` has **583 rows (2026-06-01 → 2026-06-09)** with six production writer modules. This is real, persisting, queryable truth.
2. **The dispatch-evidence layer (EvidenceReceipt + invoke_agent) is WIRED-BUT-DORMANT.** The flag `DHARMA_SPINE_DISPATCH` is default-OFF and set nowhere persistent (verified: no hits in `~/.zshrc`, `~/.dharma/cron/`, `~/Library/LaunchAgents/`, Makefile, run_operator.sh). The receipt persistence sink `spine/persistence.py:persist_receipt` has **zero production callers**. Re-verified clean negative: **`delegation_runs.receipt_json` = 0 / 3,495 rows** (column exists, never written).

Provider honesty: on main, **8 of ~11 provider classes can still silently convert a reasoning-only model response into an empty string** — the system literally reporting "the model said nothing" when it said something. The Jun 10 `honest-spine-v2` WIP fixes 7 of them but is **uncommitted** and `providers_extended.py` is only partially converted.

Rough calibration: identity join-key ~70% real · runtime ledger ~50% real (selected paths only) · dispatch evidence ~15% real · provider honesty ~60% on main, ~85% if the WIP lands · substrate constitution = unmerged spec whose receipt mandate is enforced nowhere.

---

## Tension 1 Resolved: SIX spine generations exist; main's `dharma_swarm/spine/` is canonical

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

## Tension 2 Resolved: receipts persist — but only ONE of the two receipt systems

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

## Tension 3 Resolved: what the substrate spec declares vs. what code does

`SWARM_SUBSTRATE.md` (read end-to-end, 833 lines) is a constitution that was **never ratified** — absent from main — yet partially obeyed:

- Declared (line 30-32): *"agents decompose it into typed work, claim visible cards, produce receipts, verify outcomes, and remain interruptible through one observable control plane."* — Receipts: partially real (runtime ledger, selected paths). Interruptibility: v2 flipped `InterruptGate` to fail-closed (`checkpoint.py:78,102` per v2_report.md:112).
- Declared (line 499): *"Completion requires at least one receipt or an explicit no-check reason."* — **Enforced nowhere.** Orchestrator completion path (`orchestrator.py:2333-2337`) writes `last_completed_at`/`last_result_chars` with no receipt requirement; honors-checkpoint gating exists (`:2304-2320`) but only for tasks carrying a completion contract.
- Declared (line 580-591): BoardStore facade over TaskBoard/OperatorBridge/RuntimeStateStore — **shipped** (`dharma_swarm/board/` on main).
- Declared (line 691-701): noticer forbidden actions incl. *"submitting directly to Darwin/evolution pipelines from notice-only mode"* — consistent with the WS4a/WS4b gate work but not implemented by this spec's machinery.
- The spec's self-assessment is honest: *"The missing layer is not capability. It is convergence"* (line 96-99). That diagnosis is still exactly right on Jun 10.

The doc's authority chain was superseded: the live constitution-equivalent is now `ACTIVE_TRACK.yaml` (2 active tracks: `runtime-truth-reconciliation-2026-06` + `runtime-truth-nats-2026-06`, both serving `substrate-nativeness`) plus the doctrine lines embedded in track definitions: *"Receipts may differ by closure layer. Correlation identity must not"* (v1/v2 worktree CLAUDE.md) and *"Read models project truth from owners; they do not become authority"* (live CLAUDE.md, reconciliation track).

---

## Axis 1 — Working-code docks (verified live)

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

## Axis 2 — Vision docks (quoted)

- `spine/invoke.py:2,44-48`: *"invoke_agent — the one blessed agent invocation path. PR A: thin pass-through… PR B: A2A becomes the default invoker. PR C+: every router collapses onto this signature."* — We are at PR A, flag-off. PR B/C are roadmap text living inside the docstring.
- `spine/receipt.py:4-6`: *"OTel is an EXPORT ADAPTER, not the truth surface. The receipt itself is the canonical record."* — A canonical record that is never durably recorded (see Tension 2).
- `spine/persistence.py:8`: *"No new persistence surface — this writes to the existing canonical store."* — True in design, false in practice: it writes to nothing.
- v1/v2 track doctrine (worktree CLAUDE.md): *"Every dispatch produces exactly one receipt. No more generic dispatch_dropoff."* — `dispatch_dropoff` still exists on main (`orchestrator.py:2157` `source="dispatch_dropoff"`).
- v2 report's own bottom line (v2_report.md:247): *"The v2 branch does not claim the entire platform is canonical yet… 16 surfaces: Joined 5/16 (31.25%), joined-or-adapter-ready 9/16 (56.25%)."* — Unusually honest self-grading; matches what I found.
- `SWARM_SUBSTRATE.md:499`: *"Completion requires at least one receipt or an explicit no-check reason."* — the constitution's strongest truth clause; unenforced.
- WIP test header (`honest_spine_v2/tests/test_providers_quality_track.py:+795`): *"Reasoning-only or list-typed message content must never collapse to ''. Fixed in Honest Spine v2 Phase 0; previously only OpenAIProvider was routed through _extract_openai_compatible_message_text."*

## Axis 3 — Anatomy: organ / surface / spine

- **Spine (skeleton):** `ExecutionIdentity` is the vertebra; it is the only artifact shared by all six generations and the only one with live production writes today. The v2 design choice — *"dependency-light so runtime producers can import it without creating circular ownership"* (`identity.py:4-6`) — is why it survived merge while everything heavier stalled.
- **Organs:** runtime_lifecycle (delegation/claim/artifact receipts), message_bus (consumption receipts + idempotency gate), task_board, artifact_store, a2a_server, nats_transport — each writes receipts through `record_receipt_for_identity`, i.e., the organs joined the ledger without local rewrites, exactly as `adapters.py:3-6` intended.
- **Surfaces:** two declared truth surfaces — (a) the runtime ledger (authority), (b) `operator_core/runtime_truth.py` packets (read-only projection). The doctrine separating them (*"Read models project truth from owners"*) is structurally respected: the projector opens the DB read-only and refuses to migrate (`runtime_truth.py:3-5`).
- **Vestigial organs:** `command_spine.py` (G1, 587 lines, unmerged), `SWARM_SUBSTRATE.md` (G2, unmerged), v1 worktree's uncommitted spine (G3, superseded), `submit_via_spine` (G5, callerless). Four of six generations left organs that nothing circulates blood through.

## Axis 4 — Ecosystem position

- Two ACTIVE tracks own the fabric: `runtime-truth-reconciliation-2026-06` (operator; owns `operator_core/**`, `runtime_state.py`) and `runtime-truth-nats-2026-06` (codex; owns NATS transport contacts). Surface separation is the declared safety boundary. `runtime-truth-spine-2026-06` closed SHIPPED 2026-06-04.
- The live CLAUDE.md still says *"Substrate-nativeness is currently estimated at ~10–15%"* (live CLAUDE.md, "CRITICAL" section) while the 2026-06-09 ground-truth pass measured 81.2% for the runtime spine specifically — a stale doctrine number sitting in the first-read file. The spine-vs-spine confusion documented in project memory is reproduced inside the repo's own onboarding doc.
- Cross-worktree drift is the live hazard: the canonical spine exists in 1 of 6 generations; agents landing in the wrong worktree (e.g., v1, where the spine is uncommitted) would read a different truth. G6 (honest-spine-v2) is based on current main, which is the correct pattern.
- The bypass report's allowlist (5 intentional `.submit()` bypasses, all in `a2a/`) is the honest migration ledger for "PR B" — but it is warning-only and not wired to fail CI.

## Axis 5 — Grading summary (RUNS / WIRED-BUT-DORMANT / ASPIRATION)

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

## What would most move "cannot lie to itself" toward real (evidence-ranked)

1. **One call:** invoke `persist_receipt(receipt, db)` from `orchestrator.py:2232` and `submit_via_spine` — turns the canonical record from in-memory to durable. The sink, schema, and column already exist.
2. **Land G6:** commit the honest-spine-v2 provider diff and finish `providers_extended.py:86,152,213` — closes the only path by which the system actively misreports model output today.
3. **Set the flag somewhere real** (daemon env or launchd) after GATE review — the dispatch evidence path has literally never run outside tests.
4. **Fix the stale 10–15% line in live CLAUDE.md** — the truth fabric's own onboarding doc carries a falsified number on the fabric itself.
5. **Decide the fate of orphan generations** (G1 command spine, G2 spec doc): merge as depth-on-demand docs or compost — six generations is itself a legibility cost.

*Files read end-to-end: spine/{invoke,receipt,identity,persistence,routing,tollbooth,adapters}.py (live), orchestrator.py:2140-2340, a2a_bridge.py:60-220, runtime_truth.py header, SWARM_SUBSTRATE.md (833L), runtime_truth_spine_v1_report.md (169L), runtime_truth_spine_v2_report.md (247L), honest_spine_v2 full diffs + pulse commit, providers.py extraction sites both branches.*
