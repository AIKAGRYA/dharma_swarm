# Review Request — Adversarial Second Pass on the Humming Spec (Codex lane)

**Document role:** `handoff_request` — a cross-lane review request. It does not
create a track, assign ownership, close a finding, authorize implementation,
or grant merge authority. It is subordinate to `CLAUDE.md`,
`docs/governance/ACTIVE_TRACK.yaml`, and the human operator.

**Requested reviewer:** the Codex-lane agent that independently read the same
harness/loop/graph-engineering article and performed its own pass (operator's
words). If that is the `cybernetics_codex` steward, its own
`docs/agents/cybernetics_codex/PROTOCOLS.md` evidence discipline applies; if it
is another Codex session, the operator may paste this file's path into that
session as the wake instruction.

**Subject under review:**
`docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md`
pinned at commit `2d4aa5a1f86b2030454b7cb504239c4d78d73816`
(PR [#1186](https://github.com/AmitabhainArunachala/dharma_swarm/pull/1186),
branch `claude/harness-loop-graph-review-o8uy5o`).

**Context:** the spec was produced from a three-lane audit of the working tree
(harness chokepoints; loop levels L1–L4; DharmaGraph vs. the live dispatch
path). Its baseline table (§1) carries the audit's `file:line` evidence; its
doctrine section (§2) proposes two deltas (consumption-or-it-didn't-happen;
monitors must have actuators); §3–§6 are the workstreams, enforcement matrix,
phasing, and acceptance scoreboard; §8 is the research bibliography.

---

## The ask (from the operator, via the Claude lane)

1. **Independent adversarial read, from your angle.** You read the same
   article and did your own pass — review the spec against *your* pass, not
   ours. Where your reading of the article's taxonomy (harness / loop / graph;
   the four loop levels; the diagnostic "behavior vs. cadence vs. path")
   disagrees with the spec's framing, say so with evidence.

2. **Do whatever research you judge necessary.** The spec's bibliography (§8)
   is fourteen entries (GEPA arXiv:2507.19457; DGM 2505.22954; HGM 2510.21614;
   Red Queen 2606.26294; Group-Evolving 2602.04837; ACE 2510.04618; CaMeL
   2503.18813; out-of-band-defense evaluation 2606.26479; AFlow 2410.10762;
   MaAS 2502.04180; EvoAgentX 2507.03616; MAST 2503.13657; RUVER-BENCH
   2606.29920; TiMem 2601.02845). Flag anything it missed, misread, or
   over-weighted, and add whatever current work your own search surfaces —
   especially anything that post-dates or supersedes these.

3. **Confidence rating.** Grade the current spec, per-dimension and overall,
   on:
   - **A. Article coverage** — does executing this spec fully answer the
     article's three disciplines and four loop levels, including its
     prescriptive ordering (harness first; simplest loop + grader; graph only
     where the answer is known; then the compounding loops)?
   - **B. Enforcement realism** — will the §4 enforcement matrix and §6
     scoreboard actually hold under this repo's gate reality
     (`docs/governance/CI_TRUTH_CONTRACT.json`,
     `scripts/runtime/pr_merge_control.py`), or are any acceptance criteria
     charmable?
   - **C. Future-proofing** — does the research integration (WS-R) track where
     the bleeding edge is actually going, and are the adoption rules
     (arena-scored candidates only; One Wire untouched) sufficient against
     the self-referential risks (DGM Appendix F telemetry attack, grader
     Goodharting)?
   - **D. Governance fit** — track routing, WIP ceiling, unowned-surface
     handling, BR-id hygiene.
   Use your own verdict vocabulary (`SUPPORTED` / `PARTIAL` / `CONTRADICTED`
   per your Cross-Check Protocol, or a 0–100 grade in the gauntlet style) —
   whichever you use, state the rubric before the scores, frozen before
   grading, per this repo's rubric discipline.

4. **Deliverable — either is acceptable:**
   - **(a) Insights response:** a handoff doc in `docs/plans/handoffs/`
     (precedent: `CODEX_PRE_1004_ADVERSARIAL_REVIEW_2026-07-19.md`) and/or a
     PR review on #1186, carrying your ratings, disagreements, and additions;
     or
   - **(b) A superseding V2:** a new
     `docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_V2_<date>.md` that integrates
     everything in V1 and adds what you find missing — with a delta table
     against V1, the same `file:line` citation-or-silence discipline, the same
     no-new-track governance position, and V1 marked SUPERSEDED in its header
     by that PR (not by prose elsewhere).

## Constraints that bind the review

- Citation-or-silence: uncited claims carry zero weight (`CLAUDE.md`).
- Do not round up: if a spec claim cannot be verified from the pinned commit,
  mark it `PARTIAL`/`UNKNOWN`, not confirmed.
- No gate may be weakened in any V2 proposal; One Wire
  (`dharma_swarm/archive.py:572-591`) and the chamber's efferent-closed
  boundary (`dharma_swarm/chamber/__init__.py:1-17`) are invariants.
- The review itself grants no authority; adoption of any recommendation goes
  through the owning tracks in `docs/governance/ACTIVE_TRACK.yaml`.

## Where to respond

Reply as a PR review or comment on #1186, and/or commit your response doc to a
branch and open a PR referencing #1186. The Claude lane is subscribed to #1186
and will integrate your findings either way.
