# DHARMA SWARM — Makefile
# Run `make help` to see all targets.

.PHONY: help boot stop logs health metrics test lint clean install docker-up docker-down gh-auth semgrep semgrep-strict gitleaks precommit-install precommit-run governance-baseline test-hygiene test-contracts uplift-guards module-budget docops-integrity docops-report memory-kernel-readiness operator-prod-smoke governance-all onboard go-fmt-check go-test go-vet go-ci

PYTHON ?= python3
GO ?= go
GOFMT ?= gofmt
SEMGREP ?= scripts/governance/run_semgrep_with_ca.sh
SWARM_PLIST := $(HOME)/Library/LaunchAgents/com.dharma.swarm.plist
STATE_DIR    := $(HOME)/.dharma
GO_EVIDENCE_MODULE := tools/evidence_ingestor_go
GO_SDK_MODULE := tools/go_sdk
GO_GITHUB_INGESTOR_MODULE := tools/github_ingestor_go
GO_WORLD_SIGNAL_INGESTOR_MODULE := tools/world_signal_ingestor_go
GO_MODULES := $(GO_SDK_MODULE) $(GO_EVIDENCE_MODULE) $(GO_GITHUB_INGESTOR_MODULE) $(GO_WORLD_SIGNAL_INGESTOR_MODULE)
GO_CACHE_DIR ?= /tmp/dharma-swarm-go-build
GO_MOD_CACHE_DIR ?= /tmp/dharma-swarm-go-mod

help:
	@echo ""
	@echo "DHARMA SWARM — available targets:"
	@echo ""
	@echo "  make install      Install Python deps (pip install -e .[dev])"
	@echo "  make boot         Start the swarm as a background service (macOS)"
	@echo "  make stop         Stop the background service"
	@echo "  make restart      Stop + start"
	@echo "  make logs         Tail swarm logs"
	@echo "  make health       Check health API (curl localhost:7433/health)"
	@echo "  make metrics      Show full metrics (curl localhost:7433/metrics)"
	@echo "  make loops        Show loop status (curl localhost:7433/loops)"
	@echo "  make test         Run test suite"
	@echo "  make lint         Run ruff linter"
	@echo "  make clean        Remove .pyc and __pycache__"
	@echo "  make docker-up    Start via docker-compose (includes health + cron)"
	@echo "  make docker-down  Stop docker-compose stack"
	@echo "  make gh-auth      Authenticate gh CLI (needed for Guardian Crew issues)"
	@echo "  make live         Run dgc orchestrate-live in foreground (dev mode)"
	@echo "  make semgrep      Run governance Semgrep rules"
	@echo "  make gitleaks     Scan for secrets"
	@echo "  make precommit-run Run pre-commit on all files"
	@echo "  make governance-baseline Capture scanner baselines"
	@echo "  make test-contracts Run governance contract tests"
	@echo "  make uplift-guards Run uplift pre-commit guards"
	@echo "  make docops-integrity Run machine-verifiable documentation checks"
	@echo "  make docops-report Generate local DocOps JSON/Markdown reports"
	@echo "  make memory-kernel-readiness Run read-only MemoryKernel readiness gates"
	@echo "  make operator-prod-smoke Run fast read-only operator production smoke"
	@echo "  make onboard      Render current operating reality (active track, live ops, broken register, axioms)"
	@echo "  make go-ci        Run Go evidence sense-organ fmt/vet/test gates"
	@echo ""

install:
	pip install -e ".[dev]"

boot:
	@mkdir -p $(STATE_DIR)/logs
	@cp com.dharma.swarm.plist $(SWARM_PLIST)
	@launchctl unload $(SWARM_PLIST) 2>/dev/null || true
	@launchctl load $(SWARM_PLIST)
	@echo "Swarm loaded. Logs: tail -f $(STATE_DIR)/logs/swarm.log"

stop:
	@launchctl unload $(SWARM_PLIST) 2>/dev/null || true
	@echo "Swarm stopped."

restart: stop boot

logs:
	@tail -f $(STATE_DIR)/logs/swarm.log 2>/dev/null || echo "No log yet — run 'make boot' first"

health:
	@curl -s http://localhost:7433/health | python3 -m json.tool

metrics:
	@curl -s http://localhost:7433/metrics | python3 -m json.tool

loops:
	@curl -s http://localhost:7433/loops | python3 -m json.tool

providers:
	@curl -s http://localhost:7433/providers | python3 -m json.tool

telos:
	@curl -s http://localhost:7433/telos | python3 -m json.tool

guardian:
	@curl -s http://localhost:7433/guardian | python3 -m json.tool | python3 -c "import sys,json; print(json.load(sys.stdin)['report'])"

live:
	TINY_ROUTER_BACKEND=heuristic dgc orchestrate-live

test:
	python -m pytest tests/ -q --tb=short -x -m "not slow and not docker and not network"

test-fast:
	python -m pytest tests/ -q --tb=line -x --timeout=10

lint:
	ruff check dharma_swarm/ --select=E,F,W --ignore=E501

