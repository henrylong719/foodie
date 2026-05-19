"use client";

import { use, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import {
  Card,
  EmptyState,
  PageContent,
  PageHeader,
  StatusBadge,
  cx,
} from "@/components/ui";

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

      <div className="border-b bg-[color:rgba(255,255,255,0.56)] backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <span
            className={`h-2.5 w-2.5 rounded-full ${connected ? "live-dot" : ""}`}
            style={{
              background: connected
                ? "var(--color-good)"
                : "var(--color-text-dim)",
            }}
          />
          <StatusBadge status={connected ? "active" : "waiting"}>
            {connected ? "connected - listening" : "waiting for call stream"}
          </StatusBadge>
          <span
            className="text-xs text-[var(--color-text-dim)]"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {API_BASE}/calls/{callId}/stream
          </span>
        </div>
      </div>

      <PageContent>
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b bg-[var(--color-surface-2)] px-4 py-4 sm:px-5">
            <div>
              <h2 className="text-sm font-semibold text-[var(--color-text)]">
                Transcript
              </h2>
              <p className="mt-1 text-xs text-[var(--color-text-dim)]">
                Live assistant and customer messages stream into this log.
              </p>
            </div>
            <span
              className="text-xs text-[var(--color-text-dim)]"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {lines.length} lines
            </span>
          </div>
          <div
            ref={scrollRef}
            className="h-[62vh] space-y-4 overflow-y-auto bg-[color:rgba(255,255,255,0.72)] p-4 sm:p-5"
          >
          {lines.length === 0 ? (
            <EmptyState title="Waiting for transcript">
              The transcript will stream here line by line as the call
              progresses. Once the stream connects, assistant and customer
              messages will separate into a readable call log.
            </EmptyState>
          ) : (
            lines.map((line, i) => (
              <div
                key={i}
                className={cx(
                  "row-in flex",
                  line.role === "assistant" ? "justify-start" : "justify-end",
                )}
              >
                <div
                  className={cx(
                    "max-w-[min(42rem,88%)] rounded-2xl border px-4 py-3 text-sm shadow-sm",
                    line.role === "assistant"
                      ? "bg-[var(--color-surface-2)] text-[var(--color-text)]"
                      : "border-[color:rgba(33,122,74,0.18)] bg-[color:rgba(33,122,74,0.08)] text-[var(--color-text)]",
                  )}
                >
                  <div
                    className={cx(
                      "mb-1 text-[11px] font-semibold uppercase tracking-[0.1em]",
                      line.role === "assistant"
                        ? "text-[var(--color-accent)]"
                        : "text-[var(--color-text-dim)]",
                    )}
                  >
                    {line.role}
                  </div>
                  <div className="leading-6">{line.text}</div>
                </div>
              </div>
            ))
          )}
          </div>
        </Card>
      </PageContent>
    </div>
  );
}
