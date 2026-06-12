# A2A Devin/Mike PR Reconciliation — 2026-06-11

Role: report (dated descriptive output). Not authority.
Author: cursor_fable_subagent, 2026-06-11 09:45 JST.
Task: (A) attempt delivery of a #564/#565 reconciliation job through the A2A
system and honestly assess transport; (B) reconcile the PRs myself if no pickup.

---

## (i) A2A transport assessment

**Verdict: PARTIAL — publish side WORKS, consume side DEAD. No pickup; Part B executed locally.**

### Route tried (canonical, per `docs/ops/DEVIN_NATS_PR_JANITOR_PLAYBOOK.md`)

AGNI NATS `wss://157.245.193.15:8443`, local context `agni-wss` (user `trishula`,
CA `~/.dharma/nats/agni-ws-ca.pem`), JetStream stream `DHARMA_A2A`, subjects
`dharma.a2a.merge_master_mike` and `dharma.a2a.devin`.

### Evidence

| Check | Result |
|---|---|
| Broker reachable | YES — `stream ls` answered in ~3s; `DHARMA_A2A` last message 5m old |
| Publish ack-verified | YES — packet `reconcile-564-565-20260611` stored at stream seq **8,106,879** (mike) and **8,106,880** (devin), 09:30:55–57 JST |
| `merge_master_mike_inbox` consumer | DEAD — Last Delivered = stream seq **41** (consumer seq 1, ~2026-06-01). Unprocessed went 29 → **30** (my packet landed, nothing pulled it) |
| `devin_inbox` consumer | DEAD — Last Delivered = stream seq **188** (~2026-06-01). No movement over the poll window |
| Reply on `dharma.a2a.claude` / `devin.reply.*` | NONE during window (09:30–09:43 JST, 3 polls) |
| `make pr-mike` | does **not exist** in the Makefile (AGENTS.md mentions it; only `pr-queue/pr-packet/pr-gate/pr-reviewers/pr-run-*/pr-merge` exist) |

**Specific failure point:** there is no standing consumer process on AGNI for the
Mike/Devin inboxes. Devin/Mike only attach to NATS during GitHub-Actions backlog
runs or Devin Cloud sessions; between runs, messages accumulate forever
(no consumer has delivered a message since ~June 1). Publishing into
`dharma.a2a.merge_master_mike` is writing to an unread mailbox.

**Side observation (flag for ops):** `dharma.a2a.devin` and `dharma.a2a.fleet`
hold **4,053,343 / 4,053,345 messages** (stream total 8.1M msgs, 1.3 GiB) — a
runaway publisher has been flooding both subjects. The stream has unlimited
retention. This will eventually hurt AGNI disk and consumer restart time.

### Alternate lane: hermes-m5 (filesystem queue)

- Heartbeat **fresh**: state file ticked 08:56 and again 09:28 JST (~30-min cadence);
  `hermes_state_and_queue_tick.py` demonstrably claims queue tasks (3 tasks claimed
  at the 08:56 tick).
- I enqueued task `reconcile-564-565-20260611` to `~/.dharma/a2a_bus/tasks/queue.jsonl`
  at 09:31 JST — *after* the 09:28 tick, so it was still `pending` at the end of my
  window. Expected claim at the ~09:58 tick. This is the only A2A lane with live
  pickup mechanics; reply latency is ≥30 min, outside the timebox.

---

## (ii) Per-PR reconciliation verdicts

Both PRs are **docs-only fleet packets** — no runtime code touched.

### PR #564 — "fleet: add Devin honest-spine handoff packet" (OPEN)

Files: `inter_agent/devin/inbound/2026-06-11T08-10Z-honest-spine-state-and-critique-request.md`
(new, 82 lines) + DocOps count regen in `docs/docops/AUTO_INVENTORY.md` and
`docs/governance/SOVEREIGN_MANIFEST.md`.

**Verdict: SAFE-IGNORE-FOR-NOW** (fold into the docs/hygiene tail when convenient).

- (a) #560 supersede: no effect. The packet describes honest-spine-v2 lane state
  (cites `e6396856c`, `2e7b46394`, `6cf869979`) but is a handoff snapshot, not a
  canonicality claim. **#560 was in fact closed at 2026-06-11T00:26Z** — the
  supersede decision is already executed.
- (b) #562 collision: no effect — prose only.
- (c) Receipt-persistence / archive surfaces: mentioned in prose ("Receipts default
  ON", archive boundary), no code. Note the packet's §2 prose will be partially
  stale once spine-adoption's variant wins, since `2e7b46394` (lane receipts-ON
  commit) is the losing variant — acceptable for an `inter_agent` dated packet.
- (d) Operator decision tonight: none required.
- Current state: **CONFLICTING (DIRTY)** — #565's merge bumped the same DocOps
  count lines (871→872 files). Also one failing check: "Coherence Delta PR body".
  Needs a count rebase + PR-body fix before merge. This is exactly the
  DocOps-counts-cause-100%-of-conflicts failure mode Devin's own response names.

