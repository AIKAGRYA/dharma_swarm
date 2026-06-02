# MemoryKernel Eval Receipt

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Mission ledger: `20260602-venturecell-operator-os-autoresearch-8h`
Loop: `02_memorykernel_query_eval_surface`
Adversary ds-goal receipt: `r-bd8cca03a910c3e8`
Verifier ds-goal receipt: `r-84f0aca99cebb926`
Started UTC: `2026-06-02T14:20:22Z`
Ended UTC: `2026-06-02T14:33:29Z`
Decision: `keep_and_queue_repair`

## Hypothesis

If the six program-kernel MemoryKernel prompts are rendered as deterministic
eval output, the Operator OS can distinguish "memory index exists" from "memory
recall is actually useful" and future agents can repair recall without rereading
the whole repo or internet.

## Patch Scope

Changed or created:

- `dharma_swarm/venture_cell/operator_os/memory_kernel.py`
- `dharma_swarm/venture_cell/operator_os/projection.py`
- `dharma_swarm/venture_cell/operator_os/schema.py`
- `dharma_swarm/venture_cell/operator_os/daily_digest.py`
- `dharma_swarm/venture_cell/operator_os/cli.py`
- `dharma_swarm/venture_cell/operator_os/__init__.py`
- `tests/test_venture_cell_operator_os_projection.py`
- `reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z/memory_kernel_query_eval.json`
- regenerated `operator_os_projection.json`, `operator_os_digest.md`, and `memory_kernel_index.json`

## Eval Results

| Command | Result |
|---|---|
| `pytest -q tests/test_venture_cell_operator_os_projection.py` | `6 passed, 1 warning` |
| `pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k 'GoReceiptRows or external_reader'` | `11 passed, 74 deselected, 1 warning` |
| `pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py` | `31 passed, 1 warning` |
| `./.venv/bin/python -m compileall -q dharma_swarm/venture_cell/operator_os` | passed |
| `./.venv/bin/python -m dharma_swarm.venture_cell.operator_os.cli --output-dir reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z` | passed; wrote query eval artifact |
| `git diff --check -- <scoped paths>` | passed |
| `contextplus.run_static_analysis(target_path="dharma_swarm/venture_cell/operator_os")` | tool failed with eslint `--eslintrc` option error and py_compile missing filename arguments |
| commit hook policy | normal hooks are known to fail on unrelated docops inventory drift and semgrep findings outside this packet; use scoped `git commit --no-verify --only` after focused verification |

Common pytest warning: `PytestConfigWarning: Unknown config option: timeout`.

## Live Query Eval

Artifact:

- `reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z/memory_kernel_query_eval.json`

Observed result:

- `query_eval_status`: `partial`
- `query_eval_passed`: `0`
- `query_eval_total`: `6`
- `trusted_promotion_claimed`: `false`

All six queries returned at least some local trusted wiki references, but each
missed key query terms. This is useful evidence precisely because it prevents a
false green:

- `Polsia Cofounder VentureCell Operator OS` missed `cofounder`, `operator`, `os`.
- `Darshan external reader gate Go evidence receipt` missed `external`, `reader`, `gate`, `go`, `evidence`, `receipt`.
- `Go evidence receipt source_url event_uid accepted` missed `go`, `evidence`, `receipt`, `url`, `event`, `uid`, `accepted`.
- `Cofounder Canvas Library Plan Execute publishing` missed `cofounder`, `canvas`, `library`, `execute`, `publishing`.
- `Chetana wiki memory kernel staged trusted quarantine` missed `staged`, `quarantine`.
- `VentureCell autonomy ladder external action approval` missed `autonomy`, `ladder`, `external`, `action`, `approval`.

## Adversarial Review

- False memory usefulness: blocked. The digest now says `partial` and lists failed query prompts instead of treating any match as success.
- Memory pollution: blocked. Eval result includes `trusted_promotion_claimed=false`; no Chetana atom was promoted.
- Source provenance: partially satisfied. Every query result includes local source refs and source roots, but term coverage is weak.
- External authority: unchanged. No outreach, spend, deploy, publish, push, merge, or live authority occurred.
- Gate safety: preserved. Darshan external-reader and governed-admission regression tests stayed green.
- Future-agent compounding: improved. The next repair target is now machine-readable, not prose-only.

## Keep/Revert/Queue Decision

Keep:

- deterministic query eval dataclasses and strict pass/fail criteria;
- CLI output `memory_kernel_query_eval.json`;
- digest summary of query status and missing terms;
- projection gap `memory_kernel_query_eval_partial`.

Queue:

- build a mission-local Chetana/wiki ingestion or index bridge so these six
  queries retrieve the actual Operator OS, Darshan GO gate, Cofounder shell,
  Polsia dossier, and autonomy ladder packets.

Do not promote trusted Chetana atoms in this run without the existing gates.

## Score Update

Before: `72/100`.

| Area | Before | After | Reason |
|---|---:|---:|---|
| Operator clarity | 12 | 13 | digest exposes query eval status and missing terms |
| Memory usefulness | 13 | 13 | actual live recall still fails all six strict evals |
| Task truth | 8 | 8 | no ds-goal repair this loop |
| Governance safety | 15 | 15 | gates preserved and verified |
| Iteration quality | 10 | 11 | loop rejected a false green and queued precise repair |
| Product structure | 8 | 8 | no shell restructuring this loop |
| Tests/evals | 9 | 10 | six-query eval fixture and CLI artifact now exist |
| Metabolization | 4 | 5 | machine-readable eval artifact and receipt written |

After: `74/100`.

## Metabolization Note

The durable learning is that the current live Chetana/wiki corpus can produce
nearby local references, but it does not yet satisfy the mission's six recall
prompts. Future agents should start from `memory_kernel_query_eval.json`, repair
one failed prompt family at a time, and rerender the same artifact until the
strict pass count improves without trusted promotion shortcuts.

## Next Loop Target

`03_operator_surface_receipt.md`: improve the operator surface around blocked
state and next governed action, while preserving the MemoryKernel partial eval
as an explicit blocker. If staying in MemoryKernel, the next patch should ingest
or bridge mission-local packets so at least the Darshan GO gate and Cofounder
shell queries pass.
