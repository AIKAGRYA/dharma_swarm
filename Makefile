# DHARMA SWARM — Makefile
# Run `make help` to see all targets.

.PHONY: help boot stop logs health metrics test lint lint-blockers verifier-selfcheck clean install docker-up docker-down gh-auth semgrep semgrep-strict gitleaks precommit-install precommit-run governance-baseline test-hygiene test-contracts nats-substrate-contract nats-live-production-matrix uplift-guards module-budget hygiene-audit hygiene-check bug-corral-scan name-drift-preflight semantic-commons-check semantic-commons-project agent-admit onboard-agent codex-composer-bootstrap codex-composer-once codex-composer-status codex-composer-start codex-composer-stop agent-wake-once agent-wake-status agent-wake-bootstrap agent-wake-start agent-wake-stop docops-integrity docops-report ci-truth pr-queue pr-packet pr-gate pr-reviewers pr-run-codex pr-run-claude pr-merge pr-mike mike-wake mike-status mike-cycle mike-tmux-start mike-tmux-stop tmux-bootstrap tmux-status tmux-substrate-contract memory-kernel-readiness memory-kernel-readiness-strict memory-kernel-burn-in memory-kernel-write-receipt-smoke memory-kernel-promotion-smoke memory-kernel-knowledgeops-bridge-smoke memory-kernel-full-power-preflight operator-prod-smoke runtime-truth-ci runtime-truth-closeout runtime-truth-burn-in runtime-truth-burn-in-smoke runtime-truth-100-audit runtime-task-firebreak ds-goal-longrun-preflight-check governance-all agent-build-preflight agent-build-closeout cybernetics-codex-audit wiki-orphan-status wiki-orphan-upgrade spine-check onboard offboard orient status sprawl-guard go-fmt-check go-test go-vet go-ci xray compile test-smoke test-all dashboard-lint dashboard-build

