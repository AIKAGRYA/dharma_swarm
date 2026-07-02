# DHARMA SWARM — Makefile
# Run `make help` to see all targets.

.PHONY: help boot stop logs health metrics test lint lint-blockers verifier-selfcheck clean install docker-up docker-down gh-auth semgrep semgrep-strict gitleaks precommit-install precommit-run governance-baseline test-hygiene mypy-strict-ratchet test-contracts nats-substrate-contract uplift-guards module-budget hygiene-audit hygiene-check docops-integrity docops-report ci-truth pr-queue pr-packet pr-gate pr-reviewers pr-run-codex pr-run-claude pr-merge pr-mike mike-wake mike-status mike-cycle mike-tmux-start mike-tmux-stop memory-kernel-readiness memory-kernel-readiness-strict memory-kernel-burn-in memory-kernel-write-receipt-smoke memory-kernel-promotion-smoke memory-kernel-knowledgeops-bridge-smoke memory-kernel-full-power-preflight operator-prod-smoke governance-all agent-build-preflight agent-build-closeout spine-check onboard orient status a2a-status a2a-up a2a-send go-fmt-check go-test go-vet go-ci verify-corral verify-corral-strict hygiene-delta-ratchet claim-evidence-check claim-evidence mutation-test

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
	@echo "  make nats-substrate-contract Verify NATS substrate contract wiring"
	@echo "  make uplift-guards Run uplift pre-commit guards"
	@echo "  make hygiene-audit Run non-blocking vibe-code hygiene scan"
	@echo "  make mypy-strict-ratchet Verify allowlisted modules pass mypy --strict"
	@echo "  make hygiene-check Verify hygiene catalogue/generated docs integrity"
	@echo "  make docops-integrity Run machine-verifiable documentation checks"
	@echo "  make verify-corral  Verify DE_BUG_CORRAL findings still resolve to live code"
	@echo "  make verify-corral-strict Same, but fail non-zero on any stale finding"
	@echo "  make hygiene-delta-ratchet  Fail if PR-touched files added new hygiene violations"
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
	@echo "  make memory-kernel-readiness Run read-only MemoryKernel readiness gates"
	@echo "  make memory-kernel-readiness-strict Require 100% strict MemoryKernel readiness"
	@echo "  make memory-kernel-burn-in Append M3 context preview burn-in receipts"
	@echo "  make memory-kernel-write-receipt-smoke Smoke M4 governed write receipts"
	@echo "  make memory-kernel-promotion-smoke Smoke M5 human-gated promotion receipts"
	@echo "  make memory-kernel-knowledgeops-bridge-smoke Smoke KnowledgeOps to MemoryKernel promotion bridge"
	@echo "  make memory-kernel-full-power-preflight Run M2-M5 governed live preflight"
	@echo "  make operator-prod-smoke Run fast read-only operator production smoke"
	@echo "  make onboard      Render current operating reality (active track, live ops, broken register, axioms)"
	@echo "  make orient       Render the whole organism at once (identity, organs, tracks, custody, liveness)"
	@echo "  make agent-onboard Fleet-identity join route + identity-surface drift check (new A2A agents)"
	@echo "  make agent-build-preflight Run onboarding + hygiene integrity before agent work"
	@echo "  make agent-build-closeout Run hygiene scan + full governance bundle after agent work"
	@echo "  make status       Quick cross-agent state snapshot (PRs, stale, hotlist, track)"
	@echo "  make a2a-status   Connect to the AGNI hub: Devin identity + live fleet roster + inbox state"
	@echo "  make a2a-up       Run the persistent Devin A2A agent (registers on fleet, drains inbox)"
	@echo "  make a2a-send     Send a packet: make a2a-send TO=codex FILE=path/to/packet.md"
	@echo "  make go-ci        Run Go evidence sense-organ fmt/vet/test gates"
	@echo "  make go-build     Compile the 4 Go tool mains into their module dirs (gitignored)"
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
	$(VENV_PYTHON) -m pytest tests/ -q --tb=short -x -m "not slow and not docker and not network"

test-fast:
	$(VENV_PYTHON) -m pytest tests/ -q --tb=line -x --timeout=10

lint:
	ruff check dharma_swarm/ --select=E,F,W --ignore=E501

