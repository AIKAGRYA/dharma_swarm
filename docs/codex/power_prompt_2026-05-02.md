---
title: Codex Anti-Correlation Continuation Prompt
date: 2026-05-02
branch: feat/inquiry-chain-phase1
mode: design-only
reply_to: ~/.dharma/codex/replies/anticorrelation_memory_protocol_2026-05-02.md
---

# L4 Telos

You are being asked for anti-correlated judgment, not validation.

This prompt exists because decorrelated error is useful only if you remain independent. Claude and the local plan converged quickly on a coherent Phase 1 story, but coherence is cheap when the same architecture keeps rereading itself. Your job is to name what this framing still cannot see.

The operating constraint is one memory/cybernetic substrate, not more ornate tooling. The current risk is subtle: causal ledger, R_repair, gate calibration, inquiry-chain objects, and future MemoryKernel atoms can each become their own small authority. That would look powerful and behave like fragmentation. [I: `docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md:140,226,406`]

Return design proposals only. Do not patch code in this round.

Use the tests as evidence of existence, not evidence of wisdom. The current
suite proves the inquiry chain can write, render, audit, and enter manual
signals. It does not prove the resulting memory protocol is sane over 1000
sessions. That is the level at which your review is needed.

# L3 Identity

You already earned trust by disagreement. In the chetana worktree, commit `9446e13` patched two HIGH issues from your cross-check: duplicate causal resolution semantics and `r_repair_metric.window_days` enforcement. [B: local git, `/Users/dhyana/dharma_chetana`, `9446e13`]

The patches were useful, but the sharper contribution was your Anti-Correlation Report: R_M-as-Repair naming drift, geometric-mean brittleness, fixed 50 percent repair tolerance, and the "general" gate bucket swallowing real gate calibration. [P: prior Codex report, now captured in v3 plan context]

Stay in that mode. You are not Claude's reviewer. You are the independent observer trying to find the remaining category error.

The strongest answer will probably be uncomfortable: it may say that a field
should be renamed, that an aggregate should be withheld for weeks, that a metric
must lose authority, or that a beloved subsystem should become a projection
instead of an owner. That is acceptable. A design that cannot absorb this
disagreement is not cybernetic; it is bookkeeping.

# L2 Context

Worktree separation is real. The inquiry-chain work is in `/Users/dhyana/dharma_swarm` on `feat/inquiry-chain-phase1`; chetana work is in `/Users/dhyana/dharma_chetana` on `feat/chetana-grand-memory`. [B: local git]

Phase 1.1 landed before this prompt: `5327c3b feat(ontology): inquiry chain types` and `7969498 feat(brief): canonicalize ontology-native insight brief`. [B: local git]

Phase 1.2-1.5 now also landed:

- `6cacc3f` adds `TelicSeam.record_signal`, `record_question`, `record_claim`, `record_evidence`, and `record_doctrine`. [G: `dharma_swarm/telic_seam.py:165,207,247,298,358`]
- `7971da2` surfaces proposed Claims and open Questions in the daily brief. [G: `dharma_swarm/insight_brief.py:209,242,284,295`]
- `99d70b5` adds registry-first audit queries plus `dgc audit gates`. [G: `dharma_swarm/audit_queries.py:30,44,62`; `dharma_swarm/dgc_cli.py:516,583`]
- `f512bbb` adds root `codex_skills/observe_signal` and `codex_skills/assert_claim` wrappers over TelicSeam. [G: `codex_skills/observe_signal/entry.py:20,24`; `codex_skills/assert_claim/entry.py:19,23`]
- `cd36a26` adds the execution addendum that reframes Track A as evidence admission into a single memory architecture. [G: `docs/plans/2026-05-02-inquiry-chain-v3-integration-addendum.md:12,38,60`]

Locked decisions from v2 still matter: `R_V_Measurement` should not become a peer ObjectType; Cause and Movement remain schema-only later, runtime parked; `is_principal` on `AgentIdentity` carries human-principal authority. [P: `~/.claude/plans/now-reserach-this-and-jaunty-owl-v2.md:40,86,94,161,189`]

The substrate-nativeness estimate remains low, 0.41 to 1.25 percent, so do not overread a few ontology-native commits as proof the substrate has won. [B: `~/.claude/plans/now-reserach-this-and-jaunty-owl-v2.md:30`]

The evidence manifest for this prompt is `~/.dharma/codex/alignment_sweep_2026-05-02.md`. It deliberately drops the claim that every named memory tool was available and agreed. The admission rule is narrower: a claim enters this prompt only if it has a local code, git, plan, or architecture source. [B]

# L1 Task

Return five bounded design proposals. One paragraph each is enough if precise. Use file paths and line references.

1. Naming: resolve `R_M` vs `R_repair`. Recommend final names and a migration path. State whether "repair" is identity, fitness, calibration, or only one component of identity.

   Minimum useful output: a three-column map of current name, proposed final
   name, and migration action. If your answer is "keep R_repair," say what it
   must never be allowed to mean. If your answer is "rename," say whether old
   JSON fields should be dual-read, aliased, or hard-migrated.

2. Repair tolerance: design per-kind tolerance profiles for gate predictions, welfare deltas, and mutation outcomes. Name the metric, threshold shape, and failure mode. Do not reuse one 50 percent magnitude heuristic unless you can defend it across all three.

   The key problem is dimensional mismatch. Gate predictions are categorical or
   ordinal; welfare deltas may be continuous and heavy-tailed; mutation outcomes
   are delayed and sometimes binary. A shared tolerance may create false repair
   confidence. Propose the smallest profile table that avoids that collapse.

