"""Bounded read-only Mission Control snapshot provider."""

from __future__ import annotations

from typing import Any

from dharma_swarm.mission_control_contract import (
    MissionControlError,
    MissionSnapshot,
    public_mission_identifier,
)


class ConfiguredMissionSnapshotProvider:
    """Expose one configured Mission Control read without mutation methods.

    The embedding owner API supplies an existing :class:`MissionControl` (or
    another object implementing its async ``get_snapshot`` read). This adapter
    neither opens owner storage nor discovers missions, and an ID mismatch is
    rejected before the canonical reader is invoked.
    """

    runtime_projection_mode = "owner_supplied_read_only"

    def __init__(self, owner_reader: Any, *, mission_id: str) -> None:
        reader = getattr(owner_reader, "get_snapshot", None)
        if not callable(reader):
            raise MissionControlError("owner reader must provide get_snapshot")
        self._get_snapshot = reader
        self._configured_mission_id = public_mission_identifier(mission_id)

    @property
    def configured_mission_id(self) -> str:
        return self._configured_mission_id

    async def get_snapshot(self, mission_id: str) -> MissionSnapshot | None:
        requested = public_mission_identifier(mission_id)
        if requested != self._configured_mission_id:
            raise MissionControlError("requested mission is not configured")
        snapshot = self._get_snapshot(requested)
        if not hasattr(snapshot, "__await__"):
            raise MissionControlError("owner get_snapshot must be asynchronous")
        return await snapshot


__all__ = ["ConfiguredMissionSnapshotProvider"]
