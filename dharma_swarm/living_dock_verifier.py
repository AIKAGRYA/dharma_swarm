"""Read-only verifier for the canonical LivingDock projection.

LivingDock lives under ``~/.dharma/agents/<agent_uid>``. Legacy mirrors such as
``external_agents`` and ``ginko/agents`` may exist, but they are not authority.
This module inspects shape only; it never creates or repairs files.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

_AGENT_UID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{0,95}$")

CORE_FILES = (
    "identity.json",
    "living_agent.json",
)
HEARTBEAT_FILES = (
    "service_heartbeats.jsonl",
    "transport_heartbeats.jsonl",
    "wake_ledger.jsonl",
)
DIALOGUE_PATHS = (
    "dialogue/operator_sessions.jsonl",
    "dialogue/relationship_memory.jsonl",
    "dialogue/conversation_receipts",
)
SANCTUM_PATHS = (
    "sanctum/codex",
    "sanctum/vault",
    "sanctum/dojo",
    "sanctum/ingest_gate",
    "sanctum/tools",
    "sanctum/receipts",
)


@dataclass(frozen=True)
class LivingDockFinding:
    severity: Literal["pass", "warn", "fail"]
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class LivingDockReport:
    agent_uid: str
    status: Literal["pass", "warn", "fail"]
    living_dock_path: str
    findings: list[LivingDockFinding] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)
    legacy_mirrors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["findings"] = [finding.to_dict() for finding in self.findings]
        return data


def _aliases(agent_uid: str) -> list[str]:
    aliases = [agent_uid]
    if "_" in agent_uid:
        aliases.append(agent_uid.replace("_", "-"))
    if "-" in agent_uid:
        aliases.append(agent_uid.replace("-", "_"))
    return list(dict.fromkeys(aliases))


def _status(findings: list[LivingDockFinding]) -> Literal["pass", "warn", "fail"]:
    if any(finding.severity == "fail" for finding in findings):
        return "fail"
    if any(finding.severity == "warn" for finding in findings):
        return "warn"
    return "pass"


def _require_path(root: Path, relative: str, findings: list[LivingDockFinding], evidence: list[str]) -> None:
    path = root / relative
    if path.exists():
        findings.append(LivingDockFinding("pass", "path_present", f"{relative} present", str(path)))
        evidence.append(str(path))
        return
    findings.append(LivingDockFinding("fail", "path_missing", f"{relative} missing", str(path)))


def _warn_path(root: Path, relative: str, findings: list[LivingDockFinding], evidence: list[str]) -> None:
    path = root / relative
    if path.exists():
        findings.append(LivingDockFinding("pass", "path_present", f"{relative} present", str(path)))
        evidence.append(str(path))
        return
    findings.append(LivingDockFinding("warn", "path_missing_optional", f"{relative} missing", str(path)))


def verify_living_dock(
    agent_uid: str,
    *,
    dharma_home: Path | str | None = None,
    agents_root: Path | str | None = None,
    require_dialogue: bool = False,
    require_sanctum: bool = False,
) -> LivingDockReport:
    """Inspect ``~/.dharma/agents/<agent_uid>`` without mutating it."""
    if not _AGENT_UID_RE.fullmatch(agent_uid or ""):
        raise ValueError("invalid agent_uid")

    home = Path(dharma_home or Path.home() / ".dharma").expanduser().resolve()
    root = Path(agents_root).expanduser().resolve() if agents_root else home / "agents"
    dock = root / agent_uid
    findings: list[LivingDockFinding] = []
    evidence: list[str] = []
    legacy_mirrors: list[str] = []

    if dock.exists():
        findings.append(LivingDockFinding("pass", "living_dock_present", "canonical LivingDock exists", str(dock)))
        evidence.append(str(dock))
    else:
        findings.append(LivingDockFinding("fail", "living_dock_missing", "canonical LivingDock missing", str(dock)))

    for relative in CORE_FILES:
        _require_path(dock, relative, findings, evidence)

    for relative in HEARTBEAT_FILES:
        _warn_path(dock, relative, findings, evidence)

    for relative in DIALOGUE_PATHS:
        if require_dialogue:
            _require_path(dock, relative, findings, evidence)
        else:
            _warn_path(dock, relative, findings, evidence)

    for relative in SANCTUM_PATHS:
        if require_sanctum:
            _require_path(dock, relative, findings, evidence)
        else:
            _warn_path(dock, relative, findings, evidence)

    for alias in _aliases(agent_uid):
        external = home / "external_agents" / alias
        if external.exists():
            legacy_mirrors.append(str(external))
            findings.append(
                LivingDockFinding(
                    "warn" if not dock.exists() else "pass",
                    "external_agent_mirror",
                    "external_agents mirror exists; LivingDock remains canonical",
                    str(external),
                )
            )
        ginko = home / "ginko" / "agents" / alias
        if ginko.exists():
            legacy_mirrors.append(str(ginko))
            findings.append(
                LivingDockFinding(
                    "fail" if not dock.exists() else "warn",
                    "ginko_legacy_agent",
                    "ginko agent identity is legacy mirror, not canonical authority",
                    str(ginko),
                )
            )

    for candidate in (home / "AgentHome", home / "agent_home", root / "AgentHome", root / "agent_home"):
        if candidate.exists():
            findings.append(
                LivingDockFinding(
                    "fail",
                    "parallel_agent_home_object",
                    "AgentHome/agent_home must not become a parallel authority",
                    str(candidate),
                )
            )

    return LivingDockReport(
        agent_uid=agent_uid,
        status=_status(findings),
        living_dock_path=str(dock),
        findings=findings,
        evidence_paths=list(dict.fromkeys(evidence)),
        legacy_mirrors=list(dict.fromkeys(legacy_mirrors)),
    )

