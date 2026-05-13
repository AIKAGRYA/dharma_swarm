"""Agent Handoff Prompt Generation for the Control Surface.

Extracted from control_surface.py to keep the projection engine under
the 1000-line module budget (Rule 10).
"""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.operator_core.control_surface_models import (
    AgentHandoffPrompt,
    ControlSurfaceRow,
    _utc_now_iso,
)

_KIND_FIX_TEMPLATES: dict[str, str] = {
    "api_router": "Implement or fix the API router so it is registered and responds correctly.",
    "dashboard_page": "Create or repair the dashboard page so it renders the declared UI.",
    "agent_subsystem": "Wire the agent module so it can be dispatched by the orchestrator.",
    "broken_register": "Fix the root cause described in the broken register entry.",
    "feedback_loop": "Close the feedback loop so sense→act→evaluate→adapt completes.",
    "integration": "Connect the integration so the declared dependency is satisfied.",
    "runtime_store": "Ensure the runtime store is present and populated with the expected schema.",
    "organ": "Bring the organ into coherence with its declared boundary.",
}


def generate_handoff_prompt(
    row: ControlSurfaceRow,
    repo_root: Path | None = None,
) -> AgentHandoffPrompt:
    """Generate a scoped agent prompt for fixing a control surface row."""
    context_files: list[str] = []
    for ref in row.source_refs:
        if ref.kind in ("file", "go_module") and ref.path:
            context_files.append(ref.path)
    if row.owner_module:
        mod_path = row.owner_module.replace(".", "/")
        if not mod_path.endswith(".py"):
            mod_path += ".py"
        if mod_path not in context_files:
            context_files.append(mod_path)

    expected_tests: list[str] = []
    if row.owner_module:
        stem = Path(row.owner_module.replace(".", "/")).stem
        test_file = f"tests/test_{stem}.py"
        expected_tests.append(test_file)
    for ref in row.source_refs:
        if ref.kind == "file" and ref.path.startswith("tests/"):
            if ref.path not in expected_tests:
                expected_tests.append(ref.path)

    fix_type = _KIND_FIX_TEMPLATES.get(row.kind, "Bring this surface into coherence.")
    gap_desc = ", ".join(row.gap_codes) if row.gap_codes else "none detected"

    evidence_block = ""
    for ev in row.evidence[:10]:
        evidence_block += f"  - [{ev.kind}] {ev.source} (status={ev.status})\n"

    invariant = (
        f"The declared state is '{row.declared_state}' with desired state "
        f"'{row.desired_state}'. After your fix, the coherence_state must be "
        f"'bound' (declared == observed). Do not break other surfaces."
    )

    prompt_text = f"""## Agent Handoff: {row.label}

**Row ID:** {row.id}
**Kind:** {row.kind}
**Coherence:** {row.coherence_state}
**Priority:** {row.priority}
**Gap Codes:** {gap_desc}

### What needs to happen
{fix_type}

### Current Evidence
{evidence_block}
### Context Files (read these first)
{chr(10).join(f"- {f}" for f in context_files)}

### Expected Tests
{chr(10).join(f"- {t}" for t in expected_tests)}

### Invariant
{invariant}

### Anti-slop Gates
- No decorative changes. Every edit must trace to this ControlSurfaceRow.
- Commit messages must include [impact-checked].
- Run `pytest {' '.join(expected_tests)}` before committing.
"""

    return AgentHandoffPrompt(
        row_id=row.id,
        label=row.label,
        prompt_text=prompt_text.strip(),
        context_files=context_files,
        expected_tests=expected_tests,
        invariant=invariant,
        generated_at=_utc_now_iso(),
    )
