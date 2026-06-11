# Dharma Forge / Hydra Archaeology

Date: 2026-06-11
Original source branch for this handoff: `qwen/spine-adoption`
Audience: remote Devin / roaming agent without access to local `~/.dharma`
Status: archaeology report, not a launch authorization

## Remote Read Card

The live-ops census on main registers a mission surface named `Forge Reality Arena Hydra`, but its declared restart command, `scripts/start_forge_hydra_long_run.sh`, does not exist on `origin/main` or in the local worktree scanned. The real runtime state is off-repo under `~/.dharma/forge_reality_arena_master`, with heartbeat and handoff files showing the mission stopped honestly on 2026-06-02 after exhausting internal packets. The current conclusion is: keep the Forge/Hydra evidence, do not merge the Hydra blob wholesale, and extract only the narrow launcher/status/receipt contract needed for future agents to reason about it.

This document is self-contained for remote readers. Paths marked `[off-repo]` were present on the operator machine when this report was written; remote agents will usually not have them unless a state bundle is separately provided.

## Custody Labels

- `[main]`: file exists on `origin/main`.
- `[source branch: qwen/spine-adoption]`: file existed on that source branch when this report was written; if this report is read from main, treat this as historical custody unless the path is also present on main.
- `[branch: forge/dharma-reward-forge-v0]`: file exists on that branch, not main.
- `[branch: cashclaw/revenue-hydra-v1]`: file exists on that branch/worktree, not main.
- `[untracked]`: local file in the current worktree, not committed.
- `[off-repo]`: state/log/receipt file outside the git repo.
- `[missing]`: path cited by live state or handoff, but not found in the checked locations.

## 1. What Dharma Forge / Hydra Is

Dharma Forge is the organism's reality-reward membrane: it tries to turn every inward agent improvement, VentureCell action, bounty PR, benchmark run, failure capsule, and external human response into a verifiable receipt that can safely influence swarm fitness. Hydra is the long-running execution pattern around that: many-headed, receipt-first, overnight or `ds-goal` driven, pushing Forge packets until it either closes an internal proof loop or hits a real external authority gate. In operator framing, it is not another runner; it is the anti-theater loss-function spine for self-evolution.

Primary conceptual anchors:

- `dharma_swarm/quality_forge.py` `[main]`: artifact scoring/diagnostic Forge, not Hydra.
- `docs/architecture/DHARMA_REWARD_FORGE.md` `[branch: forge/dharma-reward-forge-v0]`: design doc saying Forge is the loss-function spine, not a product layer.
- `scripts/runtime/reward_forge_v0.py` `[branch: forge/dharma-reward-forge-v0]`: deterministic one-task loop closure runner.
- `~/.dharma/knowledge/wiki/concepts/dharma-reward-forge.md` `[off-repo]`: wiki atom summarizing Reward Forge as receipt-backed reality scoring.

## 2. Version History

### Generation 0 - Quality Forge Diagnostic

- `dharma_swarm/quality_forge.py` `[main]`
- Role: scores source artifacts through elegance, behavioral, and telos checks.
- Current status: present on main; useful diagnostic; not a long-run Hydra.

### Generation 1 - Reward Forge v0

- `docs/architecture/DHARMA_REWARD_FORGE.md` `[branch: forge/dharma-reward-forge-v0]`
- `scripts/runtime/reward_forge_v0.py` `[branch: forge/dharma-reward-forge-v0]`
- `tests/test_reward_forge_v0.py` `[branch: forge/dharma-reward-forge-v0]`
- Role: closed sealed holdout loop using DharmaEval, evolution receipt, `FitnessScore.from_external_receipt`, and promotion review.
- Current status: branch-only. The relevant branch is `forge/dharma-reward-forge-v0`.

### Generation 2 - Forge Council v0.1 Chain

- `~/.dharma/autonomy_spine/20260531T172816Z-dharma-reward-forge-v0-1-x-chain-forge-council-v-97f649/mission.json` `[off-repo]`
- `~/.dharma/autonomy_spine/20260531T172816Z-dharma-reward-forge-v0-1-x-chain-forge-council-v-97f649/brief.md` `[off-repo]`
- Role: v0.1.x chain covering live telos gate, transfer gate, inspect sandbox, first external receipt, lineage rollback, deterministic oracle purge, isomorphic perturbation, Goodworks MRV, VentureCell feed, and Karpathy autoresearch seal.
- Current status: open off-repo state mission. Builder evidence exists; some architect heartbeat receipts later no-op due LLM attempt cap.
- Hash: `mission.json` sha256 `e4dc435eb553e80d08b2542a1c184a7ca7ddaaf69e73c37e25e26298608ef61a`.

