"""WP-0C1 (TIT-004): the required Semgrep scan fails closed.

Contract under test: ``scripts/governance/run_semgrep_with_ca.sh`` plus the
Makefile scanner targets. A missing or version-mismatched scanner is a named
nonzero failure, never a green skip; the warn-only behavior lives in an
explicitly named advisory target that never enters ``governance-all``; the
scan carries a portable wall-clock bound converted into a named nonzero failure.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "scripts/governance/run_semgrep_with_ca.sh"
MAKEFILE = REPO_ROOT / "Makefile"
RATIFIED_PIN = "1.168.0"


def _run_wrapper(args: list[str], env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_overrides)
    return subprocess.run(
        [str(WRAPPER), *args],
        cwd=REPO_ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _fake_semgrep(tmp_path: Path, *, version: str, body: str = "exit 0") -> Path:
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "semgrep"
    script = (
        "#!/usr/bin/env bash\n"
        'if [[ "${1:-}" == "--version" ]]; then\n'
        f'  echo "{version}"\n'
        "  exit 0\n"
        "fi\n"
        f"{body}\n"
    )
    fake.write_text(script)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return fake


def _fake_hanging_version_semgrep(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "hanging-version-bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "semgrep"
    fake.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            if [[ "${1:-}" == "--version" ]]; then
              sleep 30
              exit 0
            fi
            exit 0
            """
        )
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return fake


def test_absent_semgrep_is_named_nonzero_failure():
    proc = _run_wrapper(
        ["--config", ".semgrep", "--error", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": "definitely-missing-semgrep-xyz",
            "DHARMA_SEMGREP_ALLOW_MISSING": "",
        },
    )
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_MISSING" in proc.stderr


