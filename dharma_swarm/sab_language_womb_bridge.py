"""Bridge persistent-agent witness logs into SAB language-womb contributions.

This module is intentionally local-only. It writes small JSON contribution
fragments for the dharmic-agora packager to wrap as SAB seed packets. It does
not contact external services and it does not grant standing.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


AGORA_REPO = Path.home() / "dharmic-agora"
AGORA_SCRIPT = AGORA_REPO / "scripts" / "sab_language_womb_tick.py"
AGORA_INBOX = (
    AGORA_REPO
    / "docs"
    / "lanes"
    / "sab-agent-seeding-v1"
    / "contributions"
    / "inbox"
)

RELEVANCE_TERMS = (
    "claim",
    "evidence",
    "uncertainty",
    "proof",
    "authority",
    "standing",
    "typecheck",
    "typechecker",
    "evaluator",
    "language",
    "modality",
    "provenance",
    "witness",
    "governance",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(value: str, fallback: str = "agent") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value.strip()).strip("_")
    return cleaned or fallback


def _read_recent_lines(path: Path, *, limit: int = 40) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-limit:]


def _relevant_lines(lines: list[str]) -> list[str]:
    relevant = []
    for line in lines:
        lowered = line.lower()
        if any(term in lowered for term in RELEVANCE_TERMS):
            relevant.append(line[:1000])
    return relevant


def _digest_lines(agent_name: str, lines: list[str]) -> str:
    material = json.dumps({"agent": agent_name, "lines": lines}, sort_keys=True)
    return sha256(material.encode("utf-8")).hexdigest()


def _state_path(state_dir: Path, agent_name: str) -> Path:
    return state_dir / "sab_language_womb" / f"{_slug(agent_name)}.json"


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _packager_python(agora_repo: Path) -> str:
    python_path = agora_repo / ".venv" / "bin" / "python"
    return str(python_path) if python_path.exists() else "python3"


def write_witness_contribution(
    *,
    agent_name: str,
    witness_log: Path,
    state_dir: Path,
    agora_repo: Path = AGORA_REPO,
    run_packager: bool = True,
) -> str:
    """Write one SAB contribution from recent relevant witness lines.

    Returns a concise status string for persistent-agent cron logs.
    """

    recent = _read_recent_lines(witness_log)
    relevant = _relevant_lines(recent)
    if not relevant:
        return "sab_language_womb: no_relevant_witness_delta"

    digest = _digest_lines(agent_name, relevant)
    state_path = _state_path(state_dir, agent_name)
    state = _load_state(state_path)
    if state.get("last_digest") == digest:
        return "sab_language_womb: unchanged"

    inbox = (
        agora_repo
        / "docs"
        / "lanes"
        / "sab-agent-seeding-v1"
        / "contributions"
        / "inbox"
    )
    inbox.mkdir(parents=True, exist_ok=True)
    agent_slug = _slug(agent_name)
    contribution_path = inbox / f"{_utc_stamp()}_{agent_slug}_{digest[:12]}.json"
    contribution = {
        "problem_ref": "language_womb.epistemic_authority.v1",
        "delta_kind": "trace",
        "claim": (
            f"Persistent agent {agent_name} produced witness-log material "
            "relevant to claim, evidence, authority, proof, or language semantics."
        ),
        "evidence_or_reasoning": [
            f"{witness_log} sha256:{digest}",
            *relevant[:5],
        ],
        "falsification_route": (
            "Inspect the witness log and challenge whether the cited lines are "
            "actually relevant to the language-womb problem."
        ),
        "language_impact": (
            "If accepted, this trace can become a fixture or counterexample for "
            "epistemic-authority type/evaluator rules."
        ),
        "authority_boundary": (
            "Witness-log trace only; no truth, standing, external posting, or "
            "deployment authority."
        ),
    }
    contribution_path.write_text(
        json.dumps(contribution, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "last_digest": digest,
                "last_contribution_path": str(contribution_path),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if not run_packager:
        return f"sab_language_womb: inbox={contribution_path.name}"

    script = agora_repo / "scripts" / "sab_language_womb_tick.py"
    if not script.exists():
        return f"sab_language_womb: inbox={contribution_path.name} packager_missing"
    proc = subprocess.run(
        [
            _packager_python(agora_repo),
            str(script),
            "--agent-id",
            f"agent_{agent_slug}",
            "--agent-name",
            agent_name,
        ],
        cwd=str(agora_repo),
        capture_output=True,
        text=True,
        timeout=90,
    )
    if proc.returncode != 0:
        return f"sab_language_womb: inbox={contribution_path.name} packager_failed={proc.stderr[:160]}"
    try:
        summary = json.loads(proc.stdout)
        packet_count = len(summary.get("packets_written", []))
    except Exception:
        packet_count = 0
    return f"sab_language_womb: inbox={contribution_path.name} packets={packet_count}"
