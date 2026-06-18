"""Shadow-first Saraswati/Dharmic Agora bridge.

The bridge is intentionally disabled by default. A post-run caller can build the
same contribution packet a live SAB submit would use, but no network request is
made unless DHARMA_SAB_BRIDGE_ENABLED=1 or the caller passes enabled=True.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


DEFAULT_SAB_BASE_URL = "http://127.0.0.1:8000"
SAB_SUBMIT_PATH = "/api/spark/submit"


class _Opener(Protocol):
    def open(self, request: urllib.request.Request, timeout: float | None = None) -> Any:
        ...


@dataclass(frozen=True)
class SABContribution:
    """A witnessed loop contribution candidate for SAB."""

    run_id: str
    agent_uid: str
    loop_id: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    schema_version: str = "dharma_swarm.sab_contribution.v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "run_id": self.run_id,
            "agent_uid": self.agent_uid,
            "loop_id": self.loop_id,
            "summary": self.summary,
            "evidence": dict(self.evidence),
        }


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def content_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def build_post_run_contribution(
    *,
    run_id: str,
    agent_uid: str,
    summary: str,
    evidence: dict[str, Any] | None = None,
    loop_id: str = "swarm_task_loop",
) -> SABContribution:
    return SABContribution(
        run_id=run_id,
        agent_uid=agent_uid,
        loop_id=loop_id,
        summary=summary,
        evidence=dict(evidence or {}),
    )


def build_submit_payload(
    contribution: SABContribution,
    *,
    author_id: str,
    signature: str,
) -> dict[str, Any]:
    content = contribution.to_dict()
    return {
        "author_id": author_id,
        "content": content,
        "content_sha256": content_sha256(content),
        "signature": signature,
        "signature_scheme": "external-ed25519",
    }


class SABClient:
    """Tiny stdlib SAB client with live submission disabled by default."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        enabled: bool | None = None,
        timeout_seconds: float = 5.0,
        opener: _Opener | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("DHARMA_SAB_BASE_URL") or DEFAULT_SAB_BASE_URL).rstrip("/")
        if enabled is None:
            enabled = os.environ.get("DHARMA_SAB_BRIDGE_ENABLED") == "1"
        self.enabled = bool(enabled)
        self.timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.build_opener()

    def submit_spark(
        self,
        contribution: SABContribution,
        *,
        author_id: str = "",
        signature: str = "",
    ) -> dict[str, Any]:
        content = contribution.to_dict()
        digest = content_sha256(content)
        if not self.enabled:
            return {
                "submitted": False,
                "mode": "shadow",
                "endpoint": self.base_url + SAB_SUBMIT_PATH,
                "content_sha256": digest,
                "content": content,
            }
        if not author_id or not signature:
            return {
                "submitted": False,
                "mode": "blocked",
                "endpoint": self.base_url + SAB_SUBMIT_PATH,
                "content_sha256": digest,
                "error": "live SAB submit requires author_id and external signature",
            }

        payload = build_submit_payload(contribution, author_id=author_id, signature=signature)
        request = urllib.request.Request(
            self.base_url + SAB_SUBMIT_PATH,
            data=canonical_json(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = self._opener.open(request, timeout=self.timeout_seconds)
        raw = response.read().decode("utf-8")
        try:
            body: Any = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return {
            "submitted": True,
            "mode": "live",
            "endpoint": self.base_url + SAB_SUBMIT_PATH,
            "content_sha256": digest,
            "response": body,
        }


def post_run_shadow_hook(
    *,
    run_id: str,
    agent_uid: str,
    summary: str,
    evidence: dict[str, Any] | None = None,
    loop_id: str = "swarm_task_loop",
    client: SABClient | None = None,
) -> dict[str, Any]:
    contribution = build_post_run_contribution(
        run_id=run_id,
        agent_uid=agent_uid,
        summary=summary,
        evidence=evidence,
        loop_id=loop_id,
    )
    return (client or SABClient(enabled=False)).submit_spark(contribution)
