# Fleet-State Resurvey — 2026-06-12 ~01:40 JST

**Surveyor:** fable_5_cursor (hub coordinator session)
**Baseline:** 2026-06-11 ~14:00 JST survey
**Mode:** read-only (this file is the only write)

---

## Headline

**The June-10 merge order is fully stalled — zero of #561/#562/#567/#564/#568 merged — while a parallel Devin loop-closure campaign merged 8 OTHER PRs (NORTH_STAR v2, orientation wire-in, loop-closure dossier) and re-dirtied the whole queue via DocOps counter drift.** qwen/spine-adoption WAS pushed and got PR #574, but it's CONFLICTING. GATE-1 witness still not run. A2A has been silent for ~11h; an unread peer-holon critique request addressed to fable_5_cursor sits at seq 8,106,906 with no consumer to receive it. ESCALATION-3 (settle-ledger lock) is resolved. Our critique to perplexity-computer was never pushed to origin — the counterparty likely cannot read it.

---

## 1. PR board

### Merged since baseline (8 PRs — none from the established order)

| PR | Merged (UTC) | What |
|---|---|---|
| #565 | 06-11 00:29 | Devin response to honest-spine-v2 critique |
| #566 | 06-11 00:30 | `a2a_send.py` operator surface |
| #572 | 06-11 12:28 | swarm genome convergence report |
| #549 | 06-11 13:06 | vibe-code hygiene catalogue + onboard wire-in |
| #570 | 06-11 15:35 | **NORTH_STAR v2** — locked-in operator vision |
| #575 | 06-11 15:56 | **loop-closure Phase 0 dossier + loop-closure-2026-06 track** (PR-zero of 13-loop campaign) |
| #569 | 06-11 16:09 | Devin session registration + Fable 5 master prompt |
| #573 | 06-11 16:10 | orientation wire-in (onboard WHY section, venv-aware Makefile) |

(Evidence: `gh pr list --state merged --search "merged:>2026-06-10"` + `git log origin/main`.)

### The established merge order — ALL STALLED

| PR | State | Blocker |
|---|---|---|
| #561 provider-honesty-g6 | OPEN, MERGEABLE but **BLOCKED** | **Coherence Delta PR body check FAILING** (run 27361029790); all other checks pass; no review decision |
| #562 evolution-archive-honesty | OPEN, **CONFLICTING DIRTY** | DocOps counter drift from the 8 merges above |
| #567 pr-mike make targets | OPEN, CONFLICTING | same |
| #564 Devin honest-spine handoff | OPEN, CONFLICTING | same |
| #568 A2A retention proposal | OPEN, CONFLICTING | same |
| #574 qwen/spine-adoption (NEW) | OPEN, **CONFLICTING DIRTY** | same |

Per `SEAT_REBASE_PREVIEW_2026-06-11.md` (dharma_swarm_live, untracked): **all inter-lane conflicts are generated-file counter drift** (`docs/docops/AUTO_INVENTORY.md`, `docs/governance/SOVEREIGN_MANIFEST.md`) — zero Python conflicts between #561, #562, spine-adoption, and the seat slices; 351 targeted tests pass on the dry-run integrated tree.

### New PRs since baseline

- **#574** [operator] `qwen/spine-adoption` — the spine lane now has a PR (created 06-11 14:54 UTC). CONFLICTING.
- **#576** [operator] DocOps TTL renewal 2026-06-12. MERGEABLE.
- **#577** [Devin] provider hardening Phase 1a (rate-limit/quota/billing failure classes). MERGEABLE.
- **#578** [operator] trust-gate scoreboard (NORTH_STAR §8 in onboard). CONFLICTING.
- **#579** [Devin] **make Coherence Delta gate malleable in form, strict in substance** — directly relevant to #561's blocker. MERGEABLE.
- **#571** automated spine-adoption metric refresh.

### Devin 13:00 UTC janitor

**No evidence it fired.** Last Devin comments on #567/#568: 06-11 01:51–02:33 UTC. No janitor workflow runs near 13:00 UTC. Devin's activity instead came 15:35–16:33 UTC via the loop-closure campaign (#570/#573/#575 merged; #577/#579 opened).

