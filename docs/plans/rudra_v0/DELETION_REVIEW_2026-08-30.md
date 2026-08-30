---
role: report
date: 2026-08-30
status: FINAL — deletion review per RUDRA_BUILD_SPEC §18; gate for first real mission
subordinates to: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md
world:
  commit: 065da4b55 · host: Mac · branch: feat/rudra-v0-build
---

# RUDRA v0 — §18 deletion review (2026-08-30)

Spec §18: "Stop the build for a deletion review if production hot-path code
exceeds 1,000 lines before a real mission runs." The ceiling was exceeded;
this is that review. Read-only: no code was changed by this document.

Measured non-blank LOC at 065da4b55 (builder's "~2,300" was low):

| Module | Non-blank LOC | Spec target |
|---|---:|---:|
| `rudra/contracts.py` | 467 | 250 (with goal_gate) |
| `rudra/goal_gate.py` | 701 | (shared 250) |
| `rudra/workcell.py` | 571 | 275 |
| `rudra/codex_driver.py` | 262 | 225 |
| `rudra/runner.py` | 397 | 175 |
| `terminal_commands/rudra.py` | 75 | 75 |
| **Total hot path** | **2,473** | **1,000** |

---

## 1. Load-bearing inventory (spec citation per retained unit)

### contracts.py (467)
- `_StrictLoader`, `_reject_non_finite`, `load_mission_yaml` — §7: admission
  MUST reject aliases, merge keys, duplicate keys, non-finite numbers.
- `validate_rel_path` / `_check_paths` — §7: absolute paths, `..`, backslash,
  control chars, `.git/**` rejected.
- `RepositorySpec`, `ScopeSpec`, `LockfileBinding`, `EnvironmentManifest`,
  `ExecutableBinding`, `ToolchainSpec`, `PytestJunitAssertion`,
  `VerifierExpect`, `VerifierCommand`, `AcceptanceSpec`, `ExecutorSpec`,
  `ContainmentSpec`, `BudgetSpec`, `RecoverySpec`, `ResultSpec`,
  `RudraMissionContract` — §7 required contract groups, strict+frozen+extra-forbid.
- `canonical_json` / `digest` — §7 canonical dump settings before SHA-256.
- `VerifierReceipt`, `GateResult`, `ProcessHandle`, `TurnObservation`,
  `GoalGatePassed`, `ReportedCompletion`, `ReproducedCompletion` + `_GATE_TOKEN`
  — §7 interface freeze; §9 the one epistemic type edge.
- `sha256_json`, `derive_mission_key`, `derive_attempt_key` — §7: raw IDs
  never name directories.
- `AdmissionError`/`AdmissionReject`/`Terminal`/`DerivedStatus` — §12 vocabulary.

### goal_gate.py (701)
- `admit` (steps 1–10), `rehash_admitted` (§3.2 rehash before every effect),
  `base_digests`/`prove_base_preserved` (§3.6) — §8 admission algorithm.
- `_bind_repository` (incl. case-fold collision rejection), `_bind_toolchain`,
  `_bind_verifier_executables` — §8 steps 2, 5; §7 toolchain binding.
- `workspace_snapshot`, `_porcelain_paths`, `_scope_check` — §8 scope
  inventory (porcelain-v2 -z, flags, symlink ancestors, forbidden literals
  vs base counts, `.git` pointer digest).
- `scrubbed_environment`, `_run_verifier`, `_check_junit` — §8 verifier
  execution (env scrub list, fixed PATH, bounded HOME/TMP, JUnit proof).
- `evaluate` — §8: verifiers always fresh, after last mutation; nothing cached.
- `freeze_candidate` (filter audit, staged-set equality, ancestry, empty
  porcelain) and `verify_candidate` (fresh detached verification workcell,
  read-only tree, tree-digest recheck) — §8 candidate freeze steps 1–10;
  executive requirements 6, 7.
- `promote` — §9 sole constructor of `ReproducedCompletion`; requirement 8.

### workcell.py (571)
- `os_boot_id`, `process_start_id`, `process_command`, `_pgid_members`,
  `descendants_of` — §10 process identity + setsid-escape enumeration
  (requirement 4).
- `rudra_state_root` — §10 symlink-safe state root; §19 resolver reuse.
- `MissionLock` — §10 single-owner never-unlinked kernel lock.
- `Journal` (complete-write+fsync, seq/dup validation, torn-tail repair,
  intent/result digests, `compare_and_seal_terminal`, post-seal violation) —
  §10 journal contract; §3.12 terminal compare-and-seal.
- `hermetic_git_env`, `run_git`, `require_git_ok` — §8 step 4 hermetic Git.
- `Workcell.create/git/quarantine` — §10 private Git directory, read-only
  alternate, no force-removal of ambiguous workcells.
- `ProcessOwner.spawn/identity_status/terminate_tree/_census/prove_dead/
  status_for_recovery` — §10 sole subprocess owner; §13 central recovery rule.

### codex_driver.py (262)
- `MUTATION_METHODS`/`READ_ONLY_METHODS`/`ALLOWED_METHODS`, `JsonRpcPeer`
  (frame ceiling, deadline, wrong-ID/malformed/conflicting-terminal fail-closed,
  server-request deny) — §11 allowed protocol surface.
- `deterministic_message_id` — §11 crash reconciliation key.
- `CodexDriver` Protocol — §7 frozen seam.
- `bytes_written` — §11 "never retried after any byte may have been written";
  asserted by tests as retry-safety evidence. Keep.

### runner.py (397)
- `run` (lock before current-attempt pointer), `_adopt` (digest rehash,
  torn-tail repair, post-seal check, base-preservation proof, process
  identity recovery) — §12 CLI semantics, §13 recovery.
- `_loop` (stop-request precedence, budget seals, rehash before effects,
  gate before every turn, conservative token charge, no-delta) — §12 core loop.
- `_freeze_and_reproduce` — §8 freeze steps 1–3 (interrupt, close, prove the
  whole tree dead twice) before commit; requirements 4, 5, 6, 7, 8.
- `status` (kernel-lock liveness, never stale files) and `stop` (durable
  request, sealed-terminal wins) — §12.

### terminal_commands/rudra.py (75) — meets target.
- `cmd_rudra_run/status/stop` + exit-code mapping — §12 CLI.

## 2. Decorative / duplicated / over-defensive findings

- **F1 — `StubTurn` + `StubCodexDriver` (~105 LOC) live in production
  `codex_driver.py`.** Spec §6 names the module "narrow app-server JSON-RPC
  driver". The stub is test scaffolding (imported only by
  `tests/test_rudra_{codex_driver,runner,adversarial}.py`). Belongs in a
  test-support module. Largest single honest cut.