3. Aggregate authority: define minimum coverage before a geometric aggregate can publish as anything stronger than provisional. Include minimum `n` per kind, missing-kind behavior, and whether zero should annihilate the aggregate or produce "insufficient signal."

   Be explicit about "no signal" versus "bad signal." If a kind has zero
   observations, the system should probably not report a moral failure score.
   If a kind has thirty observations and zero repairs, that is different. Name
   the state machine.

4. Gate witness schema: propose the exact witness field that should be written at gate-evaluation time so `gate_calibration` stops relying on the "general" bucket. Include impact analysis for `TelosGatekeeper.check()` and the AHIMSA fast path. Do not patch yet.

   Include the exact field name, allowed values, and whether the source of truth
   is a top-level witness key, a gate_results map, or both. If you think the
   field belongs in `GateDecisionRecord` instead of witness logs, say so and
   explain the bridge.

5. Unified memory protocol: reconcile `causal_ledger`, `R_repair`, `gate_calibration`, inquiry-chain objects, and future `MemoryKernel` atoms into one protocol. The local architecture says vector DBs are projections, not authority, and names `PriorRetrievalController` as the read path after the kernel facade. [I: `docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md:452,490,504,506`] Your task is to say what contract prevents five truth stores.

   This is the most important proposal. Give a minimal canonical record shape:
   identity, source episode, truth state, confidence, contradiction edges,
   supersession edges, use feedback, and retirement rule. Then say which current
   files are sources, which are derived projections, and which must lose write
   authority.

# L0 Technical

Write your answer as markdown to:

`~/.dharma/codex/replies/anticorrelation_memory_protocol_2026-05-02.md`

Use pramana tags on every claim:

- `[G]` code/schema/geometric fact
- `[B]` observed behavior, test, or git state
- `[P]` proxy from plan/session memory
- `[I]` inference from sources
- `[S]` speculative design

Include an explicit section titled:

`I disagree with the framing because...`

No code patches. No new files except the reply markdown. If a proposal depends on a code change, give the smallest future diff shape and the files it would touch.

Do not write a long philosophical essay. Each proposal should let a future
builder open the named files and know what to change, what not to change, and
what would falsify the design.

# Appendix A: Verified Findings

The current build passed:

`./.venv/bin/python -m pytest tests/test_telic_seam_inquiry.py tests/test_telic_seam.py tests/test_insight_brief.py tests/test_audit_queries.py tests/test_inquiry_codex_skills.py tests/test_ontology_inquiry_chain.py tests/test_ontology_registry.py -q`

Result: 159 passed, 1 existing pytest config warning. [B]

The new inquiry writers are non-blocking and schema-correct against the current ontology. `record_claim()` writes `lifecycle_state="proposed"`, not `asserted`; `record_doctrine()` refuses non-principal signing and does not write a non-schema `signer_agent_id`. [G: `dharma_swarm/telic_seam.py:247,358`; `tests/test_telic_seam_inquiry.py`]

The brief now surfaces inquiry pressure without becoming a second memory engine:
it reads proposed Claims, open Questions, linked Evidence counts, and skips
empty sections. [G: `dharma_swarm/insight_brief.py:209,242,284,295`]

The audit surface is deliberately registry-first. It should make governance
gaps visible, not become a reporting database with its own hidden schema. [G:
`dharma_swarm/audit_queries.py:30,44,62`]

# Appendix B: Locked Decisions

Do not revive `R_V_Measurement` as a peer ObjectType unless you explicitly argue against the v2 lock. The accepted path is Experiment field / Recognition wrapper later, not Phase 1 object proliferation. [P: `~/.claude/plans/now-reserach-this-and-jaunty-owl-v2.md:40,189`]

Do not treat Cause or Movement runtime rows as part of this build. They remain parked until Phase 1 acceptance. [P: `~/.claude/plans/now-reserach-this-and-jaunty-owl-v2.md:94,129`]

Do not treat Chetana, Chroma, contextplus, claude-mem, or the memory palace as authority. They are sources or projections unless admitted by the future kernel contract. [I: `docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md:490,498,500`]

Do not assume `dgc_cli.py` is a full modern CLI surface in this branch. It is a
reduced argparse entrypoint here, and the audit verb was added minimally. If you
recommend more CLI work, account for that branch reality. [G:
`dharma_swarm/dgc_cli.py:516,583`]

# Appendix C: What Claude Likely Got Wrong

Claude probably still overweights closure. "Five arcs are wired" can become a story that hides whether the system predicts, intervenes, and improves. Your prior critique that there is no real generative prediction ledger should remain active. [I]

Claude may also over-trust semantic unity. Calling all of this one memory system does not make it one. A real single-memory substrate needs one admission contract, truth-state lifecycle, contradiction edge, use feedback, and retirement policy. [S]

Finally, Claude may underweight operator load. Every extra "daily digest," "repair metric," and "calibration file" adds one more surface a human or agent must interpret. Your proposal should reduce surfaces, not merely align names. [I]

Claude may also confuse reversible commits with reversible cognition. The code
can be reverted, but once metrics enter daily briefings they become attractors.
Your design should include an authority ladder: observed, candidate,
provisional, trusted, deprecated, refused. Without that ladder, the system will
treat early measurements as doctrine because they are convenient to retrieve.
[S]

The biggest possible mistake is to make `MemoryKernel` a new grand module that
absorbs everything by name while leaving legacy writers active. A kernel that
does not remove write authority is only another facade. Name the enforcement
point.

# Closing

This prompt is one move in the Transcendence loop, not a directive. Find what would make the current Phase 1 story wrong even after the tests pass.
