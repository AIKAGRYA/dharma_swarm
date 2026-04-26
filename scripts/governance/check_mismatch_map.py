"""Mismatch-map drift checker.

Parse `INTERFACE_MISMATCH_MAP.md`, extract every `file.py:LINE` citation,
and verify the cited file (and where possible, the cited line) still
exists. The map only stays useful if its references stay current; when
code moves or is deleted, the map's claim degrades from "this is the
exact spot of the mismatch" to "the mismatch was somewhere here, once."

What this gate fails on:
- A cited file no longer exists in the repo.
- A cited line is past the file's current end-of-file.

What this gate does NOT do:
- Verify the cited code still says the same thing (would require the
  map to embed the snippet, which it sometimes does and sometimes
  doesn't).
- Verify resolved mismatches were actually resolved (the map text
  records this in prose).

Usage:
    python3 scripts/governance/check_mismatch_map.py

Exit codes:
    0 — no drift detected
    1 — at least one drifted citation
    2 — map file itself is missing
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAP_PATH = REPO_ROOT / "INTERFACE_MISMATCH_MAP.md"

# Citations are like `module.py:LINE` or `path/to/module.py:LINE`.
# Allow up to one trailing `–LINE` for ranges (e.g., `file.py:51-52`).
CITATION = re.compile(
    r"`([a-zA-Z_][a-zA-Z0-9_/\-\.]*\.py):(\d+)(?:[-–](\d+))?`"
)

# Skip citations that match these well-known external-dep patterns.
EXTERNAL_DEP_PATTERN = re.compile(
    r"^(huggingface_hub|anthropic|openai|ollama|pydantic|fastapi|"
    r"sqlalchemy|pytest|hypothesis)\.py$"
)

# A few module names referenced in the map exist as relative paths
# (e.g., "swarm.py" really means "dharma_swarm/swarm.py"). Map these
# bare names to their canonical absolute paths within the repo.
BARE_MODULE_HINTS = {
    "swarm.py": "dharma_swarm/swarm.py",
    "orchestrate_live.py": "dharma_swarm/orchestrate_live.py",
    "orchestrator.py": "dharma_swarm/orchestrator.py",
    "tiny_router_shadow.py": "dharma_swarm/tiny_router_shadow.py",
    "persistent_agent.py": "dharma_swarm/persistent_agent.py",
    "message_bus.py": "dharma_swarm/message_bus.py",
    "organism.py": "dharma_swarm/organism.py",
    "auto_proposer.py": "dharma_swarm/auto_proposer.py",
    "evolution.py": "dharma_swarm/evolution.py",
    "memory.py": "dharma_swarm/memory.py",
    "witness.py": "dharma_swarm/witness.py",
    "subconscious.py": "dharma_swarm/subconscious.py",
    "shakti.py": "dharma_swarm/shakti.py",
    "agent_runner.py": "dharma_swarm/agent_runner.py",
    "neural_consolidator.py": "dharma_swarm/neural_consolidator.py",
    "thinkodynamic_director.py": "dharma_swarm/thinkodynamic_director.py",
    "replication_protocol.py": "dharma_swarm/replication_protocol.py",
    "conductors.py": "dharma_swarm/conductors.py",
    "router_v1.py": "dharma_swarm/router_v1.py",
    "meta_evolution.py": "dharma_swarm/meta_evolution.py",
    "engine/conversation_memory.py": "dharma_swarm/engine/conversation_memory.py",
}


def file_line_count(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def resolve_citation(raw_path: str) -> Path | None:
    """Map a citation path to an absolute file in the repo, or None
    if the path looks like an external dep that's not a real file."""
    if EXTERNAL_DEP_PATTERN.match(raw_path):
        return None
    if raw_path in BARE_MODULE_HINTS:
        return REPO_ROOT / BARE_MODULE_HINTS[raw_path]
    candidate = REPO_ROOT / raw_path
    if candidate.exists():
        return candidate
    # Try `dharma_swarm/{raw_path}` as a fallback.
    fallback = REPO_ROOT / "dharma_swarm" / raw_path
    if fallback.exists():
        return fallback
    return candidate  # Will fail existence check downstream.


def main() -> int:
    if not MAP_PATH.exists():
        print(f"::error::INTERFACE_MISMATCH_MAP.md not found at {MAP_PATH}",
              file=sys.stderr)
        return 2

    text = MAP_PATH.read_text(encoding="utf-8")

    seen: set[tuple[str, int]] = set()
    drifted_missing: list[str] = []
    drifted_past_eof: list[str] = []
    skipped_external: set[str] = set()
    checked = 0

    for m in CITATION.finditer(text):
        raw_path = m.group(1)
        start_line = int(m.group(2))
        end_line = int(m.group(3)) if m.group(3) else start_line

        if EXTERNAL_DEP_PATTERN.match(raw_path):
            skipped_external.add(raw_path)
            continue

        key = (raw_path, start_line)
        if key in seen:
            continue
        seen.add(key)

        resolved = resolve_citation(raw_path)
        if resolved is None:
            continue
        checked += 1

        if not resolved.exists():
            drifted_missing.append(
                f"  {raw_path}:{start_line}  →  {resolved} does not exist"
            )
            continue

        line_count = file_line_count(resolved)
        if end_line > line_count:
            drifted_past_eof.append(
                f"  {raw_path}:{start_line}-{end_line}  →  "
                f"{resolved.relative_to(REPO_ROOT)} only has {line_count} lines"
            )

    print("Mismatch-map drift check")
    print("-" * 60)
    print(f"  Citations parsed:           {checked}")
    print(f"  External deps skipped:      {len(skipped_external)} "
          f"({', '.join(sorted(skipped_external))})")
    print(f"  Drifted (missing file):     {len(drifted_missing)}")
    print(f"  Drifted (line past EOF):    {len(drifted_past_eof)}")
    print()

    if drifted_missing:
        print("Citations whose file no longer exists:")
        for d in drifted_missing:
            print(d)
        print()

    if drifted_past_eof:
        print("Citations whose line is past EOF (file shrank or moved):")
        for d in drifted_past_eof:
            print(d)
        print()

    if drifted_missing or drifted_past_eof:
        print("::error::Mismatch-map drift detected.")
        print("Either fix the cited code path, update the map entry,")
        print("or mark the entry RESOLVED and remove its citation.")
        return 1

    print("No drift detected. Map references are current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
