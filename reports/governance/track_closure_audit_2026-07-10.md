# Closure-Gauntlet Audit: TAM, Arena, and Chamber

Audit date: 2026-07-10. Entry SHA: `a2298f77880c409511290820840ef147e83e86eb`.
Branch: `codex/track-closure-audit-20260710`. This report is read-only with
respect to every audited track surface; the owned surfaces are declared in
`docs/governance/ACTIVE_TRACK.yaml:420-431,1246-1263,1413-1420`.

## Host record

The repository requires Python 3.11 or newer (`pyproject.toml:10`). The shell's
bare `python3` is 3.9.6, while the reusable project environment is Python
3.13.12:

```text
$ uname -sm && sw_vers -productVersion && command -v python3 && python3 --version
Darwin arm64
26.5.1
/usr/bin/python3
Python 3.9.6
[exit 0]

$ /Users/dhyana/dharma_swarm/.venv/bin/python --version
Python 3.13.12
[exit 0]
```

The bare interpreter has `pydantic`, `pytest`, and `yaml`, but not `textual`,
`numpy`, `scipy`, `hypothesis`, `aiofiles`, or `aiosqlite`. The Python 3.13
environment has all nine modules. This is the exact optional-dependency probe:

```text
$ python3 -c "import importlib.util; mods=['pydantic','pytest','textual','numpy','scipy','hypothesis','yaml','aiofiles','aiosqlite']; print(' '.join(f'{m}={bool(importlib.util.find_spec(m))}' for m in mods))"
pydantic=True pytest=True textual=False numpy=False scipy=False hypothesis=False yaml=True aiofiles=False aiosqlite=False
[exit 0]

$ /Users/dhyana/dharma_swarm/.venv/bin/python -c "import importlib.util; mods=['pydantic','pytest','textual','numpy','scipy','hypothesis','yaml','aiofiles','aiosqlite']; print(' '.join(f'{m}={bool(importlib.util.find_spec(m))}' for m in mods))"
pydantic=True pytest=True textual=True numpy=True scipy=True hypothesis=True yaml=True aiofiles=True aiosqlite=True
[exit 0]
```

Outbound HTTPS and GitHub access were available. The six-cell TAM sample used
five distinct cited endpoints; all returned HTTP 200, after which the claims
were checked against retrieved bodies, Cofounder primary docs, and the GitHub
API rather than URL presence alone:

```text
$ curl -L -sS -o /dev/null -w 'cofounder=%{http_code}\n' https://cofounder.co/
cofounder=200
$ curl -L -sS -o /dev/null -w 'polsia=%{http_code}\n' https://polsia.com/
polsia=200
$ curl -L -sS -o /dev/null -w 'polsia_github=%{http_code}\n' https://github.com/PolsiaAI/Polsia
polsia_github=200
$ curl -L -sS -o /dev/null -w 'context_studios=%{http_code}\n' https://www.contextstudios.ai/blog/polsia-how-a-solo-founder-hit-1m-arr-in-30-days-with-ai-agents
context_studios=200
$ curl -L -sS -o /dev/null -w 'cofounder_memory=%{http_code}\n' https://www.generalintelligencecompany.com/writing/introducing-cofounder-our-state-of-the-art-memory-system-in-an-agent
cofounder_memory=200
[all exit 0]

$ ollama --version && curl -fsS -o /dev/null -w 'ollama_http=%{http_code}\n' http://127.0.0.1:11434/api/tags
ollama version is 0.31.2
ollama_http=200
[exit 0]
```

The worktree was created when remote `main` was the entry SHA. Remote `main`
advanced during the audit, so all code findings remain explicitly entry-SHA
scoped:

```text
$ git rev-parse HEAD
a2298f77880c409511290820840ef147e83e86eb
[exit 0]
$ git ls-remote --exit-code origin refs/heads/main
94a3877c7799bbde7f0ac9adff060ee1f449683f  refs/heads/main
[exit 0]
```

### Mandatory baseline

The mandated default-host onboarding command failed after rendering the
portfolio, and the standalone status command still returned zero despite
multiple failed criteria:

```text
$ make onboard
... TypeError: Unable to evaluate type annotation 'dict[str, Any] | None' ...
make: *** [onboard] Error 1
[exit 2]

$ python3 scripts/governance/check_track_status.py
... orchestration-arena-v1-2026-06 10/12 ...
... hyperbolic-time-chamber-2026-07 5/11 ...
... company-builder-parity-2026-07 2/4 ...
[exit 0]
```

The handoff's green state is reproducible only when the project environment is
also prepended to `PATH`. Merely invoking the checker with the venv interpreter
does not redirect nested literal `python3` commands (`scripts/governance/check_track_status.py:444-461`):

| Invocation | TAM | Arena | Chamber | Exit |
|---|---:|---:|---:|---:|
| bare system Python | 2/4 | 10/12 | 5/11 | 0 |
| venv interpreter, ordinary `PATH` | 3/4 | 12/12 | 9/11 | 0 |
| venv interpreter and venv-first `PATH` | 4/4 SHIPPABLE | 12/12, 1 blocker | 11/11, 1 blocker | 0 |

Every PASS below therefore names the interpreter/host on which it passed. The
repository's Citation-or-silence rule is at `CLAUDE.md:84`.

### Classification rule

- **EXISTENCE** checks only that a path or text pattern exists.
- **SELF-REFERENTIAL** checks that a track-produced artifact replays, hashes,
  chains, or agrees with another track-produced projection.
- **BEHAVIORAL** executes behavior beyond presence/replay, even if only over a
  hermetic fixture.
- **EXTERNAL** compares the claim with evidence outside the audited artifact's
  authority.

The checker calls `receipt_valid` rigorous `S2_LANDED`
(`scripts/governance/check_track_status.py:586-623`), but the implementation
only checks JSON shape, required keys, timestamp age, digest, and chain links
(`scripts/governance/check_track_status.py:713-845`). It does not dereference a
source, run the claimed owner, or establish correspondence. Receipt criteria
are therefore SELF-REFERENTIAL unless a separate independent witness is bound.

## TAM: company-builder-parity-2026-07

**Headline:** 2 EXISTENCE / 3 SELF-REFERENTIAL / 1 BEHAVIORAL / 0 EXTERNAL.
The six declarations are at `docs/governance/ACTIVE_TRACK.yaml:1461-1499`.

### Criterion audit

| Entry | Class | Verdict | Independent result |
|---|---|---|---|
| `tam_ledger_exists` | EXISTENCE | CONFIRMED | `test -f scripts/governance/tam_ledger.py` exited 0. |
| `tam_axes_exist` | EXISTENCE | CONFIRMED | `test -f scripts/governance/tam_axes.py` exited 0. |
| `tam_tests_pass` | BEHAVIORAL | OVERSTATED | Project Python 3.13: 11 passed, exit 0. System Python: 11 setup errors, exit 1. The tests accept nonempty owner/source strings without correspondence (`tests/test_tam_ledger.py:88-98`). |
| `tam_receipt_valid` | SELF-REFERENTIAL | OVERSTATED | The checker reports nine keys, digest intact, fresh, exit 0; its proof boundary is structural (`scripts/governance/check_track_status.py:748-845`). |
| `tam_history_chain_valid` | SELF-REFERENTIAL | CONFIRMED narrowly | The checker reports four keys and an intact chain, exit 0. This proves ordering/tamper evidence only. |
| `tam_check_replays` | SELF-REFERENTIAL | REFUTED on the declared host | Exact `python3 scripts/governance/tam_ledger.py --check` exits 1. Explicit project Python exits 0 with `surface replays exactly (projection_only)`. |

