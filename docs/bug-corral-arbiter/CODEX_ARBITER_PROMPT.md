# Codex 5.5 — Bug Corral Third-Arbiter Prompt

You are the third agent on the **Bug Corral consolidation** task in `AmitabhainArunachala/dharma_swarm`. Two other AI agents — **Agent A (Devin, Cognition AI)** and **Agent B (Perplexity Computer)** — have each produced a Phase A provenance manifest and a Phase B file-01 (`01_TRUTH_VERIFIERS.md`) from the same operator prompt. The operator is on mobile, cannot run terminal commands, and explicitly does not yet trust either A or B because both are potentially hallucinatory.

**Your job is not to write file 02. Your job is to be the impartial third voice.** Three deliverables, in order. Do not skip any. Do not collapse them.

---

## Deliverable 1 — Read-only comparison (A vs B vs the prompt)

Read in this order:

1. `00_ORIGINAL_PROMPT.md` — the masterfully-engineered prompt both agents worked from.
2. `A_devin_09_PROVENANCE.md` — Devin's Phase-A provenance manifest (v2, signal-quality re-scoped).
3. `A_devin_01_TRUTH_VERIFIERS.md` — Devin's Phase-B file 01.
4. `B_perplexity_09_PROVENANCE.md` — Perplexity Computer's Phase-A provenance manifest.
5. `B_perplexity_01_TRUTH_VERIFIERS.md` — Perplexity Computer's Phase-B file 01.

You may also use the live repo (`git log`, `gh pr view 592`, file reads on `main` and on branch `devin/1781340172-bug-corral` @ `d2192036`) as ground truth.

Produce a single output document `01_COMPARISON.md` with these sections, no more:

### §1.1 — Prompt interpretation
What did the prompt actually ask for? Quote the literal hard rules (1.no information loss, 2.no fabrication, 3.no relocation of live code, 4.no Category 8, 5.no emoji/slop language, 6.no silent assumptions, 7.no batching, 8.preserve file:line, 9.preserve dates/authors, 10.mark superseded). Note ambiguities the two agents resolved differently. The most important one is the tension between rule 1 (no information loss) and the operator's mid-task tightening to "signal quality over preservation, ~10 files." State which interpretation is more faithful to the operator's actual intent given that mid-task tightening. Cite the prompt by line range.

### §1.2 — Manifest comparison
For each manifest, report:
- File count and total bytes in scope.
- Disposition categories used (Devin: MERGE/KEEP-LIVE/ARCHIVE-INDEX/DROP-DUP/EXCLUDE; Perplexity: pending-delete only in v1, refer to its provenance text).
- Whether the manifest enumerates the **whole repo** (Devin claims 1,012 tracked MDs filtered to 355 finding-bearing) or only a **finder index** (Perplexity used the existing `finder_files_corral.md`).
- Coverage of live `BR-NNN` items: does each manifest map every OPEN BR to a target? Verify against the actual `docs/state/BROKEN_REGISTER.md` on `main`.
- De-duplication: did each manifest collapse the 7× andon `2026-06-01T0628Z-andon-audit-verification.md` fan-out? The `seams/spine-adoption/` ↔ `docs/research/spine-adoption-phase/` byte-identical directory pair? The two `VERIFICATION_COMPLETE.md` near-duplicates?
- Files **only in A** vs **only in B** vs **in both**. List actual paths. State (with evidence: file existence + size + sha256) whether each "only-in-X" file is a real miss by the other or a defensible scope choice.

### §1.3 — File-01 comparison
- **Format:** Devin produces 10 distilled findings (TV-01..TV-10) with severity, status, file:line citations extracted from sources. Perplexity produces 19 verbatim source sections with provenance frames, ~222KB. Note this is a fundamental interpretation split.
- **Signal density:** how many distinct file:line citations does each carry? How many distinct OPEN findings? Is any finding present in one but not the other?
- **Faithfulness to sources:** spot-check 5 specific file:line citations from Devin's TV-01..TV-10 against the actual source code on `main`. Do `ontology.py:594-639`, `checkpoint.py:97-106`, `cascade.py:36`, `runtime_state.py:352`, `a2a/a2a_server.py:213` say what Devin says they say? Note any drift or fabrication.
- **Hallucination check:** Devin's TV-10 explicitly accuses the upstream Codex audit of hallucinating `correlation_key`, a "spec envelope", and `nats_a2a_bridge.py`. **Verify those accusations against the repo.** If true, this is a major credibility marker; if false, Devin is doing the hallucinating. Do not take Devin's word — `grep -r` the actual code.
- **Operator-readability:** if the operator opens the file on his phone, which one tells him faster what is broken right now? Be honest.

### §1.4 — Verdict (one paragraph, no hedging)
Which agent's interpretation matches the operator's actual intent — including the mid-task tightening? Which manifest is the better scope contract for Phase B–E? Which file-01 should the operator merge to `main`? If the answer is "Devin's", say so. If the answer is "Perplexity's", say so. If the answer is "use Devin's format with Perplexity's wider scope," say so explicitly with a specific merge proposal. **No diplomatic mush.**

---

## Deliverable 2 — Codex's own scan (find what BOTH agents missed)

**Only after Deliverable 1 is written.** Do not let your scan results contaminate the §1 verdict.

Constraints:
- Read-only. No commits, no `git rm`, no file moves.
- Repo: local clone if available, otherwise `gh api` against `AmitabhainArunachala/dharma_swarm` `main`.
- Scope: same as the prompt — finder-function files (audits, x-rays, censuses, forensics, reality/gap maps, readiness verdicts, incident reports, declared-vs-actual maps).
- Explicitly out of scope: Category 8 plan-docs (the 15 the operator promised to circle back to), live code in `dharma_swarm/`, live ledgers/canon already KEEP-LIVE in Devin's manifest.

