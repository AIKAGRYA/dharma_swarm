# State Directory Owners

This register documents code paths that may directly reference `~/.dharma`.
New entries must name the owned path slice, read/write behavior, and why the
access does not bypass the canonical runtime-state contract.

## PTR Meta Artifacts

Owner files:

- `dharma_swarm/ptr_metric.py`
- `dharma_swarm/ptr_integrity.py`
- `scripts/ptr_integrity_probe.py`

Owned path slice:

- `~/.dharma/meta/ptr_score.json`
- `~/.dharma/meta/ptr_history.jsonl`
- `~/.dharma/meta/repo_integrity.json`
- `~/.dharma/meta/governance_integrity.json`

Contract:

PTR is a shadow-only, negative-authority cybernetic metric. Runtime modules
must stay pure and cheap: `ptr_metric.py` computes/persists the derived PTR
score only when explicitly called, and `ptr_integrity.py` only reads small JSON
artifacts produced out of band. Expensive checks are isolated in
`scripts/ptr_integrity_probe.py`, which writes the small repo/governance
integrity artifacts under `~/.dharma/meta`.

PTR artifacts do not grant ALLOW, raise autonomy, infer operator consent, or
bypass TelosGatekeeper/PolicyCompiler. Missing, stale, malformed, provisional,
or low-coverage evidence withholds authoritative PTR.
