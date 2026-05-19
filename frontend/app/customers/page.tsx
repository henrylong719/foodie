import Link from "next/link";
import { listCustomers } from "@/lib/api";
import { PageHeader, ErrorNote } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function CustomersPage() {
  try {
    const { customers, count } = await listCustomers();

    return (
      <div>
        <PageHeader
          title="Customers"
          subtitle={`${count} existing customers — select one to place a call`}
        />

        <div className="px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
          <div className="overflow-x-auto rounded-2xl border bg-[color:rgba(255,255,255,0.86)] shadow-sm">
            <div className="min-w-[680px]">
              <div className="flex items-center gap-4 border-b bg-[var(--color-surface-2)] px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-dim)]">
                <span className="flex-1">Name</span>
                <span className="w-40">Phone</span>
                <span className="w-32">Status</span>
                <span className="w-24 text-right">Action</span>
              </div>
              {customers.map((c) => (
                <div
                  key={c._id}
                  className="flex items-center gap-4 border-t px-5 py-4 text-sm transition first:border-t-0 hover:bg-[var(--color-surface-2)]"
                >
                  <span className="min-w-0 flex-1 truncate font-medium text-[var(--color-text)]">
                    {c.name}
                  </span>
                  <span
                    className="w-40 text-[var(--color-text-dim)]"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {c.phone}
                  </span>
                  <span className="w-32">
                    {c.do_not_call ? (
                      <span className="rounded-full border border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-danger)]">
                        do not call
                      </span>
                    ) : (
                      <span className="rounded-full border border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-good)]">
                        callable
                      </span>
                    )}
                  </span>
                  <span className="w-24 text-right">
                    {c.do_not_call ? (
                      <span className="text-xs text-[var(--color-text-dim)]">
                        —
                      </span>
                    ) : (
                      <Link
                        href={`/calls/new?customer=${c._id}`}
                        className="inline-flex rounded-full border border-[color:rgba(15,118,110,0.22)] bg-[color:rgba(15,118,110,0.08)] px-3.5 py-1.5 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                      >
                        Call
                      </Link>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-3 max-w-3xl text-xs leading-5 text-[var(--color-text-dim)]">
            Customers flagged “do not call” cannot be dialled — the compliance
            gate is enforced before any call is placed.
          </p>
        </div>
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
