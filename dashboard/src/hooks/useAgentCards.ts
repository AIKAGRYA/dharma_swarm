"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { AgentCardIndexPayload, AgentCardOut } from "@/lib/types";

export function useAgentCards() {
  const { data, isLoading, error, refetch, isFetching } =
    useQuery<AgentCardIndexPayload>({
      queryKey: ["agent-cards"],
      queryFn: () => apiFetch<AgentCardIndexPayload>("/api/agent-cards"),
      refetchInterval: 15_000,
    });

  return {
    agents: data?.agents ?? [],
    summary: data?.summary ?? null,
    isLoading,
    isFetching,
    error,
    refetch,
  };
}

export function useAgentCard(agentUid: string | null) {
  const { data, isLoading, error, refetch, isFetching } = useQuery<AgentCardOut>({
    queryKey: ["agent-card", agentUid],
    queryFn: () =>
      apiFetch<AgentCardOut>(
        `/api/agent-cards/${encodeURIComponent(agentUid ?? "")}`,
      ),
    enabled: Boolean(agentUid),
    refetchInterval: 15_000,
  });

  return {
    agent: data ?? null,
    isLoading,
    isFetching,
    error,
    refetch,
  };
}
