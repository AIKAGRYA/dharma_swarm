"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CreateTaskBody, TaskOut } from "@/lib/types";

export function useTasks() {
  const { data, isLoading, error } = useQuery<TaskOut[]>({
    queryKey: ["tasks"],
    queryFn: () => apiFetch<TaskOut[]>("/api/commands/tasks"),
    refetchInterval: 5_000,
  });

  return {
    tasks: data ?? [],
    isLoading,
    error,
  };
}

export function useCreateTask() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (body: CreateTaskBody) =>
      apiFetch<TaskOut>("/api/commands/task", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}
