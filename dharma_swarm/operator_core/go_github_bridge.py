"""Bridge GitHub-event evidence receipts emitted by tools/github_ingestor_go
into typed Python views.

This module is deliberately read-only: it parses sidecar receipts and exposes
their payload as a typed dataclass per supported GitHub event type. It does
not write canonical state, create WorkPackets, dispatch agents, or mutate
ontology / runtime databases. Decision-making remains in
``dharma_swarm.operator_core.closure_v0``.

The four supported event types mirror the Go adapter at
``tools/github_ingestor_go/adapter.go``:

* ``github_pull_request``
* ``github_commit``
* ``github_check_run``
* ``github_release``
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

GO_EVIDENCE_SCHEMA_V0 = "go_evidence_receipt.v0"

GitHubEventType = Literal[
    "github_pull_request",
    "github_commit",
    "github_check_run",
    "github_release",
]

SUPPORTED_GITHUB_EVENT_TYPES: tuple[GitHubEventType, ...] = (
    "github_pull_request",
    "github_commit",
    "github_check_run",
    "github_release",
)


class GoGitHubBridgeError(ValueError):
    """Raised when a GitHub-event Go receipt cannot be admitted as a sidecar
    sense-organ observation."""


@dataclass(frozen=True)
class GoGitHubReceipt:
    """Typed view of a Go-emitted GitHub-event receipt.

    Mirrors the on-disk JSON shape produced by tools/github_ingestor_go. The
    ``payload`` dict carries the original GitHub event body verbatim.
    """

    receipt_id: str
    correlation_id: str
    source: GitHubEventType
    source_url: str
    observed_at: str
    content_hash: str
    event_uid: str
    schema_version: str
    status: str
    payload: dict[str, Any]
    rejected_reason: str = ""

    def __post_init__(self) -> None:
        required = (
            self.receipt_id,
            self.correlation_id,
            self.source,
            self.observed_at,
            self.content_hash,
            self.event_uid,
            self.schema_version,
            self.status,
        )
        if not all(required):
            raise GoGitHubBridgeError("GoGitHubReceipt missing required identity fields")
        if self.schema_version != GO_EVIDENCE_SCHEMA_V0:
            raise GoGitHubBridgeError(
                f"unsupported Go evidence schema: {self.schema_version}"
            )
        if self.source not in SUPPORTED_GITHUB_EVENT_TYPES:
            raise GoGitHubBridgeError(f"unsupported GitHub event type: {self.source}")
        if self.status not in {"accepted", "rejected"}:
            raise GoGitHubBridgeError(f"unsupported receipt status: {self.status}")
        if self.status == "rejected" and not self.rejected_reason:
            raise GoGitHubBridgeError("rejected receipt must carry rejected_reason")


def load_go_github_receipt(path: Path) -> GoGitHubReceipt:
    """Read a JSON receipt produced by github_ingestor_go and return a typed
    view. Raises GoGitHubBridgeError for malformed receipts."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise GoGitHubBridgeError("Go GitHub receipt payload must be a JSON object")
    source = str(raw.get("source", ""))
    if source not in SUPPORTED_GITHUB_EVENT_TYPES:
        raise GoGitHubBridgeError(f"unsupported GitHub event type: {source!r}")
    return GoGitHubReceipt(
        receipt_id=str(raw.get("receipt_id", "")),
        correlation_id=str(raw.get("correlation_id", "")),
        source=source,  # type: ignore[arg-type]
        source_url=str(raw.get("source_url", "")),
        observed_at=str(raw.get("observed_at", "")),
        content_hash=str(raw.get("content_hash", "")),
        event_uid=str(raw.get("event_uid", "")),
        schema_version=str(raw.get("schema_version", "")),
        status=str(raw.get("status", "")),
        rejected_reason=str(raw.get("rejected_reason", "")),
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Per-event-type typed views — minimal, matches required fields enforced by
# the Go adapter so consumers can pattern-match without re-validating.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PullRequestEvent:
    number: int
    state: str
    head_sha: str
    base_sha: str
    title: str


@dataclass(frozen=True)
class CommitEvent:
    sha: str
    author: str
    message: str


@dataclass(frozen=True)
class CheckRunEvent:
    id: int
    name: str
    status: str


@dataclass(frozen=True)
class ReleaseEvent:
    tag_name: str
    name: str
    draft: bool
    prerelease: bool


def pull_request_event(receipt: GoGitHubReceipt) -> PullRequestEvent:
    if receipt.source != "github_pull_request":
        raise GoGitHubBridgeError(f"expected pull_request receipt, got {receipt.source!r}")
    p = receipt.payload
    return PullRequestEvent(
        number=int(p["number"]),
        state=str(p["state"]),
        head_sha=str(p["head_sha"]),
        base_sha=str(p["base_sha"]),
        title=str(p["title"]),
    )


def commit_event(receipt: GoGitHubReceipt) -> CommitEvent:
    if receipt.source != "github_commit":
        raise GoGitHubBridgeError(f"expected commit receipt, got {receipt.source!r}")
    p = receipt.payload
    return CommitEvent(
        sha=str(p["sha"]),
        author=str(p["author"]),
        message=str(p["message"]),
    )


def check_run_event(receipt: GoGitHubReceipt) -> CheckRunEvent:
    if receipt.source != "github_check_run":
        raise GoGitHubBridgeError(f"expected check_run receipt, got {receipt.source!r}")
    p = receipt.payload
    return CheckRunEvent(
        id=int(p["id"]),
        name=str(p["name"]),
        status=str(p["status"]),
    )


def release_event(receipt: GoGitHubReceipt) -> ReleaseEvent:
    if receipt.source != "github_release":
        raise GoGitHubBridgeError(f"expected release receipt, got {receipt.source!r}")
    p = receipt.payload
    return ReleaseEvent(
        tag_name=str(p["tag_name"]),
        name=str(p["name"]),
        draft=bool(p["draft"]),
        prerelease=bool(p["prerelease"]),
    )
