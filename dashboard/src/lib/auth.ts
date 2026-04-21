const DASHBOARD_API_TOKEN_STORAGE_KEY = "dharma.dashboard.api-token";
const DESKTOP_BOOTSTRAP_HASH_KEY = "desktop_api_key";

let desktopBootstrapHashConsumed = false;

function storage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readDashboardApiToken(): string | null {
  const value = storage()?.getItem(DASHBOARD_API_TOKEN_STORAGE_KEY)?.trim();
  return value ? value : null;
}

export function writeDashboardApiToken(token: string): boolean {
  const normalized = token.trim();
  if (!normalized) {
    return false;
  }
  const target = storage();
  if (!target) {
    return false;
  }
  target.setItem(DASHBOARD_API_TOKEN_STORAGE_KEY, normalized);
  return true;
}

export function clearDashboardApiToken(): void {
  storage()?.removeItem(DASHBOARD_API_TOKEN_STORAGE_KEY);
}

export function authorizedHeaders(headersInit?: HeadersInit): Headers {
  const headers = new Headers(headersInit);
  if (!headers.has("Authorization")) {
    const token = readDashboardApiToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }
  return headers;
}

export function consumeDesktopShellBootstrapHash(): string | null {
  if (desktopBootstrapHashConsumed || typeof window === "undefined") {
    return null;
  }
  desktopBootstrapHashConsumed = true;

  const rawHash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  if (!rawHash) {
    return null;
  }

  const params = new URLSearchParams(rawHash);
  const token = params.get(DESKTOP_BOOTSTRAP_HASH_KEY)?.trim() ?? "";
  if (!token) {
    return null;
  }

  writeDashboardApiToken(token);
  params.delete(DESKTOP_BOOTSTRAP_HASH_KEY);

  const nextHash = params.toString();
  const nextUrl = `${window.location.pathname}${window.location.search}${
    nextHash ? `#${nextHash}` : ""
  }`;
  window.history.replaceState(window.history.state, "", nextUrl);
  return token;
}
