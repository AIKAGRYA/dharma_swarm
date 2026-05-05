from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "governance" / "module_metabolism_report.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("module_metabolism_report", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_mini_repo(tmp_path: Path) -> None:
    package = tmp_path / "dharma_swarm"
    tests = tmp_path / "tests"
    package.mkdir()
    tests.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "sample.py").write_text(
        "\n".join(
            [
                "import os",
                "import sqlite3",
                "from pathlib import Path",
                "",
                "class PublicThing:",
                "    pass",
                "",
                "def public_func(flag: bool) -> str:",
                "    if flag:",
                "        Path.home().joinpath('x.jsonl').write_text('x')",
                "    os.environ.get('HOME')",
                "    return 'ok'",
                "",
                "def _private_func() -> None:",
                "    return None",
            ]
        ),
        encoding="utf-8",
    )
    (tests / "test_sample.py").write_text(
        "from dharma_swarm.sample import PublicThing, public_func\n",
        encoding="utf-8",
    )


def test_build_report_counts_small_temp_module(tmp_path: Path) -> None:
    _write_mini_repo(tmp_path)
    module = _load_module()

    report = module.build_report(tmp_path, targets=["dharma_swarm"])
    sample = next(item for item in report.modules if item.path == "dharma_swarm/sample.py")

    assert sample.line_count == 15
    assert sample.import_count == 3
    assert sample.class_count == 1
    assert sample.function_count == 2
    assert sample.public_api_names == ["PublicThing", "public_func"]
    assert sample.test_reference_count > 0


def test_detects_side_effect_keywords(tmp_path: Path) -> None:
    _write_mini_repo(tmp_path)
    module = _load_module()

    report = module.build_report(tmp_path, targets=["dharma_swarm"])
    sample = next(item for item in report.modules if item.path == "dharma_swarm/sample.py")

    assert sample.side_effect_hits["sqlite"] >= 1
    assert sample.side_effect_hits["Path.home"] == 1
    assert sample.side_effect_hits["write_text"] == 1
    assert sample.side_effect_hits["jsonl"] >= 1
    assert sample.side_effect_hits["os.environ"] == 1
    assert "write_surface" in sample.flags


def test_cli_outputs_json_for_syntax_valid_files(tmp_path: Path) -> None:
    _write_mini_repo(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--json",
            "dharma_swarm",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["summary"]["module_count"] == 2
    assert any(item["path"] == "dharma_swarm/sample.py" for item in data["modules"])


def test_high_split_pressure_is_not_a_hard_gate(tmp_path: Path) -> None:
    package = tmp_path / "dharma_swarm"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "large.py").write_text(
        "def public_func():\n"
        + "\n".join(f"    value_{index} = {index}" for index in range(1100))
        + "\n    return value_1099\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--json",
            "dharma_swarm",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    data = json.loads(result.stdout)
    large = next(item for item in data["modules"] if item["path"] == "dharma_swarm/large.py")

    assert result.returncode == 0
    assert data["summary"]["over_1000_lines"] == 1
    assert large["suggested_action"] == "split-review"
    assert "large_module" in large["flags"]