- **F2 — `RecoveryView` (~12 LOC) is dead.** The §7 frozen seam named it, but
  the implementation carries recovery state on `AdmittedMission`; nothing
  imports `RecoveryView`. Cut, or annotate as reserved.
- **F3 — `process_cwd` (~10 LOC) in workcell.py is dead.** Note the flip
  side: §10 restart matching lists cwd among required identity fields and
  `identity_status` does not check it — a spec *gap*, not just dead code
  (see §4 risks).
- **F4 — Duplicated git wrappers:** goal_gate's private `_git` re-implements
  workcell's `run_git`/`require_git_ok` (~10 LOC).
- **F5 — Duplicated fsync idioms:** runner has three inline open/fsync/close
  blocks that duplicate goal_gate's `_fsync_file` (~12 LOC).
- **F6 — Duplicated status/stop journal-reading** in runner (~12 LOC);
  factor one `_sealed_terminal(mission_dir)`.
- **F7 — Repeated `ConfigDict(frozen=True, extra="forbid")`** on 8 result
  models in contracts.py; one `_Frozen` base mirrors the existing `_Strict`
  pattern (~10 LOC).
- **F8 — Three hand-rolled HEX64 validators** (LockfileBinding,
  ExecutableBinding, ExecutorSpec) can share one helper (~8 LOC).
- **F9 — Dead duplicate line** `actual_comm = process_command(...)` twice in
  `identity_status` (−2); no-op `except JournalConflict: raise` in
  `runner._seal` (−2).
- **F10 — Repo-idiom duplication (informational, not actionable):**
  `canonical_json`/`sha256_file`/fsync helpers exist in at least six other
  modules (`context_compiler_utils.py:33`, `capital_lab/alpha_evidence.py:246-260`,
  `chamber/traces.py:30`, `operator_core/runtime_truth.py:71`,
  `verifier_ranker_v0/inventory.py:24`, `episode_ledger.py:258`). None is a
  shared public utility; RUDRA's copies match repo practice. No import
  consolidation recommended inside this review.
- **Not duplicated (checked):** `sandbox.py:34-78` process-group cleanup is
  asyncio-shaped and lacks the ppid-lineage census §10 requires;
  `file_lock.py` and `event_log.py` are explicitly unsuitable per spec §19;
  `runtime_admission._git_environment` is private and probe-scoped. RUDRA
  correctly does not reuse these.
- **Over-defensive but cheap, keep:** `_version_output` exact-string compare
  (§8 step 5 says "record"; equality is stricter but honest and small);
  `_HOSTILE_TOKENS` scan (§8 step 7 requires hostile-text rejection).

## 3. Compaction plan (per module; post-cut estimates; requirement risks)

Requirements referenced: R4 = no double execution, R7 = fresh verifier,
R8 = COMPLETE_REPRODUCED only from fresh.

### contracts.py 467 → ~395
- Cut `RecoveryView` (F2). Risk: none (dead).
- `_Frozen` base class (F7); shared HEX64 validator (F8). Risk: none —
  validation behavior identical.
- Trim banner comments/module docstring; keep all spec citations. Risk: none.
- No model, validator, or digest function is removable — every group is §7
  normative.

### goal_gate.py 701 → ~575
- Reuse `run_git`/`require_git_ok` from workcell (F4). Risk: none.
- Extract a shared "ephemeral private gitdir at ref" helper used by both
  `Workcell.create` and `verify_candidate`. Risk: none if the verification
  workcell remains a **fresh detached** gitdir — the helper must not be
  used to reuse the mutation gitdir.