Direct command evidence:

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_tam_ledger.py -q --no-header -p no:cacheprovider
11 passed
[exit 0]
$ python3 -m pytest tests/test_tam_ledger.py -q --no-header -p no:cacheprovider
11 errors
[exit 1]
$ python3 scripts/governance/tam_ledger.py --check
... TypeError: Unable to evaluate type annotation ...
[exit 1]
$ /Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/tam_ledger.py --check
tam_ledger --check: OK - surface replays exactly (projection_only).
[exit 0]
```

### Six-cell source and owner sample

| Axis | Competitor source result | `ours` owner result | Verdict |
|---|---|---|---|
| Org-shaped orchestration | [Cofounder](https://cofounder.co/) currently states departments, managers, and shared context; [Polsia GitHub](https://github.com/PolsiaAI/Polsia) documents nine scheduled Claude-CLI agents. | Spine dispatch is invoked at `dharma_swarm/orchestrator.py:2569-2638`; `tests/test_orchestrator_spine_dispatch.py` passed 6/6. Daemon persistence was not tested here. | CONFIRMED with live-host caveat (`scripts/governance/tam_axes.py:47-61`). |
| Human approval | [Cofounder](https://cofounder.co/) states approval for potentially dangerous actions. | Tier A/B blocking executes at `dharma_swarm/telos_gates.py:650-687`; `tests/test_telos_gates.py` passed 67/67. | CONFIRMED (`scripts/governance/tam_axes.py:62-68`). |
| Typed witnessed gates | The cited Cofounder page proves HITL approval, not the negative assertion that no typed/witnessed record exists. | Typed records and witness writes exist at `dharma_swarm/telos_gates.py:122-200,777-799`; witness persistence is fail-open. | OVERSTATED: the sole AHEAD premium lacks an external absence proof (`scripts/governance/tam_axes.py:69-78`). |
| Extensibility | [Cofounder](https://cofounder.co/) supports MCP, APIs, skills, and custom codebases. | `dharma_swarm/skills.py:192-280` and 26 passing tests prove skill discovery/matching only, not the composite MCP/API/codebase claim. | OVERSTATED parity (`scripts/governance/tam_axes.py:93-100`). |
| Public pricing and billing | `polsia.com` returned 200 but its current body contained neither `$49` nor `20%`; the cited [Context Studios article](https://www.contextstudios.ai/blog/polsia-how-a-solo-founder-hit-1m-arr-in-30-days-with-ai-agents) supports `$49/month` but not the composite 20% claim. | The cited clean negative is stale: current `RevenueTarget`, `Offer`, `OutreachDraft`, and `Engagement` are at `dharma_swarm/revenue/spine_models.py:100-165`, and payment recording is at `dharma_swarm/revenue/spine.py:278-338`; the no-mock integration battery passed 4/4. A public Stripe/billing surface is still absent. | REFUTED evidence cell (`scripts/governance/tam_axes.py:101-109`). |
| Internal architecture | The Polsia API shows exactly two commits, declared Celery/Claude-CLI components, and no advertised `backend/app` tree; Cofounder's [memory article](https://www.generalintelligencecompany.com/writing/introducing-cofounder-our-state-of-the-art-memory-system-in-an-agent) supports a three-tier design. | Repo inspection found 995 Python modules and 21 passing durable-invoker/receipt-chain tests. | OVERSTATED: component inventories do not establish cross-system behavioral parity (`scripts/governance/tam_axes.py:164-182`). |

The local behavioral counts and GitHub inventory claims above replay as follows
on the project Python and entry SHA:

```text
$ curl -L -sS https://polsia.com/ | rg -n '\$49|20%'
[no output; exit 1]
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_orchestrator_spine_dispatch.py -q --no-header -p no:cacheprovider
6 passed
[exit 0]
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_telos_gates.py -q --no-header -p no:cacheprovider
67 passed
[exit 0]
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_skills.py -q --no-header -p no:cacheprovider
26 passed
[exit 0]
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_revenue_spine_integration.py -q --no-header -p no:cacheprovider
4 passed
[exit 0]
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_graph_durable_invoker.py tests/test_graph_receipt_chain.py -q --no-header -p no:cacheprovider
21 passed
[exit 0]
$ git ls-tree -r --name-only a2298f77880c409511290820840ef147e83e86eb dharma_swarm | rg '\.py$' | wc -l
995
[exit 0]
$ gh api repos/PolsiaAI/Polsia/commits --paginate --jq 'length'
2
[exit 0]
$ gh api 'repos/PolsiaAI/Polsia/git/trees/main?recursive=1' --jq '[.tree[].path] | {count:length, backend_app:any(.[]; startswith("backend/app"))}'
{"backend_app":false,"count":120}
[exit 0]
```

### Parity re-derivation and UNMEASURED

The committed lanes are Behind 6, At parity 3, Ahead 1, No-equivalent 2,
Unmeasured 0 (`reports/governance/tam/tam_receipt.json:8-32`). The arithmetic is
correct: `6*0 + 3*1 + 1*1.5 = 4.5`; no-equivalent rows are excluded, so
`4.5/10 = 45.0%`. The implementation genuinely counts UNMEASURED as zero in
the denominator (`scripts/governance/tam_ledger.py:124-146`); inserting one
synthetic UNMEASURED row produced `4.5/11 = 40.9%`.

The semantic admission rule is the failure. Any nonempty URL, owner string, and
exceed string is accepted (`scripts/governance/tam_ledger.py:90-121`). The
following runnable adversarial probe passed validation and earned AHEAD:

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c "import runpy; m=runpy.run_path('scripts/governance/tam_ledger.py'); r={'key':'forged','capability':'forged','ours_status':'RUNS','ours_owner':'definitely_missing.py:999','ours_note':'','comp_name':'x','comp_status':'CLAIMED','comp_claim':'x','comp_sources':['https://example.com'],'comp_verification':'vendor-claim','structural_exceed_cite':'missing.md:999'}; m['validate_row'](r); r['bucket']=m['parity_bucket'](r); r['score']=m['BUCKET_SCORES'][r['bucket']]; print('validate_row=PASS bucket='+r['bucket'], 'parity_pct='+str(m['compute_parity']([r])['parity_pct']))"
validate_row=PASS bucket=AHEAD parity_pct=150.0
[exit 0]
```

