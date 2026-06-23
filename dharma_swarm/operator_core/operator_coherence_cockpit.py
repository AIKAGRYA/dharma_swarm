"""Compatibility shim for the Operator Coherence Cockpit projection.

The implementation lives in :mod:`dharma_swarm.operator_core.operator_coherence`
so each module stays inside the Rule 10 line budget.
"""

from __future__ import annotations

from dharma_swarm.operator_core.operator_coherence import (
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_REPO_ROOT,
    build_operator_coherence_cockpit,
    render_markdown_report,
    write_operator_coherence_outputs,
)

__all__ = [
    "DEFAULT_JSON_OUTPUT",
    "DEFAULT_MARKDOWN_OUTPUT",
    "DEFAULT_REPO_ROOT",
    "build_operator_coherence_cockpit",
    "render_markdown_report",
    "write_operator_coherence_outputs",
]
