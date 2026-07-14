"use client";

import { useCallback, useSyncExternalStore } from "react";
import {
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";

const EVIDENCE_QUERY_KEYS: readonly QueryKey[] = [
  ["fleet-nodes"],
  ["agents"],
  ["tasks"],
  ["traces", 48],
  ["control-surface-a2a-cards", "", 48],
];

function sameQueryKey(left: QueryKey, right: QueryKey): boolean {
  return (
    left.length === right.length &&
    left.every((value, index) => Object.is(value, right[index]))
  );
}

function isEvidenceQuery(queryKey: QueryKey): boolean {
  return EVIDENCE_QUERY_KEYS.some((candidate) =>
    sameQueryKey(candidate, queryKey),
  );
}

function latestEvidenceUpdate(queryClient: QueryClient): number {
  return EVIDENCE_QUERY_KEYS.reduce(
    (latest, queryKey) =>
      Math.max(
        latest,
        queryClient.getQueryState(queryKey)?.dataUpdatedAt ?? 0,
      ),
    0,
  );
}

function serverSnapshot(): number {
  return 0;
}

export function useEvidenceDataUpdatedAt(): number {
  const queryClient = useQueryClient();
  const subscribe = useCallback(
    (notify: () => void) =>
      queryClient.getQueryCache().subscribe((event) => {
        if (isEvidenceQuery(event.query.queryKey)) {
          notify();
        }
      }),
    [queryClient],
  );
  const getSnapshot = useCallback(
    () => latestEvidenceUpdate(queryClient),
    [queryClient],
  );
  return useSyncExternalStore(subscribe, getSnapshot, serverSnapshot);
}
