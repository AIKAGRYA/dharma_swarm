# Constitutional Cybernetic Intelligence — Deep Research Dossier

**Date:** 2026-08-24
**Status:** RESEARCH DOSSIER (declared intent only; runtime truth stays with the code and closure checks; this document grants no edit, merge, deploy, or actuation authority)
**Subject:** the operator's "Constitutional Cybernetic Intelligence" thesis — six planes, twenty-capability rubric, ten axioms, eight-step build sequence — evaluated against dharma_swarm at commit `abc8bd3` (origin/main) and against the 2025–2026 external landscape.
**Method:** 17-agent research workflow (2026-08-24): six read-only repo audits with citation-or-silence discipline, five web research agents with source-URL discipline, a red team, a sequencing architect, a completeness critic, and two gap-driven follow-up audits (an effect-primitive census and an audit of the thesis's claimed-strong rubric squares). One follow-up (auditing the external vibe-halt repository) was not executed: that repository is outside this session's authorized scope, so every vibe-halt claim in this dossier remains operator-provided context, unverified.
**Provenance convention:** `path:line` citations were produced by the audit agents against commit `abc8bd3` and spot-re-verified for the load-bearing claims; external claims carry URLs. Line numbers drift as main moves; the cited files are the durable pointer.

---

## 0. Executive verdict

The thesis is **directionally right and quantitatively optimistic**. Its diagnosis — dharma_swarm has the vocabulary and organs of a constitutional architecture but not the single unavoidable causal machine that makes the organs authoritative — is confirmed by every audit, usually more brutally than the thesis itself states. Its self-scoring is inflated on exactly the squares it calls strong: every claimed-strong capability that was audited came back downgraded, and the corrected composite is **≈44–47/100**, not 50/100.

Three corrections change the plan more than any confirmation:

1. **The "one effect door" cannot be an in-process Python class.** A library cannot mediate the process it lives in (the 1975 reference-monitor requirement: tamper-proof, always-invoked, verifiable). The repo's only two doors that ever actually held are enforced *outside* the agent's trust domain (merge authority: GitHub branch protection + structural deletion of the merge actuator, `tests/test_pr_merge_control_no_actuation.py`) or by *absence* (live self-mutation: a lease documented to never validate, `dharma_swarm/evolution_safety.py:222-228`). The door must eventually be a trust boundary, not a code path — and until then, its honest form is convergence of the existing fail-closed machinery plus a merge-blocking ratchet that freezes the bypass surface.

2. **The essay's step 1 is a restatement of the repo's own unadopted spec.** Humming V2 §6 (`docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_V2_2026-08-01.md:389-431`) already contains the full constitutional envelope design and the one-dispatcher architecture, 23 days old, with zero adoption rows in `ACTIVE_TRACK.yaml`, while one-line fixes named by its own adversarial review remain unlanded. The organization's demonstrated failure mode is not missing architecture; it is *writing the architecture and not landing the wire*. A plan that opens with seven more planes repeats the disease at the meta level.

3. **The novelty claim survives only in narrowed form.** ARIA's £59M Safeguarded AI programme and the Guaranteed Safe AI position paper (Dalrymple, Bengio, Russell, Tegmark et al., arXiv:2405.06624) publicly present the *conceptual* whole. AWS ships a verified default-deny one-door for agent tool calls (Cedar inside Bedrock AgentCore Policy, GA 2026-03). CaMeL (DeepMind, SaTML 2026) implements "external content cannot select capability" with provable-security claims. Palantir ships ontology + typed-action-door + receipts-as-objects. What is genuinely unclaimed publicly: **a shipping, software-domain system that composes typed intent, deterministic falsification as an admission input, one effect door spanning effect classes, signed receipts, and — the emptiest square anywhere — re-admission of every adaptive/self-improving change through the same door.**

The charged path (§6) therefore inverts the essay's sequence: **credibility first (one CLOSED_LIVE loop), then freeze (ratchet), then converge (widen existing doors), then type (Intent IR), then prove (formal), then predict (causal/world)** — each later plane consuming the earlier one as substrate.

---

## 1. Fact-check of the thesis against the repository

Seventeen specific factual claims from the essay were adversarially verified at `abc8bd3`. Result: **15 CONFIRMED, 1 PARTIAL, 1 REFUTED.**

| # | Claim (abbreviated) | Verdict | Anchor |
|---|---|---|---|
| 1 | No universal EffectDispatcher/one-effect-door exists | CONFIRMED | no `dharma_swarm/effects/`; spec calls it "the one genuinely new build" (`HARNESS_LOOP_GRAPH_HUMMING_SPEC_V2_2026-08-01.md:424`) |
| 2 | ActionEnvelope carries actor/action/tools/provenance fields | CONFIRMED | `dharma_swarm/semantic_governance.py:100-111` |
| 3 | ActionEnvelope lacks all eight constitutional fields (capability/lease, target id, pre-state hash, expiry, idempotency, effect class, rollback, policy version) | CONFIRMED | same; idempotency lives in a different type (`dharma_swarm/spine/identity.py:42`) |
| 4–9 | Humming V2 status/diagnosis/modalities/closure-definition claims | CONFIRMED | `HARNESS_LOOP_GRAPH_HUMMING_SPEC_V2_2026-08-01.md:3,27-29,104-116,143-156,196-197,389-431` |
| 10 | CLOSED_LIVE 0/13; HARNESS_PROVEN 11/13; BLOCKED 2/13 | CONFIRMED | `docs/governance/ACTIVE_TRACK.yaml:159`; loops 12/13 blocked on One Wire quorum |
| 11 | Substrate nativeness ~10–15%, target 30%+ | CONFIRMED | `docs/governance/ACTIVE_TRACK.yaml:60`; `docs/governance/SOVEREIGN_MANIFEST.md:11` |
| 12 | Semantic governor is not authority confinement; effect paths bypass it | CONFIRMED | only production ActionEnvelope constructor is unreachable (`dharma_swarm/shakti_warrant.py:479,524` + `scripts/governance/check_shakti_warrant.py:304` passes no claims); zero references in any effect path |
| 13 | DharmaKernel: 25 axioms, SHA-256 signed | CONFIRMED | `dharma_swarm/dharma_kernel.py:29-74,355-361`; enforcement is commit-time-only, bypassable |
| 14 | Ontology/claims/claim-graph code exists | CONFIRMED | `dharma_swarm/ontology.py:449`, `claim_graph.py:81`, `dharma_corpus.py:93` |
| 15 | No learned world model | CONFIRMED | `dharma_swarm/world_model.py` is a hand-seeded Forrester snapshot; "research … is not built yet" (`world_model.py:275-285`) |
| 16 | No causal/SCM machinery | PARTIAL | no code; but a do-calculus invariant (U4) is *declared* in the signed kernel manifest with a nonexistent falsification test (`kernel/manifest.yaml:93-113`; `benchmarks/telos_redteam/` absent) |
| 17 | No Lean/SMT/TLA+/model checking anywhere | **REFUTED** | Z3 purity verification runs in CI (`packages/titanium-verify/`, `.github/workflows/kernel-titanium-verify.yml`); CrossHair in CI; one TLA+/TLC-checked spec (`specs/TaskBoardCoordination.tla`, one-shot 2026-03). Accurate formulation: *formal methods exist but are not constitutive* — path-filtered to `packages/**`, in no required merge context, never touching the effect paths |

---

## 2. Corrected rubric

Audited scores, with the thesis's original in parentheses. Every audited claimed-strong square downgraded.

| Capability | Thesis | Audited | One-line justification |
|---|---|---|---|
| Typed action/proposal boundary | (4) | **2** | typed models exist in patches; the named envelope is inert — one unreachable production constructor |
| Identity + capability authority | (3) | **2** | six incompatible authority representations; no cryptographic tokens; leases gate one wake-loop classifier |
| Universal one-door effects | (1) | **1** | confirmed; the one fail-closed door covers only evolution self-modification (`promotion_gate.py:47`; `diff_applier.py:241`) |
| Operational ontology/world state | (3) | **2** | real typed ontology + gated `execute_action`, but 10+ production writers bypass it; `check_security` never called in production; no version history; 84 registered state surfaces |
| Machine-checkable formal semantics | (1) | **1.5** | Z3/CrossHair/TLA+ exist but quarantined; runtime constitution is substring matching with an always-PASS gate (`telos_gates.py:438-440,534-535`) |
| Explicit causal/counterfactual reasoning | (1) | **1** | declared-only (U4); production "causal read" is a timestamp+run_id correlation join (`cybernetics_codex.py:820-861`) |
| Learned world model | (0) | **0** | fair for authoritative use; stale as an ecosystem claim (SWE-World, WMA, Qwen-AgentWorld exist externally, advisory-grade only) |
| Compile stochastic reasoning → deterministic artifacts | (1) | **1.5** | durable-invoker memo-replay, seeded gauntlet replay, `TopologyGenome.compile()` are real fragments |
| Deterministic replay (in dharma_swarm) | (4) | **2** | the 4/5 belonged to vibe-halt (unverified here); in-repo: digest-bound checker replay + dispatch memoization, but no decision-sequence replay |
| Counterexample/fault generation | (5) | **3** | real seeded falsifiers (arena byte-stable replay verified live; gauntlet; 41 Hypothesis property tests ENFORCED via required pytest), but hermetic subjects are scripted fixtures, the arena live lane raises NotImplementedError, and **no falsification output reaches any admission door** (`pr_merge_control.py`: zero references; `pramana-probe.yml` self-describes "can never block anything") |
| Evidence provenance/receipts | (4) | **3.5** | four integrity tiers; the highest-volume receipts are unhashed/mutable (INSERT OR REPLACE), the dispatch door is env-bypassable, and the flagship consumption evidence is discarded at its only call site (`providers.py:2923`) |
| Separation evaluator/authority/actor | (4) | **2** | real in the evolution/spine lanes; in the agent-execution lanes the same in-process code gates and executes, and the actor can disable its own gate |
| Resource/time/loop boundedness | (4) | **2.5** | bounded per-component; unbounded as a system (`agent_loop.sh` `while true`; EconomicEngine never blocks spend) |
| Durable graph/state-machine execution | (3) | **3** | fenced effectively-once dispatch is wired; the Pregel engine has zero production callers; four parallel checkpoint substrates |
| Explicit human authority edges | (4) | **3** | strongest edge is GitHub-enforced operator review — real, but borrowed from GitHub, gating a deliberately uninhabited actuator; no live runtime effect requires an in-band human |
| Causally demonstrated self-improvement | (2) | **1.5** | closed-loop only in scratch harnesses; production self-improvement open-loop by the repo's own machine-checked admission |
| External production grounding | (1) | **1** | confirmed: one externally-merged PR (waggle_mcp #222), $0 revenue self-confessed, empty Darshan ledger, One Wire quorum honestly refusing authority (N=3/5, M=1/3) |
| OS/hardware anti-bypass | (2) | **1** | DockerSandbox exists unwired; `SandboxManager.create()` always returns LocalSandbox (`sandbox.py:241-249`); production bash runs as host subprocess behind substring blocklists |
| Frontier stochastic cognition | (4) | 4 | not contested |
| Semantic compilation / Intent IR | (—) | ~1 | `action_type: str` + prose `content` is precisely the stringly-typed boundary the thesis diagnoses |

**Corrected composite ≈ 44–47/100.** The red team's observation stands: the original 50/100 landed in the right band *via compensating errors*, which means the rubric as scored could decorate the build but not steer it. What can steer it is a ratcheted mechanical number (§6, step 2).

---

## 3. Ground truth: what the audits established

### 3.1 The waist does not exist; what exists is six doors and five highways around them

- **The inert envelope.** `ActionEnvelope` (`semantic_governance.py:100-111`) is a semantic-similarity scoring payload. Its only production construction site (`shakti_warrant.py:479`) is behind an `if claims:` branch whose sole production caller passes no claims (`check_shakti_warrant.py:304`) — the SemanticGovernanceKernel never runs outside tests. The warrant lane that hosts it is CI-advisory (`fourfold_warrant` in the advisory list of `docs/governance/CI_TRUTH_CONTRACT.json`).
- **The bypass inventory (all WIRED, all ungoverned or string-gated):** `build_engine.execute_task` spawns a Hermes agent with terminal+file toolsets and auto-commits on tests-pass with zero gates (`build_engine.py:100-107,267,319-326`; callers `economic_agent.py:446`, `custodians.py:606-633`); Codex spawns default to `--dangerously-bypass-approvals-and-sandbox` (`codex_cli.py:17,38`); Claude headless defaults to `permission_mode="bypassPermissions"` (`claude_cli.py:108`); `agent_runner` gates task *prose* once, then writes files and shells ungated per-call (`agent_runner.py:1943-1973,2288-2299`); `LocalSandbox.execute` is a host subprocess behind 7 denylist regexes (`sandbox.py:83-91,151`); `autonomous_agent._tool_bash` bypasses both sandboxes (`autonomous_agent.py:1011-1041`).
- **The six independent admission mechanisms:** telos keyword gates (default trust mode `internal_yolo` skips the strict patterns, `telos_gates.py:432,449`); spine RuntimeWarrant — genuinely fail-closed but registered for exactly two surfaces (`spine/warrant.py:37-53`); the evolution promotion door — the repo's one real, ENFORCED one-door, scoped to self-modification only (`promotion_gate.py:47-122`, `evolution.py:3348,3495`); durable-invoker idempotency — exactly-once plumbing, not authority, fail-open by design (`graph/durable_invoker.py:435-458`); the ontology's `execute_action` — hard-wired gates onto an in-memory registry that 10+ writers bypass; and Merge Master — genuinely enforced, at the git boundary, by GitHub.
- **Where "evidence is not authority" is actually implemented:** `validate_merge_authorization` refuses to let a policy snapshot claim actuation (`pr_merge_control.py:277-353,2173`), and merge capability is enforced by structural deletion of the actuator (AST-verified by `tests/test_pr_merge_control_no_actuation.py`). Where it is violated: the Shakti/fourfold warrant lane, where **self-asserted metadata booleans directly raise the verdict** (`shakti_warrant.py:286-345`) — the proposer scores its own warrant.

### 3.2 The evidence plane is deep, honest, and severed at the consumer leg

- The claim boundary (CLOSED_LIVE 0/13) is real, machine-pinned by `json_count_equals` criteria with a ship-veto (`ACTIVE_TRACK.yaml:159,182-191,249-307`) — but the pinning gate is CI-advisory.
- The standing 2026-08-15 audit was generated on a host with **no runtime DB** (`latest_audit.json` `runtime.exists=false`): all 11 HARNESS_PROVEN verdicts are projections over committed, **undigested, author-producible** JSON receipts.
- The strongest verifier in the repo — the WP-LC4 consumption checker with independent P1–P4 recomputation, digest-bound receipts, two-digest replay (`scripts/governance/loop1_consumption_check.py`) — **has only ever passed on fixtures**, because the live routing path discards its own consumption evidence at the sole call site: `providers.py:2923` binds the `ReceiptConsumptionEvidence` to `_`. The repo certifies this gap deliberately (`tests/test_loop1_consumption_check.py:270-286`, `test_current_main_audit_shape_is_honestly_incomplete`).
- Negative-control ablation is ABSENT from the closure plane; the production "causal read" criterion is a correlation join, not an intervention.
- Receipt integrity is four-tiered: content-addressed Go receipts → sha256-chained VerifiedMachineReceipt → digest-bound singletons → **unhashed, mutable, env-bypassable bulk receipts** (EvidenceReceipt undigested; `runtime_receipts` INSERT OR REPLACE at `runtime_state.py:3191`; `DHARMA_SPINE_DISPATCH` opt-out at `orchestrator.py:2575-2578`; router reward learning entirely unreceipted at `providers.py:2683-2693`).

### 3.3 The falsification machinery is better than the wiring

The claimed-strong "counterexample generation" square audits at 3/5, and the shape of the shortfall matters: the arena's hermetic fitness is genuinely deterministic (byte-stable replay verified live this session) but falsifies **scripted fixture models whose correct-sets are authored so routing wins** (`coordination/arena/fixtures.py:71-75,122-127`); the DharmaGraph gauntlet is real seeded differential falsification against real LangGraph, on an advisory lane; 41 Hypothesis property tests are ENFORCED via required pytest; the chamber gym's live-solver lane never landed; and the **only admission-consumable falsifier interface in the repo** (forge_v2 promotion packets → `promotion_gate` → `evolution.py:3348`) guards a lane that is shadow-locked by default and injects LLM critics at the positive-claim edge. No falsification output reaches `pr_merge_control.py` (zero references in 3,979 lines) or any tool dispatch.

### 3.4 The effect-primitive census (round-2 decision data)

Regex census over `dharma_swarm/`, `api/`, `scripts/{runtime,governance,uplift_guards}/`, excluding tests: **1,168 effect-primitive call sites across 470 files** (subprocess family 272 + 27 async; file writes 516 + 247 open-for-write; shutil 42; HTTP client constructors 64; `os.system` 0). Concentration is LOW — the top-10 files hold 11% — so caller-by-caller routing of the whole census is a ~470-file campaign and **not** the plan. But the six bypass lanes collapse to **~12–16 edited call sites** because four already funnel through internal choke points (`LocalSandbox.execute` serves four consumers including `api/chat_tool_execution.py:308`; `claude_cli.py:118` serves pulse/cron; `codex_cli` builds one prefix for six consumers; `build_engine` git operations are three function-level edits).

Seed ranking for the one-door (audited coverage-per-edit): **two-phase hybrid wins (4.5/5)** — Phase 1 fuses the spine RuntimeWarrant's fail-closed admission semantics (`warrant.py:181-242`) with the durable-invoker's intent/complete commit semantics (`durable_invoker.py:737-785`) on the RuntimeStateStore ledger that already has the tables (`runtime_state.py:2545,2710,2742,2772`), routed through the six choke points; frozen by a **required-gate pytest AST ratchet** banked at day-one reality. Phase 2 installs a `sys.addaudithook` fuse inside `runtime_admission` (already the admitted-process door, imported at `orchestrate_live.py:45`) to convert the build-time ratchet into a runtime property. The ontology's `execute_action` is explicitly **not** the door seed — it performs zero process-level effects and its `requires_approval` is satisfied by caller-supplied params (`ontology.py:840-858`), a self-attestation hole to fix when it becomes the Intent IR layer.

The ratchet has an exact in-repo template: `scripts/governance/assurance_boundary.py` AB-04 ("No direct LLM-provider import … outside the canonical door. One way, not two."), the drained-to-zero allowlist doctrine of `spine_bypass_report.py:50-57`, and the AST walker of `tests/test_sarathi_import_boundaries.py` — shipped as a pytest test so it is merge-blocking on day one via the required `tests_py311/py312` contexts.

---

## 4. Frontier: what the world already has (and what it lacks)

- **Palantir** is the reference implementation of "operational ontology bound to one door": Action Types as the single typed write interface committing atomic transactions; declarative submission criteria evaluated at the door, independent of edit permissions, including a first-class *is-this-a-simulation* execution-context bit; one auto-generated `[LOG]` receipt object per submission, linked to every edited object and queryable in the same world model; scenario forks whose merge-back is itself a gated action; two-key authorization (agent scope ∩ principal permission); and — the thesis's cited July 2026 update is real — pro-code agents authenticating with scoped permissions instead of client secrets (palantir.com/docs: action-types/overview, submission-criteria, action-log, merge-scenario, ontology-mcp, announcements/2026-07). Its own docs concede atomicity dies at the ontology boundary (webhooks doc) — the honest precedent for scoping the door's guarantees. It has **no** formal semantics, causal plane, or learned world model.
- **AWS is the closest shipping composition**: Cedar — a Lean-modeled, theorem-proved, default-deny authorization core with ~100M nightly differential tests binding model to implementation — became the gate intercepting every LLM-agent tool call in Bedrock AgentCore Policy (GA 2026-03), with partial evaluation pruning the tools the model can even see, plus SMT-validated NL-to-policy authoring (Cedar Analysis, Bedrock Automated Reasoning). The Cedar discipline — *small executable formal model, proofs about the model, differential testing as the verified-to-live bridge* — is the template for dharma_swarm's formal kernel, at roughly one person-quarter, not seL4's 20 person-years.
- **CaMeL** (DeepMind, SaTML 2026, arXiv:2503.18813) is the canonical implementation of "external content cannot select capability": control flow extracted only from the trusted query, untrusted data quarantined with no tool access, capabilities attached to values. **FIDES** (Microsoft, arXiv:2505.23643, shipped in Agent Framework) does deterministic dual-label information flow. **Progent/AgentSpec/FORGE** provide deterministic runtime monitors. These are the differentiation targets, not competitors to out-build.
- **Causal/world models, honestly**: the buildable-now causal layer is known-DAG only (DoWhy-GCM attribution over a hand-specified pipeline graph — the graph comes from known CI/merge topology, sidestepping discovery, whose benchmarks are demonstrably gameable). The production-proven predictive layer for CI is boring and strong: Meta's predictive test selection (arXiv:1810.05286) and Google's flake-aware culprit finding. Learned software world models now exist in the literature (SWE-World arXiv:2602.03419 — 6.2%→68.2% on SWE-bench Verified as a *training/ranking surrogate*; WMA's transition-delta abstraction arXiv:2410.13232; R-WoM showing multi-step simulation degrades fast) — credible as **advisory** rankers, demonstrably not admission evidence; an independent eval (arXiv:2606.27406) finds frontier models brittle at predicting real execution.
- **Compiled AI is a real multi-group trend**, not one paper: Compiled AI (arXiv:2604.05150, vendor-adjacent, benchmark-only), PreAct's compile-runs-into-state-machines with store-time re-validation and runtime state-check-or-abort (arXiv:2606.17929), SPL's syntactic separation of stochastic and deterministic nodes (arXiv:2607.07727), LLMCompiler, DSPy. Intent IR has directly copyable prior art: TypeChat (validate→repair→fail-closed, non-LLM confirmation rendering), Genie/ThingTalk (typed canonical intent language, PLDI 2019), LLM+P, grammar-constrained decoding.
- **Weak anchors to drop from the thesis:** Symbolica (active, ~$35M, nothing independently demonstrated in 2.5 years) — cite as aspiration only; Merly/DIF — zero third-party validation, closed binaries; the "July 2026 compositional neuro-symbolic review" could not be located as cited (nearest candidates: ASPLOS 2026 compositional-architectures paper; AAAI-MAKE 2026 arXiv:2604.26521); causal-AI market sizings contradict each other by three orders of magnitude. Marcus & Belle (AAAI 2026, 40(48):40954-40961) is real but is philosophical cover, not an architecture.

---

## 5. Red team: what would kill this program

1. **FATAL if ignored — the reference-monitor problem** (§0.1 above). Corollary: the eventual real door is a separate broker process/OS boundary that exclusively holds credentials and write mounts, with the swarm reduced to proposing envelopes to it. Until then, only the ratchet + choke-point convergence is honest.
2. **FATAL if ignored — the plan-is-the-disease loop** (§0.2). The falsification test is behavioral, not architectural: *can the organization land ten fail-closed flips on existing organs within 30 days?* (See §7.)
3. **"Atomic/idempotent/bounded" overclaims**: atomicity must be scoped to the canonical store with ordering discipline + recorded compensation elsewhere (Palantir's own concession; GoEX's reversible/irreversible taxonomy, arXiv:2404.06921).
4. **No consequence taxonomy**: the audited invisible transitions that most corrode the constitution are ones no subprocess/file/network interception catches — in-memory router reward mutation, unauthenticated writes to the semantic judge's own corpus (`~/.dharma/corpus.jsonl`), unauthenticated `GateRegistry.approve()`. "Consequential effect" must include *mutations to decision-relevant state*.
5. **Planes 7–8 contradiction**: a learned world model feeding admission smuggles stochastic cognition back into the authority plane; keep it advisory forever (rank candidates before the ONE real CI run) or the thesis violates its own first axiom.
6. **Gate economics**: the repo's ten bypass flags (`internal_yolo`, `bypassPermissions`, `dangerous_bypass=True`, `DHARMA_SPINE_DISPATCH` opt-out, fail-open tollbooth…) are revealed preference — when a door slows the organism, the door loses. The door needs an explicit throughput contract (small fail-closed set first: git push, outbound sends, payments, live self-mod; ratchet outward on measured latency evidence) or it will grow the eleventh bypass flag.
7. **Three concrete month-6 failure trajectories** to watch: (a) *kernel ships as organ #7* — wired to two convenient surfaces, rubric self-score rises on existence, CLOSED_LIVE stays 0/13 (tell: the ratchet is not required-gate by month 2); (b) *proof-first inversion* — green Lean theorems over a model of an unbuilt door while `providers.py:2923` still discards evidence (tell: proof artifacts merge while the ungoverned-call-site count doesn't decrease); (c) *fail-closed collapse* — the door lands universal, throughput craters, `DHARMA_EFFECT_DOOR=permissive` appears within weeks (tell: an "internal" effect class carrying ~95% of traffic).
8. **One mechanical composed-property metric** must replace the rubric as scoreboard: *fraction of consequential effects whose receipts chain to an admission decision at the door*, ratcheted in required CI — the analogue of the existing `json_count_equals` pinning. Planes multiply only through wired edges; the audits show the failure mode is dead edges, and a plane that exists-but-unwired contributes zero.

---

## 6. The charged path

Ninety days, sequenced so every increment is shippable inside the repo's own MECHANISM/WIRED/ENFORCED and HARNESS_PROVEN/CLOSED_LIVE discipline. No new portfolio track (WIP is at max 10/10); every step maps into existing tracks' next-items. Operator involvement across the whole quarter: one scripted host session, a handful of PR approvals, and exactly two decisions (§6.9).

### Step 1 (days 1–10) — First CLOSED_LIVE loop + kill the two stale one-line defects
Persist the discarded `ReceiptConsumptionEvidence` fields (timestamp, consumer_trace_id, consumer_boot_id, consumed_trace_ids, decision_delta, chain) into the routing audit record at `providers.py:2923` — the digest-bound checker already accepts that payload shape (`tests/test_loop1_consumption_check.py:243-262`). Fix the GAUNTLET_REGRESSION emit signature (`orchestrate_live.py:1849-1855` vs `signal_bus.py:143` — a TypeError swallowed by `except: pass` since before 2026-08-01) and the non-atomic workflow checkpoint (`workflow.py:391-392` → tmp+rename+fsync). Then the bounded operator host session per `LOOP1_CLOSURE_SPEC_2026-07-11.md` §8: telemetry env on, generate completed delegation runs, one deliberate restart for the cross-boot P4 leg, run `loop1_consumption_check --check` with provenance env set, refresh the codex audit on-host, ship the WP-LC5 atomic non-author-merged PR flipping the pinned counts to **CLOSED_LIVE 1/13**.
*Done when:* checker passes P1–P4 against real host stores; on-host audit shows Loop 1 CLOSED_LIVE; a regression test pins the persisted fields. *Tracks:* loop-closure-2026-06 (+ dharmagraph for `workflow.py`).

### Step 2 (days 7–25) — Effect-surface census + merge-blocking ratchet
`tests/test_effect_primitive_boundary.py`: AST Call-node matcher over the primitive set, per-file baseline JSON banked at day-one reality (~1,168 sites / 470 files), shrink-only, kernel modules allowlisted — modeled on `test_sarathi_import_boundaries.py` and the AB-04 "one door" contract wording. ENFORCED from first merge because it rides the required pytest contexts; no CI_TRUTH_CONTRACT change needed. The UNGOVERNED count becomes the program's scoreboard.
*Done when:* ratchet red on a synthetic new ungoverned site and on a status downgrade (test-of-the-test committed); green on main. *Tracks:* sovereign-safety-tcb or titanium-hardening; `scripts/governance/` edits take packet ceremony.

### Step 3 (days 20–55) — Waist v0 by widening existing fail-closed doors (no new kernel class)
Fuse RuntimeWarrant admission + durable-invoker commit on RuntimeStateStore into an `EffectAdmissionKernel` reached by **convergence**: (1) `build_engine` obtains a warrant + tollbooth `require_identity=True` before spawn and before commit; (2) `agent_runner` write/edit/shell gain per-call warrant checks with derived `side_effect_key`; (3) `codex_cli`/`claude_cli` bypass flags stop being defaults — they require presenting a valid, unexpired, unrevoked execution lease (`operator_core/execution_lease.py:187-253,350-383` already implements expiry+revocation). Constitutional envelope v0 = ExecutionIdentity + side_effect_key + typed effect_class + lease_id + policy_version. Retire `semantic_governance.ActionEnvelope` from the authority story. Flip `unprotected_dispatch` from tag-and-proceed to DENY on fenced surfaces (the KEEL counters exist to size this safely).
*Done when:* `SURFACE_PRE_ACTION_CLAIMS` ≥5 surfaces; `require_identity=True` at ≥3 production sites (today: 0); the six lanes reclassified in the ratchet baseline (cannot regress); every admitted effect on a fenced surface emits a receipt naming its warrant — the "one admitted causal ancestry" field.

### Step 4 (days 45–70) — One door for ontology writes
Privatize `create_object/update_object/put_object`; route the 10+ direct writers through `execute_action`; move registry storage onto the hub's SQLite connection so modifies+creates+links+receipt commit in one transaction; implement `ActionDef.creates`; append-only `object_versions` (replacing INSERT OR REPLACE); allowed `(from_state, to_state)` transition relation; `check_security` on every path; fix the caller-supplied-approval hole (`ontology.py:840-858`); extend the ratchet with a no-direct-mutation rule. Fuse semantics (ontology) with transactions (RuntimeStateStore) — neither alone suffices.

### Step 5 (days 60–80) — Flip the fail-open defaults; promote exactly ONE advisory gate to required
`external_strict` default at effect-emitting boundaries; remove or warrant-gate the `DHARMA_SPINE_DISPATCH` opt-out; route fenced-surface bash through DockerSandbox (network NONE) or give LocalSandbox real OS confinement; promote one gate (candidate: kernel-titanium-verify — green, <1s; alternative: active_track pinning) through the documented advisory→stability-window→required ratchet. One gate only: the ensemble principle prices gates in diversity, and a flaky required context stalls the merge lane. Heavy hot-path/packet step.

### Step 6 (days 70–90) — Intent IR v0, fenced surfaces only
Pydantic discriminated union keyed on `effect_class` replacing prose payloads *only where the warrant already gates*; TypeChat validate→one-bounded-repair→fail-closed; ThingTalk-style canonical serialization feeding `side_effect_key` derivation so equal intents hash equal; CaMeL/FIDES provenance rule as a type-level check — capability/destination fields populated only from trusted-provenance values (closes the live injection edge at `strategy_reinforcer.py:284-292`).

### Step 7 (post-90-day gate A) — Formal kernel v0 as property/differential tests; vibe-halt contract-only
Keep the admission decision a **pure function** (envelope × authority-state → admit/deny). Encode the ~10 constitutional invariants first as Hypothesis property tests + a differential harness in required pytest (the Cedar discipline; the orphaned TLA+ spec is the standing proof that proofs without CI wiring rot). Lean/TLA+ only after the shape freezes — realistic effort per published data: person-weeks (TLA+ lifecycle spec) to 2–4 person-months (Lean admission model), ~one person-quarter total. For vibe-halt: this quarter produce only a typed falsifier contract (candidate envelope + scoped determinism claim → signed counterexample-or-pass receipt in the Step-1 evidence grammar) and an advisory lane; admission-blocking authority only after its receipts demonstrate decision-delta on real traffic — "evidence is not authority" applies to vibe-halt's own outputs too.

### Step 8 (post-90-day gate B) — Receipts become world-model food
Free rider inside Steps 3–4: WMA-style transition-delta fields on receipts (abstracted before-state, typed envelope, abstracted after-state, outcome). Causal/world planes gate on: ≥1 more loop CLOSED_LIVE, N-thousand transition receipts accumulated, and an operator-approved marginal-randomization mechanism (randomize reversible gate decisions so the door emits genuine do()-data — the honest alternative to causal discovery from observational logs). Learned world model stays advisory forever.

### 6.9 Do-not-do (the essay proposes several of these)
1. No greenfield EffectDispatcher class as the opening move (it becomes admission mechanism #7; the V2 dispatcher is the convergence *target*).
2. Do not fatten the inert `ActionEnvelope` — retire it from the authority story.
3. No learned world model this quarter; no DoWhy layer over observational logs (it reproduces the correlation-join failure with more math).
4. No Lean/TLA+/Alloy proofs before the admission function's shape freezes and the conformance harness exists.
5. Do not wire vibe-halt into admission until it is audited and its receipts show decision-delta (currently unverified operator-provided context).
6. No full Intent IR before the waist exists (typed objects with no enforced door are more vocabulary — the ActionEnvelope lesson).
7. No whole-ontology nativeness push across the 84 state surfaces while the write plane is open.
8. Promote exactly one advisory gate this quarter, not several.
9. No new portfolio track (WIP 10/10); if one must open, one must close first — an operator decision.
10. No cryptographic capability tokens / Ed25519 signer replacement until there is one admission point for signatures to bind to (after Step 5).
11. Do not publish the strong-form novelty claim (see §8).
12. Never weaken Merge Master or the six required contexts to move faster — the PR door is the working template for the waist, not an obstacle. Loops 12–13 stay BLOCKED behind One Wire until genuinely satisfied.

---

## 7. The 30-day falsification test of the whole program

The red team's single most diagnostic observable, adopted here as a commitment device. Within 30 days, land:

1. the `providers.py:2923` evidence-persist one-liner (Step 1's core),
2. `require_identity=True` at the two existing tollbooth production sites (today: zero),
3. one advisory→required gate promotion (or the ratchet test merged as required-by-construction).

These are one-line-to-days-scale conversions of existing organs from advisory/fail-open to enforced/fail-closed, at near-zero design risk. **If these three do not land, the organization cannot land an eight-plane constitution, and the correct response is to shrink the program, not to write more architecture.** Cheap same-class hardening to batch alongside: default `dangerous_bypass=False` (`codex_cli.py:17`) and `permission_mode=None` (`claude_cli.py:108`), forcing the ~8 consumer sites to opt in visibly.

---

## 8. The research claim, narrowed to survive review

**Do not publish:** "no organization publicly presents the whole composition." ARIA/Guaranteed-Safe-AI presents the conceptual whole; AWS ships 3–5 planes; the ten axioms are substantially Saltzer–Schroeder 1975 restated (complete mediation, fail-safe defaults, separation of privilege) — presenting them as new invites reviewer contempt.

**Publishable, once first-CLOSED_LIVE + an enforced waist exist as differentiating evidence:** *a shipping, software-domain agent organism in which (a) natural-language cognition compiles to typed intent, (b) every consequential effect crosses one deterministic admission door with signed receipts, (c) deterministic falsification is a consumed admission input, and (d) every adaptive/self-improving change — including changes to the governance machinery — re-enters the same admission door.* Property (d) is the least-occupied square in the public landscape (closest: Redwood's AI Control agenda, arXiv:2511.02997; Governed Capability Evolution, arXiv:2604.08059) and is the one dharma_swarm's DarwinEngine/promotion-gate machinery is unusually positioned to demonstrate.

**Venues:** SOSP/OSDI main track for the built system (SOSP 2026 already accepts agent infrastructure; stage a position version at AgenticOS@SOSP); IEEE S&P / USENIX Security / SaTML for the authority framing (CaMeL's venue; AgentDojo the expected benchmark); ACM CAIS for fit. **Mandatory differentiation list:** Guaranteed Safe AI + ARIA; CaMeL; FIDES; Progent/AgentSpec/AgentLTL; AgentCore Policy/Cedar; Palantir AIP action types; AIOS + agent-OS line; GoEX; Temporal-class durable execution; Compiled AI; MI9; Meta's Rule of Two; AI Control; NeMo Guardrails; and the MCP security corpus (NSA CSI June 2026, OWASP MCP Top 10, MCPTox) — which doubles as the motivation evidence that the ecosystem's tool invocation is many-doored by default.

---

## 9. Open items

1. **vibe-halt audit — blocked on operator authorization.** The completeness critic determined the repository is publicly accessible (AmitabhainArunachala/vibe-halt), but auditing it means attaching and running code from a repository this session was never authorized to integrate, so the safety layer correctly stopped it. Until an operator-authorized session audits it, thesis step 4 and the two rubric squares scored on vibe-halt's behalf (deterministic replay, counterexample generation at 4–5/5) remain unverified context, and the charged path treats vibe-halt as contract-only (§6, step 7).
2. **Citation repairs to the essay:** drop or correct the "July 2026 compositional neuro-symbolic review"; downgrade Symbolica to aspiration-stage; remove Merly/DIF as an evidence anchor; replace claim 17 with the "exists but not constitutive" formulation.
3. **Cheap falsification-wiring moves** surfaced by the strong-squares audit, absorbable into Steps 3–5: make the pramana probe's REFUTED verdict a consumed input of merge control (its own workflow header names this as the Stage-1 promotion condition); promote the langgraph-oracle gauntlet replay once its custody check is CI-stable; pin `derandomize=True` or explicit seeds across all Hypothesis suites so CI counterexamples replay.
4. **External grounding unlock**, named by the repo's own instruments: one paid engagement receipt through RevenueSpine flips both the $0 file and the One Wire M=1/3 domain constraint; future external receipts should commit resolvable content-addressed leaves rather than hash-pointing at an operator laptop (the cycle-004 confessed-missing-manifest lesson).