def test_absent_semgrep_advisory_optin_is_explicit_skip():
    proc = _run_wrapper(
        ["--config", ".semgrep", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": "definitely-missing-semgrep-xyz",
            "DHARMA_SEMGREP_ALLOW_MISSING": "1",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert "SEMGREP_SKIPPED" in proc.stderr


def test_version_mismatch_is_named_nonzero_failure(tmp_path):
    fake = _fake_semgrep(tmp_path, version="1.99.9")
    proc = _run_wrapper(
        ["--config", ".semgrep", "--error", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": str(fake),
            "DHARMA_SEMGREP_EXPECTED_VERSION": RATIFIED_PIN,
        },
    )
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_VERSION_MISMATCH" in proc.stderr
    assert "1.99.9" in proc.stderr
    assert RATIFIED_PIN in proc.stderr


def test_version_probe_timeout_is_named_nonzero_failure(tmp_path):
    fake = _fake_hanging_version_semgrep(tmp_path)
    started = time.monotonic()
    proc = _run_wrapper(
        ["--config", ".semgrep", "--error", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": str(fake),
            "DHARMA_SEMGREP_EXPECTED_VERSION": RATIFIED_PIN,
            "DHARMA_SEMGREP_WALLCLOCK": "1",
        },
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_VERSION_TIMEOUT" in proc.stderr
    assert elapsed < 10, f"version timeout leaked descendants for {elapsed:.1f}s"


def test_matching_version_execs_scanner_with_expanded_args(tmp_path):
    args_file = tmp_path / "recorded-args"
    fake = _fake_semgrep(
        tmp_path,
        version=RATIFIED_PIN,
        body=f'printf "%s\\n" "$@" > "{args_file}"\nexit 0',
    )
    proc = _run_wrapper(
        ["--config", ".semgrep", "--error", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": str(fake),
            "DHARMA_SEMGREP_EXPECTED_VERSION": RATIFIED_PIN,
        },
    )
    assert proc.returncode == 0, proc.stderr
    recorded = args_file.read_text().splitlines()
    assert ".semgrep/dharma-anti-slop.yml" in recorded
    assert ".semgrep/security.yml" in recorded
    assert "--error" in recorded


def test_wallclock_overrun_is_named_nonzero_failure(tmp_path):
    fake = _fake_semgrep(tmp_path, version=RATIFIED_PIN, body="sleep 30\nexit 0")
    started = time.monotonic()
    proc = _run_wrapper(
        ["--config", ".semgrep", "--metrics=off"],
        {"DHARMA_SEMGREP_BIN": str(fake), "DHARMA_SEMGREP_WALLCLOCK": "1"},
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_TIMEOUT" in proc.stderr
    assert elapsed < 10, f"scan timeout leaked descendants for {elapsed:.1f}s"


def test_invalid_wallclock_is_named_nonzero_failure(tmp_path):
    fake = _fake_semgrep(tmp_path, version=RATIFIED_PIN)
    proc = _run_wrapper(
        ["--config", ".semgrep", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": str(fake),
            "DHARMA_SEMGREP_WALLCLOCK": "not-a-number",
        },
    )
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_TIMEOUT_CONFIG_INVALID" in proc.stderr


@pytest.mark.skipif(
    shutil.which("semgrep") is None,
    reason="semgrep binary not installed on this host; the strict-scan positive "
    "path runs in the semgrep CI lane and was proven by the WP-0C1R receipt",
)
def test_strict_scan_fails_on_violating_fixture(tmp_path):
    rule = tmp_path / "rule.yml"
    rule.write_text(
        textwrap.dedent(
            """\
            rules:
              - id: wp0c1-negative-control-eval
                pattern: eval(...)
                message: WP-0C1 negative-control fixture violation
                severity: ERROR
                languages: [python]
            """
        )
    )
    target = tmp_path / "violating.py"
    target.write_text('eval("1 + 1")\n')
    proc = _run_wrapper(
        ["--config", str(rule), "--error", "--metrics=off", str(target)],
        {},
    )
    assert proc.returncode != 0, proc.stdout


def _makefile_recipe(target: str) -> str:
    text = MAKEFILE.read_text()
    lines = text.splitlines()
    body: list[str] = []
    capture = False
    for line in lines:
        if line.startswith(f"{target}:"):
            capture = True
            continue
        if capture:
            if line.startswith("\t") or not line.strip():
                body.append(line)
                if not line.strip() and body and not any(
                    later.startswith("\t") for later in body[-1:]
                ):
                    continue
            else:
                break
    return "\n".join(body)


def test_make_semgrep_is_the_strict_required_scan():
    recipe = _makefile_recipe("semgrep")
    assert "--error" in recipe, "make semgrep must be strict (--error)"
    assert ".semgrep/security.yml" in recipe, (
        "the required scan runs the security ruleset WP-0C1R proved clean"
    )
    assert "DHARMA_SEMGREP_EXPECTED_VERSION" in recipe, (
        "the required scan enforces the ratified version pin"
    )


def test_advisory_target_exists_and_never_enters_governance_all():
    text = MAKEFILE.read_text()
    assert "semgrep-advisory:" in text
    recipe = _makefile_recipe("semgrep-advisory")
    assert "DHARMA_SEMGREP_ALLOW_MISSING=1" in recipe
    assert "--error" not in recipe
    governance_line = next(
        line for line in text.splitlines() if line.startswith("governance-all:")
    )
    assert "semgrep-advisory" not in governance_line
    assert " semgrep " in governance_line + " "
    assert "gitleaks" in governance_line


def test_make_gitleaks_absent_is_named_nonzero_failure():
    proc = subprocess.run(
        ["make", "gitleaks", "GITLEAKS=definitely-missing-gitleaks-xyz"],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "GITLEAKS_MISSING" in proc.stdout + proc.stderr


# ── WP-0C1R ratified-disposition contract (operator decisions A1 + B1,
# 2026-08-02) ─────────────────────────────────────────────────────────
# The 21 strict-scan findings were adjudicated by the operator: 18 Rule 1
# files became declared research participants in ACTIVE_SURFACE_MANIFEST.yaml
# and 3 Rule 2 files carry closure-layer-role headers. These tests pin the
# rule's own documented procedure so an allowlist entry can never outlive
# its manifest declaration or role header, and the allowlists can never
# silently widen into the broad ignores the WP-0C1R spec forbids.
#
# SCOPE LIMIT (2026-08-04): everything below reads YAML, greps class names, and
# searches source text. It proves the CONFIG's shape, never the SCANNER's
# behavior — which is how Rule 2's message promised JSONL detection it did not
# have from 2026-04-26 to 2026-08-04. Rule 2's behavior is proven by running
# semgrep in tests/test_semgrep_rule2_behavior.py against the fixture
# .semgrep/tests/test_no_new_substrate.py. These tests are the supplement.

_ANTI_SLOP = REPO_ROOT / ".semgrep" / "dharma-anti-slop.yml"
_SURFACE_MANIFEST = REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml"

# Rule 1 exclude entries that are NOT research participants: canonical owners
# (2026-04-26 audit), operational cron scripts, and the Memory Common door
# (PR #1132). Pinned here so a new exclude entry cannot ride into the
# allowlist without changing this contract in the same diff.
_RULE1_PERMITTED_NON_RESEARCH_EXCLUDES = {
    "dharma_swarm/runtime_state.py",
    "dharma_swarm/system_rv.py",
    "dharma_swarm/daemon_config.py",
    "dharma_swarm/experiment_log.py",
    "dharma_swarm/pulse.py",
    "dharma_swarm/custodians.py",
    "dharma_swarm/kaizen_ops_local.py",
    "dharma_swarm/scout_report.py",
    "dharma_swarm/review_cycle.py",
    "dharma_swarm/ginko_backtest.py",
    "dharma_swarm/ginko_evolution.py",
    "dharma_swarm/engine/store_sync.py",
    "scripts/consume_review_marks.py",
    "scripts/hermes_heartbeat_poll.py",
    "scripts/check_provider_credits.py",
    "dharma_swarm/memory_common.py",
    "scripts/memory_retrieval_broad_sweep.py",
    "scripts/memory_retrieval_live_gate.py",
    "scripts/memory_retrieval_system_gate.py",
}

# WP-0C1R decision B1: the ratified substrate classes and the one file each
# is allowed to live in. Class-scoped (not file-scoped) so a DIFFERENTLY NAMED
# new substrate class in the same file still triggers Rule 2 — proven
# behaviorally by
# test_semgrep_rule2_behavior.py::test_synthetic_new_substrate_is_caught_in_a_ratified_file.
# A SAME-NAMED one does not: semgrep's `class X: ...` pattern also matches
# `class X(Base): ...`, so the exemption is precisely NAME-scoped. That gap is
# named in Rule 2's message and caught by
# dharma.no-new-substrate-exempt-name-collision.
_RULE2_RATIFIED_ROLE_CLASSES = {
    "BridgeRegistry": "dharma_swarm/bridge_registry.py",
    "SQLiteGraphStore": "dharma_swarm/graph_store.py",
    "KnowledgeStore": "dharma_swarm/knowledge_units.py",
}

# Closed role vocabulary from docs/governance/ANTI_SLOP_RULES.md Rule 2.
_RULE2_ROLE_VOCABULARY = {
    "canonical-store",
    "derived-view",
    "plugin-sink",
    "cache",
    "legacy-mirror",
    "migration-mirror",
    "exempt",
}

# Structural header: a comment line `# closure-layer-role: <role>`, not a
# bare substring (an empty value or the token inside a string must fail).
_ROLE_HEADER_RE = re.compile(r"^#\s*closure-layer-role:\s*([a-z][a-z-]*)", re.MULTILINE)


def _anti_slop_rule(rule_id: str) -> dict:
    import yaml

    config = yaml.safe_load(_ANTI_SLOP.read_text(encoding="utf-8"))
    return next(r for r in config["rules"] if r["id"] == rule_id)


def _anti_slop_rule_excludes(rule_id: str) -> list[str]:
    return list(_anti_slop_rule(rule_id).get("paths", {}).get("exclude", []))


def test_rule1_lockstep_is_bidirectional():
    import yaml

    manifest = yaml.safe_load(_SURFACE_MANIFEST.read_text(encoding="utf-8"))
    participants = manifest.get("research_state_participants", {})
    declared: set[str] = set()
    for group_name, group in participants.items():
        files = group.get("files") or []
        slices = group.get("state_slices") or []
        assert files, f"{group_name}: participant group declares no files"
        assert slices, (
            f"{group_name}: research participants must declare the state_dir "
            "slices they read/write — file names alone are not a declaration"
        )
        for state_slice in slices:
            assert state_slice.startswith("~/.dharma"), (
                f"{group_name}: state slice outside the canonical state root: "
                f"{state_slice!r}"
            )
        declared.update(files)
    assert len(declared) == 18, (
        "the WP-0C1R ratification declared exactly 18 research participants; "
        f"manifest now declares {len(declared)} — update the adjudication "
        "record and this contract together, never one alone"
    )
    excludes = set(_anti_slop_rule_excludes("dharma.no-unauthorized-dharma-write"))
    missing = declared - excludes
    assert not missing, (
        f"declared research participants missing from Rule 1 allowlist: {sorted(missing)}"
    )
    undeclared = excludes - declared - _RULE1_PERMITTED_NON_RESEARCH_EXCLUDES
    assert not undeclared, (
        "Rule 1 exclude entries with neither a manifest declaration nor a "
        f"pinned canonical/operational justification: {sorted(undeclared)} — "
        "an allowlist entry may never precede its declaration (WP-0C1R)"
    )
    for path in sorted(declared):
        assert (REPO_ROOT / path).is_file(), f"declared participant vanished: {path}"


def test_rule2_exemptions_are_class_scoped_and_role_headed():
    rule = _anti_slop_rule("dharma.no-new-substrate")
    excludes = _anti_slop_rule_excludes("dharma.no-new-substrate")
    assert excludes == ["dharma_swarm/runtime_state.py"], (
        "Rule 2 must not exempt whole files beyond the canonical store — "
        "ratified WP-0C1R exemptions are class-scoped pattern-nots so a "
        "differently-named new substrate in the same file is still caught; "
        f"got {excludes}"
    )
    exempted_classes: set[str] = set()
    for clause in rule["patterns"]:
        if "pattern-not" not in clause:
            continue
        match = re.search(r"class\s+(\w+)\s*:", clause["pattern-not"])
        assert match, f"unparseable Rule 2 pattern-not clause: {clause['pattern-not']!r}"
        exempted_classes.add(match.group(1))
    assert exempted_classes == set(_RULE2_RATIFIED_ROLE_CLASSES), (
        "Rule 2 class exemptions diverged from the ratified WP-0C1R set: "
        f"{sorted(exempted_classes)} != {sorted(_RULE2_RATIFIED_ROLE_CLASSES)}"
    )
    for cls, path in sorted(_RULE2_RATIFIED_ROLE_CLASSES.items()):
        head = (REPO_ROOT / path).read_text(encoding="utf-8")[:2000]
        header = _ROLE_HEADER_RE.search(head)
        assert header, (
            f"{path} lost its structural '# closure-layer-role: <role>' header "
            "comment — the Rule 2 exemption is only valid while the header "
            "states the role"
        )
        assert header.group(1) in _RULE2_ROLE_VOCABULARY, (
            f"{path} declares role {header.group(1)!r} outside the Rule 2 "
            f"closed vocabulary {sorted(_RULE2_ROLE_VOCABULARY)}"
        )
        definitions = subprocess.run(
            ["git", "grep", "-lE", rf"^class {cls}[(:]"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        defined_in = definitions.stdout.split()
        assert path in defined_in, f"ratified class {cls} vanished from {path}"
        for other in defined_in:
            if other == path:
                continue
            if other.startswith(".semgrep/tests/"):
                # The behavioral fixture defines the ratified names ON PURPOSE
                # (it must, to prove the exemptions still hold) and defines a
                # deliberate collision beside them. Semgrep auto-ignores
                # `tests/` directories, so fixtures never enter a repo scan;
                # their semantics are asserted by
                # tests/test_semgrep_rule2_behavior.py instead.
                continue
            body = (REPO_ROOT / other).read_text(encoding="utf-8")
            assert "sqlite3.connect" not in body and "aiosqlite.connect" not in body, (
                f"{other} defines a class named {cls} AND opens SQLite — it "
                f"would silently inherit {path}'s class-scoped Rule 2 "
                "exemption; rename the class or adjudicate it explicitly"
            )


def test_rule2_collision_companion_pins_the_same_ratified_names():
    """Structural half of the 2026-08-04 correction: the companion rule that
    catches a same-named substrate must cover exactly the ratified class set.
    Its behavior is proven in tests/test_semgrep_rule2_behavior.py."""
    rule = _anti_slop_rule("dharma.no-new-substrate-exempt-name-collision")
    names = None
    for clause in rule["patterns"]:
        if clause.get("metavariable-regex", {}).get("metavariable") == "$NAME":
            names = set(
                clause["metavariable-regex"]["regex"].strip("^$()").split("|")
            )
    assert names == set(_RULE2_RATIFIED_ROLE_CLASSES), (
        "the collision companion must name exactly the WP-0C1R ratified "
        f"classes; got {sorted(names or [])}"
    )
    behavioral = REPO_ROOT / "tests/test_semgrep_rule2_behavior.py"
    assert behavioral.is_file(), (
        "Rule 2's behavioral proof vanished — config-shape tests alone are "
        "what let the JSONL gap survive fifteen weeks"
    )


def test_anti_slop_allowlists_contain_no_globs():
    for rule_id in (
        "dharma.no-unauthorized-dharma-write",
        "dharma.no-new-substrate",
        "dharma.no-new-substrate-exempt-name-collision",
    ):
        for entry in _anti_slop_rule_excludes(rule_id):
            assert "*" not in entry and not entry.endswith("/"), (
                f"{rule_id} exclude {entry!r} is a glob/directory — the "
                "WP-0C1R spec forbids broad ignores; allowlist exact files only"
            )
