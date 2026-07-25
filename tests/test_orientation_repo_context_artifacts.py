from __future__ import annotations

import json
from pathlib import Path

from scripts.governance import orientation_graph as og


REPO_ROOT = Path(__file__).resolve().parents[1]
ORIENTATION_REPORTS = (
    REPO_ROOT / "reports/orientation/repo_context.md",
    REPO_ROOT / "reports/orientation/repo_context.json",
)
MACHINE_PATH_MARKERS = ("/Users/dhyana", "/private/tmp")


def test_repo_context_artifacts_do_not_commit_machine_paths() -> None:
    for path in ORIENTATION_REPORTS:
        text = path.read_text(encoding="utf-8")
        for marker in MACHINE_PATH_MARKERS:
            assert marker not in text, f"{path.relative_to(REPO_ROOT)} contains {marker}"


def test_orientation_generator_outputs_do_not_commit_machine_paths(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    onboarding = home / ".dharma/onboarding"
    inbox = home / ".dharma/a2a_bus/inboxes/codex"
    onboarding.mkdir(parents=True)
    inbox.mkdir(parents=True)
    (onboarding / "receipt.json").write_text("{}", encoding="utf-8")
    (inbox / "task.json").write_text("{}", encoding="utf-8")

    output_dir = tmp_path / "orientation"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(og, "A2A_BUS", home / ".dharma/a2a_bus")
    monkeypatch.setattr(og, "DEPLOY_RECEIPT", home / ".dharma/ops/deploy_receipt.json")
    monkeypatch.setattr(og, "LANE_MAP", home / ".dharma/ops/parallel_lane_map.json")
    monkeypatch.setattr(og, "REPO_CONTEXT_DIR", output_dir)
    monkeypatch.setattr(og, "REPO_CONTEXT_JSON", output_dir / "repo_context.json")
    monkeypatch.setattr(og, "REPO_CONTEXT_MD", output_dir / "repo_context.md")

    packet = og.OrientationPacket(
        identity=og.Identity(one_line="test", read_first=[]),
        organs=[],
        tracks=[],
        custody=og.CustodyReport(registered_total=0, present=0),
        liveness=og.Liveness(receipt="test"),
        broken=[],
        loop1=og.Loop1Closure(live=False),
        receipts_tail=og.build_receipts_tail(),
        a2a_bus=og.build_a2a_bus_state(),
        body=og.build_body_state(),
        context_hash="test",
    )
    json_path, md_path = og.write_repo_context(packet)

    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")
    combined = json_text + md_text
    payload = json.loads(json_text)
    assert payload["a2a_bus"]["root"].startswith("~/")
    assert payload["receipts_tail"][0]["path"].startswith("~/")
    assert str(home) not in combined
    for marker in MACHINE_PATH_MARKERS:
        assert marker not in combined
