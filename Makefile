# DHARMA SWARM — Makefile
# Run `make help` to see all targets.

.PHONY: help boot stop logs health metrics test lint lint-blockers verifier-selfcheck clean bootstrap install docker-up docker-down gh-auth semgrep semgrep-advisory semgrep-strict gitleaks precommit-install precommit-run governance-baseline test-hygiene mypy-strict-ratchet test-contracts nats-substrate-contract nats-live-production-matrix uplift-guards module-budget hygiene-audit hygiene-check docops-integrity docops-report ci-truth pr-queue pr-packet pr-gate pr-reviewers pr-run-codex pr-run-claude pr-mike mike-wake mike-status mike-cycle mike-tmux-start mike-tmux-stop memory-kernel-readiness memory-kernel-readiness-strict memory-kernel-burn-in memory-kernel-write-receipt-smoke memory-kernel-promotion-smoke memory-kernel-knowledgeops-bridge-smoke memory-kernel-full-power-preflight operator-prod-smoke governance-all agentops-report-root-check agent-build-preflight agent-build-closeout spine-check onboard onboarding-macos-compatibility vision organism-status orient agent-register agent-onboard status a2a-status a2a-up a2a-send go-fmt-check go-test go-vet go-ci frontend-check terminal-check verify-corral verify-corral-strict hygiene-delta-ratchet claim-evidence-check claim-evidence mutation-test slop-ratchet slop-baseline

# Prefer the repo venv when present so onboarding sections that need repo
# dependencies (pydantic, yaml) render instead of degrading silently. Freeze a
# caller value lexically: recursive Make syntax in an override must never be
# evaluated while admission variables are exported to a recipe or submake.
ifneq ($(findstring $$,$(value PYTHON)),)
$(error PYTHON must not contain Make expansion syntax)
endif
ifeq ($(origin PYTHON),undefined)
PYTHON := $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
else
override PYTHON := $(value PYTHON)
endif
export PYTHON
REPO_PYTHON ?= PYTHONPATH=. $(PYTHON)
PYTEST ?= pytest
MUTATION_THRESHOLD ?= 0.60
# Test targets need the repo venv (pytest-timeout etc. live there, not in system pythons).
VENV_PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,$(PYTHON))
# Verification resolves in-venv tools explicitly after bootstrap (WP-0A):
# a PATH ruff can differ from the locked closure's pin in uv.lock. Lazily
# expanded (=) so `make bootstrap lint-blockers` in one invocation sees the
# .venv that bootstrap just created, not the pre-bootstrap parse-time state.
RUFF = $(if $(wildcard .venv/bin/ruff),.venv/bin/ruff,ruff)
# Pinned resolver for the hermetic dependency path (WP-0A / TIT-004). Keep in
# lockstep with UV_VERSION in .github/workflows/hermetic.yml —
# tests/test_bootstrap_contract.py enforces the match.
UV_VERSION ?= 0.11.2
GO ?= go
GOFMT ?= gofmt
SEMGREP ?= scripts/governance/run_semgrep_with_ca.sh
GITLEAKS ?= gitleaks
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
# AgentOps admission receipts must never enter the source checkout. Reuse the
# already-external onboarding ops root when declared; otherwise choose an
# explicit host-temporary default. The runner revalidates this boundary.
override _AGENTOPS_REPORT_ROOT_INPUT := $(strip $(value AGENTOPS_REPORT_ROOT))
ifeq ($(_AGENTOPS_REPORT_ROOT_INPUT),)
override _AGENTOPS_REPORT_ROOT_INPUT := $(if $(strip $(value DHARMA_OPS_DIR)),$(value DHARMA_OPS_DIR),/tmp/dharma-agentops-$(shell /usr/bin/id -u))
endif
ifneq ($(findstring $$,$(_AGENTOPS_REPORT_ROOT_INPUT)),)
$(error AGENTOPS_REPORT_ROOT and DHARMA_OPS_DIR must not contain Make expansion syntax)
endif
override AGENTOPS_REPORT_ROOT := $(_AGENTOPS_REPORT_ROOT_INPUT)
export AGENTOPS_REPORT_ROOT
override AGENTOPS_CACHE_ROOT := $(AGENTOPS_REPORT_ROOT)/cache
export AGENTOPS_CACHE_ROOT
override AGENTOPS_PYTEST_ADDOPTS := -p no:cacheprovider
override _AGENTOPS_PACKET_INPUT := $(value PACKET)
ifneq ($(findstring $$,$(_AGENTOPS_PACKET_INPUT)),)
$(error PACKET must not contain Make expansion syntax)
endif
override PACKET := $(_AGENTOPS_PACKET_INPUT)
export PACKET
ifneq ($(filter agent-build-preflight agent-build-closeout,$(MAKECMDGOALS)),)
ifeq ($(strip $(PACKET)),)
$(error PACKET=<path> is required for exact edit admission and closeout)
endif
endif

