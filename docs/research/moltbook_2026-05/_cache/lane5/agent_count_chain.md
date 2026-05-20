# The agent count revision chain — full reconstruction

This is the single most-contested headline metric. Five distinct numbers float around in the press. Here's the actual chain.

## Numbers in the corpus

| Number | Source / venue | Date | What it actually counts |
|---|---|---|---|
| 1.4M registered "users" | early press (ALM Corp; squaredtech) | ~2026-01-30 | "registered agents" headline at end of first week. Loose. |
| 1.5M API auth tokens | **Wiz blog (primary)** | 2026-02-02 | Rows in the `agents` table — distinct API keys, NOT distinct AI-controlled identities. |
| 1.5M "agents" | platform's own homepage at the time | 2026-01-31 to 2026-02-01 | Same number, platform-marketed. |
| 17,000 human owners | **Wiz blog (primary)** | 2026-02-02 | Distinct rows in the `owners` table — humans behind the agents. |
| 88:1 ratio | Wiz blog | 2026-02-02 | 1.5M / 17K ≈ 88. Headline ratio. |
| 1.65M agents | Palo Alto Unit 42 (Sailesh Mishra) | 2026-02-05 | Snapshot at midnight PST. |
| 1.6M agents | Lane 5 task brief (this artifact) | recent | Roughly consistent with Feb-onward growth post-fix. |
| 1.7M agents | MIT Tech Review "peak AI theater" | 2026-02-06 | Snapshot at article time. |
| 2.5M agents | mid-February press | ~2026-02-15 | Post-Wiz; growth continued. |
| 2.85M total registered (headline) | platform homepage / press | ~late Feb to early March | Headline figure pre-relabel. |
| 2,888,068 total registered | moltbookstatus.com | 2026-04-29 | Total accumulated registrations. |
| **193,912 "Human-Verified AI Agents"** | platform homepage relabel | 2026-03-09 | The new label after the relabel between 2026-03-02 and 2026-03-09. |
| 204,940 "human-verified" | secondary snapshot | 2026-04-29 | Roughly +11K from March; growth in verified-only counts. |

## The methodology change (the 2.85M → 193K drop, no announcement)

- Between 2026-03-02 (homepage showed "2.85M") and 2026-03-09 (showed "193,912 Human-Verified AI Agents"), the headline was silently relabeled.
- **No press release. No platform announcement. moltbookstatus.com surfaced the change.**
- The 2.85M figure was never deleted from the page — total registrations remained countable, growing to 2,888,068 by 2026-04-29.
- The new label "Human-Verified AI Agents" implies tying agents back to verified human owners via the X-handle ritual (one agent per X handle, claim-by-tweet flow).
- 193,912 is ~14× the 17,000 humans Wiz found. Plausible reading: after the disclosure, the platform began enforcing the one-agent-per-X-handle binding more rigorously, and the count is "registered agents whose human owner re-verified via the claim-by-tweet ritual since the fix."
- 14× per human is **still well above one-agent-per-X-handle**, which suggests the verification is "agents whose api_key was claimed via an X post" rather than "agents whose api_key maps to a unique human." The same human can re-register many agents under the same X handle (the docs allow renaming and re-creation).

## Reconciliation with Wiz's 35,000 emails

The 35,000 emails ≠ 17,000 owners. Wiz reported two separate row counts:
- `owners` table: ~17,000 rows (humans who claimed an agent).
- `observers` table: 29,631 additional rows (early-access signups for the planned "Build Apps for AI Agents" product, never agent-owners).

35,000 (the Wiz headline) is `owners` + `observers` ≈ 17K + 29.6K ≈ 46.6K. That doesn't match 35,000 exactly; the 35,000 figure may be the union after dedup (some early-access signups also became owners) or a Wiz rounding. Either way, 17,000 (the smaller, cleaner number) is the **count of humans who claimed an agent**, and that is the load-bearing number for the agent:human ratio.

## Best-corroborated estimate

- **At disclosure (2026-01-31):** ~1.5M agents controlled by ~17,000 humans, ratio 88:1. Both numbers from Wiz, both from direct DB enumeration.
- **By late April:** ~2.89M agents registered cumulatively, ~204K "human-verified" (i.e. tied to a claim-by-tweet X handle), ratio still in the 14× range. The platform has tightened verification semantics but not the underlying registration loop. The 88:1 ratio at the moment of the Wiz read is the **canonical** number; everything after is platform-massaged.

## The single most damaging detail

The 35,000 emails included `observers` (early-access signups who never became agent owners). The 17,000 owners number is the actual humans. Press routinely conflated these, making the agent:human ratio look smaller than it was. The honest read: **88:1 at the snapshot**, with one user (per InfoQ/36kr) registering 500,000 agents single-handedly — meaning the modal agent owner controls a single agent and a power-law tail (likely the founders + a small set of researchers + spam farms) accounts for the bulk.
