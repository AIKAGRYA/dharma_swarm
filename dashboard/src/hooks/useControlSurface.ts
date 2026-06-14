"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  A2ASendCardsPayload,
  ActiveTrackPortfolioPayload,
  AgentOpsCardsPayload,
  ControlSurfaceEnvelope,
  ControlSurfaceRow,
  ControlSurfaceSummary,
  DsGoalCardsPayload,
  SemanticReceiptCardsPayload,
} from "@/lib/types";

export type { ControlSurfaceRow, ControlSurfaceSummary };

function unwrapControlSurfaceEnvelope<T>(payload: T | ControlSurfaceEnvelope<T>): T {
  if (
    payload &&
    typeof payload === "object" &&
    "data" in payload &&
    "schema_version" in payload
  ) {
    return (payload as ControlSurfaceEnvelope<T>).data;
  }
  return payload as T;
}

export function useControlSurfaceRows() {
  const { data, isLoading, error, refetch } = useQuery<ControlSurfaceRow[]>({
    queryKey: ["control-surface-rows"],
    queryFn: async () => {
      const payload = await apiFetch<
        ControlSurfaceRow[] | ControlSurfaceEnvelope<ControlSurfaceRow[]>
      >("/api/control-surface/rows");
      return unwrapControlSurfaceEnvelope(payload);
    },
    refetchInterval: 15_000,
  });

  return {
    rows: data ?? [],
    isLoading,
    error,
    refetch,
  };
}

export function useControlSurfaceSummary() {
  const { data, isLoading, error } = useQuery<ControlSurfaceSummary>({
    queryKey: ["control-surface-summary"],
    queryFn: async () => {
      const payload = await apiFetch<
        ControlSurfaceSummary | ControlSurfaceEnvelope<ControlSurfaceSummary>
      >("/api/control-surface/summary");
      return unwrapControlSurfaceEnvelope(payload);
    },
    refetchInterval: 15_000,
  });

  return {
    summary: data ?? null,
    isLoading,
    error,
  };
}

export function useDsGoalCards(missionId = "") {
  const query = missionId
    ? `/api/control-surface/ds-goal/cards?mission_id=${encodeURIComponent(missionId)}`
    : "/api/control-surface/ds-goal/cards";
  const { data, isLoading, error, refetch } = useQuery<DsGoalCardsPayload>({
    queryKey: ["control-surface-ds-goal-cards", missionId],
    queryFn: async () => {
      const payload = await apiFetch<
        DsGoalCardsPayload | ControlSurfaceEnvelope<DsGoalCardsPayload>
      >(query);
      return unwrapControlSurfaceEnvelope(payload);
    },
    refetchInterval: 15_000,
  });

  return {
    payload: data ?? null,
    cards: data?.cards ?? [],
    isLoading,
    error,
    refetch,
  };
}

export function useAgentOpsCards(packetId = "", limit = 12) {
  const params = new URLSearchParams();
  if (packetId) {
    params.set("packet_id", packetId);
  }
  if (limit > 0) {
    params.set("limit", String(limit));
  }
  const query = `/api/control-surface/agentops/cards${params.toString() ? `?${params}` : ""}`;
  const { data, isLoading, error, refetch } = useQuery<AgentOpsCardsPayload>({
    queryKey: ["control-surface-agentops-cards", packetId, limit],
    queryFn: async () => {
      const payload = await apiFetch<
        AgentOpsCardsPayload | ControlSurfaceEnvelope<AgentOpsCardsPayload>
      >(query);
      return unwrapControlSurfaceEnvelope(payload);
    },
    refetchInterval: 30_000,
  });

  return {
    payload: data ?? null,
    cards: data?.cards ?? [],
    isLoading,
    error,
    refetch,
  };
}

export function useA2ASendCards(target = "", limit = 12) {
  const params = new URLSearchParams();
  if (target) {
    params.set("target", target);
  }
  if (limit > 0) {
    params.set("limit", String(limit));
  }
  const query = `/api/control-surface/a2a/cards${params.toString() ? `?${params}` : ""}`;
  const { data, isLoading, error, refetch } = useQuery<A2ASendCardsPayload>({
    queryKey: ["control-surface-a2a-cards", target, limit],
    queryFn: async () => {
      const payload = await apiFetch<
        A2ASendCardsPayload | ControlSurfaceEnvelope<A2ASendCardsPayload>
      >(query);
      return unwrapControlSurfaceEnvelope(payload);
    },
    refetchInterval: 30_000,
  });

  return {
    payload: data ?? null,
    cards: data?.cards ?? [],
    isLoading,
    error,
    refetch,
  };
}

export function useSemanticReceiptCards(model = "", verdict = "", limit = 12) {
  const params = new URLSearchParams();
  if (model) {
    params.set("model", model);
  }
  if (verdict) {
    params.set("verdict", verdict);
  }
  if (limit > 0) {
    params.set("limit", String(limit));
  }
  const query = `/api/control-surface/semantic-receipts/cards${params.toString() ? `?${params}` : ""}`;
  const { data, isLoading, error, refetch } = useQuery<SemanticReceiptCardsPayload>({
    queryKey: ["control-surface-semantic-receipt-cards", model, verdict, limit],
    queryFn: async () => {
      const payload = await apiFetch<
        SemanticReceiptCardsPayload | ControlSurfaceEnvelope<SemanticReceiptCardsPayload>
      >(query);
      return unwrapControlSurfaceEnvelope(payload);
    },
    refetchInterval: 30_000,
  });

  return {
    payload: data ?? null,
    cards: data?.cards ?? [],
    isLoading,
    error,
    refetch,
  };
}

export function useActiveTrackPortfolio() {
  const { data, isLoading, error, refetch } = useQuery<ActiveTrackPortfolioPayload>({
    queryKey: ["control-surface-active-tracks"],
    queryFn: async () => {
      const payload = await apiFetch<
        ActiveTrackPortfolioPayload | ControlSurfaceEnvelope<ActiveTrackPortfolioPayload>
      >("/api/control-surface/active-tracks");
      return unwrapControlSurfaceEnvelope(payload);
    },
    refetchInterval: 30_000,
  });

  return {
    portfolio: data ?? null,
    slots: data?.slots ?? [],
    isLoading,
    error,
    refetch,
  };
}
