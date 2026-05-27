'use client';

import Link from 'next/link';
import { use, useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { getCall, getCallTranscriptStreamUrl } from '@/lib/api';
import type { CallRecord, TranscriptLine } from '@/lib/types';
import {
  Card,
  EmptyState,
  PageContent,
  PageHeader,
  StatusBadge,
  cx,
} from '@/components/ui';

type StreamState = 'connecting' | 'connected' | 'reconnecting';

function lineKey(line: TranscriptLine): string {
  return `${line.role}|${line.ts ?? 0}|${line.text}`;
}

function isTranscriptLine(value: unknown): value is TranscriptLine {
  if (!value || typeof value !== 'object') return false;
  const line = value as Partial<TranscriptLine>;
  return (
    (line.role === 'assistant' || line.role === 'customer') &&
    typeof line.text === 'string'
  );
}

/*
  Call detail view.

  Saved transcript lines are loaded from the call record first. The page also
  subscribes to the live SSE stream so an active call keeps updating.
*/
export default function CallDetailPage({
  params,
}: {
  params: Promise<{ callId: string }>;
}) {
  const { callId } = use(params);
  const searchParams = useSearchParams();
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [callRecord, setCallRecord] = useState<CallRecord | null>(null);
  const [streamState, setStreamState] = useState<StreamState>('connecting');
  const scrollRef = useRef<HTMLDivElement>(null);
  const seenKeysRef = useRef<Set<string>>(new Set());
  const hasSavedTranscript = lines.length > 0;
  const shouldStream = searchParams.get('live') === '1';

  // Merge dedupes by role+ts+text — safe to call from the initial fetch,
  // every SSE message, and the on-reconnect backfill without duplicating lines.
  const mergeLines = useCallback((incoming: TranscriptLine[]) => {
    if (incoming.length === 0) return;
    setLines((prev) => {
      const next = prev.slice();
      for (const line of incoming) {
        const key = lineKey(line);
        if (seenKeysRef.current.has(key)) continue;
        seenKeysRef.current.add(key);
        next.push(line);
      }
      return next;
    });
  }, []);

  // Vapi finalizes transcript segments on silence, not turn boundaries, so a
  // single utterance can arrive as several same-role lines. Merge consecutive
  // same-role lines into one bubble for display; the underlying lines array
  // stays intact.
  const groupedLines = lines.reduce<TranscriptLine[]>((acc, line) => {
    const last = acc[acc.length - 1];
    if (last && last.role === line.role) {
      acc[acc.length - 1] = { ...last, text: `${last.text} ${line.text}`.trim() };
      return acc;
    }
    acc.push(line);
    return acc;
  }, []);

  useEffect(() => {
    let alive = true;
    getCall(callId)
      .then((record) => {
        if (!alive) return;
        setCallRecord(record);
        if (record.transcript?.length) {
          mergeLines(record.transcript);
        }
      })
      .catch(() => {
        if (alive) setCallRecord(null);
      });
    return () => {
      alive = false;
    };
  }, [callId, mergeLines]);

  useEffect(() => {
    if (!shouldStream) return;

    // SSE connection to the backend transcript relay. EventSource auto-
    // reconnects on transport errors; on each successful (re)connect after
    // the first we refetch the call record to backfill anything missed
    // during the gap. Dedup in mergeLines makes the backfill safe.
    const streamUrl = getCallTranscriptStreamUrl(callId);
    const source = new EventSource(streamUrl);
    let hasConnectedOnce = false;

    setStreamState('connecting');
    source.onopen = () => {
      const isReconnect = hasConnectedOnce;
      hasConnectedOnce = true;
      setStreamState('connected');
      if (isReconnect) {
        getCall(callId)
          .then((record) => {
            setCallRecord(record);
            if (record.transcript?.length) mergeLines(record.transcript);
          })
          .catch(() => {});
      }
    };

    source.onmessage = (event) => {
      try {
        const line = JSON.parse(event.data);
        if (isTranscriptLine(line)) {
          mergeLines([line]);
        }
      } catch {
        // ignore keep-alive / non-JSON pings
      }
    };

    source.onerror = () => {
      // EventSource handles reconnect itself; surface the state and wait.
      setStreamState('reconnecting');
    };

    return () => source.close();
  }, [callId, shouldStream, mergeLines]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [lines]);

  return (
    <div>
      <PageHeader
        title={hasSavedTranscript ? "Call Transcript" : "Call Record"}
        subtitle={
          callRecord
            ? `${callRecord.customer_name || 'Unknown customer'} - call ${callId}`
            : `call ${callId}`
        }
      />

      {shouldStream && (
        <div className="border-b bg-[color:rgba(255,255,255,0.56)] backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              streamState === 'connected' ? 'live-dot' : ''
            }`}
            style={{
              background:
                streamState === 'connected'
                  ? 'var(--color-good)'
                  : 'var(--color-text-dim)',
            }}
          />
          <StatusBadge
            status={streamState === 'connected' ? 'active' : 'waiting'}
          >
            {streamState === 'connected'
              ? 'stream listener connected'
              : streamState === 'reconnecting'
                ? 'reconnecting to call stream'
                : 'waiting for call stream'}
          </StatusBadge>
          <Link
            href="/calls"
            className="ml-auto inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
          >
            View history
          </Link>
        </div>
      </div>
      )}

      <PageContent>
        {callRecord && (
          <Card className="mb-4 overflow-hidden">
            <div className="grid gap-4 px-4 py-4 text-sm sm:grid-cols-[minmax(180px,1fr)_120px_minmax(240px,1.5fr)_120px] sm:px-5">
              <div className="min-w-0">
                <div className="truncate font-semibold text-[var(--color-text)]">
                  {callRecord.customer_name || 'Unknown customer'}
                </div>
                <div
                  className="mt-1 truncate text-xs text-[var(--color-text-dim)]"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {callRecord.phone || '-'}
                </div>
              </div>
              <div className="flex items-start gap-2">
                <StatusBadge
                  status={callRecord.status}
                  className="whitespace-nowrap"
                />
                {callRecord.dry_run && (
                  <StatusBadge status="dry_run" className="whitespace-nowrap">
                    dry run
                  </StatusBadge>
                )}
              </div>
              <div className="min-w-0 text-xs leading-5 text-[var(--color-text-dim)]">
                {callRecord.compliance.message ||
                  'Compliance gate allowed the call.'}
              </div>
              <div className="flex items-start justify-start sm:justify-end">
                {callRecord.recording_url ? (
                  <a
                    href={callRecord.recording_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                  >
                    Recording
                  </a>
                ) : (
                  <span className="text-xs font-medium text-[var(--color-text-dim)]">
                    No recording
                  </span>
                )}
              </div>
            </div>
          </Card>
        )}

        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b bg-[var(--color-surface-2)] px-4 py-4 sm:px-5">
            <div>
              <h2 className="text-sm font-semibold text-[var(--color-text)]">
                Transcript
              </h2>
              <p className="mt-1 text-xs text-[var(--color-text-dim)]">
                Saved transcript lines appear here; active calls continue
                streaming new lines.
              </p>
            </div>
            <span
              className="text-xs text-[var(--color-text-dim)]"
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {lines.length} lines
            </span>
          </div>
          <div
            ref={scrollRef}
            className="h-[62vh] space-y-4 overflow-y-auto bg-[color:rgba(255,255,255,0.72)] p-4 sm:p-5"
          >
            {lines.length === 0 ? (
              <EmptyState title="No transcript saved">
                {callRecord?.transcript_fetch_error
                  ? `Could not fetch this transcript from Vapi: ${callRecord.transcript_fetch_error}`
                  : 'This call record does not have saved transcript lines yet. If Vapi has a transcript for it, refresh once the backend has fetched and cached the Vapi call artifact.'}
              </EmptyState>
            ) : (
              groupedLines.map((line, i) => (
                <div
                  key={i}
                  className={cx(
                    'row-in flex',
                    line.role === 'assistant' ? 'justify-start' : 'justify-end',
                  )}
                >
                  <div
                    className={cx(
                      'max-w-[min(42rem,88%)] rounded-2xl border px-4 py-3 text-sm shadow-sm',
                      line.role === 'assistant'
                        ? 'bg-[var(--color-surface-2)] text-[var(--color-text)]'
                        : 'border-[color:rgba(33,122,74,0.18)] bg-[color:rgba(33,122,74,0.08)] text-[var(--color-text)]',
                    )}
                  >
                    <div
                      className={cx(
                        'mb-1 text-[11px] font-semibold uppercase tracking-[0.1em]',
                        line.role === 'assistant'
                          ? 'text-[var(--color-accent)]'
                          : 'text-[var(--color-text-dim)]',
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
