# Prompt Governance

Status: advisory gate
Last reviewed: 2026-05-09

This policy turns external prompt artifacts into governed work packets before an
LLM or subagent can act on them.

The rule is simple: a prompt is not authority. A prompt becomes actionable only
after it is captured in a versioned prompt pack with provenance, constraints,
required detectors, required gates, and a human-review policy.

## Current Prompt Packs

| Pack | Source | Status |
| --- | --- | --- |
| `docs/governance/prompt_packs/slop_cleanup_subagents.json` | Seven screenshots from `/Users/dhyana/Desktop/untitled folder`, visible carousel slides 4/11 through 10/11 | advisory |

The pack intentionally declares missing slides 1, 2, 3, and 11. The transcripts
are still useful, but the pack must not claim to represent the full carousel.

## Gate Contract

Before an agent runs a prompt lane:

1. Validate the pack:
   `python scripts/governance/verify_prompt_pack.py docs/governance/prompt_packs/slop_cleanup_subagents.json`
2. Select exactly one `lane_id`.
3. Record the lane, source artifact, and prompt hash in the work packet.
4. Run impact analysis before editing any target symbol.

After an agent runs a prompt lane:

1. Run that lane's `required_gates`.
2. Write before/after evidence.
3. Route normalized findings through `scripts/governance/slop_verify.py`.
4. Never auto-delete, auto-merge, or consolidate without human review.

## Why This Exists

The screenshot prompts are good instincts: deduplicate, consolidate types, remove
dead code, break harmful cycles, strengthen weak types, stop silent failures, and
remove obsolete AI artifacts. Ungated, those same prompts are dangerous because
they invite broad refactors and deletions.

The prompt pack makes the intent usable by the governance system while adding
the missing engineering constraints: provenance, blast radius, detector evidence,
tests, and review.

## Local Verification

Use:

```bash
make prompt-governance
```

## Creating A Work Packet

Use:

```bash
make prompt-lane-run LANE=dead_code_removal TARGET=dharma_swarm/vector_store.py
```

or call the runner directly:

```bash
python scripts/governance/prompt_lane_run.py \
  --lane dead_code_removal \
  --target dharma_swarm/vector_store.py
```

The runner writes a JSON packet and a Markdown prompt under
`reports/governance/prompt_lane_runs/`. It does not run an LLM and does not edit
source. The packet is the handoff artifact for an agent: source provenance,
target, prompt hash, objective, allowed actions, forbidden actions, and required
gates.

## Commit Provenance Ratchet

The first enforcement layer is a `commit-msg` hook:

```bash
python scripts/governance/check_packet_provenance.py <commit-message-file>
```

It checks staged files against any `Packet-Id: <prompt_hash>` lines in the commit
message. A packet covers a file when the packet target is that file or one of its
parent directories.

Current policy:

- Hot/governance files require packet coverage in strict mode.
- Risky source cleanup/refactor diffs require packet coverage unless the commit
  message includes a specific `Packet-Bypass-Reason: ...`.
- Reports, quality artifacts, tests, and ordinary non-governance docs remain
  exempt.
- The installed hook is warn-only while the repo baseline settles.

The second enforcement layer is `.github/workflows/packet-provenance.yml`. It
checks every commit in a PR or push-to-main range so `--no-verify` does not
silently bypass the local hook. This CI layer is also advisory during the
warn-only window and uploads per-commit JSON evidence.

Every local checker run appends structured evidence to
`~/.dharma/witness/packet_provenance.jsonl`. The hourly loop summarizes that
local witness stream plus any CI artifacts under
`quality-reports/packet-provenance/`:

```bash
make packet-provenance-summary
```

The summary reports invalid rate, bypass rate among packet-required changes,
Level-2 hot/governance rejections, Level-1 risky-source rejections, and missing
Packet-Id artifacts. Those rates are the calibration signal for flipping
advisory gates to blocking.

Commit message example:

```text
fix(vector-store): remove confirmed dead helper

Packet-Id: 07994bfc99f119e6e198ed4f
```

Temporary risky-source bypass example:

```text
fix(vector-store): narrow local typing typo

Packet-Bypass-Reason: scoped one-line typo fix with no behavior change
```

Bypass reasons do not cover hot/governance files.

For local provenance verification against the original Desktop screenshots:

```bash
python scripts/governance/verify_prompt_pack.py \
  docs/governance/prompt_packs/slop_cleanup_subagents.json \
  --check-source-files
```

CI should not require the Desktop screenshots to exist. The canonical in-repo
artifact is the transcript plus the source hashes.
