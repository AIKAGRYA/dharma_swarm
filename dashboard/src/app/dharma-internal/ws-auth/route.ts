import { NextRequest, NextResponse } from "next/server";

import {
  DASHBOARD_WS_SESSION_COOKIE,
  isTrustedDashboardSessionRequest,
  issueDashboardWebSocketSession,
} from "@/lib/wsSession";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (
    !isTrustedDashboardSessionRequest(
      request.headers.get("host") ?? "",
      request.headers.get("origin") ?? "",
    )
  ) {
    return NextResponse.json(
      { error: "dashboard WebSocket sessions are loopback same-origin only" },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  const response = new NextResponse(null, {
    status: 204,
    headers: { "Cache-Control": "no-store" },
  });
  const secret = process.env.DASHBOARD_API_KEY;
  const secure = request.nextUrl.protocol === "https:";

  if (secret === undefined) {
    response.cookies.set(DASHBOARD_WS_SESSION_COOKIE, "", {
      httpOnly: true,
      sameSite: "strict",
      secure,
      path: "/ws",
      maxAge: 0,
    });
    return response;
  }

  if (!secret.trim()) {
    const invalid = NextResponse.json(
      {
        error:
          "DASHBOARD_API_KEY is set but blank; unset it for loopback dev mode or configure a nonblank secret",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
    invalid.cookies.set(DASHBOARD_WS_SESSION_COOKIE, "", {
      httpOnly: true,
      sameSite: "strict",
      secure,
      path: "/ws",
      maxAge: 0,
    });
    return invalid;
  }

  const session = issueDashboardWebSocketSession(secret);
  response.cookies.set(DASHBOARD_WS_SESSION_COOKIE, session.token, {
    httpOnly: true,
    sameSite: "strict",
    secure,
    path: "/ws",
    maxAge: session.maxAge,
  });
  return response;
}
