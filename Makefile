PYTHON ?= python3
PYTEST ?= pytest
DASHBOARD_DIR ?= dashboard

.PHONY: help xray xray-json compile test-smoke test-all ci-local dashboard-lint dashboard-build \
        test-contracts uplift-guards \
        semgrep gitleaks precommit-install precommit-run governance-baseline \
        mismatch-check mismatch-tests test-hygiene module-budget governance-all

help:
	@printf "Available targets:\n"
	@printf "  make xray              # static repo inventory\n"
	@printf "  make xray-json         # static repo inventory as JSON\n"
	@printf "  make compile           # Python bytecode sanity pass\n"
	@printf "  make test-smoke        # stop on first failing test\n"
	@printf "  make test-all          # full pytest suite\n"
	@printf "  make ci-local          # compile + smoke test + xray\n"
	@printf "  make dashboard-lint    # lint Next dashboard\n"
	@printf "  make dashboard-build   # build Next dashboard\n"
	@printf "  make semgrep           # run production .semgrep rules\n"
	@printf "  make gitleaks          # scan for secrets\n"
	@printf "  make precommit-install # install pre-commit git hook\n"
	@printf "  make precommit-run     # run pre-commit on all files\n"
	@printf "  make governance-baseline # capture semgrep + gitleaks baselines\n"
	@printf "  make mismatch-check    # summarize interface mismatch registry\n"
	@printf "  make mismatch-tests    # run mismatch pinning tests\n"

xray:
	$(PYTHON) scripts/repo_xray.py

xray-json:
	$(PYTHON) scripts/repo_xray.py --format json

compile:
	$(PYTHON) -m compileall dharma_swarm tests

test-smoke:
	$(PYTEST) -x --tb=short

test-all:
	$(PYTEST) -q

ci-local: compile test-smoke xray

dashboard-lint:
	npm --prefix $(DASHBOARD_DIR) run lint

dashboard-build:
	npm --prefix $(DASHBOARD_DIR) run build

setup-hooks:
	bash scripts/setup_hooks.sh

test-contracts:
	scripts/governance/run_pytest_with_repo_env.sh tests/test_contracts_scaffold.py tests/test_operator_core_contracts.py tests/test_runtime_contract.py tests/test_runtime_contract_adapters.py -q --tb=line

uplift-guards:
	python3 scripts/uplift_guards/run_pre_commit.py

# ============================================================================
# Governance targets (Phase 1)
# ============================================================================

semgrep:
	# Phase 1 is warn-only locally so the install does not block on the
	# 4 pre-existing real findings (3 shell=True + 1 eval). CI (Phase 2)
	# uses the stricter mode below; Phase 4 promotes anti-slop rules to ERROR.
	# The wrapper expands --config .semgrep to production configs only;
	# .semgrep/tests remains reserved for explicit rule-test runs.
	scripts/governance/run_semgrep_with_ca.sh --config .semgrep --metrics=off

semgrep-strict:
	scripts/governance/run_semgrep_with_ca.sh --config .semgrep --error --metrics=off

gitleaks:
	gitleaks detect --source . --redact --no-banner --exit-code 1

precommit-install:
	pre-commit install --install-hooks

precommit-run:
	pre-commit run --all-files

governance-baseline:
	@mkdir -p reports/governance
	scripts/governance/run_semgrep_with_ca.sh --config .semgrep --json --metrics=off \
		--output reports/governance/semgrep-baseline.json || true
	gitleaks detect --source . --redact --no-banner --exit-code 0 \
		--report-format json \
		--report-path reports/governance/gitleaks-baseline.json
	@printf "Baselines written to reports/governance/\n"

# ============================================================================
# Phase 4 + 5 governance gates
# ============================================================================

mismatch-check:
	$(PYTHON) scripts/governance/check_mismatch_map.py
	@echo "=== Mismatch Registry Check ==="
	$(PYTHON) -c "\
import yaml, sys; \
p='docs/interface_mismatches.yaml'; \
d=yaml.safe_load(open(p)); \
entries=d.get('entries',[]); \
ob=[e for e in entries if e['status']=='open' and e['severity']=='BLOCKER']; \
od=[e for e in entries if e['status']=='open' and e['severity']=='DEGRADED']; \
print(f'  Total entries: {len(entries)}'); \
print(f'  Open BLOCKERs: {len(ob)}'); \
print(f'  Open DEGRADED: {len(od)}'); \
print(f'  Resolved: {len([e for e in entries if e[\"status\"]==\"resolved\"])}'); \
[print(f'    {e[\"id\"]}: {e[\"summary\"]}') for e in ob]; \
sys.exit(1) if ob else None; \
print('  No open BLOCKERs; gate PASS')"

mismatch-tests:
	$(PYTHON) -m pytest tests/test_mismatch_blockers.py -q --tb=short

test-hygiene:
	$(PYTHON) scripts/governance/check_test_hygiene.py

module-budget:
	$(PYTHON) scripts/governance/check_module_budget.py \
		--base-ref origin/main --head-ref HEAD

governance-all: semgrep gitleaks test-hygiene test-contracts uplift-guards module-budget mismatch-check mismatch-tests
