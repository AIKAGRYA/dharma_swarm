from __future__ import annotations

import importlib.util
import io
import sys
import textwrap
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "governance"
    / "capsule_coherence_report.py"
)


def load_report_module():
    spec = importlib.util.spec_from_file_location("capsule_coherence_report", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_module(path: Path, text: str) -> Path:
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")
    return path


def test_parses_small_temp_module(tmp_path: Path) -> None:
    report_mod = load_report_module()
    module_path = write_module(
        tmp_path / "sample_capsule.py",
        """
        import os
        from pathlib import Path

        class PublicThing:
            def method(self, flag: bool) -> None:
                if flag:
                    Path.home()

        def public_api(value: int) -> int:
            if value > 0:
                return value
            return 0
        """,
    )

    report = report_mod.analyze_file(module_path, tests_dir=tmp_path / "tests")

    assert report.error is None
    assert report.path == str(module_path)
    assert report.public_api == ["PublicThing", "public_api"]


def test_reports_line_function_and_class_counts(tmp_path: Path) -> None:
    report_mod = load_report_module()
    module_path = write_module(
        tmp_path / "counts.py",
        """
        import json

        class One:
            pass

        def first() -> None:
            pass

        async def second() -> None:
            pass
        """,
    )

    report = report_mod.analyze_file(module_path, tests_dir=tmp_path / "tests")

    assert report.line_count == 10
    assert report.import_count == 1
    assert report.class_count == 1
    assert report.function_count == 2
    assert report.branch_count_by_function == {"first": 0, "second": 0}


def test_detects_side_effect_keywords(tmp_path: Path) -> None:
    report_mod = load_report_module()
    module_path = write_module(
        tmp_path / "effects.py",
        """
        import os
        import sqlite3
        import subprocess
        from pathlib import Path

        def touch(path: Path) -> None:
            open(path)
            path.write_text("ok")
            Path.home()
            subprocess.run(["true"])
            os.environ["X"] = "1"
            emit("event")
            create_task(work())
            requests.get("https://example.invalid")
            path.with_suffix(".jsonl")
        """,
    )

    report = report_mod.analyze_file(module_path, tests_dir=tmp_path / "tests")

    assert report.side_effect_hits["open"] == 1
    assert report.side_effect_hits["write_text"] == 1
    assert report.side_effect_hits["sqlite"] == 1
    assert report.side_effect_hits["subprocess"] == 2
    assert report.side_effect_hits["Path.home"] == 1
    assert report.side_effect_hits["jsonl"] == 1
    assert report.side_effect_hits["emit"] == 1
    assert report.side_effect_hits["create_task"] == 1
    assert report.side_effect_hits["requests/http"] == 2
    assert report.side_effect_hits["os.environ"] == 1


def test_cli_does_not_fail_on_syntax_valid_file(tmp_path: Path) -> None:
    report_mod = load_report_module()
    module_path = write_module(
        tmp_path / "valid.py",
        """
        def ok() -> bool:
            return True
        """,
    )
    stdout = io.StringIO()

    exit_code = report_mod.main([str(module_path), "--json"], stdout=stdout)

    assert exit_code == 0
    assert '"function_count": 1' in stdout.getvalue()


def test_high_split_pressure_is_not_a_hard_gate(tmp_path: Path) -> None:
    report_mod = load_report_module()
    functions = "\n\n".join(
        f"def public_{index}(value):\n"
        f"    if value:\n"
        f"        return open(__file__).read()\n"
        f"    return None\n"
        for index in range(55)
    )
    module_path = tmp_path / "large_capsule.py"
    module_path.write_text(
        "import subprocess\nimport sqlite3\n\n" + functions + "\n",
        encoding="utf-8",
    )
    stdout = io.StringIO()

    exit_code = report_mod.main([str(module_path)], stdout=stdout)

    assert report_mod.analyze_file(module_path, tests_dir=tmp_path / "tests").suggested_split_pressure == "high"
    assert exit_code == 0
    assert "suggested split pressure: high" in stdout.getvalue()
