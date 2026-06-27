import type { NextConfig } from "next";
import path from "path";

const apiProxyTarget =
  process.env.DHARMA_API_PROXY_URL ?? "http://127.0.0.1:8420";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
      {
        source: "/holon/:path*",
        destination: `${apiProxyTarget}/holon/:path*`,
      },
    ];
  },
};

export default nextConfig;
