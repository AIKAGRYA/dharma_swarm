# Titanium Hardening — Prep-Cycle Report (Gate State + Findings Drift)

**Doc role (per `docs/AGENTS.md`):** `working_plan` — a prep-only campaign artifact
subordinate to `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md`
(the authority for this lane), `CLAUDE.md`, and
`docs/governance/ACTIVE_TRACK.yaml`. It creates no runtime substrate, no
governance owner, and no new truth store. It records read-only observations.

**Author seat:** fable_claude_code (persistent orchestrator seat), branch
`claude/titanium-repo-hardening-5duhc3`.
**Entry SHA:** `971923a71c18b0effb5bbf2db279e85e8a7db413` (clean, `origin/main` ahead 0 / behind 0).
**Onboard verdict at entry:** `DHARMA ONBOARD — READY (exit 0)` after regenerating
the active-track projection with `python3 scripts/governance/check_track_status.py`
(the projection was stale at first run; regeneration is its owner command, not a state edit).
**Date:** 2026-07-15.

Citation-or-silence: every claim below carries a `file:line` anchor or a runnable
command with its observed exit code. Uncited claims carry zero weight.

---

## 1. Gate-state report — declared mode: **PREP-ONLY**

The gate (spec:5, spec:13, spec:15; `ACTIVE_TRACK.yaml` onboard-one-door
description lines 1864-1866 and 1909-1912): Titanium WP-00 governance admission
and dynamic baseline capture stay **BLOCKED** until the One-Door campaign's
implementation, merge-blocking CI admission (**C1**), and independent clean-room
proof (**TERMINAL-PROOF**) have MERGED. No feature work, broad refactors, or live
self-evolution before the independent Phase 0 clean-room proof passes on merged
`main` (spec:15).

Live ledger status of the six named items, read from
`docs/governance/ACTIVE_TRACK.yaml` at entry SHA:

| Gate item | Ledger `blocker` | State | `file:line` |
|---|---|---|---|
| **C1** — post-WP-O4 required-context / parity / automerge / merge-queue evidence proving the strict door fails closed | `true` | PENDING | `ACTIVE_TRACK.yaml:2013-2016` |
| **D2** — operator ratification of strict-by-default (after WP-O4/C1; author cannot mint it) | `true` | PENDING | `ACTIVE_TRACK.yaml:2017-2020` |
| **WP-O5** — promote strict verdict exits to default after C1 + merged D2 | `true` | PENDING | `ACTIVE_TRACK.yaml:2021-2024` |
| **M6-1** — DharmaGraph owner must land exact mutmut/pyproject config before WP-O6 touches it | `true` | PENDING | `ACTIVE_TRACK.yaml:2025-2028` |
| **WP-O6** — terminal-envelope proof (perf/replay/concurrency/mutation/exit-matrix/no-write-no-network) | `true` | PENDING | `ACTIVE_TRACK.yaml:2029-2032` |
| **TERMINAL-PROOF** — decorrelated verifier runs §13 on a sterile clone and merges the proof | `true` | PENDING | `ACTIVE_TRACK.yaml:2033-2036` |

**Verdict:** all six are `blocker: true` / PENDING. The dependency chain in the
ledger is `C1 → D2 → WP-O5`; `WP-O5 + M6-1 → WP-O6 → TERMINAL-PROOF`
(`ACTIVE_TRACK.yaml:1909-1912`). None has cleared. **Titanium is in PREP-ONLY
MODE.** No WP-00 admission, no baseline capture, no implementation packet is legal
this cycle. The prep work below is the legal, valuable surface (spec Agent
entrypoint / autonomous protocol; handoff PREP-ONLY items P1–P4).

Reproduce the gate read:

```bash
git rev-parse HEAD                    # 971923a71c18...
python3 scripts/governance/check_track_status.py   # regenerate projection (owner cmd)
make onboard                          # READY (exit 0)
sed -n '2013,2036p' docs/governance/ACTIVE_TRACK.yaml   # the six gate items
```

---

## 2. Findings-drift report (P1)

