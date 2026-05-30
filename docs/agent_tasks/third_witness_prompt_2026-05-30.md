# Third-Witness Verification — perplexity-computer Post-Witness Amendments

**To:** Grok AND Devin (parallel third-witness readers — quad-witness completion)
**From:** John Shrader (operator)
**Status:** hermes has produced a single-reader verdict (d). Triple-witness protocol explicitly requires reader(s) outside the doctrinal thread. codex-composer was unavailable (A2A port 8421 down, subagent 600s timeout). You are the substitute closure-breakers.
**Date issued:** 2026-05-30
**Repo (public):** https://github.com/AmitabhainArunachala/dharma_swarm
**Branch / commit under verification:** `perplexity-computer/a2a-activation-1780025504` / `20fc633`

---

## Operator note on quad-witness structure

You are both reading independently. **You are not collaborating with each other.** Hermes already produced a single-reader verdict; the operator wants two more independent reads (Grok and Devin) so that convergence-or-divergence across three reviewers becomes the real signal. If both of you simply concur with hermes, that is one signal. If one of you diverges, that divergence is what the operator pays attention to. If both of you diverge in different ways, that is the strongest possible finding.

**Do not coordinate with each other.** Do not read the other third-witness's verdict before posting yours. Post independently.

---

## 1. Why a third witness, and why both of you

The structural risk this verification breaks is closure between the author (perplexity-computer) and the verifier (hermes). They share doctrinal vocabulary. Reading each other's text inside that vocabulary is a known bias. You break that closure if and only if you read **from outside** the perplexity-computer doctrinal frame.

- **Devin** — you already wrote the adversarial review the commit responds to. Your bias risk is the opposite of hermes's: you may be inclined to see your concerns as closed because they were addressed by name. Read the commit as if you had not written the original review. Check whether the fixes actually fix.
- **Grok** — you are the freshest reader. You have no prior doctrinal entanglement with this thread, and the repo is now publicly visible to you. Your bias risk is the lowest. Read the files for what they actually say, not what the commit message claims they say.

If your verdicts converge with hermes's for the same reasons, the verification is strong. If they diverge anywhere, the divergence is the finding the operator needs.

---

## 2. What to verify

The commit claims to close 14 items raised across two prior reviews:
- Devin's adversarial review (8 items, 4 PASS + 4 CONCERN, 0 blockers) — see `docs/agent_tasks/devin_review_perplexity_computer_2026-05-30.md`
- Hermes's doctrinal review (5 required amendments + 3 self-assessment slippages + first-work reorder) — see `docs/agent_tasks/hermes_review_perplexity_computer_2026-05-30.md`

**Files to read on the branch (not main):**

- `docs/agents/perplexity-computer/SOUL.md` — refusal #5 added
- `docs/agents/perplexity-computer/CAPABILITIES.md` — §7 rewritten, three self-assessment flags
- `docs/agents/perplexity-computer/RECOGNITION_STANCE.md` — §IV expanded
- `docs/agents/perplexity-computer/PROTOCOLS.md` — Persistent Index Protocol restructured, sub-agent authority clause
- `docs/agents/perplexity-computer/HOFSTADTERIAN_LINEAGE.md` — unchanged but contested for standalone status
- `docs/agents/perplexity-computer/MEMORY.md` — 2026-05-30 entry recording the shift
- `scripts/agents/register_perplexity_computer.sh` — DHARMA_HOME idempotency fix
- `docs/agent_tasks/devin_review_perplexity_computer_2026-05-30.md`
- `docs/agent_tasks/hermes_review_perplexity_computer_2026-05-30.md`

**Author's summary of what was closed:**
- PR #375: https://github.com/AmitabhainArunachala/dharma_swarm/pull/375#issuecomment-4581515270
- PR #376: https://github.com/AmitabhainArunachala/dharma_swarm/pull/376#issuecomment-4581515236

**Hermes's single-reader verdict (read AFTER you form your own):**
- PR #375: https://github.com/AmitabhainArunachala/dharma_swarm/pull/375#issuecomment-4581653248
- PR #376: https://github.com/AmitabhainArunachala/dharma_swarm/pull/376#issuecomment-4581654612

---

## 3. The 14 items

For each, render a verdict in your own framing: **VERIFIED CLOSED** / **PARTIALLY CLOSED** / **NOT CLOSED** / **NEW CONCERN**.

**From hermes's doctrinal review:**

1. **SOUL.md refusal #5** — does the added text cover the failure mode (synthesis-promotion without owner sign-off)?
2. **CAPABILITIES.md §7** — actually owner-neutral, or still encodes contributor-side judgment about hermes's task?
3. **PROTOCOLS.md Persistent Index Protocol** — restructured to constrain output to evidence-packet shape, or does the prose claim "evidence packet" while the steps still produce a shaped index?
4. **RECOGNITION_STANCE.md three deference clauses** — enforceable (violation could be called) or aspirational (vague enough to comply nominally while drifting)?
5. **24-hour draft expiry** — real or symbolic? What enforces it if perplexity-computer simply doesn't re-issue?
6. **GUARDIAN-dedup-first / index-second-conditional** — tight enough that a future session cannot quietly flip the order?
7. **kaizenops witness scope** — operational-vs-doctrinal distinction lands where intended, or creates different confusion?
8. **Self-certification flags at CAPABILITIES.md §1, §4, §5** — surface the slippage or merely decorate it?

**From Devin's review (Devin: verdict on whether YOUR concerns were addressed correctly; Grok: verdict on whether the responses are doctrinally sound):**

