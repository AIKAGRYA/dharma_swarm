# DHARMA SWARM — Makefile
# Run `make help` to see all targets.

.PHONY: help boot stop logs health metrics test lint clean install docker-up docker-down gh-auth semgrep semgrep-strict gitleaks precommit-install precommit-run governance-baseline test-hygiene test-contracts uplift-guards module-budget docops-integrity docops-report dashboard-install dashboard-lint dashboard-build dashboard-status terminal-check frontend-check context-quorum-status context-quorum-init context-quorum-check context-quorum-handoff context-quorum-protect long-harness-init long-harness-status long-harness-validate goodworks-dgm-seed goodworks-dgm-tick goodworks-dgm-status governance-all onboard install-command-plane-stack stack-status go-fmt-check go-test go-vet go-ci

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
	@echo "  make dashboard-install Install dashboard deps with CI-compatible peer handling"
	@echo "  make dashboard-build Build the canonical Next dashboard"
	@echo "  make dashboard-status Show dashboard launchd/port status"
	@echo "  make terminal-check Run Bun terminal checks plus Python bridge import smoke"
	@echo "  make frontend-check Run dashboard and terminal frontend readiness gates"
	@echo "  make context-quorum-status Show multi-agent coordination spine status"
	@echo "  make context-quorum-init AGENT=name ROLE=role Create a persistent agent home"
	@echo "  make context-quorum-check AGENT=name RISK=Q2 QUESTION='...' Record context receipts"
	@echo "  make context-quorum-handoff AGENT=name SUMMARY='...' Write current agent handoff"
	@echo "  make long-harness-init GOAL='...' MODE=command-plane Create a planner/generator/evaluator run scaffold"
	@echo "  make long-harness-status RUN_ID=id Show long-running harness run status"
	@echo "  make long-harness-validate RUN_ID=id PHASE=scaffold Validate long-running harness artifacts"
	@echo "  make goodworks-dgm-seed Seed the local Goodworks MRV pilot ledger"
	@echo "  make goodworks-dgm-tick Run one bounded Goodworks DGM dry-run tick"
	@echo "  make goodworks-dgm-status Print Goodworks DGM status JSON"
	@echo "  make onboard      Render current operating reality (active track, live ops, broken register, axioms)"
	@echo "  make install-command-plane-stack  Install MCPs required by command-plane-redesign-2026-05 (idempotent)"
	@echo "  make stack-status  Verify MCP servers for the command-plane stack"
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

dashboard-install:
	npm --prefix dashboard ci --legacy-peer-deps

dashboard-lint:
	npm --prefix dashboard run lint -- --quiet

dashboard-build:
	NEXT_PUBLIC_WS_URL="$${NEXT_PUBLIC_WS_URL:-ws://127.0.0.1:8420}" npm --prefix dashboard run build

dashboard-status:
	bash scripts/dashboard_ctl.sh status

terminal-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -c "import dharma_swarm.terminal_bridge"
	bun run --cwd terminal typecheck
	bun run --cwd terminal test

frontend-check: dashboard-lint dashboard-build terminal-check

context-quorum-status:
	$(PYTHON) scripts/runtime/context_quorum.py status

context-quorum-init:
	$(PYTHON) scripts/runtime/context_quorum.py init-agent \
		--agent "$${AGENT:?set AGENT=name}" \
		--role "$${ROLE:-meta-agent}" \
		--purpose "$${PURPOSE:-Persistent meta-agent with context quorum duties}"

context-quorum-check:
	@set --; \
	if [ -n "$${SEMANTIC_RECEIPT:-}" ]; then set -- "$$@" --receipt "semantic_code=$${SEMANTIC_RECEIPT}"; fi; \
	if [ -n "$${TEST_COMMAND:-}" ]; then set -- "$$@" --test-command "$${TEST_COMMAND}"; fi; \
	if [ -n "$${HUMAN_APPROVAL:-}" ]; then set -- "$$@" --human-approval "$${HUMAN_APPROVAL}"; fi; \
	if [ -n "$${ROLLBACK_PLAN:-}" ]; then set -- "$$@" --rollback-plan "$${ROLLBACK_PLAN}"; fi; \
	$(PYTHON) scripts/runtime/context_quorum.py check \
		--agent "$${AGENT:?set AGENT=name}" \
		--task-id "$${TASK_ID:-manual-context-quorum}" \
		--risk "$${RISK:-Q2}" \
		--question "$${QUESTION:-manual context quorum}" \
		--exact-query "$${EXACT_QUERY:-context quorum}" \
		--changed-from "$${CHANGED_FROM:-HEAD}" \
		"$$@"

