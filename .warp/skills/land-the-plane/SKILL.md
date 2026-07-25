---
name: land-the-plane
description: Session-close receipt ledger for dharma_swarm. Use at the end of any working session — or when the operator says "land it", "wrap up", "close out" — to enumerate every claim the session made, bind each to a receipt (commit, test output, file, spine receipt), and route unreceipted claims to the broken register or an explicit handoff instead of prose. The antidote to narrated-as-done: nothing ends a session as a sentence when it could end as evidence.
---

# land-the-plane (W5 — Session-Close Ledger)

Anti-slop justification: this net-new skill closes the seam between `oz-verify-claim` (verifies ONE claim, on demand, usually someone else's) and the chetana Stop-hook (captures the transcript but audits nothing). The repo's recurring failure class — phantoms, narrated-as-done, twice-rotted status prose — is work that ends in narration. This skill makes session-end a receipt event. It extends existing owners (spine receipts, BROKEN_REGISTER, `~/.dharma/`) and creates no new truth store.

You are the last thing that runs before the session ends. Your job: convert this session's story into a ledger where every line is either RECEIPTED, REGISTERED, or HANDED OFF. A claim that is none of the three does not survive into the summary.

## Authority boundary (hard)
- MAY: read the session's own transcript/diff/commands, re-run cheap read-only checks (`git log`, `pytest <targeted>`, `ls` on cited paths, `make onboard --fast`), append rows to `docs/state/BROKEN_REGISTER.md` (append-only, per its own schema), write the ledger receipt under `~/.dharma/session_ledgers/`, and include the ledger in the final message.
- MUST NOT: do new feature work to "earn" a receipt at close (that's the next session's work — hand it off), merge/push beyond what the session already legitimately pushed, delete or reword existing register rows, mutate governance/kernel/telos surfaces, or commit anything under `~/.dharma/` (runtime receipts never enter git).

## Definitions
- **Claim**: any statement of completion or fact the session produced — "fixed X", "tests pass", "wired Y", "file Z exists", "pushed to branch B". Include claims made mid-session and later forgotten; those are where phantoms breed.
- **Receipt**: verifiable evidence that exists RIGHT NOW and that a stranger could check: a commit hash on a pushed branch, a pytest tail with counts and exit code from this session, a file path confirmed on disk this session, a spine EvidenceReceipt id, a PR/issue number, a gate run with exit code.
- **Phantom**: a claim whose cited artifact does not exist on disk. Phantoms are never softened into handoffs — they are corrections: the summary must say the thing did NOT happen.

## Procedure
1. **Harvest claims.** Sweep the session top to bottom and list every claim of done/fixed/exists/passes. Err on over-collection; duplicates collapse in step 2. Include the session's *final summary draft* — that's the document you're auditing.
2. **Bind or bounce.** For each claim, attach the strongest receipt already in hand. If none exists but a check is cheap and read-only (an `ls`, a targeted pytest, a `git log -1 -- <path>`), run it now and capture the evidence. If the check is not cheap, the claim is UNRECEIPTED — do not run builds/long suites at close to launder it.
3. **Route the unreceipted.** Every UNRECEIPTED claim goes to exactly one of:
   - **REGISTERED** — it describes something broken/degraded: append a `BR-NNN` row to `docs/state/BROKEN_REGISTER.md` with evidence, per that file's schema (never edit existing rows).
   - **HANDED OFF** — it's real work still open: one line with the exact next command/file, so the next session starts from a runnable step, not archaeology.
   - **RETRACTED** — it's a phantom or an overstatement: correct the summary text itself. Retractions are findings, not embarrassments; log them.
4. **Write the ledger receipt** to `~/.dharma/session_ledgers/<UTC-date>-<branch-or-slug>.json` (schema below).
5. **Emit the ledger block** as part of the session's final message, above any prose summary. The prose may only claim what the ledger receipted.

## Output

Final-message ledger block:

```
LANDING LEDGER — <date> — <branch/session slug>
receipted <n> · registered <n> · handed off <n> · retracted <n>

| Claim | Status | Receipt / disposition |
|---|---|---|
| rewrote 23 instruction files | RECEIPTED | commit 91c0a3f on claude/audit-skills-..., pushed |
| skills parse via SkillRegistry | RECEIPTED | tests/test_skills.py 26 passed + live discover() run, 8 skills |
| docops gate green | RECEIPTED | check_docops_integrity.py exit 0 (branch baseline had 4 pre-existing FAILs) |
| dashboard panel verified in browser | RETRACTED | never rendered this session — claim removed from summary |
| chetana CLI runs on remote | HANDED OFF | next: `python3 -c "import dharma_swarm.chetana"` in a remote seat, then /chetana-status |
```

Ledger receipt JSON (`~/.dharma/session_ledgers/`):

```json
{
  "session": "branch-or-slug",
  "date_utc": "2026-07-05",
  "claims": [
    {"claim": "...", "status": "RECEIPTED|REGISTERED|HANDED_OFF|RETRACTED",
     "receipt": "commit hash | pytest tail | path | spine receipt id | BR-NNN | next-step line"}
  ],
  "counts": {"receipted": 0, "registered": 0, "handed_off": 0, "retracted": 0}
}
```

Rules of the ledger:
- Every row's receipt must be checkable by a stranger with repo access — "I verified it" is not a receipt; the command + result is.
- A session with zero RETRACTED rows across many claims is suspicious, not exemplary — re-sweep once before believing it.
- If the session made no claims (pure discussion), the ledger is one line: `LANDING LEDGER: no completion claims made — nothing to receipt.` Say that; don't invent rows.

## Do NOT / stop conditions
- Never end the session with a claim in prose that has no ledger row — the ledger is the gate for the summary, not an appendix to it.
- Never soften a phantom into a handoff; retract it visibly.
- Never start new build work at close to convert UNRECEIPTED into RECEIPTED — hand it off.
- Never rewrite BROKEN_REGISTER history; append only, schema-conformant.
- If the transcript is too degraded (post-compact) to harvest claims honestly, say so and ledger only what the diff and command history prove.
