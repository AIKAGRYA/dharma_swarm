# Runner — run the instrument, don't trust the prose

The adversarial review's #1 finding: a library whose pitch is "we route to ground
truth" shipped demos that were **inert markdown** — every "Demonstration run" was
trust-me prose, and two of five didn't reproduce. The fix is this: an executable
runner so any demo can be **regenerated and verified**, not believed.

```bash
python3 docs/stop-the-slop/runner/slop_probe.py complexity --path dharma_swarm
python3 docs/stop-the-slop/runner/slop_probe.py cycles     --path dharma_swarm
python3 docs/stop-the-slop/runner/slop_probe.py slop-index --path dharma_swarm
```

- **complexity** → routes to `radon cc` (the *named* tool). If radon is absent it says
  `UNASSESSED` and refuses to substitute a homemade proxy — the substitution was the
  exact defect the reviewer caught.
- **cycles** → AST import graph + Tarjan SCC, `TYPE_CHECKING` excluded. Prints the
  load-time cyclic SCCs (currently **1**: provider/router — mainline, fix unmerged).
- **slop-index** → composite, **scope disclosed per signal**, and states that only
  2 of 8 signals are ratchet-gated today.

Exit code is non-zero on a RED signal, so it can gate CI.

**Status (v0.0.1 of the runner):** covers 3 of the highest-value signals as the
template. v0.1.0 = a script per prompt + regenerate every demo from runner output +
pin advisory-DB snapshots so demos stay falsifiable. This runner is the proof that
"run it yourself" beats "trust my markdown" — and it already caught two demo errors
the prose review found, plus one more (`analyze_repo` path) on first execution.