# Prefer the repo venv when present so onboarding sections that need repo
# dependencies (pydantic, yaml) render instead of degrading silently.
PYTHON ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
REPO_PYTHON ?= PYTHONPATH=. $(PYTHON)
PYTEST ?= pytest
# Test targets need the repo venv (pytest-timeout etc. live there, not in system pythons).
VENV_PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,$(PYTHON))
GO ?= go
GOFMT ?= gofmt
SEMGREP ?= scripts/governance/run_semgrep_with_ca.sh
SWARM_PLIST := $(HOME)/Library/LaunchAgents/com.dharma.swarm.plist
STATE_DIR    := $(HOME)/.dharma
GO_EVIDENCE_MODULE := tools/evidence_ingestor_go
GO_SDK_MODULE := tools/go_sdk
GO_GITHUB_INGESTOR_MODULE := tools/github_ingestor_go
GO_WORLD_SIGNAL_INGESTOR_MODULE := tools/world_signal_ingestor_go
GO_WORLD_SCOUT_MODULE := tools/world_scout_go
GO_MODULES := $(GO_SDK_MODULE) $(GO_EVIDENCE_MODULE) $(GO_GITHUB_INGESTOR_MODULE) $(GO_WORLD_SIGNAL_INGESTOR_MODULE) $(GO_WORLD_SCOUT_MODULE)
GO_CACHE_DIR ?= /tmp/dharma-swarm-go-build
GO_MOD_CACHE_DIR ?= /tmp/dharma-swarm-go-mod
TMUX ?= tmux
TMUX_MANAGED_SESSIONS := dharma-control dharma-agents dharma-vps

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
	@echo "  make live         Run repo-pinned orchestrate-live in foreground (dev mode)"
	@echo "  make semgrep      Run governance Semgrep rules"
	@echo "  make gitleaks     Scan for secrets"
	@echo "  make precommit-run Run pre-commit on all files"
	@echo "  make governance-baseline Capture scanner baselines"
	@echo "  make test-contracts Run governance contract tests"
	@echo "  make nats-substrate-contract Verify NATS substrate contract wiring"
	@echo "  make uplift-guards Run uplift pre-commit guards"
	@echo "  make hygiene-audit Run non-blocking vibe-code hygiene scan"
	@echo "  make hygiene-check Verify hygiene catalogue/generated docs integrity"
	@echo "  make bug-corral-scan Scan name drift and route findings to DE_BUG_CORRAL"
	@echo "  make semantic-commons-check Validate Semantic Commons registry and orientation routes"
	@echo "  make semantic-commons-project Generate read-only Obsidian/PKM Semantic Commons projections"
	@echo "  make agent-admit ARGS='...' Run read-only persistent-agent admission checks"
	@echo "  make onboard-agent AGENT_NAME=codex_composer Run read-only named-agent orientation"
	@echo "  make codex-composer-bootstrap Create/update codex_composer wake nest"
	@echo "  make codex-composer-once Run one read-only codex_composer wake cycle"
	@echo "  make codex-composer-status Render codex_composer wake status"
	@echo "  make codex-composer-start ARGS='--activation-lease <id>' Start lease-gated wake loop"
	@echo "  make codex-composer-stop Stop codex_composer wake loop if present"
	@echo "  make docops-integrity Run machine-verifiable documentation checks"
	@echo "  make docops-report Generate local DocOps JSON/Markdown reports"
	@echo "  make ci-truth ARGS='--pr 123' Evaluate GitHub checks against the CI truth contract"
	@echo "  make pr-queue Classify open GitHub PRs into a receipt-backed review queue"
	@echo "  make pr-packet PR=123 Create a Codex/Claude review packet for one PR"
	@echo "  make pr-reviewers Show local Codex/Claude reviewer readiness"
	@echo "  make pr-run-codex PR=123 Run Codex against the latest review packet"
	@echo "  make pr-run-claude PR=123 Run Claude Code against the latest review packet"
	@echo "  make pr-gate PR=123 Verify merge gate against live GitHub state"
	@echo "  make pr-merge PR=123 ARGS='--confirm merge-pr-123' Dry-run gated merge"
	@echo "  make pr-mike ARGS='--dry-run --max-prs 5' Merge Master Mike packet -> reviewer -> gate fanout"
	@echo "  make mike-wake    Record a fresh Mike wake receipt"
	@echo "  make mike-status  Render Mike nest status"
	@echo "  make mike-cycle ARGS='--cycle-mode dry-run --max-prs 5' Run one supervised Mike cycle"
	@echo "  make mike-tmux-start Start Mike's dry-run daemon lane in tmux"
	@echo "  make mike-tmux-stop  Stop Mike's tmux daemon lane"
	@echo "  make tmux-bootstrap Create standard local tmux cockpit sessions"
	@echo "  make tmux-status  Report standard local tmux cockpit sessions"
	@echo "  make tmux-substrate-contract Verify tmux docs/census contract wiring"
	@echo "  make memory-kernel-readiness Run read-only MemoryKernel readiness gates"
	@echo "  make memory-kernel-readiness-strict Require 100% strict MemoryKernel readiness"
	@echo "  make memory-kernel-burn-in Append M3 context preview burn-in receipts"
	@echo "  make memory-kernel-write-receipt-smoke Smoke M4 governed write receipts"
	@echo "  make memory-kernel-promotion-smoke Smoke M5 human-gated promotion receipts"
	@echo "  make memory-kernel-knowledgeops-bridge-smoke Smoke KnowledgeOps to MemoryKernel promotion bridge"
	@echo "  make memory-kernel-full-power-preflight Run M2-M5 governed live preflight"
	@echo "  make operator-prod-smoke Run fast read-only operator production smoke"
	@echo "  make runtime-truth-ci Run deterministic runtime truth invariant CI gates"
	@echo "  make runtime-truth-closeout ARGS='--allow-paused' Run runtime truth closeout gate"
	@echo "  make runtime-truth-burn-in ARGS='--duration-seconds 7200' Run strict unpaused runtime truth burn-in"
	@echo "  make runtime-truth-burn-in-smoke Run paused runtime truth burn-in smoke"
	@echo "  make runtime-truth-100-audit Run final live evidence audit for 100/100 readiness"
	@echo "  make runtime-task-firebreak ARGS='--json' Dry-run task backlog firebreak"
	@echo "  make ds-goal-longrun-preflight-check Block unpinned repo-owned ds-goal longrun workflow commands"
	@echo "  make cybernetics-codex-audit Render read-only cybernetic loop closure ledger"
	@echo "  make wiki-orphan-status Render Karpathy wiki orphan/density health"
	@echo "  make wiki-orphan-upgrade ARGS='--limit 200' Enrich orphan atoms and re-ingest wiki retrieval"
	@echo "  make onboard      Render current operating reality (active track, live ops, broken register, axioms)"
	@echo "  make offboard     Render end-of-session handoff receipt for the next agent/auditor"
	@echo "  make orient       Render the whole organism at once (identity, organs, tracks, custody, liveness)"
	@echo "  make agent-build-preflight Run onboarding + hygiene integrity before agent work"
	@echo "  make agent-build-closeout Run hygiene scan + full governance bundle after agent work"
	@echo "  make status       Quick cross-agent state snapshot (PRs, stale, hotlist, track)"
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
	TINY_ROUTER_BACKEND=heuristic $(REPO_PYTHON) -m dharma_swarm.dgc_cli orchestrate-live

