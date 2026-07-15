# Titanium WP-00 — Governance Admission DRAFT (prep-only, not merged)

**Doc role (per `docs/AGENTS.md`):** `working_plan` — a **draft** of the WP-00
admission materials, subordinate to
`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md` (spec:152-203, the
authority). **This file changes no governance state.** It does not edit
`docs/governance/ACTIVE_TRACK.yaml` (owned by `onboard-one-door-2026-07`; admission
is gated). It is a ready-to-review artifact so that, the moment the gate clears
(C1 + WP-O5 + WP-O6 + TERMINAL-PROOF merged — see `TITANIUM_PREP_2026-07-15.md` §1),
WP-00 execution starts warm.

**Author seat:** fable_claude_code. **Date:** 2026-07-15. **Entry SHA:** `971923a71c18`.

WP-00's seven required steps (spec:152-162):

1. Free a WIP slot for Titanium — **operator resolved D-T1 (2026-07-15): graduate
   `onboard-one-door-2026-07`, NOT move company-builder. See §Operator Decisions
   D-T1 and the Critical-path section below.** This is the same act that clears the
   Titanium gate, so it unifies the WIP-room and gate dependencies.
2. Capture the dynamic campaign baseline from clean current `origin/main` (spec:61-78) —
   fresh commands, not copied numbers. Drift already observed (tracks 9→11, DocOps
   counts moved; `TITANIUM_PREP_2026-07-15.md` §2 "Baseline drift").
3. Add the operator-ratified `repository-titanium-hardening-2026-07` track for the
   **currently unowned Phase 0 surfaces only** (draft YAML below).
4. Keep every already-owned surface with its current owner; the new track must **not**
   claim Go, terminal, graph, organism, or Mike-owned files (spec:159).
5. Add explicit `complements` relations to the owner tracks (spec:160).
6. Add Phase 0 acceptance criteria that execute **behavioral commands, not
   file-existence checks** (spec:161).
7. Run `render_active_track_includes.py --check` and the track-status checker before
   merging admission (spec:162).

---

## Proposed track entry (DRAFT — for operator ratification only)

Ownership list transcribed **exactly** from spec:164-193. No surface outside that
list is claimed. Go/terminal/graph/organism/Mike surfaces are deliberately absent
(spec:159). `pyproject.toml` is **not** claimed — it stays with the DharmaGraph
owner until M6-1 lands (spec:145; `ACTIVE_TRACK.yaml:2025-2028`).

