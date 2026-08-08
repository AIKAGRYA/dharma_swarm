# Graph of Loops — Grounding Audit + Design (2026-07-29)

**Role:** `working_plan` — a bounded execution plan, per the role vocabulary
in `docs/AGENTS.md:31-43`. Owns no runtime state, grants no authority.
**Subordinates to:** `CYBERNETIC_LOOP_MAP.md` (loop-closure truth) and
`docs/governance/ACTIVE_TRACK.yaml` (portfolio authority). This document
replaces nothing; where it and either owner disagree, the owner wins and this
file is the stale one.
**Produced by:** read-only grounding audit session on branch
`claude/graph-of-loops-audit-design-eh3lz5` @ `ea190e2` (clean, parity with
`origin/main`; `make onboard` READY).
**Method:** every claim below carries a `file:line` citation or a runnable
command, per the citation-or-silence rule (`CLAUDE.md` §Behavioral Rules).
Negative claims ("X does not exist") carry the command that establishes them
**and name the scope they were checked against** — a negative verified in
this checkout is not a claim about every branch, and one such over-claim in
an earlier draft is corrected in §1 below. Claims about GitHub state come
from the GitHub API on 2026-07-29, are labeled as such, and are
point-in-time.
**Suggested owning track:** `loop-closure-2026-06` (owns
`CYBERNETIC_LOOP_MAP.md`, `reports/loop_closure/**`; serves
`substrate-nativeness`). The portfolio is at its WIP ceiling
(`docs/governance/ACTIVE_TRACK.yaml`: 10 active, `max_active: 10`), so this
work should land as next-items under that track, not as an eleventh track.

---

## 1. Grounded glossary

### Apex — GROUNDED as a role qualifier, not a component

There is no `Apex` class, module, or config key in this checkout, and `apex`
never appears as a Python identifier — every occurrence is docstring or
string prose. Verified at `ea190e2`, empty output:

```bash
git grep -nE '^\s*(def|class)\s+\w*[Aa]pex|^\s*[A-Za-z_]*[Aa]pex[A-Za-z_]*\s*=' -- '*.py'
```

It is a seat description:

- Dominant usage: "apex holon" = the Sarathi seat.
  `docs/sarathi_apex_build/03_HOLON_SYSTEM_CODE_MAP.md:15` — "Sarathi = apex
  occupant/wrapper of holon_system";
  `docs/sarathi_apex_build/05_SARATHI_APEX_MAP.md:9` — "apex continuity holon
  over the holon system: a chief-of-staff seat."
- Only code coupling: the reversibility gate,
  `dharma_swarm/operator_core/reversibility_gate.py:1-3,52` — the
  "load-bearing safety invariant for an always-on apex holon (Sarathi)";
  `NEVER_AUTO_PATTERNS` at `:54`.
- Routable alias strings only: `scripts/runtime/codex_composer_wake_loop.py:125-133`
  (`display_name="Sarathi Apex"`, `extra_addresses=("sarathi-apex",
  "apex-holon", "chief-of-staff")`).
- Dangling **on the trunk**:
  `docs/architecture/APEX_HOLON_LONG_RUNNING_GOAL_SPEC.md` is referenced
  (`reports/governance/worktree_readiness_2026-06-30/promotion_candidates.md:458`)
  but is absent from this checkout and from `origin/main`
  (`git cat-file -e origin/main:docs/architecture/APEX_HOLON_LONG_RUNNING_GOAL_SPEC.md`
  → exit 1). It is **not** absent from the repository: it was added in
  `260a1153` and `326b38dc` and still exists on 15 remote branches
  (`git log --all --oneline --diff-filter=A -- <path>`, then
  `git branch -r --contains 260a1153`). An earlier draft of this document
  asserted it existed "in no branch"; that assertion was false — it was a
  main-only check reported as a repository-wide negative, and it is corrected
  here. Anyone reviving the apex line should read those branch copies before
  writing a new spec.

### Holon system — GROUNDED (code); "holarchy" — UNGROUNDED (prose only)

Implemented, tested runtime primitives:

- `RunningHolon` + `load_holon()` — `dharma_swarm/holon_bridge.py:55-68,106-149`
  (identity from `~/.dharma/agents/<name>/identity.json`).
- `holon_wake_cycle()` / `run_holon_loop()` —
  `dharma_swarm/holon_runtime.py:53-120,222` (order: kill → budget →
  reversibility gate → runner → compass → persist).