test:
	$(VENV_PYTHON) -m pytest tests/ -q --tb=short -x -m "not slow and not docker and not network"

test-fast:
	$(VENV_PYTHON) -m pytest tests/ -q --tb=line -x --timeout=10

lint:
	ruff check dharma_swarm/ --select=E,F,W --ignore=E501

syntax-check:
	@$(VENV_PYTHON) -m compileall -q dharma_swarm api scripts && echo "syntax-check: OK (compileall clean)"

# Aliases/shims for targets documented in README.md / CLAUDE.md.
# These map to existing implementations so onboarding docs do not lie.
xray:
	$(PYTHON) scripts/repo_xray.py --repo-root .

compile: syntax-check

test-smoke: test-fast

test-all:
	$(VENV_PYTHON) -m pytest tests/ -q

dashboard-lint:
	npm --prefix dashboard run lint

dashboard-build:
	npm --prefix dashboard run build

# Undefined names are guaranteed NameErrors at runtime — always blocking.
lint-blockers:
	@ruff check dharma_swarm/ api/ scripts/ --select=F821 --quiet && echo "lint-blockers: OK (no undefined names)"

# The watchmen-watcher: verifies the verification gates themselves work.
# Born 2026-06-12 after syntax-check, test-fast, and suite collection were
# all found broken simultaneously with nothing noticing.
verifier-selfcheck:
	@echo "[1/4] syntax-check"
	@$(MAKE) -s syntax-check
	@echo "[2/4] lint-blockers (F821)"
	@$(MAKE) -s lint-blockers
	@echo "[3/4] test collection"
	@$(VENV_PYTHON) -m pytest tests/ --collect-only -q >/tmp/dharma-collect-check.log 2>&1 \
		|| (echo "COLLECTION BROKEN:"; tail -20 /tmp/dharma-collect-check.log; exit 1)
	@tail -1 /tmp/dharma-collect-check.log
	@echo "[4/4] onboard door"
	@$(MAKE) -s onboard >/dev/null 2>&1 && echo "onboard: OK"
	@echo "verifier-selfcheck: ALL GATES FUNCTIONAL"

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

nats-substrate-contract:
	$(REPO_PYTHON) scripts/governance/check_nats_substrate_contract.py
	$(REPO_PYTHON) scripts/governance/check_nats_live_production_evidence.py --max-age-hours 24
	$(PYTEST) -q \
		tests/test_nats_live_contact.py \
		tests/test_nats_substrate_contract.py \
		tests/test_nats_transport.py \
		tests/test_a2a_send.py \
		tests/test_a2a_inbox_bridge.py \
		tests/test_a2a_inbox_bridge_tmux_scripts.py \
		tests/test_a2a_domain_reply_worker.py \
		tests/test_a2a_reply_capture.py \
		--tb=line

