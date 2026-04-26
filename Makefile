PYTHON ?= python3
PYTEST ?= pytest
DASHBOARD_DIR ?= dashboard

.PHONY: help xray xray-json compile test-smoke test-all ci-local dashboard-lint dashboard-build \
        semgrep gitleaks precommit-install precommit-run governance-baseline

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
	@printf "  make semgrep           # run .semgrep/ rules\n"
	@printf "  make gitleaks          # scan for secrets\n"
	@printf "  make precommit-install # install pre-commit git hook\n"
	@printf "  make precommit-run     # run pre-commit on all files\n"
	@printf "  make governance-baseline # capture semgrep + gitleaks baselines\n"

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
	$(PYTEST) tests/test_contracts.py tests/test_private_access.py -v --tb=short

# ============================================================================
# Governance targets (Phase 1)
# ============================================================================

semgrep:
	# Phase 1 is warn-only locally so the install does not block on the
	# 4 pre-existing real findings (3 shell=True + 1 eval). CI (Phase 2)
	# uses the stricter mode below; Phase 4 promotes anti-slop rules to ERROR.
	semgrep --config .semgrep --metrics=off

semgrep-strict:
	semgrep --config .semgrep --error --metrics=off

gitleaks:
	gitleaks detect --source . --redact --no-banner --exit-code 1

precommit-install:
	pre-commit install --install-hooks

precommit-run:
	pre-commit run --all-files

governance-baseline:
	@mkdir -p reports/governance
	semgrep --config .semgrep --json --metrics=off \
		--output reports/governance/semgrep-baseline.json || true
	gitleaks detect --source . --redact --no-banner --exit-code 0 \
		--report-format json \
		--report-path reports/governance/gitleaks-baseline.json
	@printf "Baselines written to reports/governance/\n"
