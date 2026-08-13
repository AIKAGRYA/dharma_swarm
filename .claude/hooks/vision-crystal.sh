#!/bin/bash
# SessionStart hook: inject the VISION_TRANSMISSION crystal (T0, ~200 tokens)
# as session context — operator ruling 2026-08-13: injection is context, not a
# sixth first-read surface. Degrades silently when the artifact, python3, or
# the tier anchors are missing; never fails the session.
set -u

DOC="${CLAUDE_PROJECT_DIR:-.}/docs/vision_maps/VISION_TRANSMISSION.md"
[ -f "$DOC" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

python3 - "$DOC" <<'PY' 2>/dev/null || true
import json, re, sys

text = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"<!-- TIER:T0:BEGIN -->\n(.*?)<!-- TIER:T0:END -->", text, re.S)
if m:
    crystal = m.group(1).strip()
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "[VISION CRYSTAL — dharma_swarm T0 · unratified projection; "
                "owners win · full tier: make vision]\n" + crystal
            ),
        }
    }))
PY
exit 0