- Satellite organs, each with its own test file: `holon_killswitch.py`,
  `holon_budget_guard.py` (`CostLimitExceeded`, `check_cost_cap` at `:15,25`),
  `holon_health.py`, `holon_compass.py`, `holon_persistence.py`.
- Singleton enforcement is code: `scripts/governance/sprawl_guard.py:52-75`.
- `dharma_swarm/holon_system/` is a thin re-export facade by declared intent
  (`dharma_swarm/holon_system/__init__.py:1-7`), enforced by
  `tests/test_holon_system_imports.py:69`.

Not implemented: **holon** composition. There is no `HolonType` enum
(`git grep -n HolonType -- '*.py'` → empty) and no parent/child field on any
holon object; the only holon composition object is a flat 4-name tuple,
`dharma_swarm/holon_system/sarathi/roster.py:7`. This is a claim about the
holon layer only. A governed recursive substrate **does** exist elsewhere and
must not be duplicated: `FractalRoom.parent_id`
(`dharma_swarm/fractal/fractal_room.py:111`), `RoomRegistry.children` /
`children_of` (`:506,:529`), and `RoomRegistry.spawn_child` (`:591`) with
depth and budget validation plus inherited controls, exposed publicly as
`RoomBridge.spawn_child` (`dharma_swarm/fractal/room_bridge.py:123`). The
configured hierarchy already nests `revenue-wedge` and `agentops` under
`core-ops` (`dharma_swarm/fractal/room_configs.py:67,140,179-181`). Any
holon-composition work should adopt or bridge that substrate rather than
re-implement it. The named
"apex holon contract" files (`~/.dharma/agents/sarathi/HOLARCHY_CONTRACT.md`,
`SUB_HOLON_ROSTER.yaml`, per `docs/sarathi_apex_build/05_SARATHI_APEX_MAP.md:45-52`)
do not exist in this checkout or the repo. "Holarchy" appears only in prose
(`docs/ops/OZ_INTEGRATION.md:8,37`; `foundations/PILLAR_03_JANTSCH.md:27`) and
in dead-branch metadata. Anyone claiming a holarchy exists is citing intent.

### A2A layer — GROUNDED (code); DORMANT (runtime)

- Package: `dharma_swarm/a2a/` (21 files). Canonical transport: NATS
  JetStream over TLS/WSS (`dharma_swarm/a2a/nats_transport.py:63-74`), plus an
  HTTP gateway (`a2a/node_gateway.py:49-67`) and file/git seats
  (`inter_agent/`, `roaming_mailbox/`).
- Routing truth: `docs/ops/FLEET_FIELD_REGISTRY.yaml` (updated 2026-07-14).
  Stream drift is recorded there: code defaults to `DS_TASKS`/`DS_DLQ`
  (`nats_transport.py:66-69`) but "no DS_* stream runs live anywhere; all
  live traffic is on DHARMA_A2A" (`FLEET_FIELD_REGISTRY.yaml:38-40`).
- Liveness verdict, from the repo's own gates run 2026-07-29:
  `python3 scripts/governance/check_nats_live_production_evidence.py
  --max-age-hours 24` → FAILED, evidence 27 days stale; the evidence artifact
  (`reports/governance/nats_live_production_matrix/latest.json:1-13`) was a
  loopback run (`broker_url: nats://127.0.0.1:4222`) on an operator-Mac
  worktree. `ACTIVE_SURFACE_MANIFEST.yaml:439` — `nats_runtime_status:
  declared_not_started`. The only live node is the `hermes` bridge on the
  Agni VPS, publish-ACL-crippled (`FLEET_FIELD_REGISTRY.yaml:84-101`, FFR-D1
  `RATIFIED_NOT_APPLIED` at `:47-68`).

### Sarathi — GROUNDED; exists and is deliberately inert

Not to be created — already on disk:

- Code: `dharma_swarm/holon_system/sarathi/` — `gateway.py`, `pulse.py`,
  `roster.py`, `brief.py` (`build_operator_brief()` at `:8`),
  `scoreboard.py`. ~100 LOC, read-only projections, zero I/O writes.
  Every liveness flag is hardcoded `False`
  (`gateway.py:20-21`, `pulse.py:23-24`), asserted honest by
  `tests/test_holon_system_imports.py:77`.
- Wake profile registered: `scripts/runtime/codex_composer_wake_loop.py:125-133`.
- Safety envelope: the reversibility gate call inside `holon_wake_cycle`
  (`dharma_swarm/holon_runtime.py:99-118`).
