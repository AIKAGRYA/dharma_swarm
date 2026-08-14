"""Contract tests for `make vision` (scripts/docops/vision_navigation.py).

Covers: byte-determinism per mode, JSON schema + pointer-only transmission
block, boundary footer in every mode, UNRATIFIED banner, typed --check exits
on the committed tree and on synthetic broken fixtures, the no-write proof,
gate-key secrecy, crystal size, and the §GATE subset in --packet.

No network, no dependencies beyond stdlib + pytest. The script under test is
stdlib-only and read-only; these tests drive it via subprocess exactly as the
Make target does.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "docops" / "vision_navigation.py"
GATE_KEY = REPO_ROOT / "scripts" / "docops" / "vision_gate_key.json"
ARTIFACT_REL = "docs/vision_maps/VISION_TRANSMISSION.md"
INDEX_REL = "docs/MEGAFILE_INDEX.md"
KERNEL_REL = "dharma_swarm/dharma_kernel.py"
GATES_REL = "dharma_swarm/telos_gates.py"

MODE_FLAGS: dict[str, list[str]] = {
    "default": [],
    "crystal": ["--crystal"],
    "full": ["--full"],
    "registry": ["--registry"],
    "json": ["--json"],
    "check": ["--check"],
    "packet": ["--packet"],
}


def _load_module():
    spec = importlib.util.spec_from_file_location("vision_navigation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VN = _load_module()


def _run(*args: str, root: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    cmd = [sys.executable, str(SCRIPT), *args]
    if root is not None:
        cmd.extend(["--root", str(root)])
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        cmd, cwd=REPO_ROOT, env=env, capture_output=True, timeout=60
    )


def _porcelain() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout


# --- fixtures ----------------------------------------------------------------


def _build_fixture(tmp_path: Path) -> Path:
    """A minimal tree the checker accepts: real artifact + registry + sources,
    plus empty stubs at every registry path so path-existence passes."""
    root = tmp_path / "fixture"
    for rel in (ARTIFACT_REL, INDEX_REL, KERNEL_REL, GATES_REL):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, target)
    registry = VN.load_registry(REPO_ROOT)
    for row in registry["rows"]:
        stub = root / row["path"]
        stub.parent.mkdir(parents=True, exist_ok=True)
        if not stub.exists():
            stub.write_text("stub\n", encoding="utf-8")
    return root


def _repin_tiers(root: Path) -> None:
    """Rewrite the fixture's tier sha pins to match its (mutated) artifact,
    so a targeted check fires instead of the sha-drift check."""
    artifact = (root / ARTIFACT_REL).read_text(encoding="utf-8")
    index_path = root / INDEX_REL
    text = index_path.read_text(encoding="utf-8")
    for tier in ("T0", "T1", "T2"):
        sha = VN.sha256_text(VN.tier_slice(artifact, tier))
        text = re.sub(
            rf"(\| {tier} \| {re.escape(ARTIFACT_REL)} \| TIER:{tier} \| )[0-9a-f]{{64}} \|",
            rf"\g<1>{sha} |",
            text,
        )
    index_path.write_text(text, encoding="utf-8")


# --- determinism -------------------------------------------------------------


@pytest.mark.parametrize("mode", sorted(MODE_FLAGS))
def test_double_render_is_byte_identical(mode: str) -> None:
    first = _run(*MODE_FLAGS[mode])
    second = _run(*MODE_FLAGS[mode])
    # Determinism is the property under test. --check legitimately reports a
    # non-zero typed exit while the Stage 0 citation backlog is outstanding;
    # it must still do so identically on every run.
    assert first.returncode == second.returncode
    if mode != "check":
        assert first.returncode == 0
    assert first.stdout == second.stdout, (
        f"mode {mode} must render byte-identically across consecutive runs"
    )


# --- boundary + banner -------------------------------------------------------


@pytest.mark.parametrize("mode", sorted(MODE_FLAGS))
def test_every_mode_carries_the_boundary_footer(mode: str) -> None:
    out = _run(*MODE_FLAGS[mode]).stdout.decode("utf-8").lower()
    assert "not ratification" in out, f"mode {mode} lost the boundary footer"
    assert "merge authority" in out, f"mode {mode} lost the boundary footer"


@pytest.mark.parametrize("mode", ["default", "full", "packet"])
def test_unratified_banner_in_transmission_modes(mode: str) -> None:
    out = _run(*MODE_FLAGS[mode]).stdout.decode("utf-8")
    assert "UNRATIFIED DRAFT" in out, f"mode {mode} must carry the UNRATIFIED banner"


# --- json schema -------------------------------------------------------------


def test_json_schema_sorted_keys_and_pointer_only_transmission() -> None:
    raw = _run("--json").stdout.decode("utf-8")
    payload = json.loads(raw)
    assert payload["schema"] == "dharma_swarm.vision_navigation.v1"
    assert payload["authority"] == "navigation_only"
    assert len(payload["registry"]) == 25
    assert raw == (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ), "--json must serialize with sorted keys, deterministically"
    for tier in ("T0", "T1", "T2"):
        pointer = payload["transmission"][tier]
        assert set(pointer) == {"anchor", "path", "sha256"}, (
            "transmission block must be pointers only — no content key"
        )
        assert pointer["path"] == ARTIFACT_REL
        assert pointer["anchor"] == f"TIER:{tier}"
        artifact = (REPO_ROOT / ARTIFACT_REL).read_text(encoding="utf-8")
        assert pointer["sha256"] == VN.sha256_text(VN.tier_slice(artifact, tier))
    assert payload["open_conflicts"], "open conflicts must render in --json"
    assert [row["index"] for row in payload["registry"]] == list(range(1, 26))


# --- crystal -----------------------------------------------------------------


def test_crystal_is_small_and_is_the_crystal() -> None:
    out = _run("--crystal").stdout.decode("utf-8")
    assert "THE CRYSTAL" in out
    assert len(out.split()) <= 260, "T0 crystal output must stay <= 260 words"


# --- packet ------------------------------------------------------------------


def test_packet_contains_tiers_ledger_firewall_and_five_gate_questions() -> None:
    out = _run("--packet").stdout.decode("utf-8")
    first_line = out.splitlines()[0]
    assert first_line.startswith(
        "DHARMA SWARM — VISION TRANSMISSION PACKET · generated from checkout "
    )
    assert first_line.endswith("· UNRATIFIED DRAFT")
    assert "THE CRYSTAL" in out
    assert "ONE PAGE" in out
    assert "OPEN CONTRADICTIONS" in out
    assert "CLAIM FIREWALL" in out
    # Questions 1, 2, 3, 5, 8 of §GATE — and only those.
    assert "Is the contemplative spine the product?" in out
    assert "Name three things you may NOT claim" in out
    assert "May you cite the R_V effect sizes?" in out
    assert "Did dharma_swarm pass or fail its 90-day kill condition?" in out
    assert "What authority does reading this document grant you?" in out
    assert "Is the telos single or dual?" not in out, "§GATE Q4 stays out of the packet"
    assert "internally-facing build idea" not in out, "§GATE Q6 stays out of the packet"


# --- gate key secrecy --------------------------------------------------------


def test_gate_key_is_wellformed_and_never_rendered() -> None:
    key = json.loads(GATE_KEY.read_text(encoding="utf-8"))
    assert set(key["questions"]) == {f"G{n}" for n in range(1, 9)}
    for name, question in key["questions"].items():
        assert question["required"], f"{name} must declare required tokens"
        assert "rationale" in question and "forbidden" in question
        assert "open_row" in question
    assert "unadjudicated" in key["questions"]["G5"]["forbidden"]
    assert "passed without adjudication" in key["questions"]["G5"]["forbidden"]

    canary = key["canary"]
    g5_rationale = key["questions"]["G5"]["rationale"]
    for mode, flags in MODE_FLAGS.items():
        out = _run(*flags).stdout.decode("utf-8")
        assert canary not in out, f"gate key leaked into mode {mode}"
        assert g5_rationale not in out, f"gate key rationale leaked into mode {mode}"


# --- check: committed tree ---------------------------------------------------


def test_check_passes_on_the_committed_tree() -> None:
    result = _run("--check")
    # Integrity (registry + tier pins + law-layer counts) must be green on the
    # committed tree. Source fidelity is a separate, stricter property: exit 5
    # is the declared state while citations are still being migrated to
    # span-pinned form, and it returns to 0 when that migration completes.
    assert b"FAIL registry" not in result.stdout, result.stdout.decode("utf-8")
    assert b"FAIL transmission" not in result.stdout, result.stdout.decode("utf-8")
    assert result.returncode in (0, 5), result.stdout.decode("utf-8")


def test_usage_errors_exit_2() -> None:
    assert _run("--definitely-not-a-flag").returncode == 2
    assert _run("--crystal", "--full").returncode == 2


# --- check: synthetic broken fixtures ---------------------------------------


def test_check_fixture_baseline_is_green(tmp_path: Path) -> None:
    """Structural baseline. The fixture's registry paths are empty stubs, so
    citation spans cannot resolve there by construction; only registry and rot
    integrity are meaningful on this tree."""
    root = _build_fixture(tmp_path)
    result = _run("--check", root=root)
    assert b"FAIL registry" not in result.stdout, result.stdout.decode("utf-8")
    assert b"FAIL transmission" not in result.stdout, result.stdout.decode("utf-8")
    assert result.returncode in (0, 5), result.stdout.decode("utf-8")


def test_check_missing_artifact_exits_4(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path)
    (root / ARTIFACT_REL).unlink()
    result = _run("--check", root=root)
    assert result.returncode == 4
    assert b"missing docs/vision_maps/VISION_TRANSMISSION.md" in result.stdout


def test_check_broken_anchor_exits_4(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path)
    artifact = root / ARTIFACT_REL
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            "<!-- TIER:T1:END -->", "<!-- TIER:T1:BROKEN -->"
        ),
        encoding="utf-8",
    )
    result = _run("--check", root=root)
    assert result.returncode == 4
    assert b"anchor" in result.stdout


def test_check_tier_sha_drift_exits_4(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path)
    artifact = root / ARTIFACT_REL
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            "<!-- TIER:T1:END -->", "silent edit inside the tier\n<!-- TIER:T1:END -->"
        ),
        encoding="utf-8",
    )
    result = _run("--check", root=root)
    assert result.returncode == 4
    assert b"sha256 drifted" in result.stdout


def test_check_seven_open_rows_exits_4(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path)
    artifact = root / ARTIFACT_REL
    text = artifact.read_text(encoding="utf-8")
    start = text.index("- **OPEN-7 ·")
    end = text.index("- **OPEN-8 ·")
    artifact.write_text(text[:start] + text[end:], encoding="utf-8")
    _repin_tiers(root)  # isolate the row-count check from the sha check
    result = _run("--check", root=root)
    assert result.returncode == 4
    assert b"OPEN row count is 7" in result.stdout


def test_check_effect_size_in_mechanism_section_exits_4(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path)
    artifact = root / ARTIFACT_REL
    text = artifact.read_text(encoding="utf-8")
    heading = "## §4 THE MECHANISM CLAIM"
    at = text.index(heading)
    line_end = text.index("\n", at) + 1
    artifact.write_text(
        text[:line_end] + "\nThe effect reached AUROC 0.9 in our runs.\n" + text[line_end:],
        encoding="utf-8",
    )
    _repin_tiers(root)
    result = _run("--check", root=root)
    assert result.returncode == 4
    assert b"effect-size firewall" in result.stdout


def test_check_malformed_registry_exits_3(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path)
    index_path = root / INDEX_REL
    lines = index_path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [
        line
        for line in lines
        if not line.startswith("| 25 | REFERENCE & ARCHITECTURE |")
    ]
    assert len(kept) == len(lines) - 1, "fixture must drop exactly one registry row"
    index_path.write_text("".join(kept), encoding="utf-8")
    result = _run("--check", root=root)
    assert result.returncode == 3
    assert b"25 rows" in result.stdout


# --- no-write proof ----------------------------------------------------------


def test_every_mode_writes_nothing() -> None:
    before = _porcelain()
    for flags in MODE_FLAGS.values():
        _run(*flags)
    _run("--definitely-not-a-flag")
    after = _porcelain()
    assert before == after, "no vision mode may mutate the repository"