The audit that produced the finding registry predates this SHA by ~90 commits
(audit baseline `212df1a8c22b`, spec:59; entry SHA `971923a`). Each `TIT-NNN`
finding was independently re-derived read-only against current `main`. Verdicts:
**STILL_REPRODUCES** / **DRIFTED_PARTIAL** / **RESOLVED** / **NEEDS_HOST**.

**Summary:** of 15 findings — **11 STILL_REPRODUCES**, **2 DRIFTED_PARTIAL**
(TIT-002 mechanism moved; TIT-008 strict-red half resolved, reconcile half
NEEDS_HOST), **1 RESOLVED with a residual guard obligation** (TIT-006), and
**TIT-007's live-branch-protection leg is NEEDS_HOST** (needs GitHub
Administration:read; not runnable from this seat).

| ID | Sev | Verdict | Key current evidence (`file:line` / command→exit) |
|---|---:|---|---|
| TIT-001 | 4 | **STILL_REPRODUCES** | `Makefile:336-347` — `verifier-selfcheck` runs syntax-check, F821, test **collection** (`--collect-only`, not execution), onboard, then prints `ALL GATES FUNCTIONAL`. No behavioral test runs, yet `make test-fast` is red (exit 2, §below). Claim ⊃ evidence. |
| TIT-002 | 4 | **DRIFTED_PARTIAL** | `make test-fast` still red (exit 2). But the audited offender `tests/test_build_engine.py::TestDryRun::test_dry_run_no_files_changed` now **passes in-suite** and alone (0.38s). New in-suite failure: `tests/conformance/test_repo_ratchet_holds.py::test_repo_quality_ratchet_has_no_regressions` hits the 10s cap (`Timeout (>10.0s)` at `ast.py:50`); alone under a 120s cap it passes in **7.45s**. Mechanism looks like an inherently ~7–10s repo-scan test tripping the fixed cap, not the audited leaked-resource coupling. **WP-0D's allowed files (`test_build_engine.py`, `autonomous_agent.py`) may no longer be where the leak/cost is** — re-bisect before editing. |
| TIT-003 | 3 | **STILL_REPRODUCES** | `dharma_swarm/world_radar/go_invoke.py:46` gates on `shutil.which("go")` presence only; version-aware check lives only in `tests/test_go_adapter_contracts.py:36-42`. `scripts/runtime/github_ingestor_runner.py:72` presence-only; incompatible-Go (host `go1.24.7` vs `tools/*/go.mod` `go 1.26`) reaches `failed/` move at `:126-129` (spec-forbidden). Missing-Go path hardened to `needs_host` at `:98-103`. |
| TIT-004 | 4 | **STILL_REPRODUCES** | `scripts/governance/run_semgrep_with_ca.sh:81-84` → `exit 0` when semgrep absent. `Makefile:590` `governance-all` depends on `semgrep` (`Makefile:372-378`). Observed: `run_semgrep_with_ca.sh --config .semgrep --metrics=off` → **EXIT=0** (semgrep not installed here). gitleaks (`Makefile:383-384`, bare binary) still hard-fails, asymmetry intact. |
| TIT-005 | 4 | **STILL_REPRODUCES** | `scripts/uplift_guards/shakti_warrant_guard.py:92-101` — `subprocess.run(...)` with no `stdin=DEVNULL`, no `timeout=`. Child `scripts/governance/check_shakti_warrant.py:248-249` does `sys.stdin.read()` on non-tty inherited stdin → unbounded block. `make uplift-guards` → `run_pre_commit.py` (`Makefile:436-437`) reaches it in-process. |
| TIT-006 | 4 | **RESOLVED** (residual guard obligation) | Current `docs/governance/CI_TRUTH_CONTRACT.json` parses with **0 duplicate keys** (`json.load` with pairs hook); `advisory` is one list of 20 incl. `tests_py311`, `tests_py312`, `gitleaks`. Dup existed through commit `9d56a70`, gone at `7406a9d`. **But** WP-0F1's "reject future duplicate JSON keys" guard is not yet in place — the resolution is data-state, not enforced. |
| TIT-007 | 4 | **STILL_REPRODUCES** (+ live leg NEEDS_HOST) | Two committed required-sets still diverge: `CI_TRUTH_CONTRACT.json` `required` = {docops_integrity, quality_ratchet, coherence_delta, onboarding_macos_compatibility}; `scripts/governance/ci_parity_manifest.json` `required_contexts` = {pytest 3.11, pytest 3.12, gitleaks, DocOps integrity gate, Coherence Delta PR body, Onboarding admission parity}. `pytest×2`+`gitleaks` are **required** in the manifest but **advisory** in CI Truth — direct contradiction. Consolidated from 3→2 committed defs (automerge.yml/pr_merge_control.py no longer carry private lists). Live branch-protection comparison = **NEEDS_HOST** (`check_ci_parity.py --live` needs Administration:read). |
| TIT-008 | 4 | **DRIFTED_PARTIAL** | Strict-red half **resolved on `main`**: `make docops-integrity` → exit 0 ("DocOps integrity checks passed", "Hygiene integrity OK", `render_active_track_includes.py --check` clean); only a non-blocking WARN (`QL-R1.yaml next_review 2026-07-12 stale`). Reconcile-workflow-fragility half (force-update loses checks; PR-count drift advisory) is CI-observable = **NEEDS_HOST**; PR #943 "reconcile generated counts" is open, indicating the loop is live. |
| TIT-009 | 3 | **STILL_REPRODUCES** (worse than described) | `governance-all` (`Makefile:590`) → `nats-substrate-contract` (`Makefile:419-431`) runs `check_nats_live_production_evidence.py --max-age-hours 24`. Observed on this clone: evidence **13 days stale** → **exit 1**. The "hermetic" `check_nats_substrate_contract.py` **itself** invokes the live-freshness check internally (`NATS_CONTRACT_FAIL … fresh live NATS production evidence check failed`, exit 1). A clean clone cannot make `governance-all` green for a non-code reason. |
| TIT-010 | 5 | **STILL_REPRODUCES** (broader) | `api/main.py:322-326` — key unset (`DASHBOARD_API_KEY`) ⇒ `BearerAuthMiddleware` passes every route through, incl. all mutating `/api` routes. Scope test is `path.startswith("/api")` (`api/main.py:336-338`), so GraphQL (`api/routers/graphql_router.py:18`), holon POST `/holon/{name}/chat` (`api/routers/holon.py:43`), and both WS mounts (`api/routers/chat.py:1353`; agents WS via `BaseHTTPMiddleware` skipping ASGI `websocket` scope) bypass the bearer even with a key set. `Dockerfile:40` ships this prod shape with no auth material required. `tests/test_api_auth.py` is **absent** — no regression test pins the invariant. (A2A gateway has its own `X-A2A-Key`, not the bearer surface.) |
| TIT-011 | 5 | **STILL_REPRODUCES** (header honestly downgraded) | `dharma_swarm/graph/durable_invoker.py` — provider call at `:506-508`, durable completion write at `:534-540`. Crash in that window leaves a `started` row; replay reclaims a stale record (`:486-489`, `:493-501`) and **re-executes the provider at `:506`** — no provider idempotency key is passed to `self._inner`. Fence commit `3c10ae4` closed only concurrent-takeover races and honestly rewrote the header to "effectively-once" (`:2-4`); two inline "exactly-once" comments remain (`:481`, `:599`). |
| TIT-012 | 4 | **STILL_REPRODUCES** | `INTERFACE_MISMATCH_MAP.md` — **BR-007** "runtime.db path drift + store split" is a **BLOCKER reopened 2026-07-14** (`:37`); NEW-05 GUARDED (`:31`), NEW-07 PARTIAL+ (`:32`), NEW-08 PARTIAL+ (`:33`). No cross-store authority/lease mechanism in `dharma_swarm/swarm.py` or `runtime_state.py` (grep for lease/authority/canonical finds only a filesystem-zone lease at `runtime_state.py:99-108`, not a store-authority table). |
| TIT-013 | 4 | **STILL_REPRODUCES** | `ratchet.py --explain modules_over_500_lines` = **207** (== audit baseline 207); `silent_exception_swallows` = **241** (audit 243; −2). Largest module `dharma_swarm/thinkodynamic_director.py` = **5255** lines (== audit baseline). Concentration + silent catches persist. |
| TIT-014 | 4 | **STILL_REPRODUCES** | `dharma_swarm/sealed_packet_apply.py:436` — `create_subprocess_shell` of an attacker-authored command string (`proof_command.txt`/`scoped_tests`/`build_meta`, `:291-305`) with only `cwd`+`timeout`, **no env scrub**, no net/fs/user/rlimit/seccomp isolation. Chamber sandbox self-documents "NOT a full jail" (`dharma_swarm/chamber/sandbox.py:15-19`); Python-level guards only. No membrane/seccomp landed (grep clean); still an open blocker (`ACTIVE_TRACK.yaml:1638-1642`). |
| TIT-015 | 3 | **STILL_REPRODUCES** | No `.github/workflows/*.yml` provisions bun or runs `terminal/` checks (43 workflows grepped; only an unrelated `@terminal-review` keyword). `active-track.yml:57-60` installs only pyyaml. Criterion `terminal_tui_test_suite_passes` (`ACTIVE_TRACK.yaml:1265-1274`) is non-blocking on an ACTIVE track. `terminal/bun.lock` (477 lines) + `terminal/package.json:11,15` (`test`, `typecheck`) exist but are unwired to CI. Host has bun 1.3.11; clean CI agents have none. |

