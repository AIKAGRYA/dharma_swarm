"""Structured tool-exposure detection for MemoryKernel context admission."""

from __future__ import annotations

from dharma_swarm.memory_kernel.atoms import MemoryAtom


_TOOL_EXPOSURE_KEYS = {
    "available_tools",
    "denial_reasons",
    "late_bound_tools",
    "requested_tools",
    "tool_call",
    "tool_calls",
    "tool_plan",
    "tool_registry",
    "tool_request",
    "tool_result",
    "tool_results",
    "tool_schema",
    "tool_schemas",
    "tools",
    "visible_tools",
}
_TOOL_EXPOSURE_FLAGS = {
    "contains_tool_exposure",
    "contains_tool_plan",
    "exposes_tools",
    "tool_exposure",
}


def has_tool_exposure(atom: MemoryAtom) -> bool:
    return _metadata_has_tool_exposure(atom.metadata)


def _metadata_has_tool_exposure(value: object) -> bool:
    if isinstance(value, dict):
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip().lower()
            if key in _TOOL_EXPOSURE_KEYS:
                return True
            if key in _TOOL_EXPOSURE_FLAGS and _truthy_metadata_value(raw_value):
                return True
            if _metadata_has_tool_exposure(raw_value):
                return True
    elif isinstance(value, (list, tuple, set)):
        return any(_metadata_has_tool_exposure(item) for item in value)
    return False


def _truthy_metadata_value(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "none", "off"}
    return bool(value)
