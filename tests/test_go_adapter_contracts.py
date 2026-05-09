from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GO_SDK = REPO_ROOT / "tools" / "go_sdk"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "go_adapters"


def test_go_adapter_contracts_pass_without_network() -> None:
    env = os.environ.copy()
    env.update(
        {
            "GOPROXY": "off",
            "GOSUMDB": "off",
            "GOFLAGS": "-mod=readonly",
        }
    )
    result = subprocess.run(
        ["go", "test", "./..."],
        cwd=GO_SDK,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout


def test_golden_receipt_has_stable_contract_fields() -> None:
    receipt = json.loads((FIXTURE_DIR / "expected_receipt.json").read_text())
    assert receipt["correlation_id"] == "corr_g03_fixture_001"
    assert receipt["status"] == "accepted"
    assert receipt["schema_version"] == "go_evidence_receipt.v0"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", receipt["content_hash"])
    assert re.fullmatch(r"evt_[0-9a-f]{24}", receipt["event_uid"])
    assert re.fullmatch(r"goev_[0-9a-f]{24}", receipt["receipt_id"])


def test_contract_harness_uses_receipt_sdk_without_parallel_primitives() -> None:
    contract = GO_SDK / "adaptercontract" / "contract.go"
    text = contract.read_text()
    assert '"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"' in text
    forbidden = [
        '"crypto/sha256"',
        '"encoding/hex"',
        "type Receipt struct",
        "func NormalizeJSON",
        "func ContentHash",
        "func EventUID",
        "func ReceiptID",
        "func Write(",
        "os.CreateTemp",
        "os.Rename",
    ]
    for needle in forbidden:
        assert needle not in text


def test_fixtures_are_file_native_and_non_networked() -> None:
    for path in FIXTURE_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        source_url = data.get("source_url", "")
        if source_url:
            assert source_url.startswith("fixture://"), path


def test_contract_harness_does_not_import_network_packages() -> None:
    forbidden = {'"net"', '"net/http"'}
    for path in GO_SDK.rglob("*.go"):
        text = path.read_text()
        for package in forbidden:
            assert package not in text, f"{path} imports {package}"
