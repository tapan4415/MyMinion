import { NextRequest, NextResponse } from "next/server";
export async function POST(request: NextRequest) {
  const body = await request.text();
  try {
    const response = await fetch(`${process.env.AGENT_API_URL ?? "http://localhost:8000"}/v1/agent/respond`, { method: "POST", headers: { "Content-Type": "application/json" }, body, cache: "no-store" });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch { return NextResponse.json({ detail: "Agent service is unavailable. Start the FastAPI service on port 8000." }, { status: 503 }); }
}