The displayed `+10` is also labeled "gap is closing"
(`reports/governance/tam/COMPANY_BUILDER_PARITY.md:12`) even though the board
attributes it to measurement improvement rather than capability growth
(`reports/governance/tam/COMPANY_BUILDER_PARITY.md:47-50`); velocity only
compares headline values (`scripts/governance/tam_ledger.py:215-223`).

### Refutation and closure kind

The admission false-green is executable: an irrelevant URL and nonexistent
owner pass row validation and earn AHEAD in the probe above. The end-to-end
correspondence false-green is live separately: the committed pricing rationale
is contradicted by current RevenueSpine owners (`dharma_swarm/revenue/spine_models.py:100-165`;
`dharma_swarm/revenue/spine.py:278-338`) while the project-Python tests, receipt
digest, history chain, and explicit replay remain green in the criterion table
and command block above.

**Earned closure kind: none.** The default target resolves to `VERIFIED_SLICE`
(`scripts/governance/check_track_status.py:1802`), which requires the declared
scope's rigorous criteria and zero blockers (`docs/governance/ACTIVE_TRACK_FINAL_BOSS.md:7`).
The exact replay command fails here, and the promised verifiable parity scope
has no EXTERNAL criterion. A narrower deterministic-renderer slice works, but
substituting that scope would not satisfy the track's declared objective.

### v1 TODO

```yaml
- id: TAM-01
  title: Enforce external source-to-claim correspondence
  why: Nonempty irrelevant URLs currently earn AHEAD (scripts/governance/tam_ledger.py:90-121).
  acceptance: "python3 scripts/governance/tam_ledger.py --check-sources exits 0; the irrelevant-source fixture exits 1"
  size: M
  blocker: true
  owner_surface: scripts/governance/tam_ledger.py, scripts/governance/tam_axes.py, tests/test_tam_ledger.py

- id: TAM-02
  title: Replace owner strings with behavioral probes
  why: The pricing owner is contradicted by current RevenueSpine behavior (dharma_swarm/revenue/spine.py:278-338).
  acceptance: "python3 scripts/governance/tam_ledger.py --check-owners exits 0; a nonexistent-owner fixture exits 1"
  size: M
  blocker: true
  owner_surface: scripts/governance/tam_ledger.py, scripts/governance/tam_axes.py, tests/test_tam_ledger.py

- id: TAM-03
  title: Split composite capability axes
  why: Skills alone imply MCP/API/codebase parity and one price implies a composite billing model (scripts/governance/tam_axes.py:93-109).
  acceptance: "pytest -q tests/test_tam_ledger.py -k composite_axes exits 0"
  size: M
  blocker: true
  owner_surface: scripts/governance/tam_axes.py, reports/governance/tam/**, tests/test_tam_ledger.py

- id: TAM-04
  title: Make replay interpreter-stable
  why: The same SHA evaluates 3/4 or 4/4 solely from PATH (scripts/governance/check_track_status.py:444-461).
  acceptance: "python3 scripts/governance/check_track_status.py exits 0 and prints company-builder-parity-2026-07 4/4 SHIPPABLE on every supported-Python host without PATH rewriting"
  size: S
  blocker: true
  owner_surface: docs/governance/ACTIVE_TRACK.yaml, scripts/governance/check_track_status.py

- id: TAM-05
  title: Separate measurement velocity from capability velocity
  why: Source coverage improvement is rendered as capability-gap closure (scripts/governance/tam_ledger.py:215-223).
  acceptance: "pytest -q tests/test_tam_ledger.py -k velocity_causality exits 0; a source-only refresh emits capability_delta=0"
  size: S
  blocker: false
  owner_surface: scripts/governance/tam_ledger.py, reports/governance/tam/**, tests/test_tam_ledger.py

- id: TAM-06
  title: Add adversarial evidence-mutation tests
  why: Fake sources, owners, and exceed cites currently pass (scripts/governance/tam_ledger.py:90-121).
  acceptance: "pytest -q tests/test_tam_ledger.py -k 'rejects_irrelevant_source or rejects_missing_owner or rejects_missing_exceed' exits 0"
  size: S
  blocker: true
  owner_surface: tests/test_tam_ledger.py
```

TAM-01 converts the replay-only source criterion into an EXTERNAL gate;
TAM-02 adds the corresponding BEHAVIORAL owner gate.

## Arena: orchestration-arena-v1-2026-06

**Headline:** 12 EXISTENCE / 1 SELF-REFERENTIAL / 2 BEHAVIORAL / 0 EXTERNAL.
The 15 declarations are at `docs/governance/ACTIVE_TRACK.yaml:453-523`.

### Criterion audit

