### §3.1 — TL;DR

- Accept Agent A's manifest as the controlling structure, after a targeted correction patch.
- Do not merge Agent A's file-01 unchanged; keep A's format, repair stale current-main claims.
- Codex adds 23 material missed files and several duplicate/path-drift corrections; none requires restarting.

### §3.2 — Convergence

Both agents understood that the bug corral should have ten files under `docs/bug-corral/`, with provenance first and index last. Both preserved `01_TRUTH_VERIFIERS.md` as the declared-vs-actual family and both identified the andon, runtime-truth, dashboard-fidelity, and spine-adoption materials as core inputs.

Both agents also recognized the live-owner rule: the corral must point to `BROKEN_REGISTER.md`, `INTERFACE_MISMATCH_MAP.md`, `REPO_GOVERNANCE_AUDIT.md`, and `VERIFICATION_LANE.md` instead of copying those ledgers wholesale. Agent B states that rule in file-01, but violates it in the manifest by marking live/canon files pending-delete.

### §3.3 — Divergence

Agent A is right on structure. Its `MERGE / KEEP-LIVE / ARCHIVE-INDEX / DROP-DUP / EXCLUDE` model matches the operator's tightened intent: one current, high-signal bug corral, not another pile of finder documents. Agent B is right that A missed some material sources, but B's manifest is unsafe as a delete plan.

The strongest evidence: B marks `docs/docops/AUTO_INVENTORY.md`, `docs/governance/ANTI_SLOP_RULES.md`, `docs/governance/REPO_GOVERNANCE_AUDIT.md`, and `docs/governance/hygiene/AUDIT_PROMPT.md` as `PENDING-DELETE`. Those are generated/live/canon surfaces. Deleting them would recreate the scatter problem under a new name.

Agent A is wrong in file-01 on current-main status. `execute_action` now applies declared updates at `dharma_swarm/ontology.py:934-957` and records success at `:958-977`; A's TV-01/TV-03 still cite old `ontology.py:594-639`. `InterruptGate` also now defaults `auto_approve=False` at `checkpoint.py:98-106`, so A's TV-02 overstates the current defect.

Codex's scan found 23 material misses, mainly `reports/living_agent_kernel/.../exact_local_receipt.md`, the clean-main audit pair, the June 10 anatomy syntheses, runtime-truth slice files under `reports/audit/runtime_truth/`, and June 12 handoff reports. These should be added to A's manifest, not used to adopt B's bulk-preservation format.

### §3.4 — Hallucination ledger

Agent A hallucinations or stale claims:
- TV-01 and TV-03 are stale against current `origin/main`; `execute_action` no longer matches A's cited line range and now consumes `ActionDef.modifies`.
- TV-02 is stale on default behavior; `InterruptGate(auto_approve=False)` is current.
- A's BR coverage table calls BR-009 through BR-012 open even though `BROKEN_REGISTER.md` marks those fixed.
- A lists several missing archive paths under `reports/audit/...`; current paths live under `reports/audit/runtime_truth/...` or `reports/audit/end_to_end/...`.

Agent B hallucinations or unsafe assumptions:
- B's pending-delete model treats live generated/canon files as disposable sources.
- B lists files missing from current `origin/main`, including `.dharma/shared/cartographer_notes.md`, `AUDIT_2026-05-07.md`, `GUARDIAN_REPORT.md`, and `reports/docops/corpus_inventory.*`.
- B preserves too much verbatim text, producing a 3,341-line file-01 that fails the operator-readability goal.

Codex risk:
- Codex may under-count finder files whose value is semantic rather than token-obvious, especially vision or handoff documents with sparse explicit severity labels. The 23-file addendum should be reviewed before final deletion.

### §3.5 — Next step

Do not approve PR #592 as-is. Tell Devin to keep A's manifest structure, apply Codex's correction list from `01_COMPARISON.md` and `02_CODEX_SCAN.md`, then rewrite `01_TRUTH_VERIFIERS.md` so stale findings become RESOLVED or SUPERSEDED and current findings cite current `origin/main` line numbers. After that, Devin can continue to `02_ANTI_SLOP.md`.

### §3.6 — Open questions

1. Should the clean-main audit pair be merged into `05_RUNTIME_GROUND_TRUTH.md` or archived as superseded history?
2. Should `reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md` be MERGE content or KEEP-LIVE owner material?
3. Should exact duplicate sovereign-holon ingested copies be handled in this bug-corral pass or a later dedupe pass?
4. Should B's missing-on-main files be ignored unless their branch source is supplied?
