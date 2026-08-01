"""WP-0H polyglot CI orchestration contract (TIT-003, TIT-015).

The Go, dashboard, and terminal lanes must exist in the required tests
workflow, run on pull_request, declare exact pinned toolchains that agree
with the read-only language manifests, and contain no false-green pattern.
The workflow cannot run locally; its text is the enforceable surface (the
same pattern as tests/test_docops_reconcile_workflow.py).

Authority: docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md (WP-0H).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_YML_PATH = REPO_ROOT / ".github" / "workflows" / "tests.yml"
TESTS_YML = TESTS_YML_PATH.read_text(encoding="utf-8")
WORKFLOW = yaml.safe_load(TESTS_YML)
JOBS = WORKFLOW["jobs"]
MAKEFILE = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

GO_LANES = ("go-adapter-contracts", "go-evidence-ingestor")
POLYGLOT_LANES = GO_LANES + ("dashboard", "terminal")

SHA_PINNED_USES = re.compile(r"@[0-9a-f]{40}\b")
EXACT_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _triggers() -> dict:
    # PyYAML parses the bare `on:` key as boolean True (YAML 1.1).
    return WORKFLOW.get("on") or WORKFLOW[True]


def _steps(job_id: str) -> list[dict]:
    return JOBS[job_id]["steps"]


def _run_text(job_id: str) -> str:
    return "\n".join(step["run"] for step in _steps(job_id) if "run" in step)


def _setup_with(job_id: str, action: str) -> dict:
    for step in _steps(job_id):
        if step.get("uses", "").startswith(f"{action}@"):
            return step["with"]
    raise AssertionError(f"{job_id} has no {action} step")


def _command_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ── Lane existence and trigger ──────────────────────────────────────────────

def test_required_polyglot_lanes_exist() -> None:
    for lane in POLYGLOT_LANES:
        assert lane in JOBS, f"required polyglot lane {lane!r} missing from tests.yml"


def test_workflow_runs_on_pull_request_and_merge_group() -> None:
    triggers = _triggers()
    assert "pull_request" in triggers
    assert "merge_group" in triggers


# ── Go lanes: one exact patch-level pin, manifest-compatible, hermetic ──────

def test_go_lanes_share_one_exact_patch_level_pin() -> None:
    pins = {lane: _setup_with(lane, "actions/setup-go")["go-version"] for lane in GO_LANES}
    for lane, pin in pins.items():
        assert EXACT_SEMVER.match(str(pin)), (
            f"{lane} go-version {pin!r} is not an exact x.y.z pin"
        )
    assert len(set(pins.values())) == 1, f"Go lanes disagree on the toolchain: {pins}"


def test_go_pin_is_compatible_with_readonly_module_directives() -> None:
    pin = str(_setup_with(GO_LANES[0], "actions/setup-go")["go-version"])
    go_mods = sorted(REPO_ROOT.glob("tools/*/go.mod"))
    assert go_mods, "no tools/*/go.mod modules found"
    for go_mod in go_mods:
        match = re.search(r"^go (\d+\.\d+(?:\.\d+)?)$", go_mod.read_text(), re.M)
        assert match, f"{go_mod} declares no go directive"
        directive = match.group(1)
        assert (pin + ".").startswith(directive + "."), (
            f"CI Go pin {pin} does not satisfy `go {directive}` in {go_mod}"
        )


def test_go_lanes_run_make_go_ci_without_live_module_resolution() -> None:
    for lane in GO_LANES:
        go_ci_steps = [s for s in _steps(lane) if "make go-ci" in s.get("run", "")]
        assert go_ci_steps, f"{lane} does not run `make go-ci`"
        env = go_ci_steps[0].get("env", {})
        assert env.get("GOPROXY") == "off", f"{lane} go-ci step must set GOPROXY=off"
        assert env.get("GOSUMDB") == "off", f"{lane} go-ci step must set GOSUMDB=off"
        assert env.get("GOFLAGS") == "-mod=readonly", (
            f"{lane} go-ci step must set GOFLAGS=-mod=readonly"
        )


# ── Dashboard lane: exact Node pin, frozen lockfile, lint + build ───────────

def test_dashboard_lane_pins_exact_node_version() -> None:
    node_pin = str(_setup_with("dashboard", "actions/setup-node")["node-version"])
    assert EXACT_SEMVER.match(node_pin), (
        f"dashboard node-version {node_pin!r} is a floating pin, not exact x.y.z"
    )


def test_dashboard_lane_installs_from_committed_lockfile() -> None:
    with_block = _setup_with("dashboard", "actions/setup-node")
    assert with_block.get("cache-dependency-path") == "dashboard/package-lock.json"
    assert (REPO_ROOT / "dashboard" / "package-lock.json").is_file()
    run_text = _run_text("dashboard")
    assert "npm ci --legacy-peer-deps" in run_text
    assert "npm install" not in run_text, "dashboard CI must use `npm ci`, never bare install"


def test_dashboard_lane_lints_and_builds() -> None:
    run_text = _run_text("dashboard")
    assert "npm run lint -- --quiet" in run_text
    assert "npm run build" in run_text


# ── Terminal lane: pinned Bun, frozen lockfile, typecheck + behavior ────────

def test_terminal_lane_bun_pin_matches_package_manager_manifest() -> None:
    manifest = json.loads((REPO_ROOT / "terminal" / "package.json").read_text())
    declared = manifest["packageManager"]
    assert declared.startswith("bun@"), f"unexpected packageManager {declared!r}"
    declared_version = declared.split("@", 1)[1]
    assert EXACT_SEMVER.match(declared_version)

    match = re.search(r"npm install -g bun@(\S+)", _run_text("terminal"))
    assert match, "terminal lane must install Bun through a version-pinned installer"
    assert match.group(1) == declared_version, (
        f"CI bun pin {match.group(1)} != manifest packageManager {declared_version}"
    )


def test_terminal_lane_runs_typecheck_and_behavioral_tests_frozen() -> None:
    assert JOBS["terminal"]["defaults"]["run"]["working-directory"] == "terminal"
    assert (REPO_ROOT / "terminal" / "bun.lock").is_file()
    run_text = _run_text("terminal")
    assert "bun install --frozen-lockfile" in run_text
    assert "bun run typecheck" in run_text
    assert "bun test" in run_text


def test_node_pin_is_uniform_across_node_lanes() -> None:
    dashboard_pin = _setup_with("dashboard", "actions/setup-node")["node-version"]
    terminal_pin = _setup_with("terminal", "actions/setup-node")["node-version"]
    assert dashboard_pin == terminal_pin, (
        f"Node lanes disagree: dashboard={dashboard_pin} terminal={terminal_pin}"
    )


# ── Supply-chain and false-green hygiene for the whole workflow ─────────────

def test_every_action_is_sha_pinned() -> None:
    for job_id, job in JOBS.items():
        for step in job["steps"]:
            uses = step.get("uses")
            if uses is None:
                continue
            assert SHA_PINNED_USES.search(uses), (
                f"{job_id} uses unpinned action {uses!r}; pin to a full commit SHA"
            )


def test_no_false_green_patterns() -> None:
    lines = _command_lines(TESTS_YML)
    assert not any("|| true" in line for line in lines), (
        "`|| true` is the dead-gate pattern; a required lane may never swallow failure"
    )
    assert not any("continue-on-error" in line for line in lines), (
        "continue-on-error inside the required tests workflow is a false-green pattern"
    )


def test_no_unpinned_script_download_in_any_lane() -> None:
    pipe_to_shell = re.compile(r"(curl|wget)[^\n|]*\|\s*(ba|z)?sh")
    for line in _command_lines(TESTS_YML):
        assert not pipe_to_shell.search(line), f"unpinned piped installer: {line!r}"


# ── Local/CI byte-comparability: Make targets mirror workflow commands ──────

def test_make_targets_mirror_workflow_commands() -> None:
    # (make recipe line, workflow command, lane running it)
    pairs = [
        ("npm --prefix dashboard ci --legacy-peer-deps", "npm ci --legacy-peer-deps", "dashboard"),
        ("npm --prefix dashboard run lint -- --quiet", "npm run lint -- --quiet", "dashboard"),
        ("npm --prefix dashboard run build", "npm run build", "dashboard"),
        # Not `bun --cwd terminal ...`: on pinned bun 1.3.11 that form prints
        # usage and exits 0 (a false green). `cd` matches CI's
        # working-directory, keeping local and CI commands byte-comparable.
        ("cd terminal && bun install --frozen-lockfile", "bun install --frozen-lockfile", "terminal"),
        ("cd terminal && bun run typecheck", "bun run typecheck", "terminal"),
        ("cd terminal && bun test", "bun test", "terminal"),
    ]
    for make_cmd, workflow_cmd, lane in pairs:
        assert make_cmd in MAKEFILE, f"Makefile lacks {make_cmd!r}"
        assert workflow_cmd in _run_text(lane), f"{lane} lane lacks {workflow_cmd!r}"

    for target in ("frontend-check:", "terminal-check:", "go-ci:"):
        assert re.search(rf"^{re.escape(target)}", MAKEFILE, re.M), (
            f"Makefile lacks the {target[:-1]} target"
        )
