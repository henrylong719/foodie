import Link from "next/link";
import { listCustomers } from "@/lib/api";
import {
  Card,
  EmptyState,
  ErrorNote,
  PageContent,
  PageHeader,
  SectionTitle,
  StatusBadge,
} from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function CustomersPage() {
  try {
    const { customers, count } = await listCustomers();

    return (
      <div>
        <PageHeader
          title="Customers"
          subtitle={`${count} existing customers available for Foodie's outbound ordering workflow.`}
        />

        <PageContent>
          <SectionTitle
            title="Customer outreach"
            subtitle="Call actions are hidden for customers flagged do-not-call."
          />
          {customers.length === 0 ? (
            <EmptyState title="No customers found">
              Customer records will appear here once the backend returns them,
              including call eligibility and preferred language.
            </EmptyState>
          ) : (
            <Card className="overflow-x-auto [scrollbar-gutter:stable]">
              <div className="min-w-[720px]">
                <div className="grid grid-cols-[minmax(240px,1fr)_180px_150px_110px] items-center gap-4 border-b bg-[var(--color-surface-2)] px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-dim)]">
                  <span>Name</span>
                  <span>Phone</span>
                  <span>Status</span>
                  <span className="text-right">Action</span>
                </div>
                {customers.map((c) => (
                  <div
                    key={c._id}
                    className="grid grid-cols-[minmax(240px,1fr)_180px_150px_110px] items-center gap-4 border-t px-5 py-4 text-sm transition first:border-t-0 hover:bg-[color:rgba(241,245,238,0.72)]"
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[color:rgba(33,122,74,0.09)] text-xs font-semibold text-[var(--color-accent)]">
                        {c.name.slice(0, 2).toUpperCase()}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-[var(--color-text)]">
                          {c.name}
                        </span>
                        <span className="mt-0.5 block text-xs text-[var(--color-text-dim)]">
                          {c.preferred_language}
                        </span>
                      </span>
                    </span>
                    <span
                      className="text-[var(--color-text-dim)]"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {c.phone}
                    </span>
                    <span>
                      {c.do_not_call ? (
                        <StatusBadge
                          status="do_not_call"
                          className="whitespace-nowrap"
                        />
                      ) : (
                        <StatusBadge
                          status="callable"
                          className="whitespace-nowrap"
                        />
                      )}
                    </span>
                    <span className="text-right">
                      {c.do_not_call ? (
                        <span className="text-xs font-medium text-[var(--color-text-dim)]">
                          Locked
                        </span>
                      ) : (
                        <Link
                          href={`/calls/new?customer=${c._id}`}
                          className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:-translate-y-px hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                        >
                          Call
                        </Link>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
          <p className="mt-3 max-w-3xl text-xs leading-5 text-[var(--color-text-dim)]">
            Customers flagged "do not call" cannot be dialled - the compliance
            gate is enforced before any call is placed.
          </p>
        </PageContent>
      </div>
    );
  } catch (e) {
    return (
      <div>
        <PageHeader title="Customers" />
        <ErrorNote message={(e as Error).message} />
      </div>
    );
  }
}