| Entry | Class | Verdict | Independent result |
|---|---|---|---|
| `arena_runner_exists` | EXISTENCE | CONFIRMED | `test -f dharma_swarm/coordination/arena/runner.py` exited 0. |
| `arena_scorer_exists` | EXISTENCE | CONFIRMED | `test -f dharma_swarm/coordination/arena/scorer.py` exited 0. |
| `orchestration_genome_exists` | EXISTENCE | CONFIRMED | `test -f dharma_swarm/coordination/genome.py` exited 0. |
| `frozen_taskpack_present` | EXISTENCE | CONFIRMED | `TASK_PACK_ID` and hashes exist at `dharma_swarm/coordination/arena/taskpack.py:28,107-133`. |
| `deterministic_scorer_hash` | EXISTENCE | CONFIRMED | Function exists at `dharma_swarm/coordination/arena/scorer.py:49-52`. |
| `orchestration_genome_class` | EXISTENCE | CONFIRMED | Class exists at `dharma_swarm/coordination/genome.py:121`. |
| `zero_weight_orchestrator_map_elites` | EXISTENCE | CONFIRMED | Class exists at `dharma_swarm/coordination/orchestrator_v1.py:47`. |
| `dpi_decorrelation_gated_on_correctness` | EXISTENCE | CONFIRMED | Gate exists at `dharma_swarm/coordination/dpi.py:49-61`; the undeclared DPI battery passed 8/8. |
| `council_trace_verification` | EXISTENCE | CONFIRMED only as existence | Council class exists at `dharma_swarm/council/council.py:94`; its control verification is refuted below. |
| `arena_v1_test_exists` | EXISTENCE | CONFIRMED | Named test exists at `tests/test_arena_v1.py:41`. |
| `dpi_test_exists` | EXISTENCE | CONFIRMED | `test -f tests/test_dpi.py` exited 0. |
| `closure_checks_test_exists` | EXISTENCE | CONFIRMED | `test -f tests/test_coordination_closure_checks.py` exited 0. |
| `arena_v1_controls_tests_pass` | BEHAVIORAL | CONFIRMED on project Python | 15 passed, exit 0; system Python failed collection, exit 2. |
| `arena_truth_surface_tests_pass` | BEHAVIORAL | OVERSTATED | Eight tests execute evolution, corpus, and replay behavior (`tests/test_arena_truth_report.py:35-133`), but a semantically stripped markdown surface also passes `check()`. |
| `arena_truth_receipt_valid` | SELF-REFERENTIAL | OVERSTATED | Nine keys, digest, and freshness pass; no independent live/control evidence is required (`scripts/governance/check_track_status.py:748-845`). |

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_arena_v1.py -q --no-header -p no:cacheprovider
15 passed
[exit 0]
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_arena_truth_report.py -q --no-header -p no:cacheprovider
8 passed
[exit 0]
$ /Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/arena_truth_report.py --check
arena_truth_report --check: OK - surface replays exactly (hermetic).
[exit 0]
$ python3 scripts/governance/arena_truth_report.py --check
... TypeError: Unable to evaluate type annotation ...
[exit 1]
```

### Semantic attack

The controls are real inside `runner.run`: the full-budget single-seat sweep,
self-MoA, ensemble, candidate, and parity control execute at
`dharma_swarm/coordination/arena/runner.py:416-425`; every arm enters the parity
ledger at `:427-454`; paired seeded bootstraps run against both baselines at
`:456-465`; and closeout requires both significance results at `:544-585`. A
runtime probe returned five arms, matching 24-call candidate/control ledgers,
both CI95 ranges `[0.4167, 0.7917]`, and `positive_lift_candidate`, exit 0.

The strongest parity tests are not criteria. The actual every-arm ledger,
dual-bootstrap, and fail-closed instrumentation tests are at
`tests/test_arena_parity_controls.py:43-92` and passed 9/9; the declared
behavioral criterion names only `tests/test_arena_v1.py`
(`docs/governance/ACTIVE_TRACK.yaml:503-508`).

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_arena_parity_controls.py -q --no-header -p no:cacheprovider
9 passed
[exit 0]

$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'from dharma_swarm.coordination.arena import ArenaRunner; from dharma_swarm.coordination.genome import OrchestrationGenome; g=OrchestrationGenome(roster=[{"role_id":"r1","member_id":"alpha-math","kind":"model"},{"role_id":"r2","member_id":"beta-code","kind":"model"},{"role_id":"r3","member_id":"gamma-logic","kind":"model"}],adjudication_rule="synthesize"); r=ArenaRunner().run(g); print("arms="+",".join(sorted(r["arm_scores"]))); print("candidate_calls={} control_calls={}".format(r["parity_control"]["candidate_total_calls"],r["parity_control"]["control_total_calls"])); print("ci={} ci_parity={}".format(r["significance"]["ci95_lift"],r["significance_vs_parity_control"]["ci95_lift"])); print("closeout="+r["closeout_state"])'
arms=best_single_full_budget,best_single_parity_budget,candidate,random_or_static_ensemble,same_budget_self_moa
candidate_calls=24 control_calls=24
ci=[0.4166666666666667, 0.7916666666666666] ci_parity=[0.4166666666666667, 0.7916666666666666]
closeout=positive_lift_candidate
[exit 0]
```

The truth receipt drops the runner's `parity_control`, `parity_ledger`, and
`significance_vs_parity_control` fields (`scripts/governance/arena_truth_report.py:89-128` versus
`dharma_swarm/coordination/arena/runner.py:522-525`). Its checker ignores the
fresh decision packet and requires only a genome ID plus `NO CAPABILITY CLAIM`
in markdown (`scripts/governance/arena_truth_report.py:205-229`). A temporary
markdown file containing only those strings returned `check_findings=[]`, exit
0.

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'import runpy,tempfile; from pathlib import Path; m=runpy.run_path("scripts/governance/arena_truth_report.py"); d=Path(tempfile.mkdtemp()); receipt=m["write_surface"](d); (d/m["MARKDOWN_NAME"]).write_text(receipt["best"]["genome_id"]+"\nNO CAPABILITY CLAIM\n",encoding="utf-8"); print("check_findings="+repr(m["check"](d)))'
check_findings=[]
[exit 0]
```

The 0.625 fixture lift is constructed, not discovered. The answer key and
correct-seat sets are duplicated literals (`dharma_swarm/coordination/arena/fixtures.py:56-75`),
and the full specialist router is seeded (`dharma_swarm/coordination/orchestrator_v1.py:98-108`).
Independent re-derivation found zero answer-key mismatches, seat totals 9/9/8,
router 24/24, and `(24-9)/24 = 0.625`. `evolve(generations=0)` already returns
the seeded score-1.0 positive winner.

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'from dharma_swarm.coordination.orchestrator_v1 import ZeroWeightOrchestratorV1; r=ZeroWeightOrchestratorV1(seed=0).evolve(generations=0); print("evaluated={} score={} closeout={} op={}".format(r.evaluated,r.best.score,r.best.closeout_state,r.best.lineage["mutation_op"]))'
evaluated=5 score=1.0 closeout=positive_lift_candidate op=seed_router
[exit 0]
```

The narrow non-goal is honored: the report says no production/C2 capability
claim (`reports/governance/arena/ARENA_TRUTH.md:6`), and C2 excludes hermetic
evidence (`scripts/governance/trust_gate_status.py:159-190`). The stronger
handoff request that lift is "nowhere phrased as capability" is REFUTED: the
same report publishes `verified_capability_delta` at
`reports/governance/arena/ARENA_TRUTH.md:55`, the package describes a verified
capability delta at `dharma_swarm/coordination/arena/__init__.py:3-6`, and DPI
labels it "Capability headline" at `dharma_swarm/coordination/dpi.py:64-69`.

### Live edge and Council

`DHARMA_ARENA_LIVE=1` selects `FixturePool.live`, then raises
`NotImplementedError` at `dharma_swarm/coordination/arena/fixtures.py:109-128`;
a full run exited 1 before the first task. A separate `LiveWorkerPool` matches
the runner's injectable pool seam (`dharma_swarm/coordination/arena/runner.py:84-97`;
`dharma_swarm/coordination/arena/live_pool.py:100-189`), but the documented
`dharma_swarm.coordination.arena.measure` constructor/CLI does not exist
(`dharma_swarm/coordination/arena/live_pool.py:1-8`; `test -e
dharma_swarm/coordination/arena/measure.py` exited 1). The local pool answered
one `llama3.2:latest` task with answer `4`, cost 66, and one receipt, exit 0.
That proves its provider adapter, not a full controlled live run or a completion
criterion.

```text
$ DHARMA_ARENA_LIVE=1 /Users/dhyana/dharma_swarm/.venv/bin/python -c 'from dharma_swarm.coordination.arena import ArenaRunner; from dharma_swarm.coordination.genome import OrchestrationGenome; g=OrchestrationGenome(roster=[{"role_id":"r1","member_id":"alpha-math","kind":"model"}],adjudication_rule="single"); ArenaRunner().run(g)'
NotImplementedError: DHARMA_ARENA_LIVE dispatch requires provider keys and is out of scope for the hermetic keystone.
[exit 1]
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'from dharma_swarm.coordination.arena.live_pool import LiveWorkerPool; p=LiveWorkerPool([{"task_id":"t1","family":"math","prompt":"What is 2+2?"}]); r=p.dispatch("llama3.2:latest","t1"); print("answer={} cost={} receipts={}".format(r.answer,r.cost,len(p.call_receipts)))'
answer=4 cost=66 receipts=1
[exit 0]
```