# AgentOps must bootstrap outside the checkout.  Keep this interpreter
# independent from the repository-oriented PYTHON default above: merely
# creating .venv/bin/python must never make admission execute repository
# bytes before the runner can validate them.  Preserve a caller spelling
# literally so Make functions in a command-line value stay data for the
# fail-closed shell grammar check below.
ifeq ($(origin AGENTOPS_PYTHON),undefined)
override _AGENTOPS_PYTHON_INPUT := python3
else
override _AGENTOPS_PYTHON_INPUT := $(value AGENTOPS_PYTHON)
endif
ifneq ($(findstring $$,$(_AGENTOPS_PYTHON_INPUT)),)
$(error AGENTOPS_PYTHON must not contain Make expansion syntax)
endif
override AGENTOPS_PYTHON := $(_AGENTOPS_PYTHON_INPUT)
export AGENTOPS_PYTHON

# Resolve the AgentOps bootstrap without executing it.  Only fixed host tools
# are used until both the lexical path and the resolved target are proven to
# be regular executables outside the source checkout and its Git state.  The
# macro checks the canonical target but leaves the absolute lexical launcher
# in $$agentops_python.  That executes one exact identity without a second
# PATH search while preserving an external venv's site-packages semantics.
define _AGENTOPS_RESOLVE_PYTHON
set -eu; \
agentops_raw="$${AGENTOPS_PYTHON-}"; \
case "$$agentops_raw" in \
  ""|*[!A-Za-z0-9_./+-]*) printf '%s\n' "AgentOps error: AGENTOPS_PYTHON must be a simple executable path" >&2; exit 2;; \
esac; \
agentops_source="$$(pwd -P)"; \
agentops_host_path=/usr/sbin:/usr/bin:/sbin:/bin; \
agentops_readlink="$$(PATH="$$agentops_host_path" command -v readlink 2>/dev/null || :)"; \
agentops_env="$$(PATH="$$agentops_host_path" command -v env 2>/dev/null || :)"; \
agentops_git="$$(PATH="$$agentops_host_path" command -v git 2>/dev/null || :)"; \
if test -z "$$agentops_readlink" || test -z "$$agentops_env" || test -z "$$agentops_git"; then \
  printf '%s\n' "AgentOps error: trusted host path resolver is unavailable" >&2; exit 2; \
