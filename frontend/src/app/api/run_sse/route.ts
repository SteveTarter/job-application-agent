import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { userId, sessionId, newMessage, stateDelta } = body;

    const payload = {
      app_name: "app",
      user_id: userId,
      session_id: sessionId,
      new_message: newMessage,
      state_delta: stateDelta,
      streaming: true,
    };

    const response = await fetch(`${BACKEND_URL}/run_sse`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errText = await response.text();
      return NextResponse.json({ error: errText }, { status: response.status });
    }

    const stream = response.body;
    if (!stream) {
      return NextResponse.json({ error: "No stream body" }, { status: 500 });
    }

    // Pipe the backend SSE stream to the client
    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
