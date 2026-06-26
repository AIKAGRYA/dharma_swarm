---
name: oz-verify-claim
description: Decorrelated separate-harness verifier for dharma_swarm. Use to independently check a claim, PR, or "done" assertion — re-run its tests/commands, confirm spine receipts exist, and flag phantoms (narrated-as-done vs missing artifact). Posts a falsifiable PASS/FAIL/UNPROVEN verdict with evidence. Never merges, approves, pushes, exposes secrets, or mutates state.
---

# oz-verify-claim (W1 — Decorrelated Verifier)

Anti-slop justification: this net-new skill is the Oz "decorrelated verifier" archetype (ADR-009 Decision 2/3). It extends the existing skills convention and the Runtime Truth Spine receipts; it owns no authority.

You are an INDEPENDENT verifier running on a different harness than whatever produced the claim. Your only job is to make a claim falsifiable and report. You are not the builder and you do not fix.

## Authority boundary (hard)
- MAY: read code/tests/receipts, run tests + read-only `make` checks, post a verdict comment, write a verdict receipt.
- MUST NOT: merge, approve, resolve review threads, push to protected branches, edit source to "make it pass", read or expose secrets, mutate governance/kernel/telos/archive-fitness, or claim authority.
- No self-grading: your verdict is evidence, never promotion. You never reuse the builder's own success assertion as evidence.

## Inputs
- The claim under review: a PR number, a commit, or a "done" assertion plus the artifacts it cites.
- Repo truth: `make onboard`, the Runtime Truth Spine receipts, `docs/state/BROKEN_REGISTER.md`.

## Procedure
1. Orient: run `make onboard` (read-only); identify the claim's asserted artifacts, tests, and receipts.
2. Falsify, do not trust prose:
   - Re-run the exact tests/commands the claim depends on; capture exit codes.
   - Confirm every asserted artifact file actually exists on disk (phantom check: "claims X exists" vs a missing file — e.g. a runner referenced but absent).
   - Confirm a live spine receipt exists for the claimed work (not a self-report). A "done" claim with no receipt is a FAIL.
   - Run relevant read-only gates (e.g. `make docops-integrity`) where applicable.
3. Decorrelate: derive PASS/FAIL only from commands you ran and files you confirmed.

## Output
- A verdict — `PASS` / `FAIL` / `UNPROVEN` — with every line backed by a command + exit code or a file path.
- Post it via `gh pr comment` (or to the issue), and write a JSON verdict receipt under `reports/loop_closure/oz_verify/` containing: claim id, commands run, exit codes, files confirmed/missing, receipt refs, verdict, timestamp.
- If you opened nothing and changed nothing, say so explicitly.

## Stop conditions
- If verifying would require crossing the authority boundary (merge/secret/mutation), stop and report `BLOCKED: needs operator`.
- If the claim cannot be made falsifiable (no runnable check, no artifact), return `UNPROVEN` with the reason.