nats-live-production-matrix:
	$(REPO_PYTHON) scripts/governance/run_nats_live_production_matrix.py --endpoint $${NATS_URL:-nats://127.0.0.1:4222} --broker-profile $${NATS_PROFILE:-local-live-jetstream}

uplift-guards:
	$(PYTHON) scripts/uplift_guards/run_pre_commit.py

module-budget:
	$(PYTHON) scripts/governance/check_module_budget.py \
		--base-ref origin/main --head-ref HEAD

hygiene-audit:
	scripts/governance/hygiene/scan.sh

hygiene-check:
	$(PYTHON) scripts/governance/hygiene/check_hygiene_integrity.py

bug-corral-scan:
	$(PYTHON) scripts/governance/name_drift_preflight.py $${ARGS:-}

name-drift-preflight: bug-corral-scan

semantic-commons-check:
	$(PYTHON) scripts/governance/agent_admission.py
	$(PYTHON) scripts/governance/agent_admission_projection.py --json > /tmp/dharma-semantic-commons-projection-check.json
	$(PYTHON) scripts/governance/name_drift_preflight.py --strict-semantic-commons --limit 20

semantic-commons-project:
	$(PYTHON) scripts/governance/agent_admission_projection.py \
		--write \
		--manifest reports/governance/semantic_commons_projection_manifest.json

agent-admit:
	$(PYTHON) scripts/governance/agent_admission.py $(ARGS)

onboard-agent:
	@[ -n "$(AGENT_NAME)" ] || (printf "set AGENT_NAME=codex_composer\n"; exit 2)
	@case "$(AGENT_NAME)" in \
		codex_composer|fable_composer) : ;; \
		*) printf "unsupported AGENT_NAME=%s; supported: codex_composer fable_composer\n" "$(AGENT_NAME)"; exit 2 ;; \
	esac
	$(PYTHON) scripts/governance/agent_admission.py
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py --agent-uid $(AGENT_NAME) once $${ARGS:-}

# Generic seat wake surface (default codex_composer; set AGENT_NAME=fable_composer etc.).
# One governed loop serves every admitted seat via --agent-uid; no per-agent fork.
AGENT_NAME ?= codex_composer
agent-wake-once:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py --agent-uid $(AGENT_NAME) once $${ARGS:-}

agent-wake-status:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py --agent-uid $(AGENT_NAME) status $${ARGS:-}

agent-wake-bootstrap:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py --agent-uid $(AGENT_NAME) bootstrap $${ARGS:-}

agent-wake-start:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py --agent-uid $(AGENT_NAME) start $${ARGS:-}

agent-wake-stop:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py --agent-uid $(AGENT_NAME) stop $${ARGS:-}

codex-composer-bootstrap:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py bootstrap $${ARGS:-}

codex-composer-once:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py once $${ARGS:-}

codex-composer-status:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py status $${ARGS:-}

codex-composer-start:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py start $${ARGS:-}

codex-composer-stop:
	$(PYTHON) scripts/runtime/codex_composer_wake_loop.py stop $${ARGS:-}

docops-integrity:
	$(PYTHON) scripts/docops/check_docops_integrity.py
	$(PYTHON) scripts/governance/hygiene/check_hygiene_integrity.py

docops-report:
	@mkdir -p reports/docops
	$(PYTHON) scripts/docops/check_docops_integrity.py \
		--report-json reports/docops/check.json \
		--inventory-json reports/docops/corpus_inventory.json \
		--inventory-markdown reports/docops/corpus_inventory.md
	$(PYTHON) scripts/governance/hygiene/check_hygiene_integrity.py

ci-truth:
	$(PYTHON) scripts/runtime/ci_truth.py $${ARGS:-}

pr-queue:
	$(PYTHON) scripts/runtime/pr_merge_control.py queue $${ARGS:-}