```yaml
  - id: repository-titanium-hardening-2026-07
    name: Titanium Repository Hardening — Phase 0 verification-truth substrate
    status: ACTIVE            # pending operator ratification of D-T1 + this entry
    opened_at: "2026-07-15"   # stamp to the actual admission-merge date
    verified_at: "2026-07-15"
    ttl_days: 30
    owner: "@AmitabhainArunachala"
    serves: substrate-nativeness
    complements:              # spec:160 — the owner tracks in spec:141-148
      - merge-master-mike-d4-2026-06
      - sovereign-safety-tcb-2026-07
      - dharmagraph-engine-2026-07
      - organism-rewire-2026-07
      - helm-worldclass-terminal-2026-06
      - loop-closure-2026-06
    owned_surfaces:           # spec:164-193 — EXACT; unowned Phase 0 surfaces only
      - Makefile
      - Dockerfile
      - .github/workflows/hermetic.yml
      - .github/workflows/tests.yml
      - .github/workflows/ci-parity.yml
      - .github/workflows/docops.yml
      - .github/workflows/docops-reconcile-main.yml
      - .github/workflows/pr-dedupe.yml
      - .github/workflows/bot-pr-limit.yml
      - docs/governance/CI_TRUTH_CONTRACT.json
      - scripts/governance/ci_parity_manifest.json
      - scripts/governance/check_ci_parity.py
      - scripts/runtime/ci_truth.py
      - scripts/governance/run_semgrep_with_ca.sh
      - scripts/uplift_guards/shakti_warrant_guard.py
      - scripts/uplift_guards/run_pre_commit.py
      - scripts/governance/check_shakti_warrant.py
      - scripts/governance/check_nats_substrate_contract.py
      - scripts/governance/check_nats_live_production_evidence.py
      - scripts/governance/run_nats_live_production_matrix.py
      - .github/workflows/a2a-agni-live-contact.yml
      - scripts/docops/**
      - dharma_swarm/build_engine.py            # TIT-002 only (spec:188)
      - dharma_swarm/autonomous_agent.py        # TIT-002 leaked-process investigation only (spec:189)
      - docs/docops/AUTO_INVENTORY.md
      - docs/governance/SOVEREIGN_MANIFEST.md   # count-managed blocks only (spec:191)
      - api/main.py                             # WP-0S narrow fail-closed containment only (spec:192)
      # + existing API-auth tests (tests/test_api_auth.py NEW, tests/test_verify_api.py)
      #   for the WP-0S packet only (spec:192)
      # + Phase 0 contract tests introduced by this specification (spec:193):
      #   tests/test_bootstrap_contract.py, tests/test_verifier_selfcheck_contract.py,
      #   tests/test_semgrep_wrapper.py, tests/test_uplift_guard_subprocess.py,
      #   tests/test_nats_verification_split.py, tests/test_nats_live_production_evidence.py,
      #   tests/test_ci_truth.py, tests/governance/test_ci_parity_guard.py,
      #   tests/test_docops_reconcile_workflow.py, tests/test_pr_dedupe_workflow.py,
      #   tests/test_fast_suite_isolation.py, tests/test_polyglot_ci_contract.py
    non_goals:
      - Claiming Go, terminal, graph, organism, or Mike-owned surfaces (spec:159).
      - Creating a new truth store, receipt format, policy engine, or catch-all module (spec:44).
      - Any Phase 1+ feature/security-boundary work before the Phase 0 exit gate passes
        on merged main (spec:15, spec:1153).
    description: >
      Sequencing track for the Titanium Phase 0 verification-truth campaign
      (docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md). Owns ONLY the
      Phase 0 surfaces that had no owner broad enough for this campaign (spec:150).
      Admitted through WP-00 after the One-Door gate cleared. Composes existing
      owners and gates; creates no new substrate. Each implementation packet ships
      as one bounded PR under one owner with a failing-first contract test, a
      finding id, and a rollback (spec:33-44). North star: main truthfully green
      from a clean clone (spec:19, spec:292).
    completion_criteria:      # spec:161 — behavioral commands, not file-existence
      - id: wp0a_hermetic_bootstrap
        kind: command_passes
        command: ["make", "bootstrap"]
      - id: wp0b_verifier_truth_contract
        kind: command_passes
        command: ["python3", "-m", "pytest", "tests/test_verifier_selfcheck_contract.py", "-q"]
      - id: wp0c1_scanner_subprocess_fail_closed
        kind: command_passes
        command: ["python3", "-m", "pytest", "tests/test_semgrep_wrapper.py", "tests/test_uplift_guard_subprocess.py", "-q"]
      - id: wp0d_fast_suite_determinism
        kind: command_passes
        command: ["make", "test-fast"]        # must pass twice consecutively (spec:754)
      - id: wp0e_hermetic_governance
        kind: command_passes
        command: ["make", "governance-all"]   # hermetic; no live-NATS freshness dependency (TIT-009)
      - id: wp0f1_ci_truth_parity
        kind: command_passes
        command: ["python3", "-m", "pytest", "tests/test_ci_truth.py", "tests/governance/test_ci_parity_guard.py", "-q"]
      - id: wp0g_strict_docops
        kind: command_passes
        command: ["make", "docops-integrity"]
      # NEEDS_HOST-class criteria (recorded, but honestly host-gated, spec:50):
      #   - make go-ci            (needs Go 1.26 toolchain; host has go1.24.7)
      #   - make terminal-check   (needs bun + terminal lane wired, TIT-015)
      #   - check_ci_parity.py --live (needs Administration:read, TIT-007 live leg)
      # These report NEEDS_HOST off their owner host and never convert to PASS.
```

