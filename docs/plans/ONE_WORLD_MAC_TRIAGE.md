# ONE WORLD — Mac Checkout Triage (chore/silvering-cleanup-2026-08-28)

**Role:** `report` (dated descriptive output per `docs/AGENTS.md`; classification only, no mutations performed).
Subordinates to `docs/plans/ONE_WORLD_2026-08-30.md` (the unification working plan); replaces nothing.
**Date:** 2026-08-30
**Scope:** `/Users/dhyana/dharma_swarm` @ `ae9957c1d` on `chore/silvering-cleanup-2026-08-28`,
16 ahead / 68 behind `origin/main` (`a0a88841f`), 43 dirty working-tree entries.
**Merge-base:** `47579e203` (`git merge-base origin/main chore/silvering-cleanup-2026-08-28`)

Evidence commands: `git status --porcelain`, `git log origin/main..HEAD --oneline`,
`git show --stat <sha>`, `git diff [--stat]`, merge-base double-diff + `comm -12`,
targeted `grep`/`sed` staleness checks, `ls`/`wc`/`du` on untracked paths.

---

## 1. THE 16 COMMITS

`git log origin/main..chore/silvering-cleanup-2026-08-28 --oneline` (newest first),
judgment per commit from `git show --stat`:

| # | SHA | Subject | Judgment |
|---|-----|---------|----------|
| 1 | `9edc5e483` | docs(vision): VISION_TRANSMISSION.md (UNRATIFIED DRAFT) | **Obsolete** — main landed its own version via PR #1331 (`5c91eb078`); add/add conflict on `docs/vision_maps/VISION_TRANSMISSION.md`. Drop the branch copy at rebase. |
| 2 | `8d9631842` | feat(docops): make vision — fused projection (1,211 +) | **Merge-worthy, conflict-prone** — touches `Makefile`, `docs/governance/CANONICAL_DOC_STACK.md`, `tests/test_make_onboarding_contract.py`, all also touched on main. Core content (`scripts/docops/vision_navigation.py`, `vision_gate_key.json`, MEGAFILE_INDEX) is branch-unique. |
| 3 | `ed0ed1801` | feat(docops): Stage 0 — citation fidelity gate (470 +) | **Merge-worthy** — self-contained (`vision_citations.py` + tests); no file intersection with main. |
| 4 | `9494887d7` | docs(governance): worktree lifecycle policy + docops assertions | **Merge-worthy, conflict-prone** — `CLAUDE.md` (policy, keep), but `AUTO_INVENTORY.md` / `SOVEREIGN_MANIFEST.md` / `assertions.yaml` counts are machine-regenerable; resolve by regenerating post-rebase. |
| 5 | `d08626f70` | chore(reports): evict loop-generated receipts, ignore tool state | **Merge-worthy** — 651 lines of receipt sediment out of tracking + `.gitignore` hardening; `.gitignore` not touched on main → clean. |
| 6 | `52c9216a5` | fix(gaia): stop recording synthetic pilot verdicts to ledger | **Merge-worthy** — honesty fix, no intersection. |
| 7 | `c48dd1359` | refactor(memory-kernel): collapse self-checked promotion gates to bool | **Merge-worthy** — anti-theater, no intersection. |
| 8 | `cb7b75ac8` | refactor(telos-gates): remove Tier-C theater gates, cap Tier-C at REVIEW | **Merge-worthy** — the branch's core silvering act (11→9 gates, −562 lines incl. `telos_gates_witness_enhancement.py`). No file intersection with main, but see §4: leaves 4+ stale references that must be fixed before merge. |
| 9 | `01d9111ea` | fix(telos-gates): gate-pressure override requires operator ack | **Merge-worthy** — pairs with #8, same files + tests. |
| 10 | `53e62e123` | refactor(shakti-warrant): remove self-passing keyword scoring | **Merge-worthy, conflict-prone** — `.github/workflows/automerge.yml` also touched on main. |
| 11 | `bcfdaaa0d` | fix(packages): telos-gatekeeper honesty + canonical repo URLs | **Merge-worthy** — no intersection; canonical-URL fix aligns with the AIKAGRYA move. |
| 12 | `6e1df5f2d` | chore(governance): delete sediment scripts, phantom refs, dead workflow | **Merge-worthy, risky-with-reason** — deletes 3,912 lines: 7 `a2a_block_*` governance blocker scripts + 7 test files + `oz-verify-claim.yml`. Merge-clean (main never touched them), but after rebase grep main-side for fresh references to the deleted scripts before landing. |
| 13 | `6a4a165ed` | refactor(archive): One Wire quorum arithmetic → operator flag | **Merge-worthy, conflict-prone** — `tests/test_cybernetics_codex.py` also touched on main; source files clean. |
| 14 | `bdda6724b` | refactor(merge-control): codex-only default quorum | **Merge-worthy, conflict-prone** — `scripts/runtime/pr_merge_control.py` + `tests/test_pr_merge_control.py` both touched on main (main landed #1421 automerge-policy deadlock fix and #1322 merge P0 fixes). **Highest-risk conflict in the set** — same subsystem, both sides changed quorum/policy semantics. |
| 15 | `ab11688e8` | refactor(coherence-delta): warn-only for human-authored PRs | **Merge-worthy, conflict-prone** — `coherence-delta.yml` touched on main. |
| 16 | `ae9957c1d` | fix(uplift-guards): assurance ImportError is loud fail-open | **Merge-worthy** — honesty fix, single file, no intersection. |

**Cluster summary:** all 16 are on-theme for "silvering" (de-theater, honesty, sediment eviction) except `9edc5e483` (superseded by main's own VISION_TRANSMISSION) — drop that one at rebase; the other 15 carry.

---

## 2. THE 43 DIRTY ENTRIES

### 2a. 15 modified tracked files (`git diff` reviewed in full)

| File | What changed | Coherent with silvering? | Verdict |
|------|--------------|--------------------------|---------|
| `Makefile` | Adds `gitnexus-status` / `gitnexus-ensure` targets + `.PHONY` + help lines pointing to `scripts/governance/gitnexus_ensure.py` | **No — broken.** Verified that script does **not exist** on disk, is not tracked, and has no git history (`ls`, `git ls-files`, `git log` all empty). Targets would fail on invocation; comment also claims `make onboard` observes gitnexus via `extensions.gitnexus`, which is not in this diff. | **Revert** (or commit only together with the missing script). |
| `dharma_swarm/chetana/claude_code_plugin/INSTALL.md` | `/Users/dhyana/dharma_chetana/...` → `~/dharma_swarm/...` (2 spots) | Yes — de-Mac-ification, kills dead path | **Commit** |
| `dharma_swarm/chetana/claude_code_plugin/chetana/README.md` | Drops "on `feat/chetana-grand-memory` branch at `/Users/dhyana/dharma_chetana/`" → "in this repo" | Yes | **Commit** |
| `dharma_swarm/chetana/graph_unifier.py` (+101) | gitnexus 1.6 adaptation: `search --json` → `query` subcommand, bunyan-log-tolerant JSON parser, `--repo` from `git rev-parse`, structured hit extraction | Off-theme but finished, real fix for an API break, paired with a new test | **Commit** (with its test; note: test not run in this triage — run `pytest dharma_swarm/chetana/tests/test_graph_unifier.py` before committing) |
| `dharma_swarm/chetana/tests/test_graph_unifier.py` (+46) | Test for the above | Yes | **Commit** |
| `dharma_swarm/cybernetics_codex.py` | Hardcoded `/Users/dhyana/cybernetics_codex_note.md` → `Path.home()`-derived in `OWNED_SURFACES` | Yes | **Commit** |
| `dharma_swarm/evolution_safety.py` | Removes `Path("/Users/dhyana/dharma_swarm")` from `_PROTECTED_LITERAL_ROOTS` | Yes — redundant with existing `Path.home() / "dharma_swarm"` entry on this host | **Commit** (with test below) |
| `dharma_swarm/forge_v1/run_real.py` | Docstring: absolute venv paths → `PYTHONPATH=. .venv/bin/python` | Yes | **Commit** |
| `dharma_swarm/forge_v1/smoke_live.py` | Same docstring de-absolutizing | Yes | **Commit** |
| `dharma_swarm/memory_kernel/context_eval_cases.py` | 3 eval-case content strings: `/Users/dhyana/.dharma/...` → `Path.home()`-derived | Yes; strings are fixture inputs — equivalent on this host, but re-run the context-eval suite after committing | **Commit** |
| `dharma_swarm/operator_core/control_surface_memory.py` | Canary context string → `Path.home()`-derived | Yes | **Commit** |
| `dharma_swarm/terminal_bridge_text.py` | Default `repo_root="/Users/dhyana/dharma_swarm"` → derived from `__file__` | Yes | **Commit** |
| `docs/docops/AUTO_INVENTORY.md` | Regenerated metric block (1,064→1,063 modules, etc.) | Yes — generated block reflecting branch deletions | **Commit** (or regenerate after rebase; will conflict with main's count-reconcile commits either way) |
| `docs/governance/SOVEREIGN_MANIFEST.md` | Same count refresh in the metrics table | Yes | **Commit** (same regeneration note) |
| `tests/test_evolution_safety.py` | Protected-roots assertion: `/Users/dhyana/dharma_swarm` → `/app/dharma_swarm` | Yes — pairs with `evolution_safety.py` | **Commit** |

### 2b. 28 untracked entries

| Entry | Verdict | Reason |
|-------|---------|--------|
| `data` (repo root) | **Compost** | Verified: 255-byte ASCII junk word-list (numbers + tantra/kundalini/science word salad). `file` says "c program text" — it is not code. Do not commit; delete. |
| `forge_lab/` (repo root) | **Compost** | Verified: empty directory (`ls -la` → only `.`/`..`), created Aug 28 22:45. Git doesn't track it (absent from porcelain). `rmdir`. |
| `docs/plans/THE_BLUEPRINT_2026-08-29.md`, `THE_BLUEPRINT_AUDIT_GOAL.md`, `ONE_WORLD_2026-08-30.md`, `reports/2026-08-30_blueprint_adversarial_audit.md` | **Keep** | Known-good per task brief; content not reviewed. |
| `docs/plans/2026-08-18-spec-001-mechanical-hardening-v2.md` | **Keep** | Self-labeled `working_plan` DRAFT pending operator admission; harmless doc, belongs with the planning corpus. |
| `reports/agentops/decorrelated_review_council/` (14 `hold_blockers` .json/.md + 4 `evidence/` + 2 `prompts/` files, July 2026) | **Compost (or keep-ignored)** | Loop-generated review receipts — exactly the class commit `d08626f70` evicted from tracking and gitignored on this branch. Consistent action: delete locally or leave untracked under the ignore rules. |
| `reports/agentops/work_packets/agent-governance-workbench-1000x/` (80K, ~11 docs + closeout receipt) | **Needs-owner** | Deliberate work product (specs, decision doc, verification ladder), not loop sediment. Operator decides: commit under reports/ or move out of repo. |
| `reports/agentops/work_packets/dharma-trust-forge-viability/` (16K) | **Needs-owner** | Same class — deliberate analysis packet. |
| `reports/wayfinder/research/terminal_chassis_and_bleeding_edge_tui_2026-08-06.md` | **Needs-owner** | Single research note; keep-or-compost is the operator's call. |

---

## 3. CONFLICT FORECAST

Method: `git diff --name-only <merge-base>..HEAD | sort -u` (104 files) vs
`git diff --name-only <merge-base>..origin/main | sort -u` (528 files), intersect with `comm -12`.

**13 files touched on both sides (conflict candidates), with the branch commit that touches them:**

| File | Branch side | Main side (why) | Expected severity |
|------|-------------|------------------|-------------------|
| `scripts/runtime/pr_merge_control.py` | `bdda6724b` (codex-only quorum) | #1421 automerge deadlock fix, #1322 merge P0 fixes | **High** — same policy semantics changed both sides |
| `tests/test_pr_merge_control.py` | `bdda6724b` | same PRs | **High** |
| `docs/vision_maps/VISION_TRANSMISSION.md` | `9edc5e483` (add, 707 lines) | #1331 `5c91eb078` (add, own version) | **High** — add/add; resolve by dropping branch version |
| `Makefile` | `8d9631842` (vision targets) + dirty gitnexus hunks | main-side changes | Medium; resolve after reverting dirty gitnexus hunk |
| `CLAUDE.md` | `9494887d7` (worktree lifecycle policy) | main-side edits | Medium — textual |
| `.github/workflows/automerge.yml` | `53e62e123` | #1421 | Medium |
| `.github/workflows/coherence-delta.yml` | `ab11688e8` | main-side edits | Medium |
| `tests/test_cybernetics_codex.py` | `6a4a165ed` | main-side edits | Medium |
| `tests/test_make_onboarding_contract.py` | `8d9631842` | main-side edits | Medium |
| `docs/governance/CANONICAL_DOC_STACK.md` | `8d9631842` | main-side edits | Low |
| `docs/docops/AUTO_INVENTORY.md` | `9494887d7` + dirty count refresh | ≥6 "reconcile generated counts" commits on main | Low — **regenerate, don't hand-merge** |
| `docs/docops/assertions.yaml` | `9494887d7` | main-side edits | Low |
| `docs/governance/SOVEREIGN_MANIFEST.md` | `9494887d7` + dirty count refresh | main-side edits | Low — regenerate counts |

**Non-conflicts of note:** `dharma_swarm/telos_gates.py`, `gaia_platform.py`, `shakti_warrant.py`,
`memory_kernel/promotion_gate.py`, `archive.py`, the 7 deleted `a2a_block_*` scripts, and
`dharma_swarm/telos_gates_witness_enhancement.py` (deleted on branch) are **not** touched by main's
68 commits — the silvering core merges clean.

---

## 4. STALENESS SWEEP — verified today (2026-08-30)

All four audit findings still present. Each is a fix-before-merge item:

1. **`dharma_swarm/telos_gates.py:3`** — docstring still reads
   `Eleven gates from Akram Vignan mapped to computational safety checks.` (file actually has 9).
   Confirmed via `sed -n '1,8p'`.
2. **`dharma_swarm/claude_hooks.py:142`** — comment still reads `# Gate sweep — check all 11 core gates`
   ahead of the `DEFAULT_GATEKEEPER.check(...)` baseline call. Confirmed via `grep -n "11 core gates"`.
3. **`hooks/telos_gate.py:118–123`** — still hard-passes **both** deleted gates:
   `results["SVABHAAVA"] = ("PASS", "")` (118–119) and
   `results["BHED_GNAN"] = ("PASS", "Doer-witness distinction noted")` (121–123),
   plus `"BHED_GNAN": "C"` in the `GATES` map at line 25. Confirmed via `sed -n '115,130p'`.
   This file now reports gates that `dharma_swarm/telos_gates.py` no longer defines — the two gate
   vocabularies have diverged on this branch.
4. **`dharma_swarm/operator_brief/insight_brief.py:689–693`** — still fabricates a BHED_GNAN row:
   `keeper_gates.get("BHED_GNAN") or (GateResult.PASS, "Doer-witness distinction noted")`, so the
   brief always emits a BHED_GNAN PASS even though the gate no longer exists upstream. Docstrings at
   lines 14 and 662 also still cite BHED_GNAN. Confirmed via `sed -n '655,700p'`.

**Secondary sweep (not in the original audit, found by repo-wide `grep SVABHAAVA|BHED_GNAN`, ~180 hits):**
- `dharma_swarm/splash.py:318-319, 403, 496` — renders `SVABHAAVA ◇ BHED_GNAN` in the TUI splash (cosmetic, but now advertises deleted gates).
- `dharma_swarm/architecture/PRINCIPLES.md:83` — lists the 11-gate set incl. both deleted gates, citing `hooks/telos_gate.py`.
- `dharma_swarm/foundations/` (`ECONOMIC_VISION.md:335`, `PILLAR_08:174`, `PILLAR_09:42,279-280`, `PILLAR_10:319`, `GLOSSARY.md:19,96`) — doctrine docs describing the 11-gate system.
- `dharma_swarm/reports/` historical/verification/loop-closure receipts — historical records; **leave alone** (receipts describe the past truthfully).
- Judgment: items 1–4 above are code-truth bugs → fix before merge. splash.py + PRINCIPLES.md are one-PR follow-ups. foundations/ doctrine docs are an operator decision (they describe the design lineage, not the live registry); reports/ must not be rewritten.

---

## 5. MERGE-READINESS VERDICT

**Verdict: ready after listed fixes, with a rebase strategy** (not ready as-is — a dirty tree containing
one broken Makefile hunk, four code-level stale-gate references, and one superseded add/add doc commit
stand between here and a clean merge).

**Recommended order of operations:**

1. **Settle the working tree** (43 entries → 0):
   - Revert the `Makefile` gitnexus hunks (targets point to nonexistent `scripts/governance/gitnexus_ensure.py`).
   - Commit the other 14 tracked modifications as one `chore(de-mac): port hardcoded operator paths, refresh counts, gitnexus 1.6 query API` commit (or split: de-mac paths / gitnexus / count refresh). Run `pytest dharma_swarm/chetana/tests/test_graph_unifier.py tests/test_evolution_safety.py` first.
   - Delete `data` and `forge_lab/`; compost the `decorrelated_review_council` receipts; operator-decide the two `work_packets` subdirs and `reports/wayfinder/`; stage the four blueprint/audit docs + the spec-001 v2 draft if they belong in the merge.
2. **Fix the four stale gate references** (§4 items 1–4) as one `fix(telos-gates): finish Tier-C gate removal` commit: docstring count, `claude_hooks.py` comment, `hooks/telos_gate.py` GATES map + hard-pass blocks, `insight_brief.py` fabricated row + docstrings. Run `pytest tests/test_telos_gates.py` + the operator-brief and claude-hooks test files.
3. **Rebase onto `origin/main`**, handling the 13 conflict files per §3: drop `9edc5e483`'s VISION_TRANSMISSION in favor of main's; regenerate `AUTO_INVENTORY.md` / `SOVEREIGN_MANIFEST.md` counts post-rebase rather than hand-merging; give real review to `pr_merge_control.py` + its test (both sides changed merge-quorum policy — this is the one conflict with semantic, not textual, stakes).
4. **Post-rebase verification:** grep main-side for references to the 7 deleted `a2a_block_*` scripts (`6e1df5f2d`); run the touched test files (`test_pr_merge_control`, `test_cybernetics_codex`, `test_make_onboarding_contract`, `test_vision_citations`, `test_vision_navigation`, `test_telos_gates`, `test_shakti_warrant`, `test_memory_kernel_promotion_gate`, `test_gaia_platform`); run `make onboard` read-only check.
5. **Then merge.** Follow-ups that do not block: splash.py gate names, PRINCIPLES.md gate list, foundations/ doctrine docs (operator decision).

**Not done in this triage (read-only scope):** no tests were executed; test outcomes above are
recommendations, not results. The `graph_unifier.py` gitnexus change is reviewed but unverified at runtime.