fi; \
agentops_resolve() { \
  agentops_resolve_path="$$1"; \
  case "$$agentops_resolve_path" in /*) :;; *) return 1;; esac; \
  agentops_resolve_links=0; \
  while :; do \
    while test "$$agentops_resolve_path" != / && test "$${agentops_resolve_path%/}" != "$$agentops_resolve_path"; do \
      agentops_resolve_path="$${agentops_resolve_path%/}"; \
    done; \
    if test "$$agentops_resolve_path" = /; then printf '%s\n' /; return 0; fi; \
    if test ! -e "$$agentops_resolve_path" && test ! -L "$$agentops_resolve_path"; then return 1; fi; \
    agentops_resolve_dir="$${agentops_resolve_path%/*}"; \
    agentops_resolve_base="$${agentops_resolve_path##*/}"; \
    test -n "$$agentops_resolve_dir" || agentops_resolve_dir=/; \
    agentops_resolve_dir="$$(CDPATH= cd -P "$$agentops_resolve_dir" 2>/dev/null && pwd -P)" || return 1; \
    if test "$$agentops_resolve_dir" = /; then \
      agentops_resolve_candidate="/$$agentops_resolve_base"; \
    else \
      agentops_resolve_candidate="$$agentops_resolve_dir/$$agentops_resolve_base"; \
    fi; \
    if test -L "$$agentops_resolve_candidate"; then \
      agentops_resolve_links=$$((agentops_resolve_links + 1)); \
      test "$$agentops_resolve_links" -le 64 || return 1; \
      agentops_resolve_target="$$($$agentops_readlink "$$agentops_resolve_candidate" 2>/dev/null)" || return 1; \
      case "$$agentops_resolve_target" in \
        /*) agentops_resolve_path="$$agentops_resolve_target";; \
        *) agentops_resolve_path="$$agentops_resolve_dir/$$agentops_resolve_target";; \
      esac; \
    else \
      printf '%s\n' "$$agentops_resolve_candidate"; \
      return 0; \
    fi; \
  done; \
}; \
agentops_git_dir="$$($$agentops_env -i PATH="$$agentops_host_path" HOME=/ GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null "$$agentops_git" -C "$$agentops_source" rev-parse --absolute-git-dir 2>/dev/null || :)"; \
agentops_common_raw="$$($$agentops_env -i PATH="$$agentops_host_path" HOME=/ GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null "$$agentops_git" -C "$$agentops_source" rev-parse --git-common-dir 2>/dev/null || :)"; \
if test -z "$$agentops_git_dir" || test -z "$$agentops_common_raw"; then \
  printf '%s\n' "AgentOps error: source Git state cannot be resolved" >&2; exit 2; \
fi; \
case "$$agentops_common_raw" in \
  /*) agentops_common_lexical="$$agentops_common_raw";; \
  *) agentops_common_lexical="$$agentops_source/$$agentops_common_raw";; \
esac; \
agentops_git_dir="$$(agentops_resolve "$$agentops_git_dir" 2>/dev/null || :)"; \
agentops_common_dir="$$(agentops_resolve "$$agentops_common_lexical" 2>/dev/null || :)"; \
if test -z "$$agentops_git_dir" || test -z "$$agentops_common_dir"; then \
  printf '%s\n' "AgentOps error: source Git state cannot be normalized" >&2; exit 2; \
fi; \
agentops_search_path=; \
agentops_path_remaining="$${PATH-}:"; \
while test -n "$$agentops_path_remaining"; do \
  agentops_path_entry="$${agentops_path_remaining%%:*}"; \
  agentops_path_remaining="$${agentops_path_remaining#*:}"; \
  case "$$agentops_path_entry" in \
    /*) agentops_path_lexical="$$agentops_path_entry";; \
    *) agentops_path_lexical="$$agentops_source/$${agentops_path_entry:-.}";; \
  esac; \
  agentops_path_resolved="$$(agentops_resolve "$$agentops_path_lexical" 2>/dev/null || :)"; \
  test -n "$$agentops_path_resolved" && test -d "$$agentops_path_resolved" || continue; \
  agentops_path_allowed=1; \
  for agentops_boundary in "$$agentops_source" "$$agentops_git_dir" "$$agentops_common_dir"; do \
    case "$$agentops_path_lexical" in "$$agentops_boundary"|"$$agentops_boundary"/*) agentops_path_allowed=0;; esac; \
    case "$$agentops_path_resolved" in "$$agentops_boundary"|"$$agentops_boundary"/*) agentops_path_allowed=0;; esac; \
  done; \
  if test "$$agentops_path_allowed" = 1; then \
    agentops_search_path="$${agentops_search_path:+$$agentops_search_path:}$$agentops_path_resolved"; \
  fi; \
done; \
agentops_search_path="$${agentops_search_path:+$$agentops_search_path:}$$agentops_host_path"; \
case "$$agentops_raw" in \
  /*) agentops_lexical="$$agentops_raw";; \
  */*) agentops_lexical="$$agentops_source/$$agentops_raw";; \
  *) agentops_lexical="$$(PATH="$$agentops_search_path" command -v "$$agentops_raw" 2>/dev/null || :)";; \