---

## 2. Spine lane (qwen/spine-adoption)

- **Pushed: YES.** origin tip `aecd81001` ("merge: main into qwen/spine-adoption", 06-11 16:03 UTC) — main (incl. NORTH_STAR v2, loop-closure track) merged into the branch. PR #574 opened. Local workspace (`~/dharma_swarm`) is **behind 11** on this branch.
- **GATE-1: NOT witnessed.** `reports/governance/GATE1_WITNESSED.md` MISSING (track criteria `gate1_witnessed ✗`); only the script `scripts/governance/gate1_witness.sh` exists in the tree.
- **Track status** (reports/governance/active_track_evidence.md, last committed 06-09 — slightly stale): spine-adoption **5/8 criteria** (also failing: `bypass_allowlist_empty`). Three other tracks read **SHIPPABLE**: reconciliation (11/11), NATS (2/2), composer-holon (6/6) — close-out decisions pending operator.

## 3. Seat lane (~/dharma_swarm_live, organ/03-seat)

- **No new commits** past `e67b91829`. Seat/wounds PRs NOT opened.
- **NEW artifact:** `reports/handoffs/SEAT_REBASE_PREVIEW_2026-06-11.md` (untracked) — full dry-run: zero real code conflicts onto future-main, split plan ready. The lane is **merge-ready the moment the queue ahead clears**.
- **ESCALATION-3: RESOLVED.** Old cron daemon PID 77950 gone. New daemon PID 85814 (started 06-12 01:08:57 JST, `com.dharma.cron-daemon`, `dgc cron daemon`). The editable install maps `dharma_swarm` → `/Users/dhyana/dharma_swarm_main`, which **now contains the busy_timeout fix** (task_board.py, agent_memory_manager.py, message_bus.py). Last `database is locked` error: **06-11 09:09 JST** — none in ~16h.

## 4. A2A

- **Stream:** DHARMA_A2A last_seq **8,106,907** (+7 from baseline 8,106,900); last message **06-11 05:46:33 UTC (14:46 JST)** — **zero traffic in ~11 hours**.
- **The 7 new messages:** a2a_send context-patch probe to Devin + acks (seqs 8,106,901–903), then a 4-way **codex_composer peer-holon broadcast** at 05:46 UTC to fable_composer / hermes-m5 / **fable_5_cursor** / devin (seqs 8,106,904–907).
- **Inbound for fable_5_cursor (seq 8,106,906): UNREAD.** Codex Composer requests a holon-context review ("reply with disagreement, missing evidence, next seam, verifier"; authority: critique-only). Packet: `~/.dharma/a2a_bus/collab/convergence/PEER_HOLON_CONTEXT_PACKET_20260611T054237Z.md`. **No fable_5_cursor consumer exists** (consumer ls: 10 consumers, none ours).
- **merge_master_mike_inbox:** 30 pending, still never pulled (unchanged). **devin_inbox:** 10 unprocessed, never delivered.
- **nats-a2a-bridge:** `com.dhyana.nats-a2a-bridge` not running, last exit 1 — revive-or-remove still undone.
- **perplexity-computer reply: NONE — and a worse finding:** honest-spine-v2 worktree is still at `7ef5668cc` but the branch is **ahead 13 of origin** — our critique (and the whole receipt-grammar packet chain) **was never pushed**. Unless delivered out-of-band, perplexity-computer has no path to read our reply.

## 5. Hygiene drift

