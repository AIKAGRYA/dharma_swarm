"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiPath } from "@/lib/api";
import type {
  A2ASendCardsPayload,
  AgentOpsCardsPayload,
  ControlSurfaceEnvelope,
  ControlSurfaceRow,
  ControlSurfaceSummary,
  DsGoalCardsPayload,
  SemanticReceiptCardsPayload,
} from "@/lib/types";

export type { ControlSurfaceRow, ControlSurfaceSummary };

const CONTROL_SURFACE_ROWS_QUERY_KEY = ["control-surface-rows"] as const;

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

function useControlSurfaceRowsStream(enabled = true) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }

    const source = new EventSource(apiPath("/api/control-surface/stream"));
    source.onmessage = (event) => {
      try {
        const rows = JSON.parse(event.data) as ControlSurfaceRow[];
        if (Array.isArray(rows)) {
          queryClient.setQueryData(CONTROL_SURFACE_ROWS_QUERY_KEY, rows);
        }
      } catch {
        // Malformed stream payloads should not break the cockpit; polling remains active.
      }
    };
    source.onerror = () => {
      // Keep polling as the compatibility path when SSE is unavailable or unauthorized.
      source.close();
    };

    return () => source.close();
  }, [enabled, queryClient]);
}

export function useControlSurfaceRows() {
  const { data, isLoading, error, refetch } = useQuery<ControlSurfaceRow[]>({
    queryKey: CONTROL_SURFACE_ROWS_QUERY_KEY,
    queryFn: async () => {
      const payload = await apiFetch<
        ControlSurfaceRow[] | ControlSurfaceEnvelope<ControlSurfaceRow[]>
      >("/api/control-surface/rows");
      return unwrapControlSurfaceEnvelope(payload);
    },
    refetchInterval: 15_000,
  });
  useControlSurfaceRowsStream(true);

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
