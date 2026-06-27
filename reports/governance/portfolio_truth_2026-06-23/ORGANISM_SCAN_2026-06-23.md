# Organism Scan — DGM Reconciliation / Latent Gold Scan (2026-06-23)

## Authority and scope

This report is a **read-only synthesis** for the now-live DGM substrate. It is not a new source of truth. It projects over Git, worktrees, stashes, existing governance reports, preservation packets, `.dharma` metadata, and current local probes.

Canonical baseline used here:

- `origin/main`: `4137e83c3d0e6fb18a9182d3842c6a34b77a585c`
- On-main state: Arena v1 / Council / zero-weight orchestrator has landed.
- Canonical `ACTIVE_TRACK.yaml`: 7 active tracks / max 10.
- Canonical objective coverage: `0.33` because current active tracks serve only `substrate-nativeness`; `revenue-external-humans-served` and `research-depth` are uncovered.
- Primary dirty checkout: `/Users/dhyana/dharma_swarm`, branch `telos-ai-seed-v0-from-sandbox`, 211 dirty porcelain entries.
- Current auth correction: the checkpoint said GitHub auth was down, but a fresh read-only `gh auth status` probe in this session showed GitHub auth is available. Promotion still requires operator approval.
- `.dharma/STOP_BUILD`: present with `Test regression at 2026-05-30T22:40:52.959006`.

Safety line: no branch refs, stashes, worktrees, PRs, `ACTIVE_TRACK.yaml`, or `.dharma` storage objects were modified.

## Working notes / evidence probes

Read-only probes used in this synthesis:

```bash
git -C /Users/dhyana/dharma_swarm rev-parse origin/main
# 4137e83c3d0e6fb18a9182d3842c6a34b77a585c

git -C /Users/dhyana/dharma_swarm status --porcelain | wc -l
# 211

git -C /Users/dhyana/dharma_swarm stash list | wc -l
# 70

git -C /Users/dhyana/dharma_swarm branch --format='%(refname:short)' | wc -l
# 208

git -C /Users/dhyana/dharma_swarm worktree list | wc -l
# 13

gh auth status
# currently authenticated for GitHub in this session

gh pr list --repo AmitabhainArunachala/dharma_swarm --state open --limit 30
# 9 open PRs observed
```

Reused read-only scout outputs:

- Branch Archaeologist: 208 branches classified; top latent gold list produced.
- Worktree+Sibling Scout: project cards for Forge, Supply Chain, A2A/NATS, Helm, CashClaw, Chetana, Capital, and empty sibling dirs.
- Off-Repo/.dharma Evidence Scout: metadata-only registry and storage-risk report.
- Theme/Track Mapper: find-to-theme and successor-track proposals.
- Dirty+Stash Miner: final output was not available; this report uses branch/stash list, preservation packets, and dirty porcelain clusters with uncertainty explicitly marked.

## Executive summary

The machine is not empty chaos; it is an overfull portfolio with high-value candidates mixed with dirty overlays, local-only branches, stashes, stale duplicate refs, and large off-repo storage objects. DGM/Arena can evolve only if it consumes clean packets, not raw machine state.

Current truth split:

| Layer | State |
|---|---|
| Canonical origin/main | `4137e83c3d0e6fb18a9182d3842c6a34b77a585c`; Arena v1/Council/orchestrator landed; 7 active tracks / max 10. |
| Dirty candidate checkout | 211 dirty entries on `telos-ai-seed-v0-from-sandbox`; contains high-priority cockpit work but is not canonical. |
| Branch portfolio | 208 local branches; 21 already-on-main, 21 local-only valuable, 9 unpushed-ahead, 62 stale duplicates, 38 orphaned-upstream-gone, 57 needs operator decision. |
| Stashes | 70; locally preserved as patches/refs, but off-machine preservation is still uncertain. |
| Worktrees | 13 currently observed; several are high-value candidate lanes, several are dirty. |
| PR queue | 9 open PRs observed; auth currently available for read-only triage. |
| Storage | `.dharma` is 344G; storage policy needed, not a cleanup swarm. |
| Safety sentinel | STOP_BUILD still present; treat as unresolved until explicitly cleared by verification. |