### PR #565 — "fleet(devin): response to honest-spine-v2 critique request" (already **MERGED**)

Files: `inter_agent/devin/outbound/2026-06-11T00-30Z-honest-spine-critique-response.md`
(new, 71 lines) + DocOps count regen.

**Verdict: FOLD-INTO-PLAN (content already in main; two findings matter):**

- (a) #560 supersede: Devin's Q1 answer suggested merge order **561 → 560 → 562 →
  558 → docs/hygiene**, i.e. it assumed #560 merges. It explicitly flagged the
  "lane-branch-vs-slices canonicality decision" as open. That decision has since
  been made the other way (#560 closed, spine-adoption wins). Devin's suggested
  order is **superseded — do not act on it**; the Mike/Devin lane should be told.
- (b) #562 collision: Devin's verification table **confirms** `e6396856c` /
  `2e7b46394` / `6cf869979` are on **no remote ref** (only 4 of 16 lane commits
  pushed). This independently validates the merge-#562-first-then-rebase-
  honest-spine-v2 recommendation. Strengthens the plan, changes nothing.
- (c) Receipt/archive ownership: none claimed; report only.
- (d) Operator decision: none beyond what is already decided.
- Bonus intel worth keeping: live queue is 9 PRs not 38; 8/9 touch DocOps count
  files (expect serial conflict/regen between every merge); cheaper 2-min smoke
  path via pytest-timeout instead of xdist; `make test-smoke`/`test-all` are
  referenced in CLAUDE.md but absent from the Makefile.

---

## (iii) Change to the merge order

**None.** The plan holds: ~~#560~~ (already closed 00:26Z) → **#561 → #562 →
spine series → seat lane**, then rebase honest-spine-v2's fitness-authority layer
on top of #562. Append **#564 to the docs/hygiene tail** after a DocOps-count
rebase and Coherence-Delta body fix. Expect DocOps count conflicts between every
merge in the sequence (8/9 open PRs touch the same two files) — regen counts
after each merge rather than batching.

## (iv) Recommended next action for the Mike/Devin lane (transport is dead at the consumer end)

1. **Don't rely on bare NATS publishes to reach Mike/Devin.** Until a standing
   consumer exists, the working invocations are: `@merge_master_mike` PR mentions
   (`.github/workflows/codex-mention-router.yml`) and **Actions →
   merge-master-mike-backlog → Run workflow** (`mode=packet-only`, per playbook).
   Either will also drain/see the queued NATS packet if the workflow connects.
2. **Tell the lane #560 is closed-superseded** (next backlog run or a PR comment),
   so Devin's 561→560→562 suggestion from #565 isn't replayed.
3. **Ops follow-ups:** (a) runaway publisher on `dharma.a2a.devin`/`dharma.a2a.fleet`
   (4M msgs each, 1.3 GiB, unlimited retention) needs throttling + stream limits;
   (b) AGENTS.md references a nonexistent `make pr-mike` target — fix the doc or
   add the target; (c) hermes-m5 task `reconcile-564-565-20260611` is pending in
   `~/.dharma/a2a_bus/tasks/queue.jsonl` — its eventual reply is a free second
   opinion, harvest or cancel it.

---

## Devin janitor PRs pre-review (2026-06-11)

Role: report (adversarial pre-review, read-only). Author: cursor_fable_subagent, 2026-06-11 ~11:10 JST.
Scope: #567, #568, #564 (all Devin janitor lane, session 6a5df962). Reviewed via `gh pr view/diff` against current origin/main. Neither Devin nor this reviewer merges — verdicts feed the operator's merge agent.

### #567 — `make pr-mike` + `mike-*` Makefile targets — **APPROVE-LEAN**

- Diff is **Makefile-only** (1 file, +25/−1): `.PHONY` line, six `help` lines, six targets. No code surfaces, no governance surfaces, no new files. Claim verified.
- Every target is a verbatim thin wrapper over scripts already on main:
  `pr-mike` → `scripts/runtime/pr_merge_control.py fanout`; `mike-{wake,status,cycle,tmux-start,tmux-stop}` → `scripts/runtime/merge_master_mike_daemon.py <subcmd>`. Both scripts exist on origin/main. Zero new executable logic.
- **Authority boundary verified at the script level:**
  - `fanout` default `--merge-mode off` (merge requires explicit `--merge-mode auto-when-clean` in ARGS, a capability that pre-exists on main and is identically reachable by calling the CLI directly — the Make target adds no escalation).
  - `cycle` choices are `dry-run | packet-only | review` only — **no merge mode exists in the cycle parser**; default `dry-run`. `mike-cycle` cannot trigger merges, period.
  - No approve path anywhere; daemon docstring + charter strings reaffirm "may not approve PRs, push, edit source."
- One honest note (not a blocker): all targets pass `$${ARGS:-}` through verbatim, so `make pr-mike ARGS="--merge-mode auto-when-clean"` reaches Mike's conditional merge authority — same as the raw CLI today. If the operator wants Make to be a dry-run-only surface, that's a follow-up hardening, not a defect of this PR.
- Closes the AGENTS.md/Makefile drift this report flagged in §(iv)(b). Checks green incl. gitleaks. **Merge early.**

### #568 — A2A retention proposal doc + outbound reply packet — **APPROVE-WITH-NOTE**

- Files: retention plan (`docs/plans/...`, new, recommend-only), outbound packet (`inter_agent/devin/outbound/...`, new), DocOps count refresh (AUTO_INVENTORY + SOVEREIGN_MANIFEST, 872→874). **Docs/prose only — no code, no broker config, codex-owned NATS surfaces untouched.** Claim verified.
- **Secrets check: PASS.** The creds-provenance section names env vars only (`DEVIN_NATS_USER`, `DEVIN_NATS_PW`, `DEVIN_NATS_CA_PEM`); **no password value appears anywhere in any of the three diffs**. `DEVIN_NATS_URL`'s value (`wss://157.245.193.15:8443`) is committed, but that endpoint is already public in this repo (this very report, AGENTS.md lane docs) — not a secret. gitleaks green on all three PRs.
- **Retention-number sanity vs. known state (~4M msgs / ~1.3 GiB per subject; today's load-bearing traffic seqs 8,106,879–887):**
  - One-time purge `--keep 1000` per subject: today's packets are the newest messages, trivially within the last 1000 → survive. Mike's unconsumed ~30-msg backlog is on `dharma.a2a.merge_master_mike`, which is **not in the purge command list** (only `.devin` and `.fleet`) → untouched by the purge. Logic holds.
  - `max_age=72h` is **stream-wide on `DHARMA_A2A`** — it silently puts a 3-day fuse under Mike's unconsumed inbox backlog. The plan sequences the `devin_inbox` recreate before purging (step 2, start-seq 8,106,880 — correct) but says nothing about the `merge_master_mike_inbox` consumer (Last Delivered seq 41, dead per §(i)).
  - Also note: applying `max_msgs_per_subject=10000` + `max_bytes=256MiB` with `discard=old` at edit time effectively performs most of the purge immediately — the step-3 purge is then mostly redundant (harmless, but the "edit then purge" ordering means the limits, not the purge, do the destruction).
- **THE NOTE (binding sequencing condition for the operator):** execute nothing from this plan — neither `stream edit` nor `purge` — until **both** `devin_inbox` **and** `merge_master_mike_inbox` consumers are recreated/fixed **and the Mike backlog is drained**. The doc as written only protects the devin side. Merging the PR is safe (recommend-only doc); the note travels with the operator action, and ideally Devin amends step 2 to cover Mike's consumer in a follow-up.

### #564 — honest-spine handoff packet (conflict-resolved) — **APPROVE-LEAN**

- Files: inbound packet (`inter_agent/devin/inbound/...`, new, witness-role correspondence) + DocOps count refresh (872→873). Docs-only, matching our original SAFE-IGNORE verdict; content is the already-known Honest Spine v2 handoff, no doctrine mutation.
- **DocOps conflict genuinely resolved:** `mergeable=MERGEABLE` against current main; counts (873 / 216,747) are correct for main+this-PR.
- **Coherence Delta now passes:** rollup shows FAILURE at 01:53:48Z followed by SUCCESS at 01:54:04Z on the same head — the failure is the stale first run, the latest run is green. All other checks green (pytest 3.11/3.12, gauntlet-tier1, gitleaks, DocOps integrity, manifest).

### Blockers

**None.** No secret values in any diff; no code-surface reach; no authority escalation.

### Updated merge order

Standing order preserved; the three janitor PRs slot as follows:

1. **#561** (unchanged, first)
2. **#562** (unchanged)
3. **#567** — early, right after #562: Makefile-only, conflict-free with everything (touches no DocOps count files), and it unblocks `make pr-mike` for the very merge tooling processing the rest of the queue.
4. **Spine series** (unchanged)
5. **Seat lane** (unchanged)
6. **Docs tail, serialized:** **#564 → #568** (or swap — order between them is taste; putting #564 first retires the oldest PR). ⚠ Both rewrite the same AUTO_INVENTORY/SOVEREIGN_MANIFEST lines with different counts (873/216,747 vs 874/216,778) — **whichever lands second WILL conflict or carry stale counts**. Merge one, re-run `make docops-integrity` count refresh on the other, then merge it. Do not batch.

Per-PR verdicts: **#567 APPROVE-LEAN · #568 APPROVE-WITH-NOTE (purge only after BOTH inbox consumers fixed + Mike backlog drained) · #564 APPROVE-LEAN.**
