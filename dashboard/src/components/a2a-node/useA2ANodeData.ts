"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchNodeAgents,
  fetchNodeCards,
  fetchNodeTasks,
  fetchNodeTraces,
  type A2ANodeAgent,
  type A2ANodeCardsPayload,
  type A2ANodeTask,
  type A2ANodeTrace,
} from "./a2aNodeReadModel";

const PROXY_BASE = "/dashboard/a2a-node/api/";

export function useA2ANodeAgents() {
  const query = useQuery<A2ANodeAgent[]>({
    queryKey: ["a2a-node", "agents"],
    queryFn: () =>
      fetchNodeAgents({
        url: `${PROXY_BASE}agents`,
      }),
    refetchInterval: 5_000,
  });
  return {
    agents: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    dataUpdatedAt: query.dataUpdatedAt,
  };
}

export function useA2ANodeTasks() {
  const query = useQuery<A2ANodeTask[]>({
    queryKey: ["a2a-node", "tasks"],
    queryFn: () =>
      fetchNodeTasks({
        url: `${PROXY_BASE}tasks`,
      }),
    refetchInterval: 5_000,
  });
  return {
    tasks: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    dataUpdatedAt: query.dataUpdatedAt,
  };
}

export function useA2ANodeTraces() {
  const query = useQuery<A2ANodeTrace[]>({
    queryKey: ["a2a-node", "traces", 48],
    queryFn: () =>
      fetchNodeTraces({
        url: `${PROXY_BASE}traces?limit=48`,
      }),
    refetchInterval: 5_000,
  });
  return {
    traces: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    dataUpdatedAt: query.dataUpdatedAt,
  };
}

export function useA2ANodeCards() {
  const query = useQuery<A2ANodeCardsPayload>({
    queryKey: ["a2a-node", "a2a-cards", 48],
    queryFn: () =>
      fetchNodeCards({
        url: `${PROXY_BASE}a2a/cards?limit=48`,
      }),
    refetchInterval: 30_000,
  });
  return {
    payload: query.data ?? null,
    cards: query.data?.cards ?? [],
    partial: query.data?.partial ?? null,
    isLoading: query.isLoading,
    error: query.error,
    dataUpdatedAt: query.dataUpdatedAt,
  };
}