syntax-check:
	@python3 -c "\
import ast; from pathlib import Path; \
errors = [f'{f.name}:{e.lineno}: {e.msg}' for f in Path('dharma_swarm').glob('*.py') \
          for e in [None] if (lambda: (lambda e: e)(None))() or True \
          if (setattr(__builtins__, '_', None) or True)]; \
[print(f'Checking {len(list(Path(\"dharma_swarm\").glob(\"*.py\")))} files...')] and \
[print('OK: all clean') if not [print('FAIL:', f) for f in \
    [f'{p.name}:{e.lineno}: {e.msg}' for p in Path('dharma_swarm').glob('*.py') \
     for e in [None] if True]] else None]"
	@python3 -c "\
import ast; from pathlib import Path; errs=[] ; \
[errs.append(f'{f.name}:{e.lineno}') for f in Path('dharma_swarm').glob('*.py') \
 for _ in [None] if (lambda f=f: \
   [errs.append(f'{f.name}') for e in [None] \
    if not (__import__('builtins').__dict__.update({'_e': None}) or True)])()]; \
print('syntax check done')"
	python3 -c "import ast; from pathlib import Path; errs=[]; [errs.append(f.name) or print(f'FAIL: {f.name}') for f in Path('dharma_swarm').glob('*.py') if not __import__('ast').parse(f.read_text()) is not None or False]; print(f'Checked {len(list(Path(\"dharma_swarm\").glob(\"*.py\")))} files, {len(errs)} errors')" || \
	python3 -c "import ast; from pathlib import Path; [ast.parse(f.read_text()) for f in Path('dharma_swarm').glob('*.py')]; print('All syntax OK')"

gh-auth:
	gh auth login

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

docker-up:
	@cp .env.example .env 2>/dev/null || true
	docker-compose up -d --build swarm
	@echo "Swarm running in Docker. Health: curl http://localhost:7433/health"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f swarm

# ============================================================================
# Governance targets (Phase 1)
# ============================================================================

semgrep:
	# Phase 1 is warn-only locally so the install does not block on the
	# 4 pre-existing real findings (3 shell=True + 1 eval). CI (Phase 2)
	# uses the stricter mode below; Phase 4 promotes anti-slop rules to ERROR.
	# The wrapper expands --config .semgrep to production configs only;
	# .semgrep/tests remains reserved for explicit rule-test runs.
	$(SEMGREP) --config .semgrep --metrics=off

semgrep-strict:
	$(SEMGREP) --config .semgrep --error --metrics=off

gitleaks:
	gitleaks detect --source . --redact --no-banner --exit-code 1

precommit-install:
	pre-commit install --install-hooks

precommit-run:
	pre-commit run --all-files

governance-baseline:
	@mkdir -p reports/governance
	$(SEMGREP) --config .semgrep --json --metrics=off \
		--output reports/governance/semgrep-baseline.json || true
	gitleaks detect --source . --redact --no-banner --exit-code 0 \
		--report-format json \
		--report-path reports/governance/gitleaks-baseline.json
	@printf "Baselines written to reports/governance/\n"

# ============================================================================
# Phase 4 governance gates
# ============================================================================

test-hygiene:
	$(PYTHON) scripts/governance/check_test_hygiene.py

test-contracts:
	scripts/governance/run_pytest_with_repo_env.sh -q \
		tests/test_contracts_scaffold.py \
		tests/test_operator_core_contracts.py \
		tests/test_runtime_contract.py \
		tests/test_runtime_contract_adapters.py \
		--tb=line

uplift-guards:
	python3 scripts/uplift_guards/run_pre_commit.py

module-budget:
	$(PYTHON) scripts/governance/check_module_budget.py \
		--base-ref origin/main --head-ref HEAD

docops-integrity:
	$(PYTHON) scripts/docops/check_docops_integrity.py

docops-report:
	@mkdir -p reports/docops
	$(PYTHON) scripts/docops/check_docops_integrity.py \
		--report-json reports/docops/check.json \
		--inventory-json reports/docops/corpus_inventory.json \
		--inventory-markdown reports/docops/corpus_inventory.md

memory-kernel-readiness:
	$(PYTHON) scripts/memory_kernel_readiness.py --repo-root . --dry-run
	$(PYTHON) scripts/memory_writer_sentinel.py --repo-root . --ci
	$(PYTHON) scripts/memory_context_eval.py --repo-root . --run-default-cases --fail-on-hard-failure --dry-run
	$(PYTHON) scripts/memory_context_shadow_sweep.py --repo-root . --fail-on-hard-failure --dry-run

operator-prod-smoke:
	$(PYTHON) scripts/operator_prod_smoke.py --repo-root .

governance-all: semgrep gitleaks test-hygiene test-contracts uplift-guards module-budget docops-integrity

# Single-door onboarding: prints the current operating reality from existing
# owners (ACTIVE_TRACK.yaml, LIVE_OPS_DASHBOARD.md, BROKEN_REGISTER.md,
# ACTIVE_SURFACE_MANIFEST.yaml). Always exits 0. Run this before any build
# session — humans and agents both.
onboard:
	$(PYTHON) scripts/governance/agent_onboard.py

# ============================================================================
# Go evidence sense-organ gates (Track G)
# ============================================================================

go-fmt-check:
	@for mod in $(GO_MODULES); do \
		files="$$( $(GOFMT) -l $$mod )"; \
		if [ -n "$$files" ]; then \
			printf "Go files need gofmt in %s:\n%s\n" "$$mod" "$$files"; \
			exit 1; \
		fi; \
	done

go-test:
	@mkdir -p $(GO_CACHE_DIR) $(GO_MOD_CACHE_DIR)
	@for mod in $(GO_MODULES); do \
		echo "go test ./... in $$mod"; \
		( cd $$mod && GOCACHE=$(GO_CACHE_DIR) GOMODCACHE=$(GO_MOD_CACHE_DIR) $(GO) test ./... ) || exit 1; \
	done

go-vet:
	@mkdir -p $(GO_CACHE_DIR) $(GO_MOD_CACHE_DIR)
	@for mod in $(GO_MODULES); do \
		echo "go vet ./... in $$mod"; \
		( cd $$mod && GOCACHE=$(GO_CACHE_DIR) GOMODCACHE=$(GO_MOD_CACHE_DIR) $(GO) vet ./... ) || exit 1; \
	done

go-ci: go-fmt-check go-vet go-test