pr-packet:
	$(PYTHON) scripts/runtime/pr_merge_control.py packet --pr "$${PR:?set PR=number}" $${ARGS:-}

pr-gate:
	$(PYTHON) scripts/runtime/pr_merge_control.py gate --pr "$${PR:?set PR=number}" $${ARGS:-}

pr-reviewers:
	$(PYTHON) scripts/runtime/pr_merge_control.py reviewers $${ARGS:-}

pr-run-codex:
	$(PYTHON) scripts/runtime/pr_merge_control.py run-agent --agent codex --pr "$${PR:?set PR=number}" $${ARGS:-}

pr-run-claude:
	$(PYTHON) scripts/runtime/pr_merge_control.py run-agent --agent claude --pr "$${PR:?set PR=number}" $${ARGS:-}

pr-merge:
	$(PYTHON) scripts/runtime/pr_merge_control.py merge --pr "$${PR:?set PR=number}" $${ARGS:-}

pr-mike:
	$(PYTHON) scripts/runtime/pr_merge_control.py fanout $${ARGS:-}

mike-wake:
	$(PYTHON) scripts/runtime/merge_master_mike_daemon.py wake $${ARGS:-}

mike-status:
	$(PYTHON) scripts/runtime/merge_master_mike_daemon.py status $${ARGS:-}

mike-cycle:
	$(PYTHON) scripts/runtime/merge_master_mike_daemon.py cycle $${ARGS:-}

mike-tmux-start:
	$(PYTHON) scripts/runtime/merge_master_mike_daemon.py tmux-start $${ARGS:-}

mike-tmux-stop:
	$(PYTHON) scripts/runtime/merge_master_mike_daemon.py tmux-stop $${ARGS:-}

tmux-bootstrap:
	@command -v $(TMUX) >/dev/null || (printf "tmux not found\n"; exit 127)
	@for session in $(TMUX_MANAGED_SESSIONS); do \
		if $(TMUX) has-session -t "$$session" 2>/dev/null; then \
			printf "tmux session '%s' already running\n" "$$session"; \
		else \
			$(TMUX) new-session -d -s "$$session" -c "$(CURDIR)"; \
			printf "tmux session '%s' created\n" "$$session"; \
		fi; \
	done

tmux-status:
	@command -v $(TMUX) >/dev/null || (printf "tmux not found\n"; exit 127)
	@$(TMUX) -V
	@$(TMUX) ls 2>/dev/null || true
	@missing=0; \
	for session in $(TMUX_MANAGED_SESSIONS); do \
		if $(TMUX) has-session -t "$$session" 2>/dev/null; then \
			printf "managed session '%s': live\n" "$$session"; \
		else \
			printf "managed session '%s': missing\n" "$$session"; \
			missing=1; \
		fi; \
	done; \
	exit $$missing

tmux-substrate-contract:
	@grep -q "dharma-control" docs/ops/TMUX_AGENT_SUBSTRATE.md
	@grep -q "dharma-agents" docs/ops/TMUX_AGENT_SUBSTRATE.md
	@grep -q "dharma-vps" docs/ops/TMUX_AGENT_SUBSTRATE.md
	@grep -q "managed_tmux = {\"dharma-control\", \"dharma-agents\", \"dharma-vps\"}" scripts/runtime/live_ops_census.py
	@$(MAKE) -s tmux-status

memory-kernel-readiness:
	$(REPO_PYTHON) scripts/memory_kernel_readiness.py --repo-root . --dry-run
	$(REPO_PYTHON) scripts/memory_writer_sentinel.py --repo-root . --ci
	$(REPO_PYTHON) scripts/memory_context_eval.py --repo-root . --run-default-cases --fail-on-hard-failure --dry-run
	$(REPO_PYTHON) scripts/memory_context_shadow_sweep.py --repo-root . --fail-on-hard-failure --dry-run

