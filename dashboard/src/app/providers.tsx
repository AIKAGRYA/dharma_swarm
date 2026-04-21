"use client";

/**
 * DHARMA COMMAND -- Client-side providers wrapper.
 * Wraps children in TanStack QueryClientProvider.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { consumeDesktopShellBootstrapHash } from "@/lib/auth";

export function Providers({ children }: { children: ReactNode }) {
  consumeDesktopShellBootstrapHash();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 10_000,
            refetchInterval: 30_000,
            retry: 2,
            refetchOnWindowFocus: true,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
