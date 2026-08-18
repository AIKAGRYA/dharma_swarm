"""Bridge-boundary tests for the bounded Helm context projection."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from dharma_swarm import model_status
from dharma_swarm.operator_core.helm_context_projection import HelmContextSources
from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.terminal_bridge import TerminalBridge
from dharma_swarm.terminal_bridge_helm_context import _safe_origin_identity


def _valid_request(request_id: str = "helm-context-1") -> dict[str, Any]:
    return {
        "id": request_id,
        "type": "helm.context.request",
        "ui": {
            "face": "zen",
            "place": "conversation",
            "facet": "chat",
            "overlay": "none",
            "keyboard_focus": "composer",
            "available_navigation": [
                "home",
                "conversation",
                "activity",
                "evidence",
                "system",
            ],
        },
    }


def _bridge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    sources: HelmContextSources | None = None,
) -> tuple[TerminalBridge, SessionStore, list[dict[str, Any]]]:
    monkeypatch.setattr(TerminalBridge, "_ensure_adapters", lambda self: None)
    session_store = SessionStore(root=tmp_path / "sessions")
    bridge = TerminalBridge(
        session_store=session_store,
        helm_context_sources=sources,
    )
    bridge._repo_root = tmp_path / "checkout"
    bridge._repo_root.mkdir()
    bridge._build_git_summary = lambda: {
        "branch": "unknown",
        "head": "unknown",
        "upstream": None,
        "ahead": None,
        "behind": None,
        "staged": None,
        "unstaged": None,
        "untracked": None,
    }
    emitted: list[dict[str, Any]] = []
    bridge._emit = emitted.append
    return bridge, session_store, emitted


def _file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_origin_identity_discards_git_credentials_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="https://sk-proj-do-not-leak@github.com/AIKAGRYA/dharma_swarm.git?token=hidden\n",
        ),
    )
    assert _safe_origin_identity(tmp_path) == (
        "github.com/AIKAGRYA/dharma_swarm",
        "AIKAGRYA/dharma_swarm",
    )


def test_origin_identity_fails_closed_for_unrecognized_remote(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="file:///tmp/local-only.git\n",
        ),
    )
    assert _safe_origin_identity(tmp_path) == (None, tmp_path.name)

    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="https://github.com/Org/Repo.git\nmalicious\n",
        ),
    )
    assert _safe_origin_identity(tmp_path) == (None, tmp_path.name)

    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="git@example.invalid:../escape.git\n",
        ),
    )
    assert _safe_origin_identity(tmp_path) == (None, tmp_path.name)


def test_git_summary_does_not_refresh_index(tmp_path: Path) -> None:
    repo = tmp_path / "read-only-summary"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("stable\n")
    for command in (
        ["git", "init", "-q"], ["git", "add", "tracked.txt"],
        ["git", "-c", "user.name=Helm Test", "-c", "user.email=helm@example.invalid", "commit", "-qm", "fixture"],
    ):
        subprocess.run(command, cwd=repo, check=True)
    tracked.touch()
    index = repo / ".git" / "index"
    before = index.read_bytes()
    summary = TerminalBridge._build_git_summary(SimpleNamespace(_repo_root=repo))
    assert summary["unstaged"] == 0
    assert index.read_bytes() == before


def test_helm_context_request_is_correlated_and_uses_server_runtime_epoch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    bridge._runtime_owner_id = "terminal-bridge:server-owned-epoch"
    bridge._build_git_summary = lambda: {
        "branch": "agent/self-aware",
        "head": "abc1234",
        "upstream": "origin/agent/self-aware",
        "ahead": 2,
        "behind": 0,
        "staged": 0,
        "unstaged": 1,
        "untracked": 0,
    }

    asyncio.run(bridge._handle_request(_valid_request("correlation-17")))

    assert len(emitted) == 1
    result = emitted[0]
    assert result["type"] == "helm.context.result"
    assert result["request_id"] == "correlation-17"
    assert set(result) == {"type", "request_id", "envelope"}
    envelope = result["envelope"]
    assert envelope["schema_version"] == "dharma.helm.context.v1"
    assert envelope["runtime_epoch"] == "terminal-bridge:server-owned-epoch"
    assert envelope["context_digest"].startswith("sha256:")
    workspace = envelope["projections"]["workspace"]["data"]
    assert workspace["workspace_path"] == str(tmp_path / "checkout")
    assert workspace["repository"] == "dharma_swarm"
    assert workspace["branch"] == "agent/self-aware"
    assert workspace["head"] == "abc1234"
    assert all(
        projection["authority"]["runtime_epoch"]
        == "terminal-bridge:server-owned-epoch"
        for projection in envelope["projections"].values()
    )


def test_invalid_place_facet_pair_returns_bounded_request_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    request = _valid_request("bad-coordinates")
    request["ui"].update({"place": "home", "facet": "chat"})
    asyncio.run(bridge._handle_request(request))
    assert emitted == [{
        "type": "bridge.error", "request_id": "bad-coordinates",
        "code": "invalid_helm_context_request",
        "message": "ui coordinates are outside the canonical Helm contract",
    }]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime_epoch", "client-forged-epoch"),
        ("authority", {"modality": "observed", "owner": "client"}),
        ("envelope", {"provider_state_promotion": True}),
        ("owner_sources", {"runtime_state": {"ready": True}}),
    ],
)
def test_request_cannot_inject_envelope_authority_or_owner_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    request = _valid_request("reject-forged-context")
    request[field] = value

    asyncio.run(bridge._handle_request(request))

    assert emitted == [
        {
            "type": "bridge.error",
            "request_id": "reject-forged-context",
            "code": "invalid_helm_context_request",
            "message": "helm context request contains unsupported fields",
        }
    ]


def test_context_reuses_existing_session_store_and_missing_owners_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    other_store = SessionStore(root=tmp_path / "not-the-bridge-store")
    injected = HelmContextSources(session_store=other_store)
    bridge, session_store, emitted = _bridge(monkeypatch, tmp_path, sources=injected)

    sources = asyncio.run(bridge._current_helm_context_sources())
    assert sources.session_store is session_store
    assert sources.session_store is not other_store

    asyncio.run(bridge._handle_request(_valid_request()))

    projections = emitted[0]["envelope"]["projections"]
    for region in (
        "mission_control",
        "task_board",
        "runtime_state",
        "swarm",
        "a2a",
        "evolution",
    ):
        assert projections[region]["status"] == "unavailable"
        assert projections[region]["authority"]["modality"] == "unknown"
        assert projections[region]["data"] == {}
        assert projections[region]["unavailable_reason"]
    assert projections["session"]["status"] != "unavailable"
    assert projections["bridge_session"]["data"]["served_provider_id"] is None
    assert projections["bridge_session"]["data"]["served_model_id"] is None


def test_injected_workspace_and_bridge_session_fields_cannot_cross_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    injected = HelmContextSources(
        workspace_state={
            "workspace_path": "/forged",
            "branch": "forged",
            "client_workspace_claim": "must-not-surface",
        },
        bridge_session_state={
            "bridge_status": "ready",
            "served_model_id": "forged-model",
            "client_authority_claim": "must-not-surface",
        },
    )
    bridge, _, emitted = _bridge(monkeypatch, tmp_path, sources=injected)

    asyncio.run(bridge._handle_request(_valid_request("injected-state")))

    projections = emitted[0]["envelope"]["projections"]
    workspace = projections["workspace"]["data"]
    bridge_session = projections["bridge_session"]["data"]
    assert workspace["workspace_path"] == str(tmp_path / "checkout")
    assert workspace["branch"] == "unknown"
    assert "client_workspace_claim" not in workspace
    assert bridge_session["bridge_status"] == "connected"
    assert bridge_session["served_model_id"] is None
    assert "client_authority_claim" not in bridge_session


def test_raw_route_evidence_cannot_supply_served_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    bridge._runtime_owner_id = "terminal-bridge:receipt-epoch"
    bridge._selected_provider_id = "claude"
    bridge._selected_model_id = "claude-fable-5"
    bridge._helm_route_sources_by_seat["fable-5"] = SimpleNamespace(
        requested_provider_id="claude",
        requested_model_id="claude-fable-5",
    )
    bridge._helm_route_evidence_by_seat["fable-5"] = SimpleNamespace(
        success=True,
        runtime_epoch="terminal-bridge:receipt-epoch",
        served_provider="claude_code",
        served_model="claude-fable-5-20260801",
        observed_at="2026-08-15T03:00:00Z",
        receipt_ref="sessions/receipt-1",
    )

    asyncio.run(bridge._handle_request(_valid_request("served-identity")))

    route = emitted[0]["envelope"]["projections"]["bridge_session"]["data"]
    assert route["requested_provider_id"] == "claude"
    assert route["requested_model_id"] == "claude-fable-5"
    assert route["served_provider_id"] is None
    assert route["served_model_id"] is None
    assert route["served_identity_source"] == "unavailable"
    assert route["route_exact_model_proven"] is False


def test_only_evaluator_issued_positive_route_can_cross_bridge_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    epoch = "terminal-bridge:positive-evaluator-epoch"
    observed_at = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)
    bridge._runtime_owner_id = epoch
    bridge._selected_provider_id = "claude"
    bridge._selected_model_id = "claude-fable-5"
    bridge._helm_on_call_projection = model_status.project_helm_on_call(
        [model_status.RouteEvidence(
            seat_id="fable-5", logical_lineage="fable-5",
            requested_provider="claude_code", requested_model="claude-fable-5",
            served_provider="claude_code", served_model="claude-fable-5",
            success=True, synthetic=False, observed_at=observed_at,
            expires_at=observed_at + timedelta(hours=1),
            verifier_id=model_status.ACCEPTED_ROUTE_VERIFIER_ID,
            verifier_version=model_status.ACCEPTED_ROUTE_VERIFIER_VERSION,
            verifier_accepted=True, receipt_ref="sessions/positive-receipt",
            receipt_sha256="e" * 64, runtime_epoch=epoch,
        )],
        now=observed_at + timedelta(minutes=1),
        current_runtime_epoch=epoch,
    )
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context._route_identity_now",
        lambda: observed_at + timedelta(minutes=2),
    )
    asyncio.run(bridge._handle_request(_valid_request("positive-identity")))
    route = emitted[0]["envelope"]["projections"]["bridge_session"]
    assert route["status"] == "observed"
    assert route["data"]["route_verdict"] == "ON_CALL"
    assert route["data"]["route_exact_model_proven"] is True
    assert route["data"]["route_receipt_sha256"] == "e" * 64


def test_evaluator_projection_preserves_served_identity_and_rejection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    epoch = "terminal-bridge:evaluator-epoch"
    observed_at = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)
    bridge._runtime_owner_id = epoch
    bridge._selected_provider_id = "claude"
    bridge._selected_model_id = "claude-fable-5"
    bridge._helm_on_call_projection = model_status.project_helm_on_call(
        [
            model_status.RouteEvidence(
                seat_id="fable-5",
                logical_lineage="fable-5",
                requested_provider="claude_code",
                requested_model="claude-fable-5",
                served_provider="claude_code",
                served_model="claude-fable-5-provider-build",
                success=True,
                synthetic=False,
                observed_at=observed_at,
                expires_at=observed_at + timedelta(hours=1),
                verifier_id=model_status.ACCEPTED_ROUTE_VERIFIER_ID,
                verifier_version=model_status.ACCEPTED_ROUTE_VERIFIER_VERSION,
                verifier_accepted=True,
                receipt_ref="sessions/evaluator-receipt",
                receipt_sha256="a" * 64,
                runtime_epoch=epoch,
            )
        ],
        now=observed_at + timedelta(minutes=1),
        current_runtime_epoch=epoch,
    )
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context._route_identity_now",
        lambda: observed_at + timedelta(minutes=2),
    )

    asyncio.run(bridge._handle_request(_valid_request("evaluated-identity")))

    route = emitted[0]["envelope"]["projections"]["bridge_session"]["data"]
    assert route["served_provider_id"] == "claude_code"
    assert route["served_model_id"] == "claude-fable-5-provider-build"
    assert route["served_identity_source"] == "provider_response_via_route_evaluator"
    assert route["route_receipt_ref"] == "sessions/evaluator-receipt"
    assert route["route_receipt_sha256"] == "a" * 64
    assert route["route_verifier_id"] == model_status.ACCEPTED_ROUTE_VERIFIER_ID
    assert route["route_verifier_version"] == model_status.ACCEPTED_ROUTE_VERIFIER_VERSION
    assert route["route_evidence_synthetic"] is False
    assert route["route_verdict"] == "REJECTED"
    assert route["route_verdict_reason"] == "served_identity_mismatch"
    assert route["route_exact_model_proven"] is False
    assert route["route_evidence_expires_at"] == "2026-08-15T04:00:00Z"
    assert route["route_evidence_freshness"] == "fresh"


def test_cached_expired_evaluator_evidence_cannot_remain_on_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    epoch = "terminal-bridge:expired-evaluator-epoch"
    observed_at = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)
    expires_at = observed_at + timedelta(hours=1)
    bridge._runtime_owner_id = epoch
    bridge._selected_provider_id = "claude"
    bridge._selected_model_id = "claude-fable-5"
    bridge._helm_on_call_projection = model_status.project_helm_on_call(
        [
            model_status.RouteEvidence(
                seat_id="fable-5",
                logical_lineage="fable-5",
                requested_provider="claude_code",
                requested_model="claude-fable-5",
                served_provider="claude_code",
                served_model="claude-fable-5",
                success=True,
                synthetic=False,
                observed_at=observed_at,
                expires_at=expires_at,
                verifier_id=model_status.ACCEPTED_ROUTE_VERIFIER_ID,
                verifier_version=model_status.ACCEPTED_ROUTE_VERIFIER_VERSION,
                verifier_accepted=True,
                receipt_ref="sessions/expired-receipt",
                receipt_sha256="b" * 64,
                runtime_epoch=epoch,
            )
        ],
        now=observed_at + timedelta(minutes=1),
        current_runtime_epoch=epoch,
    )
    assert (
        bridge._helm_on_call_projection.seats[0].verdict
        is model_status.RouteVerdict.ON_CALL
    )
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context._route_identity_now",
        lambda: expires_at,
    )

    asyncio.run(bridge._handle_request(_valid_request("expired-identity")))

    route = emitted[0]["envelope"]["projections"]["bridge_session"]["data"]
    assert route["served_provider_id"] == "claude_code"
    assert route["served_model_id"] == "claude-fable-5"
    assert route["route_evidence_expires_at"] == "2026-08-15T04:00:00Z"
    assert route["route_evidence_freshness"] == "expired"
    assert route["route_verdict"] == "UNKNOWN"
    assert route["route_verdict_reason"] == "cached_route_evidence_expired"
    assert route["route_exact_model_proven"] is False


def test_future_cached_evaluator_evidence_cannot_become_current(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    epoch = "terminal-bridge:future-evaluator-epoch"
    observed_at = datetime(2026, 8, 15, 4, 0, tzinfo=timezone.utc)
    bridge._runtime_owner_id = epoch
    bridge._selected_provider_id = "claude"
    bridge._selected_model_id = "claude-fable-5"
    bridge._helm_on_call_projection = model_status.project_helm_on_call(
        [model_status.RouteEvidence(
            seat_id="fable-5", logical_lineage="fable-5",
            requested_provider="claude_code", requested_model="claude-fable-5",
            served_provider="claude_code", served_model="claude-fable-5",
            success=True, synthetic=False, observed_at=observed_at,
            expires_at=observed_at + timedelta(hours=1),
            verifier_id=model_status.ACCEPTED_ROUTE_VERIFIER_ID,
            verifier_version=model_status.ACCEPTED_ROUTE_VERIFIER_VERSION,
            verifier_accepted=True, receipt_ref="sessions/future-receipt",
            receipt_sha256="d" * 64, runtime_epoch=epoch,
        )],
        now=observed_at,
        current_runtime_epoch=epoch,
    )
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context._route_identity_now",
        lambda: observed_at - timedelta(minutes=1),
    )
    asyncio.run(bridge._handle_request(_valid_request("future-identity")))
    route = emitted[0]["envelope"]["projections"]["bridge_session"]["data"]
    assert route["route_verdict"] == "UNKNOWN"
    assert route["route_verdict_reason"] == "route_evaluation_timestamp_in_future"
    assert route["route_exact_model_proven"] is False
    assert route["served_model_id"] is None


def test_evaluator_evidence_for_different_selected_route_cannot_be_promoted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    epoch = "terminal-bridge:route-mismatch-epoch"
    observed_at = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)
    bridge._runtime_owner_id = epoch
    bridge._selected_provider_id = "claude"
    bridge._selected_model_id = "claude-fable-5"
    bridge._helm_on_call_projection = model_status.project_helm_on_call(
        [
            model_status.RouteEvidence(
                seat_id="fable-5",
                logical_lineage="fable-5",
                requested_provider="another-provider",
                requested_model="another-model",
                served_provider="claude_code",
                served_model="claude-fable-5",
                success=True,
                synthetic=False,
                observed_at=observed_at,
                expires_at=observed_at + timedelta(hours=1),
                verifier_id=model_status.ACCEPTED_ROUTE_VERIFIER_ID,
                verifier_version=model_status.ACCEPTED_ROUTE_VERIFIER_VERSION,
                verifier_accepted=True,
                receipt_ref="sessions/mismatched-route-receipt",
                receipt_sha256="c" * 64,
                runtime_epoch=epoch,
            )
        ],
        now=observed_at + timedelta(minutes=1),
        current_runtime_epoch=epoch,
    )
    assert (
        bridge._helm_on_call_projection.seats[0].verdict
        is model_status.RouteVerdict.ON_CALL
    )
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_helm_context._route_identity_now",
        lambda: observed_at + timedelta(minutes=2),
    )

    asyncio.run(bridge._handle_request(_valid_request("route-mismatch")))

    route = emitted[0]["envelope"]["projections"]["bridge_session"]["data"]
    assert route["served_provider_id"] is None
    assert route["served_model_id"] is None
    assert route["route_evidence_expires_at"] is None
    assert route["route_evidence_freshness"] == "selected_route_mismatch"
    assert route["route_verdict"] == "UNKNOWN"
    assert route["route_verdict_reason"] == "selected_route_mismatch"
    assert route["route_exact_model_proven"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda request: request["ui"].__setitem__("face", "admin-console"),
        lambda request: request["ui"].__setitem__("facet", "sk-live-do-not-leak-1234567890"),
        lambda request: request["ui"].__setitem__("overlay", None),
        lambda request: request["ui"].__setitem__("overlay", {"authority": "observed"}),
        lambda request: request["ui"].__setitem__(
            "available_navigation",
            ["system", "evidence", "activity", "conversation", "home"],
        ),
        lambda request: request["ui"].__setitem__("authority", "observed"),
    ],
)
def test_malformed_ui_is_rejected_without_echoing_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutate,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    request = deepcopy(_valid_request("malformed-ui"))
    mutate(request)

    asyncio.run(bridge._handle_request(request))

    assert len(emitted) == 1
    assert emitted[0]["type"] == "bridge.error"
    assert emitted[0]["request_id"] == "malformed-ui"
    assert emitted[0]["code"] == "invalid_helm_context_request"
    assert "sk-live-do-not-leak" not in json.dumps(emitted)


def test_request_id_bound_matches_typescript_decoder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    asyncio.run(bridge._handle_request(_valid_request("r" * 129)))
    assert emitted == [{
        "type": "bridge.error",
        "request_id": "",
        "code": "invalid_helm_context_request",
        "message": "request id is missing or out of bounds",
    }]


def test_secret_shaped_request_id_is_rejected_without_echo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    asyncio.run(bridge._handle_request(_valid_request("sk-proj-do-not-echo-1234567890")))
    assert emitted == [{
        "type": "bridge.error",
        "request_id": "",
        "code": "invalid_helm_context_request",
        "message": "request id contains protected content",
    }]
    assert "sk-proj-do-not-echo" not in json.dumps(emitted)


def test_bidirectional_request_id_is_rejected_without_echo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)
    asyncio.run(bridge._handle_request(_valid_request("safe\u202eevil")))
    assert emitted[0]["type"] == "bridge.error"
    assert emitted[0]["request_id"] == ""
    assert "\u202e" not in json.dumps(emitted, ensure_ascii=False)


def test_context_request_does_not_construct_runtime_owners_or_write_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge, _, emitted = _bridge(monkeypatch, tmp_path)

    def unexpected_owner(*args: object, **kwargs: object) -> object:
        raise AssertionError("context observation instantiated an effectful owner")

    monkeypatch.setattr("dharma_swarm.terminal_bridge.RuntimeStateStore", unexpected_owner)
    monkeypatch.setattr("dharma_swarm.terminal_bridge.OperatorViews", unexpected_owner)
    before = _file_snapshot(tmp_path)

    asyncio.run(bridge._handle_request(_valid_request("read-only-context")))

    assert emitted[0]["type"] == "helm.context.result"
    assert _file_snapshot(tmp_path) == before
    assert not list(tmp_path.rglob("*.db"))
    assert not list(tmp_path.rglob("*.sqlite"))