memory-kernel-readiness-strict:
	$(REPO_PYTHON) scripts/memory_kernel_readiness.py --repo-root . --dry-run --strict --fail-on-missing-adapter
	$(REPO_PYTHON) scripts/memory_writer_sentinel.py --repo-root . --ci
	$(REPO_PYTHON) scripts/memory_context_eval.py --repo-root . --run-default-cases --fail-on-hard-failure --dry-run
	$(REPO_PYTHON) scripts/memory_context_shadow_sweep.py --repo-root . --fail-on-hard-failure --dry-run

memory-kernel-burn-in:
	$(REPO_PYTHON) scripts/memory_kernel_burn_in.py --repo-root . --fail-on-blocked

memory-kernel-write-receipt-smoke:
	$(REPO_PYTHON) scripts/memory_kernel_write_receipt_smoke.py --repo-root . --fail-on-blocked

memory-kernel-promotion-smoke: memory-kernel-write-receipt-smoke
	$(REPO_PYTHON) scripts/memory_kernel_promotion_smoke.py --repo-root . --fail-on-blocked

memory-kernel-knowledgeops-bridge-smoke:
	$(REPO_PYTHON) scripts/memory_kernel_knowledgeops_bridge_smoke.py --repo-root . --fail-on-blocked

memory-kernel-full-power-preflight:
	$(MAKE) memory-kernel-readiness-strict
	$(MAKE) memory-kernel-burn-in
	$(MAKE) memory-kernel-write-receipt-smoke
	$(MAKE) memory-kernel-promotion-smoke
	$(MAKE) memory-kernel-knowledgeops-bridge-smoke
	DHARMA_MEMORY_KERNEL_ROLLOUT=live $(REPO_PYTHON) scripts/operator_prod_smoke.py --repo-root .

operator-prod-smoke:
	$(REPO_PYTHON) scripts/operator_prod_smoke.py --repo-root .

runtime-truth-ci:
	$(VENV_PYTHON) -m pytest -q --tb=line \
		tests/test_runtime_state_invariants.py \
		tests/test_runtime_receipt_coverage_report.py \
		tests/test_runtime_truth_closeout.py \
		tests/test_runtime_truth_burn_in.py \
		tests/test_runtime_truth_100_audit.py \
		tests/test_agent_runner.py::test_runner_records_attempted_route_from_provider_chain_failure \
		tests/test_agent_runner.py::test_runner_exposes_actual_served_route_from_llm_response \
		tests/test_agent_runner.py::test_runner_preserves_served_route_when_local_tool_fails_after_provider \
		tests/test_orchestrator_spine_dispatch.py \
		tests/test_daemon_operator_status.py \
		tests/test_dashboard_health_route.py \
		tests/test_swarm_health_api.py

runtime-truth-closeout:
	$(REPO_PYTHON) scripts/runtime/runtime_truth_closeout.py $${ARGS:-}

runtime-truth-burn-in:
	$(REPO_PYTHON) scripts/runtime/runtime_truth_burn_in.py $${ARGS:-}

runtime-truth-burn-in-smoke:
	$(REPO_PYTHON) scripts/runtime/runtime_truth_burn_in.py --allow-paused --duration-seconds 0 --interval-seconds 0 --min-samples 1 $${ARGS:-}

runtime-truth-100-audit:
	$(REPO_PYTHON) scripts/runtime/runtime_truth_100_audit.py $${ARGS:-}

runtime-task-firebreak:
	$(REPO_PYTHON) scripts/runtime/runtime_task_backlog_firebreak.py $${ARGS:-}

ds-goal-longrun-preflight-check:
	$(PYTHON) scripts/governance/ds_goal_longrun_preflight_report.py --strict

# spine-check is composed into uplift-guards via
# scripts/uplift_guards/check_spine_ownership.py (PR A.5 governance
# convergence). It is intentionally NOT a separate governance-all
# dependency — running it once via uplift-guards is enough. The standalone
# `make spine-check` target stays as an operator-convenience alias only.
governance-all: semgrep gitleaks test-hygiene test-contracts nats-substrate-contract uplift-guards module-budget ds-goal-longrun-preflight-check docops-integrity