### Generation 3 - Forge Hydra FQ1

- `~/.dharma/autonomy_spine/20260601T044422Z-forge-hydra-fq1-sealed-reserve-perturbation-gene-d6420f/mission.json` `[off-repo]`
- `~/.dharma/autonomy_spine/20260601T044422Z-forge-hydra-fq1-sealed-reserve-perturbation-gene-d6420f/launch_forge_hydra_fq1.sh` `[off-repo]`
- Role: sealed-reserve perturbation generator; an earlier true Hydra launch using `ds-goal run` with Codex, Opus, and Hermes agents.
- Current status: review. Builder and local verifier completed; 31 focused tests passed. Adversary/reporter lanes were blocked by Hermes timeout and Claude credit.
- Hashes:
  - `mission.json` `[off-repo]` sha256 `72a7838da317260b9c8008d53ffad922c66a3a5ea4759389e9f6281d4b85fe91a`
  - `launch_forge_hydra_fq1.sh` `[off-repo]` sha256 `3075d3cd90af93e7a51d456691726de8d0bf8094ddffe4bd6c811650159c3c47`

### Generation 4 - External Beast / Measurement Guardian

- `~/.dharma/forge_external_beast/codex_overnight_heartbeat.json` `[off-repo]`
- `~/.dharma/forge_external_beast/shared/codex_overnight_handoff.md` `[off-repo]`
- `reports/agentops/work_packets/forge-external-beast-cycle-76.json` `[untracked]`
- `reports/agentops/work_packets/forge-external-beast-cycle-81.json` `[untracked]`
- `~/.dharma/forge_measurement_guardian/codex_overnight_heartbeat.json` `[off-repo]`
- `~/.dharma/forge_measurement_guardian/shared/codex_overnight_handoff.md` `[off-repo]`
- `reports/agentops/work_packets/forge-measurement-guardian-cycle-003.json` `[untracked]`
- Role: external receipt pursuit and independent verifier/countersign path.
- Current status: External Beast reached 82 cycles, but cycle 82 handoff has placeholders; cycle 81 is the last crisp external packet. Measurement Guardian cycle 3 revalidated three confirmed external acted receipts and blocked archive fitness at N=3/M=1.
- Hashes:
  - `~/.dharma/forge_measurement_guardian/cycle-003-fitness-quorum-guard.json` `[off-repo]` sha256 `05036769ac6c72db2196198e20e5a01e0c34099c5b7736179b808ab5f14fac5e`
  - `~/.dharma/forge_measurement_guardian/shared/codex_overnight_handoff.md` `[off-repo]` sha256 `d8a1e8faf8d3a412f3b5c5a476ccb6a5640eb1e73e9e603779b1b9239e8235bb`

### Generation 5 - Forge Reality Arena v0

- `~/.dharma/forge_reality_arena/codex_overnight_heartbeat.json` `[off-repo]`
- `~/.dharma/forge_reality_arena/shared/codex_overnight_handoff.md` `[off-repo]`
- `reports/agentops/work_packets/forge-reality-arena-status.json` `[untracked]`
- Role: local dense arena and status path.
- Current status: four-cycle local arena. Latest v0 heartbeat was 2026-06-02T05:10:34Z; status added failure-capsule learning summaries while keeping fitness zero.

### Generation 6 - Forge Reality Arena v1 Master

- `scripts/runtime/live_ops_census.py` `[main]`
- `~/.dharma/forge_reality_arena_master/codex_overnight_heartbeat.json` `[off-repo]`
- `~/.dharma/forge_reality_arena_master/shared/codex_overnight_handoff.md` `[off-repo]`
- `reports/agentops/work_packets/forge-reality-arena-v1-10h-closeout.json` `[untracked]`
- `reports/agentops/work_packets/forge-reality-arena-master-cycle-50.json` `[untracked]`
- Role: the mission surface now called `Forge Reality Arena Hydra` by the live-ops census.
- Current status: current registered surface, but operationally stopped. Last heartbeat: 2026-06-02T15:52:49Z. Latest stop reason: `internal_packets_exhausted`.
- Hashes:
  - `~/.dharma/forge_reality_arena_master/codex_overnight_heartbeat.json` `[off-repo]` sha256 `ceb63e20da3567bc24385ff29d45d2ae9f193f3d7fe29019d128e71850cae30e`
  - `~/.dharma/forge_reality_arena_master/shared/codex_overnight_handoff.md` `[off-repo]` sha256 `c43114ab4180d2ea2abcfd0d01e5335427449620d61dac9d36fdc6ff15ce07fa`

