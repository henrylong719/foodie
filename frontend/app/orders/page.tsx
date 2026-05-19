import Link from "next/link";
import { listOrders } from "@/lib/api";
import {
  Card,
  EmptyState,
  ErrorNote,
  BrandSourceTag,
  PageContent,
  PageHeader,
  SectionTitle,
  StatusBadge,
} from "@/components/ui";

export const dynamic = "force-dynamic";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default async function OrdersPage() {
  try {
    const { orders, count } = await listOrders();

    return (
      <div>
        <PageHeader
          title="Captured Orders"
          subtitle={`${count} orders captured from completed calls`}
        />

        <PageContent>
          <SectionTitle
            title="Order review"
            subtitle="Each card shows the captured grocery items and how Foodie selected each brand."
          />
          {orders.length === 0 ? (
            <EmptyState
              title="No orders captured yet"
              action={
                <Link
                  href="/customers"
                  className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                >
                  View customers
                </Link>
              }
            >
              Each completed call writes one order here, with every item,
              quantity, and how its brand was decided.
            </EmptyState>
          ) : (
            <div className="space-y-4">
              {orders.map((o) => (
                <Card
                  key={o._id}
                  className="overflow-hidden transition hover:border-[color:rgba(33,122,74,0.22)]"
                >
                  <div className="flex flex-wrap items-start gap-3 border-b bg-[var(--color-surface-2)] px-4 py-4 sm:items-center sm:gap-4 sm:px-5">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-xs font-semibold text-[var(--color-accent)] shadow-sm">
                      {o.customer_name.slice(0, 2).toUpperCase()}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-[var(--color-text)]">
                        {o.customer_name}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-[var(--color-text-dim)]">
                        <span>{formatDate(o.created_at)}</span>
                        <span>{o.item_count} item{o.item_count === 1 ? "" : "s"}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={o.status} />
                    </div>
                  </div>

                  <div>
                    {o.items.map((item, i) => (
                      <div
                        key={i}
                        className={`flex items-center gap-3 px-4 py-3.5 text-sm transition hover:bg-[color:rgba(241,245,238,0.72)] sm:gap-4 sm:px-5 ${
                          i > 0 ? "border-t" : ""
                        }`}
                      >
                        <span
                          className="flex h-8 w-10 shrink-0 items-center justify-center rounded-lg bg-[color:rgba(33,122,74,0.08)] font-semibold text-[var(--color-accent)]"
                          style={{ fontFamily: "var(--font-mono)" }}
                        >
                          ×{item.quantity}
                        </span>
                        <span className="min-w-0 flex-1 text-[var(--color-text)]">
                          {item.name}
                        </span>
                        <BrandSourceTag source={item.brand_source} />
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </PageContent>
      </div>
    );
  } catch (e) {
    return (
      <div>
        <PageHeader title="Captured Orders" />
        <ErrorNote message={(e as Error).message} />
      </div>
    );
  }
}