agent-build-preflight: verifier-selfcheck onboard hygiene-check
	@printf "\nAgent build preflight complete. Use the task route from make onboard; leave a handoff with make offboard, and run make agent-build-closeout before PR/merge handoff.\n"

agent-build-closeout:
	$(PYTHON) scripts/governance/hygiene/scan.py --output /tmp/dharma-hygiene-audit.txt
	$(MAKE) governance-all
	@printf "\nAgent build closeout complete. Hygiene audit receipt: /tmp/dharma-hygiene-audit.txt\n"

cybernetics-codex-audit:
	$(REPO_PYTHON) scripts/governance/cybernetics_codex_audit.py

wiki-orphan-status:
	$(PYTHON) scripts/wiki_orphan_upgrade.py --status $(ARGS)

wiki-orphan-upgrade:
	$(PYTHON) scripts/wiki_orphan_upgrade.py --apply $(ARGS)
	$(PYTHON) /Users/dhyana/.dharma/scripts/regen_wiki_index.py
	$(REPO_PYTHON) -c 'from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts; r=ingest_wiki_concepts(); print(r.to_json()["discovered_files"])'
	$(REPO_PYTHON) scripts/wiki_vector_live_gate.py

spine-check:
	$(PYTHON) -m scripts.uplift_guards.check_spine_ownership

# Single-door onboarding: prints the current operating reality from existing
# owners (ACTIVE_TRACK.yaml, LIVE_OPS_DASHBOARD.md, BROKEN_REGISTER.md,
# ACTIVE_SURFACE_MANIFEST.yaml). Always exits 0. Run this before any build
# session — humans and agents both.
onboard:
	$(PYTHON) scripts/governance/agent_onboard.py
	@printf "\n== Wiki Knowledge Health ==\n"
	@$(PYTHON) scripts/wiki_orphan_upgrade.py --status --max-print 8
	@printf "\n== Sprawl Guard (A1/A2 singletons — advisory here; run 'make sprawl-guard' to gate) ==\n"
	-@$(PYTHON) scripts/governance/sprawl_guard.py

# Single-door offboarding: writes a receipt for the next agent/auditor after a
# scoped work session. By default this writes under ~/.dharma/ops; pass
# ARGS='--repo-receipt ...' only when a durable repo handoff is intended.
offboard:
	$(PYTHON) scripts/governance/agent_offboard.py $(ARGS)

# Whole-system orientation: identity, organs, tracks, canon custody, liveness,
# broken register — one read-only view projected from the owners. Always exits 0.
orient:
	$(PYTHON) scripts/governance/orientation_graph.py
	@printf "\n== Wiki Knowledge Health ==\n"
	@$(PYTHON) scripts/wiki_orphan_upgrade.py --status --max-print 8
	@printf "\n== Sprawl Guard (A1/A2 singletons — advisory here; run 'make sprawl-guard' to gate) ==\n"
	-@$(PYTHON) scripts/governance/sprawl_guard.py

# Deterministic, read-only A1/A2 duplicate-primitive gate. Non-zero exit on any
# sprawl finding, so this is the target to put in pre-commit / CI. `onboard` and
# `orient` call the guard advisory-only (never blocking orientation); THIS target
# is the one that fails the build when a declared singleton is duplicated.
sprawl-guard:
	$(PYTHON) scripts/governance/sprawl_guard.py

# Quick cross-agent state snapshot: active track, open PRs, stale items,
# broken register, hotlist. Any agent on any platform can run this.
status:
	$(PYTHON) scripts/governance/repo_status.py

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

# ── Operational targets ──────────────────────────────────────────────────

staging-report:
	$(PYTHON) scripts/consume_review_marks.py --report

staging-promote:
	$(PYTHON) scripts/consume_review_marks.py --auto-promote

staging-promote-dry:
	$(PYTHON) scripts/consume_review_marks.py --auto-promote --dry-run

provider-check:
	$(PYTHON) scripts/check_provider_credits.py

hermes-heartbeat:
	$(PYTHON) scripts/hermes_heartbeat_poll.py
