# Independence Charter

**Status:** constitutional (outward engine). Subordinate to
`docs/governance/SOVEREIGN_MANIFEST.md` and
`docs/doctrine/OPERATIONAL_DOCTRINE.md`.
**Mechanical owners:** `scripts/audit/generate_client_report.py`,
`scripts/daemon/publish_public_ledger.py`.
**Price surface:** Full Audit is USD **2,500** flat
(`docs/reports/wedge_candidate_slate_v1.md:80`).

This charter exists so the $2,500 audit is an **unconflicted auditor**, not a
mirror looking at itself. The brake on an empty reactor is still the beach;
this document forbids selling that beach.

## Unconflicted auditor rules

1. **We never audit systems we build.** `dharma_swarm` and `vibe-halt` (and any
   git remote that normalizes to `github.com/aikagrya/dharma_swarm` or
   `github.com/amitabhainarunachala/vibe-halt`) are refused. The CLI exits 2
   and writes no `AUDIT_REPORT`. Citation: independence check in
   `scripts/audit/generate_client_report.py` (`FORBIDDEN_IDENTITY_NEEDLES`,
   `IndependenceError`).
2. **We never suppress failed invariant logs.** There is no hide-findings
   flag. Every miss is in `AUDIT_REPORT.md`, `AUDIT_REPORT.pdf`, and
   `audit_receipt.json`.
3. **All misses are published.** Lane 3
   (`scripts/daemon/publish_public_ledger.py`) posts hit **and** miss
   receipts to the public issue thread. A digest whose `misses` count does
   not match its `kind=miss` entries is refused (`miss_count_mismatch`).
4. **Pricing is flat and decoupled from audit outcome.** USD 2,500 is the
   Full Audit fee whether the suite returns zero misses or fifty. The
   receipt field `pricing.decoupling` is the string
   `flat fee decoupled from audit outcome`. Outcome does not change price.
   Lightning ($500) and retainers are separate SKUs; they do not discount
   or inflate this charter's Full Audit.

## What this charter is not

- It is not a claim that a foreign target was "verified safe."
- It is not permission to audit this organism and sell the receipt.
- It is not a substitute for Ring 3 human presence
  (`docs/governance/CONTINUITY_OF_INTENT.md`).

## Why (one sentence)

A self-rewriting system that certifies itself is the hall of mirrors named in
`docs/doctrine/OPERATIONAL_DOCTRINE.md:43`; an auditor that is also the
builder is the same mirror with an invoice.
