"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  ControlSurfaceEnvelope,
  ControlSurfaceSourceError,
  MissionSnapshotProjection,
} from "@/lib/types";

const MISSION_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/;

function assertMissionProjection(
  envelope: ControlSurfaceEnvelope<MissionSnapshotProjection>,
  missionId: string,
): MissionSnapshotProjection {
  const projection = envelope?.data;
  if (
    !projection ||
    projection.schema_version !== "dharma.control_surface.mission_snapshot_projection.v1" ||
    projection.mission_id !== missionId ||
    projection.authority !== "TaskBoard+RuntimeStateStore" ||
    projection.proves_executor_liveness !== false ||
    projection.simulation !== false
  ) {
    throw new Error("Mission projection failed its typed claim boundary");
  }
  if (projection.state === "observed") {
    const snapshot = projection.snapshot;
    if (
      !snapshot ||
      snapshot.mission.mission_id !== missionId ||
      snapshot.authority !== "TaskBoard+RuntimeStateStore" ||
      snapshot.proves_executor_liveness !== false
    ) {
      throw new Error("Observed mission snapshot failed its authority boundary");
    }
  } else if (projection.snapshot !== null) {
    throw new Error("Unobserved mission projection carried a snapshot");
  }
  return projection;
}

export function isMissionIdentifier(value: string): boolean {
  return MISSION_ID_PATTERN.test(value);
}

export function useMissionControl(missionId: string, queryEnabled = true) {
  const enabled = queryEnabled && isMissionIdentifier(missionId);
  const query = useQuery<ControlSurfaceEnvelope<MissionSnapshotProjection>>({
    queryKey: ["mission-control-snapshot", missionId],
    enabled,
    queryFn: async () => {
      const envelope = await apiFetch<ControlSurfaceEnvelope<MissionSnapshotProjection>>(
        `/api/control-surface/missions/${encodeURIComponent(missionId)}/snapshot`,
      );
      assertMissionProjection(envelope, missionId);
      return envelope;
    },
    refetchInterval: 15_000,
  });

  return {
    projection: query.data?.data ?? null,
    sourceErrors: (query.data?.source_errors ?? []) as ControlSurfaceSourceError[],
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
    enabled,
  };
}
