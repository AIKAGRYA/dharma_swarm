import type { NextConfig } from "next";
import path from "path";

import { dashboardProxyRewrites } from "./src/lib/dashboardProxy";

const apiProxyTarget =
  process.env.DHARMA_API_PROXY_URL ?? "http://127.0.0.1:8420";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
  async rewrites() {
    return dashboardProxyRewrites(apiProxyTarget);
  },
};

export default nextConfig;