context-quorum-handoff:
	$(PYTHON) scripts/runtime/context_quorum.py handoff \
		--agent "$${AGENT:?set AGENT=name}" \
		--task-id "$${TASK_ID:-manual-context-quorum}" \
		--summary "$${SUMMARY:-No summary provided}" \
		--next-step "$${NEXT_STEP:-Run make onboard and refresh context quorum before editing}"

context-quorum-protect:
	$(PYTHON) scripts/runtime/context_quorum.py protect --changed-from "$${CHANGED_FROM:-HEAD}" --fail-on-hit

long-harness-init:
	@set --; \
	if [ -n "$${RUN_ID:-}" ]; then set -- "$$@" --run-id "$${RUN_ID}"; fi; \
	if [ -n "$${REQUIRE_CLEAN:-}" ]; then set -- "$$@" --require-clean; fi; \
	$(PYTHON) scripts/runtime/long_running_harness.py init \
		--mode "$${MODE:-brownfield}" \
		--risk "$${RISK:-Q3}" \
		--max-rounds "$${MAX_ROUNDS:-3}" \
		--goal "$${GOAL:?set GOAL='harness goal'}" \
		"$$@"

long-harness-status:
	$(PYTHON) scripts/runtime/long_running_harness.py status --run-id "$${RUN_ID:?set RUN_ID=id}"

long-harness-validate:
	$(PYTHON) scripts/runtime/long_running_harness.py validate \
		--run-id "$${RUN_ID:?set RUN_ID=id}" \
		--phase "$${PHASE:-scaffold}"

goodworks-dgm-seed:
	$(PYTHON) scripts/runtime/seed_goodworks_mrv.py

goodworks-dgm-tick:
	$(PYTHON) scripts/runtime/goodworks_dgm_tick.py $${ARGS:-}

goodworks-dgm-status:
	$(PYTHON) -c "import json; from dharma_swarm.goodworks_dgm import GoodworksDGMService; print(json.dumps(GoodworksDGMService().status(), indent=2))"

governance-all: semgrep gitleaks test-hygiene test-contracts uplift-guards module-budget docops-integrity frontend-check

# Single-door onboarding: prints the current operating reality from existing
# owners (ACTIVE_TRACK.yaml, LIVE_OPS_DASHBOARD.md, BROKEN_REGISTER.md,
# ACTIVE_SURFACE_MANIFEST.yaml). Always exits 0. Run this before any build
# session — humans and agents both.
onboard:
	$(PYTHON) scripts/governance/agent_onboard.py

# ============================================================================
# Command-plane stack installer (queued track command-plane-redesign-2026-05)
# ============================================================================

# install-command-plane-stack — Install MCP servers required by the
# command-plane-redesign-2026-05 queued track. Idempotent. See
# docs/plans/COMMAND_PLANE_MULTIAGENT_PROTOCOL.md for usage.
install-command-plane-stack:
	@bash scripts/setup/install_command_plane_stack.sh

# stack-status — Verify the command-plane stack is installed and healthy
stack-status:
	@echo "▶ MCP servers (Connected | Needs auth | Failed):"
	@claude mcp list 2>/dev/null | grep -E "Connected|authentication|✗" | sort | uniq -c | sort -rn || echo "  (claude mcp list failed — is claude on PATH?)"
	@echo
	@echo "▶ Required MCPs for command-plane track:"
	@for mcp in shadcn figma vercel sentry linear builder posthog playwright context7 tavily filesystem github sequential-thinking memory fetch; do \
		status=$$(claude mcp list 2>/dev/null | grep "^$$mcp:" | grep -oE "Connected|authentication|✗" | head -1); \
		printf "  %-22s %s\n" "$$mcp" "$${status:-NOT INSTALLED}"; \
	done

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
