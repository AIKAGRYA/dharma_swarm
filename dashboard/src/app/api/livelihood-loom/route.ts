import { NextResponse } from "next/server";
import { loadLivelihoodLoomDashboard } from "@/lib/livelihoodLoom";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET() {
  return NextResponse.json(loadLivelihoodLoomDashboard());
}

