# RSI / DGM Lab — 50-Round Run Record (2026-08-09)

**Command:**
```
python3 -m dharma_swarm.dgc_cli evolve daemon --cycles 50 --interval 5 --shadow \
  --single-model --model claude-code --token-budget 500000
```
(Run from `/root/dharma_swarm` — a symlink to the checkout, required because the daemon scans
`$HOME/dharma_swarm/dharma_swarm`; run in the sandbox at 13:55–14:03 UTC.)

**Result: 50 cycles completed, 0 proposals generated, 0 fitness records.**

- Every proposal attempt (150 total — 3 target files per cycle) failed with
  `LLM proposal generation failed: OPENROUTER_API_KEY not set` (run log; count via
  `grep -c 'proposal generation failed'` = 150).
- `dgc evolve trend` after the run: "No fitness data yet."
- Root cause receipt: the evolve daemon constructs its LLM lane as
  `provider = swarm._router.get_provider(ProviderType.OPENROUTER)`
  (`dharma_swarm/terminal_commands/evolution.py:134-135` and :198), ignoring both the
  `--model claude-code` argument and the router's fallback chain — while the working
  ClaudeCodeProvider lane completed real tasks in the same session
  (`~/.dharma/traces/traces_2026-08-09.jsonl`).
- Second defect: before the symlink, the daemon reported
  `No Python files found in /root/dharma_swarm/dharma_swarm` — the scan path is home-relative,
  not checkout-relative (run log, first launch 13:53 UTC).

**Interpretation:** the DGM lab is real, safe to run (shadow mode never applied a diff), and
currently brainless outside the founder's keyed environment. Wiring it to the same provider
chain the orchestrator uses (it already holds `swarm._router`) — or setting
`OPENROUTER_API_KEY` — is the single unblock for a genuine 50-round result. Re-run this exact
command afterward and this record becomes the baseline to compare against.

Raw log preserved in the session scratchpad (`rsi_lab_run.log`, 160 lines; not committed —
runtime receipts stay out of git per CLAUDE.md).
