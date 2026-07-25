"""Thin gateway status helper; does not start daemons."""

from __future__ import annotations


def gateway_status() -> dict[str, object]:
    return {"schema_version": "dharma.holon_system.gateway_status.v1", "wake_loop_active": False}


__all__ = ["gateway_status"]