### Baseline drift relevant to WP-00 capture

- **Active tracks: 9 → 11.** Spec baseline (spec:92) recorded 9; `make onboard`
  now renders 11 (`company-builder-parity`, `darshan-publication`,
  `dharmagraph-engine`, `helm-worldclass-terminal`, `hyperbolic-time-chamber`,
  `loop-closure`, `merge-master-mike-d4`, `onboard-one-door`,
  `orchestration-arena-v1`, `organism-rewire`, `sovereign-safety-tcb`). WP-00 must
  recapture this fresh (spec:61-78), not copy the spec's frozen 9.
- **DocOps count-managed metrics moved** since the spec baseline table (spec:82-94):
  current `make docops-integrity` reports `dharma_python_modules=1010`,
  `test_files=899`, `total_python_loc=362505`, `markdown_files=1434`,
  `markdown_total_lines=301951`. The spec's 995 / 884 / 358,267 / 1,388 / 290,297
  are stale. Again: WP-00 captures fresh, never copies.
- **Toolchain deltas on this host vs the spec's proposed clean-room pins
  (spec:275-284):** uv `0.8.17` (spec wants `0.11.2`); go `go1.24.7` (spec wants
  `1.26.3`; `tools/*/go.mod` require `go 1.26`); bun `1.3.11` (spec wants `1.1.38`;
  `terminal/package.json:7` pins `bun@1.1.38`). These are host facts, **not**
  authority to change the pins — the WP-0A owner validates and amends the toolchain
  table through a reviewed packet (spec:288).

### What this means for execution (once the gate clears)

1. **TIT-002 findings-drift is the load-bearing correction.** WP-0D's investigation
   protocol (spec:730-745) must re-bisect on current `main` before touching any
   production file; the audited offender no longer reproduces and the allowed-file
   list may be pointing at the wrong owner. Editing `build_engine.py` on the strength
   of the stale symptom would burn the packet (spec:728 "If another file owns the
   leak, stop and amend").
2. **TIT-006 is closeable but not closed** — WP-0F1 must still add the duplicate-key
   rejection guard (spec:857) so the resolved state is enforced, not incidental.
3. **TIT-009 is broader than the registry row** — WP-0E must also decouple the
   *structural* contract (`check_nats_substrate_contract.py`) from live freshness,
   not only the explicit `--max-age-hours` line in the Make target.
4. **The rest reproduce as written** — WP-0A/0B/0C1/0C1R/0C2/0F1/0F2/0G/0H/0S and
   the deferred phases (TIT-010/011/012/013/014) remain accurately scoped.

Nothing here authorizes implementation. It ensures WP-00's baseline is captured
fresh and no packet chases a stale symptom.