## Highest-ROI promotions

1. **Canonicalize Operator Coherence Cockpit**  
   Candidate: `operator-coherence-cockpit-control-tower-2026-06`  
   Why: it is the control tower that lets every other lane be seen, classified, preserved, and promoted without mixing dirty/local truth with canonical truth.  
   Gate: clean extraction branch, JSON/report validation, dashboard build/lint, explicit canonicality labels.

2. **Admit Orchestration Arena v1 to governance**  
   Candidate: `orchestration-arena-v1-2026-06`  
   Why: #670 landed on main, but the active-track portfolio has not caught up. DGM must know its own substrate exists.  
   Gate: frozen task battery, zero-weight genome schema, Council trace receipts, best-single-model controls.

3. **Open one narrow revenue lane**  
   Candidate: `revenue-external-human-receipt-2026-06`  
   Why: fixes the portfolio's revenue objective gap.  
   Gate: one external-human action or cash receipt, not just more revenue infrastructure.

4. **Open one narrow research-depth lane**  
   Candidate: `research-depth-verified-sensemaking-2026-06`  
   Why: fixes the portfolio's research-depth objective gap.  
   Gate: source ingest → claim extraction → decorrelated verification → paper-grade claim packet.

5. **Port Forge V1 scoreboard as an Arena arm**  
   Candidate source: `/Users/dhyana/ds_forge_v1_scoreboard`, branch `forge-v1/tokenbroker-scoreboard-20260620`  
   Why: clean local-only high-signal Arena/scoreboard work.  
   Gate: off-machine preservation first, then port as experiment; do not make it fitness authority immediately.

## Already-on-main

Important already-on-main findings:

- #670 coordination/council/arena substrate is on-main at `4137e83c3d0e6fb18a9182d3842c6a34b77a585c`.
- #663 Chetana MarkItDown ingest is on-main at `4137e83c3d0e6fb18a9182d3842c6a34b77a585c`.
- 21 local branches were classified as already represented on `origin/main` by direct tip or cherry-equivalence.

Action: keep them as history unless ref hygiene is explicitly requested. Any ref retirement should be **archive-after-preserve after off-machine preservation + operator approval**.

## Preserve-as-candidate

High-value candidate work that should be preserved and reviewed, not raw-promoted:

| Candidate | Canonicality | Why preserve |
|---|---|---|
| `/Users/dhyana/dharma_swarm` cockpit/backplane overlay | dirty | High-priority cockpit implementation and V2 UI work; not canonical. |
| `/Users/dhyana/ds_forge_v1_scoreboard` | local-only | Clean Forge/Arena scoreboard candidate. |
| `/Users/dhyana/ds_supplychain_slice` | local-only | Single unmerged Bronze/frontier-council residue after #648 mostly landed. |
| `/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618` | dirty | Useful A2A/NATS topology/probe material. |
| `/Users/dhyana/dharma_swarm_cashclaw` | dirty | Primary revenue candidate, but current cash proof is not sufficient. |
| `lane/palantir-pilot`, `research/persistent-agents-2026-05`, `research/moltbook-investigation` | local-only | Research-depth candidates. |
| Stashes `stash@{8}`, `stash@{31}`, `stash@{32}`, `stash@{61}` | stash | Telos/cockpit, persistent-agents, and Chetana high-signal clusters. |

## Fold-into-active-theme

| Theme | Fold candidates | Recommendation |
|---|---|---|
| Runtime Truth Spine | #674 closure rigor, dirty runtime closeout/burn-in/audit files | Fold only after isolated extraction and fresh runtime DB receipt snapshot. |
| A2A/NATS | `ds_a2a_nats_rebuild_preflight_20260618`, dirty A2A launchd/inbox bridge material | Keep active; require live JetStream/NATS ack proof. |
| Provider Routing | #675 provider discoverability, `fix/provider-honesty-g6` | Review PR head separately from local overlay; require live-provider canary/egress proof for closeout. |
| Bronze/Ingest | `ds_supplychain_slice`, #663 Chetana MarkItDown, mined #662 pieces | Build a durable read-only throat consumer; no dispatch authority. |
| Holons | composer-holon active track, dirty Holon L4, `organ/03-seat` | Split Build A readiness from standing Holon L4 production proof. |
| Operator Coherence | cockpit dirty checkout, lane admission schemas, prod-readiness packets | Successor/control-tower track, not hidden inside runtime truth. |