- Status ladder: `docs/sarathi_apex_build/06_PROOF_GATES.md:12-21` — gates
  1–9 DONE, gate 10 (unattended proof) PENDING. No `wake_loop_active=true`
  claim is permitted until gate 10 closes.
- Current-truth owner for this whole estate:
  `docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md` (`:31` demotes
  `docs/sarathi_apex_build/` to historical narrative).

---

## 2. Corrected loop-graph architecture

### 2.1 What already exists (reuse, do not rebuild)

The repo already IS a declared graph of loops with honest closure grading:

- **Loop inventory:** `CYBERNETIC_LOOP_MAP.md:82-94` — 13 loops;
  `CLOSED_LIVE: 0/13`, HARNESS_PROVEN 11/13, loops 12–13 (self-improvement)
  BLOCKED behind the One Wire receipt quorum (N=3/5, M=1/3).
- **Doctrine:** `docs/vision_maps/NORTH_STAR.md:31-53` — "not one loop; many
  heterogeneous cybernetic loops … with meta-loops that evolve the loops
  themselves." The Steinberger/Perez "graphs of loops" frame is arriving
  home, not being imported.
- **Always-on substrate with cloud-side proof:** GitHub Actions crons — 14
  scheduled workflows (`.github/workflows/`: `automerge.yml` 45 \* \* \* \*,
  `merge-master-mike-backlog.yml` 17 \* \* \* \*, `pr-ci-health.yml` hourly,
  `nightly-tests.yml`, `langgraph-oracle.yml` daily, weekly
  `quality-ratchet.yml`, `docops.yml`, `active-track.yml`, `pramana-probe.yml`,
  `semgrep.yml`, `codeql.yml`, `branch-janitor.yml`, `stale-pr.yml`,
  `pr-dedupe.yml`). Everything else (28-job `cron_jobs.json` scheduler, 6
  launchd plists hardcoding `/Users/dhyana/`, 8+ daemons writing receipts to
  `~/.dharma/`) is Mac-host-bound and unverifiable from a clean checkout.
- **Watcher/counter-metric machinery:** `scripts/runtime/ci_truth.py` +
  `docs/governance/CI_TRUTH_CONTRACT.json` (CI-actually-executed);
  `quality-ratchet.yml` + ratchet baselines (counts only ratchet down);
  `scripts/governance/cybernetics_codex_audit.py` (read-only receipts
  auditor); `arena_truth_report.py --check` (re-derives, fails on drift);
  `scripts/governance/check_claim_evidence_binding.py`;
  `ci-parity.yml` (manifest vs live branch protection, fail-closed).
- **Arbitration/merge doctrine:** Merge Master Mike,
  `docs/governance/MMM_CHARTER.md:49,109-110` — the only agent with
  conditional merge authority; deterministic gate in
  `scripts/runtime/pr_merge_control.py` (`MERGE_CANDIDATE` guard at `:1665`,
  risk policy `HOT_PATH_PATTERNS` at `:94-109`).

### 2.2 The corrected topology

Six nodes, five of which are mostly reuse. Names below are seats/lanes, not
new packages.

```
                    OPERATOR (root judgment, outside the graph)
                       ▲ brief (read)      │ voice-note issue (write)
                       │                   ▼
   [N1 BRIEF LOOP] ◄── [N4 SARATHI SEAT: decompose + arbitrate, NO merge rights]
        ▲                        │ tasks (git-stored, dependency-aware)
        │ receipts               ▼
   [N5 AUDIT LOOP] ◄── [N2 HARDENING LANE]   [N3 PR-QUEUE LANE]
        (read-only,          │ draft PRs only      │ rebase/stage only
         counter-metrics)    ▼                     ▼
                        ────────── main (door: operator merge act) ──────────
                    frozen refs: tests.yml matrix · gitleaks · ci_truth ·
                    ratchet baselines · ci_parity_manifest (anchors, §3)
```

- **N1 Brief loop** (build): daily scheduled workflow that composes the
  operator brief from existing projections — `make onboard` output,
  `check_track_status.py`, Mike's queue status, N5 audit deltas — and posts
  it to a pinned GitHub issue. Reuses `dharma_swarm/operator_brief/`
  content logic where useful (`insight_brief.py:78 run_once`), but delivery
  is the new part (§4). The in-repo `operator_brief` cron job is disabled
  (`cron_jobs.json:224-234`, `"enabled": false`) and its `deliver:` field is
  a dead contract — documented at `dharma_swarm/cron_scheduler.py:9,238` but
  read by nothing that routes.
