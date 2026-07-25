export interface DashboardProxyRewrite {
  source: string;
  destination: string;
}

export function dashboardProxyRewrites(
  apiProxyTarget: string,
): DashboardProxyRewrite[] {
  const target = apiProxyTarget.replace(/\/+$/, "");
  return [
    {
      source: "/api/:path*",
      destination: `${target}/api/:path*`,
    },
    {
      source: "/ws/:path*",
      destination: `${target}/ws/:path*`,
    },
  ];
}
