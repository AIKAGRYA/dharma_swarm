"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchChatStatus, fetchHealth, fetchRuntimeGraph } from "@/lib/api";
import {
  buildRuntimeControlPlaneSnapshot,
  normalizeRuntimeControlPlaneResponses,
  type RuntimeControlPlaneData,
} from "@/lib/runtimeControlPlane";

const DEFAULT_REFRESH_INTERVAL_MS = 30_000;

async function loadRuntimeControlPlane(): Promise<RuntimeControlPlaneData> {
  const [chatResponse, healthResponse, runtimeGraphResponse] = await Promise.all([
    fetchChatStatus(),
    fetchHealth(),
    fetchRuntimeGraph({ limit: 20, receipt_limit: 50 }),
  ]);
  return normalizeRuntimeControlPlaneResponses(
    chatResponse,
    healthResponse,
    runtimeGraphResponse,
  );
}

export function useRuntimeControlPlane(options?: { refetchInterval?: number }) {
  const query = useQuery<RuntimeControlPlaneData>({
    queryKey: ["runtime-control-plane"],
    queryFn: loadRuntimeControlPlane,
    refetchInterval: options?.refetchInterval ?? DEFAULT_REFRESH_INTERVAL_MS,
  });

  const data = query.data ?? {
    chatStatus: null,
    health: null,
    runtimeGraph: null,
    chatError: null,
    healthError: null,
    runtimeGraphError: null,
    error: null,
  };
  const error =
    data.error ??
    (query.error instanceof Error ? query.error.message : query.error ? String(query.error) : null);

  return {
    ...query,
    chatStatus: data.chatStatus,
    health: data.health,
    runtimeGraph: data.runtimeGraph,
    runtimeGraphError: data.runtimeGraphError,
    error,
    snapshot: buildRuntimeControlPlaneSnapshot({
      chatStatus: data.chatStatus,
      health: data.health,
      runtimeGraph: data.runtimeGraph,
      chatError: data.chatError,
      healthError: data.healthError,
      runtimeGraphError: data.runtimeGraphError,
      error,
    }),
    refresh: query.refetch,
  };
}
