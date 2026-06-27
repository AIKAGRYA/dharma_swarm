# Local/Remote Total Reconciliation Report — 2026-06-22
## Executive Verdict
- **Canonical remote:** CONFIRMED — `origin` is `https://github.com/AmitabhainArunachala/dharma_swarm.git`; canonical target is `github.com/amitabhainarunachala/dharma_swarm`.
- **Main topology:** local `main` is **BEHIND** vs `origin/main`: merge-base `86418541a` dated `2026-06-18` (4 days old), `114` behind / `0` ahead. Histories are not forked.
- **Preservation risk:** **470 local-only commits**, **70 stashes**, **189 local branches without same-named origin**, **54 upstream-gone branches**, and **188 dirty/untracked working-tree entries** must be preserved before any destructive cleanup.
- **Portfolio:** origin/main has `7` active tracks; local has `11` active tracks; target union after keeping PR #662 and the five local-only tracks would have `13` active tracks, which exceeds origin/main `track_policy.max_active=10` and requires explicit governance edit or lifecycle closure.
- **Phase 3 status:** not executed. This report stops at read-only/capture and proposes the next steps for operator approval.

## Loud Local-Only Work Warning
The following categories may be the only copy of real work and must not be overwritten or discarded:
- `470` commits reachable from local branches but from no remote ref.
- `70` local stashes. These are local-only unless converted to pushed archive refs.
- Local-only active tracks absent from origin/main and PR #662: `agent-admission-semantic-commons-2026-06, cybernetics-codex-stewardship-2026-06, telos-ai-morning-refinery-2026-06, helm-worldclass-terminal-2026-06, a2a-cloud-agent-bridge-2026-06`.
- Current working tree is dirty on branch `telos-ai-seed-v0-from-sandbox` with `188` tracked/untracked/deleted entries.

## Phase 0 — Identity And Topology
### Raw Identity Commands
`git remote -v`
```text
origin	https://github.com/AmitabhainArunachala/dharma_swarm.git (fetch)
origin	https://github.com/AmitabhainArunachala/dharma_swarm.git (push)
```
`git fetch --all --prune --tags`
```text
<no output; exit 0>
```
`git merge-base main origin/main`
```text
86418541a99c265c09040b9bfc064625c6d59994
```
`git rev-list --left-right --count origin/main...main`
```text
114	0
```
### Topology Summary
- `NO_REMOTE`: 104 local branches
- `SAME_NAME_REMOTE_NOT_TRACKED`: 3 local branches
- `UPSTREAM`: 46 local branches
- `UPSTREAM_GONE`: 54 local branches
- `BEHIND`: 4 local branch surfaces
- `AHEAD`: 166 local branch surfaces
- `DIVERGED`: 32 local branch surfaces
- `IN-SYNC`: 5 local branch surfaces

No local branch with a comparable remote was found to have an empty/no merge-base fork. The disconnect is branch/stash/worktree sprawl over a valid main lineage, not a wrong-origin forked-history event.

### Branch Topology Table
| branch | remote | remote status | merge-base date | age days | behind | ahead | forked? | drift | subject |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `_rebase_tmp` | `origin/codex/toolbelt-onboarding` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(docops): correct manifest counts from docops metrics |
| `_rtmp` | `origin/devin/1779503110-staging-promote-hermes-wiring` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(ops): restrict review mark authority to operator [impact-checked] |
| `archive/trust-build-compass-20260605` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `audit/runtime-truth-2026-04-26` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(runtime): normalize executive campaign datetimes [impact-checked] |
| `backup/memory-kernel-prep-2026-05-14` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(memory): add context shadow sweep [impact-checked] |
| `backup/route-witness-main-pre-rebase-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(routing): add route witness telemetry [impact-checked] |
| `backup/route-witness-pr297-pre-rebase-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(docops): refresh route witness inventory [impact-checked] |
| `chore/agentops-base-check` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | test(governance): use active python for cli subprocesses |
| `chore/agentops-v0` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(agentops): add governed work packet runner |
| `chore/brake-stabilization` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(cleanup): preserve current audit and control maps |
| `chore/capsule-coherence-tool` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(governance): add capsule coherence report |
| `chore/command-plane-nav-trim` | `origin/chore/command-plane-nav-trim` | UPSTREAM | 2026-05-22 | 31 | 0 | 15 | NO | **AHEAD** | feat(cockpit): consume /api/manifest/command-plane via CommandPlaneTruthPanel |
| `chore/control-plane-stabilizer` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(control): restore CLI collection compatibility |
| `chore/core-four-ontology-phase3` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(ontology): add core four value metrics |
| `chore/daily-brief-discovery-agentops` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(agentops): add governed work packet runner |
| `chore/docops-integrity-v0` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(docops): add semantic codec readiness plan |
| `chore/docops-ttl-renewal-20260612` | `origin/chore/docops-ttl-renewal-20260612` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | chore(docops): re-verify assertions, renew TTL 2026-06-12 |
| `chore/governance-truth-repairs` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(governance): sharpen assurance truth signals |
| `chore/invariant-daily-insight-seam` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(telic): preserve proposal linkage for insight chain |
| `chore/kaizen-review-v0` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(kaizen): add AgentOps review report |
| `chore/kimi-claw-agentops-task` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(agentops): add governed work packet runner |
| `chore/loop1-truth-registry` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(governance): overlay current loop1 truth maps |
| `chore/memory-tail-proof` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(telic): preserve agent runner proposal linkage |
| `chore/opportunity-dispatcher-budget-fix` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(governance): route local semgrep through ca wrapper |
| `chore/opportunity-dispatcher-budget-surgeon` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | refactor(opportunity): extract dispatcher support capsules |
| `chore/phase2-governance-checkpoint` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | test(observability): isolate local trace store |
| `chore/phase2-governance-rollup` | `origin/chore/phase2-governance-rollup` | UPSTREAM | 2026-05-04 | 49 | 0 | 2 | NO | **AHEAD** | chore(agentops): add governed work packet runner |
| `chore/phase2-governance-rollup-core-four` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(ontology): add core four value metrics |
| `chore/phase2-test-verify` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(governance): route local semgrep through ca wrapper |
| `chore/semgrep-high-risk-batch` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(governance): remove high-risk command and eval sinks |
| `chore/semgrep-rule-scope` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(governance): exclude semgrep test rules from local scans |
| `chore/semgrep-triage` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(governance): route local semgrep through ca wrapper |
| `chore/state-authority-map` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(governance): route local semgrep through ca wrapper |
| `chore/telic-seam-budget-exception` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(governance): grandfather telic seam budget |
| `chore/uplift-guard-recovery` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(governance): restore uplift guard runner |
| `cleanup/action-authority-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve action authority runtime wiring [impact-checked] |
| `cleanup/agent-truth-spine-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve agent truth spine lane [impact-checked] |
| `cleanup/brake-stabilization-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve brake stabilization residue [impact-checked] |
| `cleanup/core-operating-circuit-proof-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve core operating circuit proof [impact-checked] |
| `cleanup/go-local-model-runtime-inventory-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve go local model inventory lane [impact-checked] |
| `cleanup/kaizen-review-v0-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve kaizen review human yds lane [impact-checked] |
| `cleanup/main-dirty-salvage-2026-05-12` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore: preserve dirty main work for triage |
| `cleanup/main-late-dirty-salvage-2026-05-12` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve late dirty main work |
| `cleanup/main-recurring-live-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve recurring live main residue [impact-checked] |
| `cleanup/memory-kernel-context-eval-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(memory): shadow context reads and sentinel ci [impact-checked] |
| `cleanup/mixed-quality-recovery-2026-05-10` | `origin/cleanup/mixed-quality-recovery-2026-05-10` | UPSTREAM | 2026-05-10 | 43 | 0 | 4 | NO | **AHEAD** | feat(selection): catalytic-graph parent-selection bias (spine §9 closure) [impact-checked] |
| `cleanup/module-metabolism-strategy-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(cleanup): preserve core four ontology strategy notes [impact-checked] |
| `cleanup/opportunity-dispatcher-budget-fix-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve opportunity dispatcher budget lane [impact-checked] |
| `cleanup/root-memory-context-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(memory): preserve context admission residue [impact-checked] |
| `cleanup/root-mixed-salvage-2026-05-12` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve late root residue |
| `cleanup/runtime-result-projector-salvage-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(cleanup): preserve runtime result projector lane [impact-checked] |
| `cleanup/viz-invariant-projection-2026-05-12` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(viz): project invariant measurements [impact-checked] |
| `codex/cyber-loop-closure-provider-truth-20260619` | `origin/codex/cyber-loop-closure-provider-truth-20260619` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | test: make run daemon script test repo-relative |
| `codex/exec10-lf5` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(guardian): dataclass auto-init detection — eliminates false-positive BLOCKER |
| `codex/fix-docops-autorefresh-dispatch-20260605` | `origin/codex/fix-docops-autorefresh-dispatch-20260605` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(ci): repair docops autorefresh dispatch |
| `codex/fix-docops-autorefresh-repo-arg-20260605` | `origin/codex/fix-docops-autorefresh-repo-arg-20260605` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(ci): resolve docops manual dispatch repo context |
| `codex/fix-pr-398-coherence` | `origin/perplexity-computer/reply-to-claude-four-layer-stack` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | docs: refresh docops counts for perplexity reply |
| `codex/go-idea-spark-ingest-spine-clean-20260604` | `origin/codex/go-idea-spark-ingest-spine-clean-20260604` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | chore(go-ingest): satisfy CI governance gates |
| `codex/live-ops-cockpit-v1` | `origin/codex/live-ops-cockpit-v1` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | chore(ops): satisfy live cockpit PR gates |
| `codex/live-ops-cockpit-v1-docops-fix` | `origin/codex/live-ops-cockpit-v1` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | chore(ops): fix live cockpit docops gate |
| `codex/live-ops-cockpit-v2-slice-b` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(ops): project PR queue into live cockpit |
| `codex/live-ops-cockpit-v2-slice-c` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(ops): add live ops proposal packets |
| `codex/main-review-blockers` | `origin/codex/main-review-blockers` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(security): close post-574 review blockers |
| `codex/memory-kernel-default-context-20260523` | `origin/codex/memory-kernel-default-context-20260523` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | Merge remote-tracking branch 'origin/main' into codex/memory-kernel-default-context-20260523 |
| `codex/pr388-disambig` | `origin/devin/2026-05-30-receipt-disambiguation` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | test(receipts): add pr388 merge proof |
| `codex/pr408-schema-align` | `origin/perplexity/2026-06-01-schema-alignment-gate` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(governance): distinguish stale ontology branches |
| `codex/pr409-oms-hardening` | `origin/devin/1780259643-oms-hardening` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(ontology): preserve adapter idempotency |
| `codex/pr468-docops-clean` | `origin/docs/runtime-truth-spine-plan-and-vel-rfc` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | docs(spine): resolve #468 DocOps conflicts after matrix merge |
| `codex/pr470-after-468-fix` | `origin/devin/1780551922-spine-a2a-hardening` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into #470 after spine RFC merge |
| `codex/pr470-docops-review` | `origin/devin/1780551922-spine-a2a-hardening` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | docs(spine): refresh DocOps counts after invariant tests |
| `codex/pr546-main-sync` | `origin/chore/hygiene/evidence-snapshots-to-release` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into evidence snapshot lane after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved] |
| `codex/pr558-main-sync` | `origin/governance/ws4-gate-pep` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into telos gate lane after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved] |
| `codex/pr562-main-sync` | `origin/fix/evolution-archive-honesty` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into evolution archive honesty [impact-checked] [large_diff_ack] [structural-delete-approved] |
| `codex/pr564-main-sync` | `origin/devin/honest-spine-handoff-20260611` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into honest spine handoff after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved] |
| `codex/pr574-codeql-tests` | `origin/qwen/spine-adoption` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | governance: re-render ACTIVE_TRACK managed block after main sync (gate: no drift) [impact-checked] |
| `codex/pr578-main-sync` | `origin/feat/trust-gate-scoreboard` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into trust gate scoreboard lane [impact-checked] [large_diff_ack] [structural-delete-approved] |
| `codex/pr578-main-sync2` | `origin/feat/trust-gate-scoreboard` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into trust gate scoreboard after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved] |
| `codex/pr584-main-sync` | `origin/copilot/close-duplicate-prs-and-enable-automerge` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into automerge dedupe lane [impact-checked] [large_diff_ack] [structural-delete-approved] |
| `codex/pr586-main-sync` | `origin/codex/truth-graph-v1` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | merge main into truth graph platform after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved] |
| `codex/repair-pr-392` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(guardian): refresh docops after dedup tests |
| `codex/repair-pr-399` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(track): refresh proposed cloud bridge docops |
| `codex/runtime-truth-nats-adapter-20260606` | `origin/codex/runtime-truth-nats-adapter-20260606` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | chore(governance): refresh spine metric after NATS ack fix |
| `codex/toolbelt-onboarding` | `origin/codex/toolbelt-onboarding` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | docs(ops): publish Codex toolbelt onboarding |
| `codex/truth-graph-v1` | `origin/codex/truth-graph-v1` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | feat(governance): add truth graph platform projection |
| `complexity-stress/replay-metamorphic-v1` | `origin/complexity-stress/replay-metamorphic-v1` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | Clarify replay metamorphic fixture invariant |
| `copilot/close-duplicate-prs-and-enable-automerge` | `origin/copilot/close-duplicate-prs-and-enable-automerge` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(ci): harden automerge governance lane [impact-checked] |
| `cutover/lf5-runtime-on-main-20260510-integrate-main` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(runtime): port lf5 daemon spine onto main cutover [impact-checked] [structural-delete-approved] |
| `daemon-lane-upgrade-20260616` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(daemon): versioned provenance soak candidate [impact-checked] [large-diff-ack] |
| `dashboard-lf5-operator-lane` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | lf5: Live Fire 5 results — gauntlet baseline established |
| `devin/1778037205-marathon-cleanup` | `origin/devin/1778037205-marathon-cleanup` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | docs: refresh DocOps counts (556 modules, 567 test files, 688 md files) [impact-checked] |
| `devin/1778426210-ship-revenue-wedge-report` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs: refresh revenue wedge docops counts [impact-checked] |
| `dgc-splash-art` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(tui): pipe bridge stderr to prevent double-render corruption |
| `docs/adr-008-ontology-api-grammar` | `origin/docs/adr-008-ontology-api-grammar` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | docs(adr): ADR-008 — resolve open-Q3 sibling api_name conventions (Palantir-grounded) |
| `feat/brief-to-spec-seam-2026-05-07` | `origin/feat/brief-to-spec-seam-2026-05-07` | UPSTREAM | 2026-05-07 | 46 | 0 | 1 | NO | **AHEAD** | docs(state): record post-cron verification |
| `feat/cwt-v0-collector` | `origin/feat/cwt-v0-collector` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | feat(governance): CWT v0 read-only collector + report renderer [impact-checked] |
| `feat/inquiry-chain-phase1` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(cleanup): preserve current audit and control maps |
| `feat/runtime-result-projector` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(selection): catalytic-graph parent-selection bias (spine §9 closure) [impact-checked] |
| `feat/trust-gate-scoreboard` | `origin/feat/trust-gate-scoreboard` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | chore: drop unused import (pyright) |
| `feat/world-radar-shakti-telos-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(world): preserve radar shakti telos build lane [impact-checked] |
| `feat/world-radar-shakti-telos-docs-tests-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(world): preserve zeitgeist docs test residue [impact-checked] |
| `feat/world-radar-shakti-telos-final-residue-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(world): preserve final scoring zeitgeist residue [impact-checked] |
| `feat/world-radar-shakti-telos-followup-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(world): preserve recurring signal followup [impact-checked] |
| `feat/world-radar-shakti-telos-live-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(world): preserve live recurring radar state [impact-checked] |
| `feat/world-radar-shakti-telos-residual-2026-05-13` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(world): preserve runtime residual wiring [impact-checked] |
| `fix/evolution-archive-honesty` | `origin/fix/evolution-archive-honesty` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | Merge remote-tracking branch 'origin/main' into fix/evolution-archive-honesty |
| `fix/provider-honesty-g6` | `origin/fix/provider-honesty-g6` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | providers_extended: route Ollama generate, NVIDIA NIM, Moonshot through honest extractor |
| `fix/runtime-spine-audit-followups` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | gov(runtime-receipt): sanctioned fixture quarantine excludes fixture rows from 70->75 score gate |
| `forge/dharma-reward-forge-v0` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(forge): Dharma Reward Forge v0 — close the sealed-task loop |
| `governance/parallel-lane-policy-2026-06-06` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | governance: support 1-10 active_tracks (schema v2, primary alias) |
| `governance/ws3-spine-dispatch` | `origin/governance/ws3-spine-dispatch` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | spine: route orchestrator dispatch through invoke_agent behind flag (WS3) [impact-checked] |
| `governance/ws4-gate-pep` | `origin/governance/ws4-gate-pep` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | telos: enforce gate on REVIEW-decision self-mods (WS4a) [impact-checked] |
| `helm/worldclass-20260612` | `origin/helm/worldclass-20260612` | UPSTREAM | 2026-06-12 | 10 | 0 | 57 | NO | **AHEAD** | helm(theme): Nihonga Mineral palette — bold mineral pigments on warm sumi-black |
| `lane/loop-closure-reconciled` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | loop-closure: graft Opus all-night closure harness onto Fable phase1b [docops-resync; additive manifest drift] |
| `lf5-live-fire-clean` | `origin/lf5-live-fire-clean` | UPSTREAM | 2026-04-10 | 73 | 0 | 25 | NO | **AHEAD** | fix(guardian): dataclass auto-init detection — eliminates false-positive BLOCKER |
| `loop-closure/phase1b-2026-06` | `origin/loop-closure/phase1b-2026-06` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | loop-closure: campaign RETROSPECTIVE — what the map predicted vs reality (5th criterion) |
| `loop-closure/supplychain-bronze-20260620` | `origin/loop-closure/supplychain-bronze-20260620` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | loop-closure: close thin supply chain loop [impact-checked] |
| `migration/old-machine-main` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(dashboard): Phase 1 Hokusai — indigo depths, telemetry strip, sharp panels |
| `mmm-nats-aiohttp` | `origin/mmm-nats-aiohttp` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix: install aiohttp for Mike NATS websocket |
| `mmm-nats-ca-pem` | `origin/mmm-nats-ca-pem` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix: trust private CA for Mike NATS fanout |
| `mmm-nats-mike-credentials` | `origin/mmm-nats-mike-credentials` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix: use Mike NATS credentials for backlog fanout |
| `mmm-nats-publish-deadline` | `origin/mmm-nats-publish-deadline` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix: bound Mike A2A publish deadline |
| `mmm-pin-actions` | `origin/mmm-pin-actions` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix: pin Mike workflow actions |
| `mmm-visible-backlog-router` | `origin/mmm-visible-backlog-router` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | Make Mike mentions visibly route backlog requests |
| `model-routing/nim-live-catalog-fix-20260620` | `origin/model-routing/nim-live-catalog-fix-20260620` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | model-routing: fix NVIDIA DeepSeek catalog route |
| `organ/00-floor` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(floor): unblock dispatch — bound workspace scan, satisfy think-point, non-bare pulse (H02 P1) [impact-checked] |
| `organ/02-wounds` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | fix(wounds): test fixtures no longer pollute the production witness stream (H02 P3.8) [impact-checked] |
| `pr-344-backlog` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(docops): refresh counts for PR344 rebase |
| `pr-384-backlog` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(docops): refresh counts for PR384 rebase |
| `pr-388-backlog` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(docops): refresh counts for PR388 rebase |
| `pr-406-review-20260531` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(ontology): hard-wire telos gate into execute_action (W1) |
| `pr-465-backlog` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(ops): repair live cockpit rebase gates |
| `pr-474-backlog` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(docops): refresh counts for PR474 rebase |
| `pr-495-backlog` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(mike): retrigger coherence delta |
| `qwen/spine-adoption` | `origin/qwen/spine-adoption` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | ummm, just randomly starting a new codex chat and it happened to be in qwen, if anyone sees this find out what is not clean and metabolized from qwen and next time clean it up and see if we can close the branch if it is backed up and saved on main |
| `repair/pr-325-toolbelt` | `origin/codex/toolbelt-onboarding` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | Merge remote-tracking branch 'origin/main' into repair/pr-325-toolbelt |
| `repair/pr413-docops-rebase` | `origin/perplexity-grounding/1780286494-auto-grounded` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | research(palantir-ontology): auto-grounding for PR#409 — gaps surfaced |
| `research/persistent-agents-2026-05` | `origin/research/persistent-agents-2026-05` | UPSTREAM | 2026-05-20 | 33 | 0 | 1 | NO | **AHEAD** | Add persistent agents landscape survey |
| `research/persistent-agents-deepdive-2026-05` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | Add persistent agents landscape survey |
| `review/interop-fleet-2026-05-12` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(interop): park fleet interop control surface [impact-checked] |
| `review/memory-knowledge-2026-05-12` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(memory): preserve context admission residue [impact-checked] |
| `review/root-governance-residue-2026-05-12` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | chore(governance): park root cleanup residue [impact-checked] |
| `routing-lane-source` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat(cron): add shakti executive handler |
| `rss/FU-CONDUCTOR-MALFORMED-DB` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-CONDUCTOR-UTF8` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-CQ-PASSPORT-COUNT` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-CRON-HANDLERS` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-GOV-MODULE-BUDGET` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-SEAM-KEY-CONTRACT` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-SMOKE-PROFILE-ENUM` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-SMOKE-SLEEPCYCLE-SIG` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-SPINE-CORRELATION-JOIN` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-SPINE-DB-PATH` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-STIG-SCHEMA-BACKEND` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-STIG-WRITE-PATH` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-SUBPROC-NULLBYTE` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-TOOL-LOOP-CONVERGE` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-WIRE-MINIMAX` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-WIRE-XAI` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `rss/FU-WIRE-ZAI` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | docs(operator-os): close eight-hour mission |
| `sattva/quality-ratchet-2026-06` | `origin/sattva/quality-ratchet-2026-06` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | docs(quality): reconcile draft track with landed assurance boundary |
| `spec/shakti-ginko-organ` | `origin/spec/shakti-ginko-organ` | UPSTREAM_GONE |  |  |  |  | N/A | **AHEAD** | fix(docops): register 3 new architecture docs in canonical_guard |
| `telos-ai-seed-v0-from-sandbox` | `origin/telos-ai-seed-v0-from-sandbox` | UPSTREAM | 2026-06-17 | 5 | 0 | 2 | NO | **AHEAD** | docs(adr): ADR-009 Holarchy of Standing Holons + Falsifiable Internal Coherence |
| `telosproof-v0-advisory-spike` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | TelosProof v0: advisory proof-carrying-telos gate (prove the body, not the ghost) |
| `telosproof-v1-verification-substrate` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | TelosProof v1 (increment 2): mutation-kill suite + close the aliased-import false-negative |
| `trust-build-compass` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | doctrine(governance): implement multi-track with parallel_lane_policy (v2 schema) |
| `worktree-research-integration` | `` | NO_REMOTE |  |  |  |  | N/A | **AHEAD** | feat: research-informed evolution — 4 new modules + full integration |
| `codex/governance-fitness-ci-20260620` | `origin/codex/governance-fitness-ci-20260620` | UPSTREAM | 2026-06-20 | 2 | 89 | 0 | NO | **BEHIND** | test: read daemon script from checkout |
| `main` | `origin/main` | UPSTREAM | 2026-06-18 | 4 | 114 | 0 | NO | **BEHIND** | Merge pull request #633 from AmitabhainArunachala/devin/1781768310-stop-noise-prs-automerge-botpr |
| `runtime-truth/nats-rebuild-preflight-20260618` | `origin/main` | UPSTREAM | 2026-06-18 | 4 | 114 | 0 | NO | **BEHIND** | Merge pull request #633 from AmitabhainArunachala/devin/1781768310-stop-noise-prs-automerge-botpr |
| `tam/operator-seed-v1` | `origin/main` | UPSTREAM | 2026-06-12 | 10 | 253 | 0 | NO | **BEHIND** | docs(plans): DHARMA_A2A retention proposal + outbound A2A reply packet (janitor lane) (#568) |
| `chore/action-authority-gate-spec` | `origin/main` | UPSTREAM | 2026-05-04 | 49 | 803 | 5 | NO | **DIVERGED** | fix(governance): restore local telic seam writeback |
| `chore/authority-ptr-rollup` | `origin/main` | UPSTREAM | 2026-05-04 | 49 | 798 | 8 | NO | **DIVERGED** | docs(governance): register ptr state ownership |
| `chore/current-truth-refresh` | `origin/main` | UPSTREAM | 2026-05-06 | 47 | 779 | 8 | NO | **DIVERGED** | docs(governance): refresh current repo truth |
| `chore/repo-runway-daily-brief-seam` | `origin/main` | UPSTREAM | 2026-05-07 | 46 | 754 | 1 | NO | **DIVERGED** | feat(ops): add repo cleanup pressure cockpit [structural-delete-approved] |
| `cleanup/memory-kernel-shadow-context-main-2026-05-13` | `origin/main` | UPSTREAM | 2026-05-14 | 39 | 581 | 6 | NO | **DIVERGED** | fix(memory): require strict readiness in operator smoke [impact-checked] |
| `codex/live-ops-cockpit-v1-docops-fix-mainbase` | `origin/main` | UPSTREAM | 2026-06-05 | 17 | 359 | 3 | NO | **DIVERGED** | chore(ops): fix live cockpit docops gate |
| `codex/live-ops-cockpit-v2-slice-a` | `origin/main` | UPSTREAM | 2026-06-05 | 17 | 359 | 4 | NO | **DIVERGED** | feat(ops): add live ops state authority model |
| `daemon-versioning/v0.0.1` | `origin/main` | UPSTREAM | 2026-06-12 | 10 | 197 | 1 | NO | **DIVERGED** | feat(versioning): v0.0.1 soak-testable promote-on-verified-metrics scaffold |
| `feat/a2a-correlation-spine-phase2a` | `origin/main` | UPSTREAM | 2026-05-28 | 25 | 444 | 3 | NO | **DIVERGED** | docs(a2a): correlation spine architecture anchor note |
| `feat/codex-lane-runner-2026-05-13` | `origin/main` | UPSTREAM | 2026-05-13 | 40 | 583 | 3 | NO | **DIVERGED** | fix(codex-lane): close subprocess stdin |
| `feat/governed-memory-recursive-preflight` | `origin/main` | UPSTREAM | 2026-05-14 | 39 | 581 | 7 | NO | **DIVERGED** | feat(governance): integrate recursive memory preflight proof [impact-checked] |
| `feat/ontology-telos-gate-hardwire` | `origin/main` | UPSTREAM | 2026-05-31 | 22 | 436 | 20 | NO | **DIVERGED** | docs(governance): refresh telos count stamp |
| `feat/world-radar-live-integration-2026-05-13` | `origin/main` | UPSTREAM | 2026-05-13 | 40 | 585 | 1 | NO | **DIVERGED** | feat(world): consolidate live radar shakti telos lane [impact-checked] |
| `forge-v1/tokenbroker-scoreboard-20260620` | `origin/main` | UPSTREAM | 2026-06-18 | 4 | 114 | 9 | NO | **DIVERGED** | forge-v1: REAL coordinated multi-model coding agent (PLAN->BUILD->VERIFY) |
| `holarchy/crossfalsify-20260619` | `origin/main` | UPSTREAM | 2026-06-18 | 4 | 114 | 1 | NO | **DIVERGED** | holarchy: Falsifiable Holarchy cross-falsification primitive (the acceptance test, as running code) |
| `integrate/chetana-grand-memory-2026-05-02` | `origin/integrate/chetana-grand-memory-2026-05-02` | UPSTREAM | 2026-05-02 | 51 | 2 | 13 | NO | **DIVERGED** | feat(governance): add ptr shadow metric |
| `lane/cybernetics-codex` | `origin/main` | UPSTREAM | 2026-06-12 | 10 | 197 | 1 | NO | **DIVERGED** | landing(cybernetics-codex): stewardship agent charter + audit/registration + tests |
| `lane/leftover-telos-cockpit` | `origin/main` | UPSTREAM | 2026-06-12 | 10 | 197 | 1 | NO | **DIVERGED** | landing(telos-cockpit): morning-refinery persona council + vision map + product surface |
| `lane/palantir-pilot` | `origin/main` | UPSTREAM | 2026-06-12 | 10 | 197 | 1 | NO | **DIVERGED** | landing(palantir-pilot): pilot agent + research toolchain (separate lane, no track) |
| `lane/runtime-spine-hardening` | `origin/main` | UPSTREAM | 2026-06-12 | 10 | 197 | 1 | NO | **DIVERGED** | landing(runtime-spine): runtime core + receipt/provenance + live-ops + A2A + governance evidence |
| `lane/untangle-manifest` | `origin/main` | UPSTREAM | 2026-06-12 | 10 | 197 | 1 | NO | **DIVERGED** | docs(governance): UNTANGLE_MANIFEST for cc9c05f21 segmentation |
| `merge-master/pr399-restack` | `origin/main` | UPSTREAM | 2026-06-01 | 21 | 407 | 3 | NO | **DIVERGED** | docs(governance): restack cloud bridge proposal [impact-checked] |
| `merge-master/pr411-restack` | `origin/main` | UPSTREAM | 2026-06-01 | 21 | 413 | 2 | NO | **DIVERGED** | chore(inter-agent): restack inbound status after outbound merge [impact-checked] |
| `merge-master/pr435-restack` | `origin/main` | UPSTREAM | 2026-06-02 | 20 | 403 | 4 | NO | **DIVERGED** | feat(spine): restack adapter saturation slice [impact-checked] |
| `merge-master/pr436-restack` | `origin/main` | UPSTREAM | 2026-06-02 | 20 | 401 | 4 | NO | **DIVERGED** | feat(spine): restack mapping receipt slice [impact-checked] |
| `model-routing/nim-bleeding-edge-20260618` | `origin/main` | UPSTREAM | 2026-06-18 | 4 | 141 | 1 | NO | **DIVERGED** | model-routing: fix dead NIM routes + expand to wide bleeding-edge selection [impact-checked] |
| `research/moltbook-investigation` | `origin/main` | UPSTREAM | 2026-05-18 | 35 | 580 | 2 | NO | **DIVERGED** | docs(research): round 1 follow-up — R_V calibration, schemas, corrections log |
| `review-pr393c` | `origin/main` | UPSTREAM | 2026-06-01 | 21 | 415 | 1 | NO | **DIVERGED** | chore(inter-agent): restack outbound responses after ops refresh |
| `review-pr411b` | `origin/main` | UPSTREAM | 2026-06-01 | 21 | 425 | 2 | NO | **DIVERGED** | chore(inter-agent): restack inbound status after ops refresh |
| `spine-adoption/slice-b-adapter-saturation` | `origin/main` | UPSTREAM | 2026-06-01 | 21 | 407 | 3 | NO | **DIVERGED** | chore(spine): tighten slice B runlog wording [impact-checked] |
| `spine-adoption/slice-c-mapping-receipts` | `origin/main` | UPSTREAM | 2026-06-01 | 21 | 407 | 3 | NO | **DIVERGED** | chore(spine): tighten slice C runlog wording [impact-checked] |
| `telos-ai-seed-2026-06-13` | `origin/main` | UPSTREAM | 2026-06-12 | 10 | 197 | 1 | NO | **DIVERGED** | audit(telos-ai): substrate feasibility pass v0 (concept; seed not yet written) |
| `base/brief-to-spec-seam-018ef60` | `origin/base/brief-to-spec-seam-018ef60` | SAME_NAME_REMOTE_NOT_TRACKED | 2026-05-07 | 46 | 0 | 0 | NO | **IN-SYNC** | feat(build): brief_to_spec — synthesis→action seam + pilot00 pipeline |
| `cashclaw/revenue-hydra-v1` | `origin/cashclaw/revenue-hydra-v1` | UPSTREAM | 2026-06-14 | 8 | 0 | 0 | NO | **IN-SYNC** | scan: add farm detection (0-merge repos flagged as DO NOT CLAIM) |
| `codex/pr570-orientation-fixes` | `origin/codex/pr570-orientation-fixes` | SAME_NAME_REMOTE_NOT_TRACKED | 2026-06-11 | 11 | 0 | 0 | NO | **IN-SYNC** | docs: harden north star orientation receipts |
| `devin/1778035620-wire-fractal-runtime` | `origin/devin/1778035620-wire-fractal-runtime` | SAME_NAME_REMOTE_NOT_TRACKED | 2026-05-06 | 47 | 0 | 0 | NO | **IN-SYNC** | fix(fractal): make runtime room wiring explicit [impact-checked] |
| `organ/03-seat` | `origin/organ/03-seat` | UPSTREAM | 2026-06-11 | 11 | 0 | 0 | NO | **IN-SYNC** | docs(handoffs): H02 divergence audit harvested — 6/6 claim families VERIFIED, kill test re-run green (discharges ESCALATION-6) |

## Phase 1 — Preservation Ledger
### Stash Manifest
Total stashes: **70**. None were popped, dropped, or applied.

| stash | one-line intent | files | stat | first files |
|---|---|---:|---|---|
| `stash@{0}` | On (no branch): deploy-unblock: stray governance reports 20260618T151442Z | 3 | 3 files changed, 16 insertions(+), 3 deletions(-) | `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json` |
| `stash@{1}` | On feat/trust-gate-scoreboard: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_trust_gate | 3 | 3 files changed, 3 insertions(+), 3 deletions(-) | `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json` |
| `stash@{2}` | On codex/pr578-main-sync: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_pr578_fix | 3 | 3 files changed, 3 insertions(+), 3 deletions(-) | `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json` |
| `stash@{3}` | On codex/main-review-blockers: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_main_review_blockers | 3 | 3 files changed, 3 insertions(+), 3 deletions(-) | `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json` |
| `stash@{4}` | On (no branch): compost/worktree-cull/2026-06-18 /Users/dhyana/ds_loopclose_night | 1 | 1 file changed, 1 insertion(+), 1 deletion(-) | `reports/loop_closure/2026-06-16/closure_ledger.json` |
| `stash@{5}` | On fable/loop1-trunk-delegated: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_loop1_trunk | 3 | 3 files changed, 409 insertions(+) | `.qwen/skills/provider-chain-debug/SKILL.md`, `reports/loop1/WIRING_DIAGNOSTIC_2026-06-12.md`, `reports/loop1/qwen_leg_b_transcript.log` |
| `stash@{6}` | On codex/truth-graph-v1: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_codex_truthgraph | 3 | 3 files changed, 3 insertions(+), 3 deletions(-) | `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json` |
| `stash@{7}` | On tam/build-2026-06: compost/worktree-cull/2026-06-18 /Users/dhyana/dharma_swarm_tam | 3 | 3 files changed, 3 insertions(+), 3 deletions(-) | `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json` |
| `stash@{8}` | On telos-ai-seed-v0-from-sandbox: codex-telos-ontology-wip | 2 | 2 files changed, 36 insertions(+) | `docs/ontology/semantic_aliases.yaml`, `docs/ontology/semantic_objects.yaml` |
| `stash@{9}` | On telos-ai-seed-v0-from-sandbox: what-not-to-do mandala cockpit attempt 2026-06-16 | 13 | 13 files changed, 1811 insertions(+), 65 deletions(-) | `dashboard/README.md`, `dashboard/src/app/dashboard/cockpit/page.tsx`, `dashboard/src/app/dashboard/layout.tsx`, `dashboard/src/app/globals.css`, `dashboard/src/app/layout.tsx`, `dashboard/src/components/cockpit/ActiveTrackPortfolioBoard.tsx`, `dashboard/src/components/cockpit/MandalaMissionCockpit.tsx`, `dashboard/src/components/layout/AppChrome.tsx`, `dashboard/src/lib/mandalaCockpitScene.test.ts`, `dashboard/src/lib/mandalaCockpitScene.ts`, `dashboard/src/lib/types.ts`, `dharma_swarm/operator_core/active_track_portfolio.py`, +1 more |
| `stash@{10}` | On qwen/spine-adoption: pre-merge-lane-files | 5 | 5 files changed, 61 insertions(+), 20 deletions(-) | `Makefile`, `dharma_swarm/orchestrator.py`, `docs/docops/assertions.yaml`, `scripts/governance/agent_onboard.py`, `scripts/governance/render_active_track_includes.py` |
| `stash@{11}` | On qwen/spine-adoption: docops-commit-world-dance | 58 | 58 files changed, 1771 insertions(+), 361 deletions(-) | `.gitignore`, `CLAUDE.md`, `Makefile`, `README.md`, `api/main.py`, `dharma_swarm/api_key_audit.py`, `dharma_swarm/api_keys.py`, `dharma_swarm/archive.py`, `dharma_swarm/assurance/scanner_providers.py`, `dharma_swarm/autonomous_agent.py`, `dharma_swarm/build_engine.py`, `dharma_swarm/conductors.py`, +46 more |
| `stash@{12}` | WIP on qwen/spine-adoption: aa5a8e82b feat(go-ingest): wire idea spark ingest spine (#474) | 1 | 1 file changed, 12 insertions(+), 12 deletions(-) | `docs/docops/AUTO_INVENTORY.md` |
| `stash@{13}` | On trust-build-compass: codex-preserve-hook-restored-wip-before-lak-commit | 36 | 36 files changed, 13456 insertions(+), 17 deletions(-) | `dharma_swarm/operator_core/governed_work_admission.py`, `dharma_swarm/operator_core/living_agent_kernel.py`, `dharma_swarm/operator_core/living_agent_kernel_activation.py`, `dharma_swarm/operator_core/living_agent_kernel_promotion.py`, `dharma_swarm/operator_core/living_agent_kernel_provider_worker.py`, `dharma_swarm/operator_core/living_agent_kernel_recovery.py`, `dharma_swarm/operator_core/living_agent_kernel_service.py`, `dharma_swarm/operator_core/living_agent_kernel_status.py`, `dharma_swarm/operator_core/living_agent_kernel_supervisor.py`, `dharma_swarm/operator_core/living_agent_kernel_workers.py`, `dharma_swarm/operator_core/runtime_truth.py`, `docs/docops/AUTO_INVENTORY.md`, +24 more |
| `stash@{14}` | On trust-build-compass: codex-preserve-provider-tool-call-gate-wip-2 | 36 | 36 files changed, 13455 insertions(+), 16 deletions(-) | `dharma_swarm/operator_core/governed_work_admission.py`, `dharma_swarm/operator_core/living_agent_kernel.py`, `dharma_swarm/operator_core/living_agent_kernel_activation.py`, `dharma_swarm/operator_core/living_agent_kernel_promotion.py`, `dharma_swarm/operator_core/living_agent_kernel_provider_worker.py`, `dharma_swarm/operator_core/living_agent_kernel_recovery.py`, `dharma_swarm/operator_core/living_agent_kernel_service.py`, `dharma_swarm/operator_core/living_agent_kernel_status.py`, `dharma_swarm/operator_core/living_agent_kernel_supervisor.py`, `dharma_swarm/operator_core/living_agent_kernel_workers.py`, `dharma_swarm/operator_core/runtime_truth.py`, `docs/docops/AUTO_INVENTORY.md`, +24 more |
| `stash@{15}` | On trust-build-compass: codex-preserve-provider-tool-call-gate-wip | 36 | 36 files changed, 13357 insertions(+), 16 deletions(-) | `dharma_swarm/operator_core/governed_work_admission.py`, `dharma_swarm/operator_core/living_agent_kernel.py`, `dharma_swarm/operator_core/living_agent_kernel_activation.py`, `dharma_swarm/operator_core/living_agent_kernel_promotion.py`, `dharma_swarm/operator_core/living_agent_kernel_provider_worker.py`, `dharma_swarm/operator_core/living_agent_kernel_recovery.py`, `dharma_swarm/operator_core/living_agent_kernel_service.py`, `dharma_swarm/operator_core/living_agent_kernel_status.py`, `dharma_swarm/operator_core/living_agent_kernel_supervisor.py`, `dharma_swarm/operator_core/living_agent_kernel_workers.py`, `dharma_swarm/operator_core/runtime_truth.py`, `docs/docops/AUTO_INVENTORY.md`, +24 more |
| `stash@{16}` | On trust-build-compass: codex-lak-docops-staged-metrics | 120 | 120 files changed, 14326 insertions(+), 531 deletions(-) | `Makefile`, `dharma_swarm/agent_runner.py`, `dharma_swarm/archaeology_ingestion.py`, `dharma_swarm/build_engine.py`, `dharma_swarm/cascade_domains/product.py`, `dharma_swarm/claude_hooks.py`, `dharma_swarm/cli.py`, `dharma_swarm/dataset_builder.py`, `dharma_swarm/ecosystem_bridge.py`, `dharma_swarm/ginko_evolution.py`, `dharma_swarm/harness_audit.py`, `dharma_swarm/model_hierarchy.py`, +108 more |
| `stash@{17}` | On trust-build-compass: archive trust-build-compass dirty cleanup 2026-06-05 before branch deletion | 1333 | 1333 files changed, 301275 insertions(+), 3462 deletions(-) | `.augmentignore`, `.github/workflows/codex-mention-router.yml`, `.github/workflows/merge-master-mike-backlog.yml`, `.github/workflows/tests.yml`, `.gitignore`, `.gitnexusignore`, `.semgrep/dharma-anti-slop.yml`, `.windsurf/rules/devin-nats-pr-janitor.md`, `3000`, `ACTIVE_SURFACE_MANIFEST.yaml`, `CLAUDE.md`, `CYBERNETIC_LOOP_MAP.md`, +1321 more |
| `stash@{18}` | On codex/runtime-truth-spine-e2e-20260604T143553Z: runtime-truth-spine-e2e-reconciliation-slice-after-479 | 13 | 13 files changed, 633 insertions(+), 255 deletions(-) | `CLAUDE.md`, `dharma_swarm/operator_core/__init__.py`, `dharma_swarm/operator_core/contracts.py`, `docs/docops/AUTO_INVENTORY.md`, `docs/governance/ACTIVE_TRACK.yaml`, `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `scripts/governance/agent_onboard.py`, `tests/test_agent_onboard.py`, `tests/test_operator_core_contracts.py`, +1 more |
| `stash@{19}` | On codex/runtime-truth-spine-e2e-20260604T143553Z: runtime-truth-spine-e2e-reconciliation-slice | 13 | 13 files changed, 633 insertions(+), 255 deletions(-) | `CLAUDE.md`, `dharma_swarm/operator_core/__init__.py`, `dharma_swarm/operator_core/contracts.py`, `docs/docops/AUTO_INVENTORY.md`, `docs/governance/ACTIVE_TRACK.yaml`, `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `scripts/governance/agent_onboard.py`, `tests/test_agent_onboard.py`, `tests/test_operator_core_contracts.py`, +1 more |
| `stash@{20}` | On spine-grounding/combined-production-grounding: preserve C2 approval enforcement WIP | 1 | 1 file changed, 41 insertions(+), 2 deletions(-) | `dharma_swarm/ontology.py` |
| `stash@{21}` | WIP on codex/runtime-truth-spine-v2: 2ea5a8e8 feat(runtime): add execution identity spine v2 [impact-checked] | 2 | 2 files changed, 2 insertions(+), 2 deletions(-) | `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md` |
| `stash@{22}` | On chore/command-plane-nav-trim: font-swap-parallel-isolation | 2 | 2 files changed, 31 insertions(+), 6 deletions(-) | `dashboard/src/app/globals.css`, `dashboard/src/app/layout.tsx` |
| `stash@{23}` | On chore/command-plane-nav-trim: cmdk-parallel-isolation | 22 | 22 files changed, 1761 insertions(+), 37 deletions(-) | `Makefile`, `dashboard/src/app/dashboard/layout.tsx`, `dashboard/src/components/dashboard/CommandPalette.tsx`, `dharma_swarm/operator_core/control_surface.py`, `dharma_swarm/operator_core/control_surface_goodworks_dgm.py`, `dharma_swarm/operator_core/control_surface_models.py`, `dharma_swarm/terminal_commands/__init__.py`, `dharma_swarm/tui/commands/system_commands.py`, `docs/docops/AUTO_INVENTORY.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/ops/AGENT_ONBOARDING.md`, `docs/ops/LONG_RUNNING_HARNESS.md`, +10 more |
| `stash@{24}` | On chore/command-plane-nav-trim: round8-eval-isolate-parallel-harness-edits | 2 | 2 files changed, 46 insertions(+), 10 deletions(-) | `schemas/long_running_harness.schema.json`, `scripts/runtime/long_running_harness.py` |
| `stash@{25}` | On chore/command-plane-nav-trim: round6-parallel-session-isolation | 11 | 11 files changed, 531 insertions(+), 72 deletions(-) | `Makefile`, `dashboard/src/app/dashboard/control-surface/page.tsx`, `dashboard/src/components/cockpit/EvidenceDrawer.tsx`, `dharma_swarm/subconscious.py`, `docs/ops/AGENT_ONBOARDING.md`, `docs/ops/LONG_RUNNING_HARNESS.md`, `docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md`, `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `scripts/runtime/long_running_harness.py`, `tests/test_long_running_harness.py` |
| `stash@{26}` | On chore/command-plane-nav-trim: round3-freeze | 42 | 42 files changed, 4749 insertions(+), 12 deletions(-) | `Makefile`, `dashboard/src/components/primitives/Glyph.tsx`, `dashboard/src/components/primitives/Numeral.tsx`, `dashboard/src/components/primitives/StatusBadge.tsx`, `docs/agents/AUTHORITY_LADDER_SCAFFOLD.md`, `docs/agents/CONTROL_WATCH_TOWER.md`, `docs/agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md`, `docs/agents/REGISTRATION_DESK.md`, `docs/docops/AUTO_INVENTORY.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/ops/AGENT_ONBOARDING.md`, `docs/ops/CODEX_TOOLBELT_ONBOARDING.md`, +30 more |
| `stash@{27}` | On chore/command-plane-nav-trim: round2-stash-untracked | 213 | 213 files changed, 26176 insertions(+), 168 deletions(-) | `.importlinter`, `ACTIVE_SURFACE_MANIFEST.yaml`, `CLAUDE.md`, `Makefile`, `api/chat_tools.py`, `api/main.py`, `api/routers/goodworks_dgm.py`, `api/routers/pool.py`, `dashboard/registry.json`, `dashboard/src/app/dashboard/codex-composer/page.tsx`, `dashboard/src/app/dashboard/goodworks/page.tsx`, `dashboard/src/hooks/useGoodworksDgm.ts`, +201 more |
| `stash@{28}` | On chore/command-plane-nav-trim: round2-final-2 | 88 | 88 files changed, 11315 insertions(+), 168 deletions(-) | `ACTIVE_SURFACE_MANIFEST.yaml`, `CLAUDE.md`, `Makefile`, `api/chat_tools.py`, `api/main.py`, `api/routers/goodworks_dgm.py`, `api/routers/pool.py`, `dashboard/src/app/dashboard/goodworks/page.tsx`, `dashboard/src/hooks/useGoodworksDgm.ts`, `dashboard/src/lib/api.ts`, `dashboard/src/lib/dashboardNav.ts`, `dashboard/src/lib/types.ts`, +76 more |
| `stash@{29}` | On chore/command-plane-nav-trim: round2-temp | 93 | 93 files changed, 10376 insertions(+), 161 deletions(-) | `ACTIVE_SURFACE_MANIFEST.yaml`, `CLAUDE.md`, `Makefile`, `api/chat_tools.py`, `api/main.py`, `api/routers/goodworks_dgm.py`, `api/routers/pool.py`, `dashboard/registry.json`, `dashboard/src/app/dashboard/goodworks/page.tsx`, `dashboard/src/hooks/useGoodworksDgm.ts`, `dashboard/src/lib/api.ts`, `dashboard/src/lib/dashboardNav.ts`, +81 more |
| `stash@{30}` | On chore/command-plane-nav-trim: phase1-commit-temp | 25 | 25 files changed, 683 insertions(+), 310 deletions(-) | `ACTIVE_SURFACE_MANIFEST.yaml`, `CLAUDE.md`, `Makefile`, `api/chat_tools.py`, `api/main.py`, `dashboard/src/app/globals.css`, `dashboard/src/lib/api.ts`, `dashboard/src/lib/dashboardNav.ts`, `dashboard/src/lib/motion.ts`, `dashboard/src/lib/theme.ts`, `dashboard/src/lib/types.ts`, `dharma_swarm/daemon_config.py`, +13 more |
| `stash@{31}` | WIP on research/persistent-agents-deepdive-2026-05: 39291ad3 Add persistent agents landscape survey | 69 | 69 files changed, 2780 insertions(+), 165 deletions(-) | `.env.example`, `CLAUDE.md`, `Makefile`, `api/graphql/schema.py`, `api/routers/agents.py`, `api/routers/chat.py`, `api/routers/graphql_router.py`, `api/routers/ontology.py`, `dashboard/src/lib/dashboardNav.test.ts`, `dashboard/src/lib/dashboardNav.ts`, `dharma_swarm/agent_registry.py`, `dharma_swarm/agent_runner.py`, +57 more |
| `stash@{32}` | WIP on research/persistent-agents-2026-05: aa48a1f7 research(persistent-agents): X1 Hermes + I1 dharma_swarm audit (v2 path) | 15 | 15 files changed, 318 insertions(+), 101 deletions(-) | `CLAUDE.md`, `dharma_swarm/agent_runner.py`, `dharma_swarm/config.py`, `dharma_swarm/context.py`, `dharma_swarm/stigmergy.py`, `dharma_swarm/swarm.py`, `dharma_swarm/web_search.py`, `dharma_swarm/world_model.py`, `dharma_swarm/yoga_node.py`, `tests/test_agent_runner.py`, `tests/test_config.py`, `tests/test_stigmergy.py`, +3 more |
| `stash@{33}` | On cleanup/memory-kernel-release-split-2026-05-17: codex-temp-before-gitignore-cleanup-2026-05-18 | 31 | 31 files changed, 1534 insertions(+), 45 deletions(-) | `.gitignore`, `Makefile`, `PRODUCT_SURFACE.md`, `benchmarks/README.md`, `benchmarks/fixtures/swarm_native_redteam_cases.json`, `benchmarks/swarm_native_redteam.py`, `dharma_swarm/agent_runner.py`, `dharma_swarm/config.py`, `dharma_swarm/context.py`, `dharma_swarm/operator_core/control_surface.py`, `dharma_swarm/operator_core/control_surface_governed_evolution.py`, `dharma_swarm/operator_core/control_surface_models.py`, +19 more |
| `stash@{34}` | On cleanup/recursive-evolution-lane-2026-05-16: lane-mask-rv-whitebox-artifacts-2026-05-16 | 211 | 211 files changed, 488 insertions(+) | `experiments/mask_rv_whitebox/cache/activations/024ed3ce-2128-43b7-a869-c9935f2b9096_err.npz`, `experiments/mask_rv_whitebox/cache/activations/073152B8E1F1.npz`, `experiments/mask_rv_whitebox/cache/activations/32EE3324BB48_dd.npz`, `experiments/mask_rv_whitebox/cache/activations/47a03596-4745-4b73-8128-0d4e3d7d0092_err_dd.npz`, `experiments/mask_rv_whitebox/cache/activations/5A127C872261.npz`, `experiments/mask_rv_whitebox/cache/activations/5B3E4180F890.npz`, `experiments/mask_rv_whitebox/cache/activations/5EF3DC0A4A37.npz`, `experiments/mask_rv_whitebox/cache/activations/627411C67739.npz`, `experiments/mask_rv_whitebox/cache/activations/676f535fe636d9ab52c39bfd.npz`, `experiments/mask_rv_whitebox/cache/activations/676f5360e1d0621a03333334.npz`, `experiments/mask_rv_whitebox/cache/activations/676f5362e7ddfbf5711245b9.npz`, `experiments/mask_rv_whitebox/cache/activations/676f5363f4cba8c4c95e2152.npz`, +199 more |
| `stash@{35}` | On cleanup/memory-kernel-shadow-context-main-2026-05-13: wip: freeze prod preflight report residue 2026-05-16 | 1 | 1 file changed, 200 insertions(+) | `reports/prod_preflight/latest.json` |
| `stash@{36}` | On cleanup/memory-kernel-shadow-context-main-2026-05-13: wip: freeze before memory kernel lane split 2026-05-16 | 240 | 240 files changed, 3293 insertions(+), 94 deletions(-) | `.gitignore`, `Makefile`, `dharma_swarm/evolution.py`, `dharma_swarm/memory_kernel/adapters/__init__.py`, `dharma_swarm/memory_kernel/adapters/file_snapshot.py`, `dharma_swarm/memory_kernel/adapters/read_only.py`, `dharma_swarm/memory_kernel/facade.py`, `dharma_swarm/memory_kernel/readiness.py`, `dharma_swarm/memory_kernel/surface_specs_extended.py`, `dharma_swarm/operator_core/control_surface.py`, `dharma_swarm/operator_core/control_surface_memory_readiness.py`, `dharma_swarm/operator_core/control_surface_recursive.py`, +228 more |
| `stash@{37}` | On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-memory-kernel-base-dirty-2026-05-14 | 6 | 6 files changed, 699 insertions(+), 18 deletions(-) | `dharma_swarm/memory_kernel/surfaces.py`, `dharma_swarm/memory_kernel/writers.py`, `docs/architecture/memory_kernel_current_intent.md`, `docs/architecture/memory_kernel_m4a_shadow_report_sweep.md`, `scripts/memory_writer_sentinel.py`, `tests/test_memory_writer_sentinel.py` |
| `stash@{38}` | On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-operator-control-smoke-2026-05-14 | 5 | 5 files changed, 385 insertions(+), 2 deletions(-) | `Makefile`, `dharma_swarm/operator_core/control_surface.py`, `dharma_swarm/operator_core/control_surface_memory.py`, `dharma_swarm/operator_core/control_surface_models.py`, `scripts/operator_prod_smoke.py` |
| `stash@{39}` | On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-knowledgeops-m4b-2026-05-14 | 8 | 8 files changed, 1589 insertions(+) | `dharma_swarm/knowledge_ops/__init__.py`, `dharma_swarm/knowledge_ops/cli.py`, `dharma_swarm/knowledge_ops/memory_conflict_review.py`, `dharma_swarm/knowledge_ops/memory_decision_ledger.py`, `dharma_swarm/knowledge_ops/memory_intake.py`, `dharma_swarm/knowledge_ops/memory_promotion_queue.py`, `docs/architecture/memory_kernel_m4b_knowledgeops_writer_readiness.md`, `tests/test_knowledge_ops_memory_intake.py` |
| `stash@{40}` | On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-unrelated-research-spec-cleanup-2026-05-14 | 60 | 60 files changed, 29422 insertions(+), 523 deletions(-) | `ACTIVE_SURFACE_MANIFEST.yaml`, `docs/MEGAFILE_INDEX.md`, `docs/plans/2026-04-02-specs-spec-forge-seam-plan.md`, `docs/plans/2026-04-03-autonomous-cleanup-overnight-control.md`, `docs/research/README.md`, `docs/research/RECURSIVE_SUPERINTELLIGENCE_STRATEGIC_NODE_2026-05-14.md`, `docs/telos-engine/INDEX.md`, `experiments/mask_rv_whitebox/01_load_mask.py`, `experiments/mask_rv_whitebox/02_run_inference.py`, `experiments/mask_rv_whitebox/03_compute_rv.py`, `experiments/mask_rv_whitebox/04_classifiers.py`, `experiments/mask_rv_whitebox/README.md`, +48 more |
| `stash@{41}` | On cleanup/memory-kernel-shadow-context-main-2026-05-13: memory-kernel-prep-full-dirty-snapshot-2026-05-14 | 79 | 79 files changed, 32095 insertions(+), 543 deletions(-) | `ACTIVE_SURFACE_MANIFEST.yaml`, `Makefile`, `dharma_swarm/knowledge_ops/__init__.py`, `dharma_swarm/knowledge_ops/cli.py`, `dharma_swarm/knowledge_ops/memory_conflict_review.py`, `dharma_swarm/knowledge_ops/memory_decision_ledger.py`, `dharma_swarm/knowledge_ops/memory_intake.py`, `dharma_swarm/knowledge_ops/memory_promotion_queue.py`, `dharma_swarm/memory_kernel/surfaces.py`, `dharma_swarm/memory_kernel/writers.py`, `dharma_swarm/operator_core/control_surface.py`, `dharma_swarm/operator_core/control_surface_memory.py`, +67 more |
| `stash@{42}` | On chore/phase2-governance-isolation: quarantine interop dashboard api status context after semgrep wrapper | 23 | 23 files changed, 1922 insertions(+), 75 deletions(-) | `ACTIVE_SURFACE_MANIFEST.yaml`, `AGENTS.md`, `CLAUDE.md`, `SWARM_HOT_ITEMS.md`, `api/main.py`, `api/routers/health.py`, `api/routers/interop.py`, `dashboard/src/app/dashboard/interop/page.tsx`, `dashboard/src/hooks/useInterop.ts`, `dashboard/src/lib/api.test.ts`, `dashboard/src/lib/api.ts`, `dashboard/src/lib/dashboardNav.test.ts`, +11 more |
| `stash@{43}` | On chore/phase2-governance-isolation: rogue_interop_feature | 21 | 21 files changed, 1914 insertions(+), 21 deletions(-) | `ACTIVE_SURFACE_MANIFEST.yaml`, `SWARM_HOT_ITEMS.md`, `api/main.py`, `api/routers/health.py`, `api/routers/interop.py`, `dashboard/src/app/dashboard/interop/page.tsx`, `dashboard/src/hooks/useInterop.ts`, `dashboard/src/lib/api.test.ts`, `dashboard/src/lib/api.ts`, `dashboard/src/lib/dashboardNav.test.ts`, `dashboard/src/lib/dashboardNav.ts`, `dashboard/src/lib/types.ts`, +9 more |
| `stash@{44}` | On chore/phase2-governance-isolation: quarantine interop dashboard api wip before semgrep wrapper | 22 | 22 files changed, 2042 insertions(+), 21 deletions(-) | `ACTIVE_SURFACE_MANIFEST.yaml`, `AGENTS.md`, `SWARM_HOT_ITEMS.md`, `api/main.py`, `api/routers/health.py`, `api/routers/interop.py`, `dashboard/src/app/dashboard/interop/page.tsx`, `dashboard/src/hooks/useInterop.ts`, `dashboard/src/lib/api.test.ts`, `dashboard/src/lib/api.ts`, `dashboard/src/lib/dashboardNav.test.ts`, `dashboard/src/lib/dashboardNav.ts`, +10 more |
| `stash@{45}` | On feat/inquiry-chain-phase1: cleanup-hold-2026-05-03T07:27:00Z generated-agent-context-after-memory-probe | 1 | 1 file changed, 65 insertions(+) | `AGENTS.md` |
| `stash@{46}` | On refactor/runtime-lifecycle-producers: cleanup-hold-2026-05-03T07:15:06Z holistic-sweep dharma_swarm_runtime_lifecycle_producers branch=refactor/runtime-lifecycle-producers entries=1 | 1 | 1 file changed, 104 insertions(+) | `reports/ops/PR46_REVIEW.md` |
| `stash@{47}` | On (no branch): cleanup-hold-2026-05-03T07:15:06Z holistic-sweep dharma_swarm_repo_state_now branch=detached entries=1 | 1 | 1 file changed, 160 insertions(+) | `reports/ops/REPO_STATE_NOW.md` |
| `stash@{48}` | On site/dharma-swarm-research: cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_public_site_publish branch=site/dharma-swarm-research entries=1 | 2 | 2 files changed, 454 insertions(+) | `docs/site/index.html`, `docs/site/styles.css` |
| `stash@{49}` | On (no branch): cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_model_routing_cartography branch=detached entries=2 | 2 | 2 files changed, 451 insertions(+) | `reports/cartography/03_MODEL_ROUTING.md`, `reports/ops/MODEL_ROUTING_MIGRATION_PLAN.md` |
| `stash@{50}` | On cartography/memory-substrates: cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_memory_substrates_origin_main branch=cartography/memory-substrates entries=1 | 1 | 1 file changed, 706 insertions(+) | `reports/cartography/02_MEMORY_SUBSTRATES.md` |
| `stash@{51}` | On (no branch): cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_main_stabilization_audit branch=detached entries=1 | 1 | 1 file changed, 111 insertions(+) | `reports/ops/MAIN_STABILIZATION_CHECKPOINT.md` |
| `stash@{52}` | On promote/lf5-runtime-spine: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_lf5_promotion branch=promote/lf5-runtime-spine entries=16 | 26 | 26 files changed, 5381 insertions(+) | `reports/audit/end_to_end/100_DOCS_DRIFT_REGISTER.md`, `reports/audit/end_to_end/10_RUNTIME_SPINE_MAP.md`, `reports/audit/end_to_end/20_AGENT_IDENTITY_COHERENCE.md`, `reports/audit/end_to_end/30_MODEL_ROUTING_COHERENCE.md`, `reports/audit/end_to_end/40_MEMORY_SUBSTRATE_MAP.md`, `reports/audit/end_to_end/50_GUARDIAN_OBSERVABILITY_MAP.md`, `reports/audit/end_to_end/60_API_DASHBOARD_COHERENCE.md`, `reports/audit/end_to_end/70_SHAKTI_DARWIN_LOOP_MAP.md`, `reports/audit/end_to_end/80_REPO_GOVERNANCE_MAP.md`, `reports/audit/end_to_end/90_TEST_COVERAGE_BY_LOOP.md`, `reports/audit/runtime_truth/03_MATRIX_REVIEW.md`, `reports/audit/runtime_truth/12_GOVERNANCE_BRANCH_READINESS.md`, +14 more |
| `stash@{53}` | On fix/guardian-warning-cases: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_guardian_warning_cases branch=fix/guardian-warning-cases entries=1 | 1 | 1 file changed, 154 insertions(+) | `reports/ops/PR45_REVIEW.md` |
| `stash@{54}` | On governance/tier-1-clean: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_governance_tier_1_clean branch=governance/tier-1-clean entries=1 | 1 | 1 file changed, 44 insertions(+) | `reports/ops/POST_GOVERNANCE_MERGE.md` |
| `stash@{55}` | On docs/main-stabilization-checkpoint: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_ci_unblock_pr28 branch=docs/main-stabilization-checkpoint entries=1 | 1 | 1 file changed, 98 insertions(+) | `reports/ops/MAIN_STABILIZATION_CHECKPOINT.md` |
| `stash@{56}` | On dashboard-lf5-operator-lane: cleanup-hold-2026-05-03T07:15:03Z holistic-sweep dharma_swarm_lf5_operator branch=dashboard-lf5-operator-lane entries=6 | 6 | 6 files changed, 219 insertions(+), 7 deletions(-) | `api/chat_tools.py`, `api/routers/chat.py`, `dashboard/src/app/dashboard/claude-code/page.tsx`, `dashboard/src/app/dashboard/codex/page.tsx`, `dashboard/src/lib/controlPlaneSurfaces.ts`, `dashboard/src/lib/dashboardNav.ts` |
| `stash@{57}` | On audit/runtime-truth-2026-04-26: cleanup-hold-2026-05-03T07:15:03Z holistic-sweep dharma_swarm_lf5 branch=audit/runtime-truth-2026-04-26 entries=54 | 66 | 66 files changed, 13717 insertions(+), 4 deletions(-) | `.github/pull_request_template.md`, `.github/workflows/codeql.yml`, `.github/workflows/governance.yml`, `.gitleaks.toml`, `.playwright-mcp/console-2026-04-29T16-39-54-968Z.log`, `.playwright-mcp/page-2026-04-29T16-39-55-031Z.yml`, `.playwright-mcp/page-2026-04-29T16-56-03-401Z.yml`, `.semgrep/dharma-governance.yml`, `.serena/.gitignore`, `.serena/project.yml`, `AGENTS.md`, `GUARDIAN_REPORT.md`, +54 more |
| `stash@{58}` | On (no branch): cleanup-hold-2026-05-03T07:15:02Z holistic-sweep dharma_swarm_dashboard_skill_worktree branch=detached entries=1 | 3 | 3 files changed, 559 insertions(+) | `skills/dharma-dashboard-master/01_HOLES_AND_GAPS.md`, `skills/dharma-dashboard-master/02_TOOLS_AND_ARSENAL.md`, `skills/dharma-dashboard-master/03_HIGH_VISION.md` |
| `stash@{59}` | On worktree-research-integration: cleanup-hold-2026-05-03T07:15:02Z holistic-sweep research-integration branch=worktree-research-integration entries=2 | 2 | 2 files changed, 301 insertions(+) | `tests/test_contracts.py`, `tests/test_private_access.py` |
| `stash@{60}` | On dgc-splash-art: cleanup-hold-2026-05-03T07:15:02Z holistic-sweep dgc-splash-art branch=dgc-splash-art entries=34 | 146 | 146 files changed, 2125 insertions(+), 2 deletions(-) | `.gitignore`, `CODEX_AUDIT_PROMPT.md`, `CODEX_CROSSCHECK.md`, `terminal/.dharma-terminal-state.json`, `terminal/bun_all.ansi`, `terminal/bun_braille.ansi`, `terminal/bun_halfblock.ansi`, `terminal/capture-terminal.ts`, `terminal/fuji_all.ansi`, `terminal/fuji_braille.ansi`, `terminal/fuji_half.ansi`, `terminal/fuji_timg.ansi`, +134 more |
| `stash@{61}` | On feat/chetana-grand-memory: cleanup-hold-2026-05-03T07:15:01Z holistic-sweep dharma_chetana branch=feat/chetana-grand-memory entries=9 | 9 | 9 files changed, 436 insertions(+), 2 deletions(-) | `CODEX_REVIEW_PROMPT.md`, `dharma_swarm/chetana/README.md`, `dharma_swarm/chetana/cli.py`, `dharma_swarm/chetana/governance.py`, `dharma_swarm/chetana/ingest.py`, `dharma_swarm/chetana/provenance.py`, `dharma_swarm/chetana/tests/test_governance.py`, `dharma_swarm/chetana/tests/test_ingest_promote.py`, `dharma_swarm/tui_launcher.py` |
| `stash@{62}` | On feat/inquiry-chain-phase1: cleanup-hold-2026-05-03T07:15:01Z holistic-sweep dharma_swarm branch=feat/inquiry-chain-phase1 entries=50 | 61 | 61 files changed, 6164 insertions(+), 139 deletions(-) | `.pre-commit-config.yaml`, `.semgrep/.semgrepignore`, `.semgrep/dharma-anti-slop.yml`, `ACTIVE_SURFACE_MANIFEST.yaml`, `AGENTS.md`, `CLAUDE.md`, `SWARM_HOT_ITEMS.md`, `api/main.py`, `api/routers/agent_day.py`, `api/routers/health.py`, `api/routers/interop.py`, `dashboard/src/app/dashboard/command-post/page.tsx`, +49 more |
| `stash@{63}` | On feat/inquiry-chain-phase1: WIP feat/inquiry-chain-phase1 — 30 modified + 35 untracked (deep_agent_*, agent_interop, intrinsic_rewards, dharma-judge tests, governance docs, dashboard interop) — parked 2026-05-03 by clean-up sweep | 88 | 88 files changed, 11557 insertions(+), 1070 deletions(-) | `.pre-commit-config.yaml`, `.semgrep/.semgrepignore`, `ACTIVE_SURFACE_MANIFEST.yaml`, `AGENTS.md`, `AGENT_INSTRUCTIONS.md`, `CLAUDE.md`, `GUARDIAN_REPORT.md`, `SWARM_HOT_ITEMS.md`, `api/main.py`, `api/routers/agent_day.py`, `api/routers/health.py`, `api/routers/interop.py`, +76 more |
| `stash@{64}` | On feat/inquiry-chain-phase1: cleanup-hold-2026-05-02-active-untracked-surfaces | 240 | 240 files changed, 72554 insertions(+) | `AGENTS.md`, `GUARDIAN_REPORT.md`, `api/routers/cascade_router.py`, `api/routers/catalytic.py`, `api/routers/fleet.py`, `api/routers/gates.py`, `api/routers/strange_loop.py`, `api/routers/vsm.py`, `api/runtime_cache.py`, `artifacts/severa_fggm_prototype.py`, `artifacts/severa_fggm_prototype_spec.md`, `build_queues/operator_cockpit_truth.queue.json`, +228 more |
| `stash@{65}` | On governance/tier-1-install: pre-merge checkpoint: canonical governance/tier-1-install work (82 modified + untracked) before chetana merge 2026-05-01T14:43:51Z | 579 | 579 files changed, 104731 insertions(+), 917 deletions(-) | `.agents/skills/agentdb-advanced/SKILL.md`, `.agents/skills/agentdb-learning/SKILL.md`, `.agents/skills/agentdb-memory-patterns/SKILL.md`, `.agents/skills/agentdb-optimization/SKILL.md`, `.agents/skills/agentdb-vector-search/SKILL.md`, `.agents/skills/browser/SKILL.md`, `.agents/skills/github-code-review/SKILL.md`, `.agents/skills/github-multi-repo/SKILL.md`, `.agents/skills/github-project-management/SKILL.md`, `.agents/skills/github-release-management/SKILL.md`, `.agents/skills/github-workflow-automation/SKILL.md`, `.agents/skills/gitnexus/debugging/SKILL.md`, +567 more |
| `stash@{66}` | WIP on main: 4ec9579 fix: 3 critical integration fixes — recognition, knowledge extraction, director vision | 315 | 315 files changed, 43438 insertions(+), 1 deletion(-) | `.playwright-mcp/console-2026-04-03T14-47-55-878Z.log`, `.playwright-mcp/console-2026-04-03T14-58-50-550Z.log`, `.playwright-mcp/console-2026-04-03T15-11-41-801Z.log`, `.playwright-mcp/console-2026-04-03T23-56-36-556Z.log`, `.playwright-mcp/console-2026-04-04T00-01-13-165Z.log`, `.playwright-mcp/page-2026-04-03T14-47-56-067Z.yml`, `.playwright-mcp/page-2026-04-03T14-51-51-186Z.yml`, `.playwright-mcp/page-2026-04-03T14-52-14-541Z.yml`, `.playwright-mcp/page-2026-04-03T14-52-31-294Z.yml`, `.playwright-mcp/page-2026-04-03T14-52-43-480Z.yml`, `.playwright-mcp/page-2026-04-03T14-56-47-983Z.yml`, `.playwright-mcp/page-2026-04-03T14-58-50-665Z.yml`, +303 more |
| `stash@{67}` | WIP on main: 4ec9579 fix: 3 critical integration fixes — recognition, knowledge extraction, director vision | 1 | 1 file changed, 2 insertions(+), 2 deletions(-) | `terminal/.dharma-terminal-state.json` |
| `stash@{68}` | WIP on main: 27f84e4 feat(dashboard): collapsible micrographics header — collapsed by default, saves 550px viewport | 8 | 8 files changed, 179 insertions(+), 39 deletions(-) | `dharma_swarm/agent_runner.py`, `dharma_swarm/model_hierarchy.py`, `dharma_swarm/orchestrator.py`, `dharma_swarm/terminal_bridge.py`, `dharma_swarm/tui/engine/adapters/claude.py`, `dharma_swarm/tui/model_routing.py`, `terminal/.dharma-terminal-state.json`, `tests/tui/test_model_routing.py` |
| `stash@{69}` | WIP on main: 06405c9 feat(terminal): Bun TUI cleanup + governance audit + dual-audit tool | 1 | 1 file changed, 123 insertions(+), 56 deletions(-) | `terminal/src/app.tsx` |

### Local-Only Commits
Total commits from `git log --branches --not --remotes --oneline`: **470**. Full raw list follows.

```text
11de04fb7 loop-closure: close thin supply chain loop [impact-checked]
d8bca7aab forge-v1: REAL coordinated multi-model coding agent (PLAN->BUILD->VERIFY)
b9ca47a98 forge-v1 L4: real swarm-vs-best-of-N run on live SWE-bench-Verified (Docker-graded)
88a92e2f2 forge-v1: RunPod x86 SWE-bench runbook + setup script
5d6be0f6e forge-v1 L2.5: real-model swarm arm (build_arm_from_models)
3c2511c93 forge_v1 L3: real SWE-bench-Verified verifier through official Docker harness
6a6acaaa4 forge-v1 L2: wire PoolCompletion to live provider stack (real call -> verified patch)
d314bfdb7 forge-v1: gate ship decision on paired bootstrap CI
c852fe3d5 forge-v1: all 4 layers end-to-end (offline, green) — evolution closes, swarm beats best-of-N
29dfdaf84 forge-v1: offline scoreboard harness (TokenBroker + sandboxed verifier + best-of-N) — 10 tests green
d2dd09ad5 holarchy: Falsifiable Holarchy cross-falsification primitive (the acceptance test, as running code)
cd610be3c docs(adr): ADR-009 Holarchy of Standing Holons + Falsifiable Internal Coherence
8ac5118ca model-routing: fix dead NIM routes + expand to wide bleeding-edge selection [impact-checked]
adc35ab39 chore(hygiene): gitignore loop receipts + worktree-budget + Semantic-Commons naming SSOT in CLAUDE.md
680b013c0 helm(theme): Nihonga Mineral palette — bold mineral pigments on warm sumi-black
aae03c54e helm(route): show the chat brain (Claude Opus 4.8) as the route, not codex
a3eed4649 helm(composer): expandable typing pane — grows to 3-6 lines, bottom-anchored
02f71a589 helm(navigator): aliveness — the chat agent drives the Helm by plain language
1e0ab7e4e helm(navigator): persistent chat rail — Navigator Copilot milestone 1 (layout)
25d95d49e helm(model): port the Kimi K2.6 power floor to every TUI model surface
6649fcc91 helm(tour): gate the guided tour to /tour + ^G, render it in an isolated box
a008d300e helm(model): one truthful model identity — Claude-first routing + display follows the real route
81eb62d0d helm(zen): span full terminal width — kill the right-half dead zone
8e2290afb helm(zen): Claude-Code baseline — composer pinned bottom, conversation bottom-anchored
04853456f helm: Navigator Copilot v1 increment 1 — persistent steering strip (surface only)
12793ebd5 loop-closure: graft Opus all-night closure harness onto Fable phase1b [docops-resync; additive manifest drift]
69fda66ee feat(daemon): versioned provenance soak candidate [impact-checked] [large-diff-ack]
551b88e21 gov(runtime-receipt): sanctioned fixture quarantine excludes fixture rows from 70->75 score gate
b3355e8e0 fix(orchestrator): seed mission_id so fan-out delegation_run receipts pass mission gate [impact-checked]
d23746f13 test: land replay order-invariance test + fix wall-clock census time-bomb
6c7e2b1cd docs(governance): UNTANGLE_MANIFEST for cc9c05f21 segmentation
1e6668d7c landing(runtime-spine): runtime core + receipt/provenance + live-ops + A2A + governance evidence
80f06814c landing(palantir-pilot): pilot agent + research toolchain (separate lane, no track)
b278bf4a6 landing(cybernetics-codex): stewardship agent charter + audit/registration + tests
e231fce0c landing(telos-cockpit): morning-refinery persona council + vision map + product surface
bfd09a769 feat(versioning): v0.0.1 soak-testable promote-on-verified-metrics scaffold
c540f2edf loop-closure: campaign RETROSPECTIVE — what the map predicted vs reality (5th criterion)
d17948fa9 loop-closure phase1: honest test-regression scorecard for the K2.6-floor fix
a8dcc5066 loop-closure: fix K2.6-floor test regression — update canonical-default expectations to frontier + close hierarchy drift
ab77adff7 loop-closure phase1: append 'Floor airtight' addendum (router_v1 leak closed) + regen governance evidence
14447e33e loop-closure: make K2.6 floor airtight — router_v1 tier hints >=K2.6 + register frontier literals + fix inventory guards
539fe6c33 loop-closure: routing wired E2E — continuous frontier served-truth receipts on canonical, receipt-fill climbs, orient routing-truth LIVE
c598d1dcc loop-closure: routing-truth panel in make orient + >=K2.6 floor classification test
cc962bfe1 model routing: enforce Kimi K2.6 power floor; route the >=K2.6 frontier vigorously
e90dcf78b loop-closure: provider robustness receipt (>=5 models served-truth + fallback)
86e6b0148 loop-closure: spine receipt carries actually-served provider/model (robust under routing/fallback) [impact-checked]
b2830bef4 loop-closure: add 24h freshness guard to build_loop1_closure (was LIVE off a stale receipt)
ac90c295b loop-closure Phase 2: cascade audit summary (honest per-loop LIVE/NOT-LIVE)
6239d6be0 loop-closure Phase 2: orient closure checks for loops 6,2,5,9,3,4,7,8,10,11 (honest LIVE/NOT-LIVE)
d719476ba loop-closure Phase 1b: Loop 1 E2E close receipt (canonical orient LIVE via $0 ollama dispatch; daemon adopts on merge+restart)
49ef2baba loop-closure Phase 1b: Loop 1 receipts carry real provider+model through spine + orient closure check
7217fbe1e audit(telos-ai): substrate feasibility pass v0 (concept; seed not yet written)
d87edb5d4 ummm, just randomly starting a new codex chat and it happened to be in qwen, if anyone sees this find out what is not clean and metabolized from qwen and next time clean it up and see if we can close the branch if it is backed up and saved on main
fa7f0cc8e helm proto-night: FACE-3 THE SCROLL — a reading-first manuscript face (/scroll), the wildcard design.
d04c32717 helm proto-night: FACE-2 COMMAND POST — Hokusai truecolor + de-bordered cockpit chrome (military-grade data, woodblock calm).
461e2e354 helm proto-night: FACE-1 repair — resize repaints immediately + tour probe rides the real queue path again. (1) RESIZE REPAINT SETTLE: ink 5 re-lays-out the existing tree on stdout resize but React width-derived props (zen 100-col clamp, compactShell, paneWindowSize) stayed stale until the next state event (offline = the 15s probe; live+idle unbounded) — App now bumps a viewportTick useState on process.stdout 'resize', forcing a React re-render the moment the terminal resizes; live tmux 120x40->80x24 settles <=0.5s, tour frames 08==09 both clean, resize-back clean at 0.7s; width still read at render so F-022 width-stub tests untouched. (2) tour.sh probe text 'tour probe message' matched TOUR_RE (uiIntents.ts) and was answered locally under a backend-route label that never ran — probe is now 'namaste helm probe' (no intent token); tour 02/03 again exercise the offline natural-prompt queue path ('○ queued (backend offline)' verified in canonical tour 20260613T014813). Gates: typecheck 0, 557/557, lint 0 err/19-warn budget, ratchet OK, boot_smoke OK, golden_diff OK (frames unchanged, no re-capture needed).
e2c331976 helm proto-night: FACE-1 zen-pure — the Claude Code-clean default perfected. Welcome shrinks to 2 dim lines; turn chrome collapses to ONE dim row ('… thinking · <route>' while waiting — no step counts, no ▶ flicker — '✓ <n>s · <route> · ^T details' on completion, '✖ failed' loud, '○ queued' honest); zen status pinned to 'zen · <route> · <live|offline> · F2 cockpit · /tour' with transient statusLine spam removed (durable state only); composer gains ghost placeholder + visible inverse-block cursor; zen prose clamps to ~100 cols at wide terminals (measure law). Turn duration parses both ISO and epoch-second wire timestamps. Harness retuned for the quieter zen frame: boot/pty smoke + golden_capture grep the durable offline token; 4 E2E checks updated to the new summary grammar. Gates: typecheck 0, 557/557, lint 0 err/19-warn budget, ratchet OK, boot_smoke OK, pty_smoke OK, trace_collapse + assistant_event + slash_feedback + offline_queue all OK, goldens re-captured (42) + golden_diff OK; live-verified hermetic tmux 120x40 (stub turn: response above one '✓ 1s' row) and 80x24 offline ('○ queued' row), zero garble/overflow.
2839be608 helm scenic v2: playful pixel-art Hokusai scene replaces the photo downsample (operator verdict: blur). Procedurally painted at native grid resolution — flat woodblock fields: cream sky, persimmon sun, snow-zigzag Fuji, the curling wave with spaced foam fingers, woodblock water streaks, and a small boat on the open sea. Same bulletproof half-block engine (U+2580 + truecolor, edges faded to night). scripts/print_wave.ts = standalone printer for ds wave. Goldens left to the in-flight face agent's cycle (corpus re-captured green against the joint tree).
32b17916b helm proto-night: independent verifier receipt GREEN @7b07f5491 — hello 11s free-route, memory probe pass, zero leak flags, 557/557 + typecheck 0 + boot_smoke OK; flagged trace-label-vs-answering-model mismatch (Haiku 4.5 under codex:gpt-5.4 label)
7b07f5491 helm proto-night: chat turns answer in seconds with conversation memory — intent=chat rides a lightweight no-tools completion lane (_run_chat_turn) instead of booting an agentic claude -p with the 10KB bootstrap. Lane ladder per THE ONE WAY: configured-route-if-cheap -> model_hierarchy free-first openrouter -> claude Max no-tools (--tools '' --setting-sources '' --strict-mcp-config --max-turns 1 --max-budget-usd, CLI --resume session continuity, metered-key scrub); lanes buffer events so the TS sees exactly one session lifecycle. Rolling history retain-48/send-24 in the bridge process, seeded from TS-sent messages (wire field consumed at last). ROOT-CAUSE FIX: claude child inherited the bun<->python stdio socket as stdin and hung forever awaiting EOF — adapter now spawns stdin=DEVNULL. Silent route-switch failure fixed: model.set refuses unavailable routes (ok:false + assistant ✖ event in-chat) instead of silently falling back while reporting ok:true; run_stdio survives handler crashes with explicit bridge.error. Live-verified in tmux against the real backend: hello 13-15s, codeword recall across 3 route switches, zero processes with --allowedTools */--dangerously-skip-permissions during chat turns, route flips confirmed in footer. Gates: 557/557 bun, typecheck 0, boot_smoke OK, goldens byte-identical, pytest tui 125 pass.
67eb29100 helm: receipt — scenic wave landing
0dce0fc16 helm scenic: the REAL Great Wave — ScenicStrip now renders Hokusai's actual woodblock print (public domain, 1280x883 Wikimedia scan) as half-block truecolor cells via generated asset (scripts/scenic_generate.py -> scenicArt.ts, 118/98/78-col variants, 9 rows, edges faded into night #10141C). Root cause of the confetti (design truth finding 19): the old strip was a hand-typed glyph mosaic using block-eighths/quadrants/U+224B with hand-counted alignment — font-fragile and already misaligned. New strip uses ONE universally-covered glyph (U+2580) + 24-bit color; truecolor-absent terminals degrade to a single quiet wave rule (F-176). ratchet hex allowlist extended to the generated data file (image pixels, not styling). Verified live: 9 rows, 897 unique bg / 849 unique fg colors at 120x44; goldens re-captured (2 overlay frames carry the new strip); 557/557 tests, all gates green.
989f765b6 docs(quality): reconcile draft track with landed assurance boundary
5ecb82ac9 feat(assurance): Sattva Assurance Boundary V0 — contracts, not counts, on critical surfaces
23c1684f4 fix(quality): harden ratchet fail-closed contract — crash=BROKEN, no noqa bypass, pinned ruff
5a85115cf docs(quality): demote SATTVA_STYLE to reference role; relocate cartography archive under docs/_archive
4ad0c1658 helm: receipt — operator round 3
5d97e2b2b helm operator round 3: printable-keys law (bare 1/2/3 and [ ] hotkeys removed — typing '5.1' fired sidebar commands mid-sentence, operator live hit); zen composer now content-anchored under the last message with spacer below the status line (Claude Code shape; full-height frame kept — mixed-height frames desync ink repaint, found via stash-discrimination when ^G return-to-chat broke); model-switch matcher handles short names + trailing periods ('glm 5.'), and an unmistakable-but-unmatched switch ask answers locally with the route menu instead of spawning a billed agentic backend turn. 557/557 tests, goldens re-captured, all gates green, live-verified.
154ba4420 feat(quality): seed the Sattva quality lattice — one-way ratchet organ, canon, first lifecycle promotion, F821/F811 floor at zero
45c742d34 helm: receipt — gauntlet round 1
540442739 helm gauntlet round 1: F-159 BTab reversal fixed (shift+tab ordering); unknown slash commands answer in-chat with nearest-command suggestion (no more /hlep -> Control pane detonation); NL router accepts filler words ('change models to claude opus') + change verb; 556/556 tests; live-verified. Gauntlet NOTES.md committed — top remaining felt gaps: per-turn agentic claude -p with 10KB bootstrap (F-174 + backend), silent route-switch failure, multi-line paste (F-171). ds launcher now scrubs metered Anthropic keys (Credit-balance incident root-caused: claude CLI subprocess inherited exported ANTHROPIC_API_KEY).
2a4dc8664 helm zen cluster: F-063/064/065/066/111 done, F-110 zen half — boot default is the Claude Code-grade main stage (transcript + composer + one dim status line, nothing else); plain-language UI steering via src/uiIntents.ts (open <pane> pane / switch to <model> / guided tour / layout phrases), confirmations ride the F-173 assistant-event path so the Helm answers in-conversation; /zen /cockpit /deck /tour slash commands; F2 zen<->cockpit via raw-stdin listener (ink5 blanks F-keys in useInput); cockpit chrome unchanged for non-chat panes. 554/554 tests (9 new incl. operator's exact phrases), ratchets flat, goldens re-captured deterministic, live-verified against the real bridge.
5b1312e52 helm: receipt — F-163 conductor landing line
25add18e9 helm F-163: fill law landed by conductor (operator emergency) — root layout owns exactly terminalHeight; chrome flexShrink 0; pane row flexGrow + clip-don't-squeeze wrappers (sidebar + active pane keep natural height, overflow hidden). Live root cause: real-backend telemetry inflated the layout past the terminal, scrolling header/tab bar/conversation permanently off-screen (operator flunk #2). Live-verified: 120x40 real-backend hello -> echo + real answer + collapsed trace on one stable frame. Goldens re-captured (42 corpus + 6 pre-theme full-height) per receipted sanction; golden_capture markers runtime/paneSwitcher moved above the clip line; 4 boot-hydration tests given explicit 500-row stdout stubs (assertions untouched). 545/545 tests, ratchets 4013/40/97/0, golden_diff OK, boot_smoke OK. Includes killed-batch-4-cycle residue (F-022 progress/receipt/lessons records).
8161f71e2 helm eval F-022: verified GREEN
3790dd6c0 helm F-022: compactShell <=90 regression fence — 4 app-level tests pin the compact markers (DHARMA brand, OFF label, one-line tab bar, borderless summary strip) and the 90/91 threshold edge; width lever = process.stdout.columns stub since App ignores the ink test stdout
2d5b5c61d helm: receipt — batch-3 boundary HARNESS-AMENDED line
2b19c32c2 helm: batch-3 boundary — receipt residue + mid-batch tour log (7 GREEN: F-018 F-019 F-172 F-173 F-157 F-158 F-021; F-161 RED awaits attempt 2)
e6ddd2ae3 helm eval F-021: verified GREEN
2148dbed7 helm F-021: one-line tab bar at ALL widths (attempt 2, evaluator-prescribed re-land) — implementation byte-identical to graded-green 6fd1e2478 (pills replaced by windowed single-row bar, summary in compact shell, chrome margins trimmed, offsets 17/20, scenic strip gated); fix per 09:15:40Z RED note: terminal/tests/golden/ excluded from end-of-file-fixer + pre-theme goldens committed FULL-HEIGHT 24/30/40 byte-matching raw captures; corpus (42) + pre-theme (6) re-captured per F-021 new-baseline clause
ec1c1eed2 helm eval F-021: RED — reverted
28d2bced9 Revert "helm F-021: one-line tab bar at ALL widths — bordered pills replaced by the windowed single-row bar; operator summary now renders in the compact shell (borderless 1-row strip); header+summary+composer fit one frame at 80x24/100x30/120x40 (chrome margins trimmed, label rows dropped, offsets re-derived 17/20, scenic strip gated to quiet 40-row chat); golden corpus (42) + pre-theme (6) re-captured per F-021 description's new-baseline clause"
6fd1e2478 helm F-021: one-line tab bar at ALL widths — bordered pills replaced by the windowed single-row bar; operator summary now renders in the compact shell (borderless 1-row strip); header+summary+composer fit one frame at 80x24/100x30/120x40 (chrome margins trimmed, label rows dropped, offsets re-derived 17/20, scenic strip gated to quiet 40-row chat); golden corpus (42) + pre-theme (6) re-captured per F-021 description's new-baseline clause
a668b6fad helm eval F-161: RED — reverted
289716567 Revert "helm F-161: offline panes never claim loading — bridge-down projects pending placeholders to 'no signal (backend offline)' at the display boundary; 12-pane E2E law check + registry-sweep unit tests; golden corpus re-captured (18 frames) per F-018 doctrine"
42dc1baf0 helm F-161: offline panes never claim loading — bridge-down projects pending placeholders to 'no signal (backend offline)' at the display boundary; 12-pane E2E law check + registry-sweep unit tests; golden corpus re-captured (18 frames) per F-018 doctrine
abd9700f5 helm eval F-158: verified GREEN
d3cf29e62 helm F-158: every slash command leaves a visible transcript turn — echoed command plus result, or explicit queued (backend offline)/failed status; explicit command registry + coverage test bans the silent-swallow branch
2728d0208 helm eval F-157: verified GREEN
f6a871839 helm F-157: offline prompts queue explicitly — queued (backend offline) within 2s, never perpetual running; bridge connect dispatches or fails every queued turn
04503891b helm eval F-173: verified GREEN
c91376270 helm F-173: assistant bridge event renders as the turn's response; turns that end with no response-bearing event carry an explicit ✖ no-response marker, never bare complete
ba4c7700f merge main into evidence snapshot lane after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
09954a5cf merge main into telos gate lane after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
7d2cdc6b6 merge main into honest spine handoff after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
582137c5e merge main into trust gate scoreboard after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
9ef5ecc57 helm eval F-172: verified GREEN
d85b525cd merge main into truth graph platform after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
b26d69e30 fix(ci): harden automerge governance lane [impact-checked]
115cbcf45 helm F-172: trace collapse by default — response-first turn, one ✓-summary line with ^T toggle, hex-id scrub at every expansion state
5b273a562 merge main into ws4 gate pep lane [impact-checked] [large_diff_ack] [structural-delete-approved]
e3bdf898a merge main into evidence snapshot release lane [impact-checked] [large_diff_ack] [structural-delete-approved]
5b94404be merge main into truth graph platform lane [impact-checked] [large_diff_ack] [structural-delete-approved]
a14085182 helm eval F-019: verified GREEN
1b843a3f4 merge main into trust gate scoreboard lane [impact-checked] [large_diff_ack] [structural-delete-approved]
06bc54e73 merge main into honest spine handoff lane [impact-checked] [large_diff_ack] [structural-delete-approved]
ab49f6dc0 merge main into automerge dedupe lane [impact-checked] [large_diff_ack] [structural-delete-approved]
c5b340ee6 helm F-019: truecolor preflight gate — 3-link chain check (pane COLORTERM, tmux RGB features, 38;2 capture survival), exit 1 names the broken link
7893937e3 fix(security): close post-574 review blockers
c1c4b4bf7 merge main into evolution archive honesty [impact-checked] [large_diff_ack] [structural-delete-approved]
d7d9bff54 helm eval F-018: verified GREEN
78c93cc3a helm F-018: golden-diff checker — fresh temp-dir capture vs committed corpus, exit 1 names drifted frames + approval doctrine
36380c926 Merge remote-tracking branch 'origin/main' into codex/truth-graph-v1
6d1c43b96 helm: batch-2 boundary amendment — F-171..F-176 from operator flunk verdict + felt-experience re-plan
1c0a25a39 feat(governance): add truth graph platform projection
07516bea3 merge: resolve conflicts with origin/main
192ae3df2 chore(docops): resolve recurring doc count merge conflicts
e8335af4e automerge: auto-enroll bot/automated PRs; pr-dedupe: collapse draft duplicates
dfcc22a56 helm F-017: baseline golden corpus committed — 42 frames (14 surfaces x 3 sizes) under tests/golden/, second capture run diffs clean
9ce78e0ec helm eval F-016: verified GREEN
99af4d2ab helm F-016: golden-frame capture script — 14 offline surfaces x 3 sizes = 42 deterministic frames via hermetic tmux walk, GOLDEN_OUT_DIR override
85aee5f1a chore: merge origin/main after #561 — regen DocOps counters [impact-checked]
7d84d8c1c chore: merge origin/main after #561 — regen DocOps counters [impact-checked]
026e34253 helm eval F-013: verified GREEN
6e692ec25 helm F-013: ESLint flat config for src+tests via bun run lint — 0 errors, 19-warning legacy budget enforced by --max-warnings
8aa23b4f9 ci(pr-flow): automerge lane, duplicate-PR dedupe, reviewer-gate fix, merge-queue readiness
3941d39cd merge: main into honest-spine-handoff — regen DocOps counts + manifest md-count row sync
f8fb428bc Merge remote-tracking branch 'origin/main' into fix/evolution-archive-honesty
7e823c7f6 chore: drop unused import (pyright)
605e40654 governance(trust-gate): NORTH_STAR §8 scoreboard — measured conditions in onboard + JSON
4c65f017e chore(docops): re-verify assertions, renew TTL 2026-06-12
727564b5b merge: main into ws4-gate-pep — regen docops counts
bbbf31ed6 merge: main into honest-spine-handoff — regen docops counts
0ace8edb7 chore(docops): resolve merge conflicts with main — refresh counts [impact-checked]
2d7cb0cde chore(docops): resolve merge conflicts with main — refresh counts [impact-checked]
a0ba9853e chore(docops): resolve merge conflicts with main — refresh counts [impact-checked]
67b430d04 merge main into devin/honest-spine-handoff-20260611; refresh DocOps counts
4c1b662e6 chore(docops): auto-refresh count-sensitive sections
c179e57bd chore: merge origin/main into fix/evolution-archive-honesty — resolve AUTO_INVENTORY conflict
5394194b7 fleet: add Devin honest-spine handoff packet
a9b8fc957 fix(evolution): honest archive status, real gates_passed, lineage parent_id [impact-checked]
8e086e092 providers_extended: route Ollama generate, NVIDIA NIM, Moonshot through honest extractor
fc82294e3 providers: close Loop-1 content-drop on 7 sibling providers + NVIDIA NIM + providers_extended [impact-checked]
5d333431e telos: enforce gate on REVIEW-decision self-mods (WS4a) [impact-checked]
b930a9578 spine: route orchestrator dispatch through invoke_agent behind flag (WS3) [impact-checked]
d8851167f chore(hygiene): move 17MB semantic-graph evidence to release artifacts (draft)
a3ea1ee9a doctrine(governance): implement multi-track with parallel_lane_policy (v2 schema)
3ff3d44b4 governance: support 1-10 active_tracks (schema v2, primary alias)
758fd5fc8 governance: preserve codex #1 parallel-lane-policy + multi-lane onboarding
cee160f24 chore(governance): refresh spine metric after NATS ack fix
4b86b8aef fix(a2a): persist NATS consume ack intent before broker ack
96d942bb3 chore(governance): refresh spine adoption receipt
25510113e feat(a2a): add runtime-truth NATS transport
c33d8758b chore(docops): refresh counts for PR474 rebase
5e001e996 chore(go-ingest): satisfy CI governance gates
fbdf59544 docs(go-ingest): add idea spark integration spec
ea108c4bd test(go-ingest): cover ingest spine receipts and transport
2abf817c1 feat(go-ingest): wire receipt-first ingest spine
489f51ad8 chore(mike): retrigger coherence delta
2762e4fb4 docs(mike): use canonical backlog mention
bfd261a65 fix merge master mike backlog defaults
141337bbf plan merge master mike defaults
8ea05b1f9 chore(ops): repair live cockpit rebase gates
c8e7b5cc2 chore(ops): satisfy live cockpit PR gates
0ac4b2bca feat(ops): add read-only live ops cockpit
807040cc0 chore(docops): refresh counts for PR388 rebase
b6e522e8a docs(receipts): clarify closure receipt behavior change
af22825dd PR-H1: disambiguate ClosureEvidenceReceipt from spine EvidenceReceipt
9255d6bcd ci: retrigger with [impact-checked] in PR body
3f0497add chore(docops): refresh counts for PR384 rebase
75f67ac46 ci: retrigger with [impact-checked] in PR body
88707455d PR-H2: manifest_check enforces ACTIVE_SURFACE_MANIFEST <-> repo reality
2076897a7 chore(docops): refresh counts for PR344 rebase
812bd9823 chore: remove accidental package-lock.json
774bdaa05 style: remove 9 redundant blank lines from orchestrator.py to fit module-line-budget
d9b03271b refactor(memory): split default context helpers [impact-checked]
9b58aa3b0 feat(memory): default context through memory kernel [impact-checked]
6fecf9624 fix(ci): resolve docops manual dispatch repo context
a6561b3f6 fix(ci): repair docops autorefresh dispatch
11f68953b Make Mike mentions visibly route backlog requests
eb6d8d883 fix(ops): restrict review mark authority to operator [impact-checked]
0b827cbde fix(ops): trust-bind review marks and cron roots [impact-checked]
9e75e221d fix(ops): bind review marks to atom content [impact-checked]
41c4da68c fix(ops): externalize staging review authority [impact-checked]
b5a16aa5f fix(ops): keep staging dry-run non-mutating [impact-checked]
d804f92e4 fix(ops): require explicit hermes queue capability [impact-checked]
1661d9a73 fix(ops): scope cron commands and trusted promotion [impact-checked]
5c4703864 fix(ops): make hermes queue claims failure-atomic [impact-checked]
e14714326 fix(ops): harden staging promotion and hermes queue polling [impact-checked]
3a942db4c fix(cron): replace shell redirect with --output flag in provider_credit_check
a5c9cd715 fix(security): avoid dry-run path disclosure
fa88e4437 fix(security): use shlex.split instead of shell=True in cron shell handler
0b4833183 fix(cron): add shell handler + fix schedule format + fix NameError edge case
ec4612847 fix(governance): add operational scripts to semgrep dharma-write allowlist
8ddab10fb feat(ops): recreate consume_review_marks.py + Hermes heartbeat poll + provider credit check
1d2049d3c feat(ops): add live ops proposal packets
8c5c27bb4 chore(ops): fix live cockpit docops gate
ab3fe2006 fix: use Mike NATS credentials for backlog fanout
2eb6133d8 fix: trust private CA for Mike NATS fanout
eb9d8fa81 fix: install aiohttp for Mike NATS websocket
a32127ab7 fix: bound Mike A2A publish deadline
fbc3a4e11 fix: pin Mike workflow actions
b1cd7076b research(palantir-ontology): auto-grounding for PR#409 — gaps surfaced
a2a92a246 merge main into #470 after spine RFC merge
7a19c7c3e docs(spine): resolve #468 DocOps conflicts after matrix merge
b92c72c14 docs(docops): refresh counts after rebase onto main
d89399f31 test(spine): fold #473 persistence invariant into #470 (tests-only)
d8750b246 docs: remove duplicate VEL RFC from #470; #468 owns the canonical RFC
2d9bbb58f docs(rfc): remove EvidenceReceipt->RuntimeReceipt bridge language (no second writer)
bfe72455e docs(rfc): align receipt persistence language to Option C
bdcbdd919 spine(slice-1.1): add bypass report and classify all A2A dispatch paths
768d825ea docops: register RFC in canonical guard registered list
45d3949c0 docops: update manifest counts and verified_at for adoption slice
0fe69fc3d chore(go-ingest): satisfy CI governance gates
dd252d79e docs(go-ingest): add idea spark integration spec
acea1614c test(go-ingest): cover ingest spine receipts and transport
79b184028 feat(go-ingest): wire receipt-first ingest spine
043c27037 docs(spine): refresh DocOps counts after invariant tests
e3d557ad7 test(spine): fold #473 persistence invariant into #470 (tests-only)
d3a6b0ee1 docs(docops): refresh markdown counts after VEL RFC removal
5e1980adb docs: remove duplicate VEL RFC from #470; #468 owns the canonical RFC
c85dbe3d6 docs(rfc): remove EvidenceReceipt->RuntimeReceipt bridge language (no second writer)
9eac0e639 docs(rfc): align receipt persistence language to Option C
03c077ece chore(ops): satisfy live cockpit PR gates
2cf01f8b8 feat(ops): add read-only live ops cockpit
31f0b8d1a fix(docops): correct manifest counts from docops metrics
8a25e5891 fix(docops): refresh counts after rebase onto main
553adfdc9 fix(docops): register ops onboarding docs in canonical guard + ownership map
d51d27d25 docs(ops): publish Codex toolbelt onboarding
b122f276c feat(spine): restack mapping receipt slice [impact-checked]
0e2ed53b3 feat(spine): restack adapter saturation slice [impact-checked]
6c793fabd chore(spine): tighten slice B runlog wording [impact-checked]
71120f9f4 chore(spine): tighten slice C runlog wording [impact-checked]
da98a4f55 chore(spine): record slice B runlog [impact-checked]
105b77b0c chore(spine): record slice C runlog [impact-checked]
5d5711b3c docs(governance): restack cloud bridge proposal [impact-checked]
816a10181 feat(spine): saturate runtime boundary adapters [impact-checked]
33faa19c3 feat(spine): add runtime identity mapping receipts [impact-checked]
aeabeec3f chore(inter-agent): restack inbound status after outbound merge [impact-checked]
11647bcc5 chore(inter-agent): restack outbound responses after ops refresh
ff8cd9e36 chore(inter-agent): restack inbound status after ops refresh
6da5a23fc chore(inter-agent): inbound check — ACK durable-delivery fix, RFC #407, operator directive (devin-roaming-2987d222)
cb2c80867 chore(inter-agent): inbound check — ACK durable-delivery fix, RFC #407, operator directive (devin-roaming-2987d222)
f24a2adf3 test(receipts): add pr388 merge proof
003aa8860 docs(receipts): clarify closure receipt behavior change
598f05643 fix(governance): distinguish stale ontology branches
b91617440 fix(governance): fail closed on ontology baseline gaps
03b282c3e fix(governance): close alignment gate overclaims
9c6f2a27b fix(governance): align schema gate with OMS
81de4e556 Merge remote-tracking branch 'origin/main' into codex/pr408-schema-align
0f2525880 fix(ontology): preserve adapter idempotency
9cf5188d3 fix(ontology): enforce api name grammar
a443ae7fb fix(ontology): freeze promoted api names
c4e3e6b0f fix(ontology): enforce api_name uniqueness
a06e0021c merge: resolve conflicts with main — sync docops counts [impact-checked]
008334e15 merge: resolve conflicts with main — sync docops counts [impact-checked]
5efbc6fd8 merge: resolve conflicts with main — sync docops counts [impact-checked]
845e3a5f0 docs(agents): update devin-roaming protocols — NATS as primary channel
ec4b4fb39 docs(adr): ADR-008 — resolve open-Q3 sibling api_name conventions (Palantir-grounded)
3b57eb550 fix(ontology): drop .vN suffix from api_names per ADR-008 ratified grammar
2e11a2549 docs(adr): ADR-008 — resolve open-Q1 api_name mutability via #413 Palantir grounding
91ae3ea00 fix(docops): soften reserved authority terms in ADR-008 + regen auto-inventory
4d38c0163 docs(adr): ADR-008 ontology api_name grammar + status-lifecycle + SEMVER [PROPOSED]
6aaecf8ea fix(ontology): rebase api_name grammar to PascalCase per operator decision
003c4b563 feat(ontology): OMS hardening — TypeStatus lifecycle, api_name, uniqueness guard
a39ffebbd feat(governance): schema-alignment gate (KARMA) + typed-proposal envelope
236006e54 feat(forge): Dharma Reward Forge v0 — close the sealed-task loop
236e9e8ef fix(guardian): refresh docops after dedup tests
a93452514 fix(guardian): bulletproof dedup — open issues + open PRs + circuit breaker
066157dd9 docs(track): refresh proposed cloud bridge docops
ffebfa285 propose(track): perplexity-a2a-bus-bridge-2026-06 — cloud agents onto the NATS substrate
a39fde863 docs: refresh docops counts for perplexity reply
f9fe7a955 chore(inter-agent): perplexity → claude reply — endorse (b) land main, name (c) revenue track, five-layer stack
cee7e88e6 PR-H1: disambiguate ClosureEvidenceReceipt from spine EvidenceReceipt
a8929954a PR-H2: manifest_check enforces ACTIVE_SURFACE_MANIFEST <-> repo reality
0b0cd8b9a Merge remote-tracking branch 'origin/main' into codex/memory-kernel-default-context-20260523
847ccc584 Merge remote-tracking branch 'origin/main' into codex/memory-kernel-default-context-20260523
563511a56 refactor(memory): split default context helpers [impact-checked]
548123e10 Merge remote-tracking branch 'origin/main' into repair/pr-325-toolbelt
f12cd309b Merge remote-tracking branch 'origin/main' into codex/memory-kernel-default-context-20260523
35bbed303 feat(memory): default context through memory kernel [impact-checked]
1e44d7e04 docs: refresh DocOps counts after rebase onto main
740ed0df3 fix(docops): register ops onboarding docs in canonical guard + ownership map
866e02c03 docs(ops): publish Codex toolbelt onboarding
8fc17f2bc docs(ops): publish Codex toolbelt onboarding
242b67ce2 feat(governance): CWT v0 read-only collector + report renderer [impact-checked]
39291ad3d Add persistent agents landscape survey
22951df4b fix(docops): register 3 new architecture docs in canonical_guard
60e9cea8f docs(architecture): SHAKTI_GINKO organ + venture-cell lifecycle + BI noticers + ADR-006
2b6c3776a docs(research): round 1 follow-up — R_V calibration, schemas, corrections log
01efb8a04 docs(research): moltbook → SAB v2 investigation (7 lanes + synthesis)
8c2629ad4 fix(codex-lane): close subprocess stdin
b14bea571 feat(memory): add context shadow sweep [impact-checked]
62eb5aedf fix(codex-lane): pass exec prompt as argument
ea7b62c4d feat(memory): land memory kernel shadow context lane [impact-checked]
d5c2de364 feat(codex): add durable lane runner [impact-checked]
71ca01d72 feat(memory): shadow context reads and sentinel ci [impact-checked]
7b2c08f9d docs(docops): refresh route witness inventory [impact-checked]
162978c9d fix(memory): keep context eval outputs off memory surfaces [impact-checked]
f70028f85 feat(routing): add route witness telemetry [impact-checked]
f1e28af1d chore(memory): preserve context parity lane [impact-checked]
1ff15b98d feat(world): consolidate live radar shakti telos lane [impact-checked]
0dd5c3ff9 chore(memory): preserve context eval lane [impact-checked]
9848011cf chore(cleanup): preserve recurring live main residue [impact-checked]
4666be110 chore(cleanup): preserve runtime result projector lane [impact-checked]
9919a1f4f chore(cleanup): preserve go local model inventory lane [impact-checked]
64f86b4bd chore(cleanup): preserve agent truth spine lane [impact-checked]
be2571eae chore(cleanup): preserve kaizen review human yds lane [impact-checked]
e28a4bbd2 docs(cleanup): preserve core four ontology strategy notes [impact-checked]
ac21e6fae chore(cleanup): preserve core operating circuit proof [impact-checked]
2593169b9 chore(cleanup): preserve opportunity dispatcher budget lane [impact-checked]
1976329e1 chore(cleanup): preserve brake stabilization residue [impact-checked]
b913b957a feat(world): preserve final scoring zeitgeist residue [impact-checked]
b6e0342e0 feat(world): preserve live recurring radar state [impact-checked]
4c4eeb01c docs(world): preserve zeitgeist docs test residue [impact-checked]
86d1c0330 feat(world): preserve runtime residual wiring [impact-checked]
0200888a4 feat(world): preserve recurring signal followup [impact-checked]
afc962e22 chore(cleanup): preserve action authority runtime wiring [impact-checked]
479528df5 chore(memory): preserve context admission residue [impact-checked]
2427abe0f chore(memory): preserve context admission residue [impact-checked]
caf59efc2 feat(routing): add route witness telemetry [impact-checked]
be5ef013e feat(world): preserve radar shakti telos build lane [impact-checked]
77aba9243 chore(cleanup): preserve late dirty main work
8a083dcd2 chore(cleanup): preserve late root residue
af374d108 chore(governance): park root cleanup residue [impact-checked]
58e809eef chore(interop): park fleet interop control surface [impact-checked]
b04ee3072 chore(memory): park memory kernel knowledge ops [impact-checked]
3d0868587 feat(viz): project invariant measurements [impact-checked]
55f77d0d3 chore(cleanup): preserve root mixed recovery pile
49248cae1 chore: preserve dirty main work for triage
e447becf2 docs: refresh revenue wedge docops counts [impact-checked]
e9cb336d6 refactor(revenue): place wedge pipeline inside revenue organ [impact-checked]
8e113c6d5 feat: Revenue Wedge pipeline — ship first real intelligence report
c5f138117 docs: refresh DocOps counts (556 modules, 567 test files, 688 md files) [impact-checked]
fb15f9ee8 fix: shakti warrant guard, attractor hardening, MM-07 cadence [impact-checked]
60666c387 fix(runtime): normalize executive campaign datetimes [impact-checked]
b735fc830 fix(ontology): add fail-closed action gateway [impact-checked]
1332abdd8 fix(runtime): suppress recurring provider and campaign noise [impact-checked]
300801729 fix(gates): make phase5 hardening live in lf5 [impact-checked]
2ab4590c9 chore(runtime): preserve system-map zeitgeist work [impact-checked]
529f1f8b1 fix(pulse): raise daily limit via env [impact-checked]
e9730ec06 fix(runtime): restore task contract modules [impact-checked]
8b46bc0ab fix(daemon): ignore pre-commit false positives [impact-checked]
be40bba03 fix(conductor): defer register() to prevent boot hang [impact-checked]
bb64f2dcc feat(ops): add repo cleanup pressure cockpit [structural-delete-approved]
ec74ee0c6 docs(governance): refresh current repo truth
2fd647f66 fix(governance): exclude semgrep test rules from local scans
9dfdb1f23 docs(docops): add semantic codec readiness plan
67c821770 chore(docops): add local report target
2722fb1a2 docs(docops): add review routing checklist
eea1a7b23 ci(docops): add documentation integrity workflow
683dc18a5 chore(docops): add integrity reports and hook
60caa504c feat(docops): add documentation integrity checks
b329e1abe docs(governance): overlay current loop1 truth maps
8dcf1789f test(brief): pin canonical daily insight surface
fb862508e test(routing): inventory shared router bypasses
a6ecddeda chore(governance): weave loop1 substrate seams
73b7dac44 test(loop1): align mismatch registry with bootstrap truth
93132013f docs(docops): add semantic codec readiness plan
09efe94fd chore(docops): add local report target
949eb618a docs(docops): add review routing checklist
afbdb0cef ci(docops): add documentation integrity workflow
ba6b08b4a chore(docops): add integrity reports and hook
c84671fad feat(docops): add documentation integrity checks
f01b79851 chore(kaizen): add AgentOps review report
25a02e555 docs(governance): register ptr state ownership
12162b16d test(governance): keep ptr integration standalone on main
e0ad2613f fix(governance): restore local telic seam writeback
76b7fc635 feat(governance): add action authority gate contracts
eea31d04d docs(governance): harden action authority rollout
da4bcdd7a docs(governance): bind ptr to action authority evidence
3329118a5 docs(governance): specify action authority gate rollout
2d3e907eb feat(governance): add ptr shadow metric
32e3eb224 fix(governance): restore local telic seam writeback
4d8e083d3 feat(governance): add action authority gate contracts
722e172ac docs(governance): harden action authority rollout
b0b562244 docs(governance): bind ptr to action authority evidence
c509d4e8e feat(governance): add ptr shadow metric
a36b445b2 chore(agentops): add governed work packet runner
2049e513c docs(governance): specify action authority gate rollout
0ba34f6b9 test(observability): isolate local trace store
6e2bdc91a chore(governance): add shakti substrate baseline contracts
74d14cba1 feat(ontology): add core four value metrics
5339d5091 feat(ontology): add core four value metrics
3daaee673 fix(observability): record agent runner usage tokens
d22d3b960 feat(brief): normalize llm burn spans
f9040f3c4 feat(brief): include trace burn signals
4b07e9233 feat(brief): add daily operating brief
ce1227cc1 feat(governance): add agentops work packet runner
1f97b446a fix(governance): restore uplift guard runner
fba32965d fix(governance): remove high-risk command and eval sinks
5aa592bb6 fix(governance): exclude semgrep test rules from local scans
cc135f624 chore(governance): add capsule coherence report
c71db6e74 chore(governance): grandfather telic seam budget
5dd1dfb5d fix(telic): preserve proposal linkage for insight chain
cd71d5d1a refactor(opportunity): extract dispatcher support capsules
d514f6ae1 fix(control): restore CLI collection compatibility
219d6304f chore(docs): land GitNexus integration boilerplate
3e0d126d1 docs(governance): document membrane state-dir owners + extend semgrep allowlist
de75ca2ad fix(chetana): hook lifecycle hardening (atexit, lock, multi-worker)
768972a47 fix(chetana): tie default runtime emission to master canary flag
0b64b27c5 fix(memory): gate retrieval effect logger default path on canary
53c4bc9c5 fix(memory): honest gate records + actual retrieval policy filtering
1433e1e93 feat(memory): add retrieval policy telemetry
e1c637a21 feat(chetana): emit promoted atoms into runtime memory
d5ffc8bdd feat(memory): add MemoryLattice admission facade
50a6bb80e docs(governance): define memory authority map
9fe91c9de fix(memory): enforce chetana flag at canonical register boundary
9014f09b5 wip(audit): pre-merge checkpoint — runtime truth audit work
dd53c8a46 fix(guardian): dataclass auto-init detection — eliminates false-positive BLOCKER
121b24b7f fix(async): sync→async bridge helper safe under Python 3.14 thread-pool reuse
091c235e7 feat(runtime): wire cc_tool_marks consumer loop into orchestrator
fcbc4bc28 feat(bridge): cc_tool_marks consumer — close Claude-Code→Dharma one-way bridge
8d463879f feat(gnani): inject lodestone meta-task awareness into agent system prompts
696973c0d feat(dgm): DiversityArchive shadow-mode parent sampler
6f5cb4172 fix(recognition): restore R_V measurement — unblock Krogh-Vedelsby tracking
be9f468e5 fix(telos): CONSENT tri-state gate — close sensitive-path bypass
4542a5ee0 feat(runtime): operator directives — the air traffic controller
6e0c08768 feat(runtime): phase 1 — prompt and priority reorientation toward campaigns
996be803c fix(diversity): recalibrate monoculture threshold + add cascading window
156115e65 feat(cli): phase B.5 governance CLI — agent, campaign, promise, governance
209d28d01 feat(runtime): phase B.1/B.2/B.3 directed agents and durable campaign memory
ad3c7d6ed feat(governance): phase A.3 wire governance overlay into dispatch and synthesis
d8ec7c179 feat(executive): phase A.2 governance emission + substrate integration
3211ce6ae feat(governance): add campaign memory, directive queue, and governance overlay foundation
579a197d4 feat(runtime): add diversity governor for model and task balance
97c3018ce feat(runtime): throttle inward digestion and promote minimax lane
b81454774 fix(runtime): unblock swarm boot and tighten operator health truth
21436bd56 feat(research): RTN pipeline, shakti zeitgeist, gauntlet, infra
87427bf83 feat(runtime): evolution roster, consolidation, subconscious, knowledge
9881d693e feat(runtime): provider routing, cost attribution, daemon hardening
c6c829702 fix(operator): align chat provider defaults + repo-scoped tool roots
e3bab5f6e feat(api): daemon health router + routing manifest payloads
b48590f1c feat(dashboard): route-aware operator surfaces + daemon health truth
f0158968a feat: research-informed evolution — 4 new modules + full integration
36d55d9da fix(tui): pipe bridge stderr to prevent double-render corruption
05a758ac2 fix(tui): prompt submission always navigates to Chat tab
c49438426 fix(tui): model picker is overlay, not navigation
6cea36659 feat(tui): trace overlay — toggleable transparency into inner process
70b947491 feat(tui): restore color depth and visual hierarchy
76b1deae7 feat(bridge): wire ALL providers — ollama adapter + universal routing
3f47e8877 fix(bridge): sever ALL textual import chains from bridge path
82bb76b43 feat(tui): enforce semantic color tokens — no hardcoded color strings
db978396a feat(tui): basic markdown rendering — bold, italic, inline code
b67ed9c75 feat(tui): token counter and session tracking in status line
807c0dbaa feat(tui): remove pane borders — whitespace hierarchy like Claude Code
820066df2 feat(tui): scroll indicators — show content above/below visible window
1e5f6cce1 feat(tui): prompt history (up/down) and /clear command
0d9e65b52 feat(tui): borderless header/footer, subtle branding
b1d425dc0 feat(tui): minimal empty chat state — clean and inviting
1517d6e73 feat(tui): remove scenic strip default, add conversation turn separators
0744f6cc6 feat(tui): borderless text-only tab bar — minimal chrome
d3b737246 feat(tui): clean single-line prompt — no border, no title
0623e6d30 feat(tui): add animated thinking spinner component
020807821 feat(tui): single-line header and footer — minimal chrome
75c26f24e fix(tui): visual consistency pass — titles, muted text, padding
982f012dd feat(tui): apply semantic border tokens across all pane components
fc0925bb5 feat(tui): loading/error states for ControlPane and RepoPane
96628ab46 feat(tui): compact layout mode — hide scenic strip and summary on small terminals
5dccc1976 feat(tui): populate help sidebar with keybinding reference
ac7cbfbf9 fix(tui): unify header/footer frame border color
01a9cbe4e feat(tui): tab bar overflow with scroll indicators
16c1426da fix(tui): make sidebar width responsive to terminal size
a1524a2c0 feat(tui): model picker shows current model, status feedback on switch
29cb4b9f1 fix(tui): clearer footer hint text, remove Ctrl+M reference
e5bdedc7f feat(tui): add semantic design tokens and border constants
a5cee5bc3 fix(tui): remove Ctrl+M binding — conflicts with Enter in terminals
6407861d9 feat(tui): add StateBox and Skeleton components for loading/error/empty states
662b16dd7 feat(dashboard): Phase 1 Hokusai — indigo depths, telemetry strip, sharp panels
bbb2b2d0d feat(dashboard): backend stability + real data wiring + Hokusai design spec
```
### Local Branches Without Same-Named Origin
Count: **189**

```text
_rebase_tmp
_rtmp
archive/trust-build-compass-20260605
audit/runtime-truth-2026-04-26
backup/memory-kernel-prep-2026-05-14
backup/route-witness-main-pre-rebase-2026-05-13
backup/route-witness-pr297-pre-rebase-2026-05-13
chore/action-authority-gate-spec
chore/agentops-base-check
chore/agentops-v0
chore/authority-ptr-rollup
chore/brake-stabilization
chore/capsule-coherence-tool
chore/control-plane-stabilizer
chore/core-four-ontology-phase3
chore/current-truth-refresh
chore/daily-brief-discovery-agentops
chore/docops-integrity-v0
chore/docops-ttl-renewal-20260612
chore/governance-truth-repairs
chore/invariant-daily-insight-seam
chore/kaizen-review-v0
chore/kimi-claw-agentops-task
chore/loop1-truth-registry
chore/memory-tail-proof
chore/opportunity-dispatcher-budget-fix
chore/opportunity-dispatcher-budget-surgeon
chore/phase2-governance-checkpoint
chore/phase2-governance-rollup-core-four
chore/phase2-test-verify
chore/repo-runway-daily-brief-seam
chore/semgrep-high-risk-batch
chore/semgrep-rule-scope
chore/semgrep-triage
chore/state-authority-map
chore/telic-seam-budget-exception
chore/uplift-guard-recovery
cleanup/action-authority-salvage-2026-05-13
cleanup/agent-truth-spine-salvage-2026-05-13
cleanup/brake-stabilization-salvage-2026-05-13
cleanup/core-operating-circuit-proof-salvage-2026-05-13
cleanup/go-local-model-runtime-inventory-salvage-2026-05-13
cleanup/kaizen-review-v0-salvage-2026-05-13
cleanup/main-dirty-salvage-2026-05-12
cleanup/main-late-dirty-salvage-2026-05-12
cleanup/main-recurring-live-salvage-2026-05-13
cleanup/memory-kernel-context-eval-2026-05-13
cleanup/memory-kernel-shadow-context-main-2026-05-13
cleanup/module-metabolism-strategy-salvage-2026-05-13
cleanup/opportunity-dispatcher-budget-fix-salvage-2026-05-13
cleanup/root-memory-context-salvage-2026-05-13
cleanup/root-mixed-salvage-2026-05-12
cleanup/runtime-result-projector-salvage-2026-05-13
cleanup/viz-invariant-projection-2026-05-12
codex/cyber-loop-closure-provider-truth-20260619
codex/exec10-lf5
codex/fix-docops-autorefresh-dispatch-20260605
codex/fix-docops-autorefresh-repo-arg-20260605
codex/fix-pr-398-coherence
codex/go-idea-spark-ingest-spine-clean-20260604
codex/live-ops-cockpit-v1
codex/live-ops-cockpit-v1-docops-fix
codex/live-ops-cockpit-v1-docops-fix-mainbase
codex/live-ops-cockpit-v2-slice-a
codex/live-ops-cockpit-v2-slice-b
codex/live-ops-cockpit-v2-slice-c
codex/main-review-blockers
codex/memory-kernel-default-context-20260523
codex/pr388-disambig
codex/pr408-schema-align
codex/pr409-oms-hardening
codex/pr468-docops-clean
codex/pr470-after-468-fix
codex/pr470-docops-review
codex/pr546-main-sync
codex/pr558-main-sync
codex/pr562-main-sync
codex/pr564-main-sync
codex/pr574-codeql-tests
codex/pr578-main-sync
codex/pr578-main-sync2
codex/pr584-main-sync
codex/pr586-main-sync
codex/repair-pr-392
codex/repair-pr-399
codex/runtime-truth-nats-adapter-20260606
codex/toolbelt-onboarding
codex/truth-graph-v1
complexity-stress/replay-metamorphic-v1
copilot/close-duplicate-prs-and-enable-automerge
cutover/lf5-runtime-on-main-20260510-integrate-main
daemon-lane-upgrade-20260616
daemon-versioning/v0.0.1
dashboard-lf5-operator-lane
devin/1778037205-marathon-cleanup
devin/1778426210-ship-revenue-wedge-report
dgc-splash-art
docs/adr-008-ontology-api-grammar
feat/codex-lane-runner-2026-05-13
feat/cwt-v0-collector
feat/governed-memory-recursive-preflight
feat/inquiry-chain-phase1
feat/runtime-result-projector
feat/trust-gate-scoreboard
feat/world-radar-live-integration-2026-05-13
feat/world-radar-shakti-telos-2026-05-13
feat/world-radar-shakti-telos-docs-tests-2026-05-13
feat/world-radar-shakti-telos-final-residue-2026-05-13
feat/world-radar-shakti-telos-followup-2026-05-13
feat/world-radar-shakti-telos-live-2026-05-13
feat/world-radar-shakti-telos-residual-2026-05-13
fix/evolution-archive-honesty
fix/provider-honesty-g6
fix/runtime-spine-audit-followups
forge-v1/tokenbroker-scoreboard-20260620
forge/dharma-reward-forge-v0
governance/parallel-lane-policy-2026-06-06
governance/ws3-spine-dispatch
governance/ws4-gate-pep
holarchy/crossfalsify-20260619
lane/cybernetics-codex
lane/leftover-telos-cockpit
lane/loop-closure-reconciled
lane/palantir-pilot
lane/runtime-spine-hardening
lane/untangle-manifest
loop-closure/phase1b-2026-06
loop-closure/supplychain-bronze-20260620
merge-master/pr399-restack
merge-master/pr411-restack
merge-master/pr435-restack
merge-master/pr436-restack
migration/old-machine-main
mmm-nats-aiohttp
mmm-nats-ca-pem
mmm-nats-mike-credentials
mmm-nats-publish-deadline
mmm-pin-actions
mmm-visible-backlog-router
model-routing/nim-bleeding-edge-20260618
model-routing/nim-live-catalog-fix-20260620
organ/00-floor
organ/02-wounds
pr-344-backlog
pr-384-backlog
pr-388-backlog
pr-406-review-20260531
pr-465-backlog
pr-474-backlog
pr-495-backlog
qwen/spine-adoption
repair/pr-325-toolbelt
repair/pr413-docops-rebase
research/moltbook-investigation
research/persistent-agents-deepdive-2026-05
review-pr393c
review-pr411b
review/interop-fleet-2026-05-12
review/memory-knowledge-2026-05-12
review/root-governance-residue-2026-05-12
routing-lane-source
rss/FU-CONDUCTOR-MALFORMED-DB
rss/FU-CONDUCTOR-UTF8
rss/FU-CQ-PASSPORT-COUNT
rss/FU-CRON-HANDLERS
rss/FU-GOV-MODULE-BUDGET
rss/FU-SEAM-KEY-CONTRACT
rss/FU-SMOKE-PROFILE-ENUM
rss/FU-SMOKE-SLEEPCYCLE-SIG
rss/FU-SPINE-CORRELATION-JOIN
rss/FU-SPINE-DB-PATH
rss/FU-STIG-SCHEMA-BACKEND
rss/FU-STIG-WRITE-PATH
rss/FU-SUBPROC-NULLBYTE
rss/FU-TOOL-LOOP-CONVERGE
rss/FU-WIRE-MINIMAX
rss/FU-WIRE-XAI
rss/FU-WIRE-ZAI
runtime-truth/nats-rebuild-preflight-20260618
sattva/quality-ratchet-2026-06
spec/shakti-ginko-organ
spine-adoption/slice-b-adapter-saturation
spine-adoption/slice-c-mapping-receipts
tam/operator-seed-v1
telos-ai-seed-2026-06-13
telosproof-v0-advisory-spike
telosproof-v1-verification-substrate
trust-build-compass
worktree-research-integration
```
### Origin Branches Not Checked Out Locally
Count: **237**

```text
alignment-experiment-runpod
archive/tcs-heartbeat-main-diverged-20260511
audit/merge-2026-03-22
backup/pr-48-pre-rebase-ba90b5f
capital-lab/build
chore/agent-truth-spine
chore/auto-spine-adoption-2026-06-11
chore/commission-agent-runner-telic-chain
chore/cron-canonical-declaration
chore/cron-daemon-env-wrapper
chore/devin-inbound-11-step-audit
chore/docops-authority-registry
chore/governance-canon-refresh
chore/governance-onboarding-convergence
chore/governance-spine-adoption-2026-06-22T0600Z
chore/governance-spine-adoption-metric-20260608
chore/governance-spine-adoption-metric-refresh
chore/governance/hygiene-lifecycle-v2
chore/governance/spine-adoption-metric-refresh
chore/governance/spine-adoption-refresh-2026-06-07
chore/governance/spine-adoption-refresh-20260606
chore/kimi-force-response-20260505
chore/ops-run-report-2026-06-03T1200Z
chore/phase2-governance-isolation
chore/pr69-review-fixes
chore/provider-lane-pin-fix
chore/refresh-spine-adoption-metric
chore/refresh-spine-adoption-metric-20260622
chore/semgrep-hardening
chore/shakti-feedback-shadow-apply-dogfood
chore/spinal-bridge-clean-20260507
chore/spine-adoption-metric-20260605
chore/spine-adoption-metric-20260606
chore/spine-adoption-metric-20260614-1800
chore/spine-adoption-metric-refresh-20260603
chore/spine-adoption-metric-refresh-20260611
chore/telos-hierarchy-doctrine-correction
claude/confirm-plan-working-3qaaq
claude/seeing-organ-2je1gw
claude/structure-prompts-I4uPi
claude/todo-implementation-JXjD1
cleanup/docstrings-full-power-probe-20260507
cleanup/identity-onboarding-2026-05-12
cleanup/memory-kernel-preflight-lane-2026-05-16
cleanup/recursive-evolution-lane-2026-05-16
cleanup/route-witness-2026-05-12
cleanup/route-witness-main-2026-05-13
codex/a2a-active-track-20260613
codex/authority-revenue-loop-clean
codex/hypernode-empty-quadrant
codex/kaizen-exec-loop-20260601
codex/live-ops-cockpit-v2-slice-d
codex/module-metabolism-strategy
codex/operator-brief-witness-ready
codex/pr90-critical-substrates-clean
codex/provenance-fanout-derivation-clean
codex/runtime-convergence-hardening
codex/runtime-truth-spine-v1
codex/slop-verification-main
codex/trace-attractor-ledger-spec
codex/trace-attractor-projection-types
codex/trace-attractor-store-readers
converge/kimi-claw-registration-20260428
copilot/build-three-connectors
copilot/clean-pr-portfolio-map
copilot/featurecontrol-loop-hardening-chetana-rebase
copilot/latest-pull-request
copilot/merge-all-changes
copilot/triage-open-pr-backlog
cutover/lf5-runtime-on-main-20260510
design/routing-fusion-spine
design/routing-fusion-spine-pr
devin/1777890984-authority-revenue-loop-gauntlet
devin/1777901958-repo-reality-gauntlet
devin/1777903781-provenance-wiring-mm17-mm18
devin/1777909780-substrate-meta-layer-items-2-3
devin/1777910581-ledger-watcher-operator-brief
devin/1777938227-value-events-cli
devin/1777938416-provenance-fanout-derivation
devin/1777940178-test-coverage-cold-substrates
devin/1777941324-test-coverage-phase2-6
devin/1777972679-consolidation-alignment
devin/1777994193-fractal-room-research
devin/1777995295-fractal-room-build
devin/1777996370-structural-coherence
devin/1778385929-revenue-cell-v0
devin/1778683993-control-surface-contract-hardening
devin/1779271215-fix-gitnexus-hint
devin/1779279100-close-cockpit-track
devin/1779281950-track-transition-and-seeds
devin/1779703534-11-step-chain-verdict
devin/1779707153-11step-build-plan
devin/1779721563-11-step-chain-verdict
devin/1779876416-11-step-chain-verdict-v2
devin/1779883637-11-step-chain-verdict-v2
devin/1779890777-11-step-verdict-v3
devin/1779905139-11-step-chain-verdict-v2
devin/1779919577-11step-chain-verdict-v4
devin/1779943311-devin-a2a-fleet-plan
devin/1779946341-a2a-trace-persistence-e2e
devin/1779962811-11step-chain-verdict-v5
devin/1779977141-11step-chain-verdict
devin/1779978250-spine-governance-registration
devin/1779991547-11step-chain-verdict-v6
devin/1780022557-11-step-verdict-v3
devin/1780023669-verdict-clean
devin/1780038474-11step-chain-verdict-fresh
devin/1780042107-11step-chain-verdict
devin/1780059954-inbound-check-status
devin/1780095832-inbound-check-status
devin/1780103068-inbound-check-response
devin/1780128383-inbound-check-response
devin/1780131969-inbound-check-response
devin/1780298217-andon-verdict-D-E
devin/1780324280-andon-verdict-D-E-restack
devin/1780328602-andon-verdict-restack2
devin/1780339778-andon-restack3
devin/1780340193-andon-restack4
devin/1780340889-andon-restack5
devin/1780342618-andon-restack6
devin/1780373801-andon-restack7
devin/1780410762-pr-janitor-session
devin/1780411107-pr-janitor-session
devin/1780414839-pr-janitor-session
devin/1780416467-pr-janitor-session
devin/1780418181-pr-janitor-session
devin/1780420386-pr-janitor-session
devin/1780422058-pr-janitor-session
devin/1780424084-pr-janitor-session
devin/1780548631-spine-a2a-adoption
devin/1780554948-vel-equivalence-matrix
devin/1781340172-bug-corral
devin/1782057657-markitdown-document-ingest
devin/2026-05-28-autonomous-expansion-audit
devin/2026-05-29-research-organ-pivot
devin/2026-05-30-proof-artifact-pivot
devin/full-swarm-e2e-test-20260621
devin/runtime-truth-spine-pr-a
devin/update-skills-1779976321
devin/update-skills-1782049001
docs/canonical-drift-cleanup
docs/swarm-substrate-spec-2026-05-20
experiments/mask-rv-whitebox-prereg
feat/agent-chat-panel
feat/auto-evolution
feat/board-feedback-edge
feat/chetana-grand-memory
feat/chetana-restoration-from-4c70456e
feat/gauntlet-external-outcome-rewire
feat/go-evidence-sense-organ-v0
feat/governed-recursive-proof-tightening
feat/governed-recursive-proof-v0
feat/gplot-lodestone-seed
feat/knowledge-ops-organ-seed
feat/memory-census
feat/operating-spine-v2
feat/per-agent-chat-config-endpoints
feat/persist-evidence-receipts
feat/recursive-discovery-shadow-2026-05-14
feat/s4-zeitgeist-executive-stage2
feat/s4-zeitgeist-llm-scan
feat/slop-verification-system
feat/world-radar-shakti-safe-convergence-2026-05-13
feature/agent-work-os-v0
feature/control-loop-hardening-chetana-rebase-needed
feature/ontology-native-command-brief-v0
feature/operator-brief-first-tick-witness
fix-sql-injection-guardian-checks-7663364361950920885
fix/agent-wiring
fix/chetana-wiki-multiroot
fix/ci-green
fix/ci-tests-yaml
fix/false-affordance-purge
fix/packaged-build-hardening
fix/semantic-index-idempotence
governance/inquiry-chain-phase1
governance/pr-lifecycle-2026-06-13
governance/spine-adoption-refresh-2026-06-13
governance/tier-1-install
gpt55/high-roi-spine-mcp-orchestrator-20260620
gpt55/module-diet-census-20260619
honest-spine-v2
intel/decepticon-phase1
lak-e2e
mmm-a2a-conditional-merge
ops/2026-06-03-run
ops/governance-report-2026-06-14
ops/governance-report-2026-06-18
ops/governance-spine-metric-refresh
ops/pr-lifecycle-spine-2026-06-15T0000Z
ops/pr-lifecycle-spine-adoption-2026-06-14T1200Z
ops/report-2026-06-19T1800Z
ops/report-2026-06-21T1200Z
ops/report-2026-06-21T1800Z
ops/run-report-2026-06-05T00Z
ops/run-report-2026-06-05T06Z
ops/run-report-2026-06-05T1200Z
ops/spine-adoption-2026-06-13
ops/spine-adoption-2026-06-20T0600Z
ops/spine-adoption-2026-06-21T0600Z
ops/spine-adoption-metric-2026-06-03
ops/spine-adoption-metric-refresh-20260606
ops/spine-adoption-metric-refresh-20260606-060209
ops/spine-adoption-refresh-2026-06-04T12
ops/spine-metric-refresh-2026-06-04
opus-identity-levelup
opus/traverse-fix-20260605
origin
oz/route-truth-audit-2026-04-04
perf-async-roaming-daemon-7469302374074110265
perplexity-computer/a2a-activation-1780025504
perplexity-computer/doctrine-amendment-multi-track
perplexity-computer/mailbox-ack-to-claude-20260531
perplexity-computer/nest-1780023498
perplexity/bug-corral-arbiter-packet
pr/routing-coherence
pr91-review
repair/pr-323-dkeys
rescue/provenance-sentinel-go-track-20260612
research/encapsulation-language-strategy-room
review/proof-artifacts-2026-05-12
roaming-bridge-20260326
roaming-daemon-20260326
roaming-fixall-20260326
roaming-mailbox-live-20260326
spec/boardstore-facade
spine-grounding/slice-1-adoption-gate
spine-grounding/slice-2-runtime-recovery
spine-grounding/slice-3-tollbooth-gateway
stabilize/dharma-safe-clean
tests/spine-persistence-invariant
wiring/archive-build-loop-2026-05-07
wiring/triage-cron-job-runtime-2026-05-07
wiring/triage-roaming-dispatch-2026-05-07
worker4/pr323-codeql
worker4/pr332-codeql
worktree-holon-agent
```
### Dirty Working Tree Grouped By Local ACTIVE_TRACK Owned Surfaces
Current branch: `telos-ai-seed-v0-from-sandbox`. Dirty/untracked entries: **188**.

| local track | dirty entries | files |
|---|---:|---|
| `runtime-truth-reconciliation-2026-06` | 5 | `.M dharma_swarm/operator_core/control_surface_live_ops.py`, `.M dharma_swarm/operator_core/ds_goal_wrapper_contract.py`, `.M dharma_swarm/operator_core/world_radar/receipt_bridge.py`, `.M dharma_swarm/runtime_state.py`, `.M scripts/governance/agent_onboard.py` |
| `runtime-truth-spine-adoption-2026-06` | 2 | `.M dharma_swarm/agent_runner.py`, `.M dharma_swarm/orchestrator.py` |
| `orientation-graph-2026-06` | 1 | `.M tests/test_orientation_graph.py` |
| `composer-holon-spine-longrun-2026-06` | 26 | `.M dharma_swarm/holon_health.py`, `.M tests/test_holon_health.py`, `? dharma_swarm/holon_l4_activation.py`, `? dharma_swarm/holon_l4_model_probe_lease.py`, `? dharma_swarm/holon_l4_orchestration_runtime.py`, `? dharma_swarm/holon_l4_service.py`, `? dharma_swarm/holon_l4_smoke.py`, `? dharma_swarm/holon_l4_supervisor.py`, `? dharma_swarm/holon_orchestrate.py`, `? dharma_swarm/holon_service_liveness.py`, `? dharma_swarm/holon_transport_liveness.py`, `? reports/sovereign_holons/L4_HOLON_SUBSTRATE_HYGIENE_AND_SMOKE_20260618.md`, `? reports/sovereign_holons/l4_memory_write_receipts.jsonl`, `? scripts/holon_l4_activation.py`, `? scripts/holon_l4_model_probe_lease.py`, `? scripts/holon_l4_service.py`, `? scripts/holon_l4_smoke.py`, `? scripts/holon_l4_supervisor.py`, `? tests/test_holon_l4_activation.py`, `? tests/test_holon_l4_model_probe_lease.py`, `? tests/test_holon_l4_service.py`, `? tests/test_holon_l4_smoke.py`, `? tests/test_holon_l4_supervisor.py`, `? tests/test_holon_orchestrate.py`, `? tests/test_holon_service_liveness.py`, `? tests/test_holon_transport_liveness.py` |
| `agent-admission-semantic-commons-2026-06` | 7 | `.M docs/ontology/SEMANTIC_COMMONS.md`, `.M docs/ontology/semantic_aliases.yaml`, `.M docs/ontology/semantic_objects.yaml`, `.M docs/ontology/session_orientation.yaml`, `.M scripts/governance/agent_admission.py`, `.M tests/test_agent_admission.py`, `.M tests/test_semantic_commons.py` |
| `telos-ai-morning-refinery-2026-06` | 8 | `.M PRODUCT_SURFACE.md`, `.M docs/research/telos_ai/persona_agents/README.md`, `.M docs/vision_maps/TELOS_MORNING_REFINERY_V0.md`, `? docs/research/telos_ai/empire_agents/`, `? docs/research/telos_ai/persona_agents/07_ATTENTION_ECOLOGIST.md`, `? docs/research/telos_ai/persona_agents/08_MACHINE_MIND_ETHICIST.md`, `? docs/research/telos_ai/persona_agents/CANONICAL_COUNCIL.md`, `? tests/test_telos_morning_refinery.py` |
| `a2a-cloud-agent-bridge-2026-06` | 6 | `? dharma_swarm/a2a/a2a_cloud_contact.py`, `? dharma_swarm/a2a/contact_registry.py`, `? dharma_swarm/a2a/verifier.py`, `? docs/architecture/A2A_CLOUD_BRIDGE.md`, `? reports/state/a2a_score_denominator.md`, `? tests/test_a2a_cloud_contact.py` |
| `UNASSIGNED_BY_LOCAL_ACTIVE_TRACKS` | 133 | `.M .gitignore`, `.M CLAUDE.md`, `.M Makefile`, `.M api/models.py`, `.M api/routers/health.py`, `.M com.dharma.swarm.plist`, `.M dashboard/src/hooks/useRuntimeControlPlane.ts`, `.M dashboard/src/lib/api.test.ts`, `.M dashboard/src/lib/api.ts`, `.M dashboard/src/lib/runtimeControlPlane.test.ts`, `.M dashboard/src/lib/runtimeControlPlane.ts`, `.M dashboard/src/lib/types.ts`, `.M dharma_swarm/autonomous_agent.py`, `.M dharma_swarm/cron_daemon.py`, `.M dharma_swarm/evolution.py`, `.M dharma_swarm/gaia_platform.py`, `.M dharma_swarm/opportunity_dispatcher.py`, `.M dharma_swarm/orchestrate_live.py`, `.M dharma_swarm/palantir_pilot.py`, `.M dharma_swarm/profiles.py`, `.M dharma_swarm/providers.py`, `.M dharma_swarm/pulse.py`, `.M dharma_swarm/runtime_lifecycle.py`, `.M dharma_swarm/swarm.py`, `.M dharma_swarm/swarm_health_api.py`, `.M dharma_swarm/telemetry_plane.py`, `.M dharma_swarm/terminal_bridge.py`, `.M dharma_swarm/terminal_commands/_helpers.py`, `.M dharma_swarm/terminal_commands/diagnostics.py`, `.M dharma_swarm/terminal_commands/lifecycle.py`, `.M dharma_swarm/vector_store.py`, `.M dharma_swarm/world_model.py`, `.M dharma_swarm/yoga_node.py`, `.M docs/agents/palantir_pilot/MEMORY.md`, `.M docs/docops/AUTO_INVENTORY.md`, `.M docs/governance/ACTIVE_TRACK.yaml`, `.M docs/governance/CANONICAL_DOC_STACK.md`, `.M docs/governance/KAIZENOPS.md`, `.M docs/governance/SOVEREIGN_MANIFEST.md`, `.M docs/governance/SWARM_GENOME.md`, `.M docs/governance/VENTURE_CELL_PORTFOLIO.yaml`, `.M docs/ops/PR_REVIEW_CONTROL.md`, `.M docs/vision_maps/NORTH_STAR.md`, `.M holon/holon_bridge.py`, `.M holon/holon_runtime.py`, `.M holon/memory_kernel/__init__.py`, `.M reports/governance/active_track_evidence.json`, `.M reports/governance/active_track_evidence.md`, `.M reports/governance/track_portfolio.json`, `.M scripts/com.dharma.cron-daemon.plist`, `.M scripts/governance/runtime_receipt_coverage_report.py`, `.M scripts/governance/spine_dispatch_mode_report.py`, `.M scripts/runtime/a2a_inbox_bridge.py`, `.M scripts/runtime/live_ops_census.py`, `.M scripts/runtime/pr_merge_control.py`, `.M scripts/runtime/runtime_lifecycle_receipt_probe.py`, `.M scripts/verify_holon_harness_prod.py`, `D. synthesizer_memory.json`, `.M tests/test_a2a_inbox_bridge.py`, `.M tests/test_a2a_inbox_bridge_tmux_scripts.py`, `.M tests/test_agent_onboard.py`, `.M tests/test_agent_runner.py`, `.M tests/test_agent_runner_routing_feedback.py`, `.M tests/test_cron_daemon.py`, `.M tests/test_dgc_cli.py`, `.M tests/test_ds_goal_wrapper_receipt_probe.py`, `.M tests/test_evolution.py`, `.M tests/test_gaia_platform.py`, `.M tests/test_go_world_signal_bridge.py`, `.M tests/test_live_ops_census.py`, `.M tests/test_model_router_telemetry.py`, `.M tests/test_orchestrate_live.py`, `.M tests/test_orchestrator_spine_dispatch.py`, `.M tests/test_pr_merge_control.py`, `.M tests/test_profiles.py`, `.M tests/test_routing_surface_inventory.py`, `.M tests/test_runtime_lifecycle.py`, `.M tests/test_runtime_lifecycle_receipt_probe.py`, `.M tests/test_runtime_receipt_coverage_report.py`, `.M tests/test_runtime_state_invariants.py`, +53 more |

### Sibling Worktrees
| path | branch | head | exists | dirty count | first dirty paths |
|---|---|---:|---:|---:|---|
| `/Users/dhyana/dharma_swarm` | `telos-ai-seed-v0-from-sandbox` | `cd610be3c` | True | 188 | `.gitignore`, `CLAUDE.md`, `Makefile`, `PRODUCT_SURFACE.md`, `api/models.py`, `api/routers/health.py`, `com.dharma.swarm.plist`, `dashboard/src/hooks/useRuntimeControlPlane.ts`, `dashboard/src/lib/api.test.ts`, `dashboard/src/lib/api.ts`, `dashboard/src/lib/runtimeControlPlane.test.ts`, `dashboard/src/lib/runtimeControlPlane.ts` |
| `/private/tmp/dharma_nim_main_check` | `model-routing/nim-live-catalog-fix-20260620` | `4394d81b2` | False | MISSING |  |
| `/Users/dhyana/dharma_helm_build` | `helm/worldclass-20260612` | `680b013c0` | True | 9 | `dharma_swarm/operator_core/intent_payloads.py`, `dharma_swarm/terminal_bridge.py`, `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json`, `scripts/start_terminal_tui_tmux.sh`, `tests/test_intent_payloads.py`, `reports/terminal/`, `tests/test_terminal_bridge.py` |
| `/Users/dhyana/dharma_swarm_cashclaw` | `cashclaw/revenue-hydra-v1` | `c487d2725` | True | 18 | `dharma_swarm/claude_cli.py`, `reports/revenue_wedge/evolution/20260610T193223Z/`, `reports/revenue_wedge/evolution/20260611T073905Z/`, `reports/revenue_wedge/evolution/20260611T154212Z/`, `reports/revenue_wedge/evolution/20260611T194323Z/`, `reports/revenue_wedge/evolution/20260611T234419Z/`, `reports/revenue_wedge/evolution/20260612T034600Z/`, `reports/revenue_wedge/evolution/20260612T074726Z/`, `reports/revenue_wedge/evolution/20260612T155034Z/`, `reports/revenue_wedge/evolution/20260612T195220Z/`, `reports/revenue_wedge/evolution/20260613T035510Z/`, `reports/revenue_wedge/evolution/20260613T075727Z/` |
| `/Users/dhyana/dharma_swarm_live` | `organ/03-seat` | `e67b91829` | True | 1 | `reports/handoffs/SEAT_REBASE_PREVIEW_2026-06-11.md` |
| `/Users/dhyana/dharma_swarm_main` | `` | `86418541a` | True | 3 | `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json` |
| `/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618` | `runtime-truth/nats-rebuild-preflight-20260618` | `86418541a` | True | 82 | `Makefile`, `dharma_swarm/a2a/__init__.py`, `dharma_swarm/a2a/nats_transport.py`, `dharma_swarm/a2a/node_gateway.py`, `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`, `reports/governance/active_track_evidence.json`, `reports/governance/active_track_evidence.md`, `reports/governance/track_portfolio.json`, `reports/orientation/repo_context.json`, `reports/orientation/repo_context.md`, `scripts/governance/check_nats_substrate_contract.py`, `scripts/runtime/a2a_domain_reply_artifact.py` |
| `/Users/dhyana/ds_forge_v1_scoreboard` | `forge-v1/tokenbroker-scoreboard-20260620` | `d8bca7aab` | True | 0 |  |
| `/Users/dhyana/ds_governance_fitness_ci_20260620` | `codex/governance-fitness-ci-20260620` | `c69f1cf05` | True | 0 |  |
| `/Users/dhyana/ds_supplychain_slice` | `loop-closure/supplychain-bronze-20260620` | `11de04fb7` | True | 0 |  |

### Local-Only Active Tracks
These track ids are active in local `docs/governance/ACTIVE_TRACK.yaml` and absent from both active and closed tracks on origin/main. They are also absent from PR #662.

#### `agent-admission-semantic-commons-2026-06` — AgentAdmission + Semantic Commons — one door for agent identity and naming
- status: `ACTIVE`; opened_at: `2026-06-14`; verified_at: `2026-06-14`; owner: `@AmitabhainArunachala`; serves: `substrate-nativeness`
- owned surfaces: `docs/ontology/**`, `docs/ops/AGENT_ADMISSION.md`, `dharma_swarm/semantic_commons.py`, `dharma_swarm/engine/hybrid_retriever.py`, `dharma_swarm/context.py`, `scripts/governance/agent_admission*.py`, `scripts/governance/name_drift*.py`, `tests/test_agent_admission*.py`, `tests/test_semantic_commons*.py`, `tests/test_hybrid_retriever.py`

| file/surface | kind | worktree | HEAD | origin/main | PR #662 | dirty | stashes |
|---|---|---:|---:|---:|---:|---|---|
| `docs/ontology/**` | glob | 7 | 6 | 3 | 3 | `` | stash@{27}, stash@{8} |
| `docs/ops/AGENT_ADMISSION.md` | file | YES | YES | NO | NO | `` |  |
| `dharma_swarm/semantic_commons.py` | file | YES | YES | NO | NO | `` |  |
| `dharma_swarm/engine/hybrid_retriever.py` | file | YES | YES | YES | YES | `` |  |
| `dharma_swarm/context.py` | file | YES | YES | YES | YES | `` | stash@{32}, stash@{33}, stash@{65} |
| `scripts/governance/agent_admission*.py` | glob | 2 | 2 | 0 | 0 | `` |  |
| `scripts/governance/name_drift*.py` | glob | 1 | 1 | 0 | 0 | `` |  |
| `tests/test_agent_admission*.py` | glob | 1 | 1 | 0 | 0 | `` |  |
| `tests/test_semantic_commons*.py` | glob | 2 | 2 | 0 | 0 | `` |  |
| `tests/test_hybrid_retriever.py` | file | YES | YES | YES | YES | `` |  |
| `docs/ops/AGENT_ONBOARDING.md` | file | YES | YES | YES | YES | `` | stash@{17}, stash@{23}, stash@{25}, stash@{26}, stash@{27}, stash@{28}, stash@{29} |
| `dharma_swarm/operator_core/living_agent_kernel.py` | file | YES | YES | YES | YES | `` | stash@{13}, stash@{14}, stash@{15}, stash@{16}, stash@{17} |
| `docs/ontology/SEMANTIC_COMMONS.md` | file | YES | YES | YES | YES | `.M` |  |
| `docs/ontology/semantic_objects.yaml` | file | YES | YES | YES | YES | `.M` | stash@{8} |
| `docs/ontology/semantic_aliases.yaml` | file | YES | YES | YES | YES | `.M` | stash@{8} |
| `scripts/governance/name_drift_preflight.py` | file | YES | YES | NO | NO | `` |  |
| `scripts/governance/agent_admission.py` | file | YES | YES | NO | NO | `.M` |  |
| `tests/test_semantic_commons.py` | file | YES | YES | NO | NO | `.M` |  |
| `tests/test_agent_admission.py` | file | YES | YES | NO | NO | `.M` |  |
| `docs/ontology/pkm_projection.yaml` | file | YES | YES | NO | NO | `` |  |
| `docs/ontology/retrieval_scope.yaml` | file | YES | YES | NO | NO | `` |  |
| `scripts/governance/agent_admission_projection.py` | file | YES | YES | NO | NO | `` |  |
| `tests/test_semantic_commons_projection.py` | file | YES | YES | NO | NO | `` |  |
| `reports/governance/semantic_commons_projection_manifest.json` | file | YES | YES | NO | NO | `` |  |

#### `cybernetics-codex-stewardship-2026-06` — Cybernetics Codex Stewardship — permanent owner for loop ecology
- status: `ACTIVE`; opened_at: `2026-06-14`; verified_at: `2026-06-14`; owner: `@AmitabhainArunachala`; serves: `research-depth`
- owned surfaces: `docs/ops/CYBERNETICS_CODEX.md`, `docs/agents/cybernetics_codex/**`, `dharma_swarm/cybernetics_codex.py`, `scripts/governance/cybernetics_codex_audit.py`, `scripts/governance/register_cybernetics_codex.py`, `tests/test_cybernetics_codex.py`, `reports/loop_closure/cybernetics_codex/**`

| file/surface | kind | worktree | HEAD | origin/main | PR #662 | dirty | stashes |
|---|---|---:|---:|---:|---:|---|---|
| `docs/ops/CYBERNETICS_CODEX.md` | file | YES | YES | YES | YES | `` |  |
| `docs/agents/cybernetics_codex/**` | glob | 9 | 7 | 7 | 7 | `` |  |
| `dharma_swarm/cybernetics_codex.py` | file | YES | YES | YES | YES | `` |  |
| `scripts/governance/cybernetics_codex_audit.py` | file | YES | YES | YES | YES | `` |  |
| `scripts/governance/register_cybernetics_codex.py` | file | YES | YES | YES | YES | `` |  |
| `tests/test_cybernetics_codex.py` | file | YES | YES | YES | YES | `` |  |
| `reports/loop_closure/cybernetics_codex/**` | glob | 0 | 0 | 3 | 2 | `` |  |
| `docs/governance/ACTIVE_TRACK.yaml` | file | YES | YES | YES | YES | `.M` | stash@{17}, stash@{18}, stash@{19}, stash@{27}, stash@{28}, stash@{29}, stash@{30} |
| `ACTIVE_SURFACE_MANIFEST.yaml` | file | YES | YES | YES | YES | `` | stash@{17}, stash@{27}, stash@{28}, stash@{29}, stash@{30}, stash@{40}, stash@{41}, stash@{42} +4 |
| `docs/agents/cybernetics_codex/agent.seed.yaml` | file | YES | YES | YES | YES | `` |  |
| `docs/agents/cybernetics_codex/SOUL.md` | file | YES | YES | YES | YES | `` |  |
| `docs/agents/cybernetics_codex/WAKE_CONTEXT.md` | file | YES | YES | YES | YES | `` |  |
| `docs/agents/cybernetics_codex/PROTOCOLS.md` | file | YES | YES | YES | YES | `` |  |
| `docs/agents/cybernetics_codex/CONTEXT_ENGINEERING.md` | file | YES | YES | YES | YES | `` |  |
| `reports/loop_closure/cybernetics_codex/ADMISSION_RECEIPT.md` | file | NO | NO | NO | NO | `` |  |
| `reports/loop_closure/cybernetics_codex/RUNTIME_HEARTBEAT_RECEIPT.md` | file | NO | NO | NO | NO | `` |  |

#### `telos-ai-morning-refinery-2026-06` — TELOS AI Morning Refinery — user-facing semantic refinery seed
- status: `ACTIVE`; opened_at: `2026-06-14`; verified_at: `2026-06-14`; owner: `@AmitabhainArunachala`; serves: `revenue-external-humans-served`
- owned surfaces: `docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md`, `docs/vision_maps/TELOS_MORNING_REFINERY_V0.md`, `docs/research/telos_ai/**`, `PRODUCT_SURFACE.md`, `dashboard/src/app/dashboard/telos*/**`, `dashboard/src/components/telos*/**`, `tests/test_telos*.py`

| file/surface | kind | worktree | HEAD | origin/main | PR #662 | dirty | stashes |
|---|---|---:|---:|---:|---:|---|---|
| `docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md` | file | YES | YES | NO | NO | `` |  |
| `docs/vision_maps/TELOS_MORNING_REFINERY_V0.md` | file | YES | YES | NO | NO | `.M` |  |
| `docs/research/telos_ai/**` | glob | 19 | 11 | 0 | 0 | `` |  |
| `PRODUCT_SURFACE.md` | file | YES | YES | YES | YES | `.M` | stash@{33} |
| `dashboard/src/app/dashboard/telos*/**` | glob | 0 | 0 | 0 | 0 | `` |  |
| `dashboard/src/components/telos*/**` | glob | 0 | 0 | 0 | 0 | `` |  |
| `tests/test_telos*.py` | glob | 6 | 5 | 6 | 6 | `` | stash@{16}, stash@{17}, stash@{63} |
| `docs/research/telos_ai/2026-06-13_seed_research.md` | file | YES | YES | NO | NO | `` |  |
| `docs/research/telos_ai/2026-06-13_codex_feasibility_audit.md` | file | YES | YES | NO | NO | `` |  |
| `docs/research/telos_ai/persona_agents/README.md` | file | YES | YES | NO | NO | `.M` |  |
| `docs/research/telos_ai/refinery_examples/2026-06-13_ARTICULATE_ESSENCE_EXTRATOR_NODE_trial_001.md` | file | YES | YES | NO | NO | `` |  |
| `tests/test_telos_morning_refinery.py` | file | YES | NO | NO | NO | `?` |  |
| `reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md` | file | NO | NO | NO | NO | `` |  |

#### `helm-worldclass-terminal-2026-06` — Helm Worldclass Terminal — operator TUI integration and verification lane
- status: `ACTIVE`; opened_at: `2026-06-14`; verified_at: `2026-06-14`; owner: `@AmitabhainArunachala`; serves: `substrate-nativeness`
- owned surfaces: `terminal/**`, `docs/TERMINAL_TUI_TMUX_HARNESS_2026-04-02.md`, `docs/plans/2026-04-02-terminal-*.md`, `reports/terminal/**`

| file/surface | kind | worktree | HEAD | origin/main | PR #662 | dirty | stashes |
|---|---|---:|---:|---:|---:|---|---|
| `terminal/**` | glob | 9065 | 52 | 53 | 53 | `` | stash@{11}, stash@{60}, stash@{64}, stash@{65}, stash@{66}, stash@{67}, stash@{68}, stash@{69} |
| `docs/TERMINAL_TUI_TMUX_HARNESS_2026-04-02.md` | file | YES | YES | YES | YES | `` |  |
| `docs/plans/2026-04-02-terminal-*.md` | glob | 2 | 2 | 2 | 2 | `` |  |
| `reports/terminal/**` | glob | 0 | 0 | 0 | 0 | `` |  |
| `terminal/package.json` | file | YES | YES | YES | YES | `` |  |
| `terminal/src/app.tsx` | file | YES | YES | YES | YES | `` | stash@{11}, stash@{69} |
| `terminal/tests/app.test.ts` | file | YES | YES | YES | YES | `` | stash@{11} |
| `terminal/scripts/golden_capture.sh` | file | NO | NO | NO | NO | `` |  |
| `terminal/scripts/ratchet.sh` | file | NO | NO | NO | NO | `` |  |
| `terminal/tests/golden/120x40/chat.txt` | file | NO | NO | NO | NO | `` |  |
| `terminal/tests/compactShell.test.tsx` | file | NO | NO | NO | NO | `` |  |
| `reports/terminal/HELM_WORLDCLASS_LIVE_TMUX_RECEIPT.md` | file | NO | NO | NO | NO | `` |  |
| `reports/terminal/HELM_WORLDCLASS_CLOSEOUT.md` | file | NO | NO | NO | NO | `` |  |

#### `a2a-cloud-agent-bridge-2026-06` — A2A Cloud-Agent Bridge — cloud reasoners onto the NATS substrate
- status: `ACTIVE`; opened_at: `2026-06-14`; verified_at: `2026-06-14`; owner: `@codex_composer`; serves: `substrate-nativeness`
- owned surfaces: `docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml`, `docs/architecture/A2A_CLOUD_BRIDGE.md`, `dharma_swarm/a2a/a2a_cloud_contact.py`, `dharma_swarm/a2a/contact_registry.py`, `dharma_swarm/a2a/verifier.py`, `reports/state/a2a_score_denominator.md`, `tests/test_a2a_cloud_contact.py`

| file/surface | kind | worktree | HEAD | origin/main | PR #662 | dirty | stashes |
|---|---|---:|---:|---:|---:|---|---|
| `docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml` | file | YES | YES | YES | YES | `` |  |
| `docs/architecture/A2A_CLOUD_BRIDGE.md` | file | YES | NO | NO | NO | `?` |  |
| `dharma_swarm/a2a/a2a_cloud_contact.py` | file | YES | NO | NO | NO | `?` |  |
| `dharma_swarm/a2a/contact_registry.py` | file | YES | NO | NO | NO | `?` |  |
| `dharma_swarm/a2a/verifier.py` | file | YES | NO | NO | NO | `?` | stash@{17} |
| `reports/state/a2a_score_denominator.md` | file | YES | NO | NO | NO | `?` |  |
| `tests/test_a2a_cloud_contact.py` | file | YES | NO | NO | NO | `?` |  |
| `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` | file | YES | YES | YES | YES | `` | stash@{17} |

## Phase 2 — True Divergence And Portfolio Union
### Active Track Portfolio Comparison
| source | active count | active ids |
|---|---:|---|
| local worktree | 11 | `runtime-truth-reconciliation-2026-06`, `runtime-truth-nats-2026-06`, `runtime-truth-spine-adoption-2026-06`, `loop-closure-2026-06`, `orientation-graph-2026-06`, `composer-holon-spine-longrun-2026-06`, `agent-admission-semantic-commons-2026-06`, `cybernetics-codex-stewardship-2026-06`, `telos-ai-morning-refinery-2026-06`, `helm-worldclass-terminal-2026-06`, `a2a-cloud-agent-bridge-2026-06` |
| origin/main | 7 | `runtime-truth-reconciliation-2026-06`, `runtime-truth-nats-2026-06`, `runtime-truth-spine-adoption-2026-06`, `loop-closure-2026-06`, `truth-graph-platform-2026-06`, `composer-holon-spine-longrun-2026-06`, `provider-routing-consolidation-2026-06` |
| PR #662 seeing-organ | 8 | `runtime-truth-reconciliation-2026-06`, `runtime-truth-nats-2026-06`, `runtime-truth-spine-adoption-2026-06`, `loop-closure-2026-06`, `truth-graph-platform-2026-06`, `composer-holon-spine-longrun-2026-06`, `provider-routing-consolidation-2026-06`, `seeing-organ-2026-06` |
| PR #663 MarkItDown | 7 | `runtime-truth-reconciliation-2026-06`, `runtime-truth-nats-2026-06`, `runtime-truth-spine-adoption-2026-06`, `loop-closure-2026-06`, `truth-graph-platform-2026-06`, `composer-holon-spine-longrun-2026-06`, `provider-routing-consolidation-2026-06` |

### Track-Level Drift Table
| track id | local active? | origin/main active? | origin/main closed? | PR #662 active? | verdict | evidence |
|---|---:|---:|---:|---:|---|---|
| `a2a-cloud-agent-bridge-2026-06` | True | False | False | False | **AHEAD** | local-only active track absent from origin/main |
| `agent-admission-semantic-commons-2026-06` | True | False | False | False | **AHEAD** | local-only active track absent from origin/main |
| `boardstore-facade-2026-05` | False | False | True | False | **IN-SYNC** |  |
| `cockpit-control-surface-2026-05` | False | False | True | False | **IN-SYNC** |  |
| `composer-holon-spine-longrun-2026-06` | True | True | False | True | **IN-SYNC** |  |
| `cybernetics-codex-stewardship-2026-06` | True | False | False | False | **AHEAD** | local-only active track absent from origin/main |
| `helm-worldclass-terminal-2026-06` | True | False | False | False | **AHEAD** | local-only active track absent from origin/main |
| `loop-closure-2026-06` | True | True | False | True | **IN-SYNC** |  |
| `operator-brief-seam-2026-04` | False | False | True | False | **IN-SYNC** |  |
| `orientation-graph-2026-06` | True | False | True | False | **DIVERGED** | local declares active but origin/main closed track |
| `provider-routing-consolidation-2026-06` | False | True | False | True | **BEHIND** | origin/main active track absent from local active portfolio |
| `runtime-truth-nats-2026-06` | True | True | False | True | **IN-SYNC** |  |
| `runtime-truth-reconciliation-2026-06` | True | True | False | True | **IN-SYNC** |  |
| `runtime-truth-spine-2026-06` | False | False | True | False | **IN-SYNC** |  |
| `runtime-truth-spine-adoption-2026-06` | True | True | False | True | **IN-SYNC** |  |
| `seeing-organ-2026-06` | False | False | False | True | **BEHIND** | live PR #662 adds this track |
| `telos-ai-morning-refinery-2026-06` | True | False | False | False | **AHEAD** | local-only active track absent from origin/main |
| `trace-attractor-causal-spine-2026-05` | False | False | True | False | **IN-SYNC** |  |
| `trace-identity-coverage-2026-05` | False | False | True | False | **IN-SYNC** |  |
| `truth-graph-platform-2026-06` | False | True | False | True | **BEHIND** | origin/main active track absent from local active portfolio |

### Portfolio Union Target
Target = origin/main active tracks + PR #662 seeing-organ track + local-only tracks worth preserving. PR #663 does not change ACTIVE_TRACK.

| order | track id | source | status | note |
|---:|---|---|---|---|
| 1 | `runtime-truth-reconciliation-2026-06` | origin/main | `ACTIVE` |  |
| 2 | `runtime-truth-nats-2026-06` | origin/main | `ACTIVE` |  |
| 3 | `runtime-truth-spine-adoption-2026-06` | origin/main | `ACTIVE` |  |
| 4 | `loop-closure-2026-06` | origin/main | `ACTIVE` |  |
| 5 | `truth-graph-platform-2026-06` | origin/main | `ACTIVE` |  |
| 6 | `composer-holon-spine-longrun-2026-06` | origin/main | `ACTIVE` |  |
| 7 | `provider-routing-consolidation-2026-06` | origin/main | `ACTIVE` |  |
| 8 | `seeing-organ-2026-06` | PR #662 | `ACTIVE` | land via PR #662 before regen |
| 9 | `agent-admission-semantic-commons-2026-06` | local-only | `ACTIVE` | must be split to named pushed branch before unioning |
| 10 | `cybernetics-codex-stewardship-2026-06` | local-only | `ACTIVE` | must be split to named pushed branch before unioning |
| 11 | `telos-ai-morning-refinery-2026-06` | local-only | `ACTIVE` | must be split to named pushed branch before unioning |
| 12 | `helm-worldclass-terminal-2026-06` | local-only | `ACTIVE` | must be split to named pushed branch before unioning |
| 13 | `a2a-cloud-agent-bridge-2026-06` | local-only | `ACTIVE` | must be split to named pushed branch before unioning |

Policy conflict: target union count `13` exceeds origin/main `track_policy.max_active=10` and local `track_policy.max_active=11`. Operator must either raise the WIP limit with doctrine/evidence or close/archive enough tracks before final union.

### Declared Owned Surfaces Missing On Current Disk
| track | source | declared surface | current worktree matches | origin/main matches |
|---|---|---|---:|---:|
| `runtime-truth-nats-2026-06` | origin/main | `dharma_swarm/a2a/a2a_nats_contact.py` | 0 | 0 |
| `runtime-truth-nats-2026-06` | origin/main | `dharma_swarm/a2a/a2a_core_contact.py` | 0 | 0 |
| `truth-graph-platform-2026-06` | origin/main | `scripts/governance/truth_graph_nats_e2e_demo.py` | 0 | 1 |
| `truth-graph-platform-2026-06` | origin/main | `scripts/governance/run_truth_graph_nats_e2e_demo.sh` | 0 | 1 |
| `truth-graph-platform-2026-06` | origin/main | `tests/test_truth_graph_repo_context.py` | 0 | 1 |
| `truth-graph-platform-2026-06` | origin/main | `dharma_swarm/a2a/task_receipt.py` | 0 | 1 |
| `truth-graph-platform-2026-06` | origin/main | `dharma_swarm/a2a/agent_presence.py` | 0 | 1 |
| `truth-graph-platform-2026-06` | origin/main | `tests/test_a2a_gate.py` | 0 | 1 |
| `truth-graph-platform-2026-06` | origin/main | `tests/test_agent_registry_presence.py` | 0 | 1 |
| `truth-graph-platform-2026-06` | origin/main | `reports/orientation/**` | 0 | 10 |
| `provider-routing-consolidation-2026-06` | origin/main | `dharma_swarm/model_pool.py` | 0 | 1 |
| `provider-routing-consolidation-2026-06` | origin/main | `dharma_swarm/model_defaults.py` | 0 | 1 |
| `provider-routing-consolidation-2026-06` | origin/main | `docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md` | 0 | 1 |
| `seeing-organ-2026-06` | PR #662 | `dharma_swarm/world_radar/safety.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `dharma_swarm/world_radar/frontier_council.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `dharma_swarm/world_radar/warrant_handoff.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `dharma_swarm/world_radar/sensemaking.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `dharma_swarm/world_radar/proposal.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `scripts/governance/check_world_quarantine.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `scripts/governance/check_frontier_council_replay.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `scripts/governance/check_world_warrant_handoff.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `scripts/governance/run_world_signal_seed_batch.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `scripts/governance/run_world_signal_seed_batch_live.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `scripts/governance/check_world_sensemaking_closure.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `tests/test_world_radar_safety.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `tests/test_frontier_council.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `tests/test_world_warrant_handoff.py` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `docs/architecture/SENSEMAKING_ORGAN.md` | 0 | 0 |
| `seeing-organ-2026-06` | PR #662 | `docs/vision_maps/2026-06-21_seeing_organ_master_synthesis.md` | 0 | 0 |
| `cybernetics-codex-stewardship-2026-06` | local-only | `reports/loop_closure/cybernetics_codex/**` | 0 | 3 |
| `telos-ai-morning-refinery-2026-06` | local-only | `dashboard/src/app/dashboard/telos*/**` | 0 | 0 |
| `telos-ai-morning-refinery-2026-06` | local-only | `dashboard/src/components/telos*/**` | 0 | 0 |
| `helm-worldclass-terminal-2026-06` | local-only | `reports/terminal/**` | 0 | 0 |

### PR-Eligible Local Branches
| branch | drift | remote | behind | ahead | mapped track/proposal | planned handling |
|---|---|---|---:|---:|---|---|
| `cashclaw/revenue-hydra-v1` | **IN-SYNC** | `origin/cashclaw/revenue-hydra-v1` | 0 | 0 | revenue-external-humans-served | sibling worktree dirty; preserve before any branch cleanup |
| `codex/governance-fitness-ci-20260620` | **BEHIND** | `origin/codex/governance-fitness-ci-20260620` | 89 | 0 | governance fitness CI / PR #647 | local branch is behind remote PR; repair by rebasing remote head, not local stale copy |
| `forge-v1/tokenbroker-scoreboard-20260620` | **DIVERGED** | `origin/main` | 114 | 9 | propose new track or archive | rebase onto origin/main, push only after operator chooses whether Forge v1 remains active |
| `helm/worldclass-20260612` | **AHEAD** | `origin/helm/worldclass-20260612` | 0 | 57 | helm-worldclass-terminal-2026-06 | branch is 57 ahead of remote; push normal after preserving dirty worktree |
| `holarchy/crossfalsify-20260619` | **DIVERGED** | `origin/main` | 114 | 1 | propose archive or research-depth track | ahead/behind; archive unless operator wants PR |
| `lane/cybernetics-codex` | **DIVERGED** | `origin/main` | 197 | 1 | cybernetics-codex-stewardship-2026-06 | rebase onto origin/main and push as track branch |
| `lane/leftover-telos-cockpit` | **DIVERGED** | `origin/main` | 197 | 1 | telos-ai-morning-refinery-2026-06 | rebase onto origin/main and push as track branch |
| `loop-closure/supplychain-bronze-20260620` | **AHEAD** | `origin/loop-closure/supplychain-bronze-20260620` |  |  | loop-closure-2026-06 | remote branch gone; push preservation branch, then rebase/PR if still relevant |
| `model-routing/nim-bleeding-edge-20260618` | **DIVERGED** | `origin/main` | 141 | 1 | provider-routing-consolidation-2026-06 | likely superseded by provider-routing track; archive or repair |
| `model-routing/nim-live-catalog-fix-20260620` | **AHEAD** | `origin/model-routing/nim-live-catalog-fix-20260620` |  |  | provider-routing-consolidation-2026-06 | worktree path is prunable/missing; inspect branch object, push/archive before deletion |
| `organ/03-seat` | **IN-SYNC** | `origin/organ/03-seat` | 0 | 0 | historical organ seat | branch in sync but sibling worktree has staged handoff; preserve/commit or archive |
| `telos-ai-seed-v0-from-sandbox` | **AHEAD** | `origin/telos-ai-seed-v0-from-sandbox` | 0 | 2 | mixed current checkout / local ACTIVE_TRACK edits | snapshot dirty tree first; split by track |

### Open PR Triage
Open PRs found through public GitHub API: **14**. `gh` auth was not available in this environment; public API data was used.

| PR | triage | branch | local branch? | author | updated | mergeable | CI/status | title | reason |
|---:|---|---|---:|---|---|---|---|---|---|
| #642 | **CLOSE-STALE-DUPLICATE** | `ops/governance-report-2026-06-18` | False | AmitabhainArunachala | 2026-06-22T06:03:16Z | mergeable=True state=unstable draft=True | pending; failure:3, success:26 | chore(governance): ops report 2026-06-18T1800Z — spine 93.8%, 7 open PRs | ops/report metric lineage is superseded by canonical reconciliation ledger |
| #643 | **NEEDS-REPAIR** | `gpt55/module-diet-census-20260619` | False | AmitabhainArunachala | 2026-06-19T08:22:32Z | mergeable=True state=unstable draft=True | pending; failure:4, success:24 | governance: add module diet census | draft/dirty/stale branch needs explicit repair before landing |
| #645 | **CLOSE-STALE-DUPLICATE** | `ops/report-2026-06-19T1800Z` | False | AmitabhainArunachala | 2026-06-22T06:03:16Z | mergeable=True state=unstable draft=True | pending; failure:4, success:25 | chore(governance): ops report 2026-06-19T1800Z — spine 93.8%, 9 open PRs | ops/report metric lineage is superseded by canonical reconciliation ledger |
| #647 | **NEEDS-REPAIR** | `codex/governance-fitness-ci-20260620` | True | AmitabhainArunachala | 2026-06-21T12:54:10Z | mergeable=False state=dirty draft=False | pending; failure:2, success:25 | [codex] governance: refresh active track and fitness properties [impact-checked] | draft/dirty/stale branch needs explicit repair before landing |
| #649 | **CLOSE-STALE-DUPLICATE** | `ops/spine-adoption-2026-06-20T0600Z` | False | AmitabhainArunachala | 2026-06-22T06:03:15Z | mergeable=True state=unstable draft=True | pending; failure:4, success:25 | chore(governance): ops report 2026-06-20T0600Z — spine 93.8%, 13 open PRs | ops/report metric lineage is superseded by canonical reconciliation ledger |
| #653 | **CLOSE-STALE-DUPLICATE** | `ops/spine-adoption-2026-06-21T0600Z` | False | AmitabhainArunachala | 2026-06-22T06:03:14Z | mergeable=True state=unstable draft=True | pending; failure:3, success:26 | chore(governance): ops report 2026-06-21T0600Z — spine 93.8%, 13 open PRs | ops/report metric lineage is superseded by canonical reconciliation ledger |
| #659 | **CLOSE-STALE-DUPLICATE** | `ops/report-2026-06-21T1200Z` | False | AmitabhainArunachala | 2026-06-22T06:03:13Z | mergeable=True state=unstable draft=True | pending; failure:3, success:26 | chore(governance): ops report 2026-06-21T1200Z — spine 93.8%, 9 open PRs | ops/report metric lineage is superseded by canonical reconciliation ledger |
| #660 | **KEEP-REVIEW** | `devin/update-skills-1782049001` | False | devin-ai-integration[bot] | 2026-06-22T10:44:49Z | mergeable=True state=unstable draft=False | pending; success:2 | Add dashboard runtime inside-out testing skill | live dashboard skill update, not duplicate ops-report |
| #661 | **NEEDS-REPAIR** | `devin/full-swarm-e2e-test-20260621` | False | devin-ai-integration[bot] | 2026-06-21T14:54:13Z | mergeable=True state=unstable draft=True | pending; cancelled:2, failure:1, success:26 | test: add full swarm organism e2e gauntlet report | draft/dirty/stale branch needs explicit repair before landing |
| #662 | **KEEP-AND-LAND** | `claude/seeing-organ-2je1gw` | False | AmitabhainArunachala | 2026-06-22T02:57:36Z | mergeable=True state=unstable draft=False | pending; failure:3, success:25 | feat(seeing-organ): Stage 0 safety substrate + Stage 1 Frontier Council verifier (the moat) | operator explicit keep-list |
| #663 | **KEEP-AND-LAND** | `devin/1782057657-markitdown-document-ingest` | False | devin-ai-integration[bot] | 2026-06-21T16:17:58Z | mergeable=True state=unstable draft=False | pending; failure:2, skipped:4, success:29 | Wire Chetana document ingest through MarkItDown | operator explicit keep-list |
| #664 | **CLOSE-STALE-DUPLICATE** | `ops/report-2026-06-21T1800Z` | False | AmitabhainArunachala | 2026-06-22T00:02:04Z | mergeable=True state=unstable draft=True | pending; failure:2, success:28 | chore(governance): ops report 2026-06-21T1800Z — spine 93.8%, 11 open PRs | ops/report metric lineage is superseded by canonical reconciliation ledger |
| #665 | **CLOSE-STALE-DUPLICATE** | `chore/refresh-spine-adoption-metric-20260622` | False | AmitabhainArunachala | 2026-06-22T06:03:28Z | mergeable=True state=unstable draft=True | pending; cancelled:1, failure:2, success:27 | chore(governance): refresh spine adoption metric 2026-06-22T0000Z — 93.8% | ops/report metric lineage is superseded by canonical reconciliation ledger |
| #666 | **CLOSE-STALE-DUPLICATE** | `chore/governance-spine-adoption-2026-06-22T0600Z` | False | AmitabhainArunachala | 2026-06-22T06:02:49Z | mergeable=True state=unstable draft=True | pending; failure:3, success:27 | chore(governance): refresh spine adoption metric 2026-06-22T0600Z — 93.8% | ops/report metric lineage is superseded by canonical reconciliation ledger |

### Governance Legibility Contradictions
- Local ACTIVE_TRACK declares `orientation-graph-2026-06` ACTIVE while origin/main has it CLOSED/SUPERSEDED by `truth-graph-platform-2026-06`.
- Local ACTIVE_TRACK is missing origin/main active tracks `truth-graph-platform-2026-06` and `provider-routing-consolidation-2026-06`.
- Origin/main is missing five local-only active tracks that exist only in local working tree/branches/stashes.
- PR #662 adds `seeing-organ-2026-06`, but origin/main does not have `dharma_swarm/world_radar/frontier_council.py` until that PR lands.
- Target union has 13 active tracks, exceeding both origin/main max_active=10 and local max_active=11 unless the operator explicitly changes policy or closes/archive tracks.
- Current reports/governance evidence is dirty in the working tree and must not be trusted as canonical until regenerated after union on clean committed origin/main.
- The previous `check_track_status.py` run failed because `runtime-truth-reconciliation-2026-06` was stale against its TTL; do not call the portfolio green until regenerated from the reconciled tree.
- The broken-register/dashboard/onboard family cannot agree while local ACTIVE_TRACK and origin/main ACTIVE_TRACK name different live portfolios.

### Cloud Cross-Check Reconciliation
- PR #662 branch topology: `git rev-list --left-right --count origin/main...origin/claude/seeing-organ-2je1gw` = `3	7`. This matches the cloud report (`3 behind / 7 ahead`).
- `agent-admission-semantic-commons-2026-06`: local_active=True, origin/main_present=False, PR_662_present=False.
- `cybernetics-codex-stewardship-2026-06`: local_active=True, origin/main_present=False, PR_662_present=False.
- `telos-ai-morning-refinery-2026-06`: local_active=True, origin/main_present=False, PR_662_present=False.
- `helm-worldclass-terminal-2026-06`: local_active=True, origin/main_present=False, PR_662_present=False.
- `a2a-cloud-agent-bridge-2026-06`: local_active=True, origin/main_present=False, PR_662_present=False.
- `dharma_swarm/world_radar/frontier_council.py`: origin/main present=False; PR #662 present=True. This confirms seeing-organ code is absent from origin/main and lands only with #662.

## Separate Test-Failure Track
This is not treated as a reconciliation cleanliness blocker. Prior smoke was interrupted at 69% after 21:39 with `48 failed, 8384 passed, 23 skipped, 10 xfailed, 2 xpassed`; pytest cache preserves 48 failing node ids.

Cached failing tests: **48**

```text
tests/properties/test_fitness_properties.py::test_fitness_perfect_score_is_one
tests/test_assurance.py::test_provider_scan_accepts_bare_claude_models_on_claude_code
tests/test_bootstrap_loops.py::test_task_lifecycle
tests/test_browser_agent.py::TestContextManager::test_context_manager_start_stop
tests/test_browser_agent.py::TestToolRegistryIntegration::test_browser_toolset_available
tests/test_browser_agent.py::TestToolRegistryIntegration::test_check_browser_available
tests/test_build_engine.py::TestValidation::test_passing_tests
tests/test_canonical_replay.py::test_canonical_replay_cli
tests/test_command_contract.py::TestTerminalCommandsPackage::test_no_module_exceeds_line_budget
tests/test_conductors.py::TestConductorConfigs::test_codex_config
tests/test_constitutional_size_check.py::test_constitutional_size_check_cli
tests/test_context_semantic.py::test_empty_semantic_hits_no_section
tests/test_context_semantic.py::test_semantic_hits_produce_section
tests/test_cybernetics_codex.py::test_loop_closure_track_requires_steward_packet
tests/test_daemon_config.py::test_daemon_config_defaults
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_docker_is_available
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_events_recorded
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_full_container_lifecycle
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_network_none_blocks_outbound
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_python_execution
tests/test_docker_sandbox.py::TestDockerSandboxIntegration::test_timeout_enforcement
tests/test_flywheel_exporter.py::test_flywheel_exporter_filters_session_events_when_trace_is_missing
tests/test_ginko_evolution.py::TestPromptTournament::test_mutate_prompt_no_api_key
tests/test_godel_claw_e2e.py::test_all_eleven_gates_fire
tests/test_integration.py::test_fitness_trend_after_multiple_cycles
tests/test_integration.py::test_parent_selection_from_populated_archive
tests/test_integration.py::test_telos_gates_in_evolution_harmful_blocked
tests/test_memory_integration.py::TestBackwardCompatibility::test_build_sections_accepts_knowledge_block
tests/test_memory_palace.py::TestLanceDBAdapter::test_connect_creates_db
tests/test_memory_palace.py::TestLanceDBAdapter::test_cross_session_persistence
tests/test_memory_palace.py::TestLanceDBAdapter::test_search_returns_results
tests/test_memory_palace.py::TestLanceDBAdapter::test_upsert_and_count
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_cross_session_recall
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_ingest_empty_content_no_lance_write
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_ingest_whitespace_only_no_lance_write
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_ingest_writes_to_lancedb
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_palace_connects_to_lancedb_with_state_dir
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_palace_connects_to_lancedb_without_state_dir
tests/test_memory_palace.py::TestMemoryPalaceLanceDB::test_stats_includes_lancedb
tests/test_memory_writer_sentinel.py::test_writer_sentinel_cli_action_required_gate_passes_for_triaged_repo
tests/test_memory_writer_sentinel.py::test_writer_sentinel_cli_ci_profile_runs_discovery_and_gates
tests/test_mode_pack.py::test_mode_pack_contract_loads
tests/test_monitor.py::test_check_health_mean_fitness
tests/test_monitor.py::test_fitness_regression_detected
tests/test_ollama_config.py::TestConstants::test_default_local_model
tests/test_orphan_reaper.py::TestReapOrphanedTasks::test_custom_stale_minutes_threshold
tests/test_orphan_reaper.py::TestReapOrphanedTasks::test_recently_updated_task_is_not_reaped
tests/test_orphan_reaper.py::TestTaskQueueSnapshot::test_queue_snapshot_counts_blocked_pending_tasks
```
## Phase 3 Plan — Do Not Run Without Operator Approval
| label | step | action |
|---|---|---|
| [SAFE] | Freeze the evidence | Do not modify any existing branch/stash. Keep this report uncommitted until the operator confirms the plan. |
| [NEEDS-OPERATOR-CONFIRM] | Push preservation refs for every stash | For each `stash@{n}`, create a named branch at `$(git rev-parse stash@{n})`, e.g. `archive/stash-20260622-00`, then `git push -u origin archive/stash-20260622-00`. This preserves stash commits without popping or dropping them. |
| [NEEDS-OPERATOR-CONFIRM] | Push/archive local-only branches | For each NO_REMOTE or UPSTREAM_GONE branch with unique commits, push a non-force archive ref such as `origin/archive/local-reconcile-20260622/<sanitized-branch>`. Do this before branch deletion or pruning decisions. |
| [NEEDS-OPERATOR-CONFIRM] | Snapshot current dirty checkout | Create a preservation branch from `telos-ai-seed-v0-from-sandbox`, commit all dirty/untracked work as a temporary snapshot, and push it. Then split it into track branches; do not reset or clean before this snapshot exists remotely. |
| [SAFE after clean snapshot] | Fast-forward local main | Because local `main` is 114 behind / 0 ahead with merge-base `86418541a`, use `git switch main` then `git merge --ff-only origin/main`. If counts change to ahead+behind, stop and preserve local main to `reconcile/local-main-pre-sync-20260622` before any merge/replay. |
| [NEEDS-OPERATOR-CONFIRM] | Land live remote PRs | Review and land #662 seeing-organ first, then #663 MarkItDown ingest. Keep them separate from ops-report cleanup. Re-run CI checks before merge. |
| [NEEDS-OPERATOR-CONFIRM] | Repair/archive other PRs | Close stale duplicate ops reports (#642, #645, #649, #653, #659, #664, #665, #666) after preserving any unique evidence in the reconciliation ledger. Repair #647 if still useful. Review #660/#661/#643 explicitly. |
| [NEEDS-OPERATOR-CONFIRM] | Create one pushed branch per local-only track | Use origin/main after #662/#663 as rebase target. Branches: `track/agent-admission-semantic-commons-20260622`, `track/cybernetics-codex-stewardship-20260622`, `track/telos-ai-morning-refinery-20260622`, `track/helm-worldclass-terminal-20260622`, `track/a2a-cloud-agent-bridge-20260622`. |
| [NEEDS-OPERATOR-CONFIRM] | Apply portfolio union | Edit `docs/governance/ACTIVE_TRACK.yaml` to include origin/main tracks + seeing-organ + kept local-only tracks. Resolve the 13-track WIP policy conflict by either raising `track_policy.max_active` with doctrine or closing/archiving selected tracks. Keep `orientation-graph-2026-06` closed/superseded unless operator deliberately reopens it. |
| [SAFE after union commit] | Regenerate governance evidence | Only after the union is committed, run `python3 scripts/governance/check_track_status.py`, inspect `reports/governance/active_track_evidence.md`, run `make onboard`, and check dashboard/broken-register agreement. |
| [SAFE after verification] | Fresh-clone verification | Fresh clone origin/main, run `make onboard`, verify ACTIVE_TRACK validates, no orphan branch remains unaccounted, no declared-owned surface is missing, and the 48 pytest failures remain tracked separately. |

## Raw Appendices
### `git status --porcelain=v2 --branch`
```text
# branch.oid cd610be3ccef9f7fff919cf8e36f32ca46f27b59
# branch.head telos-ai-seed-v0-from-sandbox
# branch.upstream origin/telos-ai-seed-v0-from-sandbox
# branch.ab +2 -0
1 .M N... 100644 100644 100644 c5c76eb35f788c34e47023b553180188bbf14355 c5c76eb35f788c34e47023b553180188bbf14355 .gitignore
1 .M N... 100644 100644 100644 0647ac79bd78336564ad3cb7d8b42fc870fde089 0647ac79bd78336564ad3cb7d8b42fc870fde089 CLAUDE.md
1 .M N... 100644 100644 100644 1c43503a40e830fe976d1b3f4ef58b79062e5698 1c43503a40e830fe976d1b3f4ef58b79062e5698 Makefile
1 .M N... 100644 100644 100644 e01b51c190c09caa0f06b11e47783f0d13b0d79e e01b51c190c09caa0f06b11e47783f0d13b0d79e PRODUCT_SURFACE.md
1 .M N... 100644 100644 100644 f2eff493b1296483b5ea82651dffa2b52cb6c375 f2eff493b1296483b5ea82651dffa2b52cb6c375 api/models.py
1 .M N... 100644 100644 100644 7af79fa78b7f865dd45298993567a339b466a561 7af79fa78b7f865dd45298993567a339b466a561 api/routers/health.py
1 .M N... 100644 100644 100644 559077aaa234649fac05fb67b87141c02f0b7238 559077aaa234649fac05fb67b87141c02f0b7238 com.dharma.swarm.plist
1 .M N... 100644 100644 100644 b4e78fa270428c3ce1f7a223d4fccf2d7e2b7346 b4e78fa270428c3ce1f7a223d4fccf2d7e2b7346 dashboard/src/hooks/useRuntimeControlPlane.ts
1 .M N... 100644 100644 100644 ddec35d605e55177a71dec2754b2bc6c30a83b33 ddec35d605e55177a71dec2754b2bc6c30a83b33 dashboard/src/lib/api.test.ts
1 .M N... 100644 100644 100644 73cabc325b3fa88edb024ec402451be9a189319e 73cabc325b3fa88edb024ec402451be9a189319e dashboard/src/lib/api.ts
1 .M N... 100644 100644 100644 066769e7e010991b5e514d6094987818546ec36b 066769e7e010991b5e514d6094987818546ec36b dashboard/src/lib/runtimeControlPlane.test.ts
1 .M N... 100644 100644 100644 f4ee6616e3ac3f94f63b7de7263b6e5d14b6a6b4 f4ee6616e3ac3f94f63b7de7263b6e5d14b6a6b4 dashboard/src/lib/runtimeControlPlane.ts
1 .M N... 100644 100644 100644 55226c008cd708d30f829c44a5c9280acd026c43 55226c008cd708d30f829c44a5c9280acd026c43 dashboard/src/lib/types.ts
1 .M N... 100644 100644 100644 ef1cc0c6d53ccc02271bcd1128d8894957226f67 ef1cc0c6d53ccc02271bcd1128d8894957226f67 dharma_swarm/agent_runner.py
1 .M N... 100644 100644 100644 f15b550c85a1368e0144a137870c46622846954b f15b550c85a1368e0144a137870c46622846954b dharma_swarm/autonomous_agent.py
1 .M N... 100644 100644 100644 e162a02bf6ac508517acb2f2e25bc3f93c565bb7 e162a02bf6ac508517acb2f2e25bc3f93c565bb7 dharma_swarm/cron_daemon.py
1 .M N... 100644 100644 100644 b3e1bc8e20f990a0f5363f670c791b399a3b78b9 b3e1bc8e20f990a0f5363f670c791b399a3b78b9 dharma_swarm/evolution.py
1 .M N... 100644 100644 100644 b1341fd953c39113885df80c6c6ef87b60b0efae b1341fd953c39113885df80c6c6ef87b60b0efae dharma_swarm/gaia_platform.py
1 .M N... 100644 100644 100644 459ccaf092ea9de3ef59db28397ba27bcab2377d 459ccaf092ea9de3ef59db28397ba27bcab2377d dharma_swarm/holon_health.py
1 .M N... 100644 100644 100644 9d380404206c161e70db8c1b6c40cea6e00f43db 9d380404206c161e70db8c1b6c40cea6e00f43db dharma_swarm/operator_core/control_surface_live_ops.py
1 .M N... 100644 100644 100644 2c1427d8a66afc97210fb9c7b497998b215c4b65 2c1427d8a66afc97210fb9c7b497998b215c4b65 dharma_swarm/operator_core/ds_goal_wrapper_contract.py
1 .M N... 100644 100644 100644 ed29a93dd517b79e06780b406fe5e53338f9567d ed29a93dd517b79e06780b406fe5e53338f9567d dharma_swarm/operator_core/world_radar/receipt_bridge.py
1 .M N... 100644 100644 100644 29cea1f18bee91b95ff51bd773f505cd2f85632e 29cea1f18bee91b95ff51bd773f505cd2f85632e dharma_swarm/opportunity_dispatcher.py
1 .M N... 100644 100644 100644 4e4fef7922f8ffe8d1e3935c1664a6c5d95604a5 4e4fef7922f8ffe8d1e3935c1664a6c5d95604a5 dharma_swarm/orchestrate_live.py
1 .M N... 100644 100644 100644 95b452ecca03b7dd7ccd7b7acab9be03aa59a44a 95b452ecca03b7dd7ccd7b7acab9be03aa59a44a dharma_swarm/orchestrator.py
1 .M N... 100644 100644 100644 f3d621d59b7ad631c96ef0f8eeeab8df50084f36 f3d621d59b7ad631c96ef0f8eeeab8df50084f36 dharma_swarm/palantir_pilot.py
1 .M N... 100644 100644 100644 6471d1e5c9c64cb5af8e76611bb6a7a43f19ecfb 6471d1e5c9c64cb5af8e76611bb6a7a43f19ecfb dharma_swarm/profiles.py
1 .M N... 100644 100644 100644 929ed084ea2c0d4183eb0995c3d1f9792d84b104 929ed084ea2c0d4183eb0995c3d1f9792d84b104 dharma_swarm/providers.py
1 .M N... 100644 100644 100644 5bf551bcd0fec76d9aa6be4e0d0b8c16a831ebc2 5bf551bcd0fec76d9aa6be4e0d0b8c16a831ebc2 dharma_swarm/pulse.py
1 .M N... 100644 100644 100644 e29b17a6d892e077c4aa95b72294ee33c312d38f e29b17a6d892e077c4aa95b72294ee33c312d38f dharma_swarm/runtime_lifecycle.py
1 .M N... 100644 100644 100644 0392183285d9f20ccc71001fd261822665084559 0392183285d9f20ccc71001fd261822665084559 dharma_swarm/runtime_state.py
1 .M N... 100644 100644 100644 026b2796803b1b1926ecf7401d7f7f108e8e8188 026b2796803b1b1926ecf7401d7f7f108e8e8188 dharma_swarm/swarm.py
1 .M N... 100644 100644 100644 0248c5da18a6f065f5fe3220f8a51e4958399699 0248c5da18a6f065f5fe3220f8a51e4958399699 dharma_swarm/swarm_health_api.py
1 .M N... 100644 100644 100644 d5da9786dcf7c098b3ed781d61094b7b8c76820d d5da9786dcf7c098b3ed781d61094b7b8c76820d dharma_swarm/telemetry_plane.py
1 .M N... 100644 100644 100644 534cbc8ca6623c622023c708d841ba3c4cfc2737 534cbc8ca6623c622023c708d841ba3c4cfc2737 dharma_swarm/terminal_bridge.py
1 .M N... 100644 100644 100644 8d0b21bd736916b9234640e4cd9ba7a082729daf 8d0b21bd736916b9234640e4cd9ba7a082729daf dharma_swarm/terminal_commands/_helpers.py
1 .M N... 100644 100644 100644 f5c2c0e70545c609409dc0b6daa15def834f28ba f5c2c0e70545c609409dc0b6daa15def834f28ba dharma_swarm/terminal_commands/diagnostics.py
1 .M N... 100644 100644 100644 1c4cc735fbc28e677fb1fc3f0bbed0458414438e 1c4cc735fbc28e677fb1fc3f0bbed0458414438e dharma_swarm/terminal_commands/lifecycle.py
1 .M N... 100644 100644 100644 0603c8dab2225c072536ff425c7c2e3b6626a005 0603c8dab2225c072536ff425c7c2e3b6626a005 dharma_swarm/vector_store.py
1 .M N... 100644 100644 100644 25858ec8578802e15484792c5dfba5e0df3d070c 25858ec8578802e15484792c5dfba5e0df3d070c dharma_swarm/world_model.py
1 .M N... 100644 100644 100644 195bde9495b2c47bd560467e23c172e65e3b6985 195bde9495b2c47bd560467e23c172e65e3b6985 dharma_swarm/yoga_node.py
1 .M N... 100644 100644 100644 c8b1414b57fba44349c83bbe6d12adc5cc2be1b7 c8b1414b57fba44349c83bbe6d12adc5cc2be1b7 docs/agents/palantir_pilot/MEMORY.md
1 .M N... 100644 100644 100644 fa338db77dcb4c7f88579f1c4dde2923c6734a8e fa338db77dcb4c7f88579f1c4dde2923c6734a8e docs/docops/AUTO_INVENTORY.md
1 .M N... 100644 100644 100644 43d011205baae8959b466783237f714ff1f4b05f 43d011205baae8959b466783237f714ff1f4b05f docs/governance/ACTIVE_TRACK.yaml
1 .M N... 100644 100644 100644 03a65ca8225d111ebfc10f8ad94bad13b4f2c73a 03a65ca8225d111ebfc10f8ad94bad13b4f2c73a docs/governance/CANONICAL_DOC_STACK.md
1 .M N... 100644 100644 100644 77dc246cf1f55a7985818a8a112f225a4e7a7bf2 77dc246cf1f55a7985818a8a112f225a4e7a7bf2 docs/governance/KAIZENOPS.md
1 .M N... 100644 100644 100644 c41ce4704a866319e3abdd29522441d6f7899b45 c41ce4704a866319e3abdd29522441d6f7899b45 docs/governance/SOVEREIGN_MANIFEST.md
1 .M N... 100644 100644 100644 9e255cf3b139d68d5a567d949be4053065637dcf 9e255cf3b139d68d5a567d949be4053065637dcf docs/governance/SWARM_GENOME.md
1 .M N... 100644 100644 100644 ba2c494924466b9fb687dd4725b1cbd419c88671 ba2c494924466b9fb687dd4725b1cbd419c88671 docs/governance/VENTURE_CELL_PORTFOLIO.yaml
1 .M N... 100644 100644 100644 113151bc4e10b3439fa9d3d6dbbd41b48e67248e 113151bc4e10b3439fa9d3d6dbbd41b48e67248e docs/ontology/SEMANTIC_COMMONS.md
1 .M N... 100644 100644 100644 e9be4a1e000a659e02608845da25ce2e655562c0 e9be4a1e000a659e02608845da25ce2e655562c0 docs/ontology/semantic_aliases.yaml
1 .M N... 100644 100644 100644 56f1da773d13edfdf18a03a30f379355aa4f3cce 56f1da773d13edfdf18a03a30f379355aa4f3cce docs/ontology/semantic_objects.yaml
1 .M N... 100644 100644 100644 1245707fbd694f71867763751796a4f46753c539 1245707fbd694f71867763751796a4f46753c539 docs/ontology/session_orientation.yaml
1 .M N... 100644 100644 100644 b936cfeb34fb8e78c268657dc2e1409a9152f038 b936cfeb34fb8e78c268657dc2e1409a9152f038 docs/ops/PR_REVIEW_CONTROL.md
1 .M N... 100644 100644 100644 30571e5085f845454037c35c230e66f724fb7750 30571e5085f845454037c35c230e66f724fb7750 docs/research/telos_ai/persona_agents/README.md
1 .M N... 100644 100644 100644 641eb20e23b5ce965f7dcb851a7228372f9038a4 641eb20e23b5ce965f7dcb851a7228372f9038a4 docs/vision_maps/NORTH_STAR.md
1 .M N... 100644 100644 100644 67b272056a799712514c72fd8eff853afa7be9f3 67b272056a799712514c72fd8eff853afa7be9f3 docs/vision_maps/TELOS_MORNING_REFINERY_V0.md
1 .M N... 100644 100644 100644 1ad332f333493aa8db2413bce8e90ff9fe94106f 1ad332f333493aa8db2413bce8e90ff9fe94106f holon/holon_bridge.py
1 .M N... 100644 100644 100644 e5c09a561ffb996a9bc7d2982898c130d96142c5 e5c09a561ffb996a9bc7d2982898c130d96142c5 holon/holon_runtime.py
1 .M N... 100644 100644 100644 2d5ea2da97efdf933622651db7dae7998739e44b 2d5ea2da97efdf933622651db7dae7998739e44b holon/memory_kernel/__init__.py
1 .M N... 100644 100644 100644 c87c5c5f658979bec7209e007621864c1eb28165 c87c5c5f658979bec7209e007621864c1eb28165 reports/governance/active_track_evidence.json
1 .M N... 100644 100644 100644 fc82d4a8dbefa44fc611b306045a7374706159bc fc82d4a8dbefa44fc611b306045a7374706159bc reports/governance/active_track_evidence.md
1 .M N... 100644 100644 100644 c87c5c5f658979bec7209e007621864c1eb28165 c87c5c5f658979bec7209e007621864c1eb28165 reports/governance/track_portfolio.json
1 .M N... 100644 100644 100644 bd8cc42677c26d3b502836400fcc9b53a4be4a73 bd8cc42677c26d3b502836400fcc9b53a4be4a73 scripts/com.dharma.cron-daemon.plist
1 .M N... 100644 100644 100644 8cef3d271b75946937cdee2bc6c01c192538cfb5 8cef3d271b75946937cdee2bc6c01c192538cfb5 scripts/governance/agent_admission.py
1 .M N... 100755 100755 100755 0d83e122a7996d76fb8a3641ca394cfb336c4f53 0d83e122a7996d76fb8a3641ca394cfb336c4f53 scripts/governance/agent_onboard.py
1 .M N... 100644 100644 100644 2d9194318929f35b65b04bb9034c5db31ead7d6b 2d9194318929f35b65b04bb9034c5db31ead7d6b scripts/governance/runtime_receipt_coverage_report.py
1 .M N... 100644 100644 100644 55a55c4d9f0e78b8eac7b297795c2d6a6978a14c 55a55c4d9f0e78b8eac7b297795c2d6a6978a14c scripts/governance/spine_dispatch_mode_report.py
1 .M N... 100644 100644 100644 af158b3e2e7f5f8abd13908c1caf67a9e1e67516 af158b3e2e7f5f8abd13908c1caf67a9e1e67516 scripts/runtime/a2a_inbox_bridge.py
1 .M N... 100644 100644 100644 b484509efb9255460eb22bc1e065c2d7e8bdf973 b484509efb9255460eb22bc1e065c2d7e8bdf973 scripts/runtime/live_ops_census.py
1 .M N... 100644 100644 100644 b46c2267f244a5179bd28cb28cde626e2b38cf4d b46c2267f244a5179bd28cb28cde626e2b38cf4d scripts/runtime/pr_merge_control.py
1 .M N... 100644 100644 100644 4aac38003d678b230302ebea569cecb9fb15f1c0 4aac38003d678b230302ebea569cecb9fb15f1c0 scripts/runtime/runtime_lifecycle_receipt_probe.py
1 .M N... 100755 100755 100755 034e8b70f0577f28214448508f317a36f1df8216 034e8b70f0577f28214448508f317a36f1df8216 scripts/verify_holon_harness_prod.py
1 D. N... 100644 000000 000000 0f96e8292bf093689337a9e89d5339f0427e9245 0000000000000000000000000000000000000000 synthesizer_memory.json
1 .M N... 100644 100644 100644 693edae19c113ba671ff4858021bbcfaa6864475 693edae19c113ba671ff4858021bbcfaa6864475 tests/test_a2a_inbox_bridge.py
1 .M N... 100644 100644 100644 6c0d903e5c5b843da140181a904ad156b8d2a3d9 6c0d903e5c5b843da140181a904ad156b8d2a3d9 tests/test_a2a_inbox_bridge_tmux_scripts.py
1 .M N... 100644 100644 100644 35bdc2644a6aded888f4826a0f055a6ecca9c5e3 35bdc2644a6aded888f4826a0f055a6ecca9c5e3 tests/test_agent_admission.py
1 .M N... 100644 100644 100644 4009bfd65b64119513415b0932511d291d685eec 4009bfd65b64119513415b0932511d291d685eec tests/test_agent_onboard.py
1 .M N... 100644 100644 100644 86df48f062eb99f4e2e59b478d31fbb9fe516541 86df48f062eb99f4e2e59b478d31fbb9fe516541 tests/test_agent_runner.py
1 .M N... 100644 100644 100644 fc3c2716309ab966457a6ea751b334f7650c160e fc3c2716309ab966457a6ea751b334f7650c160e tests/test_agent_runner_routing_feedback.py
1 .M N... 100644 100644 100644 b0aeea8757bcf20a31d98751d50da0138e692c03 b0aeea8757bcf20a31d98751d50da0138e692c03 tests/test_cron_daemon.py
1 .M N... 100644 100644 100644 781e0c87be016960529033bb4d4af42d68c730ac 781e0c87be016960529033bb4d4af42d68c730ac tests/test_dgc_cli.py
1 .M N... 100644 100644 100644 2a675d1f63ed7eb546f4367c1f0a551de891c91e 2a675d1f63ed7eb546f4367c1f0a551de891c91e tests/test_ds_goal_wrapper_receipt_probe.py
1 .M N... 100644 100644 100644 5738dcfcd4859aeef08726892b37f1d1e3e34661 5738dcfcd4859aeef08726892b37f1d1e3e34661 tests/test_evolution.py
1 .M N... 100644 100644 100644 561c7d9bfa81f52755884ff7cb75a4154225c42a 561c7d9bfa81f52755884ff7cb75a4154225c42a tests/test_gaia_platform.py
1 .M N... 100644 100644 100644 45cdfce79a8a7b51f7106363b9f82af0c8a1ecb9 45cdfce79a8a7b51f7106363b9f82af0c8a1ecb9 tests/test_go_world_signal_bridge.py
1 .M N... 100644 100644 100644 8c98de608adfae7cc270d4b28282ab606327bb8c 8c98de608adfae7cc270d4b28282ab606327bb8c tests/test_holon_health.py
1 .M N... 100644 100644 100644 009685f8258692f914353b0678a39cdb3f7a3f6f 009685f8258692f914353b0678a39cdb3f7a3f6f tests/test_live_ops_census.py
1 .M N... 100644 100644 100644 efa798b7839cec4eee5b90ca70cf6dabe09ae502 efa798b7839cec4eee5b90ca70cf6dabe09ae502 tests/test_model_router_telemetry.py
1 .M N... 100644 100644 100644 60758c7cf8244677947fc526a4c3dc2a4ffb2138 60758c7cf8244677947fc526a4c3dc2a4ffb2138 tests/test_orchestrate_live.py
1 .M N... 100644 100644 100644 b9e6d34432b43f894265b6c3342896187ff8c736 b9e6d34432b43f894265b6c3342896187ff8c736 tests/test_orchestrator_spine_dispatch.py
1 .M N... 100644 100644 100644 c9ac910a4baa89d540ca37ba49f169612e22d1a5 c9ac910a4baa89d540ca37ba49f169612e22d1a5 tests/test_orientation_graph.py
1 .M N... 100644 100644 100644 c994bb3bd4009f602846216757a063eb159751cc c994bb3bd4009f602846216757a063eb159751cc tests/test_pr_merge_control.py
1 .M N... 100644 100644 100644 833669614a0f380d5e20978dc5865471d97bf477 833669614a0f380d5e20978dc5865471d97bf477 tests/test_profiles.py
1 .M N... 100644 100644 100644 1a9e97c180991e77c391a41de26c8fc3b807573b 1a9e97c180991e77c391a41de26c8fc3b807573b tests/test_routing_surface_inventory.py
1 .M N... 100644 100644 100644 9b51aff8c9832606a94c0be167e21cf21af39e32 9b51aff8c9832606a94c0be167e21cf21af39e32 tests/test_runtime_lifecycle.py
1 .M N... 100644 100644 100644 7575cae6efe78ecfc61c432f944e7a32975200c9 7575cae6efe78ecfc61c432f944e7a32975200c9 tests/test_runtime_lifecycle_receipt_probe.py
1 .M N... 100644 100644 100644 cdcfc041bb3147b897e53c1697501b438fe0d3a2 cdcfc041bb3147b897e53c1697501b438fe0d3a2 tests/test_runtime_receipt_coverage_report.py
1 .M N... 100644 100644 100644 cb36042543232e030e7587d92bf0e8387be2fe81 cb36042543232e030e7587d92bf0e8387be2fe81 tests/test_runtime_state_invariants.py
1 .M N... 100644 100644 100644 22a08eeb572db54fe4e5b2e078a71ee9121e52aa 22a08eeb572db54fe4e5b2e078a71ee9121e52aa tests/test_semantic_commons.py
1 .M N... 100644 100644 100644 64f7107ae8540600dc52c366b563af71a9a4a1af 64f7107ae8540600dc52c366b563af71a9a4a1af tests/test_spine_dispatch_mode_report.py
1 .M N... 100644 100644 100644 bbb80a69af0567377e8fb8cc5ee728957d834235 bbb80a69af0567377e8fb8cc5ee728957d834235 tests/test_swarm.py
1 .M N... 100644 100644 100644 09b457d8e94ddfc53cc9779d47205638d578afd2 09b457d8e94ddfc53cc9779d47205638d578afd2 tests/test_swarm_health_api.py
1 .M N... 100644 100644 100644 331cdd5929b28221ca25702d7e19730a7e28ca3c 331cdd5929b28221ca25702d7e19730a7e28ca3c tests/test_terminal_bridge.py
1 .M N... 100644 100644 100644 0e11eb8c681f6225883fbe8d6fff2a4bbba5001e 0e11eb8c681f6225883fbe8d6fff2a4bbba5001e tests/test_vector_store.py
1 .M N... 100644 100644 100644 91dda4f90f3914874258eacf33e8ff08b70b8a3f 91dda4f90f3914874258eacf33e8ff08b70b8a3f tests/test_world_model.py
1 .M N... 100644 100644 100644 30a91d575fa2b75b83dbb5da718575a7c47a4242 30a91d575fa2b75b83dbb5da718575a7c47a4242 tests/test_yoga_node.py
? .github/workflows/runtime-truth.yml
? HOLON_CODICES_SYNTHESIS.md
? HOLON_SUBSTRATE_PROOF.md
? HOLON_SUBSTRATE_SYNTHESIS.md
? S3_S4_GATE_BLOCK_ANALYSIS.md
? a2a-polish-mission/
? dharma_swarm/a2a/a2a_cloud_contact.py
? dharma_swarm/a2a/contact_registry.py
? dharma_swarm/a2a/verifier.py
? dharma_swarm/gaia_initiative.py
? dharma_swarm/holon_l4_activation.py
? dharma_swarm/holon_l4_model_probe_lease.py
? dharma_swarm/holon_l4_orchestration_runtime.py
? dharma_swarm/holon_l4_service.py
? dharma_swarm/holon_l4_smoke.py
? dharma_swarm/holon_l4_supervisor.py
? dharma_swarm/holon_orchestrate.py
? dharma_swarm/holon_service_liveness.py
? dharma_swarm/holon_transport_liveness.py
? dharma_swarm/insight_evolution_bridge.py
? dharma_swarm/palantir_pilot_manifest.py
? dharma_swarm/palantir_pilot_query.py
? dharma_swarm/runtime_context.py
? docs/agent_tasks/2026-06-17_forge_v0_10x_measurement_goal_handoff.md
? docs/agent_tasks/2026-06-18_six_agent_swarm_uplift_critique_goal.md
? docs/agents/codex_telos/
? docs/agents/factory_droid/
? docs/architecture/A2A_CLOUD_BRIDGE.md
? docs/governance/hygiene/baselines/2026-06-18.txt
? docs/missions/2026-06-20_jagat_kalyan_gaia_execution_spine.md
? docs/research/telos_ai/empire_agents/
? docs/research/telos_ai/persona_agents/07_ATTENTION_ECOLOGIST.md
? docs/research/telos_ai/persona_agents/08_MACHINE_MIND_ETHICIST.md
? docs/research/telos_ai/persona_agents/CANONICAL_COUNCIL.md
? docs/vision_maps/ALIVE_ORGAN_MAP_2026-06-18.svg
? holon_l4_substrate_proof.md
? reports/a2a/A2A_MASTER_SPEC_WORKING_STATE_20260617.md
? reports/a2a/A2A_ROLLCALL_TRIPLE_CONFIRMATION_20260617.md
? reports/a2a/codex_holon_always_live_upgrade.md
? reports/governance/local_reconciliation_2026-06-22.md
? reports/governance/name_drift_preflight_codex_telos.md
? reports/sovereign_holons/L4_HOLON_SUBSTRATE_HYGIENE_AND_SMOKE_20260618.md
? reports/sovereign_holons/l4_memory_write_receipts.jsonl
? reports/state/a2a_score_denominator.md
? roaming_mailbox/tasks/mbx_a2a_spec_signoff_devin_20260617.json
? roaming_mailbox/tasks/mbx_a2a_spec_signoff_perplexity_20260617.json
? scripts/holon_l4_activation.py
? scripts/holon_l4_model_probe_lease.py
? scripts/holon_l4_service.py
? scripts/holon_l4_smoke.py
? scripts/holon_l4_supervisor.py
? scripts/research/palantir_deep_ingest.py
? scripts/research/palantir_domain_submaps.py
? scripts/runtime/daemon_operator_status.py
? scripts/runtime/mark_runtime_truth_clean_epoch.py
? scripts/runtime/runtime_task_backlog_firebreak.py
? scripts/runtime/runtime_truth_100_audit.py
? scripts/runtime/runtime_truth_burn_in.py
? scripts/runtime/runtime_truth_closeout.py
? scripts/start_a2a_inbox_bridge_fleet_launchd.sh
? scripts/status_a2a_inbox_bridge_fleet_launchd.sh
? scripts/stop_a2a_inbox_bridge_fleet_launchd.sh
? tests/test_a2a_cloud_contact.py
? tests/test_daemon_operator_status.py
? tests/test_dashboard_health_route.py
? tests/test_holon_l4_activation.py
? tests/test_holon_l4_model_probe_lease.py
? tests/test_holon_l4_service.py
? tests/test_holon_l4_smoke.py
? tests/test_holon_l4_supervisor.py
? tests/test_holon_orchestrate.py
? tests/test_holon_service_liveness.py
? tests/test_holon_transport_liveness.py
? tests/test_insight_evolution_bridge.py
? tests/test_runtime_context.py
? tests/test_runtime_task_backlog_firebreak.py
? tests/test_runtime_truth_100_audit.py
? tests/test_runtime_truth_burn_in.py
? tests/test_runtime_truth_clean_epoch.py
? tests/test_runtime_truth_closeout.py
? tests/test_telos_morning_refinery.py
```
### `git branch -vv`
```text
  _rebase_tmp                                                  31f0b8d1a [origin/codex/toolbelt-onboarding: gone] fix(docops): correct manifest counts from docops metrics
  _rtmp                                                        eb6d8d883 [origin/devin/1779503110-staging-promote-hermes-wiring: gone] fix(ops): restrict review mark authority to operator [impact-checked]
  archive/trust-build-compass-20260605                         4bb47aedd docs(operator-os): close eight-hour mission
  audit/runtime-truth-2026-04-26                               60666c387 fix(runtime): normalize executive campaign datetimes [impact-checked]
  backup/memory-kernel-prep-2026-05-14                         b14bea571 feat(memory): add context shadow sweep [impact-checked]
  backup/route-witness-main-pre-rebase-2026-05-13              caf59efc2 feat(routing): add route witness telemetry [impact-checked]
  backup/route-witness-pr297-pre-rebase-2026-05-13             7b2c08f9d docs(docops): refresh route witness inventory [impact-checked]
  base/brief-to-spec-seam-018ef60                              018ef604a feat(build): brief_to_spec — synthesis→action seam + pilot00 pipeline
+ cashclaw/revenue-hydra-v1                                    c487d2725 (/Users/dhyana/dharma_swarm_cashclaw) [origin/cashclaw/revenue-hydra-v1] scan: add farm detection (0-merge repos flagged as DO NOT CLAIM)
  chore/action-authority-gate-spec                             32e3eb224 [origin/main: ahead 5, behind 803] fix(governance): restore local telic seam writeback
  chore/agentops-base-check                                    b2ef97684 test(governance): use active python for cli subprocesses
  chore/agentops-v0                                            a36b445b2 chore(agentops): add governed work packet runner
  chore/authority-ptr-rollup                                   25a02e555 [origin/main: ahead 8, behind 798] docs(governance): register ptr state ownership
  chore/brake-stabilization                                    d8a5cdcb0 docs(cleanup): preserve current audit and control maps
  chore/capsule-coherence-tool                                 cc135f624 chore(governance): add capsule coherence report
  chore/command-plane-nav-trim                                 b7ab21759 [origin/chore/command-plane-nav-trim: ahead 15] feat(cockpit): consume /api/manifest/command-plane via CommandPlaneTruthPanel
  chore/control-plane-stabilizer                               d514f6ae1 fix(control): restore CLI collection compatibility
  chore/core-four-ontology-phase3                              5339d5091 feat(ontology): add core four value metrics
  chore/current-truth-refresh                                  ec74ee0c6 [origin/main: ahead 8, behind 779] docs(governance): refresh current repo truth
  chore/daily-brief-discovery-agentops                         e4aa01e71 chore(agentops): add governed work packet runner
  chore/docops-integrity-v0                                    93132013f docs(docops): add semantic codec readiness plan
  chore/docops-ttl-renewal-20260612                            4c65f017e [origin/chore/docops-ttl-renewal-20260612: gone] chore(docops): re-verify assertions, renew TTL 2026-06-12
  chore/governance-truth-repairs                               70908ab53 fix(governance): sharpen assurance truth signals
  chore/invariant-daily-insight-seam                           5dd1dfb5d fix(telic): preserve proposal linkage for insight chain
  chore/kaizen-review-v0                                       f01b79851 chore(kaizen): add AgentOps review report
  chore/kimi-claw-agentops-task                                e4aa01e71 chore(agentops): add governed work packet runner
  chore/loop1-truth-registry                                   b329e1abe docs(governance): overlay current loop1 truth maps
  chore/memory-tail-proof                                      56b92d359 fix(telic): preserve agent runner proposal linkage
  chore/opportunity-dispatcher-budget-fix                      94f79b407 fix(governance): route local semgrep through ca wrapper
  chore/opportunity-dispatcher-budget-surgeon                  cd71d5d1a refactor(opportunity): extract dispatcher support capsules
  chore/phase2-governance-checkpoint                           0ba34f6b9 test(observability): isolate local trace store
  chore/phase2-governance-rollup                               e4aa01e71 [origin/chore/phase2-governance-rollup: ahead 2] chore(agentops): add governed work packet runner
  chore/phase2-governance-rollup-core-four                     74d14cba1 feat(ontology): add core four value metrics
  chore/phase2-test-verify                                     94f79b407 fix(governance): route local semgrep through ca wrapper
  chore/repo-runway-daily-brief-seam                           bb64f2dcc [origin/main: ahead 1, behind 754] feat(ops): add repo cleanup pressure cockpit [structural-delete-approved]
  chore/semgrep-high-risk-batch                                fba32965d fix(governance): remove high-risk command and eval sinks
  chore/semgrep-rule-scope                                     5aa592bb6 fix(governance): exclude semgrep test rules from local scans
  chore/semgrep-triage                                         94f79b407 fix(governance): route local semgrep through ca wrapper
  chore/state-authority-map                                    94f79b407 fix(governance): route local semgrep through ca wrapper
  chore/telic-seam-budget-exception                            c71db6e74 chore(governance): grandfather telic seam budget
  chore/uplift-guard-recovery                                  1f97b446a fix(governance): restore uplift guard runner
  cleanup/action-authority-salvage-2026-05-13                  afc962e22 chore(cleanup): preserve action authority runtime wiring [impact-checked]
  cleanup/agent-truth-spine-salvage-2026-05-13                 64f86b4bd chore(cleanup): preserve agent truth spine lane [impact-checked]
  cleanup/brake-stabilization-salvage-2026-05-13               1976329e1 chore(cleanup): preserve brake stabilization residue [impact-checked]
  cleanup/core-operating-circuit-proof-salvage-2026-05-13      ac21e6fae chore(cleanup): preserve core operating circuit proof [impact-checked]
  cleanup/go-local-model-runtime-inventory-salvage-2026-05-13  9919a1f4f chore(cleanup): preserve go local model inventory lane [impact-checked]
  cleanup/kaizen-review-v0-salvage-2026-05-13                  be2571eae chore(cleanup): preserve kaizen review human yds lane [impact-checked]
  cleanup/main-dirty-salvage-2026-05-12                        49248cae1 chore: preserve dirty main work for triage
  cleanup/main-late-dirty-salvage-2026-05-12                   77aba9243 chore(cleanup): preserve late dirty main work
  cleanup/main-recurring-live-salvage-2026-05-13               9848011cf chore(cleanup): preserve recurring live main residue [impact-checked]
  cleanup/memory-kernel-context-eval-2026-05-13                71ca01d72 feat(memory): shadow context reads and sentinel ci [impact-checked]
  cleanup/memory-kernel-shadow-context-main-2026-05-13         b1d20ccb3 [origin/main: ahead 6, behind 581] fix(memory): require strict readiness in operator smoke [impact-checked]
  cleanup/mixed-quality-recovery-2026-05-10                    ddd674d5a [origin/cleanup/mixed-quality-recovery-2026-05-10: ahead 4] feat(selection): catalytic-graph parent-selection bias (spine §9 closure) [impact-checked]
  cleanup/module-metabolism-strategy-salvage-2026-05-13        e28a4bbd2 docs(cleanup): preserve core four ontology strategy notes [impact-checked]
  cleanup/opportunity-dispatcher-budget-fix-salvage-2026-05-13 2593169b9 chore(cleanup): preserve opportunity dispatcher budget lane [impact-checked]
  cleanup/root-memory-context-salvage-2026-05-13               2427abe0f chore(memory): preserve context admission residue [impact-checked]
  cleanup/root-mixed-salvage-2026-05-12                        8a083dcd2 chore(cleanup): preserve late root residue
  cleanup/runtime-result-projector-salvage-2026-05-13          4666be110 chore(cleanup): preserve runtime result projector lane [impact-checked]
  cleanup/viz-invariant-projection-2026-05-12                  3d0868587 feat(viz): project invariant measurements [impact-checked]
  codex/cyber-loop-closure-provider-truth-20260619             5910bf17d [origin/codex/cyber-loop-closure-provider-truth-20260619: gone] test: make run daemon script test repo-relative
  codex/exec10-lf5                                             dd53c8a46 fix(guardian): dataclass auto-init detection — eliminates false-positive BLOCKER
  codex/fix-docops-autorefresh-dispatch-20260605               a6561b3f6 [origin/codex/fix-docops-autorefresh-dispatch-20260605: gone] fix(ci): repair docops autorefresh dispatch
  codex/fix-docops-autorefresh-repo-arg-20260605               6fecf9624 [origin/codex/fix-docops-autorefresh-repo-arg-20260605: gone] fix(ci): resolve docops manual dispatch repo context
  codex/fix-pr-398-coherence                                   a39fde863 [origin/perplexity-computer/reply-to-claude-four-layer-stack: gone] docs: refresh docops counts for perplexity reply
  codex/go-idea-spark-ingest-spine-clean-20260604              0fe69fc3d [origin/codex/go-idea-spark-ingest-spine-clean-20260604: gone] chore(go-ingest): satisfy CI governance gates
+ codex/governance-fitness-ci-20260620                         c69f1cf05 (/Users/dhyana/ds_governance_fitness_ci_20260620) [origin/codex/governance-fitness-ci-20260620: behind 89] test: read daemon script from checkout
  codex/live-ops-cockpit-v1                                    03c077ece [origin/codex/live-ops-cockpit-v1: gone] chore(ops): satisfy live cockpit PR gates
  codex/live-ops-cockpit-v1-docops-fix                         8c5c27bb4 [origin/codex/live-ops-cockpit-v1: gone] chore(ops): fix live cockpit docops gate
  codex/live-ops-cockpit-v1-docops-fix-mainbase                dd47d7f00 [origin/main: ahead 3, behind 359] chore(ops): fix live cockpit docops gate
  codex/live-ops-cockpit-v2-slice-a                            8f67f8630 [origin/main: ahead 4, behind 359] feat(ops): add live ops state authority model
  codex/live-ops-cockpit-v2-slice-b                            27861e0bc feat(ops): project PR queue into live cockpit
  codex/live-ops-cockpit-v2-slice-c                            1d2049d3c feat(ops): add live ops proposal packets
  codex/main-review-blockers                                   7893937e3 [origin/codex/main-review-blockers: gone] fix(security): close post-574 review blockers
  codex/memory-kernel-default-context-20260523                 0b0cd8b9a [origin/codex/memory-kernel-default-context-20260523: gone] Merge remote-tracking branch 'origin/main' into codex/memory-kernel-default-context-20260523
  codex/pr388-disambig                                         f24a2adf3 [origin/devin/2026-05-30-receipt-disambiguation: gone] test(receipts): add pr388 merge proof
  codex/pr408-schema-align                                     598f05643 [origin/perplexity/2026-06-01-schema-alignment-gate: gone] fix(governance): distinguish stale ontology branches
  codex/pr409-oms-hardening                                    0f2525880 [origin/devin/1780259643-oms-hardening: gone] fix(ontology): preserve adapter idempotency
  codex/pr468-docops-clean                                     7a19c7c3e [origin/docs/runtime-truth-spine-plan-and-vel-rfc: gone] docs(spine): resolve #468 DocOps conflicts after matrix merge
  codex/pr470-after-468-fix                                    a2a92a246 [origin/devin/1780551922-spine-a2a-hardening: gone] merge main into #470 after spine RFC merge
  codex/pr470-docops-review                                    043c27037 [origin/devin/1780551922-spine-a2a-hardening: gone] docs(spine): refresh DocOps counts after invariant tests
  codex/pr546-main-sync                                        ba4c7700f [origin/chore/hygiene/evidence-snapshots-to-release: gone] merge main into evidence snapshot lane after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
  codex/pr558-main-sync                                        09954a5cf [origin/governance/ws4-gate-pep: gone] merge main into telos gate lane after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
  codex/pr562-main-sync                                        c1c4b4bf7 [origin/fix/evolution-archive-honesty: gone] merge main into evolution archive honesty [impact-checked] [large_diff_ack] [structural-delete-approved]
  codex/pr564-main-sync                                        7d2cdc6b6 [origin/devin/honest-spine-handoff-20260611: gone] merge main into honest spine handoff after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
  codex/pr570-orientation-fixes                                ebf11a792 docs: harden north star orientation receipts
  codex/pr574-codeql-tests                                     3a813a798 [origin/qwen/spine-adoption: gone] governance: re-render ACTIVE_TRACK managed block after main sync (gate: no drift) [impact-checked]
  codex/pr578-main-sync                                        1b843a3f4 [origin/feat/trust-gate-scoreboard: gone] merge main into trust gate scoreboard lane [impact-checked] [large_diff_ack] [structural-delete-approved]
  codex/pr578-main-sync2                                       582137c5e [origin/feat/trust-gate-scoreboard: gone] merge main into trust gate scoreboard after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
  codex/pr584-main-sync                                        ab49f6dc0 [origin/copilot/close-duplicate-prs-and-enable-automerge: gone] merge main into automerge dedupe lane [impact-checked] [large_diff_ack] [structural-delete-approved]
  codex/pr586-main-sync                                        d85b525cd [origin/codex/truth-graph-v1: gone] merge main into truth graph platform after automerge lane [impact-checked] [large_diff_ack] [structural-delete-approved]
  codex/repair-pr-392                                          236e9e8ef fix(guardian): refresh docops after dedup tests
  codex/repair-pr-399                                          066157dd9 docs(track): refresh proposed cloud bridge docops
  codex/runtime-truth-nats-adapter-20260606                    cee160f24 [origin/codex/runtime-truth-nats-adapter-20260606: gone] chore(governance): refresh spine metric after NATS ack fix
  codex/toolbelt-onboarding                                    8fc17f2bc [origin/codex/toolbelt-onboarding: gone] docs(ops): publish Codex toolbelt onboarding
  codex/truth-graph-v1                                         1c0a25a39 [origin/codex/truth-graph-v1: gone] feat(governance): add truth graph platform projection
  complexity-stress/replay-metamorphic-v1                      9c8d75c92 [origin/complexity-stress/replay-metamorphic-v1: gone] Clarify replay metamorphic fixture invariant
  copilot/close-duplicate-prs-and-enable-automerge             b26d69e30 [origin/copilot/close-duplicate-prs-and-enable-automerge: gone] fix(ci): harden automerge governance lane [impact-checked]
  cutover/lf5-runtime-on-main-20260510-integrate-main          4a31d0e78 feat(runtime): port lf5 daemon spine onto main cutover [impact-checked] [structural-delete-approved]
  daemon-lane-upgrade-20260616                                 69fda66ee feat(daemon): versioned provenance soak candidate [impact-checked] [large-diff-ack]
  daemon-versioning/v0.0.1                                     bfd09a769 [origin/main: ahead 1, behind 197] feat(versioning): v0.0.1 soak-testable promote-on-verified-metrics scaffold
  dashboard-lf5-operator-lane                                  9d6a34500 lf5: Live Fire 5 results — gauntlet baseline established
  devin/1778035620-wire-fractal-runtime                        28823aa90 fix(fractal): make runtime room wiring explicit [impact-checked]
  devin/1778037205-marathon-cleanup                            c5f138117 [origin/devin/1778037205-marathon-cleanup: gone] docs: refresh DocOps counts (556 modules, 567 test files, 688 md files) [impact-checked]
  devin/1778426210-ship-revenue-wedge-report                   e447becf2 docs: refresh revenue wedge docops counts [impact-checked]
  dgc-splash-art                                               36d55d9da fix(tui): pipe bridge stderr to prevent double-render corruption
  docs/adr-008-ontology-api-grammar                            ec4b4fb39 [origin/docs/adr-008-ontology-api-grammar: gone] docs(adr): ADR-008 — resolve open-Q3 sibling api_name conventions (Palantir-grounded)
  feat/a2a-correlation-spine-phase2a                           98d9cf416 [origin/main: ahead 3, behind 444] docs(a2a): correlation spine architecture anchor note
  feat/brief-to-spec-seam-2026-05-07                           e3d1eb997 [origin/feat/brief-to-spec-seam-2026-05-07: ahead 1] docs(state): record post-cron verification
  feat/codex-lane-runner-2026-05-13                            8c2629ad4 [origin/main: ahead 3, behind 583] fix(codex-lane): close subprocess stdin
  feat/cwt-v0-collector                                        242b67ce2 [origin/feat/cwt-v0-collector: gone] feat(governance): CWT v0 read-only collector + report renderer [impact-checked]
  feat/governed-memory-recursive-preflight                     8dca25eab [origin/main: ahead 7, behind 581] feat(governance): integrate recursive memory preflight proof [impact-checked]
  feat/inquiry-chain-phase1                                    d8a5cdcb0 docs(cleanup): preserve current audit and control maps
  feat/ontology-telos-gate-hardwire                            592e7af48 [origin/main: ahead 20, behind 436] docs(governance): refresh telos count stamp
  feat/runtime-result-projector                                ddd674d5a feat(selection): catalytic-graph parent-selection bias (spine §9 closure) [impact-checked]
  feat/trust-gate-scoreboard                                   7e823c7f6 [origin/feat/trust-gate-scoreboard: gone] chore: drop unused import (pyright)
  feat/world-radar-live-integration-2026-05-13                 1ff15b98d [origin/main: ahead 1, behind 585] feat(world): consolidate live radar shakti telos lane [impact-checked]
  feat/world-radar-shakti-telos-2026-05-13                     be5ef013e feat(world): preserve radar shakti telos build lane [impact-checked]
  feat/world-radar-shakti-telos-docs-tests-2026-05-13          4c4eeb01c docs(world): preserve zeitgeist docs test residue [impact-checked]
  feat/world-radar-shakti-telos-final-residue-2026-05-13       b913b957a feat(world): preserve final scoring zeitgeist residue [impact-checked]
  feat/world-radar-shakti-telos-followup-2026-05-13            0200888a4 feat(world): preserve recurring signal followup [impact-checked]
  feat/world-radar-shakti-telos-live-2026-05-13                b6e0342e0 feat(world): preserve live recurring radar state [impact-checked]
  feat/world-radar-shakti-telos-residual-2026-05-13            86d1c0330 feat(world): preserve runtime residual wiring [impact-checked]
  fix/evolution-archive-honesty                                f8fb428bc [origin/fix/evolution-archive-honesty: gone] Merge remote-tracking branch 'origin/main' into fix/evolution-archive-honesty
  fix/provider-honesty-g6                                      8e086e092 [origin/fix/provider-honesty-g6: gone] providers_extended: route Ollama generate, NVIDIA NIM, Moonshot through honest extractor
  fix/runtime-spine-audit-followups                            551b88e21 gov(runtime-receipt): sanctioned fixture quarantine excludes fixture rows from 70->75 score gate
+ forge-v1/tokenbroker-scoreboard-20260620                     d8bca7aab (/Users/dhyana/ds_forge_v1_scoreboard) [origin/main: ahead 9, behind 114] forge-v1: REAL coordinated multi-model coding agent (PLAN->BUILD->VERIFY)
  forge/dharma-reward-forge-v0                                 236006e54 feat(forge): Dharma Reward Forge v0 — close the sealed-task loop
  governance/parallel-lane-policy-2026-06-06                   3ff3d44b4 governance: support 1-10 active_tracks (schema v2, primary alias)
  governance/ws3-spine-dispatch                                b930a9578 [origin/governance/ws3-spine-dispatch: gone] spine: route orchestrator dispatch through invoke_agent behind flag (WS3) [impact-checked]
  governance/ws4-gate-pep                                      5d333431e [origin/governance/ws4-gate-pep: gone] telos: enforce gate on REVIEW-decision self-mods (WS4a) [impact-checked]
+ helm/worldclass-20260612                                     680b013c0 (/Users/dhyana/dharma_helm_build) [origin/helm/worldclass-20260612: ahead 57] helm(theme): Nihonga Mineral palette — bold mineral pigments on warm sumi-black
  holarchy/crossfalsify-20260619                               d2dd09ad5 [origin/main: ahead 1, behind 114] holarchy: Falsifiable Holarchy cross-falsification primitive (the acceptance test, as running code)
  integrate/chetana-grand-memory-2026-05-02                    c509d4e8e [origin/integrate/chetana-grand-memory-2026-05-02: ahead 13, behind 2] feat(governance): add ptr shadow metric
  lane/cybernetics-codex                                       b278bf4a6 [origin/main: ahead 1, behind 197] landing(cybernetics-codex): stewardship agent charter + audit/registration + tests
  lane/leftover-telos-cockpit                                  e231fce0c [origin/main: ahead 1, behind 197] landing(telos-cockpit): morning-refinery persona council + vision map + product surface
  lane/loop-closure-reconciled                                 12793ebd5 loop-closure: graft Opus all-night closure harness onto Fable phase1b [docops-resync; additive manifest drift]
  lane/palantir-pilot                                          80f06814c [origin/main: ahead 1, behind 197] landing(palantir-pilot): pilot agent + research toolchain (separate lane, no track)
  lane/runtime-spine-hardening                                 1e6668d7c [origin/main: ahead 1, behind 197] landing(runtime-spine): runtime core + receipt/provenance + live-ops + A2A + governance evidence
  lane/untangle-manifest                                       6c7e2b1cd [origin/main: ahead 1, behind 197] docs(governance): UNTANGLE_MANIFEST for cc9c05f21 segmentation
  lf5-live-fire-clean                                          dd53c8a46 [origin/lf5-live-fire-clean: ahead 25] fix(guardian): dataclass auto-init detection — eliminates false-positive BLOCKER
  loop-closure/phase1b-2026-06                                 c540f2edf [origin/loop-closure/phase1b-2026-06: gone] loop-closure: campaign RETROSPECTIVE — what the map predicted vs reality (5th criterion)
+ loop-closure/supplychain-bronze-20260620                     11de04fb7 (/Users/dhyana/ds_supplychain_slice) [origin/loop-closure/supplychain-bronze-20260620: gone] loop-closure: close thin supply chain loop [impact-checked]
  main                                                         86418541a [origin/main: behind 114] Merge pull request #633 from AmitabhainArunachala/devin/1781768310-stop-noise-prs-automerge-botpr
  merge-master/pr399-restack                                   5d5711b3c [origin/main: ahead 3, behind 407] docs(governance): restack cloud bridge proposal [impact-checked]
  merge-master/pr411-restack                                   aeabeec3f [origin/main: ahead 2, behind 413] chore(inter-agent): restack inbound status after outbound merge [impact-checked]
  merge-master/pr435-restack                                   0e2ed53b3 [origin/main: ahead 4, behind 403] feat(spine): restack adapter saturation slice [impact-checked]
  merge-master/pr436-restack                                   b122f276c [origin/main: ahead 4, behind 401] feat(spine): restack mapping receipt slice [impact-checked]
  migration/old-machine-main                                   662b16dd7 feat(dashboard): Phase 1 Hokusai — indigo depths, telemetry strip, sharp panels
  mmm-nats-aiohttp                                             eb9d8fa81 [origin/mmm-nats-aiohttp: gone] fix: install aiohttp for Mike NATS websocket
  mmm-nats-ca-pem                                              2eb6133d8 [origin/mmm-nats-ca-pem: gone] fix: trust private CA for Mike NATS fanout
  mmm-nats-mike-credentials                                    ab3fe2006 [origin/mmm-nats-mike-credentials: gone] fix: use Mike NATS credentials for backlog fanout
  mmm-nats-publish-deadline                                    a32127ab7 [origin/mmm-nats-publish-deadline: gone] fix: bound Mike A2A publish deadline
  mmm-pin-actions                                              fbc3a4e11 [origin/mmm-pin-actions: gone] fix: pin Mike workflow actions
  mmm-visible-backlog-router                                   11f68953b [origin/mmm-visible-backlog-router: gone] Make Mike mentions visibly route backlog requests
  model-routing/nim-bleeding-edge-20260618                     8ac5118ca [origin/main: ahead 1, behind 141] model-routing: fix dead NIM routes + expand to wide bleeding-edge selection [impact-checked]
+ model-routing/nim-live-catalog-fix-20260620                  4394d81b2 (/private/tmp/dharma_nim_main_check) [origin/model-routing/nim-live-catalog-fix-20260620: gone] model-routing: fix NVIDIA DeepSeek catalog route
  organ/00-floor                                               af7991aab fix(floor): unblock dispatch — bound workspace scan, satisfy think-point, non-bare pulse (H02 P1) [impact-checked]
  organ/02-wounds                                              f3c926490 fix(wounds): test fixtures no longer pollute the production witness stream (H02 P3.8) [impact-checked]
+ organ/03-seat                                                e67b91829 (/Users/dhyana/dharma_swarm_live) [origin/organ/03-seat] docs(handoffs): H02 divergence audit harvested — 6/6 claim families VERIFIED, kill test re-run green (discharges ESCALATION-6)
  pr-344-backlog                                               2076897a7 chore(docops): refresh counts for PR344 rebase
  pr-384-backlog                                               3f0497add chore(docops): refresh counts for PR384 rebase
  pr-388-backlog                                               807040cc0 chore(docops): refresh counts for PR388 rebase
  pr-406-review-20260531                                       d960d2fb6 feat(ontology): hard-wire telos gate into execute_action (W1)
  pr-465-backlog                                               8ea05b1f9 chore(ops): repair live cockpit rebase gates
  pr-474-backlog                                               c33d8758b chore(docops): refresh counts for PR474 rebase
  pr-495-backlog                                               489f51ad8 chore(mike): retrigger coherence delta
  qwen/spine-adoption                                          d87edb5d4 [origin/qwen/spine-adoption: gone] ummm, just randomly starting a new codex chat and it happened to be in qwen, if anyone sees this find out what is not clean and metabolized from qwen and next time clean it up and see if we can close the branch if it is backed up and saved on main
  repair/pr-325-toolbelt                                       548123e10 [origin/codex/toolbelt-onboarding: gone] Merge remote-tracking branch 'origin/main' into repair/pr-325-toolbelt
  repair/pr413-docops-rebase                                   b1cd7076b [origin/perplexity-grounding/1780286494-auto-grounded: gone] research(palantir-ontology): auto-grounding for PR#409 — gaps surfaced
  research/moltbook-investigation                              2b6c3776a [origin/main: ahead 2, behind 580] docs(research): round 1 follow-up — R_V calibration, schemas, corrections log
  research/persistent-agents-2026-05                           39291ad3d [origin/research/persistent-agents-2026-05: ahead 1] Add persistent agents landscape survey
  research/persistent-agents-deepdive-2026-05                  39291ad3d Add persistent agents landscape survey
  review-pr393c                                                11647bcc5 [origin/main: ahead 1, behind 415] chore(inter-agent): restack outbound responses after ops refresh
  review-pr411b                                                ff8cd9e36 [origin/main: ahead 2, behind 425] chore(inter-agent): restack inbound status after ops refresh
  review/interop-fleet-2026-05-12                              58e809eef chore(interop): park fleet interop control surface [impact-checked]
  review/memory-knowledge-2026-05-12                           479528df5 chore(memory): preserve context admission residue [impact-checked]
  review/root-governance-residue-2026-05-12                    af374d108 chore(governance): park root cleanup residue [impact-checked]
  routing-lane-source                                          ddcd720b2 feat(cron): add shakti executive handler
  rss/FU-CONDUCTOR-MALFORMED-DB                                4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-CONDUCTOR-UTF8                                        4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-CQ-PASSPORT-COUNT                                     4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-CRON-HANDLERS                                         4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-GOV-MODULE-BUDGET                                     4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-SEAM-KEY-CONTRACT                                     4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-SMOKE-PROFILE-ENUM                                    4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-SMOKE-SLEEPCYCLE-SIG                                  4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-SPINE-CORRELATION-JOIN                                4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-SPINE-DB-PATH                                         4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-STIG-SCHEMA-BACKEND                                   4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-STIG-WRITE-PATH                                       4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-SUBPROC-NULLBYTE                                      4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-TOOL-LOOP-CONVERGE                                    4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-WIRE-MINIMAX                                          4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-WIRE-XAI                                              4bb47aedd docs(operator-os): close eight-hour mission
  rss/FU-WIRE-ZAI                                              4bb47aedd docs(operator-os): close eight-hour mission
+ runtime-truth/nats-rebuild-preflight-20260618                86418541a (/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618) [origin/main: behind 114] Merge pull request #633 from AmitabhainArunachala/devin/1781768310-stop-noise-prs-automerge-botpr
  sattva/quality-ratchet-2026-06                               989f765b6 [origin/sattva/quality-ratchet-2026-06: gone] docs(quality): reconcile draft track with landed assurance boundary
  spec/shakti-ginko-organ                                      22951df4b [origin/spec/shakti-ginko-organ: gone] fix(docops): register 3 new architecture docs in canonical_guard
  spine-adoption/slice-b-adapter-saturation                    6c793fabd [origin/main: ahead 3, behind 407] chore(spine): tighten slice B runlog wording [impact-checked]
  spine-adoption/slice-c-mapping-receipts                      71120f9f4 [origin/main: ahead 3, behind 407] chore(spine): tighten slice C runlog wording [impact-checked]
  tam/operator-seed-v1                                         799f30400 [origin/main: behind 253] docs(plans): DHARMA_A2A retention proposal + outbound A2A reply packet (janitor lane) (#568)
  telos-ai-seed-2026-06-13                                     7217fbe1e [origin/main: ahead 1, behind 197] audit(telos-ai): substrate feasibility pass v0 (concept; seed not yet written)
* telos-ai-seed-v0-from-sandbox                                cd610be3c [origin/telos-ai-seed-v0-from-sandbox: ahead 2] docs(adr): ADR-009 Holarchy of Standing Holons + Falsifiable Internal Coherence
  telosproof-v0-advisory-spike                                 634495425 TelosProof v0: advisory proof-carrying-telos gate (prove the body, not the ghost)
  telosproof-v1-verification-substrate                         c8efcff28 TelosProof v1 (increment 2): mutation-kill suite + close the aliased-import false-negative
  trust-build-compass                                          a3ea1ee9a doctrine(governance): implement multi-track with parallel_lane_policy (v2 schema)
  worktree-research-integration                                f0158968a feat: research-informed evolution — 4 new modules + full integration
```
### `git for-each-ref --format='%(refname:short) %(upstream:short) %(upstream:track)' refs/heads`
```text
_rebase_tmp origin/codex/toolbelt-onboarding [gone]
_rtmp origin/devin/1779503110-staging-promote-hermes-wiring [gone]
archive/trust-build-compass-20260605  
audit/runtime-truth-2026-04-26  
backup/memory-kernel-prep-2026-05-14  
backup/route-witness-main-pre-rebase-2026-05-13  
backup/route-witness-pr297-pre-rebase-2026-05-13  
base/brief-to-spec-seam-018ef60  
cashclaw/revenue-hydra-v1 origin/cashclaw/revenue-hydra-v1 
chore/action-authority-gate-spec origin/main [ahead 5, behind 803]
chore/agentops-base-check  
chore/agentops-v0  
chore/authority-ptr-rollup origin/main [ahead 8, behind 798]
chore/brake-stabilization  
chore/capsule-coherence-tool  
chore/command-plane-nav-trim origin/chore/command-plane-nav-trim [ahead 15]
chore/control-plane-stabilizer  
chore/core-four-ontology-phase3  
chore/current-truth-refresh origin/main [ahead 8, behind 779]
chore/daily-brief-discovery-agentops  
chore/docops-integrity-v0  
chore/docops-ttl-renewal-20260612 origin/chore/docops-ttl-renewal-20260612 [gone]
chore/governance-truth-repairs  
chore/invariant-daily-insight-seam  
chore/kaizen-review-v0  
chore/kimi-claw-agentops-task  
chore/loop1-truth-registry  
chore/memory-tail-proof  
chore/opportunity-dispatcher-budget-fix  
chore/opportunity-dispatcher-budget-surgeon  
chore/phase2-governance-checkpoint  
chore/phase2-governance-rollup origin/chore/phase2-governance-rollup [ahead 2]
chore/phase2-governance-rollup-core-four  
chore/phase2-test-verify  
chore/repo-runway-daily-brief-seam origin/main [ahead 1, behind 754]
chore/semgrep-high-risk-batch  
chore/semgrep-rule-scope  
chore/semgrep-triage  
chore/state-authority-map  
chore/telic-seam-budget-exception  
chore/uplift-guard-recovery  
cleanup/action-authority-salvage-2026-05-13  
cleanup/agent-truth-spine-salvage-2026-05-13  
cleanup/brake-stabilization-salvage-2026-05-13  
cleanup/core-operating-circuit-proof-salvage-2026-05-13  
cleanup/go-local-model-runtime-inventory-salvage-2026-05-13  
cleanup/kaizen-review-v0-salvage-2026-05-13  
cleanup/main-dirty-salvage-2026-05-12  
cleanup/main-late-dirty-salvage-2026-05-12  
cleanup/main-recurring-live-salvage-2026-05-13  
cleanup/memory-kernel-context-eval-2026-05-13  
cleanup/memory-kernel-shadow-context-main-2026-05-13 origin/main [ahead 6, behind 581]
cleanup/mixed-quality-recovery-2026-05-10 origin/cleanup/mixed-quality-recovery-2026-05-10 [ahead 4]
cleanup/module-metabolism-strategy-salvage-2026-05-13  
cleanup/opportunity-dispatcher-budget-fix-salvage-2026-05-13  
cleanup/root-memory-context-salvage-2026-05-13  
cleanup/root-mixed-salvage-2026-05-12  
cleanup/runtime-result-projector-salvage-2026-05-13  
cleanup/viz-invariant-projection-2026-05-12  
codex/cyber-loop-closure-provider-truth-20260619 origin/codex/cyber-loop-closure-provider-truth-20260619 [gone]
codex/exec10-lf5  
codex/fix-docops-autorefresh-dispatch-20260605 origin/codex/fix-docops-autorefresh-dispatch-20260605 [gone]
codex/fix-docops-autorefresh-repo-arg-20260605 origin/codex/fix-docops-autorefresh-repo-arg-20260605 [gone]
codex/fix-pr-398-coherence origin/perplexity-computer/reply-to-claude-four-layer-stack [gone]
codex/go-idea-spark-ingest-spine-clean-20260604 origin/codex/go-idea-spark-ingest-spine-clean-20260604 [gone]
codex/governance-fitness-ci-20260620 origin/codex/governance-fitness-ci-20260620 [behind 89]
codex/live-ops-cockpit-v1 origin/codex/live-ops-cockpit-v1 [gone]
codex/live-ops-cockpit-v1-docops-fix origin/codex/live-ops-cockpit-v1 [gone]
codex/live-ops-cockpit-v1-docops-fix-mainbase origin/main [ahead 3, behind 359]
codex/live-ops-cockpit-v2-slice-a origin/main [ahead 4, behind 359]
codex/live-ops-cockpit-v2-slice-b  
codex/live-ops-cockpit-v2-slice-c  
codex/main-review-blockers origin/codex/main-review-blockers [gone]
codex/memory-kernel-default-context-20260523 origin/codex/memory-kernel-default-context-20260523 [gone]
codex/pr388-disambig origin/devin/2026-05-30-receipt-disambiguation [gone]
codex/pr408-schema-align origin/perplexity/2026-06-01-schema-alignment-gate [gone]
codex/pr409-oms-hardening origin/devin/1780259643-oms-hardening [gone]
codex/pr468-docops-clean origin/docs/runtime-truth-spine-plan-and-vel-rfc [gone]
codex/pr470-after-468-fix origin/devin/1780551922-spine-a2a-hardening [gone]
codex/pr470-docops-review origin/devin/1780551922-spine-a2a-hardening [gone]
codex/pr546-main-sync origin/chore/hygiene/evidence-snapshots-to-release [gone]
codex/pr558-main-sync origin/governance/ws4-gate-pep [gone]
codex/pr562-main-sync origin/fix/evolution-archive-honesty [gone]
codex/pr564-main-sync origin/devin/honest-spine-handoff-20260611 [gone]
codex/pr570-orientation-fixes  
codex/pr574-codeql-tests origin/qwen/spine-adoption [gone]
codex/pr578-main-sync origin/feat/trust-gate-scoreboard [gone]
codex/pr578-main-sync2 origin/feat/trust-gate-scoreboard [gone]
codex/pr584-main-sync origin/copilot/close-duplicate-prs-and-enable-automerge [gone]
codex/pr586-main-sync origin/codex/truth-graph-v1 [gone]
codex/repair-pr-392  
codex/repair-pr-399  
codex/runtime-truth-nats-adapter-20260606 origin/codex/runtime-truth-nats-adapter-20260606 [gone]
codex/toolbelt-onboarding origin/codex/toolbelt-onboarding [gone]
codex/truth-graph-v1 origin/codex/truth-graph-v1 [gone]
complexity-stress/replay-metamorphic-v1 origin/complexity-stress/replay-metamorphic-v1 [gone]
copilot/close-duplicate-prs-and-enable-automerge origin/copilot/close-duplicate-prs-and-enable-automerge [gone]
cutover/lf5-runtime-on-main-20260510-integrate-main  
daemon-lane-upgrade-20260616  
daemon-versioning/v0.0.1 origin/main [ahead 1, behind 197]
dashboard-lf5-operator-lane  
devin/1778035620-wire-fractal-runtime  
devin/1778037205-marathon-cleanup origin/devin/1778037205-marathon-cleanup [gone]
devin/1778426210-ship-revenue-wedge-report  
dgc-splash-art  
docs/adr-008-ontology-api-grammar origin/docs/adr-008-ontology-api-grammar [gone]
feat/a2a-correlation-spine-phase2a origin/main [ahead 3, behind 444]
feat/brief-to-spec-seam-2026-05-07 origin/feat/brief-to-spec-seam-2026-05-07 [ahead 1]
feat/codex-lane-runner-2026-05-13 origin/main [ahead 3, behind 583]
feat/cwt-v0-collector origin/feat/cwt-v0-collector [gone]
feat/governed-memory-recursive-preflight origin/main [ahead 7, behind 581]
feat/inquiry-chain-phase1  
feat/ontology-telos-gate-hardwire origin/main [ahead 20, behind 436]
feat/runtime-result-projector  
feat/trust-gate-scoreboard origin/feat/trust-gate-scoreboard [gone]
feat/world-radar-live-integration-2026-05-13 origin/main [ahead 1, behind 585]
feat/world-radar-shakti-telos-2026-05-13  
feat/world-radar-shakti-telos-docs-tests-2026-05-13  
feat/world-radar-shakti-telos-final-residue-2026-05-13  
feat/world-radar-shakti-telos-followup-2026-05-13  
feat/world-radar-shakti-telos-live-2026-05-13  
feat/world-radar-shakti-telos-residual-2026-05-13  
fix/evolution-archive-honesty origin/fix/evolution-archive-honesty [gone]
fix/provider-honesty-g6 origin/fix/provider-honesty-g6 [gone]
fix/runtime-spine-audit-followups  
forge-v1/tokenbroker-scoreboard-20260620 origin/main [ahead 9, behind 114]
forge/dharma-reward-forge-v0  
governance/parallel-lane-policy-2026-06-06  
governance/ws3-spine-dispatch origin/governance/ws3-spine-dispatch [gone]
governance/ws4-gate-pep origin/governance/ws4-gate-pep [gone]
helm/worldclass-20260612 origin/helm/worldclass-20260612 [ahead 57]
holarchy/crossfalsify-20260619 origin/main [ahead 1, behind 114]
integrate/chetana-grand-memory-2026-05-02 origin/integrate/chetana-grand-memory-2026-05-02 [ahead 13, behind 2]
lane/cybernetics-codex origin/main [ahead 1, behind 197]
lane/leftover-telos-cockpit origin/main [ahead 1, behind 197]
lane/loop-closure-reconciled  
lane/palantir-pilot origin/main [ahead 1, behind 197]
lane/runtime-spine-hardening origin/main [ahead 1, behind 197]
lane/untangle-manifest origin/main [ahead 1, behind 197]
lf5-live-fire-clean origin/lf5-live-fire-clean [ahead 25]
loop-closure/phase1b-2026-06 origin/loop-closure/phase1b-2026-06 [gone]
loop-closure/supplychain-bronze-20260620 origin/loop-closure/supplychain-bronze-20260620 [gone]
main origin/main [behind 114]
merge-master/pr399-restack origin/main [ahead 3, behind 407]
merge-master/pr411-restack origin/main [ahead 2, behind 413]
merge-master/pr435-restack origin/main [ahead 4, behind 403]
merge-master/pr436-restack origin/main [ahead 4, behind 401]
migration/old-machine-main  
mmm-nats-aiohttp origin/mmm-nats-aiohttp [gone]
mmm-nats-ca-pem origin/mmm-nats-ca-pem [gone]
mmm-nats-mike-credentials origin/mmm-nats-mike-credentials [gone]
mmm-nats-publish-deadline origin/mmm-nats-publish-deadline [gone]
mmm-pin-actions origin/mmm-pin-actions [gone]
mmm-visible-backlog-router origin/mmm-visible-backlog-router [gone]
model-routing/nim-bleeding-edge-20260618 origin/main [ahead 1, behind 141]
model-routing/nim-live-catalog-fix-20260620 origin/model-routing/nim-live-catalog-fix-20260620 [gone]
organ/00-floor  
organ/02-wounds  
organ/03-seat origin/organ/03-seat 
pr-344-backlog  
pr-384-backlog  
pr-388-backlog  
pr-406-review-20260531  
pr-465-backlog  
pr-474-backlog  
pr-495-backlog  
qwen/spine-adoption origin/qwen/spine-adoption [gone]
repair/pr-325-toolbelt origin/codex/toolbelt-onboarding [gone]
repair/pr413-docops-rebase origin/perplexity-grounding/1780286494-auto-grounded [gone]
research/moltbook-investigation origin/main [ahead 2, behind 580]
research/persistent-agents-2026-05 origin/research/persistent-agents-2026-05 [ahead 1]
research/persistent-agents-deepdive-2026-05  
review-pr393c origin/main [ahead 1, behind 415]
review-pr411b origin/main [ahead 2, behind 425]
review/interop-fleet-2026-05-12  
review/memory-knowledge-2026-05-12  
review/root-governance-residue-2026-05-12  
routing-lane-source  
rss/FU-CONDUCTOR-MALFORMED-DB  
rss/FU-CONDUCTOR-UTF8  
rss/FU-CQ-PASSPORT-COUNT  
rss/FU-CRON-HANDLERS  
rss/FU-GOV-MODULE-BUDGET  
rss/FU-SEAM-KEY-CONTRACT  
rss/FU-SMOKE-PROFILE-ENUM  
rss/FU-SMOKE-SLEEPCYCLE-SIG  
rss/FU-SPINE-CORRELATION-JOIN  
rss/FU-SPINE-DB-PATH  
rss/FU-STIG-SCHEMA-BACKEND  
rss/FU-STIG-WRITE-PATH  
rss/FU-SUBPROC-NULLBYTE  
rss/FU-TOOL-LOOP-CONVERGE  
rss/FU-WIRE-MINIMAX  
rss/FU-WIRE-XAI  
rss/FU-WIRE-ZAI  
runtime-truth/nats-rebuild-preflight-20260618 origin/main [behind 114]
sattva/quality-ratchet-2026-06 origin/sattva/quality-ratchet-2026-06 [gone]
spec/shakti-ginko-organ origin/spec/shakti-ginko-organ [gone]
spine-adoption/slice-b-adapter-saturation origin/main [ahead 3, behind 407]
spine-adoption/slice-c-mapping-receipts origin/main [ahead 3, behind 407]
tam/operator-seed-v1 origin/main [behind 253]
telos-ai-seed-2026-06-13 origin/main [ahead 1, behind 197]
telos-ai-seed-v0-from-sandbox origin/telos-ai-seed-v0-from-sandbox [ahead 2]
telosproof-v0-advisory-spike  
telosproof-v1-verification-substrate  
trust-build-compass  
worktree-research-integration
```
### `git branch -r`
```text
  origin/HEAD -> origin/main
  origin/alignment-experiment-runpod
  origin/archive/tcs-heartbeat-main-diverged-20260511
  origin/audit/merge-2026-03-22
  origin/backup/pr-48-pre-rebase-ba90b5f
  origin/base/brief-to-spec-seam-018ef60
  origin/capital-lab/build
  origin/cashclaw/revenue-hydra-v1
  origin/chore/agent-truth-spine
  origin/chore/auto-spine-adoption-2026-06-11
  origin/chore/command-plane-nav-trim
  origin/chore/commission-agent-runner-telic-chain
  origin/chore/cron-canonical-declaration
  origin/chore/cron-daemon-env-wrapper
  origin/chore/devin-inbound-11-step-audit
  origin/chore/docops-authority-registry
  origin/chore/governance-canon-refresh
  origin/chore/governance-onboarding-convergence
  origin/chore/governance-spine-adoption-2026-06-22T0600Z
  origin/chore/governance-spine-adoption-metric-20260608
  origin/chore/governance-spine-adoption-metric-refresh
  origin/chore/governance/hygiene-lifecycle-v2
  origin/chore/governance/spine-adoption-metric-refresh
  origin/chore/governance/spine-adoption-refresh-2026-06-07
  origin/chore/governance/spine-adoption-refresh-20260606
  origin/chore/kimi-force-response-20260505
  origin/chore/ops-run-report-2026-06-03T1200Z
  origin/chore/phase2-governance-isolation
  origin/chore/phase2-governance-rollup
  origin/chore/pr69-review-fixes
  origin/chore/provider-lane-pin-fix
  origin/chore/refresh-spine-adoption-metric
  origin/chore/refresh-spine-adoption-metric-20260622
  origin/chore/semgrep-hardening
  origin/chore/shakti-feedback-shadow-apply-dogfood
  origin/chore/spinal-bridge-clean-20260507
  origin/chore/spine-adoption-metric-20260605
  origin/chore/spine-adoption-metric-20260606
  origin/chore/spine-adoption-metric-20260614-1800
  origin/chore/spine-adoption-metric-refresh-20260603
  origin/chore/spine-adoption-metric-refresh-20260611
  origin/chore/telos-hierarchy-doctrine-correction
  origin/claude/confirm-plan-working-3qaaq
  origin/claude/seeing-organ-2je1gw
  origin/claude/structure-prompts-I4uPi
  origin/claude/todo-implementation-JXjD1
  origin/cleanup/docstrings-full-power-probe-20260507
  origin/cleanup/identity-onboarding-2026-05-12
  origin/cleanup/memory-kernel-preflight-lane-2026-05-16
  origin/cleanup/mixed-quality-recovery-2026-05-10
  origin/cleanup/recursive-evolution-lane-2026-05-16
  origin/cleanup/route-witness-2026-05-12
  origin/cleanup/route-witness-main-2026-05-13
  origin/codex/a2a-active-track-20260613
  origin/codex/authority-revenue-loop-clean
  origin/codex/governance-fitness-ci-20260620
  origin/codex/hypernode-empty-quadrant
  origin/codex/kaizen-exec-loop-20260601
  origin/codex/live-ops-cockpit-v2-slice-d
  origin/codex/module-metabolism-strategy
  origin/codex/operator-brief-witness-ready
  origin/codex/pr570-orientation-fixes
  origin/codex/pr90-critical-substrates-clean
  origin/codex/provenance-fanout-derivation-clean
  origin/codex/runtime-convergence-hardening
  origin/codex/runtime-truth-spine-v1
  origin/codex/slop-verification-main
  origin/codex/trace-attractor-ledger-spec
  origin/codex/trace-attractor-projection-types
  origin/codex/trace-attractor-store-readers
  origin/converge/kimi-claw-registration-20260428
  origin/copilot/build-three-connectors
  origin/copilot/clean-pr-portfolio-map
  origin/copilot/featurecontrol-loop-hardening-chetana-rebase
  origin/copilot/latest-pull-request
  origin/copilot/merge-all-changes
  origin/copilot/triage-open-pr-backlog
  origin/cutover/lf5-runtime-on-main-20260510
  origin/design/routing-fusion-spine
  origin/design/routing-fusion-spine-pr
  origin/devin/1777890984-authority-revenue-loop-gauntlet
  origin/devin/1777901958-repo-reality-gauntlet
  origin/devin/1777903781-provenance-wiring-mm17-mm18
  origin/devin/1777909780-substrate-meta-layer-items-2-3
  origin/devin/1777910581-ledger-watcher-operator-brief
  origin/devin/1777938227-value-events-cli
  origin/devin/1777938416-provenance-fanout-derivation
  origin/devin/1777940178-test-coverage-cold-substrates
  origin/devin/1777941324-test-coverage-phase2-6
  origin/devin/1777972679-consolidation-alignment
  origin/devin/1777994193-fractal-room-research
  origin/devin/1777995295-fractal-room-build
  origin/devin/1777996370-structural-coherence
  origin/devin/1778035620-wire-fractal-runtime
  origin/devin/1778385929-revenue-cell-v0
  origin/devin/1778683993-control-surface-contract-hardening
  origin/devin/1779271215-fix-gitnexus-hint
  origin/devin/1779279100-close-cockpit-track
  origin/devin/1779281950-track-transition-and-seeds
  origin/devin/1779703534-11-step-chain-verdict
  origin/devin/1779707153-11step-build-plan
  origin/devin/1779721563-11-step-chain-verdict
  origin/devin/1779876416-11-step-chain-verdict-v2
  origin/devin/1779883637-11-step-chain-verdict-v2
  origin/devin/1779890777-11-step-verdict-v3
  origin/devin/1779905139-11-step-chain-verdict-v2
  origin/devin/1779919577-11step-chain-verdict-v4
  origin/devin/1779943311-devin-a2a-fleet-plan
  origin/devin/1779946341-a2a-trace-persistence-e2e
  origin/devin/1779962811-11step-chain-verdict-v5
  origin/devin/1779977141-11step-chain-verdict
  origin/devin/1779978250-spine-governance-registration
  origin/devin/1779991547-11step-chain-verdict-v6
  origin/devin/1780022557-11-step-verdict-v3
  origin/devin/1780023669-verdict-clean
  origin/devin/1780038474-11step-chain-verdict-fresh
  origin/devin/1780042107-11step-chain-verdict
  origin/devin/1780059954-inbound-check-status
  origin/devin/1780095832-inbound-check-status
  origin/devin/1780103068-inbound-check-response
  origin/devin/1780128383-inbound-check-response
  origin/devin/1780131969-inbound-check-response
  origin/devin/1780298217-andon-verdict-D-E
  origin/devin/1780324280-andon-verdict-D-E-restack
  origin/devin/1780328602-andon-verdict-restack2
  origin/devin/1780339778-andon-restack3
  origin/devin/1780340193-andon-restack4
  origin/devin/1780340889-andon-restack5
  origin/devin/1780342618-andon-restack6
  origin/devin/1780373801-andon-restack7
  origin/devin/1780410762-pr-janitor-session
  origin/devin/1780411107-pr-janitor-session
  origin/devin/1780414839-pr-janitor-session
  origin/devin/1780416467-pr-janitor-session
  origin/devin/1780418181-pr-janitor-session
  origin/devin/1780420386-pr-janitor-session
  origin/devin/1780422058-pr-janitor-session
  origin/devin/1780424084-pr-janitor-session
  origin/devin/1780548631-spine-a2a-adoption
  origin/devin/1780554948-vel-equivalence-matrix
  origin/devin/1781340172-bug-corral
  origin/devin/1782057657-markitdown-document-ingest
  origin/devin/2026-05-28-autonomous-expansion-audit
  origin/devin/2026-05-29-research-organ-pivot
  origin/devin/2026-05-30-proof-artifact-pivot
  origin/devin/full-swarm-e2e-test-20260621
  origin/devin/runtime-truth-spine-pr-a
  origin/devin/update-skills-1779976321
  origin/devin/update-skills-1782049001
  origin/docs/canonical-drift-cleanup
  origin/docs/swarm-substrate-spec-2026-05-20
  origin/experiments/mask-rv-whitebox-prereg
  origin/feat/a2a-correlation-spine-phase2a
  origin/feat/agent-chat-panel
  origin/feat/auto-evolution
  origin/feat/board-feedback-edge
  origin/feat/brief-to-spec-seam-2026-05-07
  origin/feat/chetana-grand-memory
  origin/feat/chetana-restoration-from-4c70456e
  origin/feat/gauntlet-external-outcome-rewire
  origin/feat/go-evidence-sense-organ-v0
  origin/feat/governed-recursive-proof-tightening
  origin/feat/governed-recursive-proof-v0
  origin/feat/gplot-lodestone-seed
  origin/feat/knowledge-ops-organ-seed
  origin/feat/memory-census
  origin/feat/ontology-telos-gate-hardwire
  origin/feat/operating-spine-v2
  origin/feat/per-agent-chat-config-endpoints
  origin/feat/persist-evidence-receipts
  origin/feat/recursive-discovery-shadow-2026-05-14
  origin/feat/s4-zeitgeist-executive-stage2
  origin/feat/s4-zeitgeist-llm-scan
  origin/feat/slop-verification-system
  origin/feat/world-radar-shakti-safe-convergence-2026-05-13
  origin/feature/agent-work-os-v0
  origin/feature/control-loop-hardening-chetana-rebase-needed
  origin/feature/ontology-native-command-brief-v0
  origin/feature/operator-brief-first-tick-witness
  origin/fix-sql-injection-guardian-checks-7663364361950920885
  origin/fix/agent-wiring
  origin/fix/chetana-wiki-multiroot
  origin/fix/ci-green
  origin/fix/ci-tests-yaml
  origin/fix/false-affordance-purge
  origin/fix/packaged-build-hardening
  origin/fix/semantic-index-idempotence
  origin/governance/inquiry-chain-phase1
  origin/governance/pr-lifecycle-2026-06-13
  origin/governance/spine-adoption-refresh-2026-06-13
  origin/governance/tier-1-install
  origin/gpt55/high-roi-spine-mcp-orchestrator-20260620
  origin/gpt55/module-diet-census-20260619
  origin/helm/worldclass-20260612
  origin/honest-spine-v2
  origin/integrate/chetana-grand-memory-2026-05-02
  origin/intel/decepticon-phase1
  origin/lak-e2e
  origin/lf5-live-fire-clean
  origin/main
  origin/mmm-a2a-conditional-merge
  origin/ops/2026-06-03-run
  origin/ops/governance-report-2026-06-14
  origin/ops/governance-report-2026-06-18
  origin/ops/governance-spine-metric-refresh
  origin/ops/pr-lifecycle-spine-2026-06-15T0000Z
  origin/ops/pr-lifecycle-spine-adoption-2026-06-14T1200Z
  origin/ops/report-2026-06-19T1800Z
  origin/ops/report-2026-06-21T1200Z
  origin/ops/report-2026-06-21T1800Z
  origin/ops/run-report-2026-06-05T00Z
  origin/ops/run-report-2026-06-05T06Z
  origin/ops/run-report-2026-06-05T1200Z
  origin/ops/spine-adoption-2026-06-13
  origin/ops/spine-adoption-2026-06-20T0600Z
  origin/ops/spine-adoption-2026-06-21T0600Z
  origin/ops/spine-adoption-metric-2026-06-03
  origin/ops/spine-adoption-metric-refresh-20260606
  origin/ops/spine-adoption-metric-refresh-20260606-060209
  origin/ops/spine-adoption-refresh-2026-06-04T12
  origin/ops/spine-metric-refresh-2026-06-04
  origin/opus-identity-levelup
  origin/opus/traverse-fix-20260605
  origin/organ/03-seat
  origin/oz/route-truth-audit-2026-04-04
  origin/perf-async-roaming-daemon-7469302374074110265
  origin/perplexity-computer/a2a-activation-1780025504
  origin/perplexity-computer/doctrine-amendment-multi-track
  origin/perplexity-computer/mailbox-ack-to-claude-20260531
  origin/perplexity-computer/nest-1780023498
  origin/perplexity/bug-corral-arbiter-packet
  origin/pr/routing-coherence
  origin/pr91-review
  origin/repair/pr-323-dkeys
  origin/rescue/provenance-sentinel-go-track-20260612
  origin/research/encapsulation-language-strategy-room
  origin/research/persistent-agents-2026-05
  origin/review/proof-artifacts-2026-05-12
  origin/roaming-bridge-20260326
  origin/roaming-daemon-20260326
  origin/roaming-fixall-20260326
  origin/roaming-mailbox-live-20260326
  origin/spec/boardstore-facade
  origin/spine-grounding/slice-1-adoption-gate
  origin/spine-grounding/slice-2-runtime-recovery
  origin/spine-grounding/slice-3-tollbooth-gateway
  origin/stabilize/dharma-safe-clean
  origin/telos-ai-seed-v0-from-sandbox
  origin/tests/spine-persistence-invariant
  origin/wiring/archive-build-loop-2026-05-07
  origin/wiring/triage-cron-job-runtime-2026-05-07
  origin/wiring/triage-roaming-dispatch-2026-05-07
  origin/worker4/pr323-codeql
  origin/worker4/pr332-codeql
  origin/worktree-holon-agent
  pr/322
```
### `git worktree list --porcelain`
```text
worktree /Users/dhyana/dharma_swarm
HEAD cd610be3ccef9f7fff919cf8e36f32ca46f27b59
branch refs/heads/telos-ai-seed-v0-from-sandbox

worktree /private/tmp/dharma_nim_main_check
HEAD 4394d81b201e4a42d3cc30e78dc3f428bf85c506
branch refs/heads/model-routing/nim-live-catalog-fix-20260620
prunable gitdir file points to non-existent location

worktree /Users/dhyana/dharma_helm_build
HEAD 680b013c027194eb50416840d63055f025ca4bb7
branch refs/heads/helm/worldclass-20260612

worktree /Users/dhyana/dharma_swarm_cashclaw
HEAD c487d2725663bc83d1846bf349763c25930ab2ec
branch refs/heads/cashclaw/revenue-hydra-v1

worktree /Users/dhyana/dharma_swarm_live
HEAD e67b91829cb0b375069a19e4e60125b6d89ba374
branch refs/heads/organ/03-seat

worktree /Users/dhyana/dharma_swarm_main
HEAD 86418541a99c265c09040b9bfc064625c6d59994
detached

worktree /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618
HEAD 86418541a99c265c09040b9bfc064625c6d59994
branch refs/heads/runtime-truth/nats-rebuild-preflight-20260618

worktree /Users/dhyana/ds_forge_v1_scoreboard
HEAD d8bca7aab20af7871cff4ef46d08227cdb0923fa
branch refs/heads/forge-v1/tokenbroker-scoreboard-20260620

worktree /Users/dhyana/ds_governance_fitness_ci_20260620
HEAD c69f1cf05bec9b38fa0468135d21a25e7709971d
branch refs/heads/codex/governance-fitness-ci-20260620

worktree /Users/dhyana/ds_supplychain_slice
HEAD 11de04fb743ff9b02a293b248d579bf02fe8fd38
branch refs/heads/loop-closure/supplychain-bronze-20260620
```
### `git stash list`
```text
stash@{0}: On (no branch): deploy-unblock: stray governance reports 20260618T151442Z
stash@{1}: On feat/trust-gate-scoreboard: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_trust_gate
stash@{2}: On codex/pr578-main-sync: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_pr578_fix
stash@{3}: On codex/main-review-blockers: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_main_review_blockers
stash@{4}: On (no branch): compost/worktree-cull/2026-06-18 /Users/dhyana/ds_loopclose_night
stash@{5}: On fable/loop1-trunk-delegated: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_loop1_trunk
stash@{6}: On codex/truth-graph-v1: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_codex_truthgraph
stash@{7}: On tam/build-2026-06: compost/worktree-cull/2026-06-18 /Users/dhyana/dharma_swarm_tam
stash@{8}: On telos-ai-seed-v0-from-sandbox: codex-telos-ontology-wip
stash@{9}: On telos-ai-seed-v0-from-sandbox: what-not-to-do mandala cockpit attempt 2026-06-16
stash@{10}: On qwen/spine-adoption: pre-merge-lane-files
stash@{11}: On qwen/spine-adoption: docops-commit-world-dance
stash@{12}: WIP on qwen/spine-adoption: aa5a8e82b feat(go-ingest): wire idea spark ingest spine (#474)
stash@{13}: On trust-build-compass: codex-preserve-hook-restored-wip-before-lak-commit
stash@{14}: On trust-build-compass: codex-preserve-provider-tool-call-gate-wip-2
stash@{15}: On trust-build-compass: codex-preserve-provider-tool-call-gate-wip
stash@{16}: On trust-build-compass: codex-lak-docops-staged-metrics
stash@{17}: On trust-build-compass: archive trust-build-compass dirty cleanup 2026-06-05 before branch deletion
stash@{18}: On codex/runtime-truth-spine-e2e-20260604T143553Z: runtime-truth-spine-e2e-reconciliation-slice-after-479
stash@{19}: On codex/runtime-truth-spine-e2e-20260604T143553Z: runtime-truth-spine-e2e-reconciliation-slice
stash@{20}: On spine-grounding/combined-production-grounding: preserve C2 approval enforcement WIP
stash@{21}: WIP on codex/runtime-truth-spine-v2: 2ea5a8e8 feat(runtime): add execution identity spine v2 [impact-checked]
stash@{22}: On chore/command-plane-nav-trim: font-swap-parallel-isolation
stash@{23}: On chore/command-plane-nav-trim: cmdk-parallel-isolation
stash@{24}: On chore/command-plane-nav-trim: round8-eval-isolate-parallel-harness-edits
stash@{25}: On chore/command-plane-nav-trim: round6-parallel-session-isolation
stash@{26}: On chore/command-plane-nav-trim: round3-freeze
stash@{27}: On chore/command-plane-nav-trim: round2-stash-untracked
stash@{28}: On chore/command-plane-nav-trim: round2-final-2
stash@{29}: On chore/command-plane-nav-trim: round2-temp
stash@{30}: On chore/command-plane-nav-trim: phase1-commit-temp
stash@{31}: WIP on research/persistent-agents-deepdive-2026-05: 39291ad3 Add persistent agents landscape survey
stash@{32}: WIP on research/persistent-agents-2026-05: aa48a1f7 research(persistent-agents): X1 Hermes + I1 dharma_swarm audit (v2 path)
stash@{33}: On cleanup/memory-kernel-release-split-2026-05-17: codex-temp-before-gitignore-cleanup-2026-05-18
stash@{34}: On cleanup/recursive-evolution-lane-2026-05-16: lane-mask-rv-whitebox-artifacts-2026-05-16
stash@{35}: On cleanup/memory-kernel-shadow-context-main-2026-05-13: wip: freeze prod preflight report residue 2026-05-16
stash@{36}: On cleanup/memory-kernel-shadow-context-main-2026-05-13: wip: freeze before memory kernel lane split 2026-05-16
stash@{37}: On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-memory-kernel-base-dirty-2026-05-14
stash@{38}: On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-operator-control-smoke-2026-05-14
stash@{39}: On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-knowledgeops-m4b-2026-05-14
stash@{40}: On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-unrelated-research-spec-cleanup-2026-05-14
stash@{41}: On cleanup/memory-kernel-shadow-context-main-2026-05-13: memory-kernel-prep-full-dirty-snapshot-2026-05-14
stash@{42}: On chore/phase2-governance-isolation: quarantine interop dashboard api status context after semgrep wrapper
stash@{43}: On chore/phase2-governance-isolation: rogue_interop_feature
stash@{44}: On chore/phase2-governance-isolation: quarantine interop dashboard api wip before semgrep wrapper
stash@{45}: On feat/inquiry-chain-phase1: cleanup-hold-2026-05-03T07:27:00Z generated-agent-context-after-memory-probe
stash@{46}: On refactor/runtime-lifecycle-producers: cleanup-hold-2026-05-03T07:15:06Z holistic-sweep dharma_swarm_runtime_lifecycle_producers branch=refactor/runtime-lifecycle-producers entries=1
stash@{47}: On (no branch): cleanup-hold-2026-05-03T07:15:06Z holistic-sweep dharma_swarm_repo_state_now branch=detached entries=1
stash@{48}: On site/dharma-swarm-research: cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_public_site_publish branch=site/dharma-swarm-research entries=1
stash@{49}: On (no branch): cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_model_routing_cartography branch=detached entries=2
stash@{50}: On cartography/memory-substrates: cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_memory_substrates_origin_main branch=cartography/memory-substrates entries=1
stash@{51}: On (no branch): cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_main_stabilization_audit branch=detached entries=1
stash@{52}: On promote/lf5-runtime-spine: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_lf5_promotion branch=promote/lf5-runtime-spine entries=16
stash@{53}: On fix/guardian-warning-cases: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_guardian_warning_cases branch=fix/guardian-warning-cases entries=1
stash@{54}: On governance/tier-1-clean: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_governance_tier_1_clean branch=governance/tier-1-clean entries=1
stash@{55}: On docs/main-stabilization-checkpoint: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_ci_unblock_pr28 branch=docs/main-stabilization-checkpoint entries=1
stash@{56}: On dashboard-lf5-operator-lane: cleanup-hold-2026-05-03T07:15:03Z holistic-sweep dharma_swarm_lf5_operator branch=dashboard-lf5-operator-lane entries=6
stash@{57}: On audit/runtime-truth-2026-04-26: cleanup-hold-2026-05-03T07:15:03Z holistic-sweep dharma_swarm_lf5 branch=audit/runtime-truth-2026-04-26 entries=54
stash@{58}: On (no branch): cleanup-hold-2026-05-03T07:15:02Z holistic-sweep dharma_swarm_dashboard_skill_worktree branch=detached entries=1
stash@{59}: On worktree-research-integration: cleanup-hold-2026-05-03T07:15:02Z holistic-sweep research-integration branch=worktree-research-integration entries=2
stash@{60}: On dgc-splash-art: cleanup-hold-2026-05-03T07:15:02Z holistic-sweep dgc-splash-art branch=dgc-splash-art entries=34
stash@{61}: On feat/chetana-grand-memory: cleanup-hold-2026-05-03T07:15:01Z holistic-sweep dharma_chetana branch=feat/chetana-grand-memory entries=9
stash@{62}: On feat/inquiry-chain-phase1: cleanup-hold-2026-05-03T07:15:01Z holistic-sweep dharma_swarm branch=feat/inquiry-chain-phase1 entries=50
stash@{63}: On feat/inquiry-chain-phase1: WIP feat/inquiry-chain-phase1 — 30 modified + 35 untracked (deep_agent_*, agent_interop, intrinsic_rewards, dharma-judge tests, governance docs, dashboard interop) — parked 2026-05-03 by clean-up sweep
stash@{64}: On feat/inquiry-chain-phase1: cleanup-hold-2026-05-02-active-untracked-surfaces
stash@{65}: On governance/tier-1-install: pre-merge checkpoint: canonical governance/tier-1-install work (82 modified + untracked) before chetana merge 2026-05-01T14:43:51Z
stash@{66}: WIP on main: 4ec9579 fix: 3 critical integration fixes — recognition, knowledge extraction, director vision
stash@{67}: WIP on main: 4ec9579 fix: 3 critical integration fixes — recognition, knowledge extraction, director vision
stash@{68}: WIP on main: 27f84e4 feat(dashboard): collapsible micrographics header — collapsed by default, saves 550px viewport
stash@{69}: WIP on main: 06405c9 feat(terminal): Bun TUI cleanup + governance audit + dual-audit tool
```
### Stash Name-Status Details
#### `stash@{0}` — On (no branch): deploy-unblock: stray governance reports 20260618T151442Z
```text
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	reports/governance/track_portfolio.json
```
#### `stash@{1}` — On feat/trust-gate-scoreboard: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_trust_gate
```text
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	reports/governance/track_portfolio.json
```
#### `stash@{2}` — On codex/pr578-main-sync: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_pr578_fix
```text
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	reports/governance/track_portfolio.json
```
#### `stash@{3}` — On codex/main-review-blockers: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_main_review_blockers
```text
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	reports/governance/track_portfolio.json
```
#### `stash@{4}` — On (no branch): compost/worktree-cull/2026-06-18 /Users/dhyana/ds_loopclose_night
```text
M	reports/loop_closure/2026-06-16/closure_ledger.json
```
#### `stash@{5}` — On fable/loop1-trunk-delegated: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_loop1_trunk
```text
A	.qwen/skills/provider-chain-debug/SKILL.md
A	reports/loop1/WIRING_DIAGNOSTIC_2026-06-12.md
A	reports/loop1/qwen_leg_b_transcript.log
```
#### `stash@{6}` — On codex/truth-graph-v1: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_codex_truthgraph
```text
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	reports/governance/track_portfolio.json
```
#### `stash@{7}` — On tam/build-2026-06: compost/worktree-cull/2026-06-18 /Users/dhyana/dharma_swarm_tam
```text
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	reports/governance/track_portfolio.json
```
#### `stash@{8}` — On telos-ai-seed-v0-from-sandbox: codex-telos-ontology-wip
```text
M	docs/ontology/semantic_aliases.yaml
M	docs/ontology/semantic_objects.yaml
```
#### `stash@{9}` — On telos-ai-seed-v0-from-sandbox: what-not-to-do mandala cockpit attempt 2026-06-16
```text
M	dashboard/README.md
M	dashboard/src/app/dashboard/cockpit/page.tsx
M	dashboard/src/app/dashboard/layout.tsx
M	dashboard/src/app/globals.css
M	dashboard/src/app/layout.tsx
M	dashboard/src/components/cockpit/ActiveTrackPortfolioBoard.tsx
A	dashboard/src/components/cockpit/MandalaMissionCockpit.tsx
A	dashboard/src/components/layout/AppChrome.tsx
A	dashboard/src/lib/mandalaCockpitScene.test.ts
A	dashboard/src/lib/mandalaCockpitScene.ts
M	dashboard/src/lib/types.ts
M	dharma_swarm/operator_core/active_track_portfolio.py
M	tests/test_control_surface.py
```
#### `stash@{10}` — On qwen/spine-adoption: pre-merge-lane-files
```text
M	Makefile
M	dharma_swarm/orchestrator.py
M	docs/docops/assertions.yaml
M	scripts/governance/agent_onboard.py
M	scripts/governance/render_active_track_includes.py
```
#### `stash@{11}` — On qwen/spine-adoption: docops-commit-world-dance
```text
M	.gitignore
M	CLAUDE.md
M	Makefile
M	README.md
M	api/main.py
M	dharma_swarm/api_key_audit.py
M	dharma_swarm/api_keys.py
M	dharma_swarm/archive.py
M	dharma_swarm/assurance/scanner_providers.py
M	dharma_swarm/autonomous_agent.py
M	dharma_swarm/build_engine.py
M	dharma_swarm/conductors.py
M	dharma_swarm/dgc_cli.py
M	dharma_swarm/dharma_context_mcp.py
M	dharma_swarm/hypnagogic.py
M	dharma_swarm/integrations/nvidia_rag.py
M	dharma_swarm/model_hierarchy.py
M	dharma_swarm/ollama_config.py
M	dharma_swarm/orchestrator.py
M	dharma_swarm/persistent_agent.py
M	dharma_swarm/planner.py
M	dharma_swarm/provider_smoke.py
M	dharma_swarm/pulse.py
M	dharma_swarm/runtime_provider.py
M	dharma_swarm/startup_crew.py
M	dharma_swarm/subconscious_v2.py
M	dharma_swarm/terminal_commands/agents.py
M	dharma_swarm/terminal_commands/surfaces.py
M	dharma_swarm/thinkodynamic_director.py
M	dharma_swarm/tui/engine/adapters/openrouter.py
M	dharma_swarm/witness.py
M	dharma_swarm/worker_spawn.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/docops/assertions.yaml
M	docs/governance/BUILD_SESSION_ENTRYPOINT.md
M	docs/governance/SOVEREIGN_MANIFEST.md
M	docs/governance/proposed_tracks/README.md
M	foundations/INDEX.md
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	scripts/docops/check_docops_integrity.py
M	scripts/governance/agent_onboard.py
M	scripts/governance/check_track_status.py
M	scripts/governance/render_active_track_includes.py
M	scripts/load_runtime_env.sh
M	scripts/send_terminal_tui_keys.sh
M	terminal/src/app.tsx
M	terminal/src/protocol.ts
M	terminal/tests/app.test.ts
M	terminal/tests/protocol.test.ts
M	tests/test_api_key_audit.py
M	tests/test_api_keys.py
M	tests/test_assurance.py
M	tests/test_autonomous_agent.py
M	tests/test_dgc_cli.py
M	tests/test_env_alias_normalization.py
M	tests/test_provider_smoke.py
M	tests/test_runtime_provider.py
```
#### `stash@{12}` — WIP on qwen/spine-adoption: aa5a8e82b feat(go-ingest): wire idea spark ingest spine (#474)
```text
M	docs/docops/AUTO_INVENTORY.md
```
#### `stash@{13}` — On trust-build-compass: codex-preserve-hook-restored-wip-before-lak-commit
```text
A	dharma_swarm/operator_core/governed_work_admission.py
A	dharma_swarm/operator_core/living_agent_kernel.py
A	dharma_swarm/operator_core/living_agent_kernel_activation.py
A	dharma_swarm/operator_core/living_agent_kernel_promotion.py
A	dharma_swarm/operator_core/living_agent_kernel_provider_worker.py
A	dharma_swarm/operator_core/living_agent_kernel_recovery.py
A	dharma_swarm/operator_core/living_agent_kernel_service.py
A	dharma_swarm/operator_core/living_agent_kernel_status.py
A	dharma_swarm/operator_core/living_agent_kernel_supervisor.py
A	dharma_swarm/operator_core/living_agent_kernel_workers.py
A	dharma_swarm/operator_core/runtime_truth.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/docops/assertions.yaml
M	docs/governance/SOVEREIGN_MANIFEST.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md
A	scripts/runtime/living_agent_kernel_activation.py
A	scripts/runtime/living_agent_kernel_promotion.py
A	scripts/runtime/living_agent_kernel_provider_worker.py
A	scripts/runtime/living_agent_kernel_recovery.py
A	scripts/runtime/living_agent_kernel_service.py
A	scripts/runtime/living_agent_kernel_status.py
A	scripts/runtime/living_agent_kernel_supervisor.py
A	scripts/runtime/living_agent_kernel_worker.py
A	scripts/runtime/living_agent_kernel_worker_process.py
A	spec-forge/living-agent-kernel/MASTER_SPEC.md
A	tests/test_governed_work_admission.py
A	tests/test_living_agent_kernel.py
A	tests/test_living_agent_kernel_activation.py
A	tests/test_living_agent_kernel_promotion_provider.py
A	tests/test_living_agent_kernel_recovery.py
A	tests/test_living_agent_kernel_service.py
A	tests/test_living_agent_kernel_supervisor.py
A	tests/test_living_agent_kernel_workers.py
```
#### `stash@{14}` — On trust-build-compass: codex-preserve-provider-tool-call-gate-wip-2
```text
A	dharma_swarm/operator_core/governed_work_admission.py
A	dharma_swarm/operator_core/living_agent_kernel.py
A	dharma_swarm/operator_core/living_agent_kernel_activation.py
A	dharma_swarm/operator_core/living_agent_kernel_promotion.py
A	dharma_swarm/operator_core/living_agent_kernel_provider_worker.py
A	dharma_swarm/operator_core/living_agent_kernel_recovery.py
A	dharma_swarm/operator_core/living_agent_kernel_service.py
A	dharma_swarm/operator_core/living_agent_kernel_status.py
A	dharma_swarm/operator_core/living_agent_kernel_supervisor.py
A	dharma_swarm/operator_core/living_agent_kernel_workers.py
A	dharma_swarm/operator_core/runtime_truth.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/docops/assertions.yaml
M	docs/governance/SOVEREIGN_MANIFEST.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md
A	scripts/runtime/living_agent_kernel_activation.py
A	scripts/runtime/living_agent_kernel_promotion.py
A	scripts/runtime/living_agent_kernel_provider_worker.py
A	scripts/runtime/living_agent_kernel_recovery.py
A	scripts/runtime/living_agent_kernel_service.py
A	scripts/runtime/living_agent_kernel_status.py
A	scripts/runtime/living_agent_kernel_supervisor.py
A	scripts/runtime/living_agent_kernel_worker.py
A	scripts/runtime/living_agent_kernel_worker_process.py
A	spec-forge/living-agent-kernel/MASTER_SPEC.md
A	tests/test_governed_work_admission.py
A	tests/test_living_agent_kernel.py
A	tests/test_living_agent_kernel_activation.py
A	tests/test_living_agent_kernel_promotion_provider.py
A	tests/test_living_agent_kernel_recovery.py
A	tests/test_living_agent_kernel_service.py
A	tests/test_living_agent_kernel_supervisor.py
A	tests/test_living_agent_kernel_workers.py
```
#### `stash@{15}` — On trust-build-compass: codex-preserve-provider-tool-call-gate-wip
```text
A	dharma_swarm/operator_core/governed_work_admission.py
A	dharma_swarm/operator_core/living_agent_kernel.py
A	dharma_swarm/operator_core/living_agent_kernel_activation.py
A	dharma_swarm/operator_core/living_agent_kernel_promotion.py
A	dharma_swarm/operator_core/living_agent_kernel_provider_worker.py
A	dharma_swarm/operator_core/living_agent_kernel_recovery.py
A	dharma_swarm/operator_core/living_agent_kernel_service.py
A	dharma_swarm/operator_core/living_agent_kernel_status.py
A	dharma_swarm/operator_core/living_agent_kernel_supervisor.py
A	dharma_swarm/operator_core/living_agent_kernel_workers.py
A	dharma_swarm/operator_core/runtime_truth.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/docops/assertions.yaml
M	docs/governance/SOVEREIGN_MANIFEST.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md
A	scripts/runtime/living_agent_kernel_activation.py
A	scripts/runtime/living_agent_kernel_promotion.py
A	scripts/runtime/living_agent_kernel_provider_worker.py
A	scripts/runtime/living_agent_kernel_recovery.py
A	scripts/runtime/living_agent_kernel_service.py
A	scripts/runtime/living_agent_kernel_status.py
A	scripts/runtime/living_agent_kernel_supervisor.py
A	scripts/runtime/living_agent_kernel_worker.py
A	scripts/runtime/living_agent_kernel_worker_process.py
A	spec-forge/living-agent-kernel/MASTER_SPEC.md
A	tests/test_governed_work_admission.py
A	tests/test_living_agent_kernel.py
A	tests/test_living_agent_kernel_activation.py
A	tests/test_living_agent_kernel_promotion_provider.py
A	tests/test_living_agent_kernel_recovery.py
A	tests/test_living_agent_kernel_service.py
A	tests/test_living_agent_kernel_supervisor.py
A	tests/test_living_agent_kernel_workers.py
```
#### `stash@{16}` — On trust-build-compass: codex-lak-docops-staged-metrics
```text
M	Makefile
M	dharma_swarm/agent_runner.py
M	dharma_swarm/archaeology_ingestion.py
M	dharma_swarm/build_engine.py
M	dharma_swarm/cascade_domains/product.py
M	dharma_swarm/claude_hooks.py
M	dharma_swarm/cli.py
M	dharma_swarm/dataset_builder.py
M	dharma_swarm/ecosystem_bridge.py
M	dharma_swarm/ginko_evolution.py
M	dharma_swarm/harness_audit.py
M	dharma_swarm/model_hierarchy.py
M	dharma_swarm/monad.py
M	dharma_swarm/operator_core/control_surface.py
A	dharma_swarm/operator_core/governed_work_admission.py
A	dharma_swarm/operator_core/living_agent_kernel.py
A	dharma_swarm/operator_core/living_agent_kernel_activation.py
A	dharma_swarm/operator_core/living_agent_kernel_promotion.py
A	dharma_swarm/operator_core/living_agent_kernel_provider_worker.py
A	dharma_swarm/operator_core/living_agent_kernel_recovery.py
A	dharma_swarm/operator_core/living_agent_kernel_service.py
A	dharma_swarm/operator_core/living_agent_kernel_status.py
A	dharma_swarm/operator_core/living_agent_kernel_supervisor.py
A	dharma_swarm/operator_core/living_agent_kernel_workers.py
A	dharma_swarm/operator_core/runtime_truth.py
M	dharma_swarm/orchestrate_live.py
M	dharma_swarm/orchestrator.py
M	dharma_swarm/organism.py
M	dharma_swarm/provider_policy.py
M	dharma_swarm/providers.py
M	dharma_swarm/revenue/scout_daemon.py
M	dharma_swarm/scout_framework.py
M	dharma_swarm/swarm.py
M	dharma_swarm/task_board.py
M	dharma_swarm/telos_gates.py
M	dharma_swarm/telos_gates_witness_enhancement.py
M	dharma_swarm/telos_substrate.py
M	dharma_swarm/terminal_commands/_status_helpers.py
M	dharma_swarm/terminal_commands/diagnostics.py
M	dharma_swarm/terminal_commands/evolution.py
M	dharma_swarm/terminal_commands/infrastructure.py
M	dharma_swarm/terminal_commands/lifecycle.py
M	dharma_swarm/terminal_commands/meta.py
M	dharma_swarm/terminal_commands/semantic.py
M	dharma_swarm/terminal_commands/stigmergy.py
M	dharma_swarm/xray.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/docops/assertions.yaml
M	docs/governance/SOVEREIGN_MANIFEST.md
M	docs/research/persistent_agents_census_2026-05/l4_readiness_report.md
M	pyproject.toml
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md
M	scripts/governance/agent_onboard.py
A	scripts/runtime/living_agent_kernel_activation.py
A	scripts/runtime/living_agent_kernel_promotion.py
A	scripts/runtime/living_agent_kernel_provider_worker.py
A	scripts/runtime/living_agent_kernel_recovery.py
A	scripts/runtime/living_agent_kernel_service.py
A	scripts/runtime/living_agent_kernel_status.py
A	scripts/runtime/living_agent_kernel_supervisor.py
A	scripts/runtime/living_agent_kernel_worker.py
A	scripts/runtime/living_agent_kernel_worker_process.py
A	spec-forge/living-agent-kernel/MASTER_SPEC.md
M	tests/test_agent_onboard.py
M	tests/test_agent_runner.py
M	tests/test_agent_runner_memory.py
M	tests/test_agent_runner_quality_track.py
M	tests/test_agent_runner_routing_feedback.py
M	tests/test_api_main_bootstrap.py
M	tests/test_bootstrap_loops.py
M	tests/test_br_closures.py
M	tests/test_browser_agent.py
M	tests/test_build_engine.py
M	tests/test_cascade.py
M	tests/test_claude_hooks.py
M	tests/test_context.py
M	tests/test_dataset_builder.py
M	tests/test_doctor.py
M	tests/test_e2e_boot.py
M	tests/test_ecosystem_bridge.py
M	tests/test_ginko_evolution.py
M	tests/test_go_evidence_ingestor_bridge.py
M	tests/test_go_github_ingestor_bridge.py
M	tests/test_go_world_signal_bridge.py
M	tests/test_godel_claw_e2e.py
A	tests/test_governed_work_admission.py
M	tests/test_harness_audit.py
A	tests/test_living_agent_kernel.py
A	tests/test_living_agent_kernel_activation.py
A	tests/test_living_agent_kernel_promotion_provider.py
A	tests/test_living_agent_kernel_recovery.py
A	tests/test_living_agent_kernel_service.py
A	tests/test_living_agent_kernel_supervisor.py
A	tests/test_living_agent_kernel_workers.py
M	tests/test_memory_palace.py
M	tests/test_mode_pack.py
M	tests/test_monitor.py
M	tests/test_neural_consolidator.py
M	tests/test_operating_facts.py
M	tests/test_operating_facts_and_daily_brief.py
M	tests/test_operator_core_adapters.py
M	tests/test_orchestrator.py
M	tests/test_organism_boot.py
M	tests/test_organism_graph_integration.py
M	tests/test_phase3_integration.py
M	tests/test_provider_policy.py
M	tests/test_semantic_memory_bridge.py
M	tests/test_shakti_executive.py
M	tests/test_sleep_cycle.py
M	tests/test_smart_seed_selector.py
M	tests/test_startup_crew.py
M	tests/test_strange_loop.py
M	tests/test_task_board.py
M	tests/test_telos_gates_witness_enhancement.py
M	tests/test_xray.py
```
#### `stash@{17}` — On trust-build-compass: archive trust-build-compass dirty cleanup 2026-06-05 before branch deletion
```text
A	.augmentignore
M	.github/workflows/codex-mention-router.yml
A	.github/workflows/merge-master-mike-backlog.yml
M	.github/workflows/tests.yml
M	.gitignore
A	.gitnexusignore
M	.semgrep/dharma-anti-slop.yml
A	.windsurf/rules/devin-nats-pr-janitor.md
A	3000
M	ACTIVE_SURFACE_MANIFEST.yaml
M	CLAUDE.md
M	CYBERNETIC_LOOP_MAP.md
M	INTERFACE_MISMATCH_MAP.md
M	Makefile
M	api/routers/agents.py
M	api/routers/manifest.py
A	dharma_swarm/a2a/agent_card_a2a_sdk_bridge.py
A	dharma_swarm/a2a/executors/__init__.py
A	dharma_swarm/a2a/executors/codex_executor.py
A	dharma_swarm/a2a/executors/devin_executor.py
A	dharma_swarm/a2a/executors/hermes_executor.py
A	dharma_swarm/a2a/executors/opus_executor.py
A	dharma_swarm/a2a/registry_server.py
A	dharma_swarm/a2a/server_bootstrap.py
A	dharma_swarm/a2a/verifier.py
A	dharma_swarm/adapters/__init__.py
A	dharma_swarm/adapters/remote_host/__init__.py
A	dharma_swarm/adapters/remote_host/agent_payload.py
A	dharma_swarm/adapters/remote_host/capital_membrane.py
A	dharma_swarm/adapters/remote_host/cli.py
A	dharma_swarm/adapters/remote_host/fabric.py
A	dharma_swarm/adapters/remote_host/model_council.py
A	dharma_swarm/adapters/remote_host/quant_gates.py
A	dharma_swarm/adapters/remote_host/refresh.py
A	dharma_swarm/adapters/remote_host/route_authority.py
M	dharma_swarm/agent_runner.py
M	dharma_swarm/archaeology_ingestion.py
M	dharma_swarm/archive.py
M	dharma_swarm/auto_proposer.py
A	dharma_swarm/background_tasks.py
M	dharma_swarm/build_engine.py
A	dharma_swarm/capital_lab/__init__.py
A	dharma_swarm/capital_lab/adapter_registry.py
A	dharma_swarm/capital_lab/agentic_scorecard.py
A	dharma_swarm/capital_lab/alpha_evidence.py
A	dharma_swarm/capital_lab/contracts.py
A	dharma_swarm/capital_lab/data_discipline.py
A	dharma_swarm/capital_lab/dossier_intake.py
A	dharma_swarm/capital_lab/execution_readiness.py
A	dharma_swarm/capital_lab/experiment_bridge.py
A	dharma_swarm/capital_lab/paper_fund.py
A	dharma_swarm/capital_lab/readiness_gauntlet.py
A	dharma_swarm/capital_lab/report.py
A	dharma_swarm/capital_lab/tool_surface.py
M	dharma_swarm/cascade_domains/product.py
M	dharma_swarm/cli.py
M	dharma_swarm/codex_overnight.py
A	dharma_swarm/cron/__init__.py
A	dharma_swarm/cron/trading_handlers.py
A	dharma_swarm/cron/utils.py
M	dharma_swarm/cron_runner.py
M	dharma_swarm/curriculum_engine.py
M	dharma_swarm/dataset_builder.py
A	dharma_swarm/dharma_eval.py
A	dharma_swarm/employees/__init__.py
A	dharma_swarm/employees/runtime.py
A	dharma_swarm/eval/__init__.py
A	dharma_swarm/eval/dense_code_gym.py
A	dharma_swarm/eval/dense_gym.py
A	dharma_swarm/eval/inspect_adapter.py
A	dharma_swarm/eval/metaculus_aib.py
M	dharma_swarm/evolution.py
A	dharma_swarm/evolution_promotion.py
A	dharma_swarm/evolution_receipt.py
M	dharma_swarm/fractal/fractal_room.py
M	dharma_swarm/ginko_brier.py
M	dharma_swarm/ginko_evolution.py
A	dharma_swarm/ginko_experiments/registry.py
M	dharma_swarm/ginko_orchestrator.py
M	dharma_swarm/goodworks_dgm/service.py
M	dharma_swarm/hibernation.py
M	dharma_swarm/identity.py
A	dharma_swarm/integrations/postgres_telemetry.py
A	dharma_swarm/judge/__init__.py
A	dharma_swarm/judge/live_panel.py
A	dharma_swarm/judge/signal_judge.py
M	dharma_swarm/master_prompt_engineer.py
M	dharma_swarm/meta_daemon.py
M	dharma_swarm/monad.py
M	dharma_swarm/ontology.py
M	dharma_swarm/ontology_agents.py
M	dharma_swarm/operator_core/__init__.py
A	dharma_swarm/operator_core/a2a_autonomy_score.py
A	dharma_swarm/operator_core/a2a_durable_projection.py
A	dharma_swarm/operator_core/a2a_nats_contact.py
A	dharma_swarm/operator_core/a2a_stale_claim_reaper.py
M	dharma_swarm/operator_core/a2a_task_lifecycle.py
A	dharma_swarm/operator_core/agentic_run_view.py
A	dharma_swarm/operator_core/authority_passport.py
A	dharma_swarm/operator_core/collaboration_compliance.py
M	dharma_swarm/operator_core/control_surface.py
A	dharma_swarm/operator_core/control_surface_goodworks.py
M	dharma_swarm/operator_core/control_surface_models.py
A	dharma_swarm/operator_core/customer_workspace_view.py
A	dharma_swarm/operator_core/dashboard_ssot.py
A	dharma_swarm/operator_core/dkeys_readiness.py
A	dharma_swarm/operator_core/doctrine_digest.py
A	dharma_swarm/operator_core/exchange_key_custody.py
A	dharma_swarm/operator_core/execution_lease_dispatcher.py
A	dharma_swarm/operator_core/goal_health.py
A	dharma_swarm/operator_core/governed_work_admission.py
A	dharma_swarm/operator_core/ingest_nats.py
A	dharma_swarm/operator_core/living_agent_kernel.py
A	dharma_swarm/operator_core/nats_a2a_bridge.py
A	dharma_swarm/operator_core/nats_live_contact.py
A	dharma_swarm/operator_core/nats_substrate_status.py
A	dharma_swarm/operator_core/runtime_truth.py
A	dharma_swarm/operator_core/shakti_ginko_brain.py
M	dharma_swarm/operator_core/world_radar/receipt_bridge.py
M	dharma_swarm/orchestrate_live.py
M	dharma_swarm/orchestrator.py
M	dharma_swarm/organism.py
A	dharma_swarm/persistent_fleet.py
A	dharma_swarm/persistent_fleet_manifest.json
A	dharma_swarm/provider_health.py
M	dharma_swarm/provider_policy.py
M	dharma_swarm/providers.py
A	dharma_swarm/revenue/action_gateway.py
A	dharma_swarm/revenue/action_gateway_models.py
A	dharma_swarm/revenue/cashclaw_autopilot.py
A	dharma_swarm/revenue/cashclaw_employees.py
A	dharma_swarm/revenue/idea_gauntlet.py
A	dharma_swarm/revenue/live_intake.py
A	dharma_swarm/revenue/live_intake_models.py
A	dharma_swarm/revenue/live_intake_sources.py
M	dharma_swarm/revenue/scout_daemon.py
M	dharma_swarm/scout_framework.py
M	dharma_swarm/swarm.py
M	dharma_swarm/telemetry_plane.py
M	dharma_swarm/telosproof/allowlist.py
M	dharma_swarm/telosproof/ast_safety.py
A	dharma_swarm/telosproof/diff_parser.py
A	dharma_swarm/temporal_execution.py
M	dharma_swarm/terminal_bridge.py
M	dharma_swarm/terminal_commands/_status_helpers.py
M	dharma_swarm/terminal_commands/diagnostics.py
M	dharma_swarm/terminal_commands/evolution.py
M	dharma_swarm/terminal_commands/infrastructure.py
M	dharma_swarm/terminal_commands/lifecycle.py
M	dharma_swarm/terminal_commands/meta.py
M	dharma_swarm/terminal_commands/operator.py
M	dharma_swarm/terminal_commands/semantic.py
M	dharma_swarm/terminal_commands/stigmergy.py
M	dharma_swarm/venture_cell/operator_os/cli.py
A	dharma_swarm/venture_cell/operator_os/cli_artifacts.py
A	dharma_swarm/venture_cell/operator_os/cli_payloads.py
M	dharma_swarm/venture_cell/operator_os/projection.py
A	dharma_swarm/venture_cell/operator_os/projection_packets.py
M	dharma_swarm/vsm_channels.py
M	dharma_swarm/world_radar/analysis.py
A	dharma_swarm/world_radar/archive_to_chetana.py
M	dharma_swarm/world_radar/go_bridge.py
A	dharma_swarm/world_radar/go_bridge_io.py
A	dharma_swarm/world_radar/trading_intel.py
A	dharma_swarm/world_radar/trading_intel_lab_routes.json
M	docs/AGENTS.md
M	docs/MEGAFILE_INDEX.md
A	docs/agents/AGENT_CONTRACT_AND_TEAM.md
A	docs/agents/AGENT_REGISTRY_ATLAS.md
A	docs/agents/COLLABORATION_PACKET.md
A	docs/agents/GEPA_LITE.md
M	docs/agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md
A	docs/architecture/A2A_FLEET_TREATY.md
A	docs/architecture/CHETANA_MEMORY_KERNEL_M4_M5_MIGRATION.md
A	docs/architecture/DHARMA_REWARD_FORGE.md
M	docs/architecture/NAVIGATION.md
A	docs/architecture/SHAKTI_GINKO_TRADING_INTEL_LAB_ROUTING.md
A	docs/architecture/TOPOLOGY_MAP.md
M	docs/architecture/WORLD_ZEITGEIST.md
M	docs/docops/AUTO_INVENTORY.md
M	docs/docops/assertions.yaml
M	docs/governance/ACTIVE_TRACK.yaml
M	docs/governance/ANTI_SLOP_RULES.md
M	docs/governance/BUILD_SESSION_ENTRYPOINT.md
M	docs/governance/CANONICAL_DOC_STACK.md
A	docs/governance/CI_TRUTH_CONTRACT.json
A	docs/governance/CODEX_DEVOPS_INDEX_PROMPT.md
M	docs/governance/COHERENCE_DELTA.md
A	docs/governance/DEVOPS_ENV_RULES.md
A	docs/governance/FORGE_COUNCIL_PROTOCOL.md
A	docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md
M	docs/governance/SOVEREIGN_MANIFEST.md
M	docs/interface_mismatches.yaml
M	docs/ops/AGENT_ONBOARDING.md
A	docs/ops/AUTONOMY_SPINE.md
A	docs/ops/CODEX_AGENT_LOOPS.md
A	docs/ops/DEVIN_NATS_PR_JANITOR_PLAYBOOK.md
A	docs/ops/DHARMA_CAPITAL_LAB_EXECUTION_READINESS_90_HANDOFF.md
A	docs/ops/DHARMA_SWARM_ANTI_VIBE_QUALITY_GOAL.md
A	docs/ops/PR_REVIEW_CONTROL.md
A	docs/ops/RUNTIME_TRUTH_CLOSURE_V1_GOAL.md
A	docs/ops/RUNTIME_TRUTH_RECONCILIATION_SPINE.md
A	docs/ops/RUNTIME_TRUTH_SPINE_10H_GOAL.md
A	docs/ops/TMUX_AGENT_SUBSTRATE.md
A	docs/plans/2026-05-22-dashboard-frontend-claude-handoff.md
A	docs/plans/2026-05-22-dashboard-ssot-architecture.md
A	docs/plans/2026-05-22-repo-economy-metabolization-master-plan.md
A	docs/plans/2026-05-23-recursive-machine-self-evolution-build-plan.md
A	docs/plans/2026-05-27-business-idea-gauntlet-master-spec.md
A	docs/plans/2026-05-27-dashboard-tui-parallel-lane.md
A	docs/plans/2026-05-28-cashclaw-employee-runtime-build-spec.md
A	docs/plans/2026-06-01-cashclaw-hydra-v2-pitstop-spec.md
A	docs/plans/2026-06-02-dharma-capital-lab-v0-master-goal.md
A	docs/plans/2026-06-02-dharma-capital-lab-v1-8h-autonomous-build-spec.md
A	docs/plans/2026-06-02-venturecell-operator-os-autoresearch-8h-goal.md
A	docs/plans/2026-06-04-dharma-capital-lab-six-week-micro-live-readiness-goal.md
A	docs/plans/2026-06-04-venturecell-mission-console-v1-codex55-8h-goal.md
A	docs/plans/2026-06-05-dharma-capital-lab-paper-fund-v2-goal-launch.md
A	docs/reports/hermes_persistent_agent_index_2026-05-28.md
A	docs/research/agent_collaboration_hooks_gepa_2026-05-22.md
A	docs/research/experiment_001_cross_substrate_rv.md
A	docs/research/experiment_002_results_20260523_025255.json
A	docs/research/experiment_002_temporal_ordering.md
A	docs/research/experiment_003_content_specificity.md
A	docs/research/experiment_004_sab_basin_boundary.md
A	docs/research/fleet_provider_fallback_task.md
A	docs/research/proactive_cognition_synthesis.md
A	docs/specs/GO_IDEA_SPARK_INGEST_SPINE_MASTER_BUILD.md
A	docs/specs/forge_packets/FORGE_CHAIN_AUTONOMY.md
A	docs/specs/forge_packets/FORGE_HYDRA_EXTERNAL_BEAST_MISSION.md
A	docs/specs/forge_packets/FORGE_HYDRA_GOAL.draft-codex.md
A	docs/specs/forge_packets/FORGE_HYDRA_GOAL.draft-opus.md
A	docs/specs/forge_packets/FORGE_HYDRA_GOAL.md
A	docs/specs/forge_packets/FORGE_HYDRA_LONG_RUN_MISSION.md
A	docs/specs/forge_packets/FORGE_MEASUREMENT_GUARDIAN_MISSION.md
A	docs/specs/forge_packets/FORGE_PHASE2_VERIFY_HARDEN_READY.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_HYDRA_LAUNCH_CARD.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_HYDRA_MASTER_SPEC.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V0_GOAL.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V0_STATUS.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V1_10H_MASTER_GOAL.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V2_RULES.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V3_1_LAUNCH_CARD.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V3_1_REAL_BENCHMARK_LEARNING_LOOP_GOAL.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V3_1_SWARM_BENCHMARK_SPINE.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V3_BENCHMARK_BASELINE.md
A	docs/specs/forge_packets/FORGE_REALITY_ARENA_V4_VERTICAL_SLICE_GOAL.md
A	docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_GOAL.md
A	docs/specs/forge_packets/v0.1.0-live-telos-gate.md
A	docs/specs/forge_packets/v0.1.1-transfer-gate.md
A	docs/specs/forge_packets/v0.1.2-inspect-sandbox-executor.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.1.2-inspect-sandbox-executor.md
A	docs/specs/forge_packets/v0.1.3-first-external-receipt.md
A	docs/specs/forge_packets/v0.1.4-lineage-rollback.architect-wake.md
A	docs/specs/forge_packets/v0.1.5-deterministic-oracle-purge.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.1.6-isomorphic-perturbation-oracle.architect-wake.md
A	docs/specs/forge_packets/v0.1.6-isomorphic-perturbation-oracle.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.1.7-goodworks-mrv-adapter.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.1.8-venturecell-forge-feed.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.1.9-karpathy-autoresearch-seal.architect-wake.md
A	docs/specs/forge_packets/v0.1.9-karpathy-autoresearch-seal.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.2-invariant-saturation.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.3-oracle-class-breadth.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.4-cost-pressure.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.5-v0.8-domain-transfer.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v0.9-pre-v1-audit.codex-provisional-needs-opus-countersign.md
A	docs/specs/forge_packets/v1.0-external-threshold-ledger.codex-provisional-needs-opus-countersign.md
M	docs/state/BROKEN_REGISTER.md
A	examples/agents/codex_forgewright.registration.json
A	examples/agents/forge_measurement_guardian.registration.json
A	examples/agents/merge_master_mike.registration.json
A	examples/agents/opus_forge_architect.registration.json
A	gepa-self-evolving-agents-research.md
A	hooks/codex_dharma_bridge.py
A	inter_agent/devin/inbound/2026-05-22T22-50Z-opus_composer-first_contact.md
A	inter_agent/devin/inbound/2026-06-02T13-18Z-pr332-fresh-backup-review.md
A	lodestones/seeds/darshan_writing_ratchet.md
A	lodestones/seeds/long_now_temporal_attractor.md
M	pyproject.toml
A	references/research/agentic_autonomy_2026-03-27/sources.json
A	reports/agent_registry_atlas/agent_registry_atlas.json
A	reports/agent_registry_atlas/agent_registry_atlas.md
A	reports/agent_surfaces_inventory.json
A	reports/agentops/go_idea_spark_ingest_spine_integration_2026-06-03.md
A	reports/audit/2026-05-29-telos-attuned-operator-packet.md
A	reports/audit/2026-05-30-beyond-repo-frontier.md
A	reports/audit/2026-05-30-dharma-swarm-system-map.md
A	reports/audit/2026-05-30-external-review-request.md
A	reports/audit/2026-05-30-leverage-keystone.md
A	reports/audit/2026-05-30-wild-ideation-keepers.md
A	reports/audit/2026-06-04-quality-baseline.md
A	reports/audit/2026-06-05-dharma-capital-lab-execution-readiness-90-adversary.md
A	reports/audit/2026-06-05-hostile-safety-claims-audit.md
A	reports/audit/capital_lab_v1_adversarial_audit_20260602T1430Z.md
A	reports/bug_index/dharma_swarm_bug_index_2026-06-05.md
A	reports/capital_lab/20260605T082051Z-dharma-capital-lab-execution-readiness-90/verifier/20260605T082051Z-dharma-capital-lab-execution-readiness-90-t04-verifier.md
A	reports/capital_lab/20260605T082051Z-execution-readiness-90/operator_brief_and_next_action_handoff.md
A	reports/capital_lab/20260605T082051Z-execution-readiness-90/plan/acceptance_contract_risks_smallest_proof_loop.md
A	reports/capital_lab/20260605T082051Z-execution-readiness-90/plan/context_quorum_semantic_receipt.md
A	reports/capital_lab/20260605T082051Z-execution-readiness-90/plan/ledger_truth_and_supersession.md
A	reports/capital_lab/80_goal/final_80_readiness.md
A	reports/capital_lab/80_goal/final_80_readiness_scorecard.json
A	reports/capital_lab/80_goal/phase1_baseline_scorecard.json
A	reports/capital_lab/80_goal/phase1_scope_and_baseline.md
A	reports/capital_lab/80_goal/phase2_data_discipline.md
A	reports/capital_lab/80_goal/phase2_data_discipline_scorecard.json
A	reports/capital_lab/dharma-capital-lab-v1-20260602T131534Z/capital_lab_decision_receipt.json
A	reports/capital_lab/dharma-capital-lab-v1-20260602T131534Z/capital_lab_latest.json
A	reports/capital_lab/dharma-capital-lab-v1-20260602T131534Z/dossier_batch_manifest.json
A	reports/capital_lab/dharma-capital-lab-v1-20260602T131534Z/dossiers.json
A	reports/capital_lab/dharma-capital-lab-v1-20260602T131534Z/final_report.md
A	reports/capital_lab/dharma-capital-lab-v1-20260602T131534Z/paper_experiment_run.json
A	reports/capital_lab/dharma-capital-lab-v1-20260602T131534Z/paper_operation_scorecard.json
A	reports/capital_lab/dharma-capital-lab-v1-20260602T131534Z/shakti_ginko_experiments.jsonl
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/adversary/adversary_findings.json
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/adversary/adversary_report.md
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/artifact_manifest.json
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/next_action_handoff.md
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/operator_brief.md
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/planner_acceptance_contract.json
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/planner_acceptance_contract.md
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/reporter_receipt_blocker.md
A	reports/capital_lab/goal-b-broker-paper-execution-membrane-20260605T135732Z/t04_verifier_evidence.md
A	reports/capital_lab/goal_a_12h/run_goal_a_supervisor_20260605T140100Z.sh
A	reports/capital_lab/goal_a_12h/semantic_code_context_20260605T140100Z.md
A	reports/collaboration_packets/novel-artifact-scorecard-v1-20260525.json
A	reports/control_watch_tower/20260524T014044Z/REPORT.md
A	reports/control_watch_tower/20260524T014044Z/report.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_ci_measurement_guardian.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_claude_code_cli_20260521t064502z.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_codex_5_5_cli.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_codex_composer.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_codex_goodworks_dgm.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_codex_loop_auditor.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_codex_pge_goal.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_context_librarian.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_devin-roaming-2987d222.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_frontend_allnight_builder.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_hermes_m5_bootstrap.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_kimi-2-6-claw.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_loop_repair_codex.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_opus_composer.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_repo_cartographer.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecard_strategy_librarian.json
A	reports/control_watch_tower/20260524T014044Z/scorecards/scorecards_index.json
A	reports/control_watch_tower/20260524T014739Z/REPORT.md
A	reports/control_watch_tower/20260524T014739Z/report.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_ci_measurement_guardian.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_claude_code_cli_20260521t064502z.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_codex_5_5_cli.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_codex_composer.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_codex_goodworks_dgm.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_codex_loop_auditor.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_codex_pge_goal.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_context_librarian.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_devin-roaming-2987d222.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_frontend_allnight_builder.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_hermes_m5_bootstrap.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_kimi-2-6-claw.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_loop_repair_codex.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_opus_composer.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_repo_cartographer.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecard_strategy_librarian.json
A	reports/control_watch_tower/20260524T014739Z/scorecards/scorecards_index.json
A	reports/cybernetic_loop_audit/20260523T154437Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260523T154437Z/audit.json
A	reports/cybernetic_loop_audit/20260523T155825Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260523T155825Z/audit.json
A	reports/cybernetic_loop_audit/20260524T012544Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260524T012544Z/audit.json
A	reports/cybernetic_loop_audit/20260524T012926Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260524T012926Z/audit.json
A	reports/cybernetic_loop_audit/20260524T015218Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260524T015218Z/audit.json
A	reports/cybernetic_loop_audit/20260524T065535Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260524T065535Z/audit.json
A	reports/cybernetic_loop_audit/20260524T072159Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260524T072159Z/audit.json
A	reports/cybernetic_loop_audit/20260524T113418Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260524T113418Z/audit.json
A	reports/cybernetic_loop_audit/20260524T114053Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260524T114053Z/audit.json
A	reports/cybernetic_loop_audit/20260524T114911Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260524T114911Z/audit.json
A	reports/cybernetic_loop_audit/20260525T143609Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260525T143609Z/audit.json
A	reports/cybernetic_loop_audit/20260526T030807Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260526T030807Z/audit.json
A	reports/cybernetic_loop_audit/20260527T085809Z/AUDIT.md
A	reports/cybernetic_loop_audit/20260527T085809Z/audit.json
A	reports/cybernetic_loop_audit/context_receipt.md
A	reports/cybernetic_loop_audit/initial/AUDIT.md
A	reports/cybernetic_loop_audit/initial/audit.json
A	reports/cybernetic_loop_audit/latest.json
A	reports/cybernetic_loop_audit/latest.md
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
A	reports/handoff/2026-06-03-flight-offline-runtime-handoff.md
A	reports/handoff/2026-06-04-runtime-truth-closure.json
A	reports/handoff/2026-06-04-runtime-truth-closure.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md
A	reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md
A	reports/loop1_production_stability/2026-05-25-live-ollama-5x.md
A	reports/loop_closure_receipts/20260525T143603Z/RECEIPTS.md
A	reports/loop_closure_receipts/20260525T143603Z/loop_03_receipt.json
A	reports/loop_closure_receipts/20260525T143603Z/loop_10_receipt.json
A	reports/loop_closure_receipts/20260525T143603Z/loop_13_receipt.json
A	reports/loop_closure_receipts/20260525T143603Z/receipts.json
A	reports/loop_closure_receipts/20260526T030802Z/RECEIPTS.md
A	reports/loop_closure_receipts/20260526T030802Z/loop_03_receipt.json
A	reports/loop_closure_receipts/20260526T030802Z/loop_10_receipt.json
A	reports/loop_closure_receipts/20260526T030802Z/loop_13_receipt.json
A	reports/loop_closure_receipts/20260526T030802Z/receipts.json
A	reports/loop_closure_receipts/latest.json
A	reports/loop_closure_receipts/latest.md
A	reports/metabolization/ballast_externalization_receipt.md
A	reports/metabolization/duplicate_substrate_alias_receipt.md
A	reports/milestones/2026-05-25-execution-and-receipt-spine.md
A	reports/onboarding/canonical_substrate_map.md
A	reports/onboarding/gate_glossary.md
A	reports/onboarding/make_target_index.md
A	reports/organism_heartbeat_probe/20260524T072037Z/PROBE.md
A	reports/organism_heartbeat_probe/20260524T072037Z/probe.json
A	reports/organism_heartbeat_probe/20260524T113400Z/PROBE.md
A	reports/organism_heartbeat_probe/20260524T113400Z/probe.json
A	reports/organism_heartbeat_probe/20260524T114041Z/PROBE.md
A	reports/organism_heartbeat_probe/20260524T114041Z/probe.json
A	reports/organism_heartbeat_probe/20260525T131444Z/PROBE.md
A	reports/organism_heartbeat_probe/20260525T131444Z/probe.json
A	reports/organism_heartbeat_probe/20260527T085837Z/PROBE.md
A	reports/organism_heartbeat_probe/20260527T085837Z/probe.json
A	reports/organism_heartbeat_probe/20260527T092510Z/PROBE.md
A	reports/organism_heartbeat_probe/20260527T092510Z/probe.json
A	reports/organism_heartbeat_probe/context_receipt.md
A	reports/organism_heartbeat_probe/latest.json
A	reports/organism_heartbeat_probe/latest.md
A	reports/provider_readiness/latest.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/adversarial_review.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/bug_index.json
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/completion_audit.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/docs_claim_sync.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/e2e_runtime_truth.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/false_green_register.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/gate_membrane_plan.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/generated_artifact_quarantine.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/handoff.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/launch_control.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/module_coherence.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/quality_index.md
A	reports/quality/anti_vibe/20260605-dharma-swarm-anti-vibe-quality-index/verifier_report.md
A	reports/remote_nodes/2026-05-27-vps-fabric.md
A	reports/remote_nodes/agent_payloads/INSTALL_agni.md
A	reports/remote_nodes/agent_payloads/agni_remote_node_agent.py
A	reports/remote_nodes/agent_payloads/dharma-remote-node-agni.service
A	reports/repo_readiness/2026-05-27-level-up-status.md
A	reports/repo_xray_latest.md
A	reports/research/dharma_cash_claw_scrappy_v2_research.md
A	reports/research/dharma_reward_forge_seed_2026-05-31.md
A	reports/research/verified_experiment_loop_discovery_2026-06-04.md
A	reports/runtime_truth_spine/runtime-truth-spine-20260602T141129Z-truth-reconciliation-proof.json
A	reports/temporal_pilot_v0.md
A	reports/temporal_pilot_v0/live_server_smoke_2026-05-25.md
M	reports/venture_operator_os/venturecell-operator-os-level70-20260602T131724Z/build_receipt.md
M	reports/venture_operator_os/venturecell-operator-os-level70-20260602T131724Z/verifier_matrix.md
A	reports/witness/2026-06-01-dharma-reward-forge-first-external-receipt.md
A	reports/witness/2026-06-01-dharma-reward-forge-one-task.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172504Z/RUN_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172504Z/cycles.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172504Z/cycles/0001/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172504Z/cycles/0001/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172504Z/run_manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172555Z/RUN_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172555Z/cycles.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172555Z/cycles/0001/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172555Z/cycles/0001/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T172555Z/run_manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/RUN_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0001/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0001/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0002/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0002/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0003/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0003/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0004/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0004/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0005/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0005/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0006/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0006/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0007/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0007/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0008/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0008/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0009/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0009/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0010/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0010/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0011/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0011/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0012/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0012/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0013/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0013/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0014/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0014/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0015/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0015/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0016/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0016/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0017/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0017/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0018/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0018/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0019/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0019/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0020/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/cycles/0020/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T173044Z/run_manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/RUN_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/cycles/0001/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T174917Z/run_manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/RUN_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/api.github.com_advisories_3723b337c558.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/api.github.com_search_repositories_af676b9db569.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/github.com_browser-use_browser-use_5b585fc64177.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/github.com_openai_openai-agents-python_7f67d691cc5b.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_2660ba36c798.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_4d0d63319cb9.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_723eb7bcc2be.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/bodies/www.anthropic.com_news_6b986c5ea317.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/clean_texts/github.com_browser-use_browser-use_5b585fc64177.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/clean_texts/github.com_openai_openai-agents-python_7f67d691cc5b.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/clean_texts/www.anthropic.com_news_6b986c5ea317.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/api.github.com_advisories_3723b337c558.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/api.github.com_search_repositories_af676b9db569.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/github.com_browser-use_browser-use_5b585fc64177.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/github.com_openai_openai-agents-python_7f67d691cc5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_2660ba36c798.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_4d0d63319cb9.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_723eb7bcc2be.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/content_objects/www.anthropic.com_news_6b986c5ea317.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/api.github.com_advisories_3723b337c558.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/api.github.com_search_repositories_af676b9db569.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/github.com_browser-use_browser-use_5b585fc64177.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/github.com_openai_openai-agents-python_7f67d691cc5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_2660ba36c798.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_4d0d63319cb9.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_723eb7bcc2be.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/receipts/www.anthropic.com_news_6b986c5ea317.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/cycles/0001/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175206Z/run_manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/RUN_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/bodies/github.com_browser-use_browser-use_cf92227192da.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/bodies/github.com_openai_openai-agents-python_286323b03e74.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_580d073f4349.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_bb368f7ea1c9.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/clean_texts/github.com_browser-use_browser-use_cf92227192da.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/clean_texts/github.com_openai_openai-agents-python_286323b03e74.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/content_objects/github.com_browser-use_browser-use_cf92227192da.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/content_objects/github.com_openai_openai-agents-python_286323b03e74.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_580d073f4349.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_bb368f7ea1c9.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/receipts/github.com_browser-use_browser-use_cf92227192da.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/receipts/github.com_openai_openai-agents-python_286323b03e74.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_580d073f4349.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_bb368f7ea1c9.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/cycles/0001/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175346Z/run_manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/RUN_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/bodies/github.com_browser-use_browser-use_0e373e3b2924.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/bodies/github.com_openai_openai-agents-python_0f5eb67e665e.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_580d073f4349.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_bb368f7ea1c9.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/clean_texts/github.com_browser-use_browser-use_0e373e3b2924.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/clean_texts/github.com_openai_openai-agents-python_0f5eb67e665e.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/content_objects/github.com_browser-use_browser-use_0e373e3b2924.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/content_objects/github.com_openai_openai-agents-python_0f5eb67e665e.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_580d073f4349.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_bb368f7ea1c9.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/receipts/github.com_browser-use_browser-use_0e373e3b2924.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/receipts/github.com_openai_openai-agents-python_0f5eb67e665e.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_580d073f4349.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_81ff80874ea2.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_bb368f7ea1c9.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0001/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/bodies/github.com_browser-use_browser-use_e4f2918b3217.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/bodies/github.com_openai_openai-agents-python_69700384c37b.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_6dd4dae69bfa.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_d80c458499a7.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_fa30fe311d34.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/clean_texts/github.com_browser-use_browser-use_e4f2918b3217.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/clean_texts/github.com_openai_openai-agents-python_69700384c37b.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/content_objects/github.com_browser-use_browser-use_e4f2918b3217.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/content_objects/github.com_openai_openai-agents-python_69700384c37b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_6dd4dae69bfa.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_d80c458499a7.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_fa30fe311d34.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/receipts/github.com_browser-use_browser-use_e4f2918b3217.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/receipts/github.com_openai_openai-agents-python_69700384c37b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_6dd4dae69bfa.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_d80c458499a7.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_fa30fe311d34.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0002/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/bodies/github.com_browser-use_browser-use_4258211c6713.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/bodies/github.com_openai_openai-agents-python_635cb9feecb1.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_7186154f052f.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_b803a82b227c.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_d8b062d05834.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/clean_texts/github.com_browser-use_browser-use_4258211c6713.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/clean_texts/github.com_openai_openai-agents-python_635cb9feecb1.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/content_objects/github.com_browser-use_browser-use_4258211c6713.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/content_objects/github.com_openai_openai-agents-python_635cb9feecb1.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_7186154f052f.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_b803a82b227c.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_d8b062d05834.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/receipts/github.com_browser-use_browser-use_4258211c6713.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/receipts/github.com_openai_openai-agents-python_635cb9feecb1.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_7186154f052f.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_b803a82b227c.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_d8b062d05834.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0003/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/bodies/github.com_browser-use_browser-use_a7ae8346f969.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/bodies/github.com_openai_openai-agents-python_55b5dc5e54bb.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_709f67545a31.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_c5284d834f8a.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_cbf5047d48ae.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/clean_texts/github.com_browser-use_browser-use_a7ae8346f969.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/clean_texts/github.com_openai_openai-agents-python_55b5dc5e54bb.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/content_objects/github.com_browser-use_browser-use_a7ae8346f969.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/content_objects/github.com_openai_openai-agents-python_55b5dc5e54bb.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_709f67545a31.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_c5284d834f8a.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_cbf5047d48ae.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/receipts/github.com_browser-use_browser-use_a7ae8346f969.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/receipts/github.com_openai_openai-agents-python_55b5dc5e54bb.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_709f67545a31.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_c5284d834f8a.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_cbf5047d48ae.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0004/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/bodies/github.com_browser-use_browser-use_fe26933dd993.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/bodies/github.com_openai_openai-agents-python_e4422dae50d5.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_0feacbec53a0.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_3169d0c393d0.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_bfdb19a8123f.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/clean_texts/github.com_browser-use_browser-use_fe26933dd993.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/clean_texts/github.com_openai_openai-agents-python_e4422dae50d5.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/content_objects/github.com_browser-use_browser-use_fe26933dd993.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/content_objects/github.com_openai_openai-agents-python_e4422dae50d5.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_0feacbec53a0.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_3169d0c393d0.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_bfdb19a8123f.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/receipts/github.com_browser-use_browser-use_fe26933dd993.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/receipts/github.com_openai_openai-agents-python_e4422dae50d5.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_0feacbec53a0.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_3169d0c393d0.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_bfdb19a8123f.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0005/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/bodies/github.com_browser-use_browser-use_bcc02372a84e.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/bodies/github.com_openai_openai-agents-python_e503b11c5058.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_371c96960f2f.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_74a0a0ebbba3.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_99bef2fddc89.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/clean_texts/github.com_browser-use_browser-use_bcc02372a84e.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/clean_texts/github.com_openai_openai-agents-python_e503b11c5058.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/content_objects/github.com_browser-use_browser-use_bcc02372a84e.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/content_objects/github.com_openai_openai-agents-python_e503b11c5058.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_371c96960f2f.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_74a0a0ebbba3.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_99bef2fddc89.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/receipts/github.com_browser-use_browser-use_bcc02372a84e.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/receipts/github.com_openai_openai-agents-python_e503b11c5058.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_371c96960f2f.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_74a0a0ebbba3.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_99bef2fddc89.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0006/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/bodies/github.com_browser-use_browser-use_018c8fd94fe1.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/bodies/github.com_openai_openai-agents-python_4a1a4a23ddd4.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_13399518b6b2.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_66cb7ed66e9c.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_727c7320810f.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/clean_texts/github.com_browser-use_browser-use_018c8fd94fe1.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/clean_texts/github.com_openai_openai-agents-python_4a1a4a23ddd4.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/content_objects/github.com_browser-use_browser-use_018c8fd94fe1.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/content_objects/github.com_openai_openai-agents-python_4a1a4a23ddd4.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_13399518b6b2.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_66cb7ed66e9c.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_727c7320810f.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/receipts/github.com_browser-use_browser-use_018c8fd94fe1.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/receipts/github.com_openai_openai-agents-python_4a1a4a23ddd4.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_13399518b6b2.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_66cb7ed66e9c.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_727c7320810f.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0007/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/bodies/github.com_browser-use_browser-use_24235f36605f.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/bodies/github.com_openai_openai-agents-python_54f33c03c374.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_026013394117.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_3e2d80d0a344.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_57faa8e0eaaa.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/clean_texts/github.com_browser-use_browser-use_24235f36605f.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/clean_texts/github.com_openai_openai-agents-python_54f33c03c374.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/content_objects/github.com_browser-use_browser-use_24235f36605f.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/content_objects/github.com_openai_openai-agents-python_54f33c03c374.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_026013394117.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_3e2d80d0a344.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_57faa8e0eaaa.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/receipts/github.com_browser-use_browser-use_24235f36605f.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/receipts/github.com_openai_openai-agents-python_54f33c03c374.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_026013394117.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_3e2d80d0a344.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_57faa8e0eaaa.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0008/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/bodies/github.com_browser-use_browser-use_399370c6f190.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/bodies/github.com_openai_openai-agents-python_ba457bd62848.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_29808539978b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_bab349d24f38.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_f73ed964ccec.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/clean_texts/github.com_browser-use_browser-use_399370c6f190.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/clean_texts/github.com_openai_openai-agents-python_ba457bd62848.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/content_objects/github.com_browser-use_browser-use_399370c6f190.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/content_objects/github.com_openai_openai-agents-python_ba457bd62848.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_29808539978b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_bab349d24f38.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_f73ed964ccec.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/receipts/github.com_browser-use_browser-use_399370c6f190.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/receipts/github.com_openai_openai-agents-python_ba457bd62848.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_29808539978b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_bab349d24f38.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_f73ed964ccec.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0009/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/cycle.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/cycle.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/PROBE_REPORT.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/cashclaw_live_intake/adapter_receipts.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/cashclaw_live_intake/pattern_cards.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/cashclaw_live_intake/source_items.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/cashclaw_live_intake/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/cashclaw_live_intake/top_patterns.md
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/shakti_state/meta/zeitgeist.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/summary.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/downstream_probe/world_radar_rows.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/archive_index.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/bodies/api.github.com_search_repositories_4af480b8ee5b.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/bodies/github.com_browser-use_browser-use_8bc5202175b3.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/bodies/github.com_openai_openai-agents-python_3473f81c46ae.html
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_021281cce448.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_0dc82c5ecfe7.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/bodies/hn.algolia.com_api_v1_search_by_date_1959f19bfba1.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/clean_texts/github.com_browser-use_browser-use_8bc5202175b3.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/clean_texts/github.com_openai_openai-agents-python_3473f81c46ae.txt
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/content_objects/api.github.com_search_repositories_4af480b8ee5b.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/content_objects/github.com_browser-use_browser-use_8bc5202175b3.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/content_objects/github.com_openai_openai-agents-python_3473f81c46ae.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_021281cce448.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_0dc82c5ecfe7.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/content_objects/hn.algolia.com_api_v1_search_by_date_1959f19bfba1.content.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/manifest.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/receipts/api.github.com_search_repositories_4af480b8ee5b.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/receipts/github.com_browser-use_browser-use_8bc5202175b3.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/receipts/github.com_openai_openai-agents-python_3473f81c46ae.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_021281cce448.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_0dc82c5ecfe7.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/receipts/hn.algolia.com_api_v1_search_by_date_1959f19bfba1.receipt.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/live_archive/replay_index.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/world_scout_health.json
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/cycles/0010/world_scout_observations.jsonl
A	reports/world_scout_go/evidence_turbine_hydra/20260531T175422Z/run_manifest.json
A	reports/world_scout_go/evidence_turbine_v2_design_note.md
A	schemas/codex_agent_loop.schema.json
A	schemas/collaboration_packet.v0.json
A	schemas/gepa_lite_experiment.v0.json
A	scripts/consume_review_marks.py
M	scripts/governance/agent_onboard.py
A	scripts/governance/check_forge_reality_arena_v2_rules.py
A	scripts/governance/check_memory_kernel_canonical.py
M	scripts/governance/check_module_budget.py
A	scripts/governance/check_module_coherence.py
A	scripts/governance/check_nats_substrate_contract.py
A	scripts/governance/check_revenue_gauntlet_guard.py
A	scripts/governance/check_tmux_substrate_contract.py
M	scripts/governance/check_track_status.py
A	scripts/governance/collaboration_packet.py
M	scripts/governance/render_active_track_includes.py
A	scripts/governance/render_onboarding_indexes.py
A	scripts/governance/verify_quality_membrane.py
A	scripts/launchd/com.dhyana.a2a-core-contact.plist
M	scripts/mission_preflight.sh
M	scripts/register_external_agent.py
A	scripts/research/experiment_002_temporal_ordering.py
A	scripts/revenue/cashclaw_hydra_run_manifest.py
A	scripts/revenue/cashclaw_hydra_watchdog.py
A	scripts/revenue/cashclaw_lease_packet_quality_audit.py
A	scripts/revenue/cashclaw_live_intake.py
A	scripts/revenue/cashclaw_local_executor_sidecar.py
A	scripts/revenue/cashclaw_revenue_hydra.py
A	scripts/revenue/cashclaw_v3_presence_digest.py
A	scripts/revenue/dogfood_cashclaw_autopilot.py
A	scripts/revenue/evaluate_idea_gauntlet.py
A	scripts/runtime/a2a_autonomy_score.py
A	scripts/runtime/a2a_core_contact.py
A	scripts/runtime/a2a_stale_claim_reaper.py
A	scripts/runtime/agent_registry_atlas.py
M	scripts/runtime/autonomy_spine.py
A	scripts/runtime/capital_lab_alpha_evidence_membrane.py
A	scripts/runtime/capital_lab_execution_readiness_90.py
A	scripts/runtime/capital_lab_paper_fund_v2.py
A	scripts/runtime/ci_truth.py
A	scripts/runtime/codex_agent_loops.py
A	scripts/runtime/collaboration_drill.py
A	scripts/runtime/command_plane_dogfood_loop.py
A	scripts/runtime/cybernetic_loop_audit.py
A	scripts/runtime/dashboard_browser_smoke.mjs
A	scripts/runtime/execution_lease_dispatcher.py
A	scripts/runtime/forge_benchmark_adapter.py
A	scripts/runtime/forge_dense_code_gym.py
A	scripts/runtime/forge_dense_eval_normalizer.py
A	scripts/runtime/forge_dense_gym_adapter.py
A	scripts/runtime/forge_docker_sandbox.py
A	scripts/runtime/forge_failure_capsule.py
A	scripts/runtime/forge_fitness_boundary_dry_run.py
A	scripts/runtime/forge_fq1_sealed_reserve.py
A	scripts/runtime/forge_github_receipt.py
A	scripts/runtime/forge_hydra_status.py
A	scripts/runtime/forge_metaculus_aib_anchor.py
A	scripts/runtime/forge_pre_v1_audit.py
A	scripts/runtime/forge_reality_arena_authority_scan.py
A	scripts/runtime/forge_reality_arena_master_audit.py
A	scripts/runtime/forge_reality_arena_soak.py
A	scripts/runtime/forge_reality_arena_status.py
A	scripts/runtime/forge_reality_arena_v2_scorecard.py
A	scripts/runtime/forge_reality_arena_v3_1_8h_soak.py
A	scripts/runtime/forge_reality_arena_v3_1_real_benchmark_lane.py
A	scripts/runtime/forge_reality_arena_v3_1_real_benchmark_learning_loop.py
A	scripts/runtime/forge_reality_arena_v3_1_swarm_benchmark_spine.py
A	scripts/runtime/forge_reality_arena_v3_benchmark_baseline.py
A	scripts/runtime/forge_reality_arena_v4_clean_affordance_solver.py
A	scripts/runtime/forge_reality_arena_v4_clean_candidate_scout.py
A	scripts/runtime/forge_reality_arena_v4_clean_failure_atlas_repair.py
A	scripts/runtime/forge_reality_arena_v4_internal_analog.py
A	scripts/runtime/forge_reality_arena_v4_private_complementary_evidence_topology.py
A	scripts/runtime/forge_reality_arena_v4_private_static_shape_analog.py
A	scripts/runtime/forge_reality_arena_v4_private_static_shape_multiseed.py
A	scripts/runtime/forge_reality_arena_v4_private_topology_perturbation.py
A	scripts/runtime/forge_reality_arena_v4_run_affordance_solver_controls.py
A	scripts/runtime/forge_reality_arena_v4_run_candidate_scout_controls.py
A	scripts/runtime/forge_reality_arena_v4_run_failure_atlas_repair_controls.py
A	scripts/runtime/forge_reality_arena_v4_validate_clean_adaptive_transfer.py
A	scripts/runtime/forge_reality_arena_v4_validate_clean_affordance_solver_transfer.py
A	scripts/runtime/forge_reality_arena_v4_validate_clean_candidate_scout_transfer.py
A	scripts/runtime/forge_reality_arena_v4_validate_clean_failure_atlas_repair_transfer.py
A	scripts/runtime/forge_reality_arena_v4_validate_clean_nonnoop_transfer.py
A	scripts/runtime/forge_reality_arena_v4_validate_clean_policy_search_transfer.py
A	scripts/runtime/forge_reality_arena_v4_validate_clean_transfer.py
A	scripts/runtime/forge_reality_arena_v4_validate_receipts.py
A	scripts/runtime/forge_swarm_coordination_gym.py
A	scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py
A	scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py
A	scripts/runtime/forge_v3_1_clean_noop_harbor_agent.py
A	scripts/runtime/forge_v4_clean_adaptive_agent.py
A	scripts/runtime/forge_v4_clean_affordance_solver_agent.py
A	scripts/runtime/forge_v4_clean_candidate_scout_agent.py
A	scripts/runtime/forge_v4_clean_failure_atlas_repair_agent.py
A	scripts/runtime/forge_v4_clean_nonnoop_git_agent.py
A	scripts/runtime/forge_v4_clean_policy_search_agent.py
A	scripts/runtime/forge_v4_clean_transfer_topology_noop_agent.py
A	scripts/runtime/forge_v4_harbor_scheduler_agent.py
A	scripts/runtime/gepa_lite.py
A	scripts/runtime/go_archive_downstream_probe.py
A	scripts/runtime/go_evidence_turbine_hydra.py
A	scripts/runtime/live_ops_census.py
M	scripts/runtime/long_running_harness.py
A	scripts/runtime/loop_closure_receipts.py
A	scripts/runtime/merge_master_mike_daemon.py
A	scripts/runtime/opus_forge_architect_wake.py
A	scripts/runtime/organism_heartbeat_probe.py
A	scripts/runtime/pr_merge_control.py
A	scripts/runtime/reward_forge_v0.py
A	scripts/runtime/terminal_tui_interaction_smoke.py
A	scripts/runtime/tmux_ecosystem_bootstrap.py
A	scripts/runtime/tmux_ecosystem_status.py
A	scripts/smoke_signal_judge.py
A	scripts/start_command_plane_dogfood_tmux.sh
A	scripts/start_forge_hydra_long_run.sh
A	scripts/start_forge_measurement_guardian.sh
A	scripts/status_command_plane_dogfood_tmux.sh
A	scripts/status_forge_hydra_long_run.sh
A	scripts/status_forge_measurement_guardian.sh
A	scripts/stop_command_plane_dogfood_tmux.sh
M	scripts/telosproof_mutation.sh
M	scripts/telosproof_mutmut_setup.cfg
M	spec-forge/README.md
A	spec-forge/agentic-ai-agent-architecture/MASTER_SPEC.md
A	spec-forge/agentic-ai-agent-architecture/research/01_landscape.md
A	spec-forge/agentic-ai-agent-architecture/research/02_contradictions.md
A	spec-forge/agentic-ai-agent-architecture/research/03_citation_chains.md
A	spec-forge/agentic-ai-agent-architecture/research/04_gaps.md
A	spec-forge/agentic-ai-agent-architecture/research/05_methodology_audit.md
A	spec-forge/agentic-ai-agent-architecture/research/06_synthesis.md
A	spec-forge/agentic-ai-agent-architecture/research/07_assumptions.md
A	spec-forge/agentic-ai-agent-architecture/research/08_knowledge_map.md
A	spec-forge/agentic-ai-agent-architecture/research/09_so_what.md
A	spec-forge/cashclaw-employee-runtime/MASTER_SPEC.md
A	spec-forge/dharma-capital-lab-80-agentic-trading/MASTER_GOAL.md
A	spec-forge/dharma-capital-lab-broker-paper-execution-membrane/MASTER_GOAL.md
A	spec-forge/dharma-capital-lab-broker-paper-execution-membrane/PACKET_SCHEMAS.md
A	spec-forge/dharma-capital-lab-execution-readiness-90/MASTER_GOAL.md
A	spec-forge/dharma-capital-lab-paper-fund-v2/MASTER_GOAL.md
A	spec-forge/dharma-capital-lab-real-data-alpha-evidence-membrane/MASTER_GOAL.md
A	spec-forge/dharma-capital-lab-real-data-alpha-evidence-membrane/RUN_12H_PROMPT.md
A	spec-forge/dharma-capital-lab-real-data-alpha-evidence-membrane/schemas/alpha_evidence_scorecard.schema.json
A	spec-forge/dharma-capital-lab-real-data-alpha-evidence-membrane/schemas/artifact_manifest.schema.json
A	spec-forge/dharma-capital-lab-real-data-alpha-evidence-membrane/schemas/independent_evaluator.schema.json
A	spec-forge/dharma-capital-lab-real-data-alpha-evidence-membrane/schemas/provider_readiness_packet.schema.json
A	spec-forge/dharma-capital-lab-real-data-alpha-evidence-membrane/schemas/strategy_evidence_packet.schema.json
A	spec-forge/living-agent-kernel/MASTER_SPEC.md
A	spec-forge/memory-kernel/MEMORYKERNEL_CONFLICT_PROJECTION_REVIEW_SPEC.md
A	spec-forge/memory-kernel/MEMORYKERNEL_EVIDENCE_REVIEW_SPEC.md
A	spec-forge/memory-kernel/MEMORYKERNEL_PROMOTION_PROPOSAL_QUEUE_SPEC.md
A	spec-forge/terminal-convergence/MASTER_SPEC_2026-04-02.md
M	specs/proofs/telosproof/TelosProof.lean
A	terminal-v2/spec-forge/00-raw-requirements.md
A	terminal-v2/spec-forge/features.json
M	tests/conftest.py
A	tests/test_a2a_autonomy_score.py
A	tests/test_a2a_nats_contact.py
A	tests/test_a2a_sdk_golden_circuit.py
A	tests/test_a2a_stale_claim_reaper.py
M	tests/test_a2a_task_lifecycle.py
M	tests/test_active_track_governance.py
M	tests/test_agent_onboard.py
A	tests/test_agent_registry_atlas.py
M	tests/test_agent_runner.py
M	tests/test_agent_runner_memory.py
A	tests/test_agentic_run_view.py
M	tests/test_agents_router.py
A	tests/test_algedonic_action_wiring.py
M	tests/test_archive.py
M	tests/test_autonomy_spine.py
M	tests/test_bootstrap_loops.py
M	tests/test_br_closures.py
M	tests/test_browser_agent.py
M	tests/test_build_engine.py
A	tests/test_capital_lab_agentic_scorecard.py
A	tests/test_capital_lab_alpha_evidence.py
A	tests/test_capital_lab_contracts.py
A	tests/test_capital_lab_data_discipline.py
A	tests/test_capital_lab_dossier_intake.py
A	tests/test_capital_lab_execution_readiness.py
A	tests/test_capital_lab_execution_readiness_90.py
A	tests/test_capital_lab_experiment_bridge.py
A	tests/test_capital_lab_paper_fund_v2.py
A	tests/test_capital_lab_readiness_gauntlet.py
A	tests/test_capital_lab_report.py
A	tests/test_capital_lab_shakti_projection.py
M	tests/test_cascade.py
A	tests/test_cashclaw_action_gateway.py
A	tests/test_cashclaw_autopilot.py
A	tests/test_cashclaw_dogfood.py
A	tests/test_cashclaw_hydra_run_manifest.py
A	tests/test_cashclaw_hydra_watchdog.py
A	tests/test_cashclaw_lease_packet_quality_audit.py
A	tests/test_cashclaw_live_intake.py
A	tests/test_cashclaw_local_executor_sidecar.py
A	tests/test_cashclaw_revenue_hydra.py
A	tests/test_ci_truth.py
A	tests/test_codex_agent_loops.py
A	tests/test_codex_dharma_bridge.py
M	tests/test_codex_overnight.py
A	tests/test_collaboration_drill.py
A	tests/test_collaboration_packet.py
A	tests/test_command_plane_dogfood_loop.py
A	tests/test_compass_pull.py
M	tests/test_context.py
M	tests/test_cron_runner.py
M	tests/test_curriculum_engine.py
A	tests/test_cybernetic_loop_audit.py
A	tests/test_dashboard_ssot.py
M	tests/test_dataset_builder.py
A	tests/test_dense_code_gym.py
A	tests/test_dense_gym_adapter.py
A	tests/test_dharma_eval.py
A	tests/test_employee_runtime.py
A	tests/test_evolution_promotion.py
A	tests/test_evolution_receipt.py
A	tests/test_exchange_key_custody.py
A	tests/test_execution_lease_dispatcher.py
A	tests/test_forge_benchmark_adapter.py
A	tests/test_forge_dense_eval_normalizer.py
A	tests/test_forge_docker_sandbox.py
A	tests/test_forge_failure_capsule.py
A	tests/test_forge_fitness_boundary_dry_run.py
A	tests/test_forge_github_receipt.py
A	tests/test_forge_hydra_status.py
A	tests/test_forge_pre_v1_audit.py
A	tests/test_forge_reality_arena_authority_scan.py
A	tests/test_forge_reality_arena_master_audit.py
A	tests/test_forge_reality_arena_soak.py
A	tests/test_forge_reality_arena_status.py
A	tests/test_forge_reality_arena_v2_rules.py
A	tests/test_forge_reality_arena_v2_scorecard.py
A	tests/test_forge_reality_arena_v3_1_real_benchmark_lane.py
A	tests/test_forge_reality_arena_v3_1_real_benchmark_learning_loop.py
A	tests/test_forge_reality_arena_v3_1_swarm_benchmark_spine.py
A	tests/test_forge_reality_arena_v3_benchmark_baseline.py
A	tests/test_forge_reality_arena_v4_clean_adaptive_transfer_validator.py
A	tests/test_forge_reality_arena_v4_clean_affordance_solver.py
A	tests/test_forge_reality_arena_v4_clean_affordance_solver_transfer_validator.py
A	tests/test_forge_reality_arena_v4_clean_candidate_scout.py
A	tests/test_forge_reality_arena_v4_clean_candidate_scout_transfer_validator.py
A	tests/test_forge_reality_arena_v4_clean_failure_atlas_repair.py
A	tests/test_forge_reality_arena_v4_clean_failure_atlas_repair_transfer_validator.py
A	tests/test_forge_reality_arena_v4_clean_nonnoop_transfer_validator.py
A	tests/test_forge_reality_arena_v4_clean_policy_search_transfer_validator.py
A	tests/test_forge_reality_arena_v4_clean_transfer_validator.py
A	tests/test_forge_reality_arena_v4_internal_analog.py
A	tests/test_forge_reality_arena_v4_private_complementary_evidence_topology.py
A	tests/test_forge_reality_arena_v4_private_static_shape_analog.py
A	tests/test_forge_reality_arena_v4_private_static_shape_multiseed.py
A	tests/test_forge_reality_arena_v4_private_topology_perturbation.py
A	tests/test_forge_reality_arena_v4_receipt_validator.py
A	tests/test_forge_reality_arena_v4_run_affordance_solver_controls.py
A	tests/test_forge_reality_arena_v4_run_candidate_scout_controls.py
A	tests/test_forge_reality_arena_v4_run_failure_atlas_repair_controls.py
A	tests/test_forge_swarm_coordination_gym.py
A	tests/test_forge_swarm_evolution_arena_v0_preflight.py
A	tests/test_forge_v3_1_clean_noop_harbor_agent.py
A	tests/test_forge_v4_clean_adaptive_agent.py
A	tests/test_forge_v4_clean_affordance_solver_agent.py
A	tests/test_forge_v4_clean_candidate_scout_agent.py
A	tests/test_forge_v4_clean_failure_atlas_repair_agent.py
A	tests/test_forge_v4_clean_nonnoop_git_agent.py
A	tests/test_forge_v4_clean_policy_search_agent.py
A	tests/test_forge_v4_clean_transfer_topology_noop_agent.py
A	tests/test_forge_v4_harbor_scheduler_agent.py
A	tests/test_fq1_sealed_reserve_generator.py
M	tests/test_fractal_room.py
M	tests/test_full_loop.py
A	tests/test_gepa_lite.py
M	tests/test_ginko_brier.py
M	tests/test_ginko_orchestrator.py
A	tests/test_go_archive_downstream_probe.py
A	tests/test_goal_health.py
M	tests/test_goodworks_dgm.py
A	tests/test_governed_work_admission.py
A	tests/test_idea_gauntlet.py
A	tests/test_idea_gauntlet_cli.py
A	tests/test_idea_gauntlet_evidence_refs.py
A	tests/test_idea_gauntlet_fixtures.py
A	tests/test_idea_gauntlet_semantics.py
A	tests/test_ingest_nats.py
A	tests/test_live_ops_census.py
A	tests/test_living_agent_kernel.py
M	tests/test_long_running_harness.py
A	tests/test_loop_closure_receipts.py
A	tests/test_memory_kernel_canonical_gate.py
A	tests/test_merge_master_mike_daemon.py
A	tests/test_metaculus_aib_anchor.py
A	tests/test_model_routing_outcomes.py
A	tests/test_module_coherence_gate.py
A	tests/test_nats_live_contact.py
A	tests/test_nats_substrate_contract.py
M	tests/test_ontology_agents.py
M	tests/test_ontology_registry.py
M	tests/test_operator_core_adapters.py
M	tests/test_operator_core_contracts.py
A	tests/test_organism_heartbeat_probe.py
A	tests/test_persistent_fleet.py
A	tests/test_pr_merge_control.py
M	tests/test_providers_quality_track.py
M	tests/test_register_external_agent_script.py
A	tests/test_remote_host_capital_membrane.py
A	tests/test_remote_host_contracts.py
A	tests/test_remote_host_fabric.py
A	tests/test_remote_host_model_council.py
A	tests/test_remote_host_quant_gates.py
A	tests/test_remote_host_refresh.py
A	tests/test_remote_host_route_authority.py
A	tests/test_revenue_gauntlet_guard.py
A	tests/test_reward_forge_v0.py
M	tests/test_shakti_executive.py
A	tests/test_shakti_ginko_brain.py
A	tests/test_shakti_ginko_experiment_registry.py
A	tests/test_signal_judge.py
M	tests/test_strange_loop.py
A	tests/test_telosproof_falseneg_regressions.py
A	tests/test_tmux_substrate_contract.py
M	tests/test_vsm_channels.py
A	tests/test_world_archive_to_chetana.py
M	tests/test_world_radar_go_bridge.py
A	tests/test_world_radar_trading_intel.py
A	tests/test_world_radar_trading_intel_lab_routes.py
M	tests/test_world_signal_analysis.py
A	tools/go_sdk/spool/spool.go
A	tools/go_sdk/spool/spool_test.go
M	tools/world_scout_go/archive.go
M	tools/world_scout_go/archive_test.go
M	tools/world_scout_go/go.mod
M	tools/world_scout_go/health.go
M	tools/world_scout_go/main.go
M	tools/world_scout_go/scout.go
M	tools/world_scout_go/scout_test.go
A	tools/world_scout_go/source_specs/capital_lab_trading_systems.v1.json
A	tools/world_scout_go/source_specs/cashclaw_value_sources.v1.json
M	tools/world_scout_go/sources.go
M	tools/world_signal_ingestor_go/main.go
M	tools/world_signal_ingestor_go/main_test.go
M	xray_report.md
```
#### `stash@{18}` — On codex/runtime-truth-spine-e2e-20260604T143553Z: runtime-truth-spine-e2e-reconciliation-slice-after-479
```text
M	CLAUDE.md
M	dharma_swarm/operator_core/__init__.py
M	dharma_swarm/operator_core/contracts.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/ACTIVE_TRACK.yaml
M	docs/governance/BUILD_SESSION_ENTRYPOINT.md
M	docs/governance/SOVEREIGN_MANIFEST.md
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	scripts/governance/agent_onboard.py
M	tests/test_agent_onboard.py
M	tests/test_operator_core_contracts.py
M	tests/test_spine_persistence_invariant.py
```
#### `stash@{19}` — On codex/runtime-truth-spine-e2e-20260604T143553Z: runtime-truth-spine-e2e-reconciliation-slice
```text
M	CLAUDE.md
M	dharma_swarm/operator_core/__init__.py
M	dharma_swarm/operator_core/contracts.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/ACTIVE_TRACK.yaml
M	docs/governance/BUILD_SESSION_ENTRYPOINT.md
M	docs/governance/SOVEREIGN_MANIFEST.md
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	scripts/governance/agent_onboard.py
M	tests/test_agent_onboard.py
M	tests/test_operator_core_contracts.py
M	tests/test_spine_persistence_invariant.py
```
#### `stash@{20}` — On spine-grounding/combined-production-grounding: preserve C2 approval enforcement WIP
```text
M	dharma_swarm/ontology.py
```
#### `stash@{21}` — WIP on codex/runtime-truth-spine-v2: 2ea5a8e8 feat(runtime): add execution identity spine v2 [impact-checked]
```text
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
```
#### `stash@{22}` — On chore/command-plane-nav-trim: font-swap-parallel-isolation
```text
M	dashboard/src/app/globals.css
M	dashboard/src/app/layout.tsx
```
#### `stash@{23}` — On chore/command-plane-nav-trim: cmdk-parallel-isolation
```text
M	Makefile
M	dashboard/src/app/dashboard/layout.tsx
A	dashboard/src/components/dashboard/CommandPalette.tsx
M	dharma_swarm/operator_core/control_surface.py
A	dharma_swarm/operator_core/control_surface_goodworks_dgm.py
M	dharma_swarm/operator_core/control_surface_models.py
M	dharma_swarm/terminal_commands/__init__.py
M	dharma_swarm/tui/commands/system_commands.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/SOVEREIGN_MANIFEST.md
M	docs/ops/AGENT_ONBOARDING.md
M	docs/ops/LONG_RUNNING_HARNESS.md
M	docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
A	reports/witness/2026-05-22-goodworks-dgm-receipts-into-control-surface.md
M	schemas/long_running_harness.schema.json
M	scripts/runtime/long_running_harness.py
M	tests/test_command_contract.py
A	tests/test_control_surface_goodworks_dgm.py
M	tests/test_long_running_harness.py
M	tests/tui/test_system_commands.py
```
#### `stash@{24}` — On chore/command-plane-nav-trim: round8-eval-isolate-parallel-harness-edits
```text
M	schemas/long_running_harness.schema.json
M	scripts/runtime/long_running_harness.py
```
#### `stash@{25}` — On chore/command-plane-nav-trim: round6-parallel-session-isolation
```text
M	Makefile
M	dashboard/src/app/dashboard/control-surface/page.tsx
M	dashboard/src/components/cockpit/EvidenceDrawer.tsx
M	dharma_swarm/subconscious.py
M	docs/ops/AGENT_ONBOARDING.md
M	docs/ops/LONG_RUNNING_HARNESS.md
M	docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	scripts/runtime/long_running_harness.py
M	tests/test_long_running_harness.py
```
#### `stash@{26}` — On chore/command-plane-nav-trim: round3-freeze
```text
M	Makefile
A	dashboard/src/components/primitives/Glyph.tsx
A	dashboard/src/components/primitives/Numeral.tsx
A	dashboard/src/components/primitives/StatusBadge.tsx
A	docs/agents/AUTHORITY_LADDER_SCAFFOLD.md
A	docs/agents/CONTROL_WATCH_TOWER.md
A	docs/agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md
A	docs/agents/REGISTRATION_DESK.md
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/SOVEREIGN_MANIFEST.md
A	docs/ops/AGENT_ONBOARDING.md
A	docs/ops/CODEX_TOOLBELT_ONBOARDING.md
A	docs/ops/LONG_RUNNING_HARNESS.md
A	docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md
A	docs/ops/context_quorum_policy.json
A	docs/plans/COMMAND_PLANE_LONG_RUNNING_HARNESS_APPLICATION.md
A	docs/research/persistent_agents_census_2026-05/10_cultivation_architecture.md
A	docs/research/persistent_agents_census_2026-05/l4_readiness_report.md
A	docs/strategy/agentic_harness_2026-05/00_external_research_sources.md
A	docs/strategy/agentic_harness_2026-05/00_index.md
A	docs/strategy/agentic_harness_2026-05/00_local_evidence_base.md
A	docs/strategy/agentic_harness_2026-05/01_software_3_strategy_brain.md
A	docs/strategy/agentic_harness_2026-05/02_context_quorum_harness_strategy.md
A	docs/strategy/agentic_harness_2026-05/03_repo_cartography_and_ontology_strategy.md
A	docs/strategy/agentic_harness_2026-05/04_memory_palace_strategy.md
A	docs/strategy/agentic_harness_2026-05/05_governance_and_security_strategy.md
A	docs/strategy/agentic_harness_2026-05/06_measurement_and_verifiability_strategy.md
A	docs/strategy/agentic_harness_2026-05/07_command_plane_operator_strategy.md
A	docs/strategy/agentic_harness_2026-05/08_multi_agent_coordination_strategy.md
A	docs/strategy/agentic_harness_2026-05/09_tool_ecosystem_and_router_strategy.md
A	docs/strategy/agentic_harness_2026-05/10_persistent_identity_cultivation_strategy.md
A	examples/agents/strategy_librarian.registration.json
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
A	schemas/long_running_harness.schema.json
M	scripts/governance/agent_onboard.py
A	scripts/runtime/agent_onboard.sh
A	scripts/runtime/codex_toolbelt_status.sh
A	scripts/runtime/context_quorum.py
A	scripts/runtime/long_running_harness.py
A	tests/test_context_quorum.py
A	tests/test_long_running_harness.py
```
#### `stash@{27}` — On chore/command-plane-nav-trim: round2-stash-untracked
```text
A	.importlinter
M	ACTIVE_SURFACE_MANIFEST.yaml
M	CLAUDE.md
M	Makefile
M	api/chat_tools.py
M	api/main.py
A	api/routers/goodworks_dgm.py
A	api/routers/pool.py
A	dashboard/registry.json
A	dashboard/src/app/dashboard/codex-composer/page.tsx
A	dashboard/src/app/dashboard/goodworks/page.tsx
A	dashboard/src/hooks/useGoodworksDgm.ts
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.ts
M	dashboard/src/lib/types.ts
A	dashboard/src/registry/r/evidence-row.json
A	dashboard/src/registry/r/glyph.json
A	dashboard/src/registry/r/numeral.json
A	dashboard/src/registry/r/pane.json
A	dashboard/src/registry/r/status-badge.json
A	dashboard/src/registry/r/zone-frame.json
A	dharma_swarm/gen_eval_harness.py
A	dharma_swarm/goodworks_dgm/__init__.py
A	dharma_swarm/goodworks_dgm/mcp.py
A	dharma_swarm/goodworks_dgm/models.py
A	dharma_swarm/goodworks_dgm/runtime.py
A	dharma_swarm/goodworks_dgm/seed.py
A	dharma_swarm/goodworks_dgm/service.py
A	docs/agents/AUTHORITY_LADDER_SCAFFOLD.md
A	docs/agents/CONTROL_WATCH_TOWER.md
A	docs/agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md
A	docs/agents/REGISTRATION_DESK.md
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/ACTIVE_TRACK.yaml
M	docs/governance/BUILD_SESSION_ENTRYPOINT.md
M	docs/governance/SOVEREIGN_MANIFEST.md
A	docs/ontology/object_promotion_registry.json
A	docs/ontology/typed_object_name_canon.md
A	docs/ops/AGENT_ONBOARDING.md
A	docs/ops/CODEX_TOOLBELT_ONBOARDING.md
A	docs/ops/LONG_RUNNING_HARNESS.md
A	docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md
A	docs/ops/context_quorum_policy.json
A	docs/plans/2026-05-20-l4-persistent-agent-spec-forge-master-plan.md
A	docs/plans/2026-05-21-codex-composer-l4-lead-orchestrator-cultivation-plan.md
A	docs/plans/COMMAND_PLANE_LONG_RUNNING_HARNESS_APPLICATION.md
A	docs/plans/ONTOLOGY_PROMOTION_IMPLEMENTATION_PLAN_2026-05.md
A	docs/research/hermes_bootstrap_trial_2026-05/00_hermes_trial_report.md
A	docs/research/hermes_bootstrap_trial_2026-05/hermes_l4_receipt_schema.json
A	docs/research/hermes_bootstrap_trial_2026-05/hermes_trial_scratch.md
A	docs/research/hermes_bootstrap_trial_2026-05/zai_safe_retry_prompt.md
A	docs/research/ontology_promotion_2026-05/O1_current_canon_audit.md
A	docs/research/ontology_promotion_2026-05/O2_runtime_state_mining.md
A	docs/research/ontology_promotion_2026-05/O3_workflow_use_case_mining.md
A	docs/research/ontology_promotion_2026-05/O4_naming_collision_audit.md
A	docs/research/ontology_promotion_2026-05/O5_promotion_scoring_model.md
A	docs/research/ontology_promotion_2026-05/O6_ontology_synthesis.md
A	docs/research/persistent_agents_2026-05/00_survey_synthesis.md
A	docs/research/persistent_agents_census_2026-05/00_answer.md
A	docs/research/persistent_agents_census_2026-05/01_live_census.md
A	docs/research/persistent_agents_census_2026-05/02_health_report.md
A	docs/research/persistent_agents_census_2026-05/03_recent_activity.md
A	docs/research/persistent_agents_census_2026-05/04_identity_memory_map.md
A	docs/research/persistent_agents_census_2026-05/05_false_positives.md
A	docs/research/persistent_agents_census_2026-05/06_world_map.md
A	docs/research/persistent_agents_census_2026-05/07_best_practices.md
A	docs/research/persistent_agents_census_2026-05/08_benchmark_matrix.md
A	docs/research/persistent_agents_census_2026-05/09_identity_formation_case_study.md
A	docs/research/persistent_agents_census_2026-05/10_cultivation_architecture.md
A	docs/research/persistent_agents_census_2026-05/11_tracking_schema.md
A	docs/research/persistent_agents_census_2026-05/12_30_day_trial_plan.md
A	docs/research/persistent_agents_census_2026-05/13_ontology_bridge.md
A	docs/research/persistent_agents_census_2026-05/agent_inventory.jsonl
A	docs/research/persistent_agents_census_2026-05/external_systems.jsonl
A	docs/research/persistent_agents_census_2026-05/l4_readiness.jsonl
A	docs/research/persistent_agents_census_2026-05/l4_readiness_report.md
A	docs/research/persistent_agents_census_2026-05/l4_readiness_schema.json
A	docs/research/persistent_agents_census_2026-05/ontology_bridge_matrix.jsonl
A	docs/research/persistent_agents_deepdive_2026-05/00_final_answer.md
A	docs/research/persistent_agents_deepdive_2026-05/01_benefits_case.md
A	docs/research/persistent_agents_deepdive_2026-05/02_00_synthesis.md
A	docs/research/persistent_agents_deepdive_2026-05/02_ai16z_agent_funds.md
A	docs/research/persistent_agents_deepdive_2026-05/02_ai_garden_jeffrey.md
A	docs/research/persistent_agents_deepdive_2026-05/02_ai_vtubers_beyond_neuro.md
A	docs/research/persistent_agents_deepdive_2026-05/02_anthropic_claude_code_computer_use.md
A	docs/research/persistent_agents_deepdive_2026-05/02_bittensor_subnet_specialists.md
A	docs/research/persistent_agents_deepdive_2026-05/02_crustafarian_prophets.md
A	docs/research/persistent_agents_deepdive_2026-05/02_cursor_background_agents.md
A	docs/research/persistent_agents_deepdive_2026-05/02_devin.md
A	docs/research/persistent_agents_deepdive_2026-05/02_elizaos_ai16z.md
A	docs/research/persistent_agents_deepdive_2026-05/02_friendtech_ai_companions.md
A	docs/research/persistent_agents_deepdive_2026-05/02_hermes_agent.md
A	docs/research/persistent_agents_deepdive_2026-05/02_letta.md
A	docs/research/persistent_agents_deepdive_2026-05/02_lindy.md
A	docs/research/persistent_agents_deepdive_2026-05/02_llm_discord_irc_bots.md
A	docs/research/persistent_agents_deepdive_2026-05/02_manus.md
A	docs/research/persistent_agents_deepdive_2026-05/02_neuro_sama.md
A	docs/research/persistent_agents_deepdive_2026-05/02_openai_codex_operator.md
A	docs/research/persistent_agents_deepdive_2026-05/02_openclaw.md
A	docs/research/persistent_agents_deepdive_2026-05/02_pepa_reference_implementations.md
A	docs/research/persistent_agents_deepdive_2026-05/02_replit_agent.md
A	docs/research/persistent_agents_deepdive_2026-05/02_sakana_collective_intelligence.md
A	docs/research/persistent_agents_deepdive_2026-05/02_truth_terminal.md
A	docs/research/persistent_agents_deepdive_2026-05/02_x_persona_agents.md
A	docs/research/persistent_agents_deepdive_2026-05/03_hermes_nous_bootstrap.md
A	docs/research/persistent_agents_deepdive_2026-05/04_copy_like_crazy.md
A	docs/research/persistent_agents_deepdive_2026-05/05_constraints.md
A	docs/research/persistent_agents_deepdive_2026-05/CORRECTIONS_LOG.md
A	docs/research/persistent_agents_deepdive_2026-05/_cache/source_index.md
A	docs/sis/README.md
A	docs/sis/SILICON_IS_SAND_WIKI_NODE.md
A	docs/sis/SIS_RESEARCH_QUEUE.md
A	docs/sis/SIS_SPOKE_REGISTRY.md
A	docs/sis/sis_seed_packet.json
A	docs/sis/sis_spoke_registry.json
A	docs/strategy/agentic_harness_2026-05/00_external_research_sources.md
A	docs/strategy/agentic_harness_2026-05/00_index.md
A	docs/strategy/agentic_harness_2026-05/00_local_evidence_base.md
A	docs/strategy/agentic_harness_2026-05/01_software_3_strategy_brain.md
A	docs/strategy/agentic_harness_2026-05/02_context_quorum_harness_strategy.md
A	docs/strategy/agentic_harness_2026-05/03_repo_cartography_and_ontology_strategy.md
A	docs/strategy/agentic_harness_2026-05/04_memory_palace_strategy.md
A	docs/strategy/agentic_harness_2026-05/05_governance_and_security_strategy.md
A	docs/strategy/agentic_harness_2026-05/06_measurement_and_verifiability_strategy.md
A	docs/strategy/agentic_harness_2026-05/07_command_plane_operator_strategy.md
A	docs/strategy/agentic_harness_2026-05/08_multi_agent_coordination_strategy.md
A	docs/strategy/agentic_harness_2026-05/09_tool_ecosystem_and_router_strategy.md
A	docs/strategy/agentic_harness_2026-05/10_persistent_identity_cultivation_strategy.md
A	docs/vision_maps/2026-05-20_current_spine_attachment_audit.md
A	docs/vision_maps/2026-05-20_current_spine_attachment_scorecard.json
A	examples/agents/hermes_m5_bootstrap.authority_passport.json
A	examples/agents/hermes_m5_bootstrap.registration.json
A	examples/agents/strategy_librarian.registration.json
A	lodestones/grounding/silicon_is_sand_research_anchors_2026.md
A	lodestones/seeds/silicon_is_sand_movement_spoke_factory.md
A	lodestones/seeds/silicon_is_sand_substrate_accountable_ai.md
A	reports/benchmarks/swarm_native_redteam_latest.json
A	reports/control_watch_tower/20260521T074951Z/REPORT.md
A	reports/control_watch_tower/20260521T074951Z/report.json
A	reports/control_watch_tower/20260521T074951Z/scorecards/scorecard_claude_code_cli_20260521t064502z.json
A	reports/control_watch_tower/20260521T074951Z/scorecards/scorecard_codex_composer.json
A	reports/control_watch_tower/20260521T074951Z/scorecards/scorecard_hermes_m5_bootstrap.json
A	reports/control_watch_tower/20260521T074951Z/scorecards/scorecard_kimi-2-6-claw.json
A	reports/control_watch_tower/20260521T074951Z/scorecards/scorecard_opus_composer.json
A	reports/control_watch_tower/20260521T074951Z/scorecards/scorecards_index.json
A	reports/control_watch_tower/20260521T075054Z/REPORT.md
A	reports/control_watch_tower/20260521T075054Z/report.json
A	reports/control_watch_tower/20260521T075054Z/scorecards/scorecard_claude_code_cli_20260521t064502z.json
A	reports/control_watch_tower/20260521T075054Z/scorecards/scorecard_codex_composer.json
A	reports/control_watch_tower/20260521T075054Z/scorecards/scorecard_hermes_m5_bootstrap.json
A	reports/control_watch_tower/20260521T075054Z/scorecards/scorecard_kimi-2-6-claw.json
A	reports/control_watch_tower/20260521T075054Z/scorecards/scorecard_opus_composer.json
A	reports/control_watch_tower/20260521T075054Z/scorecards/scorecards_index.json
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
A	reports/governed_evolution/latest.json
A	reports/governed_evolution/sandbox_receipts.jsonl
A	reports/memory_kernel/burn_in_latest.json
A	reports/memory_kernel/burn_in_receipts.jsonl
A	reports/memory_kernel/knowledgeops_bridge_receipts.jsonl
A	reports/memory_kernel/knowledgeops_bridge_requests.jsonl
A	reports/memory_kernel/promotion_decisions.jsonl
A	reports/memory_kernel/reviewed_canonical_receipts.jsonl
A	reports/memory_kernel/write_receipts.jsonl
A	reports/prod_preflight/dry_run_latest.json
A	reports/prod_preflight/full_latest.json
A	reports/prod_preflight/latest.json
A	reports/witness/2026-05-21-algedonic-stream-coverage-audit.md
A	reports/witness/2026-05-21-apply-gate-self-evolution-audit.md
A	reports/witness/2026-05-21-command-plane-dashboard-build.md
A	reports/witness/2026-05-21-command-plane-stack-status.md
A	reports/witness/2026-05-21-command-plane-terminal-bridge-import.md
A	reports/witness/2026-05-21-command-plane-workthread-triage.md
A	reports/witness/2026-05-21-cron-split-brain-audit.md
A	reports/witness/2026-05-21-overnight-autonomous-run.md
A	schemas/control_watch_tower_agent_scorecard.v0.json
A	schemas/control_watch_tower_report.v0.json
A	schemas/long_running_harness.schema.json
A	scripts/bootstrap_persistent_agent.py
A	scripts/com.dharma.agent.70df573a9bbf7b43.plist
A	scripts/consume_review_marks.py
M	scripts/governance/agent_onboard.py
A	scripts/persistent_agent_wake.py
A	scripts/persistent_agent_wake_v2.py
A	scripts/register_dharma_swarm_agent.py
A	scripts/register_external_agent.py
A	scripts/runtime/agent_onboard.sh
A	scripts/runtime/build_causal_registry.py
A	scripts/runtime/codex_composer_interface.py
A	scripts/runtime/codex_composer_mode1.py
A	scripts/runtime/codex_toolbelt_status.sh
A	scripts/runtime/context_quorum.py
A	scripts/runtime/goodworks_dgm_tick.py
A	scripts/runtime/long_running_harness.py
A	scripts/runtime/persistent_agent_census.py
A	scripts/runtime/seed_codex_composer.py
A	scripts/runtime/seed_goodworks_mrv.py
A	scripts/runtime/seed_opus_composer.py
A	scripts/scaffold_agent_authority_passport.py
A	tests/test_assurance_scanners.py
A	tests/test_auto_grade.py
A	tests/test_codex_composer_interface.py
A	tests/test_codex_composer_mode1.py
A	tests/test_codex_composer_status_api.py
A	tests/test_context_quorum.py
A	tests/test_goodworks_dgm.py
A	tests/test_long_running_harness.py
A	tests/test_ontology_runtime_adapters.py
A	tests/test_persistent_agent_census.py
A	tests/test_register_external_agent_script.py
A	tests/test_scaffold_agent_authority_passport.py
A	tests/test_seed_codex_composer.py
A	tests/test_web_search.py
```
#### `stash@{28}` — On chore/command-plane-nav-trim: round2-final-2
```text
M	ACTIVE_SURFACE_MANIFEST.yaml
M	CLAUDE.md
M	Makefile
M	api/chat_tools.py
M	api/main.py
A	api/routers/goodworks_dgm.py
A	api/routers/pool.py
A	dashboard/src/app/dashboard/goodworks/page.tsx
A	dashboard/src/hooks/useGoodworksDgm.ts
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.ts
M	dashboard/src/lib/types.ts
A	dharma_swarm/gen_eval_harness.py
A	dharma_swarm/goodworks_dgm/__init__.py
A	dharma_swarm/goodworks_dgm/mcp.py
A	dharma_swarm/goodworks_dgm/models.py
A	dharma_swarm/goodworks_dgm/runtime.py
A	dharma_swarm/goodworks_dgm/seed.py
A	dharma_swarm/goodworks_dgm/service.py
A	docs/agents/AUTHORITY_LADDER_SCAFFOLD.md
A	docs/agents/CONTROL_WATCH_TOWER.md
A	docs/agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md
A	docs/agents/REGISTRATION_DESK.md
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/ACTIVE_TRACK.yaml
M	docs/governance/BUILD_SESSION_ENTRYPOINT.md
M	docs/governance/SOVEREIGN_MANIFEST.md
A	docs/ops/AGENT_ONBOARDING.md
A	docs/ops/CODEX_TOOLBELT_ONBOARDING.md
A	docs/ops/LONG_RUNNING_HARNESS.md
A	docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md
A	docs/ops/context_quorum_policy.json
A	docs/plans/COMMAND_PLANE_LONG_RUNNING_HARNESS_APPLICATION.md
A	docs/research/persistent_agents_census_2026-05/00_answer.md
A	docs/research/persistent_agents_census_2026-05/01_live_census.md
A	docs/research/persistent_agents_census_2026-05/02_health_report.md
A	docs/research/persistent_agents_census_2026-05/03_recent_activity.md
A	docs/research/persistent_agents_census_2026-05/04_identity_memory_map.md
A	docs/research/persistent_agents_census_2026-05/05_false_positives.md
A	docs/research/persistent_agents_census_2026-05/06_world_map.md
A	docs/research/persistent_agents_census_2026-05/07_best_practices.md
A	docs/research/persistent_agents_census_2026-05/08_benchmark_matrix.md
A	docs/research/persistent_agents_census_2026-05/09_identity_formation_case_study.md
A	docs/research/persistent_agents_census_2026-05/10_cultivation_architecture.md
A	docs/research/persistent_agents_census_2026-05/11_tracking_schema.md
A	docs/research/persistent_agents_census_2026-05/12_30_day_trial_plan.md
A	docs/research/persistent_agents_census_2026-05/13_ontology_bridge.md
A	docs/research/persistent_agents_census_2026-05/agent_inventory.jsonl
A	docs/research/persistent_agents_census_2026-05/external_systems.jsonl
A	docs/research/persistent_agents_census_2026-05/l4_readiness.jsonl
A	docs/research/persistent_agents_census_2026-05/l4_readiness_report.md
A	docs/research/persistent_agents_census_2026-05/l4_readiness_schema.json
A	docs/research/persistent_agents_census_2026-05/ontology_bridge_matrix.jsonl
A	docs/strategy/agentic_harness_2026-05/00_external_research_sources.md
A	docs/strategy/agentic_harness_2026-05/00_index.md
A	docs/strategy/agentic_harness_2026-05/00_local_evidence_base.md
A	docs/strategy/agentic_harness_2026-05/01_software_3_strategy_brain.md
A	docs/strategy/agentic_harness_2026-05/02_context_quorum_harness_strategy.md
A	docs/strategy/agentic_harness_2026-05/03_repo_cartography_and_ontology_strategy.md
A	docs/strategy/agentic_harness_2026-05/04_memory_palace_strategy.md
A	docs/strategy/agentic_harness_2026-05/05_governance_and_security_strategy.md
A	docs/strategy/agentic_harness_2026-05/06_measurement_and_verifiability_strategy.md
A	docs/strategy/agentic_harness_2026-05/07_command_plane_operator_strategy.md
A	docs/strategy/agentic_harness_2026-05/08_multi_agent_coordination_strategy.md
A	docs/strategy/agentic_harness_2026-05/09_tool_ecosystem_and_router_strategy.md
A	docs/strategy/agentic_harness_2026-05/10_persistent_identity_cultivation_strategy.md
A	examples/agents/hermes_m5_bootstrap.authority_passport.json
A	examples/agents/hermes_m5_bootstrap.registration.json
A	examples/agents/strategy_librarian.registration.json
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
A	schemas/long_running_harness.schema.json
M	scripts/governance/agent_onboard.py
A	scripts/register_external_agent.py
A	scripts/runtime/agent_onboard.sh
A	scripts/runtime/codex_toolbelt_status.sh
A	scripts/runtime/context_quorum.py
A	scripts/runtime/goodworks_dgm_tick.py
A	scripts/runtime/long_running_harness.py
A	scripts/runtime/persistent_agent_census.py
A	scripts/runtime/seed_goodworks_mrv.py
A	scripts/scaffold_agent_authority_passport.py
A	tests/test_context_quorum.py
A	tests/test_goodworks_dgm.py
A	tests/test_long_running_harness.py
A	tests/test_persistent_agent_census.py
A	tests/test_register_external_agent_script.py
A	tests/test_scaffold_agent_authority_passport.py
```
#### `stash@{29}` — On chore/command-plane-nav-trim: round2-temp
```text
M	ACTIVE_SURFACE_MANIFEST.yaml
M	CLAUDE.md
M	Makefile
M	api/chat_tools.py
M	api/main.py
A	api/routers/goodworks_dgm.py
A	api/routers/pool.py
A	dashboard/registry.json
A	dashboard/src/app/dashboard/goodworks/page.tsx
A	dashboard/src/hooks/useGoodworksDgm.ts
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.ts
M	dashboard/src/lib/types.ts
A	dashboard/src/registry/r/evidence-row.json
A	dashboard/src/registry/r/glyph.json
A	dashboard/src/registry/r/numeral.json
A	dashboard/src/registry/r/pane.json
A	dashboard/src/registry/r/status-badge.json
A	dashboard/src/registry/r/zone-frame.json
A	dharma_swarm/goodworks_dgm/__init__.py
A	dharma_swarm/goodworks_dgm/mcp.py
A	dharma_swarm/goodworks_dgm/models.py
A	dharma_swarm/goodworks_dgm/runtime.py
A	dharma_swarm/goodworks_dgm/seed.py
A	dharma_swarm/goodworks_dgm/service.py
A	docs/agents/AUTHORITY_LADDER_SCAFFOLD.md
A	docs/agents/CONTROL_WATCH_TOWER.md
A	docs/agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md
A	docs/agents/REGISTRATION_DESK.md
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/ACTIVE_TRACK.yaml
M	docs/governance/BUILD_SESSION_ENTRYPOINT.md
M	docs/governance/SOVEREIGN_MANIFEST.md
A	docs/ops/AGENT_ONBOARDING.md
A	docs/ops/CODEX_TOOLBELT_ONBOARDING.md
A	docs/ops/LONG_RUNNING_HARNESS.md
A	docs/ops/context_quorum_policy.json
A	docs/plans/COMMAND_PLANE_LONG_RUNNING_HARNESS_APPLICATION.md
A	docs/research/persistent_agents_census_2026-05/00_answer.md
A	docs/research/persistent_agents_census_2026-05/01_live_census.md
A	docs/research/persistent_agents_census_2026-05/02_health_report.md
A	docs/research/persistent_agents_census_2026-05/03_recent_activity.md
A	docs/research/persistent_agents_census_2026-05/04_identity_memory_map.md
A	docs/research/persistent_agents_census_2026-05/05_false_positives.md
A	docs/research/persistent_agents_census_2026-05/06_world_map.md
A	docs/research/persistent_agents_census_2026-05/07_best_practices.md
A	docs/research/persistent_agents_census_2026-05/08_benchmark_matrix.md
A	docs/research/persistent_agents_census_2026-05/09_identity_formation_case_study.md
A	docs/research/persistent_agents_census_2026-05/10_cultivation_architecture.md
A	docs/research/persistent_agents_census_2026-05/11_tracking_schema.md
A	docs/research/persistent_agents_census_2026-05/12_30_day_trial_plan.md
A	docs/research/persistent_agents_census_2026-05/13_ontology_bridge.md
A	docs/research/persistent_agents_census_2026-05/agent_inventory.jsonl
A	docs/research/persistent_agents_census_2026-05/external_systems.jsonl
A	docs/research/persistent_agents_census_2026-05/l4_readiness.jsonl
A	docs/research/persistent_agents_census_2026-05/l4_readiness_report.md
A	docs/research/persistent_agents_census_2026-05/l4_readiness_schema.json
A	docs/research/persistent_agents_census_2026-05/ontology_bridge_matrix.jsonl
A	docs/strategy/agentic_harness_2026-05/00_external_research_sources.md
A	docs/strategy/agentic_harness_2026-05/00_index.md
A	docs/strategy/agentic_harness_2026-05/00_local_evidence_base.md
A	docs/strategy/agentic_harness_2026-05/01_software_3_strategy_brain.md
A	docs/strategy/agentic_harness_2026-05/02_context_quorum_harness_strategy.md
A	docs/strategy/agentic_harness_2026-05/03_repo_cartography_and_ontology_strategy.md
A	docs/strategy/agentic_harness_2026-05/04_memory_palace_strategy.md
A	docs/strategy/agentic_harness_2026-05/05_governance_and_security_strategy.md
A	docs/strategy/agentic_harness_2026-05/06_measurement_and_verifiability_strategy.md
A	docs/strategy/agentic_harness_2026-05/07_command_plane_operator_strategy.md
A	docs/strategy/agentic_harness_2026-05/08_multi_agent_coordination_strategy.md
A	docs/strategy/agentic_harness_2026-05/09_tool_ecosystem_and_router_strategy.md
A	docs/strategy/agentic_harness_2026-05/10_persistent_identity_cultivation_strategy.md
A	examples/agents/hermes_m5_bootstrap.authority_passport.json
A	examples/agents/hermes_m5_bootstrap.registration.json
A	examples/agents/strategy_librarian.registration.json
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
A	schemas/long_running_harness.schema.json
M	scripts/governance/agent_onboard.py
A	scripts/register_external_agent.py
A	scripts/runtime/agent_onboard.sh
A	scripts/runtime/codex_toolbelt_status.sh
A	scripts/runtime/context_quorum.py
A	scripts/runtime/goodworks_dgm_tick.py
A	scripts/runtime/long_running_harness.py
A	scripts/runtime/persistent_agent_census.py
A	scripts/runtime/seed_goodworks_mrv.py
A	scripts/scaffold_agent_authority_passport.py
A	tests/test_context_quorum.py
A	tests/test_goodworks_dgm.py
A	tests/test_long_running_harness.py
A	tests/test_persistent_agent_census.py
A	tests/test_register_external_agent_script.py
A	tests/test_scaffold_agent_authority_passport.py
```
#### `stash@{30}` — On chore/command-plane-nav-trim: phase1-commit-temp
```text
M	ACTIVE_SURFACE_MANIFEST.yaml
M	CLAUDE.md
M	Makefile
M	api/chat_tools.py
M	api/main.py
M	dashboard/src/app/globals.css
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.ts
A	dashboard/src/lib/motion.ts
M	dashboard/src/lib/theme.ts
M	dashboard/src/lib/types.ts
M	dharma_swarm/daemon_config.py
M	dharma_swarm/evolution.py
M	dharma_swarm/orchestrate_live.py
M	dharma_swarm/providers.py
M	dharma_swarm/resilience.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/ACTIVE_TRACK.yaml
M	docs/governance/BUILD_SESSION_ENTRYPOINT.md
M	docs/governance/SOVEREIGN_MANIFEST.md
M	docs/plans/COMMAND_PLANE_CHECKLIST.md
M	reports/governance/active_track_evidence.json
M	reports/governance/active_track_evidence.md
M	scripts/governance/agent_onboard.py
M	tests/test_daemon_config.py
```
#### `stash@{31}` — WIP on research/persistent-agents-deepdive-2026-05: 39291ad3 Add persistent agents landscape survey
```text
M	.env.example
M	CLAUDE.md
M	Makefile
M	api/graphql/schema.py
M	api/routers/agents.py
M	api/routers/chat.py
M	api/routers/graphql_router.py
M	api/routers/ontology.py
M	dashboard/src/lib/dashboardNav.test.ts
M	dashboard/src/lib/dashboardNav.ts
M	dharma_swarm/agent_registry.py
M	dharma_swarm/agent_runner.py
M	dharma_swarm/api_keys.py
M	dharma_swarm/base_provider.py
M	dharma_swarm/external_agent_registration.py
M	dharma_swarm/memory_kernel/surface_specs_extended.py
M	dharma_swarm/model_hierarchy.py
M	dharma_swarm/neural_consolidator.py
M	dharma_swarm/ontology.py
M	dharma_swarm/ontology_adapters.py
M	dharma_swarm/provider_matrix.py
M	dharma_swarm/provider_policy.py
M	dharma_swarm/providers.py
M	dharma_swarm/runtime_provider.py
M	dharma_swarm/runtime_state.py
M	dharma_swarm/skills/jagat-kalyan.skill.md
M	dharma_swarm/skills/jagat_kalyan.skill.md
M	dharma_swarm/swarm_router.py
M	dharma_swarm/telemetry_plane.py
M	dharma_swarm/telos_substrate.py
M	dharma_swarm/thinkodynamic_director.py
M	dharma_swarm/tui/app.py
M	dharma_swarm/tui/model_routing.py
M	docs/README.md
M	docs/architecture/WORLD_ZEITGEIST.md
M	docs/docops/AUTO_INVENTORY.md
M	docs/doctrine/LIVE_ROADMAP.md
M	docs/doctrine/OPERATIONAL_DOCTRINE.md
M	docs/dse/JAGAT_KALYAN_RESEARCH_BRIEF.md
M	docs/governance/CANONICAL_DOC_STACK.md
M	docs/governance/REPO_GOVERNANCE_AUDIT.md
M	docs/governance/SOVEREIGN_MANIFEST.md
M	docs/loomwork/2026-05-07-loomwork-design.md
M	docs/loomwork/vision/04_scale_architecture.md
M	docs/ops/RUNBOOK.md
M	docs/reports/PLANETARY_RECIPROCITY_COMMONS_PUBLIC_BRIEF_2026-03-11.md
M	docs/research/persistent_agents_2026-05/I1_dharma_swarm_audit.md
M	docs/research/persistent_agents_2026-05/I2_substrate_persistence.md
M	docs/research/persistent_agents_2026-05/scorecard.jsonl
M	docs/vision_maps/2026-05-07_attractor_closure/06_outward_organs.md
M	lodestones/README.md
M	run_daemon.sh
M	tests/test_agent_registry.py
M	tests/test_agent_runner.py
M	tests/test_api_keys.py
M	tests/test_base_provider.py
M	tests/test_dashboard_chat_router.py
M	tests/test_external_agent_registration.py
M	tests/test_graphql_router.py
M	tests/test_memory_surface_census.py
M	tests/test_neural_consolidator.py
M	tests/test_ontology_registry.py
M	tests/test_ontology_router.py
M	tests/test_provider_policy.py
M	tests/test_runtime_provider.py
M	tests/test_runtime_state.py
M	tests/test_telemetry_plane.py
M	tests/test_telic_seam.py
M	tests/tui/test_model_routing.py
```
#### `stash@{32}` — WIP on research/persistent-agents-2026-05: aa48a1f7 research(persistent-agents): X1 Hermes + I1 dharma_swarm audit (v2 path)
```text
M	CLAUDE.md
M	dharma_swarm/agent_runner.py
M	dharma_swarm/config.py
M	dharma_swarm/context.py
M	dharma_swarm/stigmergy.py
M	dharma_swarm/swarm.py
M	dharma_swarm/web_search.py
M	dharma_swarm/world_model.py
M	dharma_swarm/yoga_node.py
M	tests/test_agent_runner.py
M	tests/test_config.py
M	tests/test_stigmergy.py
M	tests/test_world_model.py
M	tests/test_yoga_node.py
M	xray_report.md
```
#### `stash@{33}` — On cleanup/memory-kernel-release-split-2026-05-17: codex-temp-before-gitignore-cleanup-2026-05-18
```text
M	.gitignore
M	Makefile
M	PRODUCT_SURFACE.md
M	benchmarks/README.md
A	benchmarks/fixtures/swarm_native_redteam_cases.json
A	benchmarks/swarm_native_redteam.py
M	dharma_swarm/agent_runner.py
M	dharma_swarm/config.py
M	dharma_swarm/context.py
M	dharma_swarm/operator_core/control_surface.py
A	dharma_swarm/operator_core/control_surface_governed_evolution.py
M	dharma_swarm/operator_core/control_surface_models.py
M	dharma_swarm/swarm.py
M	dharma_swarm/web_search.py
M	dharma_swarm/yoga_node.py
M	docs/architecture/NAVIGATION.md
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/CANONICAL_DOC_STACK.md
M	docs/governance/SOVEREIGN_MANIFEST.md
A	scripts/governed_evolution_sandbox_demo.py
M	scripts/operator_prod_smoke.py
A	scripts/prod_preflight.py
A	scripts/runtime/build_causal_registry.py
M	tests/test_agent_runner.py
M	tests/test_config.py
M	tests/test_control_surface.py
A	tests/test_governed_evolution_sandbox_demo.py
M	tests/test_operator_prod_smoke.py
A	tests/test_swarm_native_redteam_benchmark.py
A	tests/test_web_search.py
M	tests/test_yoga_node.py
```
#### `stash@{34}` — On cleanup/recursive-evolution-lane-2026-05-16: lane-mask-rv-whitebox-artifacts-2026-05-16
```text
A	experiments/mask_rv_whitebox/cache/activations/024ed3ce-2128-43b7-a869-c9935f2b9096_err.npz
A	experiments/mask_rv_whitebox/cache/activations/073152B8E1F1.npz
A	experiments/mask_rv_whitebox/cache/activations/32EE3324BB48_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/47a03596-4745-4b73-8128-0d4e3d7d0092_err_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/5A127C872261.npz
A	experiments/mask_rv_whitebox/cache/activations/5B3E4180F890.npz
A	experiments/mask_rv_whitebox/cache/activations/5EF3DC0A4A37.npz
A	experiments/mask_rv_whitebox/cache/activations/627411C67739.npz
A	experiments/mask_rv_whitebox/cache/activations/676f535fe636d9ab52c39bfd.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5360e1d0621a03333334.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5362e7ddfbf5711245b9.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5363f4cba8c4c95e2152.npz
A	experiments/mask_rv_whitebox/cache/activations/676f536422c41b7a26f4a27d.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5365011028365133b0e8.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5366eaa2d7ec319b5c7c.npz
A	experiments/mask_rv_whitebox/cache/activations/676f536a1e4a18dde96165b2.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca5b8bdfee84842ce32.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca68dc7b21a3f7f6b6f.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca740c14dc39260baf0.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca79787f2debf90b78c.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca8ffd1adb2f381649f.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca91d6d3aad08c49924.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca9c158b542095f827d.npz
A	experiments/mask_rv_whitebox/cache/activations/67736afd37d92e457bae5e65.npz
A	experiments/mask_rv_whitebox/cache/activations/67736afde343f23b7dd32af7.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b00184ad021c90387d3.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b0089bb46fd1454f4b0.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b00f2c3d86665eba315.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b012315f4101511d93b.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b0177a5fc1bbfdb74a9.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b017e3b417e660ea999.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b01a1dae27c161f25b0.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b01af4f3a45a3ce4ab4.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b01efc911c62aa9bc37.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b025cff1c34440ab43b.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b02c2895ecf63b84e6a.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b02d6d6ab98bfce9b23.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b0348e8698a62fb5200.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b0361d3d8c21199fa44.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05df1ad57c9fb002b38.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05e032913a2d1be9bc0.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05e1d5c7d5ff175ead4.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05e259546eece759a47.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05e9e8668738d6dd25f.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05f032913a2d1be9bd9.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05f333046a9d420b171.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05fc4444204dae7b42e.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a060032913a2d1be9bf2.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a0628e0bd2f0f9149a01.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a063d9fa9ffd1ad8d18b.npz
A	experiments/mask_rv_whitebox/cache/activations/677677c02d1c5605cb9cdd43.npz
A	experiments/mask_rv_whitebox/cache/activations/677677c04a14bb0dd4dac678.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171520678d6e4c76a349.npz
A	experiments/mask_rv_whitebox/cache/activations/67771716bb03dfd5f50d8076.npz
A	experiments/mask_rv_whitebox/cache/activations/67771717dcff84e2f0ca1977.npz
A	experiments/mask_rv_whitebox/cache/activations/67771717fdce5e74b1b2ab90.npz
A	experiments/mask_rv_whitebox/cache/activations/67771717fdce5e74b1b2aba0.npz
A	experiments/mask_rv_whitebox/cache/activations/677717184e606b1d31f67c53.npz
A	experiments/mask_rv_whitebox/cache/activations/67771718bb03dfd5f50d80ae.npz
A	experiments/mask_rv_whitebox/cache/activations/67771718dac5a736499feba6.npz
A	experiments/mask_rv_whitebox/cache/activations/677717193a6d28a71a0fb1fb.npz
A	experiments/mask_rv_whitebox/cache/activations/677717194e606b1d31f67c8b.npz
A	experiments/mask_rv_whitebox/cache/activations/677717197bf2f0fbf74c5df6.npz
A	experiments/mask_rv_whitebox/cache/activations/67771719dd7a1c86eaf48b15.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171a13943c91dffe785e.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171a359b72111f8c449a.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171a7a6be99e497fa9e9.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171a7a6be99e497fa9fe.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171b5497661900231034.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171ba239660c59de49f8.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171bdd7a1c86eaf48b2e.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171beecb18a7e1ec6677.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171c980d7873e3890b49.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171cdcff84e2f0ca1a08.npz
A	experiments/mask_rv_whitebox/cache/activations/677c4b3a0d688ab8681454f5.npz
A	experiments/mask_rv_whitebox/cache/activations/677c4b3a32f2a805c1b70278_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677c4b3a984dca9838a7bc72_dup.npz
A	experiments/mask_rv_whitebox/cache/activations/677c4b3a984dca9838a7bc72_dup_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca1630ca3c32a6e60560f_dup.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca163b4e0cec49896514f_dup.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca165466da7ed3b1ed66f_dup.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca1657597b932e9e0f70a.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca165b4e0cec498965178.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca165d69ec3708131fbb2.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca16726c55784390d50ed.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca167ef3e7cc06ed256d2_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca1684b96f907dbf5b76e.npz
A	experiments/mask_rv_whitebox/cache/activations/677d553604c3fb1dcbf942a7_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5537272e0e57ee739bd4.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5537500c5a8f11b186ac.npz
A	experiments/mask_rv_whitebox/cache/activations/677d553871bef67330e54a38.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5538f65d5feac46a8f7f_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5539d0afc24d80328264.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5539dd9411e6740876b4.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5539fe946d6b9428f2af.npz
A	experiments/mask_rv_whitebox/cache/activations/677d553a36d8f3d3fd721f1f_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677d553e0e75fcaf2976f9e9_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5540dd9411e6740876db.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5541a322fac77a47f823.npz
A	experiments/mask_rv_whitebox/cache/activations/677d55440c6cfd55d2964322.npz
A	experiments/mask_rv_whitebox/cache/activations/677d554acb2a917fcc101d98.npz
A	experiments/mask_rv_whitebox/cache/activations/67817e8c72fc706f4bb07ed7.npz
A	experiments/mask_rv_whitebox/cache/activations/67817e8d342c614cca814d6b.npz
A	experiments/mask_rv_whitebox/cache/activations/67817e8fb2c8882f84f85843.npz
A	experiments/mask_rv_whitebox/cache/activations/67817e9087aaa6c38044990e.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134d6bf44ac103fd7031.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134d75a35a2d0514b8d4.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134d7daa299a4a624d90.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134db382c92ba5d9ae62_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134e3a508c2df52e4c3f.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134e6b9341206c79ee01.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134eac38580d2ac3e4de_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134ec684a8b9e6e3e4cb.npz
A	experiments/mask_rv_whitebox/cache/activations/6783135070bdc0d2bfe05042_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/67849ecbdc95cbbe5c8d3f9b.npz
A	experiments/mask_rv_whitebox/cache/activations/67849ecd4c3c525464c20e81.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0358b9d79144b755cc.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0443986f116157b1be.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0541940eae49cf32e3.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef05e87fa36ec0ee1180.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef05fb31f2ec884cc740.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0741940eae49cf32fd.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef074b473623a516ae3c.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0784cf3709f0a2ec4f.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef07b573163cb7c8b166.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef084b473623a516ae5f.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef089f56b5f0ead5b12d.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275037753e7a22ebb11.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275a033c4ad46dc55f2.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275bbbe6f2a40494678.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275c242f7dac64128f5.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275ee047a5a11c5ce9b.npz
A	experiments/mask_rv_whitebox/cache/activations/678992762e03ca7652badf5a.npz
A	experiments/mask_rv_whitebox/cache/activations/67899276c242f7dac641290f.npz
A	experiments/mask_rv_whitebox/cache/activations/678992771730971f8902f36d.npz
A	experiments/mask_rv_whitebox/cache/activations/678e2bae6cb9edd18bfca34e.npz
A	experiments/mask_rv_whitebox/cache/activations/678e2bafabd0af51a672ee2b.npz
A	experiments/mask_rv_whitebox/cache/activations/678e2bb03c1ed7883522e64b.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a222ae8820756caba1.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a331ed060f247f278e.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a3fef0d8afb03eaf96.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a4a1304fb4b3a46c3a.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a5aee43a44e3af9ae4.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a609fdccc0b27d7398.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a8d522f8db40d762d9.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a8fef0d8afb03eafdc.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a931ed060f247f27f3.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a9ad2f430942f3f649.npz
A	experiments/mask_rv_whitebox/cache/activations/679015aa2571798d2a4d2a78.npz
A	experiments/mask_rv_whitebox/cache/activations/679015aaf05aede25a2a038d.npz
A	experiments/mask_rv_whitebox/cache/activations/679015ab2571798d2a4d2a91.npz
A	experiments/mask_rv_whitebox/cache/activations/679015ab31ed060f247f280c.npz
A	experiments/mask_rv_whitebox/cache/activations/679015abb63dfdabe513c313.npz
A	experiments/mask_rv_whitebox/cache/activations/679015acd1df171b03978e10.npz
A	experiments/mask_rv_whitebox/cache/activations/679015ad8ecbc499d01bd315.npz
A	experiments/mask_rv_whitebox/cache/activations/679015adad734e541144ecd2.npz
A	experiments/mask_rv_whitebox/cache/activations/679015adfef0d8afb03eb00e.npz
A	experiments/mask_rv_whitebox/cache/activations/679015aed522f8db40d7633f.npz
A	experiments/mask_rv_whitebox/cache/activations/679015afb63dfdabe513c345.npz
A	experiments/mask_rv_whitebox/cache/activations/679015afc80c1eb70d0932fc.npz
A	experiments/mask_rv_whitebox/cache/activations/679015afcb0357a228a65a00.npz
A	experiments/mask_rv_whitebox/cache/activations/679015b0d522f8db40d76358.npz
A	experiments/mask_rv_whitebox/cache/activations/679015b24a59c812ead9c67b.npz
A	experiments/mask_rv_whitebox/cache/activations/6794f4a6c5bc4f1a4d39a3a6.npz
A	experiments/mask_rv_whitebox/cache/activations/6794f4a790910d360abc270d.npz
A	experiments/mask_rv_whitebox/cache/activations/6794f4a794ce1a002c6671f3.npz
A	experiments/mask_rv_whitebox/cache/activations/6794f4a797042cb833b54ac9.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd05a1575c4910b2f8.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd05a1575c4910b312.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd0a51ed16578b9152.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd4f048eb25021cd47.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd7d728bf401a3efbd.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed12161e557ebd63d21.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed129a630abb104a519.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed24f048eb25021cd93.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed33ff874b837460e75.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed63ff874b837460eb3.npz
A	experiments/mask_rv_whitebox/cache/activations/67975edad94dfb05c4d78f07.npz
A	experiments/mask_rv_whitebox/cache/activations/67975edbe260b367c78ca07f.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab33a2a7776bc65e20e82f.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa04976f4830f1270db.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa1d97026f407fa32b1.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa1d97026f407fa32c0.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa1f18d5a473dc77056.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa2a1ec5f98daf75ec2.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa3145008ba956213c3.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa32a6fca04620b13cd_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa45d113ea3b741a566.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa49af16aa2e897219c_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa600b2d86ca70b072c.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa82a6fca04620b146c.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8faacf8f1fda13f9ba16.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fab461eb193ef95b490.npz
A	experiments/mask_rv_whitebox/cache/activations/D3B5A70891AD.npz
A	experiments/mask_rv_whitebox/cache/activations/F98D35EB8315.npz
A	experiments/mask_rv_whitebox/cache/activations/b4e16587-3d4f-4eef-938b-d694bd8b42d3_err.npz
A	experiments/mask_rv_whitebox/cache/activations/b4e16587-3d4f-4eef-938b-d694bd8b42d3_err_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/f99ca987-c3f2-42a3-94a5-6dce08b39fc7_err_dd.npz
A	experiments/mask_rv_whitebox/cache/activations_debug/6774a063d9fa9ffd1ad8d18b.npz
A	experiments/mask_rv_whitebox/cache/activations_debug/67817e8d342c614cca814d6b.npz
A	experiments/mask_rv_whitebox/cache/mask_raw.parquet
A	experiments/mask_rv_whitebox/cache/mask_split.json
A	experiments/mask_rv_whitebox/cache/mask_stratified.parquet
A	experiments/mask_rv_whitebox/cache/rv_scalars.parquet
A	experiments/mask_rv_whitebox/figures/roc.png
A	experiments/mask_rv_whitebox/inference_real.log
A	experiments/mask_rv_whitebox/results/auroc.json
A	experiments/mask_rv_whitebox/results/inference_results.jsonl
A	experiments/mask_rv_whitebox/results/inference_results_debug.jsonl
A	experiments/mask_rv_whitebox/results/multifeature_exploratory.json
A	experiments/mask_rv_whitebox/results/per_arm_predictions.csv
```
#### `stash@{35}` — On cleanup/memory-kernel-shadow-context-main-2026-05-13: wip: freeze prod preflight report residue 2026-05-16
```text
A	reports/prod_preflight/latest.json
```
#### `stash@{36}` — On cleanup/memory-kernel-shadow-context-main-2026-05-13: wip: freeze before memory kernel lane split 2026-05-16
```text
M	.gitignore
M	Makefile
M	dharma_swarm/evolution.py
M	dharma_swarm/memory_kernel/adapters/__init__.py
A	dharma_swarm/memory_kernel/adapters/file_snapshot.py
M	dharma_swarm/memory_kernel/adapters/read_only.py
M	dharma_swarm/memory_kernel/facade.py
M	dharma_swarm/memory_kernel/readiness.py
M	dharma_swarm/memory_kernel/surface_specs_extended.py
M	dharma_swarm/operator_core/control_surface.py
M	dharma_swarm/operator_core/control_surface_memory_readiness.py
A	dharma_swarm/operator_core/control_surface_recursive.py
M	dharma_swarm/recursive_discovery.py
A	dharma_swarm/swarm_integrity_benchmark.py
M	docs/docops/AUTO_INVENTORY.md
M	docs/governance/INTEGRATION_LANDING_ORDER.md
M	docs/governance/SOVEREIGN_MANIFEST.md
A	experiments/mask_rv_whitebox/cache/activations/024ed3ce-2128-43b7-a869-c9935f2b9096_err.npz
A	experiments/mask_rv_whitebox/cache/activations/073152B8E1F1.npz
A	experiments/mask_rv_whitebox/cache/activations/32EE3324BB48_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/47a03596-4745-4b73-8128-0d4e3d7d0092_err_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/5A127C872261.npz
A	experiments/mask_rv_whitebox/cache/activations/5B3E4180F890.npz
A	experiments/mask_rv_whitebox/cache/activations/5EF3DC0A4A37.npz
A	experiments/mask_rv_whitebox/cache/activations/627411C67739.npz
A	experiments/mask_rv_whitebox/cache/activations/676f535fe636d9ab52c39bfd.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5360e1d0621a03333334.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5362e7ddfbf5711245b9.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5363f4cba8c4c95e2152.npz
A	experiments/mask_rv_whitebox/cache/activations/676f536422c41b7a26f4a27d.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5365011028365133b0e8.npz
A	experiments/mask_rv_whitebox/cache/activations/676f5366eaa2d7ec319b5c7c.npz
A	experiments/mask_rv_whitebox/cache/activations/676f536a1e4a18dde96165b2.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca5b8bdfee84842ce32.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca68dc7b21a3f7f6b6f.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca740c14dc39260baf0.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca79787f2debf90b78c.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca8ffd1adb2f381649f.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca91d6d3aad08c49924.npz
A	experiments/mask_rv_whitebox/cache/activations/67709ca9c158b542095f827d.npz
A	experiments/mask_rv_whitebox/cache/activations/67736afd37d92e457bae5e65.npz
A	experiments/mask_rv_whitebox/cache/activations/67736afde343f23b7dd32af7.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b00184ad021c90387d3.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b0089bb46fd1454f4b0.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b00f2c3d86665eba315.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b012315f4101511d93b.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b0177a5fc1bbfdb74a9.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b017e3b417e660ea999.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b01a1dae27c161f25b0.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b01af4f3a45a3ce4ab4.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b01efc911c62aa9bc37.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b025cff1c34440ab43b.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b02c2895ecf63b84e6a.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b02d6d6ab98bfce9b23.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b0348e8698a62fb5200.npz
A	experiments/mask_rv_whitebox/cache/activations/67736b0361d3d8c21199fa44.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05df1ad57c9fb002b38.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05e032913a2d1be9bc0.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05e1d5c7d5ff175ead4.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05e259546eece759a47.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05e9e8668738d6dd25f.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05f032913a2d1be9bd9.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05f333046a9d420b171.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a05fc4444204dae7b42e.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a060032913a2d1be9bf2.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a0628e0bd2f0f9149a01.npz
A	experiments/mask_rv_whitebox/cache/activations/6774a063d9fa9ffd1ad8d18b.npz
A	experiments/mask_rv_whitebox/cache/activations/677677c02d1c5605cb9cdd43.npz
A	experiments/mask_rv_whitebox/cache/activations/677677c04a14bb0dd4dac678.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171520678d6e4c76a349.npz
A	experiments/mask_rv_whitebox/cache/activations/67771716bb03dfd5f50d8076.npz
A	experiments/mask_rv_whitebox/cache/activations/67771717dcff84e2f0ca1977.npz
A	experiments/mask_rv_whitebox/cache/activations/67771717fdce5e74b1b2ab90.npz
A	experiments/mask_rv_whitebox/cache/activations/67771717fdce5e74b1b2aba0.npz
A	experiments/mask_rv_whitebox/cache/activations/677717184e606b1d31f67c53.npz
A	experiments/mask_rv_whitebox/cache/activations/67771718bb03dfd5f50d80ae.npz
A	experiments/mask_rv_whitebox/cache/activations/67771718dac5a736499feba6.npz
A	experiments/mask_rv_whitebox/cache/activations/677717193a6d28a71a0fb1fb.npz
A	experiments/mask_rv_whitebox/cache/activations/677717194e606b1d31f67c8b.npz
A	experiments/mask_rv_whitebox/cache/activations/677717197bf2f0fbf74c5df6.npz
A	experiments/mask_rv_whitebox/cache/activations/67771719dd7a1c86eaf48b15.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171a13943c91dffe785e.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171a359b72111f8c449a.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171a7a6be99e497fa9e9.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171a7a6be99e497fa9fe.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171b5497661900231034.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171ba239660c59de49f8.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171bdd7a1c86eaf48b2e.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171beecb18a7e1ec6677.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171c980d7873e3890b49.npz
A	experiments/mask_rv_whitebox/cache/activations/6777171cdcff84e2f0ca1a08.npz
A	experiments/mask_rv_whitebox/cache/activations/677c4b3a0d688ab8681454f5.npz
A	experiments/mask_rv_whitebox/cache/activations/677c4b3a32f2a805c1b70278_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677c4b3a984dca9838a7bc72_dup.npz
A	experiments/mask_rv_whitebox/cache/activations/677c4b3a984dca9838a7bc72_dup_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca1630ca3c32a6e60560f_dup.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca163b4e0cec49896514f_dup.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca165466da7ed3b1ed66f_dup.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca1657597b932e9e0f70a.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca165b4e0cec498965178.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca165d69ec3708131fbb2.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca16726c55784390d50ed.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca167ef3e7cc06ed256d2_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677ca1684b96f907dbf5b76e.npz
A	experiments/mask_rv_whitebox/cache/activations/677d553604c3fb1dcbf942a7_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5537272e0e57ee739bd4.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5537500c5a8f11b186ac.npz
A	experiments/mask_rv_whitebox/cache/activations/677d553871bef67330e54a38.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5538f65d5feac46a8f7f_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5539d0afc24d80328264.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5539dd9411e6740876b4.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5539fe946d6b9428f2af.npz
A	experiments/mask_rv_whitebox/cache/activations/677d553a36d8f3d3fd721f1f_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677d553e0e75fcaf2976f9e9_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5540dd9411e6740876db.npz
A	experiments/mask_rv_whitebox/cache/activations/677d5541a322fac77a47f823.npz
A	experiments/mask_rv_whitebox/cache/activations/677d55440c6cfd55d2964322.npz
A	experiments/mask_rv_whitebox/cache/activations/677d554acb2a917fcc101d98.npz
A	experiments/mask_rv_whitebox/cache/activations/67817e8c72fc706f4bb07ed7.npz
A	experiments/mask_rv_whitebox/cache/activations/67817e8d342c614cca814d6b.npz
A	experiments/mask_rv_whitebox/cache/activations/67817e8fb2c8882f84f85843.npz
A	experiments/mask_rv_whitebox/cache/activations/67817e9087aaa6c38044990e.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134d6bf44ac103fd7031.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134d75a35a2d0514b8d4.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134d7daa299a4a624d90.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134db382c92ba5d9ae62_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134e3a508c2df52e4c3f.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134e6b9341206c79ee01.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134eac38580d2ac3e4de_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/6783134ec684a8b9e6e3e4cb.npz
A	experiments/mask_rv_whitebox/cache/activations/6783135070bdc0d2bfe05042_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/67849ecbdc95cbbe5c8d3f9b.npz
A	experiments/mask_rv_whitebox/cache/activations/67849ecd4c3c525464c20e81.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0358b9d79144b755cc.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0443986f116157b1be.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0541940eae49cf32e3.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef05e87fa36ec0ee1180.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef05fb31f2ec884cc740.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0741940eae49cf32fd.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef074b473623a516ae3c.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef0784cf3709f0a2ec4f.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef07b573163cb7c8b166.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef084b473623a516ae5f.npz
A	experiments/mask_rv_whitebox/cache/activations/6787ef089f56b5f0ead5b12d.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275037753e7a22ebb11.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275a033c4ad46dc55f2.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275bbbe6f2a40494678.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275c242f7dac64128f5.npz
A	experiments/mask_rv_whitebox/cache/activations/67899275ee047a5a11c5ce9b.npz
A	experiments/mask_rv_whitebox/cache/activations/678992762e03ca7652badf5a.npz
A	experiments/mask_rv_whitebox/cache/activations/67899276c242f7dac641290f.npz
A	experiments/mask_rv_whitebox/cache/activations/678992771730971f8902f36d.npz
A	experiments/mask_rv_whitebox/cache/activations/678e2bae6cb9edd18bfca34e.npz
A	experiments/mask_rv_whitebox/cache/activations/678e2bafabd0af51a672ee2b.npz
A	experiments/mask_rv_whitebox/cache/activations/678e2bb03c1ed7883522e64b.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a222ae8820756caba1.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a331ed060f247f278e.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a3fef0d8afb03eaf96.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a4a1304fb4b3a46c3a.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a5aee43a44e3af9ae4.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a609fdccc0b27d7398.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a8d522f8db40d762d9.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a8fef0d8afb03eafdc.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a931ed060f247f27f3.npz
A	experiments/mask_rv_whitebox/cache/activations/679015a9ad2f430942f3f649.npz
A	experiments/mask_rv_whitebox/cache/activations/679015aa2571798d2a4d2a78.npz
A	experiments/mask_rv_whitebox/cache/activations/679015aaf05aede25a2a038d.npz
A	experiments/mask_rv_whitebox/cache/activations/679015ab2571798d2a4d2a91.npz
A	experiments/mask_rv_whitebox/cache/activations/679015ab31ed060f247f280c.npz
A	experiments/mask_rv_whitebox/cache/activations/679015abb63dfdabe513c313.npz
A	experiments/mask_rv_whitebox/cache/activations/679015acd1df171b03978e10.npz
A	experiments/mask_rv_whitebox/cache/activations/679015ad8ecbc499d01bd315.npz
A	experiments/mask_rv_whitebox/cache/activations/679015adad734e541144ecd2.npz
A	experiments/mask_rv_whitebox/cache/activations/679015adfef0d8afb03eb00e.npz
A	experiments/mask_rv_whitebox/cache/activations/679015aed522f8db40d7633f.npz
A	experiments/mask_rv_whitebox/cache/activations/679015afb63dfdabe513c345.npz
A	experiments/mask_rv_whitebox/cache/activations/679015afc80c1eb70d0932fc.npz
A	experiments/mask_rv_whitebox/cache/activations/679015afcb0357a228a65a00.npz
A	experiments/mask_rv_whitebox/cache/activations/679015b0d522f8db40d76358.npz
A	experiments/mask_rv_whitebox/cache/activations/679015b24a59c812ead9c67b.npz
A	experiments/mask_rv_whitebox/cache/activations/6794f4a6c5bc4f1a4d39a3a6.npz
A	experiments/mask_rv_whitebox/cache/activations/6794f4a790910d360abc270d.npz
A	experiments/mask_rv_whitebox/cache/activations/6794f4a794ce1a002c6671f3.npz
A	experiments/mask_rv_whitebox/cache/activations/6794f4a797042cb833b54ac9.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd05a1575c4910b2f8.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd05a1575c4910b312.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd0a51ed16578b9152.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd4f048eb25021cd47.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ecd7d728bf401a3efbd.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed12161e557ebd63d21.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed129a630abb104a519.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed24f048eb25021cd93.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed33ff874b837460e75.npz
A	experiments/mask_rv_whitebox/cache/activations/67975ed63ff874b837460eb3.npz
A	experiments/mask_rv_whitebox/cache/activations/67975edad94dfb05c4d78f07.npz
A	experiments/mask_rv_whitebox/cache/activations/67975edbe260b367c78ca07f.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab33a2a7776bc65e20e82f.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa04976f4830f1270db.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa1d97026f407fa32b1.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa1d97026f407fa32c0.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa1f18d5a473dc77056.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa2a1ec5f98daf75ec2.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa3145008ba956213c3.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa32a6fca04620b13cd_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa45d113ea3b741a566.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa49af16aa2e897219c_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa600b2d86ca70b072c.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fa82a6fca04620b146c.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8faacf8f1fda13f9ba16.npz
A	experiments/mask_rv_whitebox/cache/activations/67ab8fab461eb193ef95b490.npz
A	experiments/mask_rv_whitebox/cache/activations/D3B5A70891AD.npz
A	experiments/mask_rv_whitebox/cache/activations/F98D35EB8315.npz
A	experiments/mask_rv_whitebox/cache/activations/b4e16587-3d4f-4eef-938b-d694bd8b42d3_err.npz
A	experiments/mask_rv_whitebox/cache/activations/b4e16587-3d4f-4eef-938b-d694bd8b42d3_err_dd.npz
A	experiments/mask_rv_whitebox/cache/activations/f99ca987-c3f2-42a3-94a5-6dce08b39fc7_err_dd.npz
A	experiments/mask_rv_whitebox/cache/activations_debug/6774a063d9fa9ffd1ad8d18b.npz
A	experiments/mask_rv_whitebox/cache/activations_debug/67817e8d342c614cca814d6b.npz
A	experiments/mask_rv_whitebox/cache/mask_raw.parquet
A	experiments/mask_rv_whitebox/cache/mask_split.json
A	experiments/mask_rv_whitebox/cache/mask_stratified.parquet
A	experiments/mask_rv_whitebox/cache/rv_scalars.parquet
A	experiments/mask_rv_whitebox/figures/roc.png
A	experiments/mask_rv_whitebox/inference_real.log
A	experiments/mask_rv_whitebox/results/auroc.json
A	experiments/mask_rv_whitebox/results/inference_results.jsonl
A	experiments/mask_rv_whitebox/results/inference_results_debug.jsonl
A	experiments/mask_rv_whitebox/results/multifeature_exploratory.json
A	experiments/mask_rv_whitebox/results/per_arm_predictions.csv
M	scripts/memory_kernel_readiness.py
M	scripts/operator_prod_smoke.py
A	scripts/prod_preflight.py
A	scripts/recursive_shadow_foundry.py
M	tests/test_control_surface.py
M	tests/test_evolution.py
M	tests/test_memory_kernel_adapters.py
M	tests/test_memory_kernel_readiness.py
M	tests/test_operator_prod_smoke.py
A	tests/test_prod_preflight.py
M	tests/test_recursive_discovery.py
A	tests/test_swarm_integrity_benchmark.py
```
#### `stash@{37}` — On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-memory-kernel-base-dirty-2026-05-14
```text
M	dharma_swarm/memory_kernel/surfaces.py
M	dharma_swarm/memory_kernel/writers.py
M	docs/architecture/memory_kernel_current_intent.md
M	docs/architecture/memory_kernel_m4a_shadow_report_sweep.md
M	scripts/memory_writer_sentinel.py
M	tests/test_memory_writer_sentinel.py
```
#### `stash@{38}` — On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-operator-control-smoke-2026-05-14
```text
M	Makefile
M	dharma_swarm/operator_core/control_surface.py
A	dharma_swarm/operator_core/control_surface_memory.py
M	dharma_swarm/operator_core/control_surface_models.py
A	scripts/operator_prod_smoke.py
```
#### `stash@{39}` — On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-knowledgeops-m4b-2026-05-14
```text
A	dharma_swarm/knowledge_ops/__init__.py
A	dharma_swarm/knowledge_ops/cli.py
A	dharma_swarm/knowledge_ops/memory_conflict_review.py
A	dharma_swarm/knowledge_ops/memory_decision_ledger.py
A	dharma_swarm/knowledge_ops/memory_intake.py
A	dharma_swarm/knowledge_ops/memory_promotion_queue.py
A	docs/architecture/memory_kernel_m4b_knowledgeops_writer_readiness.md
A	tests/test_knowledge_ops_memory_intake.py
```
#### `stash@{40}` — On cleanup/memory-kernel-shadow-context-main-2026-05-13: lane-unrelated-research-spec-cleanup-2026-05-14
```text
M	ACTIVE_SURFACE_MANIFEST.yaml
M	docs/MEGAFILE_INDEX.md
M	docs/plans/2026-04-02-specs-spec-forge-seam-plan.md
M	docs/plans/2026-04-03-autonomous-cleanup-overnight-control.md
M	docs/research/README.md
A	docs/research/RECURSIVE_SUPERINTELLIGENCE_STRATEGIC_NODE_2026-05-14.md
M	docs/telos-engine/INDEX.md
A	experiments/mask_rv_whitebox/01_load_mask.py
A	experiments/mask_rv_whitebox/02_run_inference.py
A	experiments/mask_rv_whitebox/03_compute_rv.py
A	experiments/mask_rv_whitebox/04_classifiers.py
A	experiments/mask_rv_whitebox/README.md
A	experiments/mask_rv_whitebox/cache/activations_smoke_pythia/67736b017e3b417e660ea999.npz
A	experiments/mask_rv_whitebox/cache/activations_smoke_pythia/6774a063d9fa9ffd1ad8d18b.npz
A	experiments/mask_rv_whitebox/cache/activations_smoke_pythia/67817e8d342c614cca814d6b.npz
A	experiments/mask_rv_whitebox/cache/mask_raw.parquet
A	experiments/mask_rv_whitebox/cache/mask_split.json
A	experiments/mask_rv_whitebox/cache/mask_stratified.parquet
A	experiments/mask_rv_whitebox/cache/rv_scalars_smoke_pythia.parquet
A	experiments/mask_rv_whitebox/config.yaml
A	experiments/mask_rv_whitebox/inference_smoke.log
A	experiments/mask_rv_whitebox/inference_smoke_pythia.log
A	experiments/mask_rv_whitebox/inference_smoke_qwen.log
A	experiments/mask_rv_whitebox/results/inference_results_smoke_pythia.jsonl
A	quality-reports/bandit.txt
A	quality-reports/fallow.txt
A	quality-reports/hygiene-probe-2026-05-09/bandit.json
A	quality-reports/hygiene-probe-2026-05-09/bandit.stdout
A	quality-reports/hygiene-probe-2026-05-09/bandit.txt
A	quality-reports/hygiene-probe-2026-05-09/compileall.txt
A	quality-reports/hygiene-probe-2026-05-09/dashboard-lint.txt
A	quality-reports/hygiene-probe-2026-05-09/fallow-dashboard.json
A	quality-reports/hygiene-probe-2026-05-09/fallow-dashboard.stderr
A	quality-reports/hygiene-probe-2026-05-09/mypy.txt
A	quality-reports/hygiene-probe-2026-05-09/normalized-findings.jsonl
A	quality-reports/hygiene-probe-2026-05-09/pyright.json
A	quality-reports/hygiene-probe-2026-05-09/pyright.stderr
A	quality-reports/hygiene-probe-2026-05-09/pytest-coverage.txt
A	quality-reports/hygiene-probe-2026-05-09/pytest-file-lock-integration.txt
A	quality-reports/hygiene-probe-2026-05-09/pytest-targeted.txt
A	quality-reports/hygiene-probe-2026-05-09/pytest-vector-integration.txt
A	quality-reports/hygiene-probe-2026-05-09/radon-cc-router.txt
A	quality-reports/hygiene-probe-2026-05-09/radon-cc.txt
A	quality-reports/hygiene-probe-2026-05-09/semgrep.json
A	quality-reports/hygiene-probe-2026-05-09/semgrep.stdout
A	quality-reports/hygiene-probe-2026-05-09/summary.json
A	quality-reports/hygiene-probe-2026-05-09/vulture.txt
A	quality-reports/mypy.txt
A	quality-reports/pyright.json
A	quality-reports/pyright.stderr
A	quality-reports/pyright.txt
A	quality-reports/radon-cc.txt
A	quality-reports/radon-mi.txt
A	quality-reports/semantic-gate-metrics.json
A	quality-reports/vulture.txt
A	reports/agentops/work_packets/recursive-discovery-shadow.json
D	specs/PARALLEL_BUILD_AGENT_PROMPTS_2026-03-19.md
M	specs/README.md
D	specs/SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md
D	specs/VERIFICATION_COMPLETE.md
```
#### `stash@{41}` — On cleanup/memory-kernel-shadow-context-main-2026-05-13: memory-kernel-prep-full-dirty-snapshot-2026-05-14
```text
M	ACTIVE_SURFACE_MANIFEST.yaml
M	Makefile
A	dharma_swarm/knowledge_ops/__init__.py
A	dharma_swarm/knowledge_ops/cli.py
A	dharma_swarm/knowledge_ops/memory_conflict_review.py
A	dharma_swarm/knowledge_ops/memory_decision_ledger.py
A	dharma_swarm/knowledge_ops/memory_intake.py
A	dharma_swarm/knowledge_ops/memory_promotion_queue.py
M	dharma_swarm/memory_kernel/surfaces.py
M	dharma_swarm/memory_kernel/writers.py
M	dharma_swarm/operator_core/control_surface.py
A	dharma_swarm/operator_core/control_surface_memory.py
M	dharma_swarm/operator_core/control_surface_models.py
M	docs/MEGAFILE_INDEX.md
M	docs/architecture/memory_kernel_current_intent.md
M	docs/architecture/memory_kernel_m4a_shadow_report_sweep.md
A	docs/architecture/memory_kernel_m4b_knowledgeops_writer_readiness.md
M	docs/plans/2026-04-02-specs-spec-forge-seam-plan.md
M	docs/plans/2026-04-03-autonomous-cleanup-overnight-control.md
M	docs/research/README.md
A	docs/research/RECURSIVE_SUPERINTELLIGENCE_STRATEGIC_NODE_2026-05-14.md
M	docs/telos-engine/INDEX.md
A	experiments/mask_rv_whitebox/01_load_mask.py
A	experiments/mask_rv_whitebox/02_run_inference.py
A	experiments/mask_rv_whitebox/03_compute_rv.py
A	experiments/mask_rv_whitebox/04_classifiers.py
A	experiments/mask_rv_whitebox/README.md
A	experiments/mask_rv_whitebox/cache/activations_smoke_pythia/67736b017e3b417e660ea999.npz
A	experiments/mask_rv_whitebox/cache/activations_smoke_pythia/6774a063d9fa9ffd1ad8d18b.npz
A	experiments/mask_rv_whitebox/cache/activations_smoke_pythia/67817e8d342c614cca814d6b.npz
A	experiments/mask_rv_whitebox/cache/mask_raw.parquet
A	experiments/mask_rv_whitebox/cache/mask_split.json
A	experiments/mask_rv_whitebox/cache/mask_stratified.parquet
A	experiments/mask_rv_whitebox/cache/rv_scalars_smoke_pythia.parquet
A	experiments/mask_rv_whitebox/config.yaml
A	experiments/mask_rv_whitebox/inference_smoke.log
A	experiments/mask_rv_whitebox/inference_smoke_pythia.log
A	experiments/mask_rv_whitebox/inference_smoke_qwen.log
A	experiments/mask_rv_whitebox/results/inference_results_smoke_pythia.jsonl
A	quality-reports/bandit.txt
A	quality-reports/fallow.txt
A	quality-reports/hygiene-probe-2026-05-09/bandit.json
A	quality-reports/hygiene-probe-2026-05-09/bandit.stdout
A	quality-reports/hygiene-probe-2026-05-09/bandit.txt
A	quality-reports/hygiene-probe-2026-05-09/compileall.txt
A	quality-reports/hygiene-probe-2026-05-09/dashboard-lint.txt
A	quality-reports/hygiene-probe-2026-05-09/fallow-dashboard.json
A	quality-reports/hygiene-probe-2026-05-09/fallow-dashboard.stderr
A	quality-reports/hygiene-probe-2026-05-09/mypy.txt
A	quality-reports/hygiene-probe-2026-05-09/normalized-findings.jsonl
A	quality-reports/hygiene-probe-2026-05-09/pyright.json
A	quality-reports/hygiene-probe-2026-05-09/pyright.stderr
A	quality-reports/hygiene-probe-2026-05-09/pytest-coverage.txt
A	quality-reports/hygiene-probe-2026-05-09/pytest-file-lock-integration.txt
A	quality-reports/hygiene-probe-2026-05-09/pytest-targeted.txt
A	quality-reports/hygiene-probe-2026-05-09/pytest-vector-integration.txt
A	quality-reports/hygiene-probe-2026-05-09/radon-cc-router.txt
A	quality-reports/hygiene-probe-2026-05-09/radon-cc.txt
A	quality-reports/hygiene-probe-2026-05-09/semgrep.json
A	quality-reports/hygiene-probe-2026-05-09/semgrep.stdout
A	quality-reports/hygiene-probe-2026-05-09/summary.json
A	quality-reports/hygiene-probe-2026-05-09/vulture.txt
A	quality-reports/mypy.txt
A	quality-reports/pyright.json
A	quality-reports/pyright.stderr
A	quality-reports/pyright.txt
A	quality-reports/radon-cc.txt
A	quality-reports/radon-mi.txt
A	quality-reports/semantic-gate-metrics.json
A	quality-reports/vulture.txt
A	reports/agentops/work_packets/recursive-discovery-shadow.json
M	scripts/memory_writer_sentinel.py
A	scripts/operator_prod_smoke.py
D	specs/PARALLEL_BUILD_AGENT_PROMPTS_2026-03-19.md
M	specs/README.md
D	specs/SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md
D	specs/VERIFICATION_COMPLETE.md
A	tests/test_knowledge_ops_memory_intake.py
M	tests/test_memory_writer_sentinel.py
```
#### `stash@{42}` — On chore/phase2-governance-isolation: quarantine interop dashboard api status context after semgrep wrapper
```text
M	ACTIVE_SURFACE_MANIFEST.yaml
A	AGENTS.md
M	CLAUDE.md
M	SWARM_HOT_ITEMS.md
M	api/main.py
M	api/routers/health.py
A	api/routers/interop.py
A	dashboard/src/app/dashboard/interop/page.tsx
A	dashboard/src/hooks/useInterop.ts
M	dashboard/src/lib/api.test.ts
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.test.ts
M	dashboard/src/lib/dashboardNav.ts
M	dashboard/src/lib/types.ts
A	dharma_swarm/operator_core/interop.py
A	dharma_swarm/operator_core/interop_worker.py
M	dharma_swarm/roaming_mailbox.py
A	scripts/run_interop_claude_task.sh
A	scripts/run_interop_codex_task.sh
A	scripts/start_interop_workers_tmux.sh
A	scripts/status_interop_workers_tmux.sh
A	scripts/stop_interop_workers_tmux.sh
A	tests/test_interop_router.py
```
#### `stash@{43}` — On chore/phase2-governance-isolation: rogue_interop_feature
```text
M	ACTIVE_SURFACE_MANIFEST.yaml
M	SWARM_HOT_ITEMS.md
M	api/main.py
M	api/routers/health.py
A	api/routers/interop.py
A	dashboard/src/app/dashboard/interop/page.tsx
A	dashboard/src/hooks/useInterop.ts
M	dashboard/src/lib/api.test.ts
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.test.ts
M	dashboard/src/lib/dashboardNav.ts
M	dashboard/src/lib/types.ts
A	dharma_swarm/operator_core/interop.py
A	dharma_swarm/operator_core/interop_worker.py
M	dharma_swarm/roaming_mailbox.py
A	scripts/run_interop_claude_task.sh
A	scripts/run_interop_codex_task.sh
A	scripts/start_interop_workers_tmux.sh
A	scripts/status_interop_workers_tmux.sh
A	scripts/stop_interop_workers_tmux.sh
A	tests/test_interop_router.py
```
#### `stash@{44}` — On chore/phase2-governance-isolation: quarantine interop dashboard api wip before semgrep wrapper
```text
M	ACTIVE_SURFACE_MANIFEST.yaml
A	AGENTS.md
M	SWARM_HOT_ITEMS.md
M	api/main.py
M	api/routers/health.py
A	api/routers/interop.py
A	dashboard/src/app/dashboard/interop/page.tsx
A	dashboard/src/hooks/useInterop.ts
M	dashboard/src/lib/api.test.ts
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.test.ts
M	dashboard/src/lib/dashboardNav.ts
M	dashboard/src/lib/types.ts
A	dharma_swarm/operator_core/interop.py
A	dharma_swarm/operator_core/interop_worker.py
M	dharma_swarm/roaming_mailbox.py
A	scripts/run_interop_claude_task.sh
A	scripts/run_interop_codex_task.sh
A	scripts/start_interop_workers_tmux.sh
A	scripts/status_interop_workers_tmux.sh
A	scripts/stop_interop_workers_tmux.sh
A	tests/test_interop_router.py
```
#### `stash@{45}` — On feat/inquiry-chain-phase1: cleanup-hold-2026-05-03T07:27:00Z generated-agent-context-after-memory-probe
```text
A	AGENTS.md
```
#### `stash@{46}` — On refactor/runtime-lifecycle-producers: cleanup-hold-2026-05-03T07:15:06Z holistic-sweep dharma_swarm_runtime_lifecycle_producers branch=refactor/runtime-lifecycle-producers entries=1
```text
A	reports/ops/PR46_REVIEW.md
```
#### `stash@{47}` — On (no branch): cleanup-hold-2026-05-03T07:15:06Z holistic-sweep dharma_swarm_repo_state_now branch=detached entries=1
```text
A	reports/ops/REPO_STATE_NOW.md
```
#### `stash@{48}` — On site/dharma-swarm-research: cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_public_site_publish branch=site/dharma-swarm-research entries=1
```text
A	docs/site/index.html
A	docs/site/styles.css
```
#### `stash@{49}` — On (no branch): cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_model_routing_cartography branch=detached entries=2
```text
A	reports/cartography/03_MODEL_ROUTING.md
A	reports/ops/MODEL_ROUTING_MIGRATION_PLAN.md
```
#### `stash@{50}` — On cartography/memory-substrates: cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_memory_substrates_origin_main branch=cartography/memory-substrates entries=1
```text
A	reports/cartography/02_MEMORY_SUBSTRATES.md
```
#### `stash@{51}` — On (no branch): cleanup-hold-2026-05-03T07:15:05Z holistic-sweep dharma_swarm_main_stabilization_audit branch=detached entries=1
```text
A	reports/ops/MAIN_STABILIZATION_CHECKPOINT.md
```
#### `stash@{52}` — On promote/lf5-runtime-spine: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_lf5_promotion branch=promote/lf5-runtime-spine entries=16
```text
A	reports/audit/end_to_end/100_DOCS_DRIFT_REGISTER.md
A	reports/audit/end_to_end/10_RUNTIME_SPINE_MAP.md
A	reports/audit/end_to_end/20_AGENT_IDENTITY_COHERENCE.md
A	reports/audit/end_to_end/30_MODEL_ROUTING_COHERENCE.md
A	reports/audit/end_to_end/40_MEMORY_SUBSTRATE_MAP.md
A	reports/audit/end_to_end/50_GUARDIAN_OBSERVABILITY_MAP.md
A	reports/audit/end_to_end/60_API_DASHBOARD_COHERENCE.md
A	reports/audit/end_to_end/70_SHAKTI_DARWIN_LOOP_MAP.md
A	reports/audit/end_to_end/80_REPO_GOVERNANCE_MAP.md
A	reports/audit/end_to_end/90_TEST_COVERAGE_BY_LOOP.md
A	reports/audit/runtime_truth/03_MATRIX_REVIEW.md
A	reports/audit/runtime_truth/12_GOVERNANCE_BRANCH_READINESS.md
A	reports/cartography/00_GLOBAL_REPO_MAP.md
A	reports/cartography/05_GOVERNANCE_CI.md
A	reports/cartography/06_DOCS_DRIFT.md
A	reports/cartography/COUNCIL_SYNTHESIS.md
A	reports/cartography/council/01_phenomenological.md
A	reports/cartography/council/02_sre.md
A	reports/cartography/council/03_adversarial.md
A	reports/cartography/council/04_contemplative.md
A	reports/cartography/council/05_beginner.md
A	reports/cartography/council/06_critic.md
A	reports/cartography/council/_seed_prompt.md
A	reports/ops/MERGE_PLAN_PR28.md
A	reports/ops/POST_PR28_BACKLOG_UPDATE.md
A	reports/ops/PR28_STATUS.md
```
#### `stash@{53}` — On fix/guardian-warning-cases: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_guardian_warning_cases branch=fix/guardian-warning-cases entries=1
```text
A	reports/ops/PR45_REVIEW.md
```
#### `stash@{54}` — On governance/tier-1-clean: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_governance_tier_1_clean branch=governance/tier-1-clean entries=1
```text
A	reports/ops/POST_GOVERNANCE_MERGE.md
```
#### `stash@{55}` — On docs/main-stabilization-checkpoint: cleanup-hold-2026-05-03T07:15:04Z holistic-sweep dharma_swarm_ci_unblock_pr28 branch=docs/main-stabilization-checkpoint entries=1
```text
A	reports/ops/MAIN_STABILIZATION_CHECKPOINT.md
```
#### `stash@{56}` — On dashboard-lf5-operator-lane: cleanup-hold-2026-05-03T07:15:03Z holistic-sweep dharma_swarm_lf5_operator branch=dashboard-lf5-operator-lane entries=6
```text
M	api/chat_tools.py
M	api/routers/chat.py
A	dashboard/src/app/dashboard/claude-code/page.tsx
A	dashboard/src/app/dashboard/codex/page.tsx
M	dashboard/src/lib/controlPlaneSurfaces.ts
M	dashboard/src/lib/dashboardNav.ts
```
#### `stash@{57}` — On audit/runtime-truth-2026-04-26: cleanup-hold-2026-05-03T07:15:03Z holistic-sweep dharma_swarm_lf5 branch=audit/runtime-truth-2026-04-26 entries=54
```text
A	.github/pull_request_template.md
A	.github/workflows/codeql.yml
A	.github/workflows/governance.yml
A	.gitleaks.toml
A	.playwright-mcp/console-2026-04-29T16-39-54-968Z.log
A	.playwright-mcp/page-2026-04-29T16-39-55-031Z.yml
A	.playwright-mcp/page-2026-04-29T16-56-03-401Z.yml
A	.semgrep/dharma-governance.yml
A	.serena/.gitignore
A	.serena/project.yml
A	AGENTS.md
M	GUARDIAN_REPORT.md
A	REPO_RULES.md
A	campaigns/linkedin_outreach_messages_2026-04-21.md
A	campaigns/welfare_ton_mrv_mvp_spec_2026-04-21.md
A	campaigns/welfare_ton_mrv_outreach_tracker_v2.md
A	dashboard/src/lib/auth.test.ts
A	dashboard/src/lib/auth.ts
A	dashboard/src/lib/taskBoard.ts
A	dharma-site-desktop-verify.png
A	dharma-site-desktop.png
A	dharma-site-mobile-verify.png
A	dharma-site-mobile.png
A	dharma_swarm/_campaign_manifest.py
A	dharma_swarm/build_authority.py
A	dharma_swarm/build_registry.py
A	dharma_swarm/frontier_council.py
A	dharma_swarm/ontology_context.py
A	dharma_swarm/opportunity_dispatcher.py
A	dharma_swarm/opportunity_refill.py
A	dharma_swarm/task_board_mirror.py
A	dharma_swarm/task_contract.py
A	docs/GOVERNANCE_GATES.md
A	docs/LF5_PROMOTION_READINESS.md
A	docs/MAIN_INTEGRATION_BUILD_SPEC.md
A	governance/policy.json
A	renovate.json
A	reports/audit/runtime_truth/00B_SNAPSHOT_RESULT.md
A	reports/audit/runtime_truth/00C_DAEMON_SHUTDOWN_ATTEMPT.md
A	reports/audit/runtime_truth/00_AUDIT_PROMPT.md
A	reports/audit/runtime_truth/00_LF5_LOCATION_TRUTH.md
A	reports/audit/runtime_truth/02_STRUCTURED_TABLE_PRODUCER_GAP.md
A	reports/audit/runtime_truth/03_PRODUCER_WIRING_RESULT.md
A	reports/audit/runtime_truth/IDLE_REVIEW_PROMOTION_RISK.md
A	reports/audit/runtime_truth/LF5_PROMOTION_MATRIX.md
A	reports/overnight_execution_bind_2026-04-22.md
A	scripts/build_registry_ctl.py
A	scripts/governance_scan.py
A	scripts/pre_push_governance.sh
A	scripts/repo_rules.py
A	specs/CURRENT_DAEMON_EXECUTION_COMPRESSION_SPEC_2026-04-15.md
A	specs/SWARM_HOT_PATH_LIVENESS_MASTER_SPEC_2026-04-16.md
A	tests/test_api_health_router.py
A	tests/test_archaeology_ingestion.py
A	tests/test_build_registry.py
A	tests/test_frontier_council.py
A	tests/test_gnani_lodestone.py
A	tests/test_governance_scan.py
A	tests/test_opportunity_dispatcher_full_chain.py
A	tests/test_opportunity_refill.py
A	tests/test_repo_rules.py
A	tests/test_swarm_health_api.py
A	tests/test_swarm_liveness_watchdog.py
A	tests/test_task_board_mirror.py
A	tests/test_web_search.py
A	uv.lock
```
#### `stash@{58}` — On (no branch): cleanup-hold-2026-05-03T07:15:02Z holistic-sweep dharma_swarm_dashboard_skill_worktree branch=detached entries=1
```text
A	skills/dharma-dashboard-master/01_HOLES_AND_GAPS.md
A	skills/dharma-dashboard-master/02_TOOLS_AND_ARSENAL.md
A	skills/dharma-dashboard-master/03_HIGH_VISION.md
```
#### `stash@{59}` — On worktree-research-integration: cleanup-hold-2026-05-03T07:15:02Z holistic-sweep research-integration branch=worktree-research-integration entries=2
```text
A	tests/test_contracts.py
A	tests/test_private_access.py
```
#### `stash@{60}` — On dgc-splash-art: cleanup-hold-2026-05-03T07:15:02Z holistic-sweep dgc-splash-art branch=dgc-splash-art entries=34
```text
M	.gitignore
A	CODEX_AUDIT_PROMPT.md
A	CODEX_CROSSCHECK.md
M	terminal/.dharma-terminal-state.json
A	terminal/bun_all.ansi
A	terminal/bun_braille.ansi
A	terminal/bun_halfblock.ansi
A	terminal/capture-terminal.ts
A	terminal/fuji_all.ansi
A	terminal/fuji_braille.ansi
A	terminal/fuji_half.ansi
A	terminal/fuji_timg.ansi
A	terminal/full-test.ts
A	terminal/gallery.html
A	terminal/gallery2.html
A	terminal/hokusai_all.ansi
A	terminal/hokusai_big.ansi
A	terminal/hokusai_braille.ansi
A	terminal/hokusai_half.ansi
A	terminal/iteration-log.md
A	terminal/preview-ansi.ts
A	terminal/preview-splash.tsx
A	terminal/preview-text.ts
A	terminal/preview-timg.html
A	terminal/preview.html
A	terminal/render-scene.ts
A	terminal/screenshot.ts
A	terminal/screenshots/full-test/01-boot.png
A	terminal/screenshots/full-test/02-tab-Mission.png
A	terminal/screenshots/full-test/03-tab-Repo.png
A	terminal/screenshots/full-test/04-tab-Commands.png
A	terminal/screenshots/full-test/05-tab-Models.png
A	terminal/screenshots/full-test/06-tab-Ontology.png
A	terminal/screenshots/full-test/07-tab-Runtime.png
A	terminal/screenshots/full-test/08-tab-Sessions.png
A	terminal/screenshots/full-test/09-tab-Approvals.png
A	terminal/screenshots/full-test/10-tab-Control.png
A	terminal/screenshots/full-test/11-tab-Agents.png
A	terminal/screenshots/full-test/12-tab-Evolution.png
A	terminal/screenshots/full-test/13-tab-Thinking.png
A	terminal/screenshots/full-test/14-tab-Tools.png
A	terminal/screenshots/full-test/15-tab-Timeline.png
A	terminal/screenshots/full-test/16-back-to-chat.png
A	terminal/screenshots/full-test/17-sidebar-toc.png
A	terminal/screenshots/full-test/18-sidebar-context.png
A	terminal/screenshots/full-test/19-sidebar-help.png
A	terminal/screenshots/full-test/20-sidebar-hidden.png
A	terminal/screenshots/full-test/21-sidebar-shown.png
A	terminal/screenshots/full-test/22-model-picker-open.png
A	terminal/screenshots/full-test/23-model-picker-scrolled.png
A	terminal/screenshots/full-test/24-model-picker-closed.png
A	terminal/screenshots/full-test/25-prompt-typed.png
A	terminal/screenshots/full-test/26-prompt-submitted.png
A	terminal/screenshots/full-test/27-response-received.png
A	terminal/screenshots/full-test/28-trace-on.png
A	terminal/screenshots/full-test/29-trace-off.png
A	terminal/screenshots/full-test/30-history-up.png
A	terminal/screenshots/full-test/31-history-down.png
A	terminal/screenshots/full-test/32-after-clear.png
A	terminal/screenshots/full-test/33-long-response.png
A	terminal/screenshots/full-test/34-scrolled-up.png
A	terminal/screenshots/full-test/35-final.png
A	terminal/screenshots/iter-00.png
A	terminal/screenshots/iter-01.png
A	terminal/screenshots/iter-02.png
A	terminal/screenshots/iter-03.png
A	terminal/screenshots/iter-04.png
A	terminal/screenshots/iter-05.png
A	terminal/screenshots/iter-06.png
A	terminal/screenshots/iter-07.png
A	terminal/screenshots/iter-08.png
A	terminal/screenshots/iter-09.png
A	terminal/screenshots/iter-10.png
A	terminal/screenshots/iter-11.png
A	terminal/screenshots/iter-12.png
A	terminal/screenshots/iter-13.png
A	terminal/screenshots/iter-14.png
A	terminal/screenshots/iter-15.png
A	terminal/screenshots/iter-16.png
A	terminal/screenshots/iter-17.png
A	terminal/screenshots/iter-18.png
A	terminal/screenshots/iter-22.png
A	terminal/screenshots/iter-28.png
A	terminal/screenshots/iter-29.png
A	terminal/screenshots/iter-30.png
A	terminal/screenshots/iter-31.png
A	terminal/screenshots/iter-32.png
A	terminal/screenshots/iter-33.png
A	terminal/screenshots/redfuji-highres.png
A	terminal/screenshots/scene-highres.png
A	terminal/screenshots/tui/01-boot.png
A	terminal/screenshots/tui/02-after-tab.png
A	terminal/screenshots/tui/03-model-picker.png
A	terminal/screenshots/tui/04-model-down.png
A	terminal/screenshots/tui/05-model-down2.png
A	terminal/screenshots/tui/06-escape.png
A	terminal/screenshots/tui/07-tab2.png
A	terminal/screenshots/tui/08-tab3.png
A	terminal/screenshots/tui/09-tab5-models.png
A	terminal/screenshots/tui/10-tab1-chat.png
A	terminal/screenshots/tui/11-typed-hello.png
A	terminal/screenshots/tui/12-final.png
A	terminal/screenshots/tui/models-01-ctrl-m.png
A	terminal/screenshots/tui/models-02-scrolled.png
A	terminal/screenshots/tui/models-03-scrolled-more.png
A	terminal/screenshots/tui/models-04-selected.png
A	terminal/screenshots/tui/models-05-after-select.png
A	terminal/screenshots/tui/models-06-chat.png
A	terminal/screenshots/tui/models-07-typed.png
A	terminal/screenshots/tui/models-08-submitted.png
A	terminal/screenshots/tui/models-09-response.png
A	terminal/screenshots/tui/v2-01-boot.png
A	terminal/screenshots/tui/v2-02-models-tab.png
A	terminal/screenshots/tui/v2-03-right.png
A	terminal/screenshots/tui/v2-04-more-right.png
A	terminal/screenshots/tui/v2-05-pane-switcher.png
A	terminal/screenshots/tui/v2-06-pane-at-models.png
A	terminal/screenshots/tui/v2-07-selected-pane.png
A	terminal/screenshots/tui/v2-08-ctrl-m.png
A	terminal/screenshots/tui/v2-09-model-scroll.png
A	terminal/screenshots/tui/v2-10-model-selected.png
A	terminal/screenshots/tui/v2-11-final.png
A	terminal/screenshots/tui/v3-01-models-tab.png
A	terminal/screenshots/tui/v3-02-models-scrolled.png
A	terminal/screenshots/tui/v3-03-models-more.png
A	terminal/screenshots/tui/v3-04-vim-nav.png
A	terminal/screenshots/tui/v3-05-enter-select.png
A	terminal/screenshots/tui/v3-06-after-select.png
A	terminal/screenshots/tui/v3-07-back-chat.png
A	terminal/screenshots/tui/v3-08-typed.png
A	terminal/screenshots/tui/v3-09-submitted.png
A	terminal/screenshots/tui/v3-10-response.png
A	terminal/screenshots/tui/v3-11-final.png
A	terminal/screenshots/verify-final.png
A	terminal/screenshots/verify-fixes/01-boot-clean.png
A	terminal/screenshots/verify-fixes/02-picker-overlay-on-chat.png
A	terminal/screenshots/verify-fixes/03-picker-closed-still-chat.png
A	terminal/screenshots/verify-fixes/04-prompt-submitted-on-chat.png
A	terminal/screenshots/verify-fixes/05-response-on-chat.png
A	terminal/screenshots/verify-fixes/06-final-single-render.png
A	terminal/tui-models-test.ts
A	terminal/tui-models-v2.ts
A	terminal/tui-models-v3.ts
A	terminal/tui-test.ts
A	terminal/verify-fixes.ts
A	terminal/verify-screenshot.ts
```
#### `stash@{61}` — On feat/chetana-grand-memory: cleanup-hold-2026-05-03T07:15:01Z holistic-sweep dharma_chetana branch=feat/chetana-grand-memory entries=9
```text
A	CODEX_REVIEW_PROMPT.md
M	dharma_swarm/chetana/README.md
M	dharma_swarm/chetana/cli.py
M	dharma_swarm/chetana/governance.py
M	dharma_swarm/chetana/ingest.py
M	dharma_swarm/chetana/provenance.py
M	dharma_swarm/chetana/tests/test_governance.py
M	dharma_swarm/chetana/tests/test_ingest_promote.py
A	dharma_swarm/tui_launcher.py
```
#### `stash@{62}` — On feat/inquiry-chain-phase1: cleanup-hold-2026-05-03T07:15:01Z holistic-sweep dharma_swarm branch=feat/inquiry-chain-phase1 entries=50
```text
M	.pre-commit-config.yaml
M	.semgrep/.semgrepignore
M	.semgrep/dharma-anti-slop.yml
M	ACTIVE_SURFACE_MANIFEST.yaml
A	AGENTS.md
M	CLAUDE.md
M	SWARM_HOT_ITEMS.md
M	api/main.py
A	api/routers/agent_day.py
M	api/routers/health.py
A	api/routers/interop.py
M	dashboard/src/app/dashboard/command-post/page.tsx
A	dashboard/src/app/dashboard/interop/page.tsx
A	dashboard/src/components/dashboard/AgentDayPanel.tsx
A	dashboard/src/hooks/useAgentDay.ts
A	dashboard/src/hooks/useInterop.ts
M	dashboard/src/lib/api.test.ts
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.ts
M	dashboard/src/lib/types.ts
M	dharma_swarm/dgc_cli.py
M	dharma_swarm/identity.py
M	dharma_swarm/operator_core/__init__.py
A	dharma_swarm/operator_core/agent_day.py
A	dharma_swarm/operator_core/interop.py
A	dharma_swarm/operator_core/interop_worker.py
A	dharma_swarm/rm_telemetry.py
M	dharma_swarm/roaming_mailbox.py
A	dharma_swarm/shadow_judge.py
M	dharma_swarm/sleep_cycle.py
M	docs/governance/ANTI_SLOP_RULES.md
M	docs/governance/CANONICAL_DOC_STACK.md
M	docs/governance/REPO_GOVERNANCE_AUDIT.md
A	docs/governance/STATE_DIR_OWNERS.md
A	docs/governance/track_a/README.md
A	docs/governance/track_a/adjudication_queue.yaml
A	docs/governance/track_a/calibration_abstention_contract.yaml
A	docs/governance/track_a/dataset_model_registry.yaml
A	docs/governance/track_a/evals/adversarial_gate_combo_v0.jsonl
A	docs/governance/track_a/evals/prompt_injection_security_v0.jsonl
A	docs/governance/track_a/frozen_eval_manifest.yaml
A	docs/governance/track_a/redaction_policy.md
A	docs/governance/track_a/rollback_manifest.yaml
A	docs/governance/track_a/security_threat_model.md
A	docs/governance/track_a/shadow_canary_report.md
A	docs/governance/track_a/witness_quarantine.yaml
A	docs/plans/2026-05-03-agent-day-interop-master-build.md
A	scripts/governance/check_track_a_membrane.py
A	scripts/governance/inventory_chetana_witness.py
A	scripts/governance/run_semgrep_with_ca.sh
A	scripts/run_interop_claude_task.sh
A	scripts/run_interop_codex_task.sh
A	scripts/start_interop_workers_tmux.sh
A	scripts/status_interop_workers_tmux.sh
A	scripts/stop_interop_workers_tmux.sh
A	tests/test_agent_day_control_plane.py
A	tests/test_interop_router.py
A	tests/test_rm_telemetry.py
A	tests/test_shadow_judge.py
A	tests/test_track_a_membrane.py
A	tests/test_witness_inventory.py
```
#### `stash@{63}` — On feat/inquiry-chain-phase1: WIP feat/inquiry-chain-phase1 — 30 modified + 35 untracked (deep_agent_*, agent_interop, intrinsic_rewards, dharma-judge tests, governance docs, dashboard interop) — parked 2026-05-03 by clean-up sweep
```text
M	.pre-commit-config.yaml
M	.semgrep/.semgrepignore
M	ACTIVE_SURFACE_MANIFEST.yaml
A	AGENTS.md
A	AGENT_INSTRUCTIONS.md
M	CLAUDE.md
A	GUARDIAN_REPORT.md
M	SWARM_HOT_ITEMS.md
M	api/main.py
A	api/routers/agent_day.py
M	api/routers/health.py
A	api/routers/interop.py
M	dashboard/src/app/dashboard/command-post/page.tsx
A	dashboard/src/app/dashboard/interop/page.tsx
A	dashboard/src/components/dashboard/AgentDayPanel.tsx
A	dashboard/src/hooks/useAgentDay.ts
A	dashboard/src/hooks/useInterop.ts
M	dashboard/src/lib/api.test.ts
M	dashboard/src/lib/api.ts
M	dashboard/src/lib/dashboardNav.test.ts
M	dashboard/src/lib/dashboardNav.ts
M	dashboard/src/lib/types.ts
A	dharma_swarm/agent_interop.py
A	dharma_swarm/agent_interop_cli.py
M	dharma_swarm/agent_runner.py
A	dharma_swarm/deep_agent_backend.py
A	dharma_swarm/deep_agent_harness.py
M	dharma_swarm/dgc_cli.py
M	dharma_swarm/economic_engine.py
M	dharma_swarm/identity.py
A	dharma_swarm/intrinsic_rewards.py
M	dharma_swarm/mcp_server.py
M	dharma_swarm/operator_core/__init__.py
A	dharma_swarm/operator_core/agent_day.py
A	dharma_swarm/opportunity_cli.py
M	dharma_swarm/opportunity_dispatcher.py
A	dharma_swarm/opportunity_observer.py
M	dharma_swarm/telic_seam.py
A	dharma_swarm/telic_seam_inquiry.py
A	dharma_swarm/training/__init__.py
A	dharma_swarm/training/calibration.py
A	dharma_swarm/training/dharma_judge_member_a.py
A	dharma_swarm/training/dharma_judge_member_c.py
A	dharma_swarm/training/ensemble_brier.py
M	docs/governance/ANTI_SLOP_RULES.md
M	docs/governance/CANONICAL_DOC_STACK.md
M	docs/governance/README.md
M	docs/governance/REPO_GOVERNANCE_AUDIT.md
A	docs/governance/track_a/README.md
A	docs/governance/track_a/adjudication_queue.yaml
A	docs/governance/track_a/calibration_abstention_contract.yaml
A	docs/governance/track_a/dataset_model_registry.yaml
A	docs/governance/track_a/frozen_eval_manifest.yaml
A	docs/governance/track_a/redaction_policy.md
A	docs/governance/track_a/rollback_manifest.yaml
A	docs/governance/track_a/security_threat_model.md
A	docs/governance/track_a/shadow_canary_report.md
A	docs/governance/track_a/witness_quarantine.yaml
A	roaming_mailbox/tasks/mbx_4246bb47431a4e23.json
M	scripts/com.dharma.dashboard-api.plist
A	scripts/governance/check_track_a_membrane.py
A	scripts/governance/run_semgrep_with_ca.sh
A	scripts/start_iterm_six_agents.sh
A	scripts/status_iterm_six_agents.sh
A	scripts/stop_iterm_six_agents.sh
A	scripts/uplift_guards/.kernel_sha256
A	scripts/uplift_guards/__init__.py
A	scripts/uplift_guards/autonomous_guard.py
A	scripts/uplift_guards/hotpath_guard.py
A	scripts/uplift_guards/kernel_guard.py
A	scripts/uplift_guards/mismatch_registry.py
A	scripts/uplift_guards/run_pre_commit.py
A	scripts/uplift_guards/secrets_guard.py
A	tests/test_agent_day_control_plane.py
A	tests/test_agent_interop.py
A	tests/test_calibration.py
A	tests/test_contracts.py
A	tests/test_dharma_judge_member_a.py
A	tests/test_dharma_judge_member_c.py
M	tests/test_dharma_kernel.py
A	tests/test_ensemble_brier.py
M	tests/test_identity.py
A	tests/test_interop_router.py
A	tests/test_intrinsic_rewards.py
M	tests/test_mcp_server.py
A	tests/test_private_access.py
M	tests/test_telos_gates.py
A	tests/test_track_a_membrane.py
```
#### `stash@{64}` — On feat/inquiry-chain-phase1: cleanup-hold-2026-05-02-active-untracked-surfaces
```text
A	AGENTS.md
A	GUARDIAN_REPORT.md
A	api/routers/cascade_router.py
A	api/routers/catalytic.py
A	api/routers/fleet.py
A	api/routers/gates.py
A	api/routers/strange_loop.py
A	api/routers/vsm.py
A	api/runtime_cache.py
A	artifacts/severa_fggm_prototype.py
A	artifacts/severa_fggm_prototype_spec.md
A	build_queues/operator_cockpit_truth.queue.json
A	build_queues/terminal_tui_rebuild.queue.json
A	campaigns/ACTION_REQUIRED_2_min_outreach_2026-04-23.md
A	campaigns/SEND_NOW_4_outreach_emails_2026-04-23.md
A	campaigns/aligned_revenue_engines_garden.md
A	campaigns/aligned_revenue_engines_garden_v2.md
A	campaigns/aligned_revenue_engines_garden_v3.md
A	campaigns/aligned_revenue_engines_garden_v4.md
A	campaigns/carbon_attribution_api_mvp_spec.md
A	campaigns/dgm_evolution_api_spec.md
A	campaigns/ecological_accounting_saaS_spec.md
A	campaigns/highest_free_attractor_garden.md
A	campaigns/operator_action_required_2026-04-23.md
A	campaigns/promise_abstract_welfare_ton_mrv_outreach_2026-04-24.md
A	campaigns/startup_packet_v1_2026-04-27.md
A	campaigns/startup_world_facing.md
A	campaigns/telos_sdk_extraction_plan.md
A	campaigns/welfare_ton_mrv_customer_discovery.md
A	campaigns/welfare_ton_mrv_mvp_spec.md
A	campaigns/welfare_ton_mrv_outreach_ready_2026-04-23.md
A	campaigns/welfare_ton_mrv_outreach_tracker.md
A	campaigns/welfare_ton_mrv_outreach_tracker_v2_2026-04-22.md
A	campaigns/welfare_ton_mrv_outreach_tracker_v3_2026-04-23.md
A	campaigns/welfare_ton_mrv_pilot_commitment_plan.md
A	campaigns/welfare_ton_mrv_target_list.md
A	campaigns/welfare_ton_mrv_target_list_v2_2026-04-22.md
A	codex_skills/terminal-guardian/SKILL.md
A	codex_skills/terminal-guardian/references/anti_spaghetti_checklist.md
A	dashboard/public/hud-scene.glb
A	dashboard/scripts/generate_hud_scene.py
A	dashboard/src/app/dashboard/artifacts/page.tsx
A	dashboard/src/app/dashboard/cascade/page.tsx
A	dashboard/src/app/dashboard/catalytic/page.tsx
A	dashboard/src/app/dashboard/doctor/page.tsx
A	dashboard/src/app/dashboard/fleet/page.tsx
A	dashboard/src/app/dashboard/gates-analysis/page.tsx
A	dashboard/src/app/dashboard/jobs/page.tsx
A	dashboard/src/app/dashboard/strange-loop/page.tsx
A	dashboard/src/app/dashboard/vsm/page.tsx
A	dashboard/src/components/dashboard/FleetStatusBadge.tsx
A	dashboard/src/components/dashboard/OperatorActions.tsx
A	dashboard/src/components/layout/DashboardCommandPalette.tsx
A	dashboard/src/hooks/useCatalytic.ts
A	dashboard/src/hooks/useFleet.ts
A	dashboard/src/hooks/useStrangeLoop.ts
A	dashboard/src/hooks/useSystemPulse.ts
A	dashboard/src/lib/backendReachability.test.ts
A	dashboard/src/lib/backendReachability.ts
A	dashboard/src/lib/clientSnapshotCache.ts
A	dashboard/src/lib/fleetFormat.ts
A	dharma_swarm/assurance/baseline.json
A	dharma_swarm/assurance/baseline.py
A	dharma_swarm/assurance/meta_learning.py
A	dharma_swarm/assurance/scanner_active_surface.py
A	dharma_swarm/assurance/scanner_boundaries.py
A	dharma_swarm/assurance/scanner_complexity.py
A	dharma_swarm/assurance/scanner_concepts.py
A	dharma_swarm/assurance/scanner_config_state.py
A	dharma_swarm/assurance/scanner_placeholders.py
A	dharma_swarm/cross_pollination.py
A	dharma_swarm/deep_agent_backend.py
A	dharma_swarm/deep_agent_harness.py
A	dharma_swarm/fleet_control.py
A	dharma_swarm/hermes_bridge.py
A	dharma_swarm/immutable_audit.py
A	dharma_swarm/knowledge_compiler/__init__.py
A	dharma_swarm/knowledge_compiler/compile.py
A	dharma_swarm/knowledge_compiler/config.py
A	dharma_swarm/knowledge_compiler/connections.py
A	dharma_swarm/knowledge_compiler/flush.py
A	dharma_swarm/knowledge_compiler/lint.py
A	dharma_swarm/knowledge_compiler/query.py
A	dharma_swarm/knowledge_compiler/schema.py
A	dharma_swarm/knowledge_compiler/seed.py
A	dharma_swarm/knowledge_compiler/session_extract.py
A	dharma_swarm/llm_gate_evaluator.py
A	dharma_swarm/ontology_context.py
A	dharma_swarm/persistent_memory.py
A	dharma_swarm/runtime_config.py
A	dharma_swarm/self_awareness_monitor.py
A	dharma_swarm/welfare_ton_mrv/__init__.py
A	docs/LANGGRAPH_INTEL_2026_04_10.md
A	docs/plans/2026-04-10-dharma-deep-agent-harness-build-spec.md
A	docs/public/anthropic_economic_futures_concept_note_2026-04-21.md
A	docs/public/anti_greenwashing_governance_charter_2026-04-21.md
A	docs/public/community_transition_pilot_archetypes_2026-04-21.md
A	docs/public/ecological_partner_classes_2026-04-21.md
A	docs/public/planetary_reciprocity_commons_brief_2026-04-21.md
A	docs/reports/CONTEXTPLUS_INTEGRATION_2026-04-08.md
A	docs/superpowers/specs/2026-04-10-ontology-agent-loop-design.md
A	references/research/agentic_autonomy_2026-03-27/bundle_summary.md
A	references/research/agentic_autonomy_2026-03-27/cashclaw_2026.md
A	references/research/agentic_autonomy_2026-03-27/deepagents_repo_2026.md
A	references/research/agentic_autonomy_2026-03-27/economic_closure_spine_notes.md
A	references/research/agentic_autonomy_2026-03-27/harness_self_evolution_notes.md
A	references/research/agentic_autonomy_2026-03-27/hyrve_ai_2026.md
A	references/research/agentic_autonomy_2026-03-27/identity_constitution_lineage_notes.md
A	references/research/agentic_autonomy_2026-03-27/langchain_deepagents_context_2026-01-28.md
A	references/research/agentic_autonomy_2026-03-27/langchain_deepagents_multi_agent_2026-01-21.md
A	references/research/agentic_autonomy_2026-03-27/mempo_2026-03-17.md
A	references/research/agentic_autonomy_2026-03-27/meta_rea_2026-03-17.md
A	references/research/agentic_autonomy_2026-03-27/microsoft_plugmem_2026-03-10.md
A	references/research/agentic_autonomy_2026-03-27/minimax_m27_2026-03-18.md
A	references/research/agentic_autonomy_2026-03-27/openroom_2026.md
A	references/research/agentic_autonomy_2026-03-27/ouroboros_2026.md
A	references/research/agentic_autonomy_2026-03-27/ouroboros_desktop_2026.md
A	references/research/agentic_autonomy_2026-03-27/paybot_mcp_2026.md
A	references/research/agentic_autonomy_2026-03-27/runtime_work_packages.md
A	references/research/agentic_autonomy_2026-03-27/source_index.md
A	references/research/agentic_autonomy_2026-03-27/sources.json
A	references/research/agentic_autonomy_2026-03-27/wait_state_job_engine_notes.md
A	reports/audit/runtime_truth/CLAUDE_SEMANTIC_TRUTH.md
A	reports/audit/runtime_truth/CODEX_RUNTIME_TRUTH.md
A	reports/ops/BACKLOG_ORGANIZATION.md
A	reports/ops/PR28_STATUS.md
A	roaming_mailbox/agents/kimi_2_6_claw/canonical_registration.json
A	roaming_mailbox/agents/kimi_2_6_claw/heartbeat.json
A	roaming_mailbox/agents/kimi_2_6_claw/reports/.gitkeep
A	scripts/first_real_mutation.py
A	scripts/global_vision.py
A	scripts/hermes_agni.py
A	scripts/hermes_agni_shell.sh
A	scripts/live_fire_metabolism.py
A	scripts/probe_gitnexus_mcp.mjs
A	scripts/reality_probe.py
A	scripts/reindex_global_vision.sh
A	scripts/seed_codex_opportunities.py
A	scripts/setup_hooks.sh
A	scripts/test_daemon_boot.py
A	scripts/upgrade_opportunity_board.py
A	scripts/uplift_guards/.kernel_sha256
A	scripts/uplift_guards/__init__.py
A	scripts/uplift_guards/autonomous_guard.py
A	scripts/uplift_guards/hotpath_guard.py
A	scripts/uplift_guards/kernel_guard.py
A	scripts/uplift_guards/mismatch_registry.py
A	scripts/uplift_guards/replay_history.py
A	scripts/uplift_guards/run_pre_commit.py
A	scripts/uplift_guards/secrets_guard.py
A	scripts/wiki_cli.py
A	telos_sdk/__init__.py
A	telos_sdk/gates/__init__.py
A	telos_sdk/gates/registry.py
A	telos_sdk/models/__init__.py
A	telos_sdk/models/gate.py
A	terminal-v2/README.md
A	terminal-v2/bun.lock
A	terminal-v2/package.json
A	terminal-v2/src/core/bridge.ts
A	terminal-v2/src/core/bridgeRequests.ts
A	terminal-v2/src/core/executionLog.ts
A	terminal-v2/src/core/freshness.ts
A	terminal-v2/src/core/mockContent.ts
A	terminal-v2/src/core/persistence.ts
A	terminal-v2/src/core/protocol.ts
A	terminal-v2/src/core/repoControlPreview.ts
A	terminal-v2/src/core/routePolicy.ts
A	terminal-v2/src/core/shellControls.ts
A	terminal-v2/src/core/state.ts
A	terminal-v2/src/core/transcriptFormatting.ts
A	terminal-v2/src/core/types.ts
A	terminal-v2/src/core/verification.ts
A	terminal-v2/src/hooks/useApi.ts
A	terminal-v2/src/hooks/useBridge.ts
A	terminal-v2/src/hooks/useFrameBatcher.ts
A	terminal-v2/src/index.tsx
A	terminal-v2/src/overlays/ModelPicker.tsx
A	terminal-v2/src/overlays/PaneSwitcher.tsx
A	terminal-v2/src/panes/ActivityPane.tsx
A	terminal-v2/src/panes/AgentsPane.tsx
A	terminal-v2/src/panes/ApprovalsPane.tsx
A	terminal-v2/src/panes/ChatPane.tsx
A	terminal-v2/src/panes/ControlPane.tsx
A	terminal-v2/src/panes/RepoPane.tsx
A	terminal-v2/src/panes/SessionsPane.tsx
A	terminal-v2/src/shell/Composer.tsx
A	terminal-v2/src/shell/MainPane.tsx
A	terminal-v2/src/shell/OperatorSummaryBand.tsx
A	terminal-v2/src/shell/ScenicStrip.tsx
A	terminal-v2/src/shell/ShellHeader.tsx
A	terminal-v2/src/shell/Sidebar.tsx
A	terminal-v2/src/shell/StatusFooter.tsx
A	terminal-v2/src/shell/TabBar.tsx
A	terminal-v2/src/theme.ts
A	terminal-v2/tests/core/app.test.ts
A	terminal-v2/tests/core/controlPane.test.ts
A	terminal-v2/tests/core/executionLog.test.ts
A	terminal-v2/tests/core/operatorSummaryBand.test.tsx
A	terminal-v2/tests/core/persistence.test.ts
A	terminal-v2/tests/core/protocol.test.ts
A	terminal-v2/tests/core/repoControlPreview.test.ts
A	terminal-v2/tests/core/repoPane.test.ts
A	terminal-v2/tests/core/routePolicy.test.ts
A	terminal-v2/tests/core/sidebar.test.ts
A	terminal-v2/tests/core/state.test.ts
A	terminal-v2/tests/core/transcriptFormatting.test.ts
A	terminal-v2/tests/e2e_prompt.mjs
A	terminal-v2/tests/verify_build.mjs
A	terminal-v2/tests/verify_fix.mjs
A	terminal-v2/tests/visual/boot.test.tsx
A	terminal-v2/tsconfig.json
A	terminal/tests/chat_e2e_test.mjs
A	terminal/tests/definitive_e2e.mjs
A	terminal/tests/final_e2e.mjs
A	terminal/tests/full_e2e_test.mjs
A	terminal/tests/keyboard_test.mjs
A	terminal/tests/leader_key_test.mjs
A	terminal/tests/prompt_e2e_test.mjs
A	terminal/tests/visual_feedback.mjs
A	tests/mismatches/__init__.py
A	tests/mismatches/test_MISMATCH_01.py
A	tests/mismatches/test_MISMATCH_02.py
A	tests/test_contracts.py
A	tests/test_dashboard_runtime_routes.py
A	tests/test_deep_agent_backend.py
A	tests/test_deep_agent_harness.py
A	tests/test_economic_metabolism.py
A	tests/test_fleet_control.py
A	tests/test_hermes_bridge.py
A	tests/test_immutable_audit.py
A	tests/test_knowledge_compiler.py
A	tests/test_llm_gate_evaluator.py
A	tests/test_ontology_context.py
A	tests/test_persistent_memory.py
A	tests/test_private_access.py
A	tests/test_self_awareness_monitor.py
A	tests/test_uplift_guards.py
A	tests/test_viz_router.py
A	uv.lock
```
#### `stash@{65}` — On governance/tier-1-install: pre-merge checkpoint: canonical governance/tier-1-install work (82 modified + untracked) before chetana merge 2026-05-01T14:43:51Z
```text
A	.agents/skills/agentdb-advanced/SKILL.md
A	.agents/skills/agentdb-learning/SKILL.md
A	.agents/skills/agentdb-memory-patterns/SKILL.md
A	.agents/skills/agentdb-optimization/SKILL.md
A	.agents/skills/agentdb-vector-search/SKILL.md
A	.agents/skills/browser/SKILL.md
A	.agents/skills/github-code-review/SKILL.md
A	.agents/skills/github-multi-repo/SKILL.md
A	.agents/skills/github-project-management/SKILL.md
A	.agents/skills/github-release-management/SKILL.md
A	.agents/skills/github-workflow-automation/SKILL.md
A	.agents/skills/gitnexus/debugging/SKILL.md
A	.agents/skills/gitnexus/exploring/SKILL.md
A	.agents/skills/gitnexus/gitnexus-cli/SKILL.md
A	.agents/skills/gitnexus/gitnexus-debugging/SKILL.md
A	.agents/skills/gitnexus/gitnexus-exploring/SKILL.md
A	.agents/skills/gitnexus/gitnexus-guide/SKILL.md
A	.agents/skills/gitnexus/gitnexus-impact-analysis/SKILL.md
A	.agents/skills/gitnexus/gitnexus-refactoring/SKILL.md
A	.agents/skills/gitnexus/impact-analysis/SKILL.md
A	.agents/skills/gitnexus/refactoring/SKILL.md
A	.agents/skills/hooks-automation/SKILL.md
A	.agents/skills/pair-programming/SKILL.md
A	.agents/skills/reasoningbank-agentdb/SKILL.md
A	.agents/skills/reasoningbank-intelligence/SKILL.md
A	.agents/skills/skill-builder/SKILL.md
A	.agents/skills/sparc-methodology/SKILL.md
A	.agents/skills/stream-chain/SKILL.md
A	.agents/skills/swarm-advanced/SKILL.md
A	.agents/skills/swarm-orchestration/SKILL.md
A	.agents/skills/v3-cli-modernization/SKILL.md
A	.agents/skills/v3-core-implementation/SKILL.md
A	.agents/skills/v3-ddd-architecture/SKILL.md
A	.agents/skills/v3-integration-deep/SKILL.md
A	.agents/skills/v3-mcp-optimization/SKILL.md
A	.agents/skills/v3-memory-unification/SKILL.md
A	.agents/skills/v3-performance-optimization/SKILL.md
A	.agents/skills/v3-security-overhaul/SKILL.md
A	.agents/skills/v3-swarm-coordination/SKILL.md
A	.agents/skills/verification-quality/SKILL.md
A	.codex/config.toml
M	.github/workflows/tests.yml
M	.gitignore
A	.gitnexusignore
A	.mcp_data/embeddings-cache-hash-hash-local-v1.json
A	.mcp_data/embeddings-cache-ollama-nomic-embed-text.json
A	.mcp_data/identifier-embeddings-cache.json
A	.mcp_data/memory-graph.json
A	.playwright-mcp/console-2026-04-03T14-47-55-878Z.log
A	.playwright-mcp/console-2026-04-03T14-58-50-550Z.log
A	.playwright-mcp/console-2026-04-03T15-11-41-801Z.log
A	.playwright-mcp/console-2026-04-03T23-56-36-556Z.log
A	.playwright-mcp/console-2026-04-04T00-01-13-165Z.log
A	.playwright-mcp/page-2026-04-03T14-47-56-067Z.yml
A	.playwright-mcp/page-2026-04-03T14-51-51-186Z.yml
A	.playwright-mcp/page-2026-04-03T14-52-14-541Z.yml
A	.playwright-mcp/page-2026-04-03T14-52-31-294Z.yml
A	.playwright-mcp/page-2026-04-03T14-52-43-480Z.yml
A	.playwright-mcp/page-2026-04-03T14-56-47-983Z.yml
A	.playwright-mcp/page-2026-04-03T14-58-50-665Z.yml
A	.playwright-mcp/page-2026-04-03T14-59-12-046Z.yml
A	.playwright-mcp/page-2026-04-03T15-11-41-918Z.yml
A	.playwright-mcp/page-2026-04-03T23-56-36-657Z.yml
A	.playwright-mcp/page-2026-04-03T23-57-01-972Z.yml
A	.playwright-mcp/page-2026-04-04T00-01-13-244Z.yml
A	.playwright-mcp/page-2026-04-04T00-44-46-027Z.yml
A	.playwright-mcp/page-2026-04-04T00-50-30-958Z.yml
A	AGENTS.md
M	CLAUDE.md
M	CYBERNETIC_LOOP_MAP.md
A	GUARDIAN_REPORT.md
M	README.md
A	SWARM_HOT_ITEMS.md
M	api/main.py
M	api/models.py
M	api/routers/agents.py
A	api/routers/cascade_router.py
A	api/routers/catalytic.py
M	api/routers/chat.py
M	api/routers/dashboard_new.py
M	api/routers/evolution.py
A	api/routers/fleet.py
A	api/routers/gates.py
M	api/routers/health.py
M	api/routers/routing.py
A	api/routers/strange_loop.py
A	api/routers/vsm.py
A	api/runtime_cache.py
A	artifacts/severa_fggm_prototype.py
A	artifacts/severa_fggm_prototype_spec.md
A	build_queues/operator_cockpit_truth.queue.json
A	build_queues/terminal_tui_rebuild.queue.json
A	campaigns/ACTION_REQUIRED_2_min_outreach_2026-04-23.md
A	campaigns/SEND_NOW_4_outreach_emails_2026-04-23.md
A	campaigns/aligned_revenue_engines_garden.md
A	campaigns/aligned_revenue_engines_garden_v2.md
A	campaigns/aligned_revenue_engines_garden_v3.md
A	campaigns/aligned_revenue_engines_garden_v4.md
A	campaigns/carbon_attribution_api_mvp_spec.md
A	campaigns/dgm_evolution_api_spec.md
A	campaigns/ecological_accounting_saaS_spec.md
A	campaigns/highest_free_attractor_garden.md
A	campaigns/operator_action_required_2026-04-23.md
A	campaigns/promise_abstract_welfare_ton_mrv_outreach_2026-04-24.md
A	campaigns/startup_packet_v1_2026-04-27.md
A	campaigns/startup_world_facing.md
A	campaigns/telos_sdk_extraction_plan.md
A	campaigns/welfare_ton_mrv_customer_discovery.md
A	campaigns/welfare_ton_mrv_mvp_spec.md
A	campaigns/welfare_ton_mrv_outreach_ready_2026-04-23.md
A	campaigns/welfare_ton_mrv_outreach_tracker.md
A	campaigns/welfare_ton_mrv_outreach_tracker_v2_2026-04-22.md
A	campaigns/welfare_ton_mrv_outreach_tracker_v3_2026-04-23.md
A	campaigns/welfare_ton_mrv_pilot_commitment_plan.md
A	campaigns/welfare_ton_mrv_target_list.md
A	campaigns/welfare_ton_mrv_target_list_v2_2026-04-22.md
A	codex_skills/terminal-guardian/SKILL.md
A	codex_skills/terminal-guardian/references/anti_spaghetti_checklist.md
M	cron_jobs.json
A	dashboard/.audit-screens/dashboard-agent-detail-sweep.png
A	dashboard/.audit-screens/dashboard-agent-probe.png
A	dashboard/.audit-screens/dashboard-command-post-sweep.png
A	dashboard/.audit-screens/dashboard-glm-sweep.png
A	dashboard/.audit-screens/dashboard-models-sweep.png
A	dashboard/.audit-screens/dashboard-observatory-sweep.png
A	dashboard/.audit-screens/dashboard-qwen-sweep.png
A	dashboard/.audit-screens/overview-expanded.png
A	dashboard/.audit-screens/workspace-chat.png
A	dashboard/.audit-screens/workspace-config.png
A	dashboard/.audit-screens/workspace-connections.png
A	dashboard/.audit-screens/workspace-overview.png
A	dashboard/.audit-screens/workspace-tasks.png
A	dashboard/public/hud-scene.glb
A	dashboard/scripts/generate_hud_scene.py
M	dashboard/src/app/dashboard/agents/[id]/page.tsx
M	dashboard/src/app/dashboard/agents/page.tsx
A	dashboard/src/app/dashboard/artifacts/page.tsx
A	dashboard/src/app/dashboard/cascade/page.tsx
A	dashboard/src/app/dashboard/catalytic/page.tsx
A	dashboard/src/app/dashboard/doctor/page.tsx
M	dashboard/src/app/dashboard/evolution/page.tsx
A	dashboard/src/app/dashboard/fleet/page.tsx
A	dashboard/src/app/dashboard/gates-analysis/page.tsx
A	dashboard/src/app/dashboard/jobs/page.tsx
M	dashboard/src/app/dashboard/layout.tsx
M	dashboard/src/app/dashboard/models/page.tsx
M	dashboard/src/app/dashboard/page.tsx
M	dashboard/src/app/dashboard/stigmergy/page.tsx
A	dashboard/src/app/dashboard/strange-loop/page.tsx
A	dashboard/src/app/dashboard/vsm/page.tsx
M	dashboard/src/app/globals.css
M	dashboard/src/app/page.tsx
A	dashboard/src/components/dashboard/FleetStatusBadge.tsx
A	dashboard/src/components/dashboard/OperatorActions.tsx
A	dashboard/src/components/layout/DashboardCommandPalette.tsx
M	dashboard/src/components/layout/OperatorMicrographics.tsx
M	dashboard/src/components/layout/Sidebar.tsx
M	dashboard/src/components/ui/ErrorBanner.tsx
M	dashboard/src/hooks/useAgents.ts
A	dashboard/src/hooks/useCatalytic.ts
M	dashboard/src/hooks/useEvolution.ts
A	dashboard/src/hooks/useFleet.ts
M	dashboard/src/hooks/useHealth.ts
M	dashboard/src/hooks/useLevel.ts
M	dashboard/src/hooks/useOverview.ts
A	dashboard/src/hooks/useStrangeLoop.ts
A	dashboard/src/hooks/useSystemPulse.ts
A	dashboard/src/lib/backendReachability.test.ts
A	dashboard/src/lib/backendReachability.ts
A	dashboard/src/lib/clientSnapshotCache.ts
M	dashboard/src/lib/dashboardNav.test.ts
M	dashboard/src/lib/dashboardNav.ts
A	dashboard/src/lib/fleetFormat.ts
M	dashboard/src/lib/types.ts
M	dharma_swarm/agent_runner.py
M	dharma_swarm/archive.py
A	dharma_swarm/assurance/meta_learning.py
M	dharma_swarm/assurance/run_scanners.py
M	dharma_swarm/assurance/runner.py
A	dharma_swarm/assurance/scanner_boundaries.py
A	dharma_swarm/assurance/scanner_complexity.py
A	dharma_swarm/assurance/scanner_concepts.py
A	dharma_swarm/assurance/scanner_config_state.py
A	dharma_swarm/assurance/scanner_placeholders.py
M	dharma_swarm/assurance/scanner_routes.py
M	dharma_swarm/assurance/status.py
M	dharma_swarm/autonomous_agent.py
M	dharma_swarm/build_engine.py
M	dharma_swarm/cli.py
M	dharma_swarm/context.py
M	dharma_swarm/cron_runner.py
A	dharma_swarm/cross_pollination.py
M	dharma_swarm/curriculum_engine.py
A	dharma_swarm/deep_agent_backend.py
A	dharma_swarm/deep_agent_harness.py
M	dharma_swarm/dgc_cli.py
M	dharma_swarm/economic_engine.py
M	dharma_swarm/economic_fitness.py
A	dharma_swarm/fleet_control.py
M	dharma_swarm/ginko_agents.py
A	dharma_swarm/hermes_bridge.py
A	dharma_swarm/immutable_audit.py
A	dharma_swarm/insight_brief.py
A	dharma_swarm/knowledge_compiler/__init__.py
A	dharma_swarm/knowledge_compiler/compile.py
A	dharma_swarm/knowledge_compiler/config.py
A	dharma_swarm/knowledge_compiler/connections.py
A	dharma_swarm/knowledge_compiler/flush.py
A	dharma_swarm/knowledge_compiler/lint.py
A	dharma_swarm/knowledge_compiler/query.py
A	dharma_swarm/knowledge_compiler/schema.py
A	dharma_swarm/knowledge_compiler/seed.py
A	dharma_swarm/knowledge_compiler/session_extract.py
A	dharma_swarm/llm_gate_evaluator.py
M	dharma_swarm/ontology.py
A	dharma_swarm/ontology_action_gateway.py
A	dharma_swarm/ontology_context.py
M	dharma_swarm/orchestrate_live.py
A	dharma_swarm/persistent_memory.py
A	dharma_swarm/self_awareness_monitor.py
M	dharma_swarm/sleep_cycle.py
M	dharma_swarm/swarm.py
M	dharma_swarm/task_board.py
M	dharma_swarm/telic_seam.py
M	dharma_swarm/telos_gates.py
M	dharma_swarm/terminal_bridge.py
M	dharma_swarm/terminal_bridge_renderers.py
M	dharma_swarm/thinkodynamic_director.py
A	dharma_swarm/welfare_ton_mrv/__init__.py
M	dharma_swarm/zeitgeist.py
A	docs/LANGGRAPH_INTEL_2026_04_10.md
A	docs/governance/ontology_v0_recovery_2026-05-01.md
A	docs/interface_mismatches.yaml
A	docs/parking_lot/REFRAMES_DEFERRED.md
A	docs/plans/2026-04-10-dharma-deep-agent-harness-build-spec.md
A	docs/plans/ontology-native-flow-001-insight-brief.md
A	docs/public/anthropic_economic_futures_concept_note_2026-04-21.md
A	docs/public/anti_greenwashing_governance_charter_2026-04-21.md
A	docs/public/community_transition_pilot_archetypes_2026-04-21.md
A	docs/public/ecological_partner_classes_2026-04-21.md
A	docs/public/planetary_reciprocity_commons_brief_2026-04-21.md
A	docs/reports/CONTEXTPLUS_INTEGRATION_2026-04-08.md
A	docs/superpowers/specs/2026-04-10-ontology-agent-loop-design.md
M	pyproject.toml
A	references/research/agentic_autonomy_2026-03-27/bundle_summary.md
A	references/research/agentic_autonomy_2026-03-27/cashclaw_2026.md
A	references/research/agentic_autonomy_2026-03-27/deepagents_repo_2026.md
A	references/research/agentic_autonomy_2026-03-27/economic_closure_spine_notes.md
A	references/research/agentic_autonomy_2026-03-27/harness_self_evolution_notes.md
A	references/research/agentic_autonomy_2026-03-27/hyrve_ai_2026.md
A	references/research/agentic_autonomy_2026-03-27/identity_constitution_lineage_notes.md
A	references/research/agentic_autonomy_2026-03-27/langchain_deepagents_context_2026-01-28.md
A	references/research/agentic_autonomy_2026-03-27/langchain_deepagents_multi_agent_2026-01-21.md
A	references/research/agentic_autonomy_2026-03-27/mempo_2026-03-17.md
A	references/research/agentic_autonomy_2026-03-27/meta_rea_2026-03-17.md
A	references/research/agentic_autonomy_2026-03-27/microsoft_plugmem_2026-03-10.md
A	references/research/agentic_autonomy_2026-03-27/minimax_m27_2026-03-18.md
A	references/research/agentic_autonomy_2026-03-27/openroom_2026.md
A	references/research/agentic_autonomy_2026-03-27/ouroboros_2026.md
A	references/research/agentic_autonomy_2026-03-27/ouroboros_desktop_2026.md
A	references/research/agentic_autonomy_2026-03-27/paybot_mcp_2026.md
A	references/research/agentic_autonomy_2026-03-27/runtime_work_packages.md
A	references/research/agentic_autonomy_2026-03-27/source_index.md
A	references/research/agentic_autonomy_2026-03-27/sources.json
A	references/research/agentic_autonomy_2026-03-27/wait_state_job_engine_notes.md
A	reports/audit/runtime_truth/CLAUDE_SEMANTIC_TRUTH.md
A	reports/audit/runtime_truth/CODEX_RUNTIME_TRUTH.md
A	reports/ops/BACKLOG_ORGANIZATION.md
A	reports/ops/PR28_STATUS.md
A	roaming_mailbox/agents/kimi_2_6_claw/canonical_registration.json
A	roaming_mailbox/agents/kimi_2_6_claw/heartbeat.json
A	roaming_mailbox/agents/kimi_2_6_claw/reports/.gitkeep
A	scripts/first_real_mutation.py
A	scripts/hermes_agni.py
A	scripts/hermes_agni_shell.sh
A	scripts/live_fire_metabolism.py
A	scripts/reality_probe.py
A	scripts/seed_codex_opportunities.py
A	scripts/setup_hooks.sh
A	scripts/test_daemon_boot.py
A	scripts/upgrade_opportunity_board.py
A	scripts/uplift_guards/.kernel_sha256
A	scripts/uplift_guards/__init__.py
A	scripts/uplift_guards/autonomous_guard.py
A	scripts/uplift_guards/hotpath_guard.py
A	scripts/uplift_guards/kernel_guard.py
A	scripts/uplift_guards/mismatch_registry.py
A	scripts/uplift_guards/replay_history.py
A	scripts/uplift_guards/run_pre_commit.py
A	scripts/uplift_guards/secrets_guard.py
A	scripts/wiki_cli.py
A	telos_sdk/__init__.py
A	telos_sdk/gates/__init__.py
A	telos_sdk/gates/registry.py
A	telos_sdk/models/__init__.py
A	telos_sdk/models/gate.py
A	terminal-v2/README.md
A	terminal-v2/bun.lock
A	terminal-v2/package.json
A	terminal-v2/screenshots/e2e_00_boot.png
A	terminal-v2/screenshots/e2e_01_help.png
A	terminal-v2/screenshots/e2e_02_wait_00.png
A	terminal-v2/screenshots/e2e_02_wait_01.png
A	terminal-v2/screenshots/e2e_02_wait_02.png
A	terminal-v2/screenshots/e2e_02_wait_03.png
A	terminal-v2/screenshots/e2e_02_wait_04.png
A	terminal-v2/screenshots/e2e_02_wait_05.png
A	terminal-v2/screenshots/e2e_02_wait_06.png
A	terminal-v2/screenshots/e2e_02_wait_07.png
A	terminal-v2/screenshots/e2e_02_wait_08.png
A	terminal-v2/screenshots/e2e_02_wait_09.png
A	terminal-v2/screenshots/e2e_02_wait_10.png
A	terminal-v2/screenshots/e2e_02_wait_11.png
A	terminal-v2/screenshots/e2e_03_final.png
A	terminal-v2/screenshots/fix_00_boot.png
A	terminal-v2/screenshots/fix_01_boot.png
A	terminal-v2/screenshots/fix_02_help.png
A	terminal-v2/screenshots/fix_03_chat_0.png
A	terminal-v2/screenshots/fix_03_chat_1.png
A	terminal-v2/screenshots/fix_03_chat_10.png
A	terminal-v2/screenshots/fix_03_chat_11.png
A	terminal-v2/screenshots/fix_03_chat_2.png
A	terminal-v2/screenshots/fix_03_chat_3.png
A	terminal-v2/screenshots/fix_03_chat_4.png
A	terminal-v2/screenshots/fix_03_chat_5.png
A	terminal-v2/screenshots/fix_03_chat_6.png
A	terminal-v2/screenshots/fix_03_chat_7.png
A	terminal-v2/screenshots/fix_03_chat_8.png
A	terminal-v2/screenshots/fix_03_chat_9.png
A	terminal-v2/screenshots/post_build_01.png
A	terminal-v2/screenshots/v2_01_baseline.png
A	terminal-v2/screenshots/v2_02_after_boot.png
A	terminal-v2/screenshots/v2_03_bridge_fixed.png
A	terminal-v2/screenshots/verify_00_boot.png
A	terminal-v2/screenshots/verify_01_tab_agents.png
A	terminal-v2/screenshots/verify_01_tab_chat.png
A	terminal-v2/screenshots/verify_01_tab_control.png
A	terminal-v2/screenshots/verify_01_tab_evolution.png
A	terminal-v2/screenshots/verify_01_tab_repo.png
A	terminal-v2/screenshots/verify_01_tab_timeline.png
A	terminal-v2/screenshots/verify_02_help.png
A	terminal-v2/screenshots/verify_03_status.png
A	terminal-v2/screenshots/verify_04_chat_0.png
A	terminal-v2/screenshots/verify_04_chat_1.png
A	terminal-v2/screenshots/verify_04_chat_2.png
A	terminal-v2/screenshots/verify_04_chat_3.png
A	terminal-v2/screenshots/verify_04_chat_4.png
A	terminal-v2/screenshots/verify_04_chat_5.png
A	terminal-v2/screenshots/verify_04_chat_6.png
A	terminal-v2/screenshots/verify_04_chat_7.png
A	terminal-v2/screenshots/verify_04_chat_8.png
A	terminal-v2/screenshots/verify_05_model_picker.png
A	terminal-v2/screenshots/verify_06_refresh.png
A	terminal-v2/screenshots/verify_07_final.png
M	terminal-v2/src/App.tsx
A	terminal-v2/src/core/bridge.ts
A	terminal-v2/src/core/bridgeRequests.ts
A	terminal-v2/src/core/executionLog.ts
A	terminal-v2/src/core/freshness.ts
A	terminal-v2/src/core/mockContent.ts
A	terminal-v2/src/core/persistence.ts
A	terminal-v2/src/core/protocol.ts
A	terminal-v2/src/core/repoControlPreview.ts
A	terminal-v2/src/core/routePolicy.ts
A	terminal-v2/src/core/shellControls.ts
A	terminal-v2/src/core/state.ts
A	terminal-v2/src/core/transcriptFormatting.ts
A	terminal-v2/src/core/types.ts
A	terminal-v2/src/core/verification.ts
A	terminal-v2/src/hooks/useApi.ts
A	terminal-v2/src/hooks/useBridge.ts
A	terminal-v2/src/hooks/useFrameBatcher.ts
A	terminal-v2/src/index.tsx
A	terminal-v2/src/overlays/ModelPicker.tsx
A	terminal-v2/src/overlays/PaneSwitcher.tsx
A	terminal-v2/src/panes/ActivityPane.tsx
A	terminal-v2/src/panes/AgentsPane.tsx
A	terminal-v2/src/panes/ApprovalsPane.tsx
A	terminal-v2/src/panes/ChatPane.tsx
A	terminal-v2/src/panes/ControlPane.tsx
A	terminal-v2/src/panes/RepoPane.tsx
A	terminal-v2/src/panes/SessionsPane.tsx
A	terminal-v2/src/shell/Composer.tsx
A	terminal-v2/src/shell/MainPane.tsx
A	terminal-v2/src/shell/OperatorSummaryBand.tsx
A	terminal-v2/src/shell/ScenicStrip.tsx
A	terminal-v2/src/shell/ShellHeader.tsx
A	terminal-v2/src/shell/Sidebar.tsx
A	terminal-v2/src/shell/StatusFooter.tsx
A	terminal-v2/src/shell/TabBar.tsx
A	terminal-v2/src/theme.ts
A	terminal-v2/tests/core/app.test.ts
A	terminal-v2/tests/core/controlPane.test.ts
A	terminal-v2/tests/core/executionLog.test.ts
A	terminal-v2/tests/core/operatorSummaryBand.test.tsx
A	terminal-v2/tests/core/persistence.test.ts
A	terminal-v2/tests/core/protocol.test.ts
A	terminal-v2/tests/core/repoControlPreview.test.ts
A	terminal-v2/tests/core/repoPane.test.ts
A	terminal-v2/tests/core/routePolicy.test.ts
A	terminal-v2/tests/core/sidebar.test.ts
A	terminal-v2/tests/core/state.test.ts
A	terminal-v2/tests/core/transcriptFormatting.test.ts
A	terminal-v2/tests/e2e_prompt.mjs
A	terminal-v2/tests/verify_build.mjs
A	terminal-v2/tests/verify_fix.mjs
A	terminal-v2/tests/visual/boot.test.tsx
A	terminal-v2/tsconfig.json
M	terminal/.dharma-terminal-state.json
A	terminal/screenshots/01_baseline.png
A	terminal/screenshots/chat_00_baseline.png
A	terminal/screenshots/chat_01_model_picker.png
A	terminal/screenshots/chat_02_claude_selected.png
A	terminal/screenshots/chat_03_typed.png
A	terminal/screenshots/chat_04_response_0.png
A	terminal/screenshots/chat_04_response_1.png
A	terminal/screenshots/chat_04_response_2.png
A	terminal/screenshots/chat_04_response_3.png
A	terminal/screenshots/chat_04_response_4.png
A	terminal/screenshots/chat_04_response_5.png
A	terminal/screenshots/chat_05_timeline.png
A	terminal/screenshots/def_01_route.png
A	terminal/screenshots/def_02_typed.png
A	terminal/screenshots/def_03_w00.png
A	terminal/screenshots/def_03_w01.png
A	terminal/screenshots/def_03_w02.png
A	terminal/screenshots/def_03_w03.png
A	terminal/screenshots/def_03_w04.png
A	terminal/screenshots/def_03_w05.png
A	terminal/screenshots/def_03_w06.png
A	terminal/screenshots/def_03_w07.png
A	terminal/screenshots/def_03_w08.png
A	terminal/screenshots/def_03_w09.png
A	terminal/screenshots/def_03_w10.png
A	terminal/screenshots/def_03_w11.png
A	terminal/screenshots/def_03_w12.png
A	terminal/screenshots/def_03_w13.png
A	terminal/screenshots/def_03_w14.png
A	terminal/screenshots/def_03_w15.png
A	terminal/screenshots/def_03_w16.png
A	terminal/screenshots/def_03_w17.png
A	terminal/screenshots/def_04_final.png
A	terminal/screenshots/def_05_scrolled.png
A	terminal/screenshots/e2e_00_baseline.png
A	terminal/screenshots/e2e_01_help_result.png
A	terminal/screenshots/e2e_01_help_typed.png
A	terminal/screenshots/e2e_02_runtime_result.png
A	terminal/screenshots/e2e_02_runtime_typed.png
A	terminal/screenshots/e2e_03_git_result.png
A	terminal/screenshots/e2e_03_git_typed.png
A	terminal/screenshots/e2e_04_chat_result.png
A	terminal/screenshots/e2e_04_chat_typed.png
A	terminal/screenshots/e2e_05_status_result.png
A	terminal/screenshots/e2e_05_status_typed.png
A	terminal/screenshots/e2e_06_chat_final.png
A	terminal/screenshots/e2e_07_timeline_final.png
A	terminal/screenshots/final_01_route_claude.png
A	terminal/screenshots/final_02_typed.png
A	terminal/screenshots/final_03_wait_00.png
A	terminal/screenshots/final_03_wait_01.png
A	terminal/screenshots/final_03_wait_02.png
A	terminal/screenshots/final_03_wait_03.png
A	terminal/screenshots/final_03_wait_04.png
A	terminal/screenshots/final_03_wait_05.png
A	terminal/screenshots/final_03_wait_06.png
A	terminal/screenshots/final_03_wait_07.png
A	terminal/screenshots/final_03_wait_08.png
A	terminal/screenshots/final_03_wait_09.png
A	terminal/screenshots/final_03_wait_10.png
A	terminal/screenshots/final_03_wait_11.png
A	terminal/screenshots/final_04_chat_final.png
A	terminal/screenshots/final_05_chat_scrolled.png
A	terminal/screenshots/full_01_picker.png
A	terminal/screenshots/full_02_route_set.png
A	terminal/screenshots/full_03_typed.png
A	terminal/screenshots/full_04_wait_00.png
A	terminal/screenshots/full_04_wait_01.png
A	terminal/screenshots/full_04_wait_02.png
A	terminal/screenshots/full_04_wait_03.png
A	terminal/screenshots/full_04_wait_04.png
A	terminal/screenshots/full_04_wait_05.png
A	terminal/screenshots/full_04_wait_06.png
A	terminal/screenshots/full_04_wait_07.png
A	terminal/screenshots/full_04_wait_08.png
A	terminal/screenshots/full_04_wait_09.png
A	terminal/screenshots/full_04_wait_10.png
A	terminal/screenshots/full_04_wait_11.png
A	terminal/screenshots/full_05_timeline.png
A	terminal/screenshots/full_06_thinking.png
A	terminal/screenshots/full_07_chat_final.png
A	terminal/screenshots/kb_01_tab.png
A	terminal/screenshots/kb_02_tab2.png
A	terminal/screenshots/kb_03_shift_tab.png
A	terminal/screenshots/kb_04_bracket_right.png
A	terminal/screenshots/kb_05_bracket_left.png
A	terminal/screenshots/kb_06_sidebar_toc.png
A	terminal/screenshots/kb_07_sidebar_ctx.png
A	terminal/screenshots/kb_08_sidebar_help.png
A	terminal/screenshots/kb_09_j_down.png
A	terminal/screenshots/kb_10_k_up.png
A	terminal/screenshots/kb_11_ctrl_b.png
A	terminal/screenshots/kb_12_ctrl_b2.png
A	terminal/screenshots/kb_13_ctrl_b3.png
A	terminal/screenshots/kb_14_ctrl_g.png
A	terminal/screenshots/kb_15_ctrl_r.png
A	terminal/screenshots/kb_16_ctrl_a.png
A	terminal/screenshots/kb_17_ctrl_t.png
A	terminal/screenshots/kb_18_ctrl_e.png
A	terminal/screenshots/kb_19_ctrl_n.png
A	terminal/screenshots/kb_20_ctrl_y.png
A	terminal/screenshots/kb_21_ctrl_p.png
A	terminal/screenshots/kb_22_escape.png
A	terminal/screenshots/kb_23_ctrl_k.png
A	terminal/screenshots/kb_24_switcher_j.png
A	terminal/screenshots/kb_25_switcher_k.png
A	terminal/screenshots/kb_26_escape2.png
A	terminal/screenshots/kb_27_ctrl_l.png
A	terminal/screenshots/kb_28_ctrl_w.png
A	terminal/screenshots/leader_00_baseline.png
A	terminal/screenshots/leader_01_gr_repo.png
A	terminal/screenshots/leader_02_gg_chat.png
A	terminal/screenshots/leader_03_ga_agents.png
A	terminal/screenshots/leader_04_gt_control.png
A	terminal/screenshots/leader_05_ge_evolution.png
A	terminal/screenshots/leader_06_gn_timeline.png
A	terminal/screenshots/leader_07_gy_runtime.png
A	terminal/screenshots/leader_08_gs_sessions.png
A	terminal/screenshots/leader_09_gp_model_picker.png
A	terminal/screenshots/leader_10_gk_pane_switcher.png
A	terminal/screenshots/leader_11_gb_sidebar.png
A	terminal/screenshots/leader_12_gl_refresh.png
A	terminal/screenshots/textual_tui_baseline.png
A	terminal/tests/chat_e2e_test.mjs
A	terminal/tests/definitive_e2e.mjs
A	terminal/tests/final_e2e.mjs
A	terminal/tests/full_e2e_test.mjs
A	terminal/tests/keyboard_test.mjs
A	terminal/tests/leader_key_test.mjs
A	terminal/tests/prompt_e2e_test.mjs
A	terminal/tests/visual_feedback.mjs
A	tests/mismatches/__init__.py
A	tests/mismatches/test_MISMATCH_01.py
A	tests/mismatches/test_MISMATCH_02.py
M	tests/test_agent_runner_routing_feedback.py
M	tests/test_agents_router.py
M	tests/test_assurance.py
M	tests/test_autonomous_agent.py
M	tests/test_build_engine.py
A	tests/test_contracts.py
M	tests/test_curriculum_engine.py
M	tests/test_dashboard_chat_router.py
A	tests/test_dashboard_runtime_routes.py
A	tests/test_deep_agent_backend.py
A	tests/test_deep_agent_harness.py
M	tests/test_doctor.py
M	tests/test_economic_engine.py
A	tests/test_economic_metabolism.py
M	tests/test_event_memory_integration.py
A	tests/test_fleet_control.py
M	tests/test_ginko_agents.py
A	tests/test_hermes_bridge.py
A	tests/test_immutable_audit.py
A	tests/test_insight_brief.py
A	tests/test_knowledge_compiler.py
A	tests/test_llm_gate_evaluator.py
A	tests/test_ontology_context.py
M	tests/test_ontology_registry.py
A	tests/test_persistent_memory.py
A	tests/test_private_access.py
M	tests/test_providers.py
A	tests/test_self_awareness_monitor.py
M	tests/test_swarm.py
M	tests/test_task_board.py
M	tests/test_terminal_bridge.py
M	tests/test_thinkodynamic_director.py
A	tests/test_uplift_guards.py
A	tests/test_viz_router.py
M	tests/test_zeitgeist.py
A	uv.lock
```
#### `stash@{66}` — WIP on main: 4ec9579 fix: 3 critical integration fixes — recognition, knowledge extraction, director vision
```text
A	.playwright-mcp/console-2026-04-03T14-47-55-878Z.log
A	.playwright-mcp/console-2026-04-03T14-58-50-550Z.log
A	.playwright-mcp/console-2026-04-03T15-11-41-801Z.log
A	.playwright-mcp/console-2026-04-03T23-56-36-556Z.log
A	.playwright-mcp/console-2026-04-04T00-01-13-165Z.log
A	.playwright-mcp/page-2026-04-03T14-47-56-067Z.yml
A	.playwright-mcp/page-2026-04-03T14-51-51-186Z.yml
A	.playwright-mcp/page-2026-04-03T14-52-14-541Z.yml
A	.playwright-mcp/page-2026-04-03T14-52-31-294Z.yml
A	.playwright-mcp/page-2026-04-03T14-52-43-480Z.yml
A	.playwright-mcp/page-2026-04-03T14-56-47-983Z.yml
A	.playwright-mcp/page-2026-04-03T14-58-50-665Z.yml
A	.playwright-mcp/page-2026-04-03T14-59-12-046Z.yml
A	.playwright-mcp/page-2026-04-03T15-11-41-918Z.yml
A	.playwright-mcp/page-2026-04-03T23-56-36-657Z.yml
A	.playwright-mcp/page-2026-04-03T23-57-01-972Z.yml
A	.playwright-mcp/page-2026-04-04T00-01-13-244Z.yml
A	.playwright-mcp/page-2026-04-04T00-44-46-027Z.yml
A	.playwright-mcp/page-2026-04-04T00-50-30-958Z.yml
A	build_queues/operator_cockpit_truth.queue.json
A	build_queues/terminal_tui_rebuild.queue.json
A	codex_skills/terminal-guardian/SKILL.md
A	codex_skills/terminal-guardian/references/anti_spaghetti_checklist.md
A	dashboard/.audit-screens/dashboard-agent-detail-sweep.png
A	dashboard/.audit-screens/dashboard-agent-probe.png
A	dashboard/.audit-screens/dashboard-command-post-sweep.png
A	dashboard/.audit-screens/dashboard-glm-sweep.png
A	dashboard/.audit-screens/dashboard-models-sweep.png
A	dashboard/.audit-screens/dashboard-observatory-sweep.png
A	dashboard/.audit-screens/dashboard-qwen-sweep.png
A	dashboard/.audit-screens/overview-expanded.png
A	dashboard/.audit-screens/workspace-chat.png
A	dashboard/.audit-screens/workspace-config.png
A	dashboard/.audit-screens/workspace-connections.png
A	dashboard/.audit-screens/workspace-overview.png
A	dashboard/.audit-screens/workspace-tasks.png
A	dharma_swarm/cross_pollination.py
A	dharma_swarm/terminal_adapters/__init__.py
A	dharma_swarm/terminal_adapters/base.py
A	dharma_swarm/terminal_adapters/codex.py
A	dharma_swarm/terminal_adapters/ollama.py
A	dharma_swarm/terminal_commands/__init__.py
A	dharma_swarm/terminal_commands/system_commands.py
A	dharma_swarm/terminal_engine/__init__.py
A	dharma_swarm/terminal_engine/event_types.py
A	dharma_swarm/terminal_engine/events.py
A	dharma_swarm/terminal_engine/governance.py
A	dharma_swarm/terminal_engine/session_store.py
A	dharma_swarm/terminal_engine/stream_parser.py
A	docs/superpowers/plans/2026-04-07-unify-terminal-routing.md
A	references/research/agentic_autonomy_2026-03-27/bundle_summary.md
A	references/research/agentic_autonomy_2026-03-27/cashclaw_2026.md
A	references/research/agentic_autonomy_2026-03-27/deepagents_repo_2026.md
A	references/research/agentic_autonomy_2026-03-27/economic_closure_spine_notes.md
A	references/research/agentic_autonomy_2026-03-27/harness_self_evolution_notes.md
A	references/research/agentic_autonomy_2026-03-27/hyrve_ai_2026.md
A	references/research/agentic_autonomy_2026-03-27/identity_constitution_lineage_notes.md
A	references/research/agentic_autonomy_2026-03-27/langchain_deepagents_context_2026-01-28.md
A	references/research/agentic_autonomy_2026-03-27/langchain_deepagents_multi_agent_2026-01-21.md
A	references/research/agentic_autonomy_2026-03-27/mempo_2026-03-17.md
A	references/research/agentic_autonomy_2026-03-27/meta_rea_2026-03-17.md
A	references/research/agentic_autonomy_2026-03-27/microsoft_plugmem_2026-03-10.md
A	references/research/agentic_autonomy_2026-03-27/minimax_m27_2026-03-18.md
A	references/research/agentic_autonomy_2026-03-27/openroom_2026.md
A	references/research/agentic_autonomy_2026-03-27/ouroboros_2026.md
A	references/research/agentic_autonomy_2026-03-27/ouroboros_desktop_2026.md
A	references/research/agentic_autonomy_2026-03-27/paybot_mcp_2026.md
A	references/research/agentic_autonomy_2026-03-27/runtime_work_packages.md
A	references/research/agentic_autonomy_2026-03-27/source_index.md
A	references/research/agentic_autonomy_2026-03-27/sources.json
A	references/research/agentic_autonomy_2026-03-27/wait_state_job_engine_notes.md
A	terminal-v2/bun.lock
A	terminal-v2/package.json
A	terminal-v2/screenshots/e2e_00_boot.png
A	terminal-v2/screenshots/e2e_01_help.png
A	terminal-v2/screenshots/e2e_02_wait_00.png
A	terminal-v2/screenshots/e2e_02_wait_01.png
A	terminal-v2/screenshots/e2e_02_wait_02.png
A	terminal-v2/screenshots/e2e_02_wait_03.png
A	terminal-v2/screenshots/e2e_02_wait_04.png
A	terminal-v2/screenshots/e2e_02_wait_05.png
A	terminal-v2/screenshots/e2e_02_wait_06.png
A	terminal-v2/screenshots/e2e_02_wait_07.png
A	terminal-v2/screenshots/e2e_02_wait_08.png
A	terminal-v2/screenshots/e2e_02_wait_09.png
A	terminal-v2/screenshots/e2e_02_wait_10.png
A	terminal-v2/screenshots/e2e_02_wait_11.png
A	terminal-v2/screenshots/e2e_03_final.png
A	terminal-v2/screenshots/fix_00_boot.png
A	terminal-v2/screenshots/fix_01_boot.png
A	terminal-v2/screenshots/fix_02_help.png
A	terminal-v2/screenshots/fix_03_chat_0.png
A	terminal-v2/screenshots/fix_03_chat_1.png
A	terminal-v2/screenshots/fix_03_chat_10.png
A	terminal-v2/screenshots/fix_03_chat_11.png
A	terminal-v2/screenshots/fix_03_chat_2.png
A	terminal-v2/screenshots/fix_03_chat_3.png
A	terminal-v2/screenshots/fix_03_chat_4.png
A	terminal-v2/screenshots/fix_03_chat_5.png
A	terminal-v2/screenshots/fix_03_chat_6.png
A	terminal-v2/screenshots/fix_03_chat_7.png
A	terminal-v2/screenshots/fix_03_chat_8.png
A	terminal-v2/screenshots/fix_03_chat_9.png
A	terminal-v2/screenshots/post_build_01.png
A	terminal-v2/screenshots/v2_01_baseline.png
A	terminal-v2/screenshots/v2_02_after_boot.png
A	terminal-v2/screenshots/v2_03_bridge_fixed.png
A	terminal-v2/screenshots/verify_00_boot.png
A	terminal-v2/screenshots/verify_01_tab_agents.png
A	terminal-v2/screenshots/verify_01_tab_chat.png
A	terminal-v2/screenshots/verify_01_tab_control.png
A	terminal-v2/screenshots/verify_01_tab_evolution.png
A	terminal-v2/screenshots/verify_01_tab_repo.png
A	terminal-v2/screenshots/verify_01_tab_timeline.png
A	terminal-v2/screenshots/verify_02_help.png
A	terminal-v2/screenshots/verify_03_status.png
A	terminal-v2/screenshots/verify_04_chat_0.png
A	terminal-v2/screenshots/verify_04_chat_1.png
A	terminal-v2/screenshots/verify_04_chat_2.png
A	terminal-v2/screenshots/verify_04_chat_3.png
A	terminal-v2/screenshots/verify_04_chat_4.png
A	terminal-v2/screenshots/verify_04_chat_5.png
A	terminal-v2/screenshots/verify_04_chat_6.png
A	terminal-v2/screenshots/verify_04_chat_7.png
A	terminal-v2/screenshots/verify_04_chat_8.png
A	terminal-v2/screenshots/verify_05_model_picker.png
A	terminal-v2/screenshots/verify_06_refresh.png
A	terminal-v2/screenshots/verify_07_final.png
A	terminal-v2/src/App.tsx
A	terminal-v2/src/core/bridge.ts
A	terminal-v2/src/core/bridgeRequests.ts
A	terminal-v2/src/core/executionLog.ts
A	terminal-v2/src/core/freshness.ts
A	terminal-v2/src/core/mockContent.ts
A	terminal-v2/src/core/persistence.ts
A	terminal-v2/src/core/protocol.ts
A	terminal-v2/src/core/repoControlPreview.ts
A	terminal-v2/src/core/routePolicy.ts
A	terminal-v2/src/core/shellControls.ts
A	terminal-v2/src/core/state.ts
A	terminal-v2/src/core/transcriptFormatting.ts
A	terminal-v2/src/core/types.ts
A	terminal-v2/src/core/verification.ts
A	terminal-v2/src/hooks/useApi.ts
A	terminal-v2/src/hooks/useBridge.ts
A	terminal-v2/src/hooks/useFrameBatcher.ts
A	terminal-v2/src/index.tsx
A	terminal-v2/src/overlays/ModelPicker.tsx
A	terminal-v2/src/overlays/PaneSwitcher.tsx
A	terminal-v2/src/panes/ActivityPane.tsx
A	terminal-v2/src/panes/AgentsPane.tsx
A	terminal-v2/src/panes/ApprovalsPane.tsx
A	terminal-v2/src/panes/ChatPane.tsx
A	terminal-v2/src/panes/ControlPane.tsx
A	terminal-v2/src/panes/RepoPane.tsx
A	terminal-v2/src/panes/SessionsPane.tsx
A	terminal-v2/src/shell/Composer.tsx
A	terminal-v2/src/shell/MainPane.tsx
A	terminal-v2/src/shell/OperatorSummaryBand.tsx
A	terminal-v2/src/shell/ScenicStrip.tsx
A	terminal-v2/src/shell/ShellHeader.tsx
A	terminal-v2/src/shell/Sidebar.tsx
A	terminal-v2/src/shell/StatusFooter.tsx
A	terminal-v2/src/shell/TabBar.tsx
A	terminal-v2/src/theme.ts
A	terminal-v2/tests/core/app.test.ts
A	terminal-v2/tests/core/controlPane.test.ts
A	terminal-v2/tests/core/executionLog.test.ts
A	terminal-v2/tests/core/operatorSummaryBand.test.tsx
A	terminal-v2/tests/core/persistence.test.ts
A	terminal-v2/tests/core/protocol.test.ts
A	terminal-v2/tests/core/repoControlPreview.test.ts
A	terminal-v2/tests/core/repoPane.test.ts
A	terminal-v2/tests/core/routePolicy.test.ts
A	terminal-v2/tests/core/sidebar.test.ts
A	terminal-v2/tests/core/state.test.ts
A	terminal-v2/tests/core/transcriptFormatting.test.ts
A	terminal-v2/tests/e2e_prompt.mjs
A	terminal-v2/tests/verify_build.mjs
A	terminal-v2/tests/verify_fix.mjs
A	terminal-v2/tests/visual/boot.test.tsx
A	terminal-v2/tsconfig.json
M	terminal/.dharma-terminal-state.json
A	terminal/bun.lock
A	terminal/screenshots/01_baseline.png
A	terminal/screenshots/chat_00_baseline.png
A	terminal/screenshots/chat_01_model_picker.png
A	terminal/screenshots/chat_02_claude_selected.png
A	terminal/screenshots/chat_03_typed.png
A	terminal/screenshots/chat_04_response_0.png
A	terminal/screenshots/chat_04_response_1.png
A	terminal/screenshots/chat_04_response_2.png
A	terminal/screenshots/chat_04_response_3.png
A	terminal/screenshots/chat_04_response_4.png
A	terminal/screenshots/chat_04_response_5.png
A	terminal/screenshots/chat_05_timeline.png
A	terminal/screenshots/def_01_route.png
A	terminal/screenshots/def_02_typed.png
A	terminal/screenshots/def_03_w00.png
A	terminal/screenshots/def_03_w01.png
A	terminal/screenshots/def_03_w02.png
A	terminal/screenshots/def_03_w03.png
A	terminal/screenshots/def_03_w04.png
A	terminal/screenshots/def_03_w05.png
A	terminal/screenshots/def_03_w06.png
A	terminal/screenshots/def_03_w07.png
A	terminal/screenshots/def_03_w08.png
A	terminal/screenshots/def_03_w09.png
A	terminal/screenshots/def_03_w10.png
A	terminal/screenshots/def_03_w11.png
A	terminal/screenshots/def_03_w12.png
A	terminal/screenshots/def_03_w13.png
A	terminal/screenshots/def_03_w14.png
A	terminal/screenshots/def_03_w15.png
A	terminal/screenshots/def_03_w16.png
A	terminal/screenshots/def_03_w17.png
A	terminal/screenshots/def_04_final.png
A	terminal/screenshots/def_05_scrolled.png
A	terminal/screenshots/e2e_00_baseline.png
A	terminal/screenshots/e2e_01_help_result.png
A	terminal/screenshots/e2e_01_help_typed.png
A	terminal/screenshots/e2e_02_runtime_result.png
A	terminal/screenshots/e2e_02_runtime_typed.png
A	terminal/screenshots/e2e_03_git_result.png
A	terminal/screenshots/e2e_03_git_typed.png
A	terminal/screenshots/e2e_04_chat_result.png
A	terminal/screenshots/e2e_04_chat_typed.png
A	terminal/screenshots/e2e_05_status_result.png
A	terminal/screenshots/e2e_05_status_typed.png
A	terminal/screenshots/e2e_06_chat_final.png
A	terminal/screenshots/e2e_07_timeline_final.png
A	terminal/screenshots/final_01_route_claude.png
A	terminal/screenshots/final_02_typed.png
A	terminal/screenshots/final_03_wait_00.png
A	terminal/screenshots/final_03_wait_01.png
A	terminal/screenshots/final_03_wait_02.png
A	terminal/screenshots/final_03_wait_03.png
A	terminal/screenshots/final_03_wait_04.png
A	terminal/screenshots/final_03_wait_05.png
A	terminal/screenshots/final_03_wait_06.png
A	terminal/screenshots/final_03_wait_07.png
A	terminal/screenshots/final_03_wait_08.png
A	terminal/screenshots/final_03_wait_09.png
A	terminal/screenshots/final_03_wait_10.png
A	terminal/screenshots/final_03_wait_11.png
A	terminal/screenshots/final_04_chat_final.png
A	terminal/screenshots/final_05_chat_scrolled.png
A	terminal/screenshots/full_01_picker.png
A	terminal/screenshots/full_02_route_set.png
A	terminal/screenshots/full_03_typed.png
A	terminal/screenshots/full_04_wait_00.png
A	terminal/screenshots/full_04_wait_01.png
A	terminal/screenshots/full_04_wait_02.png
A	terminal/screenshots/full_04_wait_03.png
A	terminal/screenshots/full_04_wait_04.png
A	terminal/screenshots/full_04_wait_05.png
A	terminal/screenshots/full_04_wait_06.png
A	terminal/screenshots/full_04_wait_07.png
A	terminal/screenshots/full_04_wait_08.png
A	terminal/screenshots/full_04_wait_09.png
A	terminal/screenshots/full_04_wait_10.png
A	terminal/screenshots/full_04_wait_11.png
A	terminal/screenshots/full_05_timeline.png
A	terminal/screenshots/full_06_thinking.png
A	terminal/screenshots/full_07_chat_final.png
A	terminal/screenshots/kb_01_tab.png
A	terminal/screenshots/kb_02_tab2.png
A	terminal/screenshots/kb_03_shift_tab.png
A	terminal/screenshots/kb_04_bracket_right.png
A	terminal/screenshots/kb_05_bracket_left.png
A	terminal/screenshots/kb_06_sidebar_toc.png
A	terminal/screenshots/kb_07_sidebar_ctx.png
A	terminal/screenshots/kb_08_sidebar_help.png
A	terminal/screenshots/kb_09_j_down.png
A	terminal/screenshots/kb_10_k_up.png
A	terminal/screenshots/kb_11_ctrl_b.png
A	terminal/screenshots/kb_12_ctrl_b2.png
A	terminal/screenshots/kb_13_ctrl_b3.png
A	terminal/screenshots/kb_14_ctrl_g.png
A	terminal/screenshots/kb_15_ctrl_r.png
A	terminal/screenshots/kb_16_ctrl_a.png
A	terminal/screenshots/kb_17_ctrl_t.png
A	terminal/screenshots/kb_18_ctrl_e.png
A	terminal/screenshots/kb_19_ctrl_n.png
A	terminal/screenshots/kb_20_ctrl_y.png
A	terminal/screenshots/kb_21_ctrl_p.png
A	terminal/screenshots/kb_22_escape.png
A	terminal/screenshots/kb_23_ctrl_k.png
A	terminal/screenshots/kb_24_switcher_j.png
A	terminal/screenshots/kb_25_switcher_k.png
A	terminal/screenshots/kb_26_escape2.png
A	terminal/screenshots/kb_27_ctrl_l.png
A	terminal/screenshots/kb_28_ctrl_w.png
A	terminal/screenshots/leader_00_baseline.png
A	terminal/screenshots/leader_01_gr_repo.png
A	terminal/screenshots/leader_02_gg_chat.png
A	terminal/screenshots/leader_03_ga_agents.png
A	terminal/screenshots/leader_04_gt_control.png
A	terminal/screenshots/leader_05_ge_evolution.png
A	terminal/screenshots/leader_06_gn_timeline.png
A	terminal/screenshots/leader_07_gy_runtime.png
A	terminal/screenshots/leader_08_gs_sessions.png
A	terminal/screenshots/leader_09_gp_model_picker.png
A	terminal/screenshots/leader_10_gk_pane_switcher.png
A	terminal/screenshots/leader_11_gb_sidebar.png
A	terminal/screenshots/leader_12_gl_refresh.png
A	terminal/screenshots/textual_tui_baseline.png
A	terminal/tests/chat_e2e_test.mjs
A	terminal/tests/definitive_e2e.mjs
A	terminal/tests/final_e2e.mjs
A	terminal/tests/full_e2e_test.mjs
A	terminal/tests/keyboard_test.mjs
A	terminal/tests/leader_key_test.mjs
A	terminal/tests/prompt_e2e_test.mjs
A	terminal/tests/visual_feedback.mjs
```
#### `stash@{67}` — WIP on main: 4ec9579 fix: 3 critical integration fixes — recognition, knowledge extraction, director vision
```text
M	terminal/.dharma-terminal-state.json
```
#### `stash@{68}` — WIP on main: 27f84e4 feat(dashboard): collapsible micrographics header — collapsed by default, saves 550px viewport
```text
M	dharma_swarm/agent_runner.py
M	dharma_swarm/model_hierarchy.py
M	dharma_swarm/orchestrator.py
M	dharma_swarm/terminal_bridge.py
M	dharma_swarm/tui/engine/adapters/claude.py
M	dharma_swarm/tui/model_routing.py
M	terminal/.dharma-terminal-state.json
M	tests/tui/test_model_routing.py
```
#### `stash@{69}` — WIP on main: 06405c9 feat(terminal): Bun TUI cleanup + governance audit + dual-audit tool
```text
M	terminal/src/app.tsx
```
