import assert from "node:assert/strict";
import test from "node:test";

import { dashboardProxyRewrites } from "./dashboardProxy";

test("dashboard proxies HTTP and WebSocket paths to the canonical API", () => {
  assert.deepEqual(dashboardProxyRewrites("http://127.0.0.1:8420/"), [
    {
      source: "/api/:path*",
      destination: "http://127.0.0.1:8420/api/:path*",
    },
    {
      source: "/ws/:path*",
      destination: "http://127.0.0.1:8420/ws/:path*",
    },
  ]);
});
