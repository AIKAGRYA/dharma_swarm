"use client";

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiPath, enqueueInteropTask, fetchInteropStatus } from "@/lib/api";
import { readDashboardApiToken } from "@/lib/auth";
import type { ApiResponse, InteropStatusOut, InteropTaskOut } from "@/lib/types";

export const interopStatusQueryKey = ["interop", "status"] as const;

function unwrapStatus(response: ApiResponse<InteropStatusOut>): InteropStatusOut {
  if (response.status === "error") {
    throw new Error(response.error || "Failed to load interop status");
  }
  return response.data;
}

export function useInterop() {
  const queryClient = useQueryClient();

  const statusQuery = useQuery<InteropStatusOut>({
    queryKey: interopStatusQueryKey,
    queryFn: async () => unwrapStatus(await fetchInteropStatus()),
    refetchInterval: 10_000,
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const token = readDashboardApiToken();
    const streamPath = token
      ? `/api/interop/stream?token=${encodeURIComponent(token)}`
      : "/api/interop/stream";
    const stream = new EventSource(apiPath(streamPath));

    const handleInteropEvent = () => {
      void queryClient.invalidateQueries({ queryKey: ["interop"] });
    };

    stream.addEventListener("interop", handleInteropEvent);
    stream.onerror = () => {
      void queryClient.invalidateQueries({ queryKey: ["interop"] });
    };

    return () => {
      stream.removeEventListener("interop", handleInteropEvent);
      stream.close();
    };
  }, [queryClient]);

  const enqueueMutation = useMutation<
    ApiResponse<InteropTaskOut>,
    Error,
    Parameters<typeof enqueueInteropTask>[0]
  >({
    mutationFn: enqueueInteropTask,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["interop"] });
    },
  });

  const status = statusQuery.data;

  return {
    status,
    adapters: status?.adapters ?? [],
    workers: status?.workers ?? [],
    tasks: status?.recent_tasks ?? [],
    events: status?.recent_events ?? [],
    mailboxCounts: status?.mailbox_counts ?? {},
    isLoading: statusQuery.isLoading,
    error: statusQuery.error,
    enqueueTask: enqueueMutation.mutateAsync,
    isEnqueuing: enqueueMutation.isPending,
  };
}