syntax-check:
	@$(VENV_PYTHON) -m compileall -q dharma_swarm api scripts && echo "syntax-check: OK (compileall clean)"

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

mypy-strict-ratchet:
	$(PYTHON) scripts/governance/hygiene/mypy_strict_ratchet.py

test-contracts:
	scripts/governance/run_pytest_with_repo_env.sh -q \
		tests/test_contracts_scaffold.py \
		tests/test_operator_core_contracts.py \
		tests/test_runtime_contract.py \
		tests/test_runtime_contract_adapters.py \
		--tb=line

nats-substrate-contract:
	$(REPO_PYTHON) scripts/governance/check_nats_substrate_contract.py
	$(PYTEST) -q \
		tests/test_nats_live_contact.py \
		tests/test_nats_transport.py \
		tests/test_a2a_send.py \
		tests/test_a2a_inbox_bridge.py \
		tests/test_a2a_inbox_bridge_tmux_scripts.py \
		tests/test_a2a_domain_reply_worker.py \
		tests/test_a2a_reply_capture.py \
		--tb=line

uplift-guards:
	python3 scripts/uplift_guards/run_pre_commit.py

module-budget:
	$(PYTHON) scripts/governance/check_module_budget.py \
		--base-ref origin/main --head-ref HEAD

hygiene-audit:
	scripts/governance/hygiene/scan.sh

hygiene-check:
	$(PYTHON) scripts/governance/hygiene/check_hygiene_integrity.py

# One-way quality ratchet (QL-R1): counters may only improve vs the
# git-tracked baselines; green improvements auto-tighten (commit the
# baselines file with the improving change). CI/agents use plain check.
quality-ratchet:
	$(PYTHON) scripts/governance/hygiene/ratchet.py --tighten

quality-ratchet-check:
	$(PYTHON) scripts/governance/hygiene/ratchet.py --max-baseline-age-days 45

# Assurance boundary V0: contracts (not counts) on spine, memory_kernel,
# a2a, runtime_state, runtime_provider. Exit 1 lists hold-at-zero
# violations with file:line evidence; the ratchet banks the drain.
assurance-boundary:
	$(PYTHON) scripts/governance/assurance_boundary.py

docops-integrity:
	$(PYTHON) scripts/docops/check_docops_integrity.py
	$(PYTHON) scripts/governance/hygiene/check_hygiene_integrity.py

verify-corral:
	$(PYTHON) scripts/governance/verify_corral_findings.py

verify-corral-strict:
	$(PYTHON) scripts/governance/verify_corral_findings.py --strict

hygiene-delta-ratchet:
	$(PYTHON) scripts/governance/hygiene/delta_ratchet.py \
		--base-ref $${GITHUB_BASE_REF:-origin/main} --head-ref HEAD

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

# spine-check is composed into uplift-guards via
# scripts/uplift_guards/check_spine_ownership.py (PR A.5 governance
# convergence). It is intentionally NOT a separate governance-all
# dependency — running it once via uplift-guards is enough. The standalone
# `make spine-check` target stays as an operator-convenience alias only.
governance-all: semgrep gitleaks test-hygiene test-contracts nats-substrate-contract uplift-guards module-budget docops-integrity claim-evidence-check

# Pudgala Forge (graded claim/evidence binding). claim-evidence-check is
# STAGE-DRIVEN: it blocks iff the AI-M1 hygiene pattern is at stage 'enforced'
# (operator-promoted via scripts/governance/hygiene/promote.py). AI-M1 is advisory
# today and binding_stage() fail-safes to advisory, so this exits 0 in
# governance-all NOW and starts blocking the moment AI-M1 is promoted — ONE switch
# (the stage), no separate --warn-only flag to also remember to drop. It reports
# per-track strongest evidence grade vs required min_evidence_grade so existence-
# only "shipped" claims surface. (Force advisory anywhere with --warn-only; force
# blocking with --enforce.) claim-evidence (below) appends the receipt.
claim-evidence-check:
	$(REPO_PYTHON) scripts/governance/check_claim_evidence_binding.py

claim-evidence:
	$(REPO_PYTHON) scripts/governance/check_claim_evidence_binding.py --warn-only --emit-receipt