- Merge `_chmod_tree` dir/file loops. Risk: none.
- Trim banners. Risk: none.
- **FORBIDDEN tempting cuts:**
  - Running final verification in the mutation workcell (or reusing the
    pre-commit `evaluate` receipts) instead of a fresh detached verification
    workcell — crosses R7 and R8. Forbidden.
  - Caching the baseline gate result as evidence for a later green — crosses
    R7 (verifiers must begin after the final mutation). Forbidden.
  - Dropping `promote`'s workspace-digest recheck against current state —
    crosses R8. Forbidden.
  - Dropping `_check_junit` in favor of exit-code-only proof — §8 explicitly
    forbids regex/exit-only execution proof. Forbidden.

### workcell.py 571 → ~490
- Cut dead `process_cwd` (F3) — see §4: the correct fix may instead be to
  *wire it into* `identity_status` (+~6 LOC) because §10 requires cwd in
  restart matching. Net −4 either way.
- Cut duplicated `process_command` call (F9). Risk: none.
- Collapse `Workcell.create`'s eight `require_git_ok(run_git(...))` stanzas
  into a step table. Risk: none — same argv, same order.
- Trim banners. Risk: none.
- **FORBIDDEN tempting cuts:**
  - Removing the post-KILL census / second `prove_dead` in the freeze path —
    crosses R4 (an unproven-dead tree may still execute). Forbidden.
  - Removing journal seq/duplicate validation or post-seal violation checks —
    §10/§3.12; weakens the terminal seal that R4/R8 rely on. Forbidden.
  - Replacing the never-unlinked flock with the existing `AsyncFileLock` —
    spec §19 forbids it. Forbidden.

### codex_driver.py 262 → ~150
- Move `StubTurn`/`StubCodexDriver` to test support (F1); edit the three test
  files' imports. Risk: none — GoalGate never trusts any executor, stub or
  live; R3/R7/R8 are unaffected.
- Trim banners. Risk: none.
- **FORBIDDEN:** removing the server-request deny path, the
  conflicting-terminal-notification check, or the method allowlist — §11
  fail-closed behavior that protects R3 (independent promotion). Forbidden.

### runner.py 397 → ~330
- Import `_fsync_file` from goal_gate (F5); factor `_sealed_terminal` (F6);
  cut no-op except-re-raise (F9); hoist function-local imports. Risk: none.
- Trim banners. Risk: none.
- **FORBIDDEN:** folding the freeze sequence's `prove_dead → terminate_tree →
  prove_dead` into one call — the double proof *is* R4. Forbidden. Dropping
  the pre-seal `prove_base_preserved` recheck — §3.6. Forbidden.

### terminal_commands/rudra.py 75 → ~70
- Cosmetic only (`__import__('platform')`). Meets target as-is.

### Projected total
395 + 575 + 490 + 150 + 330 + 70 ≈ **2,010 non-blank LOC** — a ~19%
reduction, still ~2× the 1,000 ceiling.

## 4. Verdict

**No redesign is needed — but compaction alone cannot satisfy §18, and the
build cannot enter a real mission until the ceiling is reconciled.**

The architecture maps cleanly onto the normative spec: every retained unit
above cites a §7–§13 obligation, and the dead/decorative mass found is only
~190 LOC. The irreducible semantic content — 15 strict contract groups,
strict YAML, admission binding, raw-state scope inventory, verifier harness
with JUnit proof, freeze + fresh verification workcell, journal with CAS
seal, process census, recovery adoption, JSON-RPC fail-closed driver,
status/stop — measures ~2,000 readable LOC. Reaching 1,000 would require
deleting spec-mandated surface (structured assertions, forbidden-diff
literals, torn-tail repair, status/stop, half the contract groups), and any
such cut crosses R7/R8 or §3.12 — forbidden by this review's own terms.

Also flagged (gaps compaction must not paper over, not cut targets):
- §3.11: CPU, memory, process-count, disk, and per-verifier budgets are
  declared in `BudgetSpec` but not enforced in `runner._loop`.
- §10: `identity_status` does not match cwd/PGID as the restart rule lists
  (see F3 — likely fix by wiring `process_cwd` in, not deleting it).

**Required operator decision (one of):**
1. Ratify a spec amendment re-baselining the §6 targets/§18 ceiling to the
   measured minimum (~2,000), then apply the §3 compaction plan and re-run
   the full suite (100 tests across 7 files) plus the adversarial corpus —
   after which RUDRA v0 may proceed to its Gate 3 real-mission proof.
2. Or order named feature removals with corresponding spec edits, accepting
   a smaller RUDRA. This review found no such removal that does not weaken
   requirements 4, 7, or 8.

Option 1 is recommended. The code is fat in comments and boilerplate, not in
concept; the ceiling was calibrated to a thinner evaluator than the spec's
own §7–§13 text mandates.

---
world: commit=065da4b55 · host=Mac · branch=feat/rudra-v0-build
