'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { CallBlockedError, listCustomers, placeCall } from '@/lib/api';
import type { ComplianceResult, Customer } from '@/lib/types';
import {
  Card,
  EmptyState,
  PageContent,
  PageHeader,
  SectionTitle,
  StatusBadge,
} from '@/components/ui';

/*
  New-call route.

  The Customers page links here as /calls/new?customer={id}. This page
  places the outbound call: the backend runs the compliance gate first, so
  one of three things happens —
    - placed   -> redirect to the live-call view (/calls/{vapi_call_id})
    - blocked  -> show the compliance reason inline; no redirect
    - error    -> show the error inline
  The call is placed once, on mount, for the given customer.
*/

type Phase =
  | { kind: 'loading' }
  | { kind: 'placing'; customer: Customer }
  | { kind: 'blocked'; customer: Customer; compliance: ComplianceResult }
  | { kind: 'error'; message: string };

// Module-level guard against the effect firing twice for the same customer
// in quick succession — React 18 StrictMode double-mounts in dev, and the
// in-flight POST can't be aborted from the cleanup. Backend dedupe handles
// the rest (refresh, hard reload, etc.).
const inFlight = new Set<string>();

function NewCallInner() {
  const router = useRouter();
  const params = useSearchParams();
  const customerId = params.get('customer');
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' });

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!customerId) {
        setPhase({
          kind: 'error',
          message:
            'No customer specified. Open this page from the Customers list.',
        });
        return;
      }

      if (inFlight.has(customerId)) return;
      inFlight.add(customerId);

      try {
        // Resolve the customer for display (the backend re-checks everything).
        let customer: Customer | undefined;
        try {
          const { customers } = await listCustomers();
          customer = customers.find((c) => c._id === customerId);
        } catch (e) {
          if (!cancelled)
            setPhase({ kind: 'error', message: (e as Error).message });
          return;
        }
        if (!customer) {
          if (!cancelled)
            setPhase({ kind: 'error', message: 'Customer not found.' });
          return;
        }
        if (cancelled) return;
        setPhase({ kind: 'placing', customer });

        // Place the call — the compliance gate runs server-side.
        try {
          const result = await placeCall(customerId);
          if (cancelled) return;
          // Success — hand off to the live-call view.
          router.replace(`/calls/${result.call_id}?live=1`);
        } catch (e) {
          if (cancelled) return;
          if (e instanceof CallBlockedError) {
            setPhase({ kind: 'blocked', customer, compliance: e.compliance });
          } else {
            setPhase({ kind: 'error', message: (e as Error).message });
          }
        }
      } finally {
        inFlight.delete(customerId);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [customerId, router]);

  return (
    <div>
      <PageHeader
        title="Place a Call"
        subtitle="The compliance gate runs before any number is dialled."
      />
      <PageContent>
        <SectionTitle
          title="Outbound call"
          subtitle="Do-not-call status and calling hours are checked server-side."
        />
        {phase.kind === 'loading' && (
          <EmptyState title="Preparing call">
            Looking up the customer record.
          </EmptyState>
        )}

        {phase.kind === 'placing' && (
          <Card className="px-5 py-6">
            <div className="flex items-center gap-3">
              <span
                className="h-2.5 w-2.5 rounded-full live-dot"
                style={{ background: 'var(--color-good)' }}
              />
              <div>
                <div className="font-medium text-[var(--color-text)]">
                  Placing call to {phase.customer.name}
                </div>
                <div
                  className="mt-0.5 text-xs text-[var(--color-text-dim)]"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {phase.customer.phone}
                </div>
              </div>
            </div>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-[var(--color-text-dim)]">
              Running the compliance gate and creating the call. You'll be taken
              to the live transcript as soon as the call connects.
            </p>
          </Card>
        )}

        {phase.kind === 'blocked' && (
          <Card className="overflow-hidden">
            <div className="border-b bg-[color:rgba(194,65,58,0.07)] px-5 py-4">
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge status="do_not_call">call blocked</StatusBadge>
                <span className="text-sm font-medium text-[var(--color-text)]">
                  {phase.customer.name} was not dialled
                </span>
              </div>
            </div>
            <div className="px-5 py-5">
              <dl className="grid gap-3 text-sm sm:grid-cols-[140px_1fr]">
                <dt className="text-[var(--color-text-dim)]">Reason</dt>
                <dd
                  className="font-medium text-[var(--color-text)]"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {phase.compliance.reason ?? 'unknown'}
                </dd>
                <dt className="text-[var(--color-text-dim)]">Detail</dt>
                <dd className="text-[var(--color-text)]">
                  {phase.compliance.message}
                </dd>
                <dt className="text-[var(--color-text-dim)]">Checked</dt>
                <dd className="text-[var(--color-text-dim)]">
                  {phase.compliance.checked_at} ({phase.compliance.timezone})
                </dd>
              </dl>
              <p className="mt-5 max-w-2xl text-xs leading-5 text-[var(--color-text-dim)]">
                The call was recorded as blocked for the audit trail. No number
                was dialled.
              </p>
              <Link
                href="/customers"
                className="mt-5 inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
              >
                Back to Customers
              </Link>
            </div>
          </Card>
        )}

        {phase.kind === 'error' && (
          <Card className="px-5 py-6">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge status="failed">could not place call</StatusBadge>
            </div>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text)]">
              {phase.message}
            </p>
            <Link
              href="/customers"
              className="mt-5 inline-flex h-9 items-center rounded-full border px-4 text-xs font-semibold text-[var(--color-text-dim)] transition hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            >
              Back to Customers
            </Link>
          </Card>
        )}
      </PageContent>
    </div>
  );
}

export default function NewCallPage() {
  // useSearchParams requires a Suspense boundary in the App Router.
  return (
    <Suspense
      fallback={
        <div>
          <PageHeader title="Place a Call" />
          <PageContent>
            <EmptyState title="Preparing call">One moment…</EmptyState>
          </PageContent>
        </div>
      }
    >
      <NewCallInner />
    </Suspense>
  );
}