**Notes for the admitting agent (not part of the YAML):**

- The `completion_criteria` above are **behavioral** (`make`/`pytest` invocations),
  satisfying spec:161. File-existence assertions are deliberately excluded.
- Several exit-gate commands are genuinely host-gated (Go 1.26, bun, live branch
  protection). Per the claim boundary (spec:50) these must surface `NEEDS_HOST`, not
  a false `PASS`. They are listed as comments so the operator can decide whether to
  encode them as `NEEDS_HOST`-typed criteria or leave them to the WP-0I clean-room
  proof on the owner host.
- Step 7 (spec:162) — before the admission PR merges, run
  `python3 scripts/governance/render_active_track_includes.py --check` and
  `python3 scripts/governance/check_track_status.py`. Both were green at entry SHA
  (`make docops-integrity` exit 0 includes the render check; the projection
  regenerated cleanly). Re-run them against the admission branch, not this baseline.
- WIP: admitting an 11th→12th track exceeds the CLAUDE.md WIP warn (8) and hits the
  max (11). D-T1 (moving `company-builder-parity`) is the intended relief valve so
  the portfolio stays within the ceiling; sequencing D-T1 before/with this admission
  is a governance requirement, not optional (spec:156, and the CLAUDE.md WIP law).

---

## Operator Decisions (P3) — requests the implementation agent may NOT self-decide

These are external prerequisites (spec:1411-1422). An unavailable prerequisite
blocks only its dependent packet; it never justifies weakening evidence (spec:1422).

### D-T1 — WIP room for Titanium (spec:156, spec:1413) — **RESOLVED 2026-07-15**

- **Operator decision (2026-07-15):** the WIP slot for Titanium comes from
  **graduating `onboard-one-door-2026-07`** ("the make onboard hardening"), **not**
  from moving `company-builder-parity-2026-07`. Company-builder stays as-is.
- **Why this supersedes spec:156:** the operator holds portfolio authority
  (CLAUDE.md portfolio model). This is the cleaner path because graduating
  onboard-one-door is *already* the Titanium gate condition
  (`ACTIVE_TRACK.yaml` 1864-1866, 1909-1912): when onboard-one-door closes,
  the same act (a) frees the WIP slot **and** (b) clears the C1/proof gate.
  One graduation resolves both the WIP ceiling and the gate.
- **Revenue spine stays covered:** `revenue-external-humans-served` remains covered
  by `darshan-publication-2026-07` (and company-builder), so nothing is orphaned.
- **What this makes the real work:** graduating onboard-one-door requires closing its
  six open blocker items (`ACTIVE_TRACK.yaml` 2013-2036) in dependency order —
  C1 → D2 → WP-O5; (WP-O5 + M6-1) → WP-O6 → TERMINAL-PROOF. See the critical-path
  note below.
- **Superseded:** the WP-00 draft's `completion_criteria` and admission steps stand,
  but WP-00 step 1 is now "graduate onboard-one-door," not "move company-builder."

### D-T2 — Extend `organism-rewire-2026-07` ownership to the Go-trigger seam (spec:195-203) — **RATIFIED 2026-07-15**

- **Operator decision (2026-07-15): RATIFIED.** Grant `organism-rewire-2026-07` the
  seven Go-seam files exactly as listed below. Enactment is a one-line-per-file
  addition to that track's `owned_surfaces` in `docs/governance/ACTIVE_TRACK.yaml`
  (a governance-surface edit; lands via the organism-rewire owner or the WP-00
  admission bundle, since the Titanium lane does not own the ledger file).


- **What:** WP-0C2 (version-aware Go capability) must edit the Go bridge seam, which
  is `organism-rewire`-adjacent but not yet in its `owned_surfaces`. Spec:195-203
  proposes extending `organism-rewire-2026-07`, **with operator ratification**, to:
  - `scripts/runtime/github_ingestor_runner.py`
  - `tests/test_github_ingestor_runner.py`
  - `tests/test_go_evidence_ingestor_bridge.py`
  - `tests/test_go_github_ingestor_bridge.py`
  - `tests/test_go_world_signal_bridge.py`
  - `tests/test_go_receipt_identity_verify.py`
  - `tests/test_go_adapter_contracts.py`
