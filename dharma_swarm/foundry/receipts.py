"""Foundry improvement receipts — the seven-link chain (``foundry_improvement.v1``).

A verified improvement is not a number the swarm asserts; it is a chain a third
party can follow. Each link is minted only when its evidence exists, and a
receipt is "externally confirmed" (ring 3) only once a link nobody in the swarm
controls is present (a merged PR or an independent-leaderboard record). The
stratified fields (domain / counterparty / value-risk / independence / transfer)
are what the One Wire guardian reads when counting quorum.

Runtime receipts live under ``~/.dharma/foundry/receipts/`` and never enter git
(CLAUDE.md: runtime receipts never enter git).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.foundry.evaluator import canonical_digest

SCHEMA_VERSION = "foundry_improvement.v1"
_STATE_ROOT = Path.home() / ".dharma" / "foundry" / "receipts"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- link constructors (each returns a plain dict; absent links stay None) ---

def pre_registration_link(
    *, target_id: str, resolved_sha: str, tree_digest: str,
    baseline_metric: float, oracle_cmd: list[str], seed: int,
) -> dict[str, Any]:
    """Link 1: the sealed manifest, registered BEFORE the attempt (anti-Goodhart)."""
    body = {
        "target_id": target_id, "resolved_sha": resolved_sha,
        "tree_digest": tree_digest, "baseline_metric": baseline_metric,
        "oracle_cmd": oracle_cmd, "seed": seed, "registered_at": _utc_now_iso(),
    }
    return {"link": "pre_registration", **body, "digest": canonical_digest(body)}


def benchmark_link(
    *, baseline_metric: float, candidate_metric: float, runs: int,
    coefficient_of_variation: float, repro_cmd: list[str], isolation_level: str,
) -> dict[str, Any]:
    """Link 2: the multi-run pre/post benchmark with variance + repro command."""
    delta = candidate_metric - baseline_metric
    body = {
        "baseline_metric": baseline_metric, "candidate_metric": candidate_metric,
        "delta": delta, "runs": runs,
        "coefficient_of_variation": coefficient_of_variation,
        "repro_cmd": repro_cmd, "isolation_level": isolation_level,
        "measured_at": _utc_now_iso(),
    }
    return {"link": "benchmark", **body, "digest": canonical_digest(body)}


def disclosure_link(*, ai_assisted: bool = True, duplicate_checked: bool = True,
                    test_results: str = "", diff_sha256: str = "") -> dict[str, Any]:
    """Link 3: the mandatory AI-assist disclosure + duplicate-check evidence.

    ``diff_sha256`` pins the exact candidate payload the receipt is about, so
    a third party can match the receipt to the artifact byte-for-byte.
    """
    return {
        "link": "disclosure", "ai_assisted": ai_assisted,
        "duplicate_checked": duplicate_checked, "test_results": test_results,
        "diff_sha256": diff_sha256,
    }


def external_ci_link(*, url: str, status: str) -> dict[str, Any]:
    """Link 4: the target's own CI (independent infrastructure) result."""
    return {"link": "external_ci", "url": url, "status": status}


def merge_event_link(
    *, repo: str, pr_url: str, state: str, author: str, merged_by: str,
    merge_commit_sha: str, merged_at: str,
) -> dict[str, Any]:
    """Link 5: the merge event — ring 3 when ``merged_by != author``."""
    return {
        "link": "merge_event", "repo": repo, "pr_url": pr_url, "state": state,
        "author": author, "merged_by": merged_by,
        "merge_commit_sha": merge_commit_sha, "merged_at": merged_at,
        "independent": bool(merged_by and merged_by != author),
    }


def guardian_countersign_link(*, cycle_file: str, verified: bool) -> dict[str, Any]:
    """Link 6: the forge-measurement-guardian recheck + drift seal."""
    return {"link": "guardian_countersign", "cycle_file": cycle_file, "verified": verified}


def report_render_link(*, path: str, digest: str) -> dict[str, Any]:
    """Link 7: the rendered report card (pure function of the sealed receipt)."""
    return {"link": "report_render", "path": path, "digest": digest}


@dataclass
class StratifiedFields:
    """The One Wire quorum dimensions the guardian counts."""

    domain: str = "external_code_contribution"
    counterparty: str = ""
    value_risk: str = ""
    independence: str = ""
    transfer: str = ""


@dataclass
class FoundryReceipt:
    """A verified-improvement receipt that accretes its seven links over time."""

    receipt_id: str
    target_id: str
    candidate_id: str
    stratified: StratifiedFields = field(default_factory=StratifiedFields)
    pre_registration: dict[str, Any] | None = None
    benchmark: dict[str, Any] | None = None
    disclosure: dict[str, Any] | None = None
    external_ci: dict[str, Any] | None = None
    merge_event: dict[str, Any] | None = None
    guardian_countersign: dict[str, Any] | None = None
    report_render: dict[str, Any] | None = None
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=_utc_now_iso)

    _LINKS = (
        "pre_registration", "benchmark", "disclosure", "external_ci",
        "merge_event", "guardian_countersign", "report_render",
    )

    def links_present(self) -> tuple[str, ...]:
        return tuple(name for name in self._LINKS if getattr(self, name) is not None)

    def externally_confirmed(self) -> bool:
        """Ring 3: a merge by a non-author, or an independent-leaderboard record."""
        me = self.merge_event
        if me and me.get("state") == "MERGED" and me.get("independent"):
            return True
        ci = self.external_ci
        return bool(ci and ci.get("status") == "independent_record")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["links_present"] = list(self.links_present())
        data["externally_confirmed"] = self.externally_confirmed()
        return data

    def seal(self) -> str:
        return canonical_digest(self.to_dict())


def _safe_filename(receipt_id: str) -> str:
    """Filesystem/artifact-safe name: model ids can contain ':' or '/'
    (e.g. ``qwen3-coder-480b:free``) which GitHub artifact upload rejects.
    The receipt payload keeps the true ``receipt_id``; only the filename
    is sanitized.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "-", receipt_id)


def write_receipt(receipt: FoundryReceipt, *, state_root: Path | None = None) -> Path:
    """Persist a receipt (with its seal) under the runtime receipts root."""
    root = Path(state_root) if state_root is not None else _STATE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    payload = receipt.to_dict()
    payload["sealed_digest"] = receipt.seal()
    path = root / f"{_safe_filename(receipt.receipt_id)}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