### Generation 7 - Reality Arena v2 / v3.1 / v4

- `~/.dharma/autonomy_spine/20260603T160201Z-forge-reality-arena-v2-reality-updates-fitness/mission.json` `[off-repo]`
- `~/.dharma/autonomy_spine/20260604T144328Z-forge-reality-arena-v3-1-swarm-benchmark-spine/mission.json` `[off-repo]`
- `~/.dharma/autonomy_spine/20260604T145000Z-forge-reality-arena-v3-1-8h-soak/receipts.jsonl` `[off-repo]`
- `~/.dharma/autonomy_spine/20260605T063423Z-forge-v31-real-benchmark-learning-loop/receipts.jsonl` `[off-repo]`
- `~/.dharma/autonomy_spine/forge-v4-continuous-transfer-20260605/receipts.jsonl` `[off-repo]`
- Role: evolution from status gym to benchmark spine, soak runs, real Harbor benchmark attempts, and clean transfer loops.
- Current status: mostly off-repo state. v2 and v3.1 are marked complete in mission state. v3.1 soak has 962 receipts. v3.1 real benchmark and v4 continuous-transfer were active state when read, but private/no-authority and mostly negative/blocked evidence.

### Generation 8 - Swarm Evolution Arena Measurement

- `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_10H_LAUNCH.md` `[untracked]`
- `scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py` `[untracked]`
- `scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py` `[untracked]`
- `scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py` `[untracked]`
- `tests/test_forge_swarm_evolution_arena_v0_measurement_runner.py` `[untracked]`
- Role: measurement successor focused on matched-budget swarm lift over best-single and same-budget Self-MoA.
- Current status: local/untracked measurement lane; not on main.

### Generation 9 - CashClaw Revenue Hydra

- `~/dharma_swarm_cashclaw/scripts/revenue/cashclaw_revenue_hydra.py` `[branch: cashclaw/revenue-hydra-v1]`
- `~/dharma_swarm_cashclaw/dharma_swarm/revenue/` `[branch: cashclaw/revenue-hydra-v1]`
- `docs/plans/2026-06-01-cashclaw-hydra-v2-pitstop-spec.md` `[branch: cashclaw/revenue-hydra-v1]`
- Role: sibling revenue hydra, not the Forge Reality Arena Hydra. Dry-run, lease-gated, external-action blocked until exact operator approval phrase.
- Current status: branch-only. Test receipt in local audit: `tests/test_cashclaw_revenue_hydra.py` 21 passed.

## 3. Missing Launcher and Actual Heartbeat / Handoff Locations

Declared by live-ops census:

- `scripts/runtime/live_ops_census.py` `[main]`
- Surface id: `mission.forge_reality_arena`
- Label: `Forge Reality Arena Hydra`
- Process key: `forge_hydra`
- Process regex: `codex_overnight_autopilot\.py|forge-reality-arena-master`
- Evidence paths:
  - `~/.dharma/forge_reality_arena_master/codex_overnight_heartbeat.json` `[off-repo]`
  - `~/.dharma/forge_reality_arena_master/shared/codex_overnight_handoff.md` `[off-repo]`
- Restart command: `scripts/start_forge_hydra_long_run.sh` `[missing]`

Searched missing companion commands:

- `scripts/start_forge_hydra_long_run.sh` `[missing]`
- `scripts/status_forge_hydra_long_run.sh` `[missing]`
- `scripts/stop_forge_hydra_long_run.sh` `[missing]`

Closest real launcher:

- `scripts/start_codex_overnight_tmux.sh` `[main]`
- `scripts/codex_overnight_autopilot.py` `[main]`
- `docs/plans/CODEX_ALLNIGHT_YOLO.md` `[main]`

Older real Hydra launcher:

- `~/.dharma/autonomy_spine/20260601T044422Z-forge-hydra-fq1-sealed-reserve-perturbation-gene-d6420f/launch_forge_hydra_fq1.sh` `[off-repo]`

AGNI/VPS check:

- SSH to `agni` responded as host `agni-openclaw`.
- Search under remote `~/.dharma` for Forge/Hydra/Codex overnight state returned no Forge/Hydra files.
- `~/.dharma/salvage/agni_vps_2026-06-11/content/forge_new/ore_bank.jsonl` `[off-repo]` exists locally as an AGNI salvage artifact, but it does not appear to be the Reality Arena launcher/state.

## 4. Relationship to Overnight Autopilot, Reality Arena, and Venture-Cell Gauntlet

Overnight autopilot is the harness:

- `scripts/codex_overnight_autopilot.py` `[main]`
- `scripts/start_codex_overnight_tmux.sh` `[main]`

Reality Arena is the internal dense gym/status/benchmark lane:

- `~/.dharma/forge_reality_arena/shared/codex_overnight_handoff.md` `[off-repo]`
- `~/.dharma/forge_reality_arena_master/shared/codex_overnight_handoff.md` `[off-repo]`
- `reports/agentops/work_packets/forge-reality-arena-v3-1-swarm-benchmark-spine.json` `[untracked]`

External Beast and Measurement Guardian are the sparse receipt side:

- `~/.dharma/forge_external_beast/shared/codex_overnight_handoff.md` `[off-repo]`
- `~/.dharma/forge_measurement_guardian/shared/codex_overnight_handoff.md` `[off-repo]`
- `reports/agentops/work_packets/forge-external-beast-cycle-81.json` `[untracked]`
- `reports/agentops/work_packets/forge-measurement-guardian-cycle-003.json` `[untracked]`

Venture-cell gauntlet is adjacent metabolism:

- `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` `[main]`
- `reports/anatomy_altitude_2026-06-10/lane_A_economic.md` `[untracked]`
- `~/dharma_swarm_cashclaw/scripts/revenue/cashclaw_revenue_hydra.py` `[branch: cashclaw/revenue-hydra-v1]`

Interpretation: Hydra is not one code file. It is a mission pattern binding the generic overnight harness, ds-goal/autonomy-spine ledgers, local dense Reality Arena, and external receipt verifier loops. The crucial safety invariant is that dense/internal artifacts are not archive-fitness authority. Only external acted receipts, countersigned and quorum-satisfying, should be allowed to touch fitness.

## 5. Is It Main-Bound?

Not wholesale. The current main-bound extraction should be narrow:

1. Fix `scripts/runtime/live_ops_census.py` `[main]` so the restart command points to a real launcher, or add a tiny `scripts/start_forge_hydra_long_run.sh` `[missing]` wrapper that uses the existing `scripts/start_codex_overnight_tmux.sh` `[main]` machinery.
2. The wrapper must read `~/.dharma/forge_reality_arena_master/shared/codex_overnight_handoff.md` `[off-repo]` before restart, because the stop policy says `restart-only-after-reading-latest-handoff`.
3. Commit a compact status/custody doc or generated machine-readable status, not the entire `~/.dharma` log tree.
4. Promote only small receipt artifacts if needed:
   - `reports/agentops/work_packets/forge-reality-arena-master-cycle-50.json` `[untracked]`
   - `reports/agentops/work_packets/forge-measurement-guardian-cycle-003.json` `[untracked]`
5. Treat `docs/plans/2026-06-10-honest-spine-v2-decision-memo.md` `[untracked]` as the strategic successor: implement the One Wire from Guardian-confirmed external receipts to archive boundary, with quorum and dry-run behavior.
6. Keep CashClaw Revenue Hydra branch-only until its lease-gated external action path and governance dock are intentionally merged.

Do not import the off-repo Hydra state as a giant source tree. The value is in the contract: live surface, state paths, honest stop reason, receipt boundary, and next extraction.

## 6. Best Run Receipts

### Best Internal Receipt

- `~/.dharma/forge_reality_arena_master/shared/codex_overnight_handoff.md` `[off-repo]`
- `reports/agentops/work_packets/forge-reality-arena-master-cycle-50.json` `[untracked]`

Summary:

- Latest v1 master run reached cycle 13 and stopped at `internal_packets_exhausted`.
- Status emitted `stop_internal_autonomy_cycles`.
- Score: `100/100`.
- Remaining internal packets: 0.
- External/fitness authority untouched.
- Master cycle 50 later confirmed: 500 dense reps, 500 coordination episodes, 25 unique scenarios, 24 failure capsules, Docker smoke passed, benchmark adapter verified, 470 transfer-gated human-review candidates, 0 authority violations, 0 buildable internal packets, 0 fitness-eligible receipts.

### Best External Verifier Receipt

- `~/.dharma/forge_measurement_guardian/shared/codex_overnight_handoff.md` `[off-repo]`
- `reports/agentops/work_packets/forge-measurement-guardian-cycle-003.json` `[untracked]`

Summary:

- Measurement Guardian cycle 3 revalidated three confirmed external acted receipts.
- Confirmed receipt count: 3.
- Quality-stratified receipt count: 3.
- Domain count: 1.
- v1 external threshold ready: false.
- Archive fitness changed: false.
- Fitness authority granted: false.
- Blocker: archive fitness intentionally blocked pending N >= 5 confirmed receipts, M >= 3 domains, and transfer-aware gate execution.

### Best External Beast Packet

- `reports/agentops/work_packets/forge-external-beast-cycle-81.json` `[untracked]`

Summary:

- Objective: move Dharma Reward Forge toward a real external acted receipt via a bounded public GitHub contribution.
- Opened `stellarkit-lab-devtools/stellarkit-api#223` after readiness passed.
- PR open/non-draft; no external maintainer action at the time of receipt.
- Local receipt guard passed; fitness boundary dry-run refused as expected.
- Some target repo full tests failed due unrelated baseline failures.

## 7. Devin Action Handoff

Remote Devin should not try to restart Hydra from this doc. Suggested next work, in priority order:

1. Read `scripts/runtime/live_ops_census.py` `[main]` and patch only the stale restart command contract.
2. Add or point to a real launcher using `scripts/start_codex_overnight_tmux.sh` `[main]`.
3. Preserve the stop policy: read latest handoff before restart.
4. Add a tiny test around the Forge live-ops surface so it cannot point to a missing command again.
5. If asked to promote receipts, start with `reports/agentops/work_packets/forge-measurement-guardian-cycle-003.json` `[untracked]` and `reports/agentops/work_packets/forge-reality-arena-master-cycle-50.json` `[untracked]`, not the whole packet pile.
6. If asked to build the successor, implement the One Wire, not more Hydra churn: Guardian-confirmed external receipt -> transfer gate -> archive boundary -> dry-run below quorum.

## 8. Important Negative Findings

- `scripts/start_forge_hydra_long_run.sh` `[missing]` was not found in `origin/main`, current branch, sibling worktrees checked, local `.dharma`, or AGNI `~/.dharma`.
- `scripts/status_forge_hydra_long_run.sh` `[missing]` and `scripts/stop_forge_hydra_long_run.sh` `[missing]` are also absent.
- `docs/specs/forge_packets/FORGE_REALITY_ARENA_HYDRA_MASTER_SPEC.md` `[missing]` and `docs/specs/forge_packets/FORGE_REALITY_ARENA_V1_10H_MASTER_GOAL.md` `[missing]` are referenced by off-repo state but were not present in the current checkout.
- `scripts/runtime/forge_reality_arena_status.py` `[missing]`, `scripts/runtime/forge_hydra_status.py` `[missing]`, `scripts/runtime/forge_github_receipt.py` `[missing]`, `scripts/runtime/forge_fitness_boundary_dry_run.py` `[missing]`, and `scripts/runtime/forge_reality_arena_authority_scan.py` `[missing]` are referenced by handoffs/receipts but not present in the current checkout.
- `reports/forge/` `[missing in current checkout]` is cited by older handoffs, but was not present in the current worktree. A separate `/Users/dhyana/reports/forge/...` `[off-repo]` strategy prompt directory exists, but it is not the same as repo-local `reports/forge`.

## 9. Bottom Line

The live-ops census is telling the truth about a mission surface but lying by implication about restartability. The mission exists as state and receipts, not as a currently runnable main-owned surface. Its best contribution is the honest stop condition: internal Forge/Reality Arena proof chains exhausted; external receipts exist but do not meet quorum; archive fitness must remain blocked. The next useful patch is a small custody-safe launcher/status correction and a test, followed by the One Wire.
