import { createHmac } from "node:crypto";

export const DASHBOARD_WS_SESSION_COOKIE = "dharma_ws_session";
export const DASHBOARD_WS_SESSION_CONTEXT = "dharma-dashboard-ws-session.v1";
export const DASHBOARD_WS_SESSION_TTL_SECONDS = 300;

export interface DashboardWebSocketSession {
  token: string;
  maxAge: number;
}

const LOOPBACK_HOSTNAMES = new Set(["127.0.0.1", "::1", "localhost"]);

function normalizedHostname(url: URL): string {
  const hostname = url.hostname.toLowerCase();
  return hostname.startsWith("[") && hostname.endsWith("]")
    ? hostname.slice(1, -1)
    : hostname;
}

export function isTrustedDashboardSessionRequest(
  host: string,
  origin: string,
): boolean {
  try {
    if (!host || !origin) return false;
    const parsed = new URL(origin);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
    return (
      parsed.host.toLowerCase() === host.toLowerCase() &&
      LOOPBACK_HOSTNAMES.has(normalizedHostname(parsed))
    );
  } catch {
    return false;
  }
}

export function issueDashboardWebSocketSession(
  secret: string,
  nowMilliseconds = Date.now(),
): DashboardWebSocketSession {
  if (!secret.trim()) {
    throw new Error("dashboard WebSocket session secret is blank");
  }
  const expires =
    Math.floor(nowMilliseconds / 1000) + DASHBOARD_WS_SESSION_TTL_SECONDS;
  const payload = `v1.${expires}`;
  const signature = createHmac("sha256", secret)
    .update(`${DASHBOARD_WS_SESSION_CONTEXT}:${payload}`, "utf8")
    .digest("base64url");
  return {
    token: `${payload}.${signature}`,
    maxAge: DASHBOARD_WS_SESSION_TTL_SECONDS,
  };
}
