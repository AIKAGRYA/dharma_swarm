"""WP-0C1 (TIT-004): the required Semgrep scan fails closed.

Contract under test: ``scripts/governance/run_semgrep_with_ca.sh`` plus the
Makefile scanner targets. A missing or version-mismatched scanner is a named
nonzero failure, never a green skip; the warn-only behavior lives in an
explicitly named advisory target that never enters ``governance-all``; the
scan carries a portable wall-clock bound converted into a named nonzero failure.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "scripts/governance/run_semgrep_with_ca.sh"
MAKEFILE = REPO_ROOT / "Makefile"
RATIFIED_PIN = "1.168.0"
SUBSTRATE_ROLE_CHECKER = (
    REPO_ROOT / "scripts/governance/check_registered_substrate_roles.py"
)
SEMGREP_RULE_CONFIG = REPO_ROOT / ".semgrep/dharma-anti-slop.yml"
SEMGREP_RULE_FIXTURE = REPO_ROOT / ".semgrep/tests/test_no_new_substrate.py"


def _load_substrate_checker():
    spec = importlib.util.spec_from_file_location(
        "registered_substrate_roles", SUBSTRATE_ROLE_CHECKER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registered_substrate_exemptions_are_exact_and_noncanonical():
    result = subprocess.run(
        [sys.executable, str(SUBSTRATE_ROLE_CHECKER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_registered_substrate_check_follows_connection_provenance():
    checker = _load_substrate_checker()
    source = textwrap.dedent(
        """\
        import sqlite3 as sql

        connection_factory = sql.connect

        def open_db(path):
            connection = connection_factory(path)
            return connection

        def open_cache(path):
            def unused_connector():
                return sql.connect(path)
            return object()

        lambda_db = lambda path: sql.connect(path)

        class WrappedProjectionStore:
            def __init__(self, path):
                connection = open_db(path)
                self.conn = connection

        class DirectProjectionStore:
            def __init__(self, path):
                self.conn = sql.connect(path)

        class ReturningProjectionStore:
            def open(self, path):
                return open_db(path)

        class LambdaProjectionStore:
            def __init__(self, path):
                self.conn = lambda_db(path)

        class HarmlessProjectionStore:
            def __init__(self, path):
                self.conn = open_cache(path)
        """
    )

    assert dict(checker._substrate_connector_sites(source, filename="rogue.py")) == {
        "DirectProjectionStore": 1,
        "LambdaProjectionStore": 1,
        "ReturningProjectionStore": 1,
        "WrappedProjectionStore": 1,
    }


def test_registered_substrate_constructor_count_is_not_blanket_suppressed(tmp_path):
    checker = _load_substrate_checker()
    sources = {
        "dharma_swarm/bridge_registry.py": "BridgeRegistry",
        "dharma_swarm/graph_store.py": "SQLiteGraphStore",
        "dharma_swarm/knowledge_units.py": "KnowledgeStore",
    }
    for relative, class_name in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "import sqlite3\n\n"
            f"class {class_name}:\n"
            "    def __init__(self, path):\n"
            "        self.conn = sqlite3.connect(path)\n"
        )
    assert checker._substrate_constructor_errors(tmp_path) == []

    bridge = tmp_path / "dharma_swarm/bridge_registry.py"
    bridge.write_text(
        bridge.read_text()
        + "\n    def audit(self, path):\n"
        + "        return sqlite3.connect(path)\n"
    )
    errors = checker._substrate_constructor_errors(tmp_path)
    assert len(errors) == 1
    assert "BridgeRegistry': 2" in errors[0]


def test_exact_exempt_declaration_multiplicity_is_not_collapsed(tmp_path):
    checker = _load_substrate_checker()
    source = tmp_path / "dharma_swarm/bridge_registry.py"
    source.parent.mkdir()
    source.write_text(
        "class BridgeRegistry:\n    pass\n\nclass BridgeRegistry:\n    pass\n"
    )

    declarations = checker._exempt_class_declarations(tmp_path)

    assert declarations["BridgeRegistry"] == [
        ("dharma_swarm/bridge_registry.py", ""),
        ("dharma_swarm/bridge_registry.py", ""),
    ]

    source.write_text("def build():\n    class BridgeRegistry:\n        pass\n")
    declarations = checker._exempt_class_declarations(tmp_path)
    assert declarations["BridgeRegistry"] == [
        ("dharma_swarm/bridge_registry.py", "    ")
    ]


def test_memory_kernel_authority_and_canon_risk_are_semantically_pinned():
    checker = _load_substrate_checker()
    writer_specs = (
        REPO_ROOT / "dharma_swarm/memory_kernel/writer_specs.py"
    ).read_text()
    surface_specs = (
        REPO_ROOT / "dharma_swarm/memory_kernel/surface_specs_core.py"
    ).read_text()
    assert checker._semantic_registration_errors(writer_specs, surface_specs) == []

    writer_mutant = re.sub(
        r'("bridge_registry\.store",.*?)(RiskLevel\.HIGH)',
        r"\1RiskLevel.MEDIUM",
        writer_specs,
        count=1,
        flags=re.DOTALL,
    )
    writer_errors = checker._semantic_registration_errors(writer_mutant, surface_specs)
    assert any(
        "bridge_registry.store semantic contract drifted" in error
        for error in writer_errors
    )

    duplicate_writer = writer_specs.replace(
        '        MemoryWriterSpec(\n            "ecosystem_index.store",',
        '        MemoryWriterSpec("bridge_registry.store", **{}),\n'
        '        MemoryWriterSpec(\n            "ecosystem_index.store",',
        1,
    )
    duplicate_errors = checker._semantic_registration_errors(
        duplicate_writer, surface_specs
    )
    assert any(
        "bridge_registry.store must have exactly one registration" in error
        for error in duplicate_errors
    )

    qualified_errors = checker._semantic_registration_errors(
        writer_specs
        + '\nqualified.MemoryWriterSpec(writer_id="bridge_registry.store")\n',
        surface_specs + '\nqualified.SurfaceSpec(surface_id="home.bridges")\n',
    )
    assert any(
        "bridge_registry.store must have exactly one registration" in error
        for error in qualified_errors
    )
    assert any(
        "home.bridges must have exactly one registration" in error
        for error in qualified_errors
    )

    starred_errors = checker._semantic_registration_errors(
        writer_specs + '\nMemoryWriterSpec(*("bridge_registry.store",))\n',
        surface_specs + '\nSurfaceSpec(*("home.bridges",))\n',
    )
    assert "MemoryKernel writers contain an unsupported constructor form" in (
        starred_errors
    )
    assert "MemoryKernel surfaces contain an unsupported constructor form" in (
        starred_errors
    )

    constant_identity_errors = checker._semantic_registration_errors(
        writer_specs
        + '\nTARGET = "bridge_registry.store"\n'
        + "MemoryWriterSpec(writer_id=TARGET)\n",
        surface_specs
        + '\nTARGET = "home.bridges"\n'
        + "SurfaceSpec(surface_id=TARGET)\n",
    )
    assert "MemoryKernel writers contain an unsupported constructor form" in (
        constant_identity_errors
    )
    assert "MemoryKernel surfaces contain an unsupported constructor form" in (
        constant_identity_errors
    )

    surface_mutant = re.sub(
        r'("home\.bridges",.*?)(AuthorityLevel\.LOW)',
        r"\1AuthorityLevel.MEDIUM",
        surface_specs,
        count=1,
        flags=re.DOTALL,
    )
    surface_errors = checker._semantic_registration_errors(writer_specs, surface_mutant)
    assert any(
        "home.bridges semantic contract drifted" in error for error in surface_errors
    )

    authority_mutant = re.sub(
        r'("home\.bridges",.*?)(projection_of=)',
        r'\1source_of_truth_for=("bridges",),\n            \2',
        surface_specs,
        count=1,
        flags=re.DOTALL,
    )
    authority_errors = checker._semantic_registration_errors(
        writer_specs, authority_mutant
    )
    assert any(
        "home.bridges semantic contract drifted" in error for error in authority_errors
    )


@pytest.mark.skipif(
    shutil.which(os.environ.get("DHARMA_SEMGREP_BIN", "semgrep")) is None,
    reason="the dedicated scanner CI lane runs this wrapper fixture non-skippably",
)
def test_no_new_substrate_semgrep_rule_fixture():
    semgrep = os.environ.get("DHARMA_SEMGREP_BIN") or shutil.which("semgrep")
    assert semgrep is not None
    result = subprocess.run(
        [
            str(WRAPPER),
            "--test",
            "--config",
            str(SEMGREP_RULE_CONFIG),
            str(SEMGREP_RULE_FIXTURE),
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DHARMA_SEMGREP_ALLOW_MISSING": "",
            "DHARMA_SEMGREP_BIN": semgrep,
            "DHARMA_SEMGREP_EXPECTED_VERSION": RATIFIED_PIN,
            "DHARMA_SEMGREP_WALLCLOCK": "90",
            "SEMGREP_ENABLE_VERSION_CHECK": "0",
            "SEMGREP_SEND_METRICS": "off",
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _run_wrapper(
    args: list[str], env_overrides: dict[str, str]
) -> subprocess.CompletedProcess:
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
                if (
                    not line.strip()
                    and body
                    and not any(later.startswith("\t") for later in body[-1:])
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
