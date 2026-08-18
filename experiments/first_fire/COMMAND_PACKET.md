# First-fire plumbing — command packet

**Status:** drafted, not executed.  
**Bit purchased if valid:** do applier + tests + rollback + keep compose on a real diff.  
**Not purchased:** DGM, SWE uplift, self-funding, live-organism mutation.

Converged spec (adversarial round 3): CI/scratch; `DarwinEngine.apply_diff_and_test`; non-empty diff; toy module nothing imports; planted red then real green; one-shot dated grant consumed when the pair starts; operator merges this packet; receipt invalid without diff-hash + `applied: true` on green.

## Refuse

- hostname `meghadharma-cloud`
- workspace `/root/dharma_swarm` (live pin)
- empty diff / `skipped: true` counted as success
- grant missing, expired, or already `consumed_at`
- diff path ≠ `experiments/first_fire/probe.py`

## Land this packet (this PR)

Files:

- `experiments/first_fire/probe.py` — toy; `spark()` returns `1`
- `experiments/first_fire/test_probe.py` — `spark()` must be int in `{1, 2}`
- `scripts/first_fire_plumbing.py` — the named runner
- `experiments/first_fire/GRANT.example.json`
- `.github/workflows/first-fire.yml` — `workflow_dispatch` only (does not fire on push)

Operator merge of this PR is the human gate for *landing the fuse*, not for lighting it.

## Mint a grant (operator)

Copy the example. Set `expires_at` in the next 24h. Do not reuse a consumed grant.

```bash
cp experiments/first_fire/GRANT.example.json /tmp/FIRST_FIRE_GRANT.json
# edit grant_id, granted_by, expires_at
```

## Light (CI — preferred)

Actions → **First-fire plumbing** → Run workflow. Paste grant JSON into the input. Download the receipt artifact.

Or, on a laptop / CI runner that is **not** megha:

```bash
export DHARMA_EVOLUTION_WORKTREE_ROOT="$HOME/.dharma/evolution_worktrees"
python3 scripts/first_fire_plumbing.py \
  --grant /tmp/FIRST_FIRE_GRANT.json \
  --receipt /tmp/first_fire_receipt.json
```

## Valid receipt

`valid: true` only if:

1. planted-red `pass_rate < 1` and file restored to `return 1`
2. real-green `pass_rate == 1` and file has `return 2` (`applied: true`)
3. both diffs have a sha256 (non-empty)

Anything else is a refusal or a fake green. Do not file it as CLOSED_LIVE.

## After a valid receipt

Stop. Do not widen the allowlist. Do not fire again without a new dated grant. Resize megha remains a halt decision, not a prize for this bit.
