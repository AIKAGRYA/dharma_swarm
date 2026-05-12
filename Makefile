PYTHON ?= $(shell command -v python >/dev/null 2>&1 && echo python || echo python3)
PYTEST ?= pytest
PYRIGHT ?= pyright
DASHBOARD_DIR ?= dashboard

.PHONY: help xray xray-json compile test-smoke test-all ci-local dashboard-lint dashboard-build \
        semgrep gitleaks precommit-install precommit-run governance-baseline \
        prompt-governance prompt-lane-run packet-provenance packet-provenance-summary \
        agent-online-check

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
	@printf "  make prompt-governance # validate governed LLM prompt packs\n"
	@printf "  make prompt-lane-run LANE=... TARGET=... # create governed prompt work packet\n"
	@printf "  make packet-provenance COMMIT_MSG=... # check Packet-Id coverage\n"
	@printf "  make packet-provenance-summary # summarize Packet-Id bypass/rejection evidence\n"
	@printf "  make agent-online-check # validate AGENT_ONLINE node integrity\n"

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
	scripts/governance/run_semgrep_with_ca.sh --config .semgrep --metrics=off

semgrep-strict:
	scripts/governance/run_semgrep_with_ca.sh --config .semgrep --error --metrics=off

gitleaks:
	gitleaks detect --source . --redact --no-banner --exit-code 1

precommit-install:
	pre-commit install --install-hooks
	pre-commit install --hook-type commit-msg

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

test-hygiene:
	$(PYTHON) scripts/governance/check_test_hygiene.py

module-budget:
	$(PYTHON) scripts/governance/check_module_budget.py \
		--base-ref origin/main --head-ref HEAD

prompt-governance:
	$(PYTHON) scripts/governance/verify_prompt_pack.py \
		docs/governance/prompt_packs/slop_cleanup_subagents.json

prompt-lane-run:
	@test -n "$(LANE)" || (printf "LANE is required\n" >&2; exit 2)
	@test -n "$(TARGET)" || (printf "TARGET is required\n" >&2; exit 2)
	$(PYTHON) scripts/governance/prompt_lane_run.py --lane "$(LANE)" --target "$(TARGET)"

packet-provenance:
	@test -n "$(COMMIT_MSG)" || (printf "COMMIT_MSG is required\n" >&2; exit 2)
	$(PYTHON) scripts/governance/check_packet_provenance.py --commit-msg-file "$(COMMIT_MSG)"

packet-provenance-summary:
	$(PYTHON) scripts/governance/packet_provenance_summary.py

agent-online-check:
	$(PYTHON) scripts/governance/check_agent_online.py

governance-all: semgrep gitleaks mismatch-check test-hygiene module-budget prompt-governance

# ============================================================================
# Tier-A code-quality stack (added 2026-05-09)
# Python: vulture, radon, bandit, mypy, pyright, pytest-cov
# TS:     fallow (dashboard)
# Composite: `make quality` runs all and routes findings to BR proposals.
# ============================================================================

quality-reports:
	@mkdir -p quality-reports

vulture: quality-reports
	@printf "═══ vulture (Python dead code) ═══\n"
	$(PYTHON) -m vulture dharma_swarm/ .vulture_whitelist.py \
		--min-confidence 80 --sort-by-size \
		2>&1 | tee quality-reports/vulture.txt

radon-cc: quality-reports
	@printf "═══ radon — cyclomatic complexity ═══\n"
	$(PYTHON) -m radon cc dharma_swarm/ -a -nc --total-average \
		2>&1 | tee quality-reports/radon-cc.txt

radon-mi: quality-reports
	@printf "═══ radon — maintainability index ═══\n"
	$(PYTHON) -m radon mi dharma_swarm/ -nc -s \
		2>&1 | tee quality-reports/radon-mi.txt

bandit: quality-reports
	@printf "═══ bandit (security) ═══\n"
	$(PYTHON) -m bandit -r dharma_swarm/ -ll \
		2>&1 | tee quality-reports/bandit.txt

mypy: quality-reports
	@printf "═══ mypy (type check) ═══\n"
	$(PYTHON) -m mypy dharma_swarm/ \
		2>&1 | tee quality-reports/mypy.txt

pyright: quality-reports
	@printf "═══ pyright (strict type check) ═══\n"
	$(PYRIGHT) dharma_swarm/ --outputjson \
		> quality-reports/pyright.json 2> quality-reports/pyright.stderr || true

cov-threshold: quality-reports
	@printf "═══ pytest --cov (coverage report) ═══\n"
	$(PYTHON) -m pytest --cov=dharma_swarm --cov-report=term --cov-report=xml:quality-reports/coverage.xml -q --tb=line \
		2>&1 | tee quality-reports/pytest-cov.txt || true

fallow: quality-reports
	@printf "═══ fallow (dashboard TS dead code/duplication/complexity) ═══\n"
	@cd dashboard && npx --yes fallow check 2>&1 | tee ../quality-reports/fallow.txt || true

route-findings:
	@printf "═══ routing findings → governance proposals ═══\n"
	$(PYTHON) scripts/governance/route_quality_findings.py --all

# Composite: run everything, then route findings into BR proposal queue.
quality: vulture radon-cc radon-mi bandit mypy pyright cov-threshold fallow route-findings
	@printf "\n═══ Tier-A quality scan complete ═══\n"
	@printf "Reports:    quality-reports/\n"
	@printf "Proposals:  ~/.dharma/audit/quality/$$(date +%%Y-%%m-%%d)/proposals/\n"
	@printf "Evidence:   ~/.dharma/audit/quality/$$(date +%%Y-%%m-%%d)/findings.jsonl\n"

# Cheap subset for pre-commit: vulture + radon-cc only (fast)
quality-fast: vulture radon-cc
	@printf "fast quality scan complete (vulture + radon-cc)\n"
