"""Operator Coherence Cockpit read-model package."""

from .base import DEFAULT_JSON_OUTPUT, DEFAULT_MARKDOWN_OUTPUT, DEFAULT_REPO_ROOT
from .report import (
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
