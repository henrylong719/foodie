'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getHealth, resetDemo } from '@/lib/api';

// Renders nothing unless the backend has DEMO_MODE=true. Lets the operator
// wipe captured orders + un-DNC the demo customer between takes.
export function DemoResetButton() {
  const router = useRouter();
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getHealth()
      .then((h) => {
        if (alive) setEnabled(Boolean(h.demo_mode));
      })
      .catch(() => {
        if (alive) setEnabled(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (!enabled) return null;

  async function handleClick() {
    if (busy) return;
    const confirmed = window.confirm(
      'Reset demo state? This clears captured orders + call history and un-flags the demo customer.',
    );
    if (!confirmed) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await resetDemo();
      setMessage(
        `Reset done — ${result.captured_orders_deleted} order(s), ${result.calls_deleted} call(s) cleared.`,
      );
      router.refresh();
    } catch (err) {
      setMessage(`Reset failed: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      {message && (
        <span className="text-xs text-[var(--color-text-dim)]">{message}</span>
      )}
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className="inline-flex h-9 items-center rounded-full border border-[color:rgba(184,107,23,0.3)] bg-[color:rgba(184,107,23,0.08)] px-4 text-xs font-semibold text-[var(--color-warn)] transition hover:border-[var(--color-warn)] hover:bg-[var(--color-warn)] hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        {busy ? 'Resetting…' : 'Reset demo'}
      </button>
    </div>
  );
}
