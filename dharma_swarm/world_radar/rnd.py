"""Three-pass R&D artifacts for incubating world signals."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_rnd_artifacts(
    movements: list[dict[str, Any]],
    *,
    output_dir: Path,
) -> list[Path]:
    """Write verify/connect/evolve Markdown and JSON artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for movement in movements:
        bundle = build_rnd_bundle(movement)
        slug = _slug(str(movement.get("title") or movement.get("movement_id") or "signal"))
        root = output_dir / f"{slug}-{bundle['incubation_id'][:8]}"
        root.mkdir(parents=True, exist_ok=True)
        for pass_name in ("verify", "connect", "evolve"):
            payload = bundle[pass_name]
            json_path = root / f"{pass_name}.json"
            md_path = root / f"{pass_name}.md"
            json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            md_path.write_text(_render_pass_markdown(payload), encoding="utf-8")
            written.extend([json_path, md_path])
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(manifest)
        movement.setdefault("strategic_vision", {})["incubation_path"] = str(root)
    return written


def build_rnd_bundle(movement: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic R&D instructions for one movement."""
    title = str(movement.get("title") or "Untitled world signal")
    movement_id = str(movement.get("movement_id") or "")
    seed = f"{movement_id}:{title}"
    strategy = dict(movement.get("strategic_vision") or {})
    signals = [row for row in movement.get("signals", []) if isinstance(row, dict)]
    evidence_urls = [str(row.get("url")) for row in signals if row.get("url")]
    llm_status = "not_requested"
    if os.environ.get("DHARMA_WORLD_RND_LLM") == "1":
        llm_status = "WAITING_MODEL: deterministic artifact written; runtime model synthesis is optional"
    return {
        "incubation_id": hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "movement_id": movement_id,
        "title": title,
        "status": movement.get("status", "incubating"),
        "score": movement.get("weighted_score", 0.0),
        "llm_status": llm_status,
        "verify": {
            "pass": "verify",
            "title": title,
            "questions": strategy.get("first_principles_questions", [])[:3],
            "evidence_urls": evidence_urls,
            "actions": [
                "Find primary public source.",
                "Find one independent corroborating public source.",
                "Record contradictions or missing evidence.",
                "Do not promote without the configured evidence threshold.",
            ],
        },
        "connect": {
            "pass": "connect",
            "title": title,
            "questions": [
                "Which adjacent companies, papers, repos, and communities rhyme with this?",
                "Which Dharma primitive should receive the signal?",
                "Does this change strategic vision or only create a task?",
            ],
            "actions": list(movement.get("cascade_queries", []))[:8],
        },
        "evolve": {
            "pass": "evolve",
            "title": title,
            "questions": [
                "What is the 10x stronger version of the observed pattern?",
                "What governed prototype would prove or falsify it fastest?",
                "What Shakti opportunity or proposal draft should exist next?",
            ],
            "actions": strategy.get("iteration_steps", [])[:10],
            "draft_proposal": {
                "domain": "ecosystem_scan",
                "artifact": "smallest governed prototype or research memo",
                "authority": "Shakti opportunity board; frontier loop remains execution authority",
            },
        },
    }


def _render_pass_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# {payload.get('pass', '').title()}: {payload.get('title', '')}", ""]
    urls = payload.get("evidence_urls") or []
    if urls:
        lines.append("Evidence:")
        lines.extend(f"- {url}" for url in urls)
        lines.append("")
    questions = payload.get("questions") or []
    if questions:
        lines.append("Questions:")
        lines.extend(f"- {question}" for question in questions)
        lines.append("")
    actions = payload.get("actions") or []
    if actions:
        lines.append("Actions:")
        lines.extend(f"- {action}" for action in actions)
        lines.append("")
    if payload.get("draft_proposal"):
        lines.append("Draft Proposal:")
        for key, value in payload["draft_proposal"].items():
            lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value[:64] or "world-signal"