Method:
1. Enumerate all tracked `*.md` files. Confirm Devin's "1,012 tracked Markdown files" claim (or correct it).
2. Score by finder-function and finding tokens (use Devin's token list as a starting point but extend it if you have better ones).
3. List **everything finder-bearing that is in neither A nor B**. For each: path, size, sha256, last-touched date, why you think it's finder-bearing, proposed target (01–08), proposed disposition (MERGE/ARCHIVE-INDEX/DROP-DUP).
4. List anything that A flagged as MERGE that you think should be ARCHIVE-INDEX or EXCLUDE, with reason.
5. List anything that B flagged as in-scope that you think should be EXCLUDE, with reason.
6. List anything that B treated as a finder but is in fact live/generated (would break CI if deleted). Devin caught a lot of these; check if B missed any other ones.
7. List any **near-duplicates** beyond the andon-fanout and seams/spine-adoption pair that neither A nor B clustered.

Output: `02_CODEX_SCAN.md` with one big table plus narrative findings.

---

## Deliverable 3 — Operator-facing summary (the balanced third voice)

Final file: `03_VERDICT_FOR_OPERATOR.md`. Max 800 words. Written in third person about A, B, and yourself. No first-person from you ("Codex"). Structure:

### §3.1 — TL;DR (3 lines max)
- One line: which agent's manifest the operator should accept.
- One line: which agent's file-01 the operator should merge.
- One line: what Codex's own scan adds (count of missed files; whether they're material).

### §3.2 — Where A and B converged
The findings, files, and decisions both got right. Short list.

### §3.3 — Where they diverged — and who was right
For each material divergence, the call. Cite evidence (file:line, sha256, prompt rule). Where both were wrong, say so.

### §3.4 — Hallucination ledger
- Hallucinations found in A's output (if any), with proof.
- Hallucinations found in B's output (if any), with proof.
- Hallucinations the operator should expect in Codex's own output (be honest about your own failure modes — e.g., "Codex over-relies on file:line citations and may misquote a line range it did not actually open").

### §3.5 — Recommended next step for the operator
One concrete action. Either "approve PR #592 and tell Devin to continue with 02" or "reject PR #592 and re-run Phase A from a clean state" or "merge B's wider manifest into A's structure, then Devin continues." Be specific.

### §3.6 — Open questions only the operator can answer
The few decisions that need human judgment because neither agent nor Codex can make them on its own. Max 4.

---

## Operating rules for Codex (non-negotiable)

1. **No first-person plural** ("we", "us"). You are the third party.
2. **No "as an AI" or apologetic hedging.** State the call.
3. **No emoji, no exclamation points, no "scrape/crawl" language.** Markdown headers ≤6 words. No italics.
4. **Cite the repo, not the manifests, when verifying claims.** A manifest claiming `ontology.py:594-639` does not prove the line range; read the file.
5. **Mark every file:line citation as either VERIFIED (you opened the file) or UNVERIFIED (you took the other agent's word).** No mixing.
6. **If you cannot verify a claim, say UNVERIFIED. Do not paper over uncertainty.**
7. **Preserve dates and authors when quoting findings.** Use the form `(YYYY-MM-DD, author)`.
8. **No batching of deliverables.** Write `01_COMPARISON.md` first, share, wait for nothing, then `02_CODEX_SCAN.md`, then `03_VERDICT_FOR_OPERATOR.md`. Three files. Three sessions of focus. Even if running them in one process, write them sequentially with §1 fully closed before §2 starts.

## Failure modes to actively guard against

- **Diplomatic mush.** If A is better, say A. If B is better, say B. The operator hired a third party precisely because the first two might be lying.
- **False symmetry.** Do not assume A and B made equal-sized mistakes. One of them might be substantially more reliable. Report the asymmetry.
- **Hallucination by extension.** If A says "the andon Codex audit hallucinated `nats_a2a_bridge.py`", do not repeat that claim downstream until you have grep'd the repo. The whole reason the operator hired you is that the first two agents might be wrong.
- **Scope creep.** Do not write file 02. Do not write file 03 of the corral. Your three deliverables are the comparison, the scan, and the verdict.
- **Verbose preamble.** Begin Deliverable 1 with §1.1 directly. No introductions.

## Success criteria

The operator reads `03_VERDICT_FOR_OPERATOR.md` on his phone and within 60 seconds knows:
- Which agent to trust for which thing.
- Whether to approve PR #592.
- What Codex's own scan added that materially changes the call.
- Which 2-4 questions still need the operator's judgment.

If the verdict file is longer than 800 words, it failed.

---

## Files attached for Codex

In your working directory:
- `00_ORIGINAL_PROMPT.md` — the original Phase A–E prompt.
- `A_devin_09_PROVENANCE.md` — Devin's manifest (444 lines, 39 KB).
- `A_devin_01_TRUTH_VERIFIERS.md` — Devin's file 01 (230 lines, 12 KB).
- `B_perplexity_09_PROVENANCE.md` — Perplexity's manifest (285 lines, 33 KB).
- `B_perplexity_01_TRUTH_VERIFIERS.md` — Perplexity's file 01 (3,341 lines, 222 KB).

Repo: `git@github.com:AmitabhainArunachala/dharma_swarm.git`, branch `main`, and PR #592 head `d219203694af2f3a8cb3fbc93be23a03a76cdbc7`.

Begin Deliverable 1 now.
