# Whole-repo archaeological audit — 2026-07-06

Read-only, history-aware swarm audit of the dharma_swarm codebase, run via a
67-agent multi-wave orchestration (16 parallel scout agents for cartography
and git-history mining, Opus-tier triage selecting 9 high-leverage clusters,
9 Opus deep-dive investigations, per-finding fresh-context adversarial
verification, and a final Opus synthesis pass). No code was changed as part
of this audit.

- **`synthesis.md`** — the final report. Start here.
- **`evidence_ledger.jsonl`** — one JSON object per verified cluster (C1-C9),
  each with its deep-dive analysis and per-finding verification verdicts
  (confirmed / weakened / rejected).
- **`scout_reports.jsonl`** — condensed output of the 16 scout-wave agents
  (cartography + git-history mining) that fed the triage stage.
- **`triage.json`** — the Opus triage pass that selected the 9 clusters and
  wrote their investigation briefs.

Git was unshallowed from 60 commits (3 days) to the full 1,319-commit history
on `origin/main` (2026-03-04 → 2026-07-06) before the history-mining wave ran.
