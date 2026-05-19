"use client";

import { use, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { PageHeader } from "@/components/ui";

// One line of the live transcript.
interface TranscriptLine {
  role: "assistant" | "customer";
  text: string;
  ts: number;
}

/*
  Live call view.

  Live transcripts arrive over Server-Sent Events from the backend, which
  relays Vapi's transcript webhooks. The SSE endpoint (/calls/{id}/stream)
  is built in the next step; this client is complete and will light up the
  moment that endpoint exists. Until then the page shows a waiting state.
*/
export default function LiveCallPage({
  params,
}: {
  params: Promise<{ callId: string }>;
}) {
  const { callId } = use(params);
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // SSE connection to the backend transcript relay.
    const url = `${API_BASE}/calls/${callId}/stream`;
    const source = new EventSource(url);

    source.onopen = () => setConnected(true);

    source.onmessage = (event) => {
      try {
        const line = JSON.parse(event.data) as TranscriptLine;
        setLines((prev) => [...prev, line]);
      } catch {
        // ignore keep-alive / non-JSON pings
      }
    };

    source.onerror = () => {
      // endpoint not live yet (next step) or call ended — close quietly
      setConnected(false);
      source.close();
    };

    return () => source.close();
  }, [callId]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [lines]);

  return (
    <div>
      <PageHeader title="Live Call" subtitle={`call ${callId}`} />

      <div className="flex items-center gap-2 border-b bg-[color:rgba(255,255,255,0.5)] px-4 py-4 backdrop-blur sm:px-6 lg:px-10">
        <span
          className={`h-2.5 w-2.5 rounded-full ${connected ? "live-dot" : ""}`}
          style={{
            background: connected
              ? "var(--color-good)"
              : "var(--color-text-dim)",
          }}
        />
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-dim)]">
          {connected ? "connected — listening" : "waiting for call stream"}
        </span>
      </div>

      <div className="px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <div
          ref={scrollRef}
          className="h-[62vh] space-y-3 overflow-y-auto rounded-2xl border bg-[color:rgba(255,255,255,0.86)] p-4 shadow-sm sm:p-5"
        >
          {lines.length === 0 ? (
            <p className="max-w-2xl text-sm leading-6 text-[var(--color-text-dim)]">
              The transcript will stream here line by line as the call
              progresses. The live relay endpoint is wired up in the next
              build step.
            </p>
          ) : (
            lines.map((line, i) => (
              <div
                key={i}
                className="row-in flex gap-3 rounded-xl px-3 py-2 text-sm transition hover:bg-[var(--color-surface-2)]"
              >
                <span
                  className={`w-20 shrink-0 text-xs font-semibold uppercase tracking-wide ${
                    line.role === "assistant"
                      ? "text-[var(--color-accent)]"
                      : "text-[var(--color-text-dim)]"
                  }`}
                >
                  {line.role}
                </span>
                <span className="leading-6 text-[var(--color-text)]">
                  {line.text}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
