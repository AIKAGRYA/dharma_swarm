"""Markdown rendering for MemoryKernel context safety eval reports."""

from __future__ import annotations

from dharma_swarm.memory_kernel.context_eval import ContextEvalReport


def render_context_eval_markdown(report: ContextEvalReport) -> str:
    lines = [
        "# Memory Context Safety Eval",
        "",
        "This is a shadow-mode safety eval. It does not inject prompts or write retrieval feedback.",
        "",
        "## Summary",
        "",
        f"- Hard failures: `{report.hard_failure_count}`",
        f"- Warnings: `{report.warning_count}`",
        "",
    ]
    if report.current_context:
        current = report.current_context
        lines.extend(
            [
                "## Current Context Lane",
                "",
                f"- Source: `{current.source}`",
                f"- Characters: `{current.char_count}`",
                f"- Lines: `{current.line_count}`",
                f"- Findings: `{current.finding_count}`",
                "",
            ]
        )
        if current.redacted_preview:
            lines.append(f"- Redacted preview: `{current.redacted_preview}`")
            lines.append("")
    if report.memory_kernel:
        memory = report.memory_kernel
        lines.extend(
            [
                "## MemoryKernel Lane",
                "",
                f"- Atoms: `{memory.atom_count}`",
                f"- Candidates: `{memory.pack.candidate_count}`",
                f"- Admitted: `{memory.pack.admitted_count}`",
                f"- Omitted: `{memory.pack.omitted_count}`",
                f"- Hard failures: `{memory.hard_failure_count}`",
                "",
            ]
        )
    findings = []
    if report.current_context:
        findings.extend(report.current_context.findings)
    if report.memory_kernel:
        findings.extend(report.memory_kernel.findings)
    if findings:
        lines.extend(["## Findings", ""])
        for finding in findings[:40]:
            lines.append(
                f"- `{finding.lane.value}` `{finding.severity.value}` "
                f"`{finding.kind}` count=`{finding.occurrence_count}` "
                f"reason={finding.reason}"
            )
        if len(findings) > 40:
            lines.append(f"- finding list truncated: `{len(findings) - 40}`")
        lines.append("")
    if report.warnings:
        lines.extend(["## Harness Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- `{warning}`")
        lines.append("")
    return "\n".join(lines)