## Latent gold / surprises

- The biggest strategic surprise is that **GitHub auth is now available** in this session, so read-only PR triage can proceed immediately; promotion still remains operator-gated.
- The second surprise is that the **Arena substrate is already on-main** but invisible to active-track governance.
- `cashclaw/revenue-hydra-v1` is the strongest revenue candidate, but it must not be overclaimed because current proof still reports no cash earned.
- `lane/palantir-pilot` and research branches can directly repair the research-depth gap if converted into verified claim packets.
- `ds_supplychain_slice` likely contains the closest observed Bronze throat consumer residue.
- `.dharma/preservation/dgm_reconciliation_20260622` is valuable local safety evidence, but not proof of off-machine safety.

## Archive-after-preserve candidates

These are lower-priority after preservation, not immediate action items:

- 62 stale-duplicate branch refs.
- Backlog/salvage/restack branches already represented on main or superseded.
- Empty sibling dirs: `dharma_swarm_integrate_chetana`, `dharma_swarm_lf5_operator`, `dharma_swarm_dashboard_skill_worktree`; value, if any, is likely in stashes or related PRs.
- Draft ops-report PR family after supersession policy is approved.
- Old UI/terminal stash experiments unless cockpit V2 has a specific gap.

Required phrase for any such action: **archive-after-preserve after off-machine preservation + operator approval**.

## Blocked by auth / preservation / approval

- Auth is no longer the immediate read-only blocker in this session, but any push/merge/promotion still needs explicit operator approval.
- Off-machine preservation remains unproven from local evidence alone.
- STOP_BUILD sentinel remains unresolved.
- Dirty+Stash Miner final output was unavailable, so stash triage remains partial.
- Production-grade closure cannot be inferred from checker-green file gates alone.

## Disk/storage risks

Storage is a policy issue, not a cleanup swarm.

| Area | Size | Handling |
|---|---:|---|
| `/Users/dhyana/.dharma` total | 344G | Preserve/policy first. |
| `.dharma/lancedb` | 243G | Storage object only; do not open/compact in reconciliation. |
| `.dharma/vectors.db` | ~49G | Storage object only; recently modified. |
| `.dharma/conversation_log` | 31G | Large corpus; metadata-only handling. |
| `.dharma/forge_external_beast` | 4.9G | Not fully tar-preserved; preserve before mining. |

Filesystem capacity observed by scout: 1.8Ti volume, 961Gi used, 875Gi available, 53% capacity. No immediate disk emergency was observed.

## Next 10 actions

1. Confirm off-machine preservation path for the existing preservation packet and high-value dirty overlays.
2. Extract cockpit to `governance/operator-coherence-cockpit-20260623` and rerun its verification.
3. Admit `orchestration-arena-v1-2026-06` as a governance-visible successor track.
4. Triage PR #675 provider discoverability separately from local dirty overlay.
5. Triage PR #674 closure gate and reconcile overlap with any tracks-consolidation grading branch.
6. Diff `ds_supplychain_slice` local tip `11de04f` and port only unique Bronze throat value.
7. Preserve and port `ds_forge_v1_scoreboard` as a controlled Arena experiment.
8. Draft `revenue-external-human-receipt-2026-06` with one real external-human/cash receipt gate.
9. Draft `research-depth-verified-sensemaking-2026-06` with one claim-verification packet gate.
10. Add STOP_BUILD sentinel and storage-object policy cards to the cockpit so DGM cannot learn from hidden unsafe state.

## Uncertainties

- Dirty+Stash Miner final result was not available; stash classification is partial.
- Some branch and PR relations may have changed since earlier scout outputs; current PR list was read-only checked, but no PR checks were executed.
- Off-machine preservation remains unproven.
- `.dharma` storage contents were not opened.
- Dirty `ACTIVE_TRACK.yaml` in the candidate checkout is not canonical and must not be raw-unioned into main.
