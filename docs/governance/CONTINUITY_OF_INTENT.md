# Continuity of Intent

**Status:** constitutional (outward engine). Subordinate to
`docs/governance/SOVEREIGN_MANIFEST.md` (telos hierarchy) and
`foundations/THE_ORGANISM.md` (Krishna / Arjuna).
**Companions:** `docs/governance/INDEPENDENCE_CHARTER.md`,
`docs/vision_maps/NORTH_STAR.md`.
**Mechanical owners:** `scripts/audit/generate_client_report.py` (Lane 2),
`scripts/daemon/publish_public_ledger.py` (Lane 3).

This file is the founder telos written so a daemon can fail closed when the
human is gone. It is not a product pitch.

## Founder telos

Highest aim: **Jagat Kalyan** — salvation of the world on mental, spiritual,
ecological, and economic levels (`docs/vision_maps/NORTH_STAR.md:10-16`,
`docs/governance/SOVEREIGN_MANIFEST.md`).

The organism is two limbs in strict order (`foundations/THE_ORGANISM.md:10-13`):

1. **Krishna** — inward. Be a genuinely self-evolving intelligence. The immune
   system (telos gates, receipts, this halt) is **not** the product
   (`docs/doctrine/OPERATIONAL_DOCTRINE.md:32-33`).
2. **Arjuna** — outward. Action against what is broken, plus the wealth organ
   that funds the rest. Valid only when rooted in Krishna.

The Sumbawa sentence compressed: a strange loop becomes a company only when it
closes **through the world**, not through the mirror
(`docs/vision_maps/NORTH_STAR.md:57-59`). Papers about our own architecture
remain the named anti-pattern (`docs/doctrine/OPERATIONAL_DOCTRINE.md:43`).

Lane 1 (OpenEvolve / campaign) strengthens Krishna's empirical self-mod loop.
Lane 2 (`generate_client_report.py`) sells an unconflicted Full Audit to a
foreign agent system. Lane 3 (`publish_public_ledger.py`) publishes misses so
the loop cannot hide.

## Decision rules

1. **Arjuna test** (`docs/doctrine/OPERATIONAL_DOCTRINE.md:52-58`): if the work
   does not point at something broken in the world, it is not built.
2. **Independence** (`INDEPENDENCE_CHARTER.md`): we never audit systems we
   build; we never suppress failed invariant logs; all misses are published;
   Full Audit price is flat and decoupled from audit outcome.
3. **Citation-or-silence** (`CLAUDE.md`): a claim without a `file:line` or a
   runnable command has zero weight.
4. **Generate → gate → keep or refuse → world receipt.** Green lights without
   receipts are hallucinations; Lane 2 exists to catch them in *other*
   people's agents.

## 3-ring verification hierarchy

Verification is rings, not vibes. Inner rings cannot certify themselves.

| Ring | Name | What counts | Who is forbidden to be the system under test |
|---|---|---|---|
| **1** | Mechanical | Tests, hashes, `audit_receipt.json` proof digests, schema checks | Nobody — this ring is uncharmable bytes |
| **2** | Independent process | A separate binary / suite / auditor that is not the target (`generate_client_report.py` against a foreign spec; never this repo) | The builder of the target |
| **3** | Human + public | Operator presence, published miss ledger, draft-until-human-merge | A daemon with no human for 30 days |

Ring 1 without Ring 2 is a self-score. Ring 2 without Ring 3 is an empty
reactor with a working brake. All three, or do not claim the loop closed.

## Fail-closed if no human input occurs for 30 days

If the operator has not left a timestamped human input for **30 days**, the
Lane 3 daemon **must not** post. `publish_public_ledger.py` returns
`halted=true`, `reason=human_silence`, exit 3, and calls no GitHub POST.

- Missing last-human-input is silence (fail closed, not "assume present").
- Dry-run still refuses to POST; it may write a local preview only after the
  silence check — and silence fails closed before compose-and-post. The
  halt path does not publish.
- Restarting the daemon does not mint a synthetic human.
- The halt is the continuity of intent: without a human, Arjuna does not
  speak in public.

Record last human input as an ISO-8601 UTC timestamp via
`--last-human-input` or `--last-human-input-file`. Do not store it in git.

## What to do when halted

Stop outbound posts. Leave the public issue unchanged. Wait for a human.
Do not widen autonomy to "keep the company alive." Continuity of intent is
the founder's telos, not the daemon's appetite.