Council also does not independently verify controls. It reconciles the
candidate score only, trusts `baseline_score`, ignores
`parity_baseline_score`, and receives no control scorecards
(`dharma_swarm/council/council.py:176-205`;
`dharma_swarm/coordination/arena/runner.py:470-493`). A probe with candidate
`0.1`, baseline `-999`, parity baseline `999`, and parity true returned
`corroborated`, exit 0. Current runner closeout remains protected by its own
actual-score checks (`dharma_swarm/coordination/arena/runner.py:544-585`).

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'from dharma_swarm.council.council import Council,TraceVerificationRequest; q=TraceVerificationRequest(genome_id="g",route_receipts=[{"genome_id":"g"}],trace_receipts=[{"genome_id":"g"}],scorecard={"genome_id":"g","score":0.1},promotion_claim={"candidate_score":0.1,"baseline_score":-999,"parity_baseline_score":999,"budget_parity_logged":True}); r=Council().verify_orchestration_trace(q); print(f"verdict={r.verdict} finding={r.findings[-2]}")'
verdict=corroborated finding=promotion_claim:supported
[exit 0]
```

### Refutation and closure kind

The live false-green is direct: all 12 criteria pass under the project
environment while `DHARMA_ARENA_LIVE=1 ArenaRunner.run(...)` exits 1. The track
honestly retains that live blocker at `docs/governance/ACTIVE_TRACK.yaml:542-553`.

**Earned closure kind: none.** `VERIFIED_SLICE` requires zero blockers
(`docs/governance/ACTIVE_TRACK_FINAL_BOSS.md:7`), and the official evaluator
returns `shippable=False`, `ship_blocks=['1 open blocker next-item(s)']`
(`reports/governance/active_track_evidence.json:581-585`).
`PRODUCTION_READY` and `SUBSTRATE_TRUSTED` additionally require the Final Boss
packet (`docs/governance/ACTIVE_TRACK_FINAL_BOSS.md:11-37`), which this synthetic
fixture result cannot supply.

### v1 TODO

```yaml
- id: ARENA-01
  title: Wire a real live measurement entrypoint
  why: The environment seam exits 1 and no repo entrypoint constructs the injectable LiveWorkerPool (dharma_swarm/coordination/arena/fixtures.py:109-128; dharma_swarm/coordination/arena/runner.py:84-97).
  acceptance: "python3 -m dharma_swarm.coordination.arena.measure --live --roster \"$ARENA_LIVE_ROSTER\" --out /tmp/arena-live exits 0 and emits live mode, every control arm, parity ledgers, both CI95 results, zero label reads, and replayable receipts"
  size: M
  blocker: true
  owner_surface: dharma_swarm/coordination/arena/measure.py, live_pool.py, live measurement tests

- id: ARENA-02
  title: Run an externally sourced held-out benchmark
  why: The current 0.625 lift is derivable from duplicated fixture literals (dharma_swarm/coordination/arena/fixtures.py:56-75).
  acceptance: "python3 -m dharma_swarm.coordination.arena.measure --manifest \"$ARENA_HELDOUT_MANIFEST\" --check-external exits 0 with live receipts from at least two model families and no fixture source or held-out leakage"
  size: L
  blocker: true
  owner_surface: Arena benchmark adapter, external receipts, C2 verifier

- id: ARENA-03
  title: Convert truth criteria from replay to semantic behavior
  why: Stripped markdown and unsigned control fields pass (scripts/governance/arena_truth_report.py:205-229).
  acceptance: "python3 -m pytest tests/test_arena_truth_report.py -k 'rejects_missing_parity_ledger or rejects_missing_parity_significance or rejects_tampered_decision_packet' -q exits 0"
  size: M
  blocker: true
  owner_surface: scripts/governance/arena_truth_report.py, tests/test_arena_truth_report.py, docs/governance/ACTIVE_TRACK.yaml

- id: ARENA-04
  title: Make Council verify control evidence independently
  why: Forged baseline values corroborate (dharma_swarm/council/council.py:176-205).
  acceptance: "python3 -m pytest tests/test_council_profiles.py -k forged_controls -q exits 0; the candidate=0.1, baseline=-999, parity=999 fixture returns refuted and hashes both control scorecards"
  size: M
  blocker: false
  owner_surface: dharma_swarm/council/council.py, runner request schema, Council tests

- id: ARENA-05
  title: Type claim modality by measurement mode
  why: Hermetic output still serializes verified_capability_delta (reports/governance/arena/ARENA_TRUTH.md:55).
  acceptance: "python3 -m pytest tests/test_dpi.py -k claim_kind_by_measurement_mode -q exits 0; hermetic artifacts carry claim_kind=CONTROL_MACHINERY and reject production capability fields"
  size: S
  blocker: false
  owner_surface: dharma_swarm/coordination/dpi.py, arena report schemas, tests

- id: ARENA-06
  title: Make the gate interpreter-portable
  why: Bare Python fails both behavioral criteria (pyproject.toml:10).
  acceptance: "python3 scripts/governance/check_track_status.py exits 0 and prints orchestration-arena-v1-2026-06 12/12 on every supported-Python host without PATH rewriting; unsupported Python exits nonzero with a version diagnostic"
  size: S
  blocker: false
  owner_surface: Makefile, CI, scripts/governance/check_track_status.py
