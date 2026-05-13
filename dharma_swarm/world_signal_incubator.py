"""R&D incubation artifacts for promising but under-verified world signals."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir


def write_incubations(
    movements: list[dict[str, Any]],
    *,
    output_dir: Path | None = None,
) -> list[Path]:
    """Write Markdown plus JSON R&D artifacts for incubating movements."""
    root = output_dir or dharma_state_dir() / "meta" / "world_radar" / "incubations"
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for movement in movements:
        payload = build_incubation_payload(movement)
        slug = _slug(str(movement.get("title") or movement.get("movement_id") or "signal"))
        stem = f"{slug}-{payload['incubation_id'][:8]}"
        json_path = root / f"{stem}.json"
        md_path = root / f"{stem}.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(render_incubation_markdown(payload), encoding="utf-8")
        movement.setdefault("strategic_vision", {})["incubation_path"] = str(md_path)
        written.extend([json_path, md_path])
    return written


def build_incubation_payload(movement: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic three-pass R&D plan for one movement."""
    title = str(movement.get("title") or "Untitled world signal")
    seed = f"{movement.get('movement_id', '')}:{title}"
    strategy = dict(movement.get("strategic_vision") or {})
    return {
        "incubation_id": hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "movement_id": movement.get("movement_id", ""),
        "title": title,
        "status": movement.get("status", "incubating"),
        "score": movement.get("weighted_score", 0.0),
        "evidence": movement.get("signals", []),
        "cascade_queries": movement.get("cascade_queries", []),
        "passes": [
            {
                "name": "Verify",
                "questions": strategy.get("first_principles_questions", [])[:3],
                "actions": [
                    "Find primary public source.",
                    "Find one independent corroborating public source.",
                    "Record uncertainty and disconfirming evidence.",
                ],
            },
            {
                "name": "Connect",
                "questions": [
                    "Which adjacent ideas, companies, papers, and repos rhyme with this?",
                    "What internal Dharma primitive already wants to receive this signal?",
                    "Where does this affect strategic vision, not just task backlog?",
                ],
                "actions": strategy.get("adjacent_searches", [])[:5],
            },
            {
                "name": "Evolve",
                "questions": [
                    "What is the 10x stronger version of the pattern?",
                    "What governed prototype would prove or falsify it fastest?",
                    "What Shakti opportunity or draft proposal should exist next?",
                ],
                "actions": strategy.get("iteration_steps", [])[:10],
            },
        ],
        "next_gate": (
            "Promote only after two independent public sources, or operator drop "
            "plus concrete public evidence."
        ),
    }


def render_incubation_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# World Signal Incubation: {payload.get('title', '')}",
        "",
        f"Status: {payload.get('status')} | Score: {payload.get('score')}",
        f"Movement: {payload.get('movement_id')}",
        "",
    ]
    for pass_row in payload.get("passes", []):
        lines.append(f"## {pass_row.get('name')}")
        for question in pass_row.get("questions", []):
            lines.append(f"- Q: {question}")
        for action in pass_row.get("actions", []):
            lines.append(f"- Step: {action}")
        lines.append("")
    lines.append(f"Next gate: {payload.get('next_gate')}")
    return "\n".join(lines).rstrip() + "\n"


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value[:64] or "world-signal"
