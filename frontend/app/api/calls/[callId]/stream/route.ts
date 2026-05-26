import { NextRequest } from 'next/server';

// Edge runtime: streaming responses are bound to the client connection and
// have no maxDuration cap, unlike Node serverless functions (10s Hobby /
// 15s Pro default). Required for long-lived SSE transcript streams.
export const runtime = 'edge';
export const dynamic = 'force-dynamic';

const BACKEND_API_BASE = (
  process.env.BACKEND_API_BASE ??
  process.env.NEXT_PUBLIC_API_BASE ??
  'http://localhost:8000'
).replace(/\/+$/, '');

type RouteContext = {
  params: Promise<{ callId: string }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const { callId } = await context.params;
  const target = `${BACKEND_API_BASE}/calls/${encodeURIComponent(callId)}/stream`;

  const upstream = await fetch(target, {
    headers: { Accept: 'text/event-stream' },
    cache: 'no-store',
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(`upstream error: ${upstream.status}`, {
      status: upstream.status || 502,
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