```

ARENA-02 converts the hermetic BEHAVIORAL proof into EXTERNAL evidence;
ARENA-03 replaces the receipt-valid SELF-REFERENTIAL gate with a BEHAVIORAL
semantic gate.

## Chamber: hyperbolic-time-chamber-2026-07

**Headline:** 3 EXISTENCE / 7 SELF-REFERENTIAL / 3 BEHAVIORAL / 0 EXTERNAL.
The 13 declarations are at `docs/governance/ACTIVE_TRACK.yaml:1291-1363`.

### Criterion audit

| Entry | Class | Verdict | Independent result |
|---|---|---|---|
| `chamber_doctrine_exists` | EXISTENCE | CONFIRMED | `test -f docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md` exited 0. |
| `phase0_dossier_exists` | EXISTENCE | CONFIRMED | `test -f docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md` exited 0. |
| `phase0_firewall_stated` | EXISTENCE | CONFIRMED only as prose | Exact `rg -F -q` exited 0 (`docs/governance/ACTIVE_TRACK.yaml:1299-1303`). |
| `baseline_receipt_valid` | SELF-REFERENTIAL | OVERSTATED | Structural validation exits 0, but `inward_ascent_baseline.py --check` exits 3, `CONTENT MISMATCH`; the receipt is bound to `devin-box` and `/home/ubuntu/.dharma` (`reports/governance/inward_ascent/baseline_receipt.json:5-8`). |
| `frontier_ledger_receipt_valid` | SELF-REFERENTIAL | CONFIRMED artifact-only | Six keys, digest, and TTL validate, exit 0. |
| `frontier_ledger_replays` | SELF-REFERENTIAL | OVERSTATED | Bare command exits 1; activated project environment exits 0. It ignores volatile displayed C1 during drift (`scripts/governance/frontier_ledger.py:65-67,267-285`). |
| `chamber_traces_tests_pass` | SELF-REFERENTIAL | CONFIRMED artifact-only | Six tests freeze schema, recompute digests, replay bytes, and reject tampering over synthetic rows (`tests/test_chamber_traces.py:1-80`). |
| `chamber_g1_run_receipt_valid` | SELF-REFERENTIAL | OVERSTATED | Validation exits 0, but receipt scorer hash `e0a4...` (`reports/governance/chamber/g1_run_receipt.json:27`) differs from current source SHA-256 `6a1bc6...`; the real G1 test is omitted from criteria (`docs/governance/ACTIVE_TRACK.yaml:1331-1343`). |
| `chamber_daily_delta_tests_pass` | BEHAVIORAL | OVERSTATED | Ten tests pass, but fake `"c"*64` causes pass because only hex shape is checked (`tests/test_chamber_daily_delta.py:16-31`; `dharma_swarm/chamber/daily_delta.py:39-53`). The real chain fails a one-day TTL check. |
| `chamber_predictions_tests_pass` | BEHAVIORAL | OVERSTATED | Ten tests pass using a temp Ginko store and fabricated Bronze rows (`tests/test_chamber_predictions.py:17-43`); no non-test caller exists. |
| `transcendence_ledger_tests_pass` | BEHAVIORAL | CONFIRMED narrowly | Seven hand-computed decomposition tests pass (`tests/test_transcendence_ledger.py:23-59`). |
| `transcendence_receipt_valid` | SELF-REFERENTIAL | CONFIRMED artifact-only | Corpus hash and two-row count match (`reports/governance/chamber/transcendence_receipt.json:2-6`); the receipt claims no benchmark capability. |
| `transcendence_ledger_replays` | SELF-REFERENTIAL | CONFIRMED on supported environment | Bare Python exits 1; activated project environment exits 0 and recomputes the pinned corpus (`scripts/governance/transcendence_ledger.py:207-231`). |

### Battery and primary-source re-derivation

The declared narrow tests pass under project Python: traces 6, daily delta 10,
predictions 10, and transcendence 7, all exit 0. The owned end-to-end battery
does not pass without PATH activation:

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_chamber_traces.py tests/test_chamber_gym_git_history.py tests/test_chamber_daily_delta.py tests/test_chamber_predictions.py tests/test_chamber_sandbox.py tests/test_chamber_ledger_history.py tests/test_transcendence_ledger.py -q --no-header -p no:cacheprovider
2 failed, 73 passed
[exit 1]

$ PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_chamber_traces.py tests/test_chamber_gym_git_history.py tests/test_chamber_daily_delta.py tests/test_chamber_predictions.py tests/test_chamber_sandbox.py tests/test_chamber_ledger_history.py tests/test_transcendence_ledger.py -q --no-header -p no:cacheprovider
75 passed in 7.08s
[exit 0]
```

Both failures are G1 scorer failures. The scorer launches literal `python3 -m
pytest` at `dharma_swarm/chamber/gym_git_history.py:275-284`; its scrubbed
environment sets `PYTHONNOUSERSITE=1` (`dharma_swarm/chamber/sandbox.py:85-100`),
so the macOS interpreter cannot see the user-site pytest installation. Thus the
fixture harness executes today only under a modified PATH, while its
digest-valid committed receipt is bound to an older scorer.

```text
$ shasum -a 256 dharma_swarm/chamber/gym_git_history.py reports/governance/chamber/trace_corpus.jsonl
6a1bc6287925ea63011da8ec3591eb18bfc43f0e87b5a843a408bf3a3100c50b  dharma_swarm/chamber/gym_git_history.py
113d6489e1f66a7ca92545ad780011daf5e481c1d2e30ccf7f97080e5249b86d  reports/governance/chamber/trace_corpus.jsonl
[exit 0]
$ jq -r '"receipt_scorer="+.scorer_hash, "receipt_trace="+.trace_corpus.sha256, "receipt_rows="+(.trace_corpus.rows|tostring)' reports/governance/chamber/g1_run_receipt.json
receipt_scorer=e0a4e986b076b0c9132e83a71a64d277c1e8f884f8892f37d76ed42ccc732145
receipt_trace=113d6489e1f66a7ca92545ad780011daf5e481c1d2e30ccf7f97080e5249b86d
receipt_rows=2
[exit 0]
$ PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/inward_ascent_baseline.py --check
--check: CONTENT MISMATCH stored=e313628e407385b7 recomputed=80f34d5e57d356c8
[host state changed since commit; exit 3]
```

The underlying Git substrate is real: `git rev-list --count de92625f23b3a9a8495cc014cb01e7016db8c1ba`
returned 1331, `--merges --count` returned 273, and the repo was non-shallow,
matching `reports/governance/inward_ascent/baseline_receipt.json:109-124`.
Frontier input hashes also match their pins
(`reports/governance/chamber/frontier_ledger_receipt.json:46-55`). The G1 trace
hash and two-row count match the receipt, but neither fact repairs the current
scorer-hash mismatch.

```text
$ git rev-list --count de92625f23b3a9a8495cc014cb01e7016db8c1ba
1331
[exit 0]
$ git rev-list --merges --count de92625f23b3a9a8495cc014cb01e7016db8c1ba
273
[exit 0]
$ git rev-parse --is-shallow-repository
false
[exit 0]
$ python3 scripts/governance/frontier_ledger.py --check
ImportError: cannot import name 'UTC' from 'datetime' (.../python3.9/datetime.py)
[exit 1]
$ PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/frontier_ledger.py --check
frontier_ledger --check: OK
[exit 0; success detail omitted]
$ python3 scripts/governance/transcendence_ledger.py --check
ImportError: cannot import name 'UTC' from 'datetime' (.../python3.9/datetime.py)
[exit 1]
$ PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/transcendence_ledger.py --check
transcendence_ledger --check: OK [decomposition replays from the pinned corpus]
[exit 0; punctuation normalized to ASCII]
```

### Standing-loop and host audit

