import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const userId = request.nextUrl.searchParams.get("user_id") ?? "demo-user";
  try {
    const response = await fetch(
      `${process.env.AGENT_API_URL ?? "http://localhost:8000"}/v1/moss/inspect?user_id=${encodeURIComponent(userId)}`,
      { cache: "no-store" },
    );
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Agent service is unavailable." }, { status: 503 });
  }
}
