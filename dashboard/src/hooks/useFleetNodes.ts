"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchRawFleetNodes,
  type FleetNodesResponse,
} from "@/components/a2a-node/a2aNodeFleet";
import {
  apiPath,
} from "@/lib/api";

export function useFleetNodes() {
  const query = useQuery<FleetNodesResponse>({
    queryKey: ["fleet-nodes"],
    queryFn: () =>
      fetchRawFleetNodes({ url: apiPath("/api/fleet/nodes") }),
    refetchInterval: 15_000,
  });

  return {
    nodes: query.data?.nodes ?? [],
    count: query.data?.count ?? 0,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    dataUpdatedAt: query.dataUpdatedAt,
    refetch: query.refetch,
  };
}