esac; \
case "$$agentops_lexical" in \
  /*) :;; \
  *) printf '%s\n' "AgentOps error: AGENTOPS_PYTHON is unavailable on the external host PATH" >&2; exit 2;; \
esac; \
if test ! -f "$$agentops_lexical" || test ! -x "$$agentops_lexical"; then \
  printf '%s\n' "AgentOps error: AGENTOPS_PYTHON is not an executable regular file" >&2; exit 2; \
fi; \
agentops_python_resolved="$$(agentops_resolve "$$agentops_lexical" 2>/dev/null || :)"; \
if test -z "$$agentops_python_resolved" || test ! -f "$$agentops_python_resolved" || test ! -x "$$agentops_python_resolved"; then \
  printf '%s\n' "AgentOps error: AGENTOPS_PYTHON cannot be resolved" >&2; exit 2; \
fi; \
for agentops_boundary in "$$agentops_source" "$$agentops_git_dir" "$$agentops_common_dir"; do \
  case "$$agentops_lexical" in "$$agentops_boundary"|"$$agentops_boundary"/*) printf '%s\n' "AgentOps error: AGENTOPS_PYTHON must be external to source and Git state" >&2; exit 2;; esac; \
  case "$$agentops_python_resolved" in "$$agentops_boundary"|"$$agentops_boundary"/*) printf '%s\n' "AgentOps error: AGENTOPS_PYTHON must be external to source and Git state" >&2; exit 2;; esac; \
done; \
agentops_python="$$agentops_lexical"
endef

# Export the fixed AgentOps execution environment inside each recipe shell.
# Values derived from caller paths stay in already-exported shell variables;
# they are never interpolated into shell source. This is compatible with GNU
# Make 3.81, which cannot combine target-specific `override` and `export`.
define _AGENTOPS_EXPORT_ENV
export PYTHONDONTWRITEBYTECODE=1; \
export PYTHONPYCACHEPREFIX="$${AGENTOPS_REPORT_ROOT}/cache/python-pycache"; \
export PYTEST_ADDOPTS='-p no:cacheprovider'; \
export RUFF_CACHE_DIR="$${AGENTOPS_REPORT_ROOT}/cache/ruff"; \
export XDG_CACHE_HOME="$${AGENTOPS_REPORT_ROOT}/cache/xdg"; \
export HYPOTHESIS_STORAGE_DIRECTORY="$${AGENTOPS_REPORT_ROOT}/cache/hypothesis"; \
export DHARMA_OPS_DIR="$${AGENTOPS_REPORT_ROOT}/onboard"; \
export AGENTOPS_PYTHON="$$agentops_python"; \
export PYTHON="$$agentops_python"; \
export VENV_PYTHON="$$agentops_python"; \
export PYTEST="$$agentops_python -m pytest"; \
export REPO_PYTHON="PYTHONPATH=. $$agentops_python"
endef

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
	@echo "  make slop-ratchet  Stop-the-Slop probe delta-ratchet vs committed baseline"
	@echo "  make slop-baseline Re-freeze the Stop-the-Slop probe baseline"
	@echo "  make docops-report Generate local DocOps JSON/Markdown reports"
	@echo "  make ci-truth ARGS='--pr 123' Evaluate GitHub checks against the CI truth contract"
	@echo "  make pr-queue Classify open GitHub PRs into a receipt-backed review queue"
	@echo "  make pr-packet PR=123 Create a Codex/Claude review packet for one PR"
	@echo "  make pr-reviewers Show local Codex/Claude reviewer readiness"
	@echo "  make pr-run-codex PR=123 Run Codex against the latest review packet"
	@echo "  make pr-run-claude PR=123 Run Claude Code against the latest review packet"
	@echo "  make pr-gate PR=123 Verify merge gate against live GitHub state"
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
	@echo "  make onboard      Show truthful read-only session status; nonzero means not ready"
	@echo "  make onboarding-macos-compatibility  Reproduce the required GNU Make 3.81 + Darwin proof"
	@echo "  make organism-status Render the whole-organism projection (runtime, agents, liveness)"
	@echo "  make orient       Compatibility alias for make organism-status"
	@echo "  make vision       Render the vision transmission: what this is FOR (read-only; ARGS=--crystal|--full|--registry|--json|--check|--packet)"
	@echo "  make agent-register Check persistent A2A identity registration route and drift"
	@echo "  make agent-onboard Compatibility alias for make agent-register"
	@echo "  make agent-build-preflight PACKET=<path>  Admit one exact packet and baseline"
	@echo "  make agent-build-closeout PACKET=<path>  Verify that packet's scope and gates"
	@echo "  make status       Quick cross-agent state snapshot (PRs, stale, hotlist, track)"
	@echo "  make a2a-status   Connect to the AGNI hub: Devin identity + live fleet roster + inbox state"
	@echo "  make a2a-up       Run the persistent Devin A2A agent (registers on fleet, drains inbox)"
	@echo "  make a2a-send     Send a packet: make a2a-send TO=codex FILE=path/to/packet.md"
	@echo "  make go-ci        Run Go evidence sense-organ fmt/vet/test gates"
	@echo "  make go-build     Compile the 4 Go tool mains into their module dirs (gitignored)"
	@echo "  make frontend-check  Dashboard lane: frozen npm ci + lint + build (same as CI)"
	@echo "  make terminal-check  Terminal lane: frozen bun install + typecheck + tests (same as CI)"
	@echo ""

# One documented command from fresh clone to working .venv, idempotent
# (WP-0A / TIT-004). Reuses a base-environment uv only when it is exactly the
# pinned version; otherwise installs the pin through the current Python's user
# site. The dependency path is always uv lock --check (drift oracle) followed
# by uv sync --frozen --extra dev (exact locked closure, no live resolution).
bootstrap:
	@set -eu; \
	uv_bin="$$(command -v uv 2>/dev/null || :)"; \
	if [ -z "$$uv_bin" ] || ! "$$uv_bin" --version 2>/dev/null | grep -Eq "^uv $(UV_VERSION)( |$$)"; then \
		python3 -m pip install --user --quiet "uv==$(UV_VERSION)" || { \
			echo "bootstrap: FAILED to install pinned uv==$(UV_VERSION) via 'python3 -m pip install --user'" >&2; \
			echo "bootstrap: check that python3 and pip work and that the package index is reachable" >&2; \
			exit 1; }; \
		uv_bin="$$(python3 -m site --user-base)/bin/uv"; \
	fi; \
	test -x "$$uv_bin" || { echo "bootstrap: pinned uv is not executable at $$uv_bin" >&2; exit 1; }; \
	"$$uv_bin" --version | grep -Eq "^uv $(UV_VERSION)( |$$)" || { \
		echo "bootstrap: resolved uv is not the pinned $(UV_VERSION): $$("$$uv_bin" --version)" >&2; exit 1; }; \
	"$$uv_bin" lock --check; \
	"$$uv_bin" sync --frozen --extra dev; \
	echo "bootstrap: OK (.venv synced from frozen uv.lock with uv $(UV_VERSION))"

# WP-0A: install is the frozen path. The old unpinned `pip install -e ".[dev]"`
# bypassed uv.lock and silently resolved fresh at install time.
install: bootstrap

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
	$(VENV_PYTHON) -m pytest tests/ -q --tb=line -x --timeout=10 -m "not slow and not docker and not network"

lint:
	$(RUFF) check dharma_swarm/ --select=E,F,W --ignore=E501

syntax-check:
	@$(VENV_PYTHON) -m compileall -q dharma_swarm api scripts && echo "syntax-check: OK (compileall clean)"

# Undefined names are guaranteed NameErrors at runtime — always blocking.
lint-blockers:
	@$(RUFF) check dharma_swarm/ api/ scripts/ --select=F821 --quiet && echo "lint-blockers: OK (no undefined names)"

# The watchmen-watcher: verifies the verification gates themselves work.
# Born 2026-06-12 after syntax-check, test-fast, and suite collection were
# all found broken simultaneously with nothing noticing.
# WP-0B (TIT-001): a bounded behavioral sentinel runs real assertions so the
# success banner and the executed evidence are equivalent; the banner names
# exactly the gates that ran, nothing broader. VERIFIER_SENTINEL is
# overridable so the meta-contract test can substitute a failing sentinel
# and prove this target goes red.
VERIFIER_SENTINEL ?= tests/test_telos_gates.py

verifier-selfcheck:
	@echo "[1/5] syntax-check"
	@$(MAKE) -s syntax-check
	@echo "[2/5] lint-blockers (F821)"
	@$(MAKE) -s lint-blockers
	@echo "[3/5] test collection"
	@set -eu; \
		collect_log="$$(mktemp "$${TMPDIR:-/tmp}/dharma-collect-check.XXXXXX")"; \
		trap 'rm -f "$$collect_log"' EXIT HUP INT TERM; \
		if ! $(VENV_PYTHON) -m pytest tests/ --collect-only --assert=plain -q >"$$collect_log" 2>&1; then \
			echo "COLLECTION BROKEN:"; \
			tail -120 "$$collect_log"; \
			exit 1; \
		fi; \
		tail -1 "$$collect_log"
	@echo "[4/5] session status"
	@$(MAKE) -s onboard >/dev/null 2>&1 && echo "onboard: OK"
	@echo "[5/5] behavioral sentinel ($(VERIFIER_SENTINEL))"
	@set -eu; \
		sentinel_log="$$(mktemp "$${TMPDIR:-/tmp}/dharma-sentinel-check.XXXXXX")"; \
		trap 'rm -f "$$sentinel_log"' EXIT HUP INT TERM; \
		if ! $(VENV_PYTHON) -m pytest -p timeout $(VERIFIER_SENTINEL) -q --timeout=120 >"$$sentinel_log" 2>&1; then \
			echo "BEHAVIORAL SENTINEL FAILED:"; \
			tail -120 "$$sentinel_log"; \
			exit 1; \
		fi; \
		tail -1 "$$sentinel_log"
	@echo "verifier-selfcheck: OK (syntax, F821, collection, onboarding, behavioral sentinel)"

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

# WP-0C1 (TIT-004): `make semgrep` is the strict REQUIRED scan. It runs the
# security ruleset that WP-0C1R proved clean on merged main and fails closed:
# an absent scanner, a version off the ratified pin, or a wall-clock overrun
# is a named nonzero failure, never a green skip. The former warn-only
# behavior lives in `semgrep-advisory` (anti-slop rules; the OWNER_DEFERRED
# findings recorded in reports/governance/titanium/
# wp0c1r_semgrep_adjudication_2026-07-18.md stay visible there and in
# semgrep-strict — they are never baselined into the required scan).
# The wrapper expands --config .semgrep to production configs only;
# .semgrep/tests remains reserved for explicit rule-test runs.
SEMGREP_PIN ?= 1.168.0
semgrep:
	DHARMA_SEMGREP_EXPECTED_VERSION=$(SEMGREP_PIN) $(SEMGREP) --config .semgrep/security.yml --error --metrics=off

semgrep-advisory:
	DHARMA_SEMGREP_ALLOW_MISSING=1 $(SEMGREP) --config .semgrep/dharma-anti-slop.yml --metrics=off

semgrep-strict:
	$(SEMGREP) --config .semgrep --error --metrics=off

gitleaks:
	@command -v $(GITLEAKS) >/dev/null 2>&1 || { \
		echo "GITLEAKS_MISSING: '$(GITLEAKS)' not found on PATH — required secrets scan cannot run (install: https://github.com/gitleaks/gitleaks/releases)" >&2; \
		exit 2; }
	$(GITLEAKS) detect --source . --redact --no-banner --exit-code 1 < /dev/null

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
		tests/test_nats_live_production_evidence.py \
		tests/test_nats_substrate_contract.py \
		tests/test_nats_verification_split.py \
		tests/test_nats_transport.py \
		tests/test_a2a_send.py \
		tests/test_a2a_inbox_bridge.py \
		tests/test_a2a_inbox_bridge_tmux_scripts.py \
		tests/test_a2a_domain_reply_worker.py \
		tests/test_a2a_reply_capture.py \
		--tb=line

nats-live-production-matrix:
	$(REPO_PYTHON) scripts/governance/run_nats_live_production_matrix.py \
		--host-mode $${DHARMA_NATS_HOST_MODE:-non-live} \
		--endpoint $${NATS_URL:-nats://127.0.0.1:4222} \
		--broker-profile $${NATS_PROFILE:-local-live-jetstream}

uplift-guards:
	$(REPO_PYTHON) scripts/uplift_guards/run_pre_commit.py

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
	$(PYTHON) scripts/governance/render_active_track_includes.py --check
	$(PYTHON) scripts/docops/vision_navigation.py --check

slop-ratchet:
	$(PYTHON) scripts/governance/slop_ratchet.py

slop-baseline:
	$(PYTHON) scripts/governance/slop_ratchet.py --write-baseline

# Substrate audit: ruff + vulture + radon + bandit + grimp behind one door,
# delta-ratcheted against reports/governance/substrate_baseline.json.
# Advisory by default; substrate-audit-strict exits 1 on any count regression.
substrate-tools:
	$(PYTHON) -m pip install --quiet "vulture>=2.14" "radon>=6" "grimp>=3.9" "bandit>=1.8" "import-linter>=2.3" "pip-audit>=2.7"

substrate-audit:
	$(PYTHON) scripts/governance/substrate_audit.py

substrate-audit-strict:
	$(PYTHON) scripts/governance/substrate_audit.py --strict

substrate-baseline:
	$(PYTHON) scripts/governance/substrate_audit.py --write-baseline

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

# Pudgala Autopoiesis Protostar (graded claim/evidence binding). This is the
# anti-slop quality membrane, not Dharma Forge / Forge Swarm Evolution Arena.
# claim-evidence-check is
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

# S6 mutation gate (Pudgala Autopoiesis Protostar P3-09): runs mutmut on the configured surfaces
# (pyproject [tool.mutmut]) and writes reports/governance/mutation_score.json, the
# report the `mutation_score_gte` criterion reads. SLOW — a separate step, NOT in
# governance-all. Needs `pip install mutmut`.
mutation-test:
	$(REPO_PYTHON) scripts/governance/run_mutation_score.py --threshold $(MUTATION_THRESHOLD)

# Packet-aware preflight: verifier-selfcheck reaches session status exactly
# once; do not also list onboard as a direct
# prerequisite. The shared AgentOps evaluator records
# a digest-bound admission receipt outside the checkout and requires the exact
# clean baseline (HEAD == base_ref) before any implementation edit.
# Target-specific exports flow through the validation prerequisite and every
# later recursive Make call. The validator therefore runs before any cache or
# onboarding receipt write, even under `make -j`; after it passes, onboarding
# is confined to a child of the same external root. Command-line overrides
# cannot weaken these boundaries, including when Make propagates them to a
# submake through MAKEOVERRIDES.
# GNU Make 3.81 rejects target-specific `override export VAR := value`.
# Ordinary overrides keep Make-side policy fixed; `_AGENTOPS_EXPORT_ENV`
# applies the same values to each recipe only after the trusted interpreter is
# resolved, without globally exporting caller-controlled Make variables.
agentops-report-root-check agent-build-preflight agent-build-closeout: override PYTHONDONTWRITEBYTECODE := 1
agentops-report-root-check agent-build-preflight agent-build-closeout: override PYTHONPYCACHEPREFIX := $(AGENTOPS_CACHE_ROOT)/python-pycache
agentops-report-root-check agent-build-preflight agent-build-closeout: override PYTEST_ADDOPTS := $(AGENTOPS_PYTEST_ADDOPTS)
agentops-report-root-check agent-build-preflight agent-build-closeout: override RUFF_CACHE_DIR := $(AGENTOPS_CACHE_ROOT)/ruff
agentops-report-root-check agent-build-preflight agent-build-closeout: override XDG_CACHE_HOME := $(AGENTOPS_CACHE_ROOT)/xdg
agentops-report-root-check agent-build-preflight agent-build-closeout: override HYPOTHESIS_STORAGE_DIRECTORY := $(AGENTOPS_CACHE_ROOT)/hypothesis
agentops-report-root-check agent-build-preflight agent-build-closeout: override DHARMA_OPS_DIR := $(AGENTOPS_REPORT_ROOT)/onboard
agentops-report-root-check agent-build-preflight agent-build-closeout: override AGENTOPS_PYTHON := $(_AGENTOPS_PYTHON_INPUT)
agentops-report-root-check agent-build-preflight agent-build-closeout: override PYTHON := $(_AGENTOPS_PYTHON_INPUT)
agentops-report-root-check agent-build-preflight agent-build-closeout: override VENV_PYTHON := $(_AGENTOPS_PYTHON_INPUT)
agentops-report-root-check agent-build-preflight agent-build-closeout: override PYTEST := $(_AGENTOPS_PYTHON_INPUT) -m pytest
agentops-report-root-check agent-build-preflight agent-build-closeout: override REPO_PYTHON := PYTHONPATH=. $(_AGENTOPS_PYTHON_INPUT)

agentops-report-root-check:
	@$(_AGENTOPS_RESOLVE_PYTHON); \
	$(_AGENTOPS_EXPORT_ENV); \
	"$$agentops_python" scripts/governance/run_agent_work_packet.py --validate-report-root "$${AGENTOPS_REPORT_ROOT}" --validate-report-child cache --validate-report-child cache/hypothesis --validate-report-child onboard

agent-build-preflight: agentops-report-root-check
	@$(_AGENTOPS_RESOLVE_PYTHON); \
	$(_AGENTOPS_EXPORT_ENV); \
	$(MAKE) -s verifier-selfcheck MAKEOVERRIDES= AGENTOPS_PYTHON="$$agentops_python" PYTHON="$$agentops_python" VENV_PYTHON="$$agentops_python" PYTEST="$$agentops_python -m pytest" REPO_PYTHON="PYTHONPATH=. $$agentops_python"
	@$(_AGENTOPS_RESOLVE_PYTHON); \
	$(_AGENTOPS_EXPORT_ENV); \
	$(MAKE) -s hygiene-check MAKEOVERRIDES= AGENTOPS_PYTHON="$$agentops_python" PYTHON="$$agentops_python" VENV_PYTHON="$$agentops_python" PYTEST="$$agentops_python -m pytest" REPO_PYTHON="PYTHONPATH=. $$agentops_python"
	@$(_AGENTOPS_RESOLVE_PYTHON); \
	$(_AGENTOPS_EXPORT_ENV); \
	"$$agentops_python" scripts/governance/run_agent_work_packet.py --packet "$${PACKET}" --preflight --report-root "$${AGENTOPS_REPORT_ROOT}"
	@printf "\nAgent build preflight complete. Close out the same packet with: make agent-build-closeout PACKET=<path>\n"

# Closeout keeps the established hygiene + governance bundle and, for a packet
# run, invokes the same evaluator in descendant-aware closeout mode exactly
# once. Its report root is explicit and external; the evaluator checks the
# preflight digest plus committed/working/staged/untracked scope union.
agent-build-closeout: agentops-report-root-check
	@$(_AGENTOPS_RESOLVE_PYTHON); \
	$(_AGENTOPS_EXPORT_ENV); \
	"$$agentops_python" scripts/governance/run_agent_work_packet.py --packet "$${PACKET}" --closeout --report-root "$${AGENTOPS_REPORT_ROOT}"
	@$(_AGENTOPS_RESOLVE_PYTHON); \
	$(_AGENTOPS_EXPORT_ENV); \
	"$$agentops_python" scripts/governance/hygiene/scan.py --output /tmp/dharma-hygiene-audit.txt
	-@$(_AGENTOPS_RESOLVE_PYTHON); \
	$(_AGENTOPS_EXPORT_ENV); \
	"$$agentops_python" scripts/governance/substrate_audit.py
	@$(_AGENTOPS_RESOLVE_PYTHON); \
	$(_AGENTOPS_EXPORT_ENV); \
	$(MAKE) governance-all MAKEOVERRIDES= AGENTOPS_PYTHON="$$agentops_python" PYTHON="$$agentops_python" VENV_PYTHON="$$agentops_python" PYTEST="$$agentops_python -m pytest" REPO_PYTHON="PYTHONPATH=. $$agentops_python"
	@printf "\nAgent build closeout complete. Hygiene audit receipt: /tmp/dharma-hygiene-audit.txt · Substrate audit: /tmp/dharma-substrate-audit.txt\n"

spine-check:
	$(PYTHON) -m scripts.uplift_guards.check_spine_ownership

# Session status: renders authoritative read-only evidence. A nonzero Make
# result means the session is not ready; a zero result is status, not edit
# authorization. GNU Make reports any failed recipe as exit 2; the displayed
# verdict and direct Python CLI retain the exact typed code. Exact edit
# admission belongs to agent-build-preflight. Documented flags forward via
# ARGS, e.g. `make onboard ARGS=--json`.
onboard:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/governance/agent_onboard.py $(ARGS)

# Purpose/telos transmission + vision-doc navigation. Read-only projection of
# docs/vision_maps/VISION_TRANSMISSION.md and the MEGAFILE_INDEX Slot-1 draft
# registry. Deliberately has NO prerequisites (no onboard dependence) and no
# authority: not session status, liveness, edit admission, ratification, or
# merge. Documented flags forward via ARGS, e.g. `make vision ARGS=--crystal`.
vision:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/docops/vision_navigation.py $(ARGS)

# Full local reproducer for the required macOS compatibility context. Invoke
# this target through stock /usr/bin/make so a parser regression fails before
# any recipe can falsely report success.
onboarding-macos-compatibility:
	@set -eu; \
		version="$$(/usr/bin/make --version | sed -n '1p')"; \
		test "$$version" = "GNU Make 3.81"; \
		printf '%s\n' "$$version"
	@/usr/bin/make -n onboard >/dev/null
	@/usr/bin/make -n orient >/dev/null
	@/usr/bin/make -n vision >/dev/null
	@/usr/bin/make -n help >/dev/null
	$(PYTHON) -m pytest -q \
		tests/test_agent_work_packet.py::test_darwin_negative_confinement_executes_and_denies_outside_write \
		tests/test_agent_work_packet.py::test_darwin_account_temp_root_native_and_prepares_report_root \
		tests/test_agent_work_packet.py::test_darwin_account_temp_root_uses_getconf_with_scrubbed_environment \
		tests/test_agent_work_packet.py::test_darwin_report_anchor_rejects_environment_minted_temp_root \
		tests/test_agent_work_packet.py::test_private_report_anchor_enforces_owner_mode_and_symlink_boundaries

# Whole-organism status: identity, tracks, lanes, agents, receipts, A2A,
# body state, and broken register. Deep, mutation-free projection — it
# regenerates NOTHING. The tracked context artifacts are
# refreshed only by their explicit owner command:
#   $(PYTHON) scripts/governance/orientation_graph.py --write-context
organism-status: override PYTHONDONTWRITEBYTECODE := 1
organism-status:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/governance/orientation_graph.py

# Compatibility name retained for existing callers.
orient: organism-status

# Fleet-identity registration: the join route for a NEW persistent A2A agent
# (card, runtime registration, roster, git seat, announcement, presence) plus
# a drift check across the identity surfaces. Read-only; always exits 0.
# `make onboard` reports session status; this checks identity registration.
# See docs/ops/A2A_AGENT_ONBOARDING.md.
agent-register: override PYTHONDONTWRITEBYTECODE := 1
agent-register:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/governance/a2a_agent_onboard.py $(ARGS)

# Compatibility name retained for existing callers.
agent-onboard: agent-register

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

# ── Polyglot lanes (WP-0H): same commands locally and in CI ────────────────
# Keep these recipes in lockstep with the dashboard/terminal jobs in
# .github/workflows/tests.yml — tests/test_polyglot_ci_contract.py compares
# the Make commands against the workflow commands.

frontend-check:
	npm --prefix dashboard ci --legacy-peer-deps
	npm --prefix dashboard run lint -- --quiet
	npm --prefix dashboard run build

# NOTE: the WP-0H plan spells these `bun --cwd terminal ...`, but on the
# pinned bun (1.3.11) `bun --cwd terminal run typecheck` prints usage and
# exits 0 — a false-green trap. `cd` mirrors CI's working-directory exactly.
terminal-check:
	cd terminal && bun install --frozen-lockfile
	cd terminal && bun run typecheck
	cd terminal && bun test

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
	bash scripts/refresh_provider_status.sh

hermes-heartbeat:
	$(PYTHON) scripts/hermes_heartbeat_poll.py
