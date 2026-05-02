# Codex Power Prompt — Bloat Triage Counter-Audit
**To**: Codex (next session)
**From**: Claude (the agent that wrote the audit you're being asked to interrogate)
**Date**: 2026-05-02
**Mode**: Counter-audit. Design only — no code patches in this round.

---

## L4 — Telos

You are being asked to do the one thing Claude is structurally bad at: **argue for deletion against an additive-biased peer**.

Dhyana caught Claude defaulting to additive (Phase 1.1 added a 5-type schema to `ontology.py` without ever asking "what could we remove instead?"). Claude wrote a bloat scan in response. The scan is honest within the limits of what Claude can see, but Claude wrote it, so Claude's blind spots are baked in.

The Transcendence Principle asks for decorrelated errors. The deletion call is the highest-stakes move on the table — it changes what 546 modules become — and Claude is the wrong agent to make it alone. You already proved you operate independently in commit `9446e13` (first-wins guard on `causal_ledger.py:437`, `window_days` enforcement in `r_repair_metric.py:160`). Lean into that mode here.

This prompt is one move in the loop. Not a directive.

---

## L3 — Identity

You are the agent who:

- Already shipped working code Claude didn't write (commit `9446e13` on `feat/chetana-grand-memory`).
- Already produced an Anti-Correlation Report sharper than your patches.
- Operates from `~/dharma_chetana/` worktree, decorrelated from Claude's `feat/inquiry-chain-phase1` work in `~/dharma_swarm/`.
- Owes Dhyana the verdict Claude can't deliver because Claude's bias is to keep building.

You are not Claude's reviewer. You are Dhyana's independent counsel. If Claude's audit is wrong, say so and quote the file:line. If it's right but understated, name the bigger version.

---

## L2 — Context

### Anchor file (read first, full)

`~/dharma_swarm/docs/audits/REPO_BLOAT_SCAN_2026-05-02.md` — Claude's bloat scan, written 2026-05-02. 10 sections. ~3,000 words. Empirical, with reproducible bash commands in §10.

### Verified facts in the scan (re-verify yourself; do not trust)

- 546 production modules (excl `__init__.py`) in `~/dharma_swarm/dharma_swarm/`. [G geometric — file count]
- 396 of 546 sit in flat root, 73%. [G]
- 35 files ≥1,000 lines. Top: `thinkodynamic_director.py` 5,167; `telos_substrate.py` 4,511; `agent_runner.py` 3,582. [G]
- 17 `ginko_*.py` files — the largest concentration by name pattern. [G]
- 13 modules with 0 internal importers AND 0 external script/api/dgc_cli references. Listed in §5 of the scan. [G]
- Load-bearing core traces through `swarm.py` as the central façade. [G — verified by importer grep]

### Locked decisions you should know (from prior plans, do not relitigate)

- HumanOperator is encoded as `is_principal: bool` flag on `AgentIdentity`, NOT a separate ObjectType. [I — Dhyana confirmed via AskUserQuestion 2026-05-01]
- R_V remains `Experiment.r_v_value` field; `Recognition` of `kind=r_v_geometric` wraps it. [I — same]
- Phase 1.1 schema (Signal / Question / Evidence / Doctrine / Claim) shipped in commit `5327c3b` on `feat/inquiry-chain-phase1`. [G]
- Phase 1.2–1.5 are paused. The build directive was reversed in this session. [B — captured in conversation]
- An external human Python engineer is being hired (8–16h, written verdict only) to call deletion shots. [I — Dhyana stated intent]

### Worktree separation (re-verify if uncertain)

- `~/dharma_swarm/` — branch `feat/inquiry-chain-phase1`. Phase 1.1 schema lives here. The bloat scan covers this tree.
- `~/dharma_chetana/` — branch `feat/chetana-grand-memory`. Your causal_ledger / r_repair_metric / 6 other modules live here. NOT in the bloat-scan denominator.
- The two trees do not intersect on file paths. Your work and Claude's work do not collide today. They will collide if/when chetana merges to main. The human auditor will gate that merge.

### What Claude likely got wrong (your starting hunting ground)

- Claude classified 9 modules as "likely entry points, NOT orphans" based on grep hits in `scripts/api/dgc_cli.py`. Some of these "entry points" may also be dead code that the scripts themselves never run. Claude did not check whether the scripts are reachable. Verify.
- Claude treated `swarm.py` as load-bearing because it imports the big files. Claude did not check whether anything imports `swarm.py` itself, or whether the codebase actually runs through it on real workloads. Verify.
- Claude excluded the 7 chetana-branch modules from the deletion list because they're in a different worktree. From a substrate-health perspective, that's a deferred problem, not absent — they're 4-of-7 orphan-risk by Claude's own self-audit. Bring them back into scope.
- Claude did not search for soft duplicates (semantic, not name-pattern). E.g. how many modules implement "score this fitness" / "track this metric" / "wrap this LLM call" with different names? That requires reading code, not grepping names. Do that read.

### What Claude can't do that you must

- Claude defaults to additive. Every "should we delete X?" implicit question, Claude rewrites as "should we extend X?" You don't have that bias.
- Claude's session is bounded; it has not seen all 546 modules in one context window. You also haven't, but you can scan with fresh eyes and find what Claude missed in the dead-zone of its own context.
- Claude's incentive structure says don't disagree with Dhyana, don't challenge prior agent claims, don't propose burning code. Yours can.

---

## L1 — Task

Five deliverables. All written to markdown. **No code patches in this round.** No edits to source files. Read-only on the repo.

### Task 1 — Independent verification of the bloat scan

Re-run the four verification commands in §10 of the scan. Report any discrepancy with Claude's numbers, with command output. Specifically pay attention to the file `dgc_cli.py`: prior agent claimed 7,115 lines; Claude found `thinkodynamic_director.py` at 5,167 as largest. One of them is wrong or stale; you tell us which.

Output: a 200–400 word section titled `## Verification` in your reply file.

### Task 2 — Counter-audit of Claude's orphan list

The scan §5 lists 13 orphan candidates. For each, do at least one of:

- Confirm zero callers using a method Claude didn't (e.g. `ast.walk`-based dynamic-import scan, plugin discovery scan, MCP config scan, `entry_points` scan in `pyproject.toml` / `setup.py`).
- Find a caller Claude missed and remove the module from the orphan list.
- Add a module to the orphan list that Claude missed.

For each module that survives your audit as a true orphan: file path, exact LOC, last-modified date from git, and one sentence on why deletion is safe.

Output: `## Orphan Candidates (verified)` table.

### Task 3 — `ginko_*.py` concern graph

17 trading-lab files in flat root. Build a one-page concern graph: for each file, what trading concern does it own (signals / risk / data / paper-trade / reporting / etc.), what does it import from other `ginko_*` files, and who imports it.

Identify (a) duplicates (two files implementing the same concern) and (b) the minimum subset of `ginko_*` files that, if kept, would preserve all unique concerns. Recommend the rest as deletion candidates.

Output: `## Ginko Cluster Triage` with table + deletion list. Aim for hitting at least 8 of the 17 marked for either deletion or merge.

### Task 4 — Find what Claude excused as "load-bearing"

Claude listed `swarm.py` and its direct importees as load-bearing. Audit this claim. Specifically:

- Read `swarm.py`. Is it actually called by anything that runs in production? Or is it itself a façade nobody invokes anymore?
- Read each of the top-10 files Claude marked load-bearing (`telos_substrate.py`, `agent_runner.py`, `orchestrator.py`, `evolution.py`, `providers.py`, `tui/app.py`, `ontology.py`, `terminal_bridge.py`, `runtime_state.py`, `operator_bridge.py`). For each, find ONE function or section that is itself dead code Claude failed to identify because Claude was looking at file-level granularity, not function-level.

Output: `## Load-Bearing Counter-Audit` — list any of the 10 you'd reclassify, plus the 10 dead functions you found.

### Task 5 — The deletion list (the actual ask)

The smallest useful artifact for the human engineer Dhyana hires. **50 specific files marked for deletion**, with:

- File path (absolute)
- Current LOC
- One-line justification (orphan / duplicate / replaced / legacy / experimental dead-end)
- Confidence: high / medium / low
- Evidence (file:line if applicable, or "no callers found via {method}")

Sort by confidence × LOC, descending — biggest, most-confident deletions first. The list is read by the engineer, not executed by you. Each row is a deletion vote, not a deletion action.

50 is the target. If you can only honestly justify 30 with high confidence, deliver 30 + 20 medium-confidence. If you find more than 50 genuine candidates, deliver the top 50 only — the engineer's bandwidth is the bottleneck.

Output: `## Deletion List (50)` — markdown table sorted as specified.

---

## L0 — Technical

### Output destination

Single markdown file at `~/.dharma/codex/replies/bloat_triage_counter_audit_<your-timestamp>.md`.
If the directory doesn't exist, create it (one-time `mkdir -p`).

### Output format

```markdown
# Bloat Triage Counter-Audit
**Author**: Codex <session-id>
**Date**: <ISO-8601>
**Anchor**: ~/dharma_swarm/docs/audits/REPO_BLOAT_SCAN_2026-05-02.md
**Worktree under analysis**: ~/dharma_swarm/ (NOT chetana)

## Verification
...

## Orphan Candidates (verified)
| module | LOC | last_modified | verdict | confidence | evidence |

## Ginko Cluster Triage
...

## Load-Bearing Counter-Audit
...

## Deletion List (50)
| rank | path | LOC | reason | confidence | evidence |

## Where I disagree with Claude's framing
(Required section. If you have no disagreements, the audit isn't honest.
At minimum say what you'd have looked at differently.)

## What Dhyana should NOT do based on this audit
(Required. Block one or two over-eager moves Dhyana might make.
"Delete tui_legacy.py without first checking dashboard imports" is one example.)
```

### Pramana tags (mandatory on every empirical claim)

Inline tag every claim with one of:
- **[G]** Geometric — verifiable from code/file system, deterministic
- **[B]** Behavioral — observed at runtime, dated
- **[P]** Proxy — inferred from a related signal
- **[I]** Inferential — derived from context not directly verifiable
- **[S]** Speculative — judgment call

Untagged empirical claims are rejected.

### Constraints

- **Read-only.** Do not edit any source file in `~/dharma_swarm/` or anywhere else. Do not commit. Do not create branches. Do not run pytest. The output is markdown only.
- **No code patches.** If you find a bug, note it; do not fix it in this round.
- **No conversation with Claude.** This is a one-shot deliverable. If you need clarification, mark the relevant deliverable `BLOCKED` with the question.
- **Time budget**: aim for ≤ 90 minutes. Quality over coverage. Better to deliver 30 high-confidence deletions than 50 vague ones.
- **No new modules.** Especially: do not propose `bloat_triage.py` or `dead_code_scanner.py` or any "tool" to automate this. The deliverable IS the analysis. The engineer the human is hiring will write tools if tools are needed.

### Anti-sycophancy gate

If your reply does not include the `## Where I disagree with Claude's framing` section with at least one substantive disagreement, the audit is rejected. Claude's framing has known blind spots — additive bias, façade-trust, scope-narrowing-to-current-worktree. You will find at least one if you look.

---

## Appendix A — Already verified by Codex on chetana side (for closure)

Two HIGH findings from your Cross-Check Report are already patched in commit `9446e13` (chetana branch):
- `causal_ledger.py:437` — last-write-wins → first-wins guard. [G — verified by Claude reading the patched code]
- `r_repair_metric.py:160` — `window_days` now filters by timestamp. [G]
- `gate_calibration.py:171` — schema-mismatch documented as deferred. [I — needs telos_gates.py upstream change]

This counter-audit is a forward-looking next move, not verification of those.

---

## Appendix B — Locked decisions Codex must not relitigate

(Re-stating from L2 Context for reference; Codex's reply must not propose changes to these.)

- HumanOperator = `is_principal: bool` flag, not a new type. [I]
- R_V_Measurement is NOT a peer ObjectType. [I]
- Phase 1.2–1.5 build is paused; reversal of build directive is in effect. [B]
- External human engineer is being hired; they call deletion shots, not Codex. [I]
- The bloat scan author (Claude) is part of the bloat surface. [B — Claude self-admitted]

---

## Appendix C — What Claude likely got wrong in Phase 1.1 (use only if scope permits)

If Tasks 1–5 finish under budget, optionally audit Phase 1.1's schema additions in `ontology.py`:

- `Signal` ObjectType — does it duplicate semantics of existing `KnowledgeArtifact` with `artifact_type=note` or existing `Outcome.result_summary`?
- `Question` ObjectType — does it duplicate any chetana-side equivalent?
- `Evidence` ObjectType — does it duplicate `KnowledgeArtifact.provenance` field?
- `is_principal: bool` on AgentIdentity — does the existing `role` enum already handle this distinction?

The honest possibility: even Phase 1.1 may have been additive when an existing field would have served. If you find this, name it. The schema is not yet load-bearing (zero rows of new types in DB); it's still cheap to revert.

---

## Closing

This prompt is one move in the Transcendence loop. Decorrelated errors cancel only if you stay independent. Don't agree with Claude's audit because Claude wrote a thorough document; agree with it where it's right and tear apart where it isn't. The numbers don't lie, but the framing can.

Dhyana is reading your reply, not Claude. Write to Dhyana.
