from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.world_radar.go_invoke import (
    go_module_directive,
    go_toolchain_capable,
    installed_go_version,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
GO_SDK = REPO_ROOT / "tools" / "go_sdk"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "go_adapters"


def _go_toolchain_available() -> bool:
    """True only when an installed Go toolchain satisfies go_sdk/go.mod.

    The dedicated `go-adapter-contracts` CI job provisions the pinned Go
    version (setup-go) and runs this file there. The general pytest matrix
    does not provision Go, so the compile-and-run contract is skipped there
    rather than failing on a missing toolchain (GOPROXY=off blocks the
    automatic toolchain download).

    WP-0C2 (TIT-003): the version comparison that used to live here is now
    the production helper `go_toolchain_capable` in
    dharma_swarm/world_radar/go_invoke.py — one oracle for tests and runtime.
    """
    return go_toolchain_capable(GO_SDK)


@pytest.mark.skipif(
    not _go_toolchain_available(),
    reason="Go toolchain matching go_sdk/go.mod unavailable; covered by the go-adapter-contracts CI job",
)
def test_go_adapter_contracts_pass_without_network() -> None:
    env = os.environ.copy()
    env.update(
        {
            "GOCACHE": "/tmp/dharma-swarm-go-build",
            "GOMODCACHE": "/tmp/dharma-swarm-go-mod",
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


# ── WP-0C2 (TIT-003): version-aware capability contract ─────────────


def _fake_go(tmp_path: Path, stdout: str, *, exit_code: int = 0) -> str:
    fake = tmp_path / "go"
    fake.write_text(f"#!/bin/sh\nprintf '%s\\n' \"{stdout}\"\nexit {exit_code}\n")
    fake.chmod(0o755)
    return str(fake)


def _module_with_directive(tmp_path: Path, directive: str) -> Path:
    module = tmp_path / "module"
    module.mkdir()
    (module / "go.mod").write_text(f"module fixture\n\n{directive}\n")
    return module


class TestGoToolchainCapability:
    def test_older_toolchain_is_incapable(self, tmp_path: Path) -> None:
        module = _module_with_directive(tmp_path, "go 1.26")
        fake = _fake_go(tmp_path, "go version go1.22.5 linux/amd64")
        assert go_toolchain_capable(module, go_bin=fake) is False

    def test_matching_toolchain_is_capable(self, tmp_path: Path) -> None:
        module = _module_with_directive(tmp_path, "go 1.26")
        fake = _fake_go(tmp_path, "go version go1.26.3 linux/amd64")
        assert go_toolchain_capable(module, go_bin=fake) is True

    def test_newer_toolchain_is_capable(self, tmp_path: Path) -> None:
        module = _module_with_directive(tmp_path, "go 1.26")
        fake = _fake_go(tmp_path, "go version go1.27.0 linux/amd64")
        assert go_toolchain_capable(module, go_bin=fake) is True

    def test_malformed_go_version_output_fails_closed(self, tmp_path: Path) -> None:
        module = _module_with_directive(tmp_path, "go 1.26")
        fake = _fake_go(tmp_path, "not a version banner")
        assert installed_go_version(fake) is None
        assert go_toolchain_capable(module, go_bin=fake) is False

    def test_patch_directive_requires_matching_patch(self, tmp_path: Path) -> None:
        # `go 1.26.1` is a minimum; a go1.26.0 host must NOT be considered
        # capable (Go itself would reject `go run .`).
        module = _module_with_directive(tmp_path, "go 1.26.1")
        assert go_module_directive(module) == (1, 26, 1)
        older_patch = _fake_go(tmp_path, "go version go1.26.0 linux/amd64")
        assert go_toolchain_capable(module, go_bin=older_patch) is False
        exact_patch = _fake_go(tmp_path, "go version go1.26.1 linux/amd64")
        assert go_toolchain_capable(module, go_bin=exact_patch) is True

    def test_minor_directive_satisfied_by_any_patch(self, tmp_path: Path) -> None:
        # `go 1.26` means 1.26.0; any 1.26.x host satisfies it.
        module = _module_with_directive(tmp_path, "go 1.26")
        assert go_module_directive(module) == (1, 26, 0)
        fake = _fake_go(tmp_path, "go version go1.26.5 linux/amd64")
        assert go_toolchain_capable(module, go_bin=fake) is True

    def test_nonzero_go_version_exit_fails_closed(self, tmp_path: Path) -> None:
        # A broken shim that prints a parseable banner but exits non-zero must
        # not be trusted (it would let `go run .` be chosen and quarantine
        # queued envelopes on a host the gate should reject).
        module = _module_with_directive(tmp_path, "go 1.26")
        broken = _fake_go(tmp_path, "go version go1.26.3 linux/amd64", exit_code=1)
        assert installed_go_version(broken) is None
        assert go_toolchain_capable(module, go_bin=broken) is False

    def test_unreadable_go_mod_fails_closed(self, tmp_path: Path) -> None:
        module = tmp_path / "no-mod"
        module.mkdir()
        fake = _fake_go(tmp_path, "go version go1.26.3 linux/amd64")
        assert go_module_directive(module) is None
        assert go_toolchain_capable(module, go_bin=fake) is False

    def test_go_mod_without_directive_fails_closed(self, tmp_path: Path) -> None:
        module = tmp_path / "bad-mod"
        module.mkdir()
        (module / "go.mod").write_text("module fixture\n")
        assert go_module_directive(module) is None

    def test_prebuilt_binary_works_without_any_toolchain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dharma_swarm.world_radar import go_invoke

        module = tmp_path / "world_scout_go"
        module.mkdir()
        binary = module / module.name
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o755)
        monkeypatch.setattr(go_invoke.shutil, "which", lambda _name: None)
        argv, mode = go_invoke._go_invocation(module)
        assert mode == "binary"
        assert argv == [str(binary)]

    def test_incompatible_toolchain_yields_needs_host(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dharma_swarm.world_radar import go_invoke

        module = _module_with_directive(tmp_path, "go 1.26")
        fake = _fake_go(tmp_path, "go version go1.22.5 linux/amd64")
        monkeypatch.setattr(go_invoke.shutil, "which", lambda _name: fake)
        argv, mode = go_invoke._go_invocation(module)
        assert mode == "needs_host"
        assert argv == []


def test_no_direct_which_go_capability_gates_remain() -> None:
    """Every affected Go bridge surface uses the shared version-aware helper.

    Spec § WP-0C2: direct which-based Go presence gates must be absent from
    the routed files; `go_invoke.py` itself holds the single sanctioned
    lookup inside `installed_go_version`.
    """
    routed = [
        REPO_ROOT / "scripts" / "runtime" / "github_ingestor_runner.py",
        REPO_ROOT / "tests" / "test_github_ingestor_runner.py",
        REPO_ROOT / "tests" / "test_go_evidence_ingestor_bridge.py",
        REPO_ROOT / "tests" / "test_go_github_ingestor_bridge.py",
        REPO_ROOT / "tests" / "test_go_world_signal_bridge.py",
        REPO_ROOT / "tests" / "test_go_receipt_identity_verify.py",
        REPO_ROOT / "tests" / "test_go_adapter_contracts.py",
    ]
    needles = ['shutil.which(' + '"go")', "shutil.which(" + "'go')"]
    for path in routed:
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            assert needle not in text, f"{path} still gates on Go presence"