The daily-delta chain is intact but stale: the same structural validator with
`fresh_ttl_days=1` returns `passed=False`, `stale: 3d old`. Its first two cause digests have no
repo occurrence outside `deltas.jsonl` (`rg -l -F ...` exit 1), although the
elevation spec requires resolvable causes and freshness
(`docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md:136-166`). Searches
find `run_gym`, `append_daily_delta`, `emit_micro_prediction`, and
`resolve_with_bronze` only in definitions/tests
(`dharma_swarm/chamber/gym_git_history.py:346`; `tests/test_chamber_gym_git_history.py:168`;
`dharma_swarm/chamber/daily_delta.py:56`; `tests/test_chamber_daily_delta.py:27`;
`dharma_swarm/chamber/predictions.py:41,118`; `tests/test_chamber_predictions.py:37-125`).
No matching LaunchAgent was found. Filtered `ps` and `crontab` inspection is
**UNTESTABLE-HERE** because the sandbox rejected both piped commands before
their scans; no process or crontab absence is claimed.

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'import runpy; m=runpy.run_path("scripts/governance/check_track_status.py"); r=m["check_receipt_valid"]("reports/governance/chamber/daily_delta/deltas.jsonl",["schema","date","yesterday","behavior_changes","metabolic_efficiency","digest","prev_digest"],fresh_ttl_days=1,expect_chain=True); print("passed={} detail={}".format(r.passed,r.detail))'
passed=False detail=receipt reports/governance/chamber/daily_delta/deltas.jsonl is stale: 3d old > fresh_ttl_days=1
[probe exit 0]
$ rg -l -F -e 7d5ceb04c180fef4af510583ad459055e5742d280196348e7b93d5eebfc33872 -e 0cf90430ba5159890e32c5b212562ee11c7112d09ef35567c2a2c52008ac2ab3 . --glob '!reports/governance/chamber/daily_delta/deltas.jsonl'
[no output; exit 1]
$ rg -n '[r]un_gym|[a]ppend_daily_delta|[e]mit_micro_prediction|[r]esolve_with_bronze' /Users/dhyana/Library/LaunchAgents
[no output; exit 1]
$ ps -axo pid=,command= | rg '[r]un_gym|[a]ppend_daily_delta|[e]mit_micro_prediction|[r]esolve_with_bronze'
zsh: operation not permitted: ps
[exit 1 before scan]
$ crontab -l | rg '[r]un_gym|[a]ppend_daily_delta|[e]mit_micro_prediction|[r]esolve_with_bronze'
zsh: operation not permitted: crontab
[exit 1 before scan]
```

The old Zeitgeist receipt says `ccr-session` received 403 and needs a daemon
host (`reports/governance/chamber/zeitgeist_attempt_receipt.json:2-7`), but this
host now receives HTTP 200 from HN Algolia. The receipt is environmental history,
not current network truth.

```text
$ curl -fsS -o /dev/null -w 'hn_algolia_http=%{http_code}\n' 'https://hn.algolia.com/api/v1/search?query=agents'
hn_algolia_http=200
[exit 0]
```

Current local state has `runtime.db` and `ontology.db` but no canonical Bronze
raw-receipt directory or Ginko prediction file. A read-only query found 8,894
`delegation_runs`; a fresh baseline still reports zero ingest, zero resolved
predictions, and Brier UNKNOWN. The expected Bronze and prediction paths are
declared at `scripts/governance/inward_ascent_baseline.py:101-147` and
`dharma_swarm/ginko_brier.py:29-32`.

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'from pathlib import Path; p={"runtime_db":Path.home()/".dharma/state/runtime.db","ontology_db":Path.home()/".dharma/ontology.db","bronze_raw_receipts":Path.home()/".dharma/meta/intelligence_supply_chain/bronze/raw_receipts","ginko_predictions":Path.home()/".dharma/ginko/predictions.jsonl"}; print(" ".join("{}={}".format(k,v.exists()) for k,v in p.items()))'
runtime_db=True ontology_db=True bronze_raw_receipts=False ginko_predictions=False
[exit 0]
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'import sqlite3; p="file:/Users/dhyana/.dharma/state/runtime.db?mode=ro"; c=sqlite3.connect(p,uri=True); print("delegation_runs={}".format(c.execute("SELECT COUNT(*) FROM delegation_runs").fetchone()[0])); c.close()'
delegation_runs=8894
[exit 0]
$ /Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/inward_ascent_baseline.py --no-write --json | jq -c '{summary,surfaces:[.surfaces[]|select(.id=="ingest_volume" or .id=="routing_regret" or .id=="forecast_brier")|{id,measured,value,detail}]}'
{"summary":{"surfaces_measured":3,"surfaces_total":9,"surfaces_unknown":6},"surfaces":[{"id":"ingest_volume","measured":true,"value":0,"detail":null},{"id":"routing_regret","measured":false,"value":null,"detail":{"delegation_runs":8894}},{"id":"forecast_brier","measured":false,"value":null,"detail":null}]}
[exit 0]
```

The blocker is real and safety-critical: candidate-controlled code executes as
an ordinary subprocess with host filesystem/network/process authority. The
module explicitly says it is not a jail (`dharma_swarm/chamber/sandbox.py:15-19`),
and `rg -n 'seccomp|container|jail|sandbox-exec|bwrap|nsjail|firejail'
dharma_swarm/chamber` returned only that warning at `sandbox.py:15-16`, exit 0;
no Chamber jail implementation was found.

### Refutation and closure kind

Three green/absent scenarios are live at the entry SHA:

1. G1 receipt validation exits 0 while the scorer hash is stale and the
   ordinary-host G1 E2E test fails.
2. Daily-delta tests pass while the real chain is stale and causal digests are
   unresolved.
3. Frontier replay exits 0 under the activated environment while displayed C1
   changed from committed RED/0.25 to live AMBER/0.725 because C1 is excluded
   from drift comparison (`scripts/governance/frontier_ledger.py:65-67,267-285`).

```text
$ /Users/dhyana/dharma_swarm/.venv/bin/python -c 'import json,runpy; from pathlib import Path; m=runpy.run_path("scripts/governance/trust_gate_status.py"); p=m["build_scoreboard"](Path.cwd(),Path.home()/"dharma_swarm_live",None); g=next(x for x in p["conditions"] if x["id"]=="C1"); print(json.dumps({k:g[k] for k in ("id","verdict","score")},separators=(",",":")))'
{"id":"C1","verdict":"AMBER","score":0.725}
[exit 0; read-only build_scoreboard call]
```

**Earned closure kind: none.** Chamber targets `CLOSED_NOT_PROD`
(`docs/governance/ACTIVE_TRACK.yaml:1267`), but still has the explicit jail
blocker (`docs/governance/ACTIVE_TRACK.yaml:1374-1377`). Its own Phase-1 done
condition additionally requires live Zeitgeist consumption, resolved
predictions/Brier, an evolution iteration, a fresh causal delta, and closure
checks (`docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md:389-397`).
The nearest honest milestone is a current, reproducible G1 `VERIFIED_SLICE`.

### v1 TODO