- **N2 Hardening lane** (build, small): scheduled workflow (2–3×/week, not
  hourly) that reads the task graph, picks one ready hardening task
  (failing nightly test, ratchet regression, quarantined test), runs a
  fresh-context agent with iteration/budget caps, and opens a **draft** PR
  labeled `mike-watch`. Exit condition: focused tests green or cap hit.
  Sensors already exist (`nightly-tests.yml`, `quality-ratchet.yml`); the
  acting loop is new.
- **N3 PR-queue lane** (mostly exists): `pr-ci-health.yml` already runs
  hourly fail-closed rebase triage (`scripts/governance/pr_ci_safe_rebase.py`),
  and `merge-master-mike-backlog.yml` runs the backlog fanout. Extend with
  conflict-resolution proposals as draft commits on the PR branch; do not
  build a second queue manager.
- **N4 Sarathi seat** (build, thin): the apex holon as *decomposer and
  arbiter*, exactly one input door (the operator's voice-note issue, §4) and
  two outputs: tasks into the graph, and the arbitration section of the
  brief. Runs as a workflow job wrapped by the existing reversibility gate
  pattern (`operator_core/reversibility_gate.py`) and budget guard
  (`holon_budget_guard.py:25 check_cost_cap`). **No merge rights**: enforced
  mechanically because its PRs are drafts (`automerge.yml:219-223` skips
  drafts; `pr_merge_control.py:333,1278` blocks drafts) and it holds no
  PAT. This walks Sarathi's own proof-gate ladder
  (`docs/sarathi_apex_build/06_PROOF_GATES.md` gate 10) instead of
  bypassing it.
- **N5 Audit loop** (mostly exists): weekly + post-lane-run workflow, a
  different model family than the lanes, read-only, that runs the existing
  auditors (`cybernetics_codex_audit.py --json`, `ci_truth.py` check,
  ratchet baseline freshness, `check_claim_evidence_binding.py`) plus two
  thin new counter-metric checks: coverage-rise-without-test-deletion
  (diff `tests/` deletions against coverage delta) and diff-sanity on lane
  PRs. Output: a receipt under `reports/loop_closure/` and a section in N1's
  brief. It watches N2/N3; N2/N3 never modify it (§3 frozen list).
- **Task graph medium** (join, don't build): dependency-aware state in
  `dharma_swarm/task_board.py` (first-class `task_dependencies` table at
  `:50-54`, ready-set query `_READY_QUERY` at `:56-69`, FSM at `:26-33`) is
  SQLite and host-local; the git-shareable file lane is
  `roaming_mailbox/` (`dharma_swarm/roaming_mailbox.py:1-11` — one JSON file
  per task, synced through git) and the claim/receipt contract in
  `dharma_swarm/operator_core/a2a_task_lifecycle.py:5-9`. The design uses
  git-stored task files (mailbox pattern, WP-\* id grammar per
  `docs/governance/BUILD_SESSION_ENTRYPOINT.md:63-65`) as the shared medium
  for cloud lanes, with a `depends_on: []` field added to the task JSON and
  ready-set computed by a ~50-line helper reusing `task_board.py` semantics.
  Anti-slop Rule 2 (`docs/governance/ANTI_SLOP_RULES.md:16` — no new
  Store/Ledger/Registry substrate) forbids a new store class; this is a
  schema field + reader, not a substrate.

### 2.3 Hypothesis phases — verdicts

| Phase (chat-side) | Verdict | Grounds |
|---|---|---|
| 0. Merge #810 first | **DROP** | Already merged 2026-07-06 by the operator (GitHub API, `merged_by: AmitabhainArunachala`). Its "one-door" is the evolution live-apply door (`tests/test_forge_v2_promotion_door.py:1`; `docs/governance/ACTIVE_TRACK.yaml:1437`), not PR merges. The real Phase 0 is §6 item 2. |
| 1. Shared dependency-aware task graph | **MODIFY** | Substrate exists split in half: DAG semantics in `task_board.py:50-69`, git-shareable files in `roaming_mailbox/`. Join them (schema field + reader); build nothing Beads-shaped from scratch. `docs/architecture/WIRING_AND_LOOPS.md:64` explicitly declares "No Beads" as an anti-dependency. |
| 2. Two Ralph lanes on timers | **MODIFY** | Keep the two-lane discipline (bitter-lesson counterweight), but lane (b) mostly exists (`pr-ci-health.yml`, `merge-master-mike-backlog.yml`) — extend it. Lane (a) is new but its sensors exist. Run on GitHub Actions schedules — the only loop substrate with cloud-side proof — not new daemons. |
| 3. Paired audit loop | **MODIFY (mostly reuse)** | The counter-metric battery largely exists: `ci_truth.py`, quality-ratchet, `cybernetics_codex_audit.py`, `arena_truth_report.py --check`. New: two thin checks + one aggregating workflow. "Different model" requirement stands. |
| 4. Sarathi as apex | **MODIFY heavily** | Sarathi exists and is deliberately inert (§1). Do not re-create; wire the thin seat (N4) and walk proof gate 10. "No merge rights" is enforceable today via draft-PR mechanics + no PAT, not by trust. |
| 5. Evolution loop with SWE-bench fitness | **KEEP as later-only, corrected** | `forge_v1` is a *measurement* harness (swarm-vs-best-of-N over official SWE-bench Verified, `dharma_swarm/forge_v1/swebench_real.py:64-71`), manual-only (zero make/CI/cron entries), with no in-repo run receipts and documented drift (runbook flags ≠ `run_real.py:212-219`; `FORGE_CANONICAL_INDEX.md` missing). Self-improvement loops 12–13 are BLOCKED behind the One Wire quorum (`CYBERNETIC_LOOP_MAP.md:93-94`) — that gate stands; do not route around it. |

---

## 3. Frozen nodes and anchors

### 3.1 Honest baseline: nothing is unwritable today

No path-level write block exists in this repo. The kernel hash guard
(`scripts/uplift_guards/kernel_guard.py:47-123`) is real code, but
`.git/hooks/` is empty in a fresh checkout (nothing installs pre-commit) and
`--no-verify` defeats it (`scripts/uplift_guards/run_pre_commit.py:108-111`).
`.claude/settings.json:1-12` registers only a SessionStart hook. The only
fail-closed freeze is `scripts/governance/ci_parity_manifest.json`, which
`ci-parity.yml` diffs against live branch protection. Per-task path scoping
exists via AgentOps work packets (`allowed_files`/`forbidden_files`,
enforced in `scripts/governance/run_agent_work_packet.py:1010,1228-1256`).

### 3.2 Frozen-node list (what lane agents may never modify)

Enforcement is packets + CI required contexts + review routing — the
mechanisms that exist — not imaginary filesystem permissions. Every lane
work packet lists these under `forbidden_files`; N5 audits lane diffs
against this list as a counter-metric.

1. `dharma_swarm/dharma_kernel.py`, `dharma_swarm/telos_gates.py` — already
   CRITICAL-risk in Mike's gate (`pr_merge_control.py:645-649`) and
   CODEOWNERS-routed (`.github/CODEOWNERS:11-33`).
2. `scripts/governance/ci_parity_manifest.json`,
   `docs/governance/CI_TRUTH_CONTRACT.json`, `scripts/runtime/ci_truth.py`.
3. The auditor set N5 runs: `scripts/governance/cybernetics_codex_audit.py`,
   `quality-ratchet` baselines (`ratchet_baselines.json`),
   `check_claim_evidence_binding.py`, `arena_truth_report.py`.
4. The merge doctrine surface: `scripts/runtime/pr_merge_control.py`,
   `.github/workflows/automerge.yml`, `codex-mention-router.yml`,
   `docs/governance/MMM_CHARTER.md`.
5. The new loop-control surface itself: the lane workflow files, the
   kill-switch file (§5), and the lane prompt/packet files.
6. `docs/governance/ACTIVE_TRACK.yaml` (operator-owned intent).

### 3.3 Anchor list (ground truths the graph settles against)

1. **Tests that actually executed:** required contexts `pytest (3.11)` /
   `pytest (3.12)` + gitleaks + DocOps + Coherence Delta + onboarding parity
   (`scripts/governance/ci_parity_manifest.json:6-42`), with
   `ci-parity.yml` asserting no required job is a false-green sensor.
2. **CI-actually-executed:** `scripts/runtime/ci_truth.py` against
   `CI_TRUTH_CONTRACT.json`.
3. **Ratcheted counts:** quality-ratchet baselines — counts only go down
   (`.github/workflows/quality-ratchet.yml`).
4. **Deterministic replay:** arena frozen fixture pool,
   `scripts/governance/check_arena_replay.py:1-11` (byte-stable scorecard
   hash across two runs).
5. **The operator merge act:** a human-initiated merge on a lane PR
   (GitHub `merged_by`), reachable only after the draft is flipped ready by
   the operator. This is the human root judgment from outside the graph.
6. **External receipts for external claims:** per
   `docs/governance/SWARM_GENOME.md:98-111` (forbidden overclaims) — cash
   landed, humans served, A2A liveness all require owner receipts, never
   loop-internal prose.
7. **SWE-bench Docker-graded resolution** (later, loop 12/13 era):
   `dharma_swarm/forge_v1/swebench_real.py` over the official harness — the
   fitness anchor, gated by the One Wire quorum.

---

## 4. Walking-mode ops spec (~10 min/day, phone only)

**Constraint from disk:** no brief can reach a phone today. The
ontology-native brief is cron-disabled and flag-off (`cron_jobs.json:231`;
`DHARMA_OPERATOR_BRIEF_ENABLED` unset in any env file); there is zero
email/SMS/push code in the tree; the Telegram adapter
(`dharma_swarm/gateway/telegram.py`) is never started by anything
(`swarm.py:501-506` constructs but never calls `gateway.start()`) and the
`deliver:` routing field is read by nothing; the dashboard is 0% PWA and
loopback-locked (`docs/plans/MOBILE_OPERATOR_PWA_AUDIT_SPEC_2026-07-25.md:11-15`).
The one channel that reaches the operator's phone with zero new transport
code is **GitHub itself** (mobile app notifications, issues, PR
review/merge). The spec therefore runs entirely on GitHub surfaces:

1. **Morning brief (read, ~3 min).** N1 workflow posts the daily brief as a
   comment on a pinned issue ("Walking Ops — Daily Brief") at a fixed UTC
   time. Sections, hard-capped at ~300 words: (a) merge window — lane PRs
   ready for the door, one line each with risk grade from Mike's gate;
   (b) audit verdicts — N5 counter-metric deltas, RED items first;
   (c) arbitration — conflicts N4 wants a ruling on, as yes/no questions;
   (d) kill-switch state. GitHub mobile push notifies on the pinned issue.
2. **One voice note (write, ~2 min).** The operator replies to the same
   issue using phone dictation. That comment is the **sole input door**.
   N4's next run reads only operator-authored comments on that issue
   (author check against the operator login — comments from any other
   account are ignored as untrusted), decomposes them into task files with
   `depends_on` edges, and answers arbitration questions from the ruling.
   This reuses the mention-router pattern
   (`.github/workflows/codex-mention-router.yml:33` already restricts
   comment triggers by author association).
3. **Merge window (~5 min).** In the GitHub mobile app: open the PR list
   filtered `label:walk-ready is:draft`, skim Mike's gate status comment
   (already posted by the existing lane, `pr_merge_control.py:1590-1608`),
   then for each accepted PR: mark ready-for-review and merge. Rejecting =
   one dictated comment; N4 turns it into a follow-up task. The draft flip
   plus merge tap is the operator hand-merge act — below that, drafts are
   mechanically unmergeable (`automerge.yml:219-223`;
   `pr_merge_control.py:1278`).
4. **Nothing else.** No terminal, no SSH, no dashboard. If GitHub is
   unreachable, the graph idles safely: lanes only ever produce drafts, and
   the kill-switch (§5) fails closed on missing signal only in the sense
   that no operator act ⇒ nothing merges.

Operator decision — **SETTLED 2026-07-29; this section asks nothing of the
operator.** The ruling is DOOR = AUTO_WITH_DECORRELATED_REVIEW, recorded in
`docs/ops/OPERATOR_RULING_2026-07-29_AUTO_WITH_DECORRELATED_REVIEW.md:22-35`:
lane PRs, once flipped ready, may be executed by Mike's arm (label
`automerge`) for eligible Tier 0-1 changes, while Tier 2 stays operator
hand-merge. The tradeoff accepted with that ruling is reliance on
`MERGEMASTERMIKE_PAT` (`automerge.yml:85`). The reasoning is retained here
because it explains a policy now enforced elsewhere — the enforcement, not
this paragraph, is authoritative.

---

## 5. Build sequence, caps, kill-switch

Sequencing rule: each step is one small PR through the normal door; no step
depends on an unmerged sibling. New workflow files touch `.github/` =
hot-path (`pr_merge_control.py:94-109`), so every step binds a work packet
(`make agent-build-preflight PACKET=<path>`,
`docs/governance/BUILD_SESSION_ENTRYPOINT.md:67-74`).

| # | Step | Builds on | Rough effort |
|---|---|---|---|
| 0 | Operator ratification (mobile, one comment): adopt this doc's door rule (drafts + `mike-watch` for all lane PRs; `walk-ready` label vocabulary; merge-window choice from §4) | — | 10 min operator |
| 1 | Kill-switch + control issue: `docs/ops/loop_control/KILLSWITCH` file (present ⇒ all lane workflows exit at step 1) + pinned brief issue. Workflows check the file at job start; the operator can create/delete it from the GitHub mobile web editor | — | 0.5 day |
| 2 | N1 brief workflow: compose from `make onboard` + `check_track_status.py` + Mike queue + (later) N5; post to pinned issue | 1 | 1 day |
| 3 | Task medium join: `depends_on` field + ready-set reader over `roaming_mailbox/tasks/` (reusing `task_board.py` ready semantics); WP-\* ids | — | 1 day |
| 4 | N2 hardening lane v1: scheduled workflow, one task per run, fresh context, caps, draft PR + `mike-watch` + `walk-ready` | 1,3 | 1.5 days |
| 5 | N5 audit loop v1: aggregate existing auditors + the two new counter-metric checks; receipt to `reports/loop_closure/`; brief section | 2 | 1 day |
| 6 | N4 Sarathi seat v1: issue-comment reader → task decomposition → arbitration answers; wrapped in reversibility-gate + budget-guard calls; walks proof gate 10 honestly (`06_PROOF_GATES.md`) | 2,3 | 1.5 days |
| 7 | N3 extension: conflict-resolution draft commits on queued PRs | existing `pr-ci-health.yml` | 1 day |
| 8 | Later only: loop 12/13 revival with `forge_v1` as fitness anchor, behind the One Wire quorum — after fixing the runbook/code drift (`run_real.py:212-219` vs `docs/RUNPOD_SWEBENCH_RUNBOOK.md:30`) | all | not scheduled |

**Run-cost caps per lane (hard, checked in-loop):**

- Iteration cap: ≤ 1 task per lane run; ≤ 25 agent turns per task
  (Ralph-style fresh context each run — no session carryover).
- Budget cap: per-run USD ceiling via the existing pattern
  (`dharma_swarm/holon_budget_guard.py:15-25 CostLimitExceeded /
  check_cost_cap`); lane exits cleanly at cap with a receipt, never retries
  past it. Suggested initial caps: N2 $5/run, N4 $2/run, N5 $3/run,
  N1 $1/run (operator-tunable in one config file that is itself frozen-list).
- Schedule cap: N2 at 3 runs/week initially; nothing hourly except the
  already-existing N3 surfaces.
- PR cap: a lane never has more than 2 open draft PRs; at the cap it stops
  producing and says so in the brief (no silent queue growth — mirrors
  `bot-pr-limit.yml` which already exists for bot PR ceilings).

**Kill-switch mechanism (corrected 2026-08-02 to match what PR-B actually
shipped — the original sketch below was wrong in a way that could have left
automation running):** one tracked file, `docs/ops/loop_control/KILLSWITCH`,
**on the dedicated `loop-control` branch, NOT on `main`.** Every guarded
workflow's first step queries it by ref:

```
repos/<owner>/<repo>/contents/docs/ops/loop_control/KILLSWITCH?ref=loop-control
```

(`automerge.yml:97`, `codex-mention-router.yml:58`,
`merge-master-mike-backlog.yml:86`, `loop-watcher.yml:51,134`). Present ⇒ the
guard exits non-zero, so a halted lane shows **red with "HALTED BY
KILLSWITCH"** rather than silently green; absent (404 on file or branch) ⇒
proceed; any other API error ⇒ fail closed. Contract:
`docs/ops/loop_control/README.md:1-32`.

**Creating this file on `main` halts nothing.** The supported operator path
is the phone-dispatchable `loop-emergency-stop` workflow to engage and
`loop-resume` (confirmation string `resume`) to release
(`docs/ops/loop_control/README.md:24-32`). The original design sketched a
single file on `main` guarded by `test ! -f ... || exit 0`; that was
superseded during PR-B because `main` is branch-protected and an emergency
write cannot wait for a PR. The superseded form is recorded here only so the
change is legible — do not follow it. This still adapts the existing local
convention (`agent_loop.sh:16` loops until `~/.dharma/.STOP`;
`holon_killswitch.py`) to the cloud substrate, and the surface stays Tier 2:
operator hand-merge, no automation may modify it.

---

## 6. Collapses corrected (chat-side memory vs disk)

1. **"Merge #810 — the anchor precedes the graph."** #810 merged
   2026-07-06 (GitHub API; hand-merged by the operator). In-repo it is
   nearly recordless — one prose mention
   (`docs/research/web5_planetary_commons_2026-07-11/refute_capacity-reality.md:15`).
   Its "one-door law" is the **evolution live-apply door**
   (`verify_promotion` as sole arbiter of `shadow=False`), not PR merges.
2. **"One-door law: agents never merge to main; operator hand-merge is
   inviolate."** No such law exists on disk, and current reality contradicts
   it: `MMM_CHARTER.md:49,109-110` charters Mike as the *only* agent with
   conditional merge authority, and an unattended chain merges green bot PRs
   with zero human touchpoints — hourly cron (`automerge.yml:45-46`) →
   auto-`bot-pr` enrollment (`:29-36`) → router dispatch with
   `merge_when_clean=true` (`:305-306` equivalent step) →
   `codex-mention-router.yml:226-240` synthesizes the "operator confirmation
   token" (`merge-pr-<N>`, derived from the PR number,
   `pr_merge_control.py:1801`) → `gh pr merge --squash` (`:1615-1627,1669`).
   Recent main history shows bot-authored squash merges (#1150, #1148,
   #1147). Separately, the retired "One-Door" *hardening campaign* holds no
   authority (`BUILD_SESSION_ENTRYPOINT.md:103-109`). This design does not
   route around the door for **its** lanes (drafts are mechanically
   unmergeable), but restating the global law as fact would be false: making
   operator-hand-merge universal is an operator doctrine change, not a
   status quo to cite.
3. **"Sarathi: to be created."** It exists — code, wake profile, safety
   gate, tests, 11 docs (§1) — and is deliberately inert with hardcoded
   `alive_claim: False` and proof gate 10 pending. The work is wiring and
   gate-walking, not creation.
4. **"Apex holon / holarchy."** "Apex" is a seat description with one code
   coupling (the reversibility gate); holon *composition* is a flat 4-name
   tuple (`roster.py:7`); the holarchy contract files are named but absent.
   Any design invoking "the holarchy" invokes prose.
5. **A2A as a live nervous system.** DORMANT. One ACL-crippled bridge is
   live; both liveness gates fail on 27-day-stale loopback evidence; stream
   topology drift (`DS_*` in code vs `DHARMA_A2A` live) is on record. The
   walking-mode design therefore rides GitHub, not NATS.
6. **"SWE-bench self-improvement protocol."** It is a comparative
   measurement harness (`forge_v1`), manual-only, with no in-repo run
   receipts, a runbook whose flags don't match the CLI, and a missing
   canonical index. Self-improvement (loops 12/13) is separately and
   deliberately BLOCKED behind the One Wire quorum.
7. **"Is anything Beads-like present?" — assumed no.** Half yes:
   `task_board.py` has a first-class dependency DAG, ready-set query, and
   status FSM; the file-native shareable half exists separately
   (`roaming_mailbox/`, `a2a_task_lifecycle.py`). The gap is a join, not a
   build — and `WIRING_AND_LOOPS.md:64` explicitly forbids adopting Beads.
8. **Operator brief assumed deliverable.** The brief pipeline exists but is
   switched off (cron `enabled: false` + env flag unset), its delivery
   contract is dead code, and no phone-reachable channel exists anywhere in
   the tree except GitHub itself.
9. **"Gate/audit prompts in an agent-unwritable directory."** No unwritable
   directory mechanism exists; pre-commit guards aren't installed in fresh
   checkouts. The real freeze mechanisms are work-packet `forbidden_files`,
   CI required contexts, and `ci_parity_manifest.json` — the design's frozen
   list uses those.
10. **Loop count.** The graph is not being founded — 13 loops are already
    mapped with an honest 0/13 CLOSED_LIVE grade, and 14 GitHub Actions
    crons already run. The contribution of this design is topology
    (watchers, arbitration, one input door, anchors) and closure, not loop
    invention.

---

*End. This document proposes; the operator disposes. Nothing in it grants
authority, and nothing in it may be cited as runtime truth.*