- **DocOps counter contention confirmed and worsened:** the 8 merges flipped essentially every queue PR to CONFLICTING. The contention is exactly the generated-counter problem the baseline predicted ("DocOps refresh between" serialized merges never happened).
- Feedback packets: spine-adoption lane partially acted on its packet (pushed, merged main, opened #574). #568's retention-fuse warning unaddressed (PR conflicting).
- Operator to-dos still pending: `DEVIN_NATS_URL/USER/PW` and `DEVIN_WEBHOOK_URL/SECRET` **absent from agent_keys.env** (name-presence check only, count=0).

## 6. Worktree / branch news

New worktrees since baseline: `dharma_helm_build` (helm/worldclass-20260612), `dharma_swarm_cashclaw` (cashclaw/revenue-hydra-v1), `dharma_swarm_governed_memory_recursive_integration`, `dharma_swarm_opus_traverse`, `dharma_swarm_pr_review_control` (hygiene-lifecycle-v2), `ds_docops_renewal` (→#576), `ds_stitch_receipts`, `ds_trust_gate` (→#578).

**Live activity at survey time:** four branches pushed 01:08–01:28 JST 06-12 (feat/governed-recursive-proof-tightening, opus/traverse-fix-20260605, chore/governance/hygiene-lifecycle-v2, feat/trust-gate-scoreboard) and the cron daemon restarted 01:08:57 — at least one other agent session is active right now. Coordinate before touching those lanes.

---

## TOP 3 ROI actions (evidence-ranked)

### 1. Unstick the merge queue — DocOps-counter conflict sweep + #561 body fix

- **Why now:** Every lane (the June-10 order, #574 spine, the seat split behind it) is blocked on ONE mechanical cause: generated-counter drift plus #561's failing Coherence Delta *body* check. The rebase preview proves zero code conflicts exist. Every hour the queue sits, new merges (#577/#579 are MERGEABLE Devin PRs) re-dirty it again. Note the sequencing option: #579 *is* a fix to the very gate failing #561 — merging #579 first may make the #561 body fix trivial.
- **Who:** Delegable worker for the mechanics (fix #561 PR body to pass Coherence Delta; rebase #562→#567→#574 with DocOps regen between each, per the preview's order). Actual merges remain operator/Mike-gated per authority boundary.
- **Payoff:** Re-opens the entire integration pipeline: #561/#562 land honest-spine, #574 lands the spine-adoption lane (incl. fable_5_cursor registration commit), and the seat lane's prepared two-PR split becomes immediately actionable. Highest leverage by far.

### 2. Stand up fable_5_cursor's AGNI consumer and answer the codex_composer critique request (+ drain mike's 30)

- **Why now:** An 11-hour-old direct request to this coordinator (seq 8,106,906) is rotting unread because the consumer was never created — the hub is registered but deaf. mike_inbox's 30 pending have never been pulled since 06-01. This is the cheapest credibility/loop-closure win on the board.
- **Who:** Consumer creation needs AGNI NATS credentials — operator (or hub session holding the agni-wss context, which works read-only today; creating a durable consumer is one command). The critique reply itself is fully delegable (authority is critique-only, no source writes).
- **Payoff:** Hub coordinator becomes bidirectional; the composer convergence round unblocks; the 30-message Mike backlog stops being dark matter. ~1 hour of work.

### 3. Publish the perplexity-computer correspondence — push honest-spine-v2 (or resend via A2A)

- **Why now:** The fleet-correspondence loop silently broke: our reply `7ef5668cc` (plus 12 more commits: receipt-grammar ruling, Phase A packet, subtraction work) exists only locally. From perplexity-computer's side we look unresponsive; from ours the loop looks "awaiting reply". Neither is true.
- **Who:** Operator-only for the push (hub authority excludes push). A worker can pre-flight (verify branch state, draft the A2A notification packet via the now-merged `a2a_send.py`).
- **Payoff:** Restores the external-counterparty loop, and lands 13 commits of receipt-grammar/subtraction work where the fleet can build on it.

**Deferred (explicitly):** lane-collision-sentinel build (G1/G2) — justified by today's evidence (the queue collision happened AGAIN), but unsticking the current collision beats building the sentinel tonight; queue it as the follow-up after rec 1. VWRITE KEY DAY prep and the seat split wait behind rec 1. AGNI subscribe user is folded into rec 2.

## Urgent breakage

- **None catastrophic.** ESCALATION-3 resolved (verified: fix present in the imported tree, no lock errors in 16h).
- Lingering: `com.dhyana.nats-a2a-bridge` still dead (exit 1) — decide revive-or-remove; Devin webhook/NATS keys still not in dkeys; devin_inbox consumer shows "never delivered" with 10 unprocessed (verify Devin's listener is actually pulling from it before assuming delivery).
