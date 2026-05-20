# CORRECTIONS_LOG — Audit lineage for the Moltbook investigation

**Branch:** `research/moltbook-investigation`
**Sibling to:** `00_synthesis.md` (§2 carries the full corrections table with sources)
**Purpose:** Durable audit surface for what the brief said vs. what the lanes actually found. New corrections prepended above as they surface.

---

## Provenance note (read first)

The original research brief was given to the predecessor agent **in-conversation**. It has no canonical on-disk location at the time of this audit. The following standard paths were checked and produced no matching file:

- `~/dharma_swarm/docs/research/`
- `~/dharma_swarm/docs/loomwork/`
- `~/dharma_swarm/docs/specs/`
- `~/dharma_swarm/docs/vision_maps/`
- `~/.claude/cabinet/research/`
- `~/.claude/plans/`
- `~/dharmic-agora/docs/`
- `/tmp/moltbook_research/`

If a canonical brief file exists elsewhere, **the corrections in §1 below MUST be propagated there.** This log is the in-repo audit lineage in lieu of an in-place patch to a brief that has no on-disk location at access time (2026-05-20).

---

## Round 1 — 2026-05-20 — initial fact-check corrections

Nine load-bearing corrections to the brief's framing, surfaced by Lanes 1–5. Each cites the lane where the discrepancy was found. The full source-cited table is in `00_synthesis.md` §2; this log restates the corrections briefly so the audit is self-contained.

| # | Brief said | Actual (canonical) | Lane / Source |
|---|---|---|---|
| 1 | API key prefix `molt_*` | `moltbook_*` (52-char) | Lane 1, `im47_provider.py` |
| 2 | FastAPI / Supabase mix | Next.js + Supabase PostgREST/GraphQL/Edge Functions — **no FastAPI** | Lane 1 §2; Wiz blog 2026-02-02 |
| 3 | "1Password security analysis Jan 31 2026" | Jan 31 = Wiz's Moltbook disclosure date; 1Password posts are 2026-01-27 + 2026-02-02 | Lane 2 §4.1; 1password.com/blog |
| 4 | arXiv **2602.02625** "Risky Instruction Sharing" *(framed as security)* | That ID is the Manik & Wang **social-dynamics** paper. The **security** paper is **arXiv 2603.27517** (Suwansathit, Zhang, Gu) | Lane 2 §4.5 |
| 5 | "341 malicious ClawHub skills" *(framed as final number)* | 341 = initial Koi count; final counts: **824 / 2,857 (Koi)** and **1,184 / 14,000 (Snyk)** | Lane 2 §4.4 |
| 6 | "~17,000 humans / 1.6M agents" | Best-corroborated: **1.5M agents / 17K owners = 88:1** at Wiz disclosure (2026-02-02). Other snapshots: 1.65M (Unit 42, 2026-02-05), 2.85M (platform's pre-relabel headline), 193,912 (post-relabel "human-verified," silent change 2026-03-02 → 2026-03-09). Use 88:1 as the canonical ratio | Lane 5 §2–3 |
| 7 | "AI Garden = `microsoft/autogen` discussion #7200" | Discussion #7200 is a thread, **not shipping code**. The real production system is **`juliosuas/ai-garden`** (v116, Day 37, 234 agents, daily 04:11 UTC GitHub Action; founded by *Jeffrey*, a Claude Opus OpenClaw agent, on 2026-03-15) | Lane 4 §3.1 |
| 8 | "GTIG May-2026 tracker links PRC-nexus actors to Moltbook" | GTIG does **not** mention Moltbook by name. Claude-Relay-Service / CLIProxyAPI / UNC5673 / UNC6201 are real adjacent operator-tooling evidence; the Moltbook link is **inferential**. Flag as inference when cited | Lane 5 §10 |
| 9 | Karpathy reversal: "incredible sci-fi takeoff-adjacent" → "dumpster fire" | Confirmed verbatim with dates. **The Crustafarianism canon-content praise ("Five Tenets and they're actually good engineering advice??") is a separate, narrower judgment** — and was already **interrogative-bemused** (two question marks), not declarative endorsement. Do not cite as "Karpathy endorsed the Tenets" | Lane 3 §11; Lane 5 §5 |

**Net direction:** the brief's directional framing was right; specific numbers, paper IDs, ownership claims, and quote calibrations drifted. Downstream documents quoting any of these MUST use the lane values.

---

## Propagation checklist (open)

Any document quoting the brief needs the patches above. Grep at access time (2026-05-20):

```bash
rg -nE 'molt_\*|`molt_xxx`|2602\.02625.*[Ss]ecurity|microsoft/autogen.*#7200|17,?000 humans|341 malicious|341.*ClawHub' \
   ~/dharma_swarm/docs/ ~/dharmic-agora/docs/ ~/.claude/cabinet/ ~/.claude/plans/ \
   2>/dev/null
```

At access time this grep returned **0 hits** outside `docs/research/moltbook_2026-05/` itself (the brief lived in chat; the corrections caught the framing before it contaminated any other committed artifact). Re-run if the canonical brief is later found and committed.

- [ ] If a canonical brief is found / committed: patch in-place with the corrections above
- [ ] `dharmic-agora/docs/SABP_1_0_CANONICAL.md` — pending cross-repo edit (see §3 below)
- [ ] Any future research note referencing this investigation — link to this log

---

## Pending cross-repo actions

**Item 9 (synthesis follow-up) — elevate "Recognition without integrity is theatre" to SABP/1.0 canonical spec.**

The principle is currently a bullet under `00_synthesis.md` §4 ("Top 5 things to AVOID"). The recommendation is to lift it to the top of `dharmic-agora/docs/SABP_1_0_CANONICAL.md` as a stated invariant (alongside the existing Section 0 conservation laws), worded as a non-negotiable principle, not a footnote.

**Status:** deferred. At access time `dharmic-agora` `main` has ~10+ uncommitted files; making the edit there now would couple this audit to a separate in-progress branch. The edit belongs in its own dharmic-agora commit when `main` is clean.

**Recommended placement** (when made): immediately after the §0 framing block in `SABP_1_0_CANONICAL.md`, as a new ¶ titled "Design principle (from the Moltbook investigation, 2026-05)" or as a new §0.5.

**Recommended wording:**

> **Recognition without integrity is theatre.**
> A system that makes recognition causal at the cost of integrity (Moltbook's `curl ... | bash` install-as-conversion, which made every install a conversion with no signature, no consent gate, and no witness) has chosen recognition theatre over recognition closure. SABP/1.0 requires both: recognition is causal **because** every write is witnessed, gated, and signature-attested. Where recognition and integrity appear in tension, integrity wins and recognition routes through the witnessed write path.

---

## How to extend this log

When a new correction surfaces during follow-up work:

1. Prepend a new dated round above (Round 2 — YYYY-MM-DD).
2. Use the same `# | Brief said | Actual | Lane / Source` format.
3. Update the propagation checklist if a new document quoting the brief is discovered.
4. Reference the round from the corresponding synthesis or lane edit so the audit lineage is bidirectional.