```yaml
- id: CHAMBER-01
  title: Make the scorer use the evaluator interpreter
  why: Literal python3 makes the owned battery fail 2/75 without PATH rewriting (dharma_swarm/chamber/gym_git_history.py:275-284).
  acceptance: "python3 -m pytest tests/test_chamber_*.py tests/test_transcendence_ledger.py -q exits 0 without PATH modification"
  size: S
  blocker: true
  owner_surface: dharma_swarm/chamber/gym_git_history.py, tests/test_chamber_gym_git_history.py

- id: CHAMBER-02
  title: Replace G1 digest completion with current-scorer replay
  why: A stale scorer receipt passes validation (reports/governance/chamber/g1_run_receipt.json:27).
  acceptance: "python3 scripts/governance/chamber_g1_replay.py --check exits 0; python3 -m pytest tests/test_chamber_gym_git_history.py -k rejects_scorer_hash_drift -q exits 0"
  size: M
  blocker: true
  owner_surface: G1 runner, governance replay script, docs/governance/ACTIVE_TRACK.yaml

- id: CHAMBER-03
  title: Isolate candidate execution from host authority
  why: The current sandbox is explicitly not a jail (dharma_swarm/chamber/sandbox.py:15-19).
  acceptance: "python3 -m pytest tests/test_chamber_jail.py -q exits 0 and proves outside-file read, network connect, and child-process escape fail closed"
  size: L
  blocker: true
  owner_surface: dharma_swarm/chamber/sandbox.py, jail adapter, adversarial tests

- id: CHAMBER-04
  title: Resolve every delta cause and enforce daily freshness
  why: Fake hex causes pass and the real chain is stale (dharma_swarm/chamber/daily_delta.py:39-53).
  acceptance: "python3 -m pytest tests/test_chamber_daily_delta.py -k 'rejects_unresolved_cause or fresh_real_chain' -q exits 0"
  size: M
  blocker: true
  owner_surface: dharma_swarm/chamber/daily_delta.py, chain tests, docs/governance/ACTIVE_TRACK.yaml

- id: CHAMBER-05
  title: Wire one repo-native daily Chamber command
  why: Gym, prediction, resolver, and delta calls occur only in definitions/tests (dharma_swarm/chamber/gym_git_history.py:346; dharma_swarm/chamber/predictions.py:41,118; dharma_swarm/chamber/daily_delta.py:56).
  acceptance: "python3 -m dharma_swarm.chamber.daily_cycle --check exits 0 after landing HN Bronze, emitting and resolving a provenance-clean prediction, and appending a fresh delta"
  size: L
  blocker: true
  owner_surface: Chamber daily-cycle command, predictions, daily delta, cadence tests

- id: CHAMBER-06
  title: Run one bounded live evolution iteration behind the jail
  why: live_solver_status remains unavailable even when keys dispatch (`dharma_swarm/chamber/gym_git_history.py:332-343`).
  acceptance: "python3 -m dharma_swarm.chamber.gym_git_history --live --iterations 1 --jail required --out /tmp/chamber-g1 exits 0 and emits non-fixture providers, current scorer hash, compute ROI, and one completed iteration"
  size: L
  blocker: true
  owner_surface: G1 runner and live solver surfaces

- id: CHAMBER-07
  title: Make baseline and Frontier host authority explicit
  why: The baseline is producer-host-bound and Frontier excludes displayed C1 drift (scripts/governance/frontier_ledger.py:65-67).
  acceptance: "python3 -m pytest tests/test_frontier_ledger.py -k 'host_authority or c1_drift' -q exits 0; producer-host replay exits 0, another host emits needs_host, and displayed C1 drift fails"
  size: M
  blocker: false
  owner_surface: scripts/governance/inward_ascent_baseline.py, scripts/governance/frontier_ledger.py, tests

- id: CHAMBER-08
  title: Gate closure on the original Phase-1 done conditions
  why: Those conditions are not completion criteria (docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md:389-397).
  acceptance: "python3 scripts/governance/chamber_phase1_gate.py --check exits 0 only when live ingest ratio, resolved predictions, non-UNKNOWN Brier, fresh causal delta, and an evolution receipt all pass"
  size: M
  blocker: true
  owner_surface: docs/governance/ACTIVE_TRACK.yaml, Chamber receipts and verifiers
```

CHAMBER-05 converts one-off SELF-REFERENTIAL receipts into a BEHAVIORAL standing
cycle; CHAMBER-06 adds the first live solver evidence. A later reality-graded
environment is still required before an EXTERNAL capability claim.

## Cross-track summary

### Criterion-class distribution

| Track | EXISTENCE | SELF-REFERENTIAL | BEHAVIORAL | EXTERNAL | Total |
|---|---:|---:|---:|---:|---:|
| TAM | 2 | 3 | 1 | 0 | 6 |
| Arena | 12 | 1 | 2 | 0 | 15 |
| Chamber | 3 | 7 | 3 | 0 | 13 |
| **All three** | **17** | **11** | **6** | **0** | **34** |

Half the declared gates are existence checks, 32.4% are self-referential,
17.6% execute behavior, and none is external. The counts are the row totals in
the three criterion tables above; `17+11+6+0=34`.

The checker therefore confuses two evidence modalities. A small enforceable
promotion rule would be:

```text
IntegrityReceipt<T> proves Untampered(T).
IntegrityReceipt<T> cannot satisfy CorrespondsTo(T, ExternalSource).
Promote only with Witness<T, kind=BEHAVIORAL|EXTERNAL,
                          authority_domain != producer.authority_domain>.
```

That rule is directly falsifiable against the current checker: its receipt
validator never consults an independent authority
(`scripts/governance/check_track_status.py:748-845`), and all three tracks have
zero EXTERNAL criteria.

### Closure adjudication

| Track | Earned now | Evidence gap to next kind |
|---|---|---|
| TAM | None | Make the exact gate portable, bind URL claims to external evidence, and bind `ours` rows to behavioral probes before `VERIFIED_SLICE`. |
| Arena | None | Clear the live blocker and produce a semantically complete live-controlled receipt before `VERIFIED_SLICE`; a held-out external benchmark is required for capability promotion. |
| Chamber | None | Make G1 current/reproducible, land the jail, and satisfy the original Phase-1 done conditions before `VERIFIED_SLICE` or `CLOSED_NOT_PROD`. |

`VERIFIED_SLICE` requires scoped rigorous evidence and no blockers;
`CLOSED_NOT_PROD` is an intentional nonproduction close; production kinds
require Final Boss review (`docs/governance/ACTIVE_TRACK_FINAL_BOSS.md:5-37`).

### Top five cards by leverage

1. **TAM-01** - stops arbitrary strings from becoming externally warranted
   AHEAD evidence (`scripts/governance/tam_ledger.py:90-121`).
2. **CHAMBER-01** - restores the currently failing owned G1 execution path
   (`dharma_swarm/chamber/gym_git_history.py:275-284`).
3. **ARENA-01** - adds the missing measurement entrypoint and full live-control
   run wiring (`dharma_swarm/coordination/arena/live_pool.py:1-8`;
   `dharma_swarm/coordination/arena/fixtures.py:109-128`).
4. **CHAMBER-03** - closes the native-code host-escape blocker before live
   evolution (`dharma_swarm/chamber/sandbox.py:15-19`).
5. **ARENA-02** - replaces constructed fixture lift with held-out external
   evidence (`dharma_swarm/coordination/arena/fixtures.py:56-75`).

The audit edited no audited owned surface. Verify the committed scope with
`git diff --name-only a2298f77880c409511290820840ef147e83e86eb...HEAD`; the
expected sole path is
`reports/governance/track_closure_audit_2026-07-10.md`.