- **Why it needs you:** these are Go/organism surfaces the hardening track is
  explicitly forbidden to claim (spec:159). Only the operator can extend an existing
  owner's surface list. WP-0C2's declared owner is "`organism-rewire-2026-07` after
  WP-00 ownership extension" (spec:654).
- **Decision requested:** ratify the ownership extension above onto
  `organism-rewire-2026-07` (the track already governs the Go tools, world radar,
  `Dockerfile.swarm`, `go_invoke.py` — this closes the trigger-seam gap).
- **Blocks:** WP-0C2 (spec:651-707) only; the rest of Phase 0 can proceed without it.

### Related operator prerequisites already in the spec queue (spec:1409-1421)

Not new asks — flagged so they are not forgotten when the gate clears:

- Approve/replace the six-context required-check set for WP-0F1 (spec:1415, spec:844-853).
- Provision Administration-read for live branch-protection parity (spec:1416) — this
  is what makes TIT-007's live leg move from NEEDS_HOST to verifiable.
- Confirm the DocOps reconcile credential or approve reviewed-PR-only delivery (spec:1417).
- Define the minimum human-approval rule for human- and bot-authored PRs (spec:1418).
- Record the FastAPI deployment exposure status before WP-0S
  (`CONTAINED`/`PRIVATE_ONLY`/`NOT_DEPLOYED`/`BLOCKED_OPERATOR`, spec:313-320, spec:1419).
  TIT-010 is confirmed live (`TITANIUM_PREP_2026-07-15.md` §2) — if the service is
  reachable beyond loopback, containment happens immediately, not after the stack.
- Nominate the independent WP-0I reviewer after every packet merges (spec:1420).

---

## Critical path to Titanium (post-D-T1, unified 2026-07-15)

Per D-T1, one graduation unblocks everything: **close `onboard-one-door-2026-07`'s
six open items → it graduates → WIP slot frees + Titanium gate clears → WP-00
admits.** Dependency order (`ACTIVE_TRACK.yaml` 1909-1912): **C1 → D2 → WP-O5;
(WP-O5 + M6-1) → WP-O6 → TERMINAL-PROOF.**

| Item | Kind | Who closes it | Status / what it needs |
|---|---|---|---|
| **C1** | governance | merge authority (Mike/operator) + this seat can assemble the hermetic evidence | Capture post-WP-O4 required-context + parity-manifest + automerge + merge-queue evidence proving the strict door fails closed. Live branch-protection leg needs **Administration:read** (operator, spec:1416) — until provisioned it is NEEDS_HOST. `ACTIVE_TRACK.yaml:2013-2016` |
| **D2** | governance | **operator only** | Author the strict-by-default ratification record (spec §9.2 format). Cannot be minted by any agent. Depends on C1. `:2017-2020` |
| **WP-O5** | code | onboard-one-door owner | Promote strict verdict exits to default, one `--no-strict` deprecation cycle. After C1 + merged D2. `:2021-2024` |
| **M6-1** | governance | **DharmaGraph owner** | Land the exact mutmut/`pyproject.toml` config under its packet (or an explicit transfer). Coordination item. `:2025-2028` |
| **WP-O6** | code | onboard-one-door owner | Terminal-envelope proof (perf/replay/concurrency/mutation/exit-matrix/no-write-no-network). After WP-O5 + M6-1. `:2029-2032` |
| **TERMINAL-PROOF** | governance | **this seat (fable_claude_code) qualifies** — authored none of WP-O1..O6 | Decorrelated verifier runs §13 on a sterile clone and merges the proof. Runs LAST, after WP-O6 merges. `:2033-2036` |

**Only-you items (front of chain):** provision **Administration:read** (unblocks C1's
live leg) and author the **D2** ratification record (after C1). **Coordination:**
M6-1 needs the DharmaGraph owner. **This seat can drive:** C1 hermetic-evidence
assembly now (read-only), and the TERMINAL-PROOF verification once WP-O6 merges.
