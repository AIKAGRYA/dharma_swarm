from __future__ import annotations

import json
import subprocess
from pathlib import Path

from dharma_swarm.operator_core.operator_coherence_cockpit import (
    build_operator_coherence_cockpit,
    render_markdown_report,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_operator_coherence_projection_is_probe_backed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)

    _write(
        repo / "docs/governance/ACTIVE_TRACK.yaml",
        """
schema_version: 2
track_policy:
  max_active: 2
active_tracks:
  - id: cockpit-track
    name: Cockpit Track
    status: ACTIVE
    verified_at: "2026-06-22"
    ttl_days: 14
    owner: "@tester"
    serves: substrate-nativeness
    owned_surfaces:
      - dashboard/src/app/dashboard/cockpit/page.tsx
closed_tracks: []
""",
    )
    _write(
        repo / "reports/governance/active_track_evidence.json",
        json.dumps(
            {
                "active_tracks": [
                    {
                        "id": "cockpit-track",
                        "shippable": True,
                        "completion_progress": {"passed": 2, "total": 2},
                    }
                ]
            }
        ),
    )
    _write(
        repo / "docs/state/BROKEN_REGISTER.md",
        """
# Broken Register
## OPEN ITEMS
### BR-001 — open real defect
- **status:** OPEN — still broken

## CLOSED ITEMS
### BR-002 — fixed defect with noisy words
- **status:** **FIXED 2026-05-20** — mentioned PARTIAL and not stale in prose
""",
    )
    for path in [
        "dashboard/package.json",
        "dashboard/src/app/dashboard/page.tsx",
        "dashboard/src/app/dashboard/cockpit/page.tsx",
        "dashboard/src/components/operator-coherence/OperatorCoherenceCockpit.tsx",
        "api/routers/control_surface.py",
        "dharma_swarm/operator_core/control_surface.py",
        "api/routers/operator_coherence.py",
        "dharma_swarm/operator_core/operator_coherence_cockpit.py",
        "scripts/runtime/live_ops_census.py",
        "docs/state/LIVE_OPS_DASHBOARD.md",
        "dharma_swarm/providers.py",
        "MODEL_ROUTING_MAP.md",
        "tests/test_model_router_telemetry.py",
    ]:
        _write(repo / path, "// proof\n")
    (repo / "terminal").mkdir()
    (repo / "terminal-v2").mkdir()
    (repo / "dharma_swarm/a2a").mkdir(parents=True)
    (repo / "reports/a2a").mkdir(parents=True)
    (repo / ".dharma/preservation").mkdir(parents=True)

    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _write(repo / "rogue.txt", "untracked local work\n")

    # A local-only branch that is NOT checked out in any worktree — the kind of
    # rogue/unpushed work the branch census must surface (worktree probe misses).
    subprocess.run(
        ["git", "branch", "rogue/local-only-feature"], cwd=repo, check=True, capture_output=True
    )

    payload = build_operator_coherence_cockpit(
        repo,
        include_github=False,
        include_live_probes=False,
    )

    assert payload["schema_version"] == "operator_coherence_cockpit.v0.1"
    assert payload["track_portfolio"]["active_count"] == 1
    assert any(card["kind"] == "dirty_files" for card in payload["cards"])
    assert [card["title"] for card in payload["cards"] if card["kind"] == "broken_register"] == [
        "BR-001 — open real defect"
    ]
    assert payload["track_portfolio"]["broken_register"]["open_like_count"] == 1
    assert payload["readiness"]["score"] >= 0

    # Branch census enumerates ALL local branches, not just checked-out ones.
    branch_census = payload["branch_census"]
    assert branch_census["total"] >= 1
    assert branch_census["local_only"] >= 1
    branch_cards = [c for c in payload["cards"] if c["kind"] == "branch"]
    assert any(c["branch"] == "rogue/local-only-feature" for c in branch_cards)
    rogue_branch = next(c for c in branch_cards if c["branch"] == "rogue/local-only-feature")
    assert rogue_branch["risk"] == "local_only_branch"
    assert rogue_branch["evidence"], "every branch card must carry evidence"
    assert payload["rogue_work_radar"]["local_only_branch_count"] >= 1

    # Live-ops integration is present (disabled here, but the key must exist and
    # report why it is unavailable rather than silently dropping the source).
    assert "live_ops" in payload
    assert payload["live_ops"]["enabled"] is False
    assert payload["live_ops"]["reason"] == "live_probes_disabled"
    assert payload["onboarding"]["status"] == "missing_or_drifted"
    assert "runtime_receipts" in payload
    assert "runtime_dbs" in payload["runtime_receipts"]

    markdown = render_markdown_report(payload)
    assert "Operator Coherence Cockpit" in markdown
    assert "Prod readiness estimate" in markdown


def test_operator_coherence_api_envelope_contract() -> None:
    """The /api/operator-coherence/report envelope wraps the cockpit projection.

    The cockpit dashboard surface depends on this contract: the HTTP envelope
    carries operator_coherence_api.v0.1 while the inner data payload carries
    operator_coherence_cockpit.v0.1 (the version the dashboard v2 model expects).
    """
    from api.routers.operator_coherence import operator_coherence_report

    result = operator_coherence_report(github=False, live_probes=False)

    assert result["schema_version"] == "operator_coherence_api.v0.1"
    assert result["status"] in ("ok", "partial")
    assert result["request_id"]
    assert result["generated_at"]
    assert result["data"] is not None
    assert result["data"]["schema_version"] == "operator_coherence_cockpit.v0.1"
