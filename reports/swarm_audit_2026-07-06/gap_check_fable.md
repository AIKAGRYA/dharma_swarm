# Gap-check of the whole-repo swarm audit — independent second opinion

*Companion to `synthesis.md` (PR #814). Produced by a separate session that did NOT run the
original audit, under an adversarial mandate: verify, don't agree. Every claim below was
re-checked by running commands against a clean read-only worktree of `origin/main`
@ `665c90c35` (2026-07-06); nothing is repeated from the prior report on trust.*

*Method: 15 independent checkers (7 deprioritized leads, 2 verdict re-reviews, 2 spine-objective
checks, 2 headline-claim spot-checks, 2 fresh-eyes gap hunts), with every escalation or dispute
adversarially re-verified by 2 refuters with distinct lenses (evidence-quality, severity).
Checkers ran across two model families (Fable 5 and Opus 4.8 — the session's Fable subagent
credits ran out mid-run, and the re-run on Opus decorrelated the verification as a side effect).*

---

## 0. Bottom line

**The audit holds up.** All eight of its headline CONFIRMED claims reproduce at HEAD; its single
REJECTED verdict (MemoryKernel) was correctly rejected; four of its five WEAKENED verdicts were
fair. All seven deprioritized leads are confirmed still-minor — none was under-rated as a defect,
though several produced useful corrections.

What the gap-check adds beyond the audit:

1. **One finding the audit under-played should be first-class**: the ThinkodynamicDirector's
   ungated dispatch tail (§3.2) — a 5,255-line, track-unowned module that in standalone mode
   dispatches raw `codex`/`claude -p` subprocesses with zero telos-gate/spine mediation. The
   lane is currently **dormant** (no logs since ~Apr 1, no heartbeat file, no live process),
   which caps runtime urgency — but it is one command away from live and invisible to the
   repo's own bypass instrument.
2. **The audit could not see the room it was standing in** (§5.1): the live environment
   contradicts repo governance — 60 worktrees against a self-declared budget of 8 whose
   "enforced" label has no enforcer, and **no checkout on this machine sits on current main**;
   the operator's primary checkout orients sessions on a portfolio where 10 of 11 rendered
   tracks are closed or absent on main.
3. **Both non-substrate spine objectives are unserved, and always have been** (§4): no track has
   ever served `revenue-external-humans-served` or `research-depth` in the entire life of the
   v2 portfolio (since 2026-06-09). The system discloses this honestly in rendered markers; what
   is missing is a recorded decision, not honesty.
4. Three small new defect-class findings: a **fail-open telos gate** (§5.2), a **class-limited
   bypass instrument** whose "DRAINED TO ZERO" only covers A2A submits (§5.2), and two **low
   security findings** from sampling the audit's missing security dimension (§5.3).

One trivial fix was applied in this PR per the mandate (§6). Everything else is a
recommendation, not a diff.

---

## 1. Verdict table

| # | Check | Verdict | Severity | Adversarial verification |
|---|-------|---------|----------|--------------------------|
| L1 | Test-suite hygiene | CONFIRMED still-minor (one audit claim disputed) | low | not needed |
| L2 | Provider routing churn + streaming | CONFIRMED still-minor (crash premise disputed) | low | not needed |
| L3 | A2A card security schemes | CONFIRMED still-minor, flip condition defined | low | not needed |
| L4 | catalytic_graph broken import | CONFIRMED trivial — **fixed in this PR** | low | not needed |
| L5 | Guardian dedup storms | CONFIRMED closed, zero recurrence | trivial | not needed |
| L6 | Review-mark authority | CONFIRMED converged | low | not needed |
| L7 | Minor doc-drift bundle | CONFIRMED still-minor (all 4 sub-items) | low | not needed |
| R1 | C5 MemoryKernel REJECTED verdict | CONFIRMED — rejection was correct | low | not needed |
| R2 | C4/C1/C8 WEAKENED verdicts | 4 of 5 fair; 1 should be **promoted** | high (gov.) | 3 of 4 refuters upheld; 1 refuted to medium on dormancy evidence |
| S1 | Revenue spine coverage | CONFIRMED zero coverage, since portfolio birth | medium | not needed |
| S2 | Research-depth spine coverage | CONFIRMED zero coverage; partially by-design, undisclosed | medium | not needed |
| V1 | Headline claims: mismatch map, CI gates, DEVIN.md | ALL CONFIRMED at HEAD | medium | not needed |
| V2 | Headline claims: skill pipeline, cost, drift, resurrection | ALL CONFIRMED (one summary line imprecise) | high | not needed |
| G1 | Operational-reality gap hunt | ESCALATE (facts unanimous; severity contested) | medium–high | contested: sprawl already receipted on main; residual real |
| G2 | Security/supply-chain sample | CONFIRMED minor; posture better than feared | medium (2 low findings) | not needed |

---

## 2. The seven deprioritized leads — explicit resolutions

### 2.1 Test-suite hygiene — STILL MINOR, with one audit claim DISPUTED

- The 7 organism/swarm xfails (6 + 1) do pin the superseded instant-HOLD policy, **but mask no
  live regression**: the replacement consecutive-hold policy (commit `8a4d96262`,
  `TELOS_DRIFT_THRESHOLD=0.15`, `CONSECUTIVE_HOLDS_BEFORE_EMERGENCY=3`) is live at
  `dharma_swarm/organism.py:1086-1290` with active non-xfail coverage in
  `tests/test_samvara.py:74-95` and `tests/test_organism.py:84-97`.
- The 8 TUI xfails are real and the "pending dispatch refactor" never landed — **but the xfail
  reason text is false as a product claim**: `_dispatch_prompt` DOES reach the runner
  (`dharma_swarm/tui/app.py:1905`). The tests fail because they don't stub the
  credential/routing gate (`_can_route_to`/`_provider_ready`, `app.py:1835`,
  `shutil.which` fails in CI). It is a test-infra gap, not a broken operator path. The
  submit→runner assertion exists only inside xfail'd tests
  (`tests/tui/test_app_interactive_e2e.py:45-73`), so passing coverage on that path is
  genuinely zero — un-xfailing by stubbing the gate is the one worthwhile cleanup here.
- **DISPUTED**: the audit's "duplicate coverage" claim for
  `test_agent_runner_quality.py` vs `test_agent_runner_quality_track.py`. Zero overlapping
  test names; one covers scoring math (46 tests), the other prompt-building/retrieval
  (21 tests). Diverged, both valuable, not duplicates.
- The 57-second reactive assertion deletion (`b92c27316` @ 11:00:24 → `483d84bd` @ 11:01:21) is
  confirmed and the assertion is still absent, but spawn-count behavior retains adjacent
  coverage (`tests/test_swarm.py:476,508-538`). No defect masked.
- New sub-finding: the xfail reason strings cite the wrong commit (`e5f4e46` instead of
  `8a4d9626`) — misleading to future maintainers. Also note commit `7486f038b` ("Green CI —
  all 6,760 tests passing") achieved green partly via bulk xfail; worth operator awareness as
  a pattern.

### 2.2 Provider routing + streaming — STILL MINOR, and the crash premise is DISPUTED

- Routing is **settled**: since canonicalization `e1aacc0fc` (2026-07-03), zero ordering
  reversals across `model_defaults/providers/runtime_provider/model_pool/model_hierarchy/
  provider_policy`; the power-first default stands (`provider_policy.py:81,124`). (Historical
  correction: the audit undercounted the churn — `7131b993f` is a fourth, earlier reversal.)
- The three `stream()` `NotImplementedError`s exist (`providers_extended.py:104,166,227`) —
  **but no production code imports `providers_extended.py`** (only tests + a note in
  `api_key_audit.py:142` that already calls it "not wired"). The production door
  (`runtime_provider.py:577,586,671`) instantiates the identically-named *working* classes
  from `providers.py` / `moonshot_provider.py`. Every production `.stream()` caller flows
  through that door. **No live path can crash**; the audit's §3 lineage row implies a live
  landmine that is actually quarantined dead code.
- Real residuals the audit missed: (i) a **name-collision hazard** — three classes exist twice
  with same names and divergent behavior; one wrong import re-arms the crash; (ii)
  `supports_streaming` and the whole `ProviderCapabilities` surface is **write-only** — declared
  on ~20 providers, read by nothing (and `providers.py:479` declares `supports_streaming=False`
  on a class that implements a working `stream()`).
- Recommended: delete or quarantine the three orphaned classes (+ their tests), rather than
  building a capability pre-check for a path that cannot currently be reached.

### 2.3 A2A card security schemes — STILL MINOR, with a precise flip condition

- Confirmed: `a2a/agent_card.py` advertises OAuth2/HTTPAuth/MutualTLS/OpenIdConnect/JWS;
  runtime enforces only APIKey (`node_gateway._verify_api_key`). But it is a self-documented
  "Tier 2 TODO", the gateway binds `127.0.0.1` by default, `init_gateway()` has **no non-test
  startup caller** (endpoints 503), the cloud ingress is NATS-only with no public HTTP, and the
  external-bridge track exists only as a PROPOSED yaml that itself mandates ingress auth.
- **Flip condition (gate on this):** escalate to ≥medium the moment (1) `init_gateway()` gains a
  real startup caller AND the bind becomes non-loopback, OR (2) any public HTTP/webhook
  card-serving ingress ships. Until then: optionally strip unenforced schemes from
  `to_dict()` output so the on-wire card cannot over-promise.

### 2.4 catalytic_graph broken import — CONFIRMED TRIVIAL, FIXED HERE (§6)

- Confirmed in every detail: `terminal_commands/diagnostics.py:149-153` imported a module-level
  `seed_ecosystem` that has **never existed** (born as a `CatalyticGraph` method in
  `b442d0eb6`; broken import introduced in `405900e7e`, moved verbatim in `8a5a8cd52`);
  `ImportError` silently swallowed; grandfathered at `name_drift_allowlist.txt:18`. Degradation
  confined to `dgc invariants` printing degenerate values from an empty graph.
- The graph instance is in scope at the site; the method takes only `self`; the outer
  `except Exception` still bounds failures. Zero ambiguity → fixed (see §6).

### 2.5 Guardian dedup storms — CLOSED, ZERO RECURRENCE

- All three claimed mechanisms live on the issue-creation path in `guardian_crew.py`:
  circuit breaker (`_MAX_OPEN_DUPLICATES=1` via `_count_open_duplicates`), synthesized-`__init__`
  detection (`_has_synthesized_init`), and WARNING-downgrade defense-in-depth.
- Recurrence hunt: zero GUARDIAN-titled issues created after the 2026-06-09 fix; only 2
  unrelated commits touched the file since; regression tests survive at HEAD. One pre-fix issue
  (#343, 2026-05-24) remains open — a single distinct finding, not a storm; worth an operator
  glance to close or confirm.

### 2.6 Review-mark authority — CONVERGED

- Authority is defined in exactly one module (`scripts/consume_review_marks.py`), restricted to
  principal `"operator"`, content-bound via `atom_sha256`, regression-tested against forged
  agent marks and frontmatter self-review.
- The identity check is an asserted name string, not cryptography — any same-user process could
  forge a mark — but the surface gates **only** promotion of staging atoms into the wiki, not
  merges, CI, telos gates, or archive fitness. The residual weakness is the OS trust floor
  (all agents run as the operator's user), which no in-repo mechanism fixes.
- New sub-finding: `memory_kernel/writer_specs.py:560-577` claims the consumer script "is not
  present on current main" and references functions that don't exist — stale writer inventory
  on this surface.

### 2.7 Minor doc-drift bundle — ALL FOUR SUB-ITEMS MINOR

- (a) The `~L1543` citation is stale twice over: the WS4 hard-reject law is at
  `evolution.py:1616-1639` (the audit's own correction "~1558-1573" was itself imprecise —
  that range is the gate *call*, not the law), and `proposal_gate_probe.py:6` carries the same
  stale number. The probe self-corrects the contract, not the citation. Fix: cite the `# WS4:`
  comment/symbol names, not line numbers.
- (b) No `tests/test_model_defaults.py`, but real transitive coverage exists
  (`test_zhipu_provider`, `test_ollama_config`, `test_model_hierarchy`, `test_model_pool`);
  the unlocked residue is ~20 provider-string data literals, not logic. Not an escalation.
- (c) **18** distinct GitHub Actions secrets across 42 workflows (audit said ~15); no
  consolidated inventory exists. A `docs/ops/SECRETS.md` is warranted. Adjacent name-drift:
  `MIKE_PAT_MIGRATION_NOTE.md` documents a secret name (`MIKE_PAT`) that workflows no longer
  use (`MERGEMASTERMIKE_PAT`).
- (d) BUILD_SESSION_ENTRYPOINT §4 is as narrow as triaged; cosmetic.

---

## 3. Re-review of the audit's WEAKENED / REJECTED verdicts

### 3.1 C5 "memorykernel-shadow-only" REJECTED — the rejection was CORRECT

Fresh-eyes re-adjudication upholds the audit's verifier: MemoryKernel is live on the production
dispatch path. `build_orchestrator_memory_kernel` is real and called on real dispatch;
`ContextCompiler.compile_bundle` injects a Memory Kernel section **unconditionally**,
independent of the `memory_kernel_shadow` flag. The original finding conflated the flag-gated
parity canary with the never-gated default-context injection.

Two residuals the audit should carry forward:
- The **parity canary itself is dormant** (`context_compiler.py:352`, default False, no shipped
  config sets it) — the live injection ships without its automated parity guard.
- CLAUDE.md's "canonical front door" phrasing still overstates: the facade is read-only
  (injection/read front door, not write/promotion authority). One-line doc fix.
- Citation correction: the mechanism landed in PR #344 (`996c96a9c`), not PR #799 as the
  audit's verifier wrote (#799 appears to be later work on the same path).

### 3.2 C4 weakenings — four of five fair; ONE SHOULD BE PROMOTED, NOT WEAKENED

The verifier corrections on the ReAct-engines finding, the dual-TUI finding, the C1 count, and
the C8 Makefile numbers all reproduce exactly at HEAD (see verdict table; e.g. Makefile: 94 real
targets / 63 documented — refuting the original "~15", confirming the audit's correction).

**The exception is the ThinkodynamicDirector "fourth tail":** the audit's verifier found a
*bigger* bypass than the original finding (`execute_pending_tasks`/`spawn_agent`) — and the
synthesis then buried it in a §10 parenthetical with no roadmap item. Verified at HEAD:

- `thinkodynamic_director.py` (5,255 lines) contains **zero** references to
  `TelosGatekeeper`/`check_action`/`invoke_agent`/`EvidenceReceipt`/spine (whole-file grep).
- In standalone mode there is no swarm pool, so `_select_named_swarm_agent` returns `None`
  (`:3342-3344`) and **every task** falls through to `spawn_agent` (`:4397`) → raw
  `codex` subprocess (`:3846`), raw `claude -p` subprocess (`:3892` — which pops the
  `CLAUDECODE` env var to defeat the nested-session guard), or direct
  `create_runtime_provider().complete()` (`:1665`).
- The operator launcher `scripts/start_allout_tmux.sh` drives exactly this standalone mode by
  default (`DIRECTOR_MODE=direct`, `:12,:110`); `run_loop` calls `execute_pending_tasks` each
  cycle (`:5022`).
- No active track owns the file (`ACTIVE_TRACK.yaml` grep: zero matches), and
  `scripts/governance/spine_bypass_report.py:34-58` scans **only** `server.submit(` calls — its
  "DRAINED TO ZERO 2026-07-03" claim structurally cannot see subprocess-CLI or direct provider
  dispatch.

Adversarial verification (4 refuters, 2 model families): the **facts were unanimous**; severity
split 3:1. The dissenting refuter produced decisive machine-state evidence that the lane is
**dormant**: the director's log dir is empty (mtime Apr 1), no heartbeat file exists, no tmux
session or process matches, and nothing in `orchestrate_live.py`/`swarm.py`/`dgc_cli.py` calls
`execute_pending_tasks` — plus the raw-codex execution surface
(`--dangerously-bypass-approvals-and-sandbox`) is *sanctioned repo-wide policy* shared by gated
lanes (`codex_cli.py:12-15`, used by 8 modules including `providers.py:775`).

**Final adjudication: high-priority governance debt on a currently-dormant lane.** One command
(`bash scripts/start_allout_tmux.sh`) turns it into a live ungated dispatch surface. Recommended
first-class treatment: assign ownership in the portfolio; gate or explicitly register the
`spawn_agent` path; widen (or sibling) the bypass instrument to cover subprocess-CLI and direct
provider dispatch classes.

---

## 4. Spine-objective coverage — revenue and research-depth

**Confirmed: on main, 100% of active tracks serve `substrate-nativeness`; the other two spine
objectives have zero coverage — and have had zero coverage for the entire life of the v2
portfolio (since 2026-06-09, `dbbc4588c`).** The tracks the stale CLAUDE.md shows serving them
(`telos-ai-morning-refinery`, `cybernetics-codex-stewardship`) came from a divergent side branch
(`cc9c05f21` on `agent/magpie-seed`) and were never in main's ancestry.

- **Disclosed, not hidden:** rendered "**no active track**" markers appear on every onboarding
  surface, and organism-rewire's item 8 records "the next track must serve revenue." This is a
  sequencing choice on record — but one with no timeline, already deferred at least since
  2026-07-02.
- **Revenue:** no acted-external receipt exists anywhere on HEAD (`reports/telos_ai/`,
  `reports/revenue_wedge/`, `FIRST_EXTERNAL_ACTED_RECEIPT` — all absent). The One Wire quorum
  self-reports 3/5 confirmed, 1/3 domains, `eligible=false`. `VENTURE_CELL_PORTFOLIO.yaml`
  still cross-references a build track (`goodworks-dgm`) that no longer exists, and its
  `gate_evidence` path points at a file absent on HEAD — the venture layer has not been
  reconciled with the portfolio for ~5 weeks.
- **Research-depth:** the real measurement chain is unwired end-to-end — `rv.py`'s
  transformer-SVD `RVMeasurer` is imported by exactly one non-test module
  (`l4_rv_correlator.py`), which is itself imported by zero modules; production R_V vocabulary
  is carried by the `gaia_fitness`/`swarm_rv` proxies (as the audit found). In-repo doctrine
  (`WHERE_IT_SITS.md:13`, `NAVIGATION.md:522`) explicitly places real MI research in the
  external mech-interp lab, so track-lessness is **partially by design** — but NORTH_STAR §2
  still presents "measurable awareness" with no disclosure that production carries it via
  proxies while the real instrument sits outside, unwired.
- New sub-finding: `ACTIVE_TRACK.yaml`'s `spine_objectives` entries have `covered/covered_by`
  set to None **for all three objectives** — including substrate-nativeness with 5 tracks. Any
  tooling rendering "covered" status is not driven by this field.

**Strategic read (finding, not plan):** by the repo's own doctrine ("every track serves one of
three objectives"; "value must leave the house"), the portfolio is structurally monocultural.
Either open one track per unserved objective, or record an explicit dated decision that they are
deferred (and, for research-depth, that the external lab serves it). The absence of the decision
record, not the absence of the tracks, is the defect.

---

## 5. Wholly new gaps the original swarm missed

### 5.1 The live environment contradicts repo governance (repo-only audits cannot see this)

Facts (unanimous across both refuter runs):
- **60 git worktrees** exist against a self-declared budget of 8 (5 active tracks + 1 canonical
  + 2 scratch). CLAUDE.md:280 says "**enforced 2026-06-18**" — **no script or CI enforces it**
  (repo-wide grep; `agent_onboard.py:372` only prints the count). Sampled branches run
  ahead 10–90 / behind 8–476 of main.
- **No checkout on this machine is on current main.** The tree named `dharma_swarm_main` is
  detached 314 commits behind. The operator's primary checkout sits on `agent/magpie-seed`
  (46 ahead / 397 behind), dirty, with a committed CLAUDE.md rendering an 11-track portfolio of
  which **one** track is still active on main — every session orienting there reads dead
  doctrine (this gap-check's own seed prompt inherited two errors from it).
- No issue or track exists for disposing of PR #814's findings; 30 of 32 open issues are >14
  days old, and the issue backlog overlaps the audit's findings with no cross-references.
  (Open-PR hygiene, by contrast, is healthy: 12 open, oldest 2 days — disputing any stale-PR
  concern.)

Adversarial counter-evidence (why this is medium, not high): most of the sprawl is already
**measured and receipted on main** — the worktree-readiness campaign (PR #745) classified every
branch with an explicit no-deletion safety boundary; `branch_janitor` dry-ran 308 remote
branches (172 deletable) two days before this check; `BRANCH_REGISTRY.yaml` lists
`agent/magpie-seed` as an exempt "operator primary checkout"; and `make onboard` in any tree
prints its ahead/behind so a compliant session is told it is stale.

**Residual finding: measurement without disposal.** The count grew 25 → 48 → 60 across one week
of receipts. The word "enforced" with no enforcer is exactly the C3/C6 pattern (docs asserting
mechanisms that don't exist) recurring at the environment layer. Cheapest durable fixes: reword
or wire the budget rule (a checker comparing `git worktree list` to the portfolio is ~20 lines
in `agent_onboard.py`); keep one always-current main checkout; execute the already-written
janitor plan for the 172 receipted-deletable branches.

Smaller environment findings: machine-generated branches are force-pushed with no history audit
(`origin/chore/docops-autorefresh`, `origin/generated/status`); a nested worktree lives inside
the primary checkout (`.claude/worktrees/langgraph-parity-verifier-20260701`); two worktrees
point at the same commit on different branches (codex/droid forge-proving-ground).

### 5.2 Defect-class findings adjacent to C4 (verified at HEAD)

- **Fail-open telos gate:** `autonomous_agent.py:960-961` wraps the per-tool gate in
  `except Exception: pass  # gate failure should not prevent tool execution` — a crashing
  gatekeeper silently permits `bash`/`write_file`/`message_agent`. The audit documented the
  gate-granularity divergence but not that one side fails open.
- **Bypass instrument is class-limited:** `spine_bypass_report.py` measures only
  `server.submit(` call sites; subprocess-CLI (`claude -p`, `codex exec`) and direct
  `create_runtime_provider()` dispatch are structurally outside its "DRAINED TO ZERO" claim.
  Other god-files may host the same unmeasured class — worth one dedicated scan.
- **Nesting-guard evasion as pattern:** `_spawn_via_claude` pops `CLAUDECODE` and sets
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` (`thinkodynamic_director.py:3901-3905`; same
  pattern at `:1637`, `:3020`) — deliberately defeating a documented constraint.

### 5.3 Security sample (the audit had no security cluster)

Posture is materially better than "unaudited" implies: every third-party GitHub Action is pinned
to a full 40-hex SHA (zero tag pins); the sole `pull_request_target` workflow never checks out
PR code; cache-token and hermetic guards actually enforce; no secrets echoed to logs.

Two low-severity findings survive:
- `swarm_health_api.py:224` binds `0.0.0.0` by default — unauthenticated read-only internal
  state (telos/provider/loop) exposed to the LAN. Default should be `127.0.0.1`, wide bind
  opt-in.
- `oz-verify-claim.yml` interpolates the PR title directly into a cloud-agent prompt — a
  prompt-injection lane into a `contents:read`, skill-bounded agent (not shell RCE). Pass PR
  text via env var as sibling workflows already do.

Bounded-sample caveat: SAST workflows (semgrep/codeql rule packs) were not executed locally;
NATS is localhost-only by default but without TLS on that local path.

### 5.4 Corrections this gap-check makes to the audit itself

For any downstream consumer of `synthesis.md`, apply these edits:
1. §3/§5 streaming row: the `NotImplementedError` classes are **production-orphaned dead code**
   (name-collision hazard), not a live request-time crash (§2.2).
2. The "duplicate coverage" test-hygiene example is wrong — the two quality files share zero
   test names (§2.1).
3. C2's headline "cost_tracker.py has zero callers" → "cost_tracker's `log_cost()` write path
   has zero production callers": `_estimate_cost`/`CostEntry` ARE used in production
   (`providers.py:2595`, `llm_burn.py`, `room_bridge.py`) — which sharpens the finding: a real
   per-run cost estimate exists on the dispatch path while the economic ledger hardcodes 0.0.
4. Routing churn count: ≥4 reversals (add `7131b993f`), not 3 (§2.2).
5. Secrets count: 18, not ~15 (§2.7).
6. §10's thinkodynamic parenthetical should be a first-class finding with a roadmap item (§3.2).
7. MemoryKernel PR citation: #344 (`996c96a9c`), not #799 (§3.1).

---

## 6. The one trivial fix applied in this PR

Per the mandate's carve-out, after confirming zero ambiguity (§2.4):

- `dharma_swarm/terminal_commands/diagnostics.py:149-153` — replaced the never-working
  `from dharma_swarm.catalytic_graph import seed_ecosystem` / silent-`ImportError` block with
  `graph.seed_ecosystem()` (instance already in scope; outer `except Exception` still bounds).
- `scripts/governance/name_drift_allowlist.txt` — removed the now-dead grandfather entry
  (ratchet tightened; stale entries are ignored by the checker either way,
  `check_name_drift.py:349-350`).

Verified: `pytest tests/test_catalytic_graph.py -q` → 20 passed;
`python3 scripts/governance/check_name_drift.py` → OK (21 grandfathered, down from 22);
runtime smoke: `CatalyticGraph().seed_ecosystem()` → 6 nodes. No active track owns either
surface (checked `ACTIVE_TRACK.yaml` owned_surfaces at HEAD).

Not fixed (same function, out of trivial scope): `diagnostics.py`'s broad `except Exception`
fallbacks still convert any failure (numpy, corrupt archive) into silent zeros — the wider
silent-degradation pattern C2 describes.

---

## 7. Questions for the operator

1. **Portfolio:** organism-rewire item 8 says the next track must serve revenue. Is that on a
   dated commitment? Both non-substrate objectives need either a track or a recorded deferral
   decision (§4).
2. **Research-depth division of labor:** is the external mech-interp lab the intended owner of
   research-depth? If yes, one disclosure line in `ACTIVE_TRACK.yaml`/NORTH_STAR closes the gap.
3. **Thinkodynamic lane:** should the director's raw CLI dispatch be a sanctioned pre-spine lane
   (register it) or an unsanctioned bypass (gate it)? Is `start_allout_tmux.sh` still intended
   for use at all? (§3.2)
4. **Primary checkout:** is `agent/magpie-seed` (46 unmerged commits) intended to merge to main,
   or a permanent divergent lane? Either way, should a dedicated always-on-main worktree exist
   so at least one tree on the machine reflects reality? (§5.1)
5. **Worktree budget:** make it real (wire a checker) or delete the word "enforced"? And should
   the branch janitor's 172 receipted-deletable branches actually be deleted now?
6. **TUI:** do you drive the TUI (`cmd_tui`) in daily operation? That decides whether un-xfailing
   the 8 submit→runner tests is worth doing now (§2.1).
7. **Guardian issue #343** (pre-fix, 2026-05-24): still a live signal, or stale-daemon artifact
   to close?
8. **Health API bind:** is port 7433 ever legitimately reached from another host, or should the
   default flip to `127.0.0.1`? (§5.3)
9. **Review marks:** do you write review-mark JSONs yourself, or has any agent minted
   `reviewer=operator` marks on your behalf? The boundary holds only if the former (§2.6).
10. **Bulk-xfail pattern** (`7486f038b` "Green CI — all 6,760 tests passing"): accepted
    stabilization tactic, or flag on recurrence?

---

## 8. Method and honesty notes

- Everything above was verified against `origin/main` @ `665c90c35` in a fresh read-only
  worktree; the dirty primary checkout was quarantined per the mandate and never used for
  file-state claims. Main moved 11 commits between the audit's fork point (`f3a14b468`) and
  this check; nothing material to the audit landed in that window.
- Escalations/disputes were adversarially re-verified by two refuters each (evidence-quality
  lens re-ran the underlying commands; severity lens argued the strongest minor-case). Where a
  refuter overturned severity with new evidence, both sides are reported (§3.2, §5.1).
- Mid-run, Fable subagent credits were exhausted; 9 of 15 checkers re-ran on Opus 4.8 with
  cached results preserved. All four refuter votes on the two escalations therefore came from a
  different model family than the original investigators — accidental but useful decorrelation.
- Not covered: the two CI issues already fixed on #814 (per mandate); exhaustive security
  audit (G2 was a bounded sample across 5 lenses); runtime daemon behavior beyond
  process/log/heartbeat presence checks; the `~/ALL MECH INTERP` external lab (out of scope by
  doctrine).