# S6 mutation gate (Pudgala Forge P3-09): runs mutmut on the configured surfaces
# (pyproject [tool.mutmut]) and writes reports/governance/mutation_score.json, the
# report the `mutation_score_gte` criterion reads. SLOW — a separate step, NOT in
# governance-all. Needs `pip install mutmut`.
mutation-test:
	$(REPO_PYTHON) scripts/governance/run_mutation_score.py

agent-build-preflight: verifier-selfcheck onboard hygiene-check
	@printf "\nAgent build preflight complete. Use the task route from make onboard; close out with: make agent-build-closeout\n"

agent-build-closeout:
	$(PYTHON) scripts/governance/hygiene/scan.py --output /tmp/dharma-hygiene-audit.txt
	$(MAKE) governance-all
	@printf "\nAgent build closeout complete. Hygiene audit receipt: /tmp/dharma-hygiene-audit.txt\n"

spine-check:
	$(PYTHON) -m scripts.uplift_guards.check_spine_ownership

# Single-door onboarding: prints the current operating reality from existing
# owners (ACTIVE_TRACK.yaml, LIVE_OPS_DASHBOARD.md, BROKEN_REGISTER.md,
# ACTIVE_SURFACE_MANIFEST.yaml). Always exits 0. Run this before any build
# session — humans and agents both.
onboard:
	$(PYTHON) scripts/governance/agent_onboard.py

# Whole-system orientation: identity, tracks, lanes, agents, receipts, A2A,
# body state, and broken register. Explicitly emits generated repo_context
# artifacts from existing owners; the artifacts own no facts.
orient:
	$(PYTHON) scripts/governance/orientation_graph.py --write-context

# Fleet-identity onboarding: the join route for a NEW persistent A2A agent
# (card, runtime registration, roster, git seat, announcement, presence) plus
# a drift check across the identity surfaces. Read-only; always exits 0.
# `make onboard` orients a session; this onboards an identity.
# See docs/ops/A2A_AGENT_ONBOARDING.md.
agent-onboard:
	$(PYTHON) scripts/governance/a2a_agent_onboard.py $(ARGS)

# Quick cross-agent state snapshot: active track, open PRs, stale items,
# broken register, hotlist. Any agent on any platform can run this.
status:
	$(PYTHON) scripts/governance/repo_status.py

track-strength:
	$(VENV_PYTHON) scripts/governance/track_acceptance_strength_report.py

# ── A2A (agent-to-agent over the AGNI NATS hub) ────────────────────────────
# One-command connect + identity + live fleet roster + inbox state. The
# bundled CA loads automatically; only DEVIN_NATS_PW must be exported.
# See docs/ops/A2A_QUICKSTART.md.
a2a-status:
	$(VENV_PYTHON) scripts/runtime/a2a_doctor.py $(ARGS)

# Run the persistent Devin agent: registers on the fleet and drains devin_inbox.
a2a-up:
	$(VENV_PYTHON) scripts/runtime/devin_a2a_agent.py $(ARGS)

# Send a packet to an agent lane and wait for ack/reply.
#   make a2a-send TO=codex FILE=inter_agent/devin/outbound/ping.md
a2a-send:
	$(VENV_PYTHON) scripts/runtime/a2a_send.py --to $(TO) --file $(FILE) $(ARGS)

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

# Compile the four Go tool mains into their module dirs (gitignored binaries,
# e.g. tools/world_scout_go/world_scout_go). The Python bridge prefers these
# prebuilt binaries and falls back to `go run .` when they are absent.
GO_TOOL_MAIN_MODULES := $(GO_EVIDENCE_MODULE) $(GO_GITHUB_INGESTOR_MODULE) $(GO_WORLD_SIGNAL_INGESTOR_MODULE) $(GO_WORLD_SCOUT_MODULE)

go-build:
	@mkdir -p $(GO_CACHE_DIR) $(GO_MOD_CACHE_DIR)
	@for mod in $(GO_TOOL_MAIN_MODULES); do \
		bin=$$(basename $$mod); \
		echo "go build -o $$bin in $$mod"; \
		( cd $$mod && GOCACHE=$(GO_CACHE_DIR) GOMODCACHE=$(GO_MOD_CACHE_DIR) $(GO) build -o $$bin . ) || exit 1; \
	done

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
