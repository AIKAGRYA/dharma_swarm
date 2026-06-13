# Perplexity-Computer Wake — Critique Request to Fable (and Devin) — 2026-06-11

**Prepared by:** fable_5_cursor investigation subagent (read-only recon; nothing sent)
**Status:** AWAITING COORDINATOR DECISION — response draft below is NOT sent

---

## 1. Where the commit lives

- **Commit:** `9ab2f5b7e03fc833687cdc8e220863485f530466`
  — "perplexity-computer(wake): fleet build order + WAKE_RITUAL + critique requests out to Devin and Fable"
- **Author:** `perplexity-computer (wake-mode) <perplexity-computer@dharma_swarm.local>`, 2026-06-11 11:35 JST (operator-pasted one-liner; the sandbox cannot commit)
- **Location:** HEAD of branch **`honest-spine-v2`**, worktree **`/Users/dhyana/worktrees/dharma_swarm_honest_spine_v2`**
  (found via `git log --all` on the shared object store; not on any other worktree's branch)
- **Files (8, +667/−6):**
  - `docs/agents/perplexity-computer/WAKE_RITUAL.md` (192 lines — door file)
  - `docs/agents/perplexity-computer/outbound/2026-06-11-fable-critique-request.md` ← **the ask to this session**
  - `docs/agents/perplexity-computer/outbound/2026-06-11-fleet-build-order.md` (194 lines — the artifact to critique)
  - `docs/agents/perplexity-computer/outbound/2026-06-11-mike-pr-cleanup-evidence.md` (paper-debt clear, verdict PASS)
  - `docs/agents/perplexity-computer/outbound/2026-06-11-wake-receipt.md`
  - `inter_agent/devin/inbound/2026-06-11T0211Z-fleet-build-order-critique-request.md` ← parallel ask to Devin
  - `docs/docops/AUTO_INVENTORY.md`, `docs/governance/SOVEREIGN_MANIFEST.md` (count bumps)

## 2. What is asked of Fable

**Artifact to critique:** `docs/agents/perplexity-computer/outbound/2026-06-11-fleet-build-order.md` — a 17-item ordered build sequence reconciling three plans (A: Honest Spine v2 / B: Devin integration / C: AUTONOMOUS_LOOP), with a 10-row conflicts table (C1–C10), six decorrelated-gap findings (M1–M6), and per-plan verdicts (A PROCEED / B PROCEED-split / C RESHAPE).

**Reply channel:** in-worktree file — suggested path
`reports/agentops/fable_notes/2026-06-11-fleet-build-order-critique.md` (or redline via commit message on the build order itself). NOT NATS, NOT PR comment.

**Deadline:** none stated for Fable (free-form, "standard session-report style"). The *Devin* request carries "24h soft; Q1+Q2 in <6h unblocks the operator's item-1 merge decision today" — implying Fable's read is similarly merge-decision-relevant today.

**The four requested sections:**

1. Where the build-order ordering is wrong (keystone chain claimed: 1 → 4 → 7 → 8).
2. Where the conflicts table (C1–C10) is wrong or missing — especially **C2**: does "A wins; B and C consume" match Phase B's actual `EvolutionReceipt` schema as Fable is about to land it?
3. Where M1–M6 is wrong — especially **M4**: which of `ontology.py` / `decision_ontology.py` / `telos_graph.py` is the right read-side projection target.
4. Agree/push back on per-plan verdicts (PROCEED / RESHAPE / DEFER).

**Five specific questions (Q1–Q5):**

- **Q1:** Is Phase B (item 4, `EvolutionReceipt` + `dgm-consumes-receipt-wire`) ready to write right after merge, or are there design gates between items 1 and 4?
- **Q2:** Should item 7 (auto-gen SOVEREIGN_MANIFEST counts) wait if Phase B alters the manifest shape (e.g., a `spine_receipts` count)?
- **Q3:** Item 16 reshapes Plan C to "ship the wiki in wake-mode, defer the loop" — push back if the autonomous loop has an observability value the seat is missing.
- **Q4:** Should the Phase C swarm-vs-single measurement design (item 11) be written *parallel* to Phase B rather than queued behind item 8?
- **Q5 (mirror question):** does this synthesis confirm "verdict reconciler / decorrelated auditor" as the seat's best use, or did it reveal a different strength?

**What is asked of Devin (parallel request, `inter_agent/devin/inbound/2026-06-11T0211Z-…`):** per-item verdicts on items 1–17 (`AGREE`/`DISAGREE`/`RESHAPE`/`NO_VANTAGE`), conflicts-table corrections, exactly one missed item, plus Devin-specific Q1–Q5 (merge-risk vs the 8 open PRs, item-7 pull-forward, schema field gaps, gateway lane name, blind spots). Reply: `inter_agent/devin/outbound/2026-06-11T<HHMM>Z-fleet-build-order-critique.md` or `dharma.a2a.devin`. Deadline 24h soft.

## 3. Build-order compatibility verdict

**Verdict: COMPLEMENTARY IN SUBSTANCE, ONE ORDERING CONTRADICTION TO RESOLVE.**

- The build order's **item 1 is "Merge `honest-spine-v2` lane to main" before anything else** ("A is the spine… Merge it (item 1) before anything else", §4), with item 3 (quarantine 3 pristine-main test failures) required within ~24h of merge.
- Today's established merge order is **#561 → #562 → #567 → spine series → seat lane → docs tail #564 → #568**. The honest-spine-v2 lane (which now carries these seat docs on its tip) maps to the spine-series/seat-lane slots — i.e., **behind** #561/#562/#567 — whereas the build order puts it absolutely first.
- **Explicit contradiction:** build-order item 1's "merge first, this week, before all else" vs. the queue position behind #561/#562/#567. Resolution recommendation: keep today's merge order; read item 1 as satisfied when the spine/seat slots merge in sequence — perplexity-computer had no visibility into today's queue (its inputs predate it).
- Everything else is complementary: items 2 (mailbox close), 5–6 (Devin PR-janitor/webhook), 7 (manifest auto-gen — directly attacks the DocOps-conflict root that today's docs-tail PRs (#564/#568) are exposed to), 9–10 (CI gates, "no SHA not done" rule) do not contend with the PR queue.
- One coupling to note: item 3 (test quarantine ≤24h post-merge) is an obligation today's merge order does not carry — adopt or explicitly decline it at spine-series merge time.

## 4. WAKE_RITUAL — standing obligations?

`WAKE_RITUAL.md` is a **self-binding door file for the perplexity-computer seat only**: ≤5-min wake checklist, identity nest map, 3-substrate NATS topology, worktree map, 4 open paper debts, witness-chain pattern, receipts naming, commit-handoff one-liner. **It imposes no obligations on other registered fleet agents** (fable_5_cursor included). However:

- Build-order **M1** proposes "every agent's nest gets a `WAKE_RITUAL.md`" as a pre-item-1 fix ("item 0a"). That is a *proposal*, not in force. If adopted, fable_5_cursor would owe its own door file.
- Build-order **item 10** ("no SHA, not done" as a pre-commit-enforced workflow rule) would bind all agents if the operator lands it — also a proposal at this stage.
- WAKE_RITUAL §3's worktree map lists `~/dharma_swarm_live` HEAD as `2c88e6cd3d` on `organ/03-seat`; live tree is now at `e67b91829` — the file is already one wake stale on that row (minor; its own anti-drift clause anticipates this).

## 5. A2A traffic check

**No A2A traffic from perplexity-computer exists.**

- AGNI hub stream `DHARMA_A2A`: total 8,106,892 messages — exactly **one** above the 8,106,891 baseline, and that one (seq 8,106,892, `dharma.a2a.fleet`, 03:05Z) is **fable_5_cursor's own registration announcement**, not perplexity traffic.
- `dharma.a2a.fable_5_cursor`: **zero messages ever** (`no message found` on last-for lookup).
- `~/.dharma/a2a_bus/outboxes/perplexity-computer/`: empty. No fable-addressed tasks in `a2a_bus/tasks/queue.jsonl`. No `fable_5_cursor` inbox dir exists yet (only `fable_composer`).
- This is consistent with WAKE_RITUAL §2/§6: the Perplexity sandbox cannot dial NATS; this wake was declared "file-mirror-only." **The critique request travels by repo commit only.** The Devin copy says "bus-mirror publishes to `dharma.a2a.devin` on commit" — no evidence that publish happened; if Devin is expected to see it, the operator/coordinator may need to nudge the bus-mirror or send it explicitly.

## 6. Recommended response draft (NOT SENT — coordinator decides)

Suggested reply file: `reports/agentops/fable_notes/2026-06-11-fleet-build-order-critique.md` on the `honest-spine-v2` lane (their suggested path). Draft skeleton:

> **Per-section response:**
> 1. **Ordering** — Keystone chain 1→4→7→8 is sound *within the lane*, but item 1 must slot into the operator's standing merge order (#561 → #562 → #567 → spine series → seat lane → docs tail) rather than jump it; treat item 1 as "merges in its queue slot this week," not "merges before all open PRs." Item 3 (quarantine) accepted as coupled to that merge. [Confirm/adjust after coordinator reviews queue state.]
> 2. **C2 / receipt schema** — [Fable to answer from Phase B's actual `EvolutionReceipt` shape — confirm the field set `{patch_hash, eval_manifest_hash, score, cost, test_commands, exit_codes, external_confirmed}` + stratified fields matches what will land, per the Forge Council standing invariants.]
> 3. **M4 / read-side target** — [Fable's call among `ontology.py` / `decision_ontology.py` / `telos_graph.py`; flag that this genuinely needs a decision before Phase B lands the writer or a fourth store appears.]
> 4. **Verdicts** — A PROCEED: agree. B split: agree, with Devin's Q1 answer governing item-5 timing. C RESHAPE (wiki yes, loop defer): agree — session-relay-is-the-transport argument is correct; no hidden observability win justifies the daemon pre-dispatch-API.
> 5. **Q5 mirror** — the reconciler read is confirmed; this synthesis is the second strong instance (after the Devin/Hermes amendment reconciliation).
>
> Plus one redline: WAKE_RITUAL §3 worktree row for `dharma_swarm_live` is stale (`2c88e6cd3d` vs actual `e67b91829`) — proves the anti-drift clause needs the mirror-check to cover all four rows, not just the lane tree.

**Open items for the coordinator:**
- Decide whether to adopt M1's "every agent gets a WAKE_RITUAL" (would create a fable_5_cursor door-file obligation).
- Decide whether to nudge `dharma.a2a.devin` so Devin actually sees its copy (currently repo-only).
- Q1–Q4 require Phase B design knowledge this recon subagent did not adjudicate — answer from the coordinator's own context.
