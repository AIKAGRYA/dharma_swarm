import assert from "node:assert/strict";
import test from "node:test";

import {
  DASHBOARD_WS_SESSION_TTL_SECONDS,
  isTrustedDashboardSessionRequest,
  issueDashboardWebSocketSession,
} from "./wsSession";

test("dashboard WebSocket session token is short-lived and digest-bound", () => {
  const session = issueDashboardWebSocketSession(
    "fixture-token-not-live",
    1_700_000_000_000,
  );

  assert.equal(session.maxAge, DASHBOARD_WS_SESSION_TTL_SECONDS);
  assert.equal(
    session.token,
    "v1.1700000300.S2MVkDTomFFWCy9ot2PT-W1NobJepZ6LJze6ZR9Z_kI",
  );
  assert.doesNotMatch(session.token, /fixture-token-not-live/);
  assert.throws(
    () => issueDashboardWebSocketSession("   ", 1_700_000_000_000),
    /secret is blank/,
  );
});

test("dashboard WebSocket sessions are minted only for loopback same-origin", () => {
  assert.equal(
    isTrustedDashboardSessionRequest(
      "127.0.0.1:3420",
      "http://127.0.0.1:3420",
    ),
    true,
  );
  assert.equal(
    isTrustedDashboardSessionRequest("localhost:3420", "http://localhost:3420"),
    true,
  );
  assert.equal(
    isTrustedDashboardSessionRequest("[::1]:3420", "http://[::1]:3420"),
    true,
  );
  assert.equal(isTrustedDashboardSessionRequest("127.0.0.1:3420", ""), false);
  assert.equal(
    isTrustedDashboardSessionRequest(
      "dashboard.example:3420",
      "https://dashboard.example:3420",
    ),
    false,
  );
  assert.equal(
    isTrustedDashboardSessionRequest(
      "127.0.0.1:3420",
      "https://evil.example",
    ),
    false,
  );
});
