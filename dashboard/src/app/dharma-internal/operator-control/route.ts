import { handleOperatorControlBridge } from "@/lib/sadhanaOperatorControlBridge";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request): Promise<Response> {
  return handleOperatorControlBridge(request);
}
