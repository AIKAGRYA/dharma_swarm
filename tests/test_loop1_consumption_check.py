from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.models import ProviderType
from scripts.governance.loop1_consumption_check import (
    _default_chain,
    _digest,
    _read_receipt,
    _receipt_row,
    _run_p1_p4,
    _stable_json,
    _write_receipt,
    _write_test_db,
    main,
    p1_failing_receipt_reorders,
    p2_no_failures_keep_default,
    p3_cross_boot_consumes_prior,
    p4_poisoning_bound,
)


@pytest.fixture
def tmp_db() -> Any:
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp) / "runtime.db"


class TestDefaultChain:
    def test_chain_has_four_providers(self) -> None:
        chain = _default_chain()
        assert len(chain) == 4
        assert len(set(chain)) == 4


class TestWriteTestDb:
    def test_rows_persisted(self, tmp_db: Path) -> None:
        rows = [_receipt_row("t1", ProviderType.ANTHROPIC)]
        _write_test_db(tmp_db, rows)
        conn = sqlite3.connect(tmp_db)
        cur = conn.execute("SELECT count(*) FROM delegation_runs")
        assert cur.fetchone()[0] == 1
        cur = conn.execute("SELECT receipt_json FROM delegation_runs LIMIT 1")
        stored = json.loads(cur.fetchone()[0])
        assert stored["trace_id"] == "t1"
        conn.close()


class TestP1P4:
    def test_p1_demotes_failing_provider(self, tmp_db: Path) -> None:
        result = p1_failing_receipt_reorders(tmp_db, _default_chain())
        assert result["ok"]
        assert result["reordered_order"][-1] == ProviderType.ANTHROPIC.value

    def test_p2_keeps_default_order(self, tmp_db: Path) -> None:
        result = p2_no_failures_keep_default(tmp_db, _default_chain())
        assert result["ok"]
        assert result["reordered_order"] == [p.value for p in _default_chain()]

    def test_p3_consumes_cross_boot_trace(self, tmp_db: Path) -> None:
        result = p3_cross_boot_consumes_prior(tmp_db, _default_chain())
        assert result["ok"]
        assert result["consumer_boot_id"] == "boot-b"

    def test_p4_respects_max_demotions(self, tmp_db: Path) -> None:
        result = p4_poisoning_bound(tmp_db, _default_chain())
        assert result["ok"]
        assert result["demoted_count"] <= 2
        assert len(result["reordered_order"]) == 4


class TestRunP1P4:
    def test_all_properties_pass(self, tmp_db: Path) -> None:
        receipt = _run_p1_p4(tmp_db)
        assert receipt["outcome"] == "ok"
        assert receipt["schema"] == "dharma.loop1_consumption_check.v1"
        assert len(receipt["properties"]) == 4
        for prop in receipt["properties"]:
            assert prop["ok"]

    def test_default_db_is_optional(self) -> None:
        receipt = _run_p1_p4()
        assert receipt["outcome"] == "ok"


class TestReceiptIO:
    def test_write_and_read_round_trip(self, tmp_db: Path) -> None:
        receipt = _run_p1_p4(tmp_db)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            _write_receipt(receipt, path)
            restored = _read_receipt(path)
            assert restored is not None
            assert restored["outcome"] == receipt["outcome"]
            assert restored["properties"] == receipt["properties"]

    def test_digest_stable(self, tmp_db: Path) -> None:
        receipt = _run_p1_p4(tmp_db)
        d1 = _digest(receipt)
        d2 = _digest(receipt)
        assert d1 == d2
        assert isinstance(d1, str) and len(d1) == 64

    def test_stable_json_deterministic(self, tmp_db: Path) -> None:
        receipt = _run_p1_p4(tmp_db)
        s1 = _stable_json(receipt)
        s2 = _stable_json(receipt)
        assert s1 == s2


class TestMain:
    def test_main_generates_receipt(self, tmp_db: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            rc = main(["--receipt", str(receipt_path), "--db", str(tmp_db)])
            assert rc == 0
            receipt = _read_receipt(receipt_path)
            assert receipt is not None
            assert receipt["outcome"] == "ok"

    def test_check_mode_without_receipt_is_needs_host(self, tmp_db: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "missing.json"
            rc = main(["--check", "--receipt", str(receipt_path), "--db", str(tmp_db)])
            assert rc == 0

    def test_check_mode_with_matching_receipt_passes(self, tmp_db: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            rc = main(["--receipt", str(receipt_path), "--stdout", "--db", str(tmp_db)])
            assert rc == 0
            rc = main(["--check", "--receipt", str(receipt_path), "--db", str(tmp_db)])
            assert rc == 0

    def test_check_mode_with_divergent_receipt_fails(self, tmp_db: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            receipt = _run_p1_p4(tmp_db)
            # Mutate outcome to simulate drift
            receipt["outcome"] = "fail"
            _write_receipt(receipt, receipt_path)
            rc = main(["--check", "--receipt", str(receipt_path), "--db", str(tmp_db)])
            assert rc == 1


class TestEndToEndInvocation:
    def test_script_invocation_default(self, tmp_db: Path) -> None:
        env = os.environ.copy()
        env["DGC_ROUTER_RECEIPT_DB"] = str(tmp_db)
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        result = subprocess.run(
            [sys.executable, "-m", "scripts.governance.loop1_consumption_check", "--stdout"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        parsed = json.loads(result.stdout)
        assert parsed["outcome"] == "ok"

    def test_script_invocation_check(self, tmp_db: Path) -> None:
        env = os.environ.copy()
        env["DGC_ROUTER_RECEIPT_DB"] = str(tmp_db)
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.governance.loop1_consumption_check",
                "--stdout",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            env=env,
        )
        assert result.returncode == 0
        receipt = json.loads(result.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            receipt_path.write_text(json.dumps(receipt))
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.governance.loop1_consumption_check",
                    "--check",
                    "--receipt",
                    str(receipt_path),
                    "--stdout",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
                env=env,
            )
            assert result.returncode == 0, result.stderr
