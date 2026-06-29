# Cybernetic Ratchet Loop

A 5-stage governance pipeline that audits code for slop classes, triages findings,
remediates with anti-gaming enforcement, re-audits with a fresh verifier, and
ratchets CI gates to prevent recurrence.

**Core invariant:** LLM proposes, deterministic oracle disposes. No LLM opinion
is ever recorded as truth. Every verdict is backed by a deterministic receipt
(exit code, test pass/fail, git diff, or schema validation).

## Pipeline Stages

1. **Audit** (`prompt_audit_run.py`): Auditor scans scoped prompts, produces
   schema-valid audit JSON per prompt. Schema-invalid output hard-aborts.
2. **Triage** (`prompt_audit_triage.py`): Deterministic routing — E2+ findings
   to IMPLEMENT, below-E2 to DEFER, dedup by failure_class, recurrence scoring.
3. **Remediate** (`prompt_audit_remediate.py`): Implementer works in an isolated
   git worktree. Red-before/green-after required. §8 anti-gaming checklist
   enforced on every fix diff. Write-set enforced via git diff (not self-report).
4. **Re-audit** (`prompt_audit_reaudit.py`): Fresh Verifier with falsification-first
   mandate. Receives only claim + deterministic evidence, never Implementer
   rationale. model_independence recorded honestly.
5. **Learn** (`prompt_audit_learn.py`): Only green CI advances. Drives existing
   ratchet engine via subprocess. Produces ratchet record + ledger entry.
   Optionally wires new gates into CI via `wire_ci_gate.py`.

## Files

| File | Description |
|------|-------------|
| `warrant.py` | Spec §4 warrant parser/validator/enforcer (write-set, expiry, budget) |
| `scoper.py` | Deterministic git-diff to changed-surface to selected prompts |
| `councils.py` | Resolves council_id + prompt_id to ported prompt file paths |
| `validate_audit.py` | JSON Schema validator for audit output (hard run-abort gate) |
| `runs.py` | Run directory orchestration (runs/YYYY-WW/\<run_id\>/ layout) |
| `oracle.py` | Deterministic oracle interface (CIOracle: real pytest/governance commands) |
| `agent_backend.py` | StubBackend / DroidBackend / ApiBackend for LLM stage invocation |
| `anti_gaming.py` | §8 anti-gaming checklist (no new skips, xfails, weakened assertions, etc.) |
| `wire_ci_gate.py` | Adds ratcheted gate steps to loop-ratchet-gates.yml |
| `prompt_audit_run.py` | Stage 1: Auditor |
| `prompt_audit_triage.py` | Stage 2: Deterministic triage |
| `prompt_audit_remediate.py` | Stage 3: Implementer + anti-gaming |
| `prompt_audit_reaudit.py` | Stage 4: Verifier (falsification-first) |
| `prompt_audit_learn.py` | Stage 5: Ratcheter + CI wiring |

## Setup

```bash
# From the repo root, always use the venv python with PYTHONPATH=.
export PYTHONPATH=.
PYTHON=/Users/dhyana/dharma_swarm/.venv/bin/python
```

## Run

```bash
# Run a single stage
$PYTHON scripts/governance/loop/prompt_audit_run.py --warrant <warrant.yaml> --base-ref <ref> --head-ref <ref>

# Full pipeline: chain all 5 stages in sequence (each reads the previous stage's output)
```

## Test

```bash
# All loop tests (325+ tests covering all stages, anti-gaming, e2e integration)
$PYTHON -m pytest tests/governance/loop/ -q

# Lint
$PYTHON -m ruff check scripts/governance/loop/ --select=E,F,W --ignore=E501,W291,W293

# Typecheck
$PYTHON -m py_compile scripts/governance/loop/*.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOOP_AGENT_BACKEND` | `stub` | Backend selection: `stub`, `droid`, or `api` |
| `LOOP_RUNS_DIR` | `/Users/dhyana/Desktop/complexity_code_testing_prompts/runs/` | Root directory for run artifacts |
| `LOOP_DROID_PATH` | `/Users/dhyana/.local/bin/droid` | Path to the droid CLI (for droid backend) |
| `LOOP_DROID_AUTO_LEVEL` | `high` | Auto-approval level for droid CLI (`low`, `medium`, `high`) |

## Exit Codes

- `0`: Success / no finding
- `1`: Finding detected (stage-appropriate)
- `2`: Environment or hard error (abort)