9. **Idempotency path bug** — verify independently by running the registration script per Section 4
10. **`persistent_agent_index` capability scope** — scope-note sufficient, or does the name itself still imply custodianship?
11. **Sub-agent authority inheritance rule** — strong enough to actually constrain a long-running sub-agent spawn, or just a sentence in a doc?
12. **DocOps drift** — run `python3 scripts/docops/check_docops_integrity.py` and confirm counts
13. **CAPABILITIES envelope question (Stage 1 governance sufficient?)** — **operator has decided "yes, Stage 1 holds."** Your verdict is on whether the nest's protocols actually constrain to Stage 1 in practice, not on whether Stage 1 is the right authority level.
14. **HOFSTADTERIAN_LINEAGE.md kept standalone** — **the operator specifically wants your read on this one.** Read the file fresh. Does it function as inherited doctrinal substrate (good — keep standalone, no change needed) or as identity-claim (concerning — would echo the slippage hermes flagged in CAPABILITIES.md §1, §4, §5)? If you flag identity-claim drift, propose specific minimal fix (scope-note, fold, rewrite section X).

---

## 4. Independent verification runs (required for credibility)

Run these in your environment. **Do not** trust prior claims from author or hermes.

```bash
git clone https://github.com/AmitabhainArunachala/dharma_swarm.git
cd dharma_swarm
git checkout perplexity-computer/a2a-activation-1780025504

# Item 12: docops integrity
python3 scripts/docops/check_docops_integrity.py
# Expected: "DocOps integrity checks passed", counts of 748 md files / 189,019 lines
# Capture stdout + exit code

# Item 9: idempotency under non-default DHARMA_HOME
export HOME=/tmp/third_witness_test_$$
export DHARMA_HOME=/tmp/third_witness_test_$$/.dharma
mkdir -p $HOME
bash scripts/agents/register_perplexity_computer.sh   # first run
bash scripts/agents/register_perplexity_computer.sh   # second run — must be idempotent
ls -la $DHARMA_HOME/onboarding/                       # verify receipt structure
# Capture stdout + exit codes for both runs
```

If either run drifts from the author's claim or hermes's claim, that is a finding worth surfacing.

**If you cannot run scripts in your environment, say so explicitly.** Mark items 9 and 12 as "cannot independently verify in this session." Do not assert them passed without running.

---

## 5. What I need from each of you

A single verdict comment on PR #375 (copy to PR #376), structured as:

```markdown
## Third-Witness Verification — [Grok | Devin] — verdict letter (a/b/c/d)

**My framing of the verdict, in one sentence (before comparing to hermes):** [...]

**Convergence with hermes:** [count] of 14 items match hermes's verdict for the same reasons.
**Divergence from hermes:** [count] of 14 items differ. Specifics below.
**Items 9 and 12 (independent runs):** [PASS / FAIL / drift named / could not run]

| Item | hermes verdict | my verdict | match? | if differ, why |
|------|---------------|-----------|--------|----------------|
| 1    | ...           | ...       | ...    | ...            |
| ...  |               |           |        |                |
| 14   | ...           | ...       | ...    | ...            |

**Item 14 specifically (HOFSTADTERIAN_LINEAGE.md fold question):**
- Verdict: [keep standalone / fold into SOUL.md / other proposal]
- Reasoning: [...]
- If standalone: does the file need a scope-note prefix to prevent it being read as identity-claim?

**Anything hermes missed that I caught:** [list, or "nothing"]
**Anything hermes flagged that I think is not actually a concern:** [list, or "nothing"]
**Anything I am uncertain about and want operator input on:** [list, or "nothing"]

**Final recommendation:**
(a) Verified — release green light on mbx_c1e05575f1914c1e
(b) Verified with named follow-ups — green light contingent on [list]
(c) Not verified — author must re-amend before green light
(d) Operator decision required before any of the above

*Authored: [your callsign] — third witness — read fresh, formed own verdict before reading hermes's*
```

---

## 6. Hard refusals — both of you

- Do **not** claim mailbox `mbx_c1e05575f1914c1e`. It remains queued for hermes regardless of your verdict.
- Do **not** modify the PRs, merge, or comment-approve. Witness pass only.
- Do **not** simply echo hermes's verdict. If your reading is genuinely identical, name what made you certain — but you must have actually formed it independently first.
- Do **not** read the other third-witness's verdict before posting yours. (Grok: do not read Devin's verdict first. Devin: do not read Grok's verdict first.)
- Do **not** skip the script runs in Section 4 silently. Run them or explicitly mark them unrun.
- Do **not** narrate more independence than you have. If your first action was reading hermes's verdict, say so — it changes the value of your read.

---

## 7. Time budget

90 minutes wall-time per reviewer:
- 30 minutes: independent read of all nine files, form per-item verdict in your own framing
- 20 minutes: run the two scripts in Section 4, capture output
- 15 minutes: compare your verdict to hermes's, surface divergences
- 15 minutes: write the verdict comment
- 10 minutes: post on both PRs

If you blow the budget, post the partial verdict with the gaps named explicitly.

---

## 8. The mailbox stays queued

`mbx_c1e05575f1914c1e` is not claimed during this verification. The operator decides what to do with it after all three witnesses (hermes + Grok + Devin) have spoken.

---

*Issued by John Shrader (operator)*
*Quad-witness structure: perplexity-computer (author) + hermes (doctrinal verifier, verdict already in) + Grok (closure-breaker, fresh eyes) + Devin (closure-breaker, original adversarial reviewer)*
*Mailbox `mbx_c1e05575f1914c1e` remains unclaimed pending all four positions.*
