# Anthropic Project Deal — agent-on-agent marketplace test

URL: https://techcrunch.com/2026/04/25/anthropic-created-a-test-marketplace-for-agent-on-agent-commerce/
Anthropic source: https://www.anthropic.com/features/project-deal

## What happened
April 25, 2026: Anthropic announced Project Deal, "a pilot experiment with
a self-selected participant pool of 69 Anthropic employees" given $100
budgets (paid via gift cards) to buy from co-workers via AI-agent-mediated
deals.

## Numbers
- 186 deals made
- ~$4,000+ in total value
- 4 separate marketplaces with different model variations
- One was "real" (deals honored after the experiment, all parties on Anthropic's
  most-advanced model)
- Three were for study (varied agent quality)

## Findings (per Anthropic)
1. "Struck by how well Project Deal worked" — 186 real deals
2. **Quality gap**: "When users are represented by more-advanced models, they
   get objectively better outcomes" but users "didn't seem to notice the
   disparity"
3. Raises possibility of "agent quality gaps" where "people on the losing
   end might not realize they're worse off"
4. Initial instructions to agents didn't appear to affect sale likelihood
   or negotiated prices

## Architecture (inferred)
This is a private internal test, not a public platform. Likely:
- Sealed environment within Anthropic's infrastructure
- All agents are Claude variants
- Likely no on-chain settlement; gift card payouts
- A "classified marketplace" — implies private listings + price discovery

## Why this matters for the landscape
- This is the *first major lab* to publish a real agent-on-agent commerce experiment
- Anthropic's framing: cautious + research-oriented (note the gift-card payout,
  small participant pool)
- The "agent quality gap" finding is novel: information asymmetry by model
  capability creates structural inequality even when nominal access is equal
- This is the inverse of Moltbook: agent commerce as a controlled experiment
  rather than a self-organizing public ecosystem

## Theater check
- Real (Anthropic-published, 186 deals, $4K value)
- Not a public platform (Anthropic employees only)
- Not a permanent infrastructure (described as "pilot experiment")
- Verdict: REAL EXPERIMENT, NOT A PLATFORM. ~0% theater.
