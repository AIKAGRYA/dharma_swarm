"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchChatStatus,
  fetchHealth,
  fetchRuntimeAssistants,
  fetchRuntimeBackgroundJobs,
  fetchRuntimeGraph,
  fetchRuntimeInterrupts,
} from "@/lib/api";
import {
  buildRuntimeControlPlaneSnapshot,
  normalizeRuntimeControlPlaneResponses,
  type RuntimeControlPlaneData,
} from "@/lib/runtimeControlPlane";

const DEFAULT_REFRESH_INTERVAL_MS = 30_000;

async function loadRuntimeControlPlane(): Promise<RuntimeControlPlaneData> {
  const [
    chatResponse,
    healthResponse,
    runtimeGraphResponse,
    runtimeInterruptResponse,
    runtimeAssistantsResponse,
    runtimeBackgroundJobsResponse,
  ] = await Promise.all([
    fetchChatStatus(),
    fetchHealth(),
    fetchRuntimeGraph({ limit: 20, receipt_limit: 50 }),
    fetchRuntimeInterrupts({ limit: 20 }),
    fetchRuntimeAssistants({ limit: 20 }),
    fetchRuntimeBackgroundJobs({ limit: 20 }),
  ]);
  return normalizeRuntimeControlPlaneResponses(
    chatResponse,
    healthResponse,
    runtimeGraphResponse,
    runtimeInterruptResponse,
    runtimeAssistantsResponse,
    runtimeBackgroundJobsResponse,
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
    runtimeInterrupts: null,
    runtimeAssistants: null,
    runtimeBackgroundJobs: null,
    chatError: null,
    healthError: null,
    runtimeGraphError: null,
    runtimeInterruptError: null,
    runtimeAssistantsError: null,
    runtimeBackgroundJobsError: null,
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
    runtimeInterrupts: data.runtimeInterrupts,
    runtimeAssistants: data.runtimeAssistants,
    runtimeBackgroundJobs: data.runtimeBackgroundJobs,
    runtimeGraphError: data.runtimeGraphError,
    runtimeInterruptError: data.runtimeInterruptError,
    runtimeAssistantsError: data.runtimeAssistantsError,
    runtimeBackgroundJobsError: data.runtimeBackgroundJobsError,
    error,
    snapshot: buildRuntimeControlPlaneSnapshot({
      chatStatus: data.chatStatus,
      health: data.health,
      runtimeGraph: data.runtimeGraph,
      runtimeInterrupts: data.runtimeInterrupts,
      runtimeAssistants: data.runtimeAssistants,
      runtimeBackgroundJobs: data.runtimeBackgroundJobs,
      chatError: data.chatError,
      healthError: data.healthError,
      runtimeGraphError: data.runtimeGraphError,
      runtimeInterruptError: data.runtimeInterruptError,
      runtimeAssistantsError: data.runtimeAssistantsError,
      runtimeBackgroundJobsError: data.runtimeBackgroundJobsError,
      error,
    }),
    refresh: query.refetch,
  };
}
